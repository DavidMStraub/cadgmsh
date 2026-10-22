from __future__ import annotations

import gmsh
import meshio
import numpy as np
from numpy.typing import ArrayLike, NDArray

# gmsh node order -> meshio (VTK) node order, for the cell types where they
# differ. Same table as meshio's gmsh reader (private ``_gmsh_to_meshio_order``).
# fmt: off
_GMSH_TO_MESHIO_ORDER: dict[str, list[int]] = {
    "tetra10": [0, 1, 2, 3, 4, 5, 6, 7, 9, 8],
    "hexahedron20": [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 13, 9, 16, 18, 19, 17, 10, 12, 14, 15,
    ],
    "hexahedron27": [
        0, 1, 2, 3, 4, 5, 6, 7, 8, 11, 13, 9, 16, 18, 19, 17, 10, 12, 14, 15,
        22, 23, 21, 24, 20, 25, 26,
    ],
    "wedge15": [0, 1, 2, 3, 4, 5, 6, 9, 7, 12, 14, 13, 8, 10, 11],
    "pyramid13": [0, 1, 2, 3, 4, 5, 8, 10, 6, 7, 9, 11, 12],
}
# fmt: on


def _to_meshio() -> meshio.Mesh:
    """
    Extract the current gmsh model into a :class:`meshio.Mesh`.

    Reads nodes, elements, and any named physical groups from the active gmsh
    session and returns them as a meshio-compatible object.
    Must be called while a gmsh session is active (between ``initialize`` /
    ``finalize``) and after ``gmsh.model.mesh.generate``.
    """
    idx, raw_pts, _ = gmsh.model.mesh.getNodes()
    pts: NDArray[np.float64] = np.asarray(raw_pts).reshape(-1, 3)
    node_idx: NDArray[np.int64] = np.asarray(idx, dtype=np.int64) - 1
    srt = np.argsort(node_idx)
    if not np.all(node_idx[srt] == np.arange(len(node_idx))):
        raise ValueError("gmsh returned non-consecutive node indices")
    pts = pts[srt]

    elem_types, elem_tags, node_tags = gmsh.model.mesh.getElements()

    cells: list[tuple[str, ArrayLike] | meshio.CellBlock] = []
    block_of: dict[int, int] = {}  # gmsh element type -> cell block
    # sorted gmsh element tags per block: a tag's position is its cell index
    block_tags: list[NDArray[np.int64]] = []
    for etype, etags, ntags in zip(elem_types, elem_tags, node_tags, strict=True):
        n: int = gmsh.model.mesh.getElementProperties(etype)[3]
        conn: NDArray[np.int64] = np.asarray(ntags, dtype=np.int64).reshape(-1, n) - 1
        order = np.argsort(np.asarray(etags, dtype=np.int64))
        block_of[int(etype)] = len(cells)
        block_tags.append(np.asarray(etags, dtype=np.int64)[order])
        mtype: str = meshio.gmsh.gmsh_to_meshio_type[etype]
        conn = conn[order]
        if mtype in _GMSH_TO_MESHIO_ORDER:
            conn = conn[:, _GMSH_TO_MESHIO_ORDER[mtype]]
        cells.append(meshio.CellBlock(mtype, conn))

    # Groups of the same name in different dimensions form one cell set.
    members: dict[str, list[list[NDArray[np.int64]]]] = {}
    for dim, tag in gmsh.model.getPhysicalGroups():
        name = gmsh.model.getPhysicalName(dim, tag)
        groups = members.setdefault(name, [[] for _ in cells])
        for etag in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
            etypes_e, etags_e, _ = gmsh.model.mesh.getElements(dim, etag)
            for etype, tags in zip(etypes_e, etags_e, strict=True):
                k = block_of[int(etype)]
                tags_k = np.asarray(tags, dtype=np.int64)
                groups[k].append(np.searchsorted(block_tags[k], tags_k))

    cell_sets: dict[str, list[ArrayLike]] = {
        name: [
            np.unique(np.concatenate(ids)) if ids else np.empty(0, dtype=np.int64)
            for ids in groups
        ]
        for name, groups in members.items()
    }

    return meshio.Mesh(pts, cells, cell_sets=cell_sets)
