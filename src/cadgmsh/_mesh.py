from __future__ import annotations

import gmsh
import meshio

from cadgmsh._extract import _to_meshio
from cadgmsh._occ import _pointer
from cadgmsh._resolve import _resolve_tags
from cadgmsh._types import Shape


def mesh(
    shapes: Shape | list[Shape],
    *,
    lc: float | None = None,
    lc_min: float | None = None,
    imprint: bool = False,
    dim: int = 3,
    order: int = 1,
    algorithm: int | None = None,
    physical: dict[str, Shape | list[Shape]] | None = None,
    verbose: bool = False,
) -> meshio.Mesh:
    """
    Mesh one or more CAD shapes and return a :class:`meshio.Mesh`.

    Parameters
    ----------
    shapes:
        A single cadquery/build123d shape or a list of them.
    lc:
        Characteristic length (maximum element size).
    lc_min:
        Minimum characteristic length.
    imprint:
        If ``True``, boolean-fragment all input shapes so shared faces are
        conformally meshed. Required for conforming multi-domain assemblies.

        .. warning::
            OCC Boolean operations on coincident or touching faces can produce
            a hard segfault inside the OCC kernel that cannot be caught as a
            Python exception. Verify that input shapes have no coincident
            boundary faces before enabling this option.
    dim:
        Maximum mesh dimension (1, 2, or 3).
    order:
        Element order (1 = linear, 2 = quadratic, …).
    algorithm:
        gmsh meshing algorithm number (see gmsh docs). ``None`` = gmsh default.
    physical:
        Dict mapping string labels to shapes (or lists of shapes).
        Each value may be a solid, face, edge, or vertex from cadquery or
        build123d. Labels become named cell sets in the returned mesh.
    verbose:
        Show gmsh terminal output.
    """
    shapes_list: list[Shape] = shapes if isinstance(shapes, list) else [shapes]

    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1 if verbose else 0)
        gmsh.model.add("model")

        if lc is not None:
            gmsh.option.setNumber("Mesh.CharacteristicLengthMax", lc)
        if lc_min is not None:
            gmsh.option.setNumber("Mesh.CharacteristicLengthMin", lc_min)

        all_dim_tags: list[list[tuple[int, int]]] = []
        for s in shapes_list:
            dt = gmsh.model.occ.importShapesNativePointer(
                _pointer(s), highestDimOnly=False
            )
            all_dim_tags.append(list(dt))

        if imprint and len(shapes_list) > 1:
            flat: list[tuple[int, int]] = [
                dt for group in all_dim_tags for dt in group
            ]
            gmsh.model.occ.fragment(flat, [], removeObject=True, removeTool=True)

        gmsh.model.occ.synchronize()

        if physical:
            for label, value in physical.items():
                entries: list[Shape] = value if isinstance(value, list) else [value]
                tags_by_dim: dict[int, list[int]] = {}
                for entry in entries:
                    for d, t in _resolve_tags(entry):
                        tags_by_dim.setdefault(d, []).append(t)
                for d, tags in tags_by_dim.items():
                    pg = gmsh.model.addPhysicalGroup(d, tags)
                    gmsh.model.setPhysicalName(d, pg, label)

        if algorithm is not None:
            gmsh.option.setNumber("Mesh.Algorithm", algorithm)

        gmsh.model.mesh.generate(dim)

        if order != 1:
            gmsh.model.mesh.setOrder(order)

        return _to_meshio()

    finally:
        gmsh.finalize()
