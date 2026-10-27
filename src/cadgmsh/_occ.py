from __future__ import annotations

import io
import math
from typing import Any

from OCP.BinTools import BinTools  # pyright: ignore[reportAttributeAccessIssue]
from OCP.BRep import BRep_Builder  # pyright: ignore[reportAttributeAccessIssue]
from OCP.BRepTools import BRepTools  # pyright: ignore[reportAttributeAccessIssue]
from OCP.gp import gp_Trsf  # pyright: ignore[reportAttributeAccessIssue]
from OCP.Message import (
    Message_ProgressRange,  # pyright: ignore[reportAttributeAccessIssue]
)
from OCP.TopAbs import (
    TopAbs_COMPOUND,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_COMPSOLID,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_EDGE,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_FACE,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_SHELL,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_SOLID,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_VERTEX,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_WIRE,  # pyright: ignore[reportAttributeAccessIssue]
)
from OCP.TopExp import TopExp  # pyright: ignore[reportAttributeAccessIssue]
from OCP.TopLoc import TopLoc_Location  # pyright: ignore[reportAttributeAccessIssue]
from OCP.TopoDS import (
    TopoDS_Builder,  # pyright: ignore[reportAttributeAccessIssue]
    TopoDS_Compound,  # pyright: ignore[reportAttributeAccessIssue]
    TopoDS_Iterator,  # pyright: ignore[reportAttributeAccessIssue]
    TopoDS_Shape,  # pyright: ignore[reportAttributeAccessIssue]
)
from OCP.TopTools import (
    TopTools_FormatVersion,  # pyright: ignore[reportAttributeAccessIssue]
)

# The indexed shape map moved between OCCT major versions: OCCT 7 exposes the
# ready-made ``TopTools_IndexedMapOfShape`` typedef, while OCCT 8 publishes the
# NCollection template instantiations under ``OCP.collections`` instead. Both
# are the same container, so one alias covers both.
#
# Exactly one of these two imports resolves for any given OCCT version, so
# whichever one pyright is checking against, the other is always "broken" --
# and *which* diagnostic it raises depends on the installed stubs (a missing
# module gives reportMissingImports, a present module missing the symbol gives
# reportAttributeAccessIssue). Both codes are suppressed on both branches so
# the type check does not depend on which OCP happens to be installed.
try:
    from OCP.TopTools import (  # pyright: ignore[reportMissingImports]
        TopTools_IndexedMapOfShape as _IndexedMapOfShape,  # pyright: ignore[reportAttributeAccessIssue]
    )
except ImportError:  # OCCT >= 8
    from OCP.collections import (  # pyright: ignore[reportMissingImports]
        IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as _IndexedMapOfShape,  # pyright: ignore[reportAttributeAccessIssue]
    )

from cadgmsh import _adapters
from cadgmsh._types import Shape

_TOPABS_BY_DIM = {3: TopAbs_SOLID, 2: TopAbs_FACE, 1: TopAbs_EDGE, 0: TopAbs_VERTEX}
# Shapes that aren't indexed themselves, only their members are
_CONTAINERS = (TopAbs_COMPOUND, TopAbs_COMPSOLID, TopAbs_SHELL, TopAbs_WIRE)

# __cad_interface__ formats cadgmsh can turn into an OCP shape, most preferred first
_ACCEPT = ("ocp", "brep_text", "brep_binary")


def _unwrap(shape: Shape) -> Any:
    """Return the raw OCP ``TopoDS_*`` object, or pass through if already unwrapped."""
    return _convert(shape)[0]


def _interface(shape: Shape) -> dict[str, Any] | None:
    """
    The ``__cad_interface__`` dict of *shape*: its own, or one for a CadQuery or
    build123d assembly. ``None`` for anything else.
    """
    if hasattr(shape, "__cad_interface__"):
        return shape.__cad_interface__(accept=_ACCEPT)  # pyright: ignore[reportAttributeAccessIssue]
    return _adapters.interface(shape)


def _convert(shape: Shape) -> tuple[Any, dict[str, list[Any]]]:
    """
    Return the raw OCP shape for *shape*, plus the placed shapes below each named
    node if it is an assembly.
    """
    d = _interface(shape)
    if d is None:
        return (shape.wrapped if hasattr(shape, "wrapped") else shape), {}  # pyright: ignore[reportAttributeAccessIssue]
    _check_version(d)
    if d["type"] == "shape":
        return _decode(d), {}

    shapes = [_decode(s) for s in d["shapes"]]  # shared by every node that uses them
    leaves: list[Any] = []
    groups: dict[str, list[Any]] = {}

    def visit(node: dict[str, Any], parent: Any, names: list[str]) -> None:
        world = parent.Multiplied(_trsf(node["location"]))
        if node["name"]:
            names = [*names, node["name"]]
        if node["shape"] is not None:
            placed = shapes[node["shape"]].Moved(TopLoc_Location(world))
            leaves.append(placed)
            for name in names:
                groups.setdefault(name, []).append(placed)
        for child in node["children"]:
            visit(child, world, names)

    visit(d["root"], gp_Trsf(), [])
    return _make_compound(leaves), groups


def _check_version(d: dict[str, Any]) -> None:
    if d.get("version") != 1:
        raise ValueError(f"Unsupported __cad_interface__ version {d.get('version')!r}")


def _decode(d: dict[str, Any]) -> Any:
    """Turn a ``__cad_interface__`` shape dict into a raw OCP shape."""
    _check_version(d)
    fmt, data = d["format"], d["data"]
    if fmt == "ocp":
        if not isinstance(data, TopoDS_Shape):
            raise ValueError(
                f"'ocp' payload is a {type(data).__name__}, not this process's "
                "OCP.TopoDS.TopoDS_Shape"
            )
        return data
    shape = TopoDS_Shape()
    if fmt == "brep_text":
        BRepTools.Read_s(shape, io.BytesIO(data), BRep_Builder())
    elif fmt == "brep_binary":
        BinTools.Read_s(shape, io.BytesIO(data))
    else:
        raise ValueError(f"Unsupported __cad_interface__ format {fmt!r}")
    return shape


def _trsf(m: list[list[float]]) -> Any:
    t = gp_Trsf()
    t.SetValues(*m[0], *m[1], *m[2])
    return t


def _make_compound(shapes: list[Any]) -> Any:
    """Bundle *shapes* into a single ``TopoDS_Compound`` for a one-shot BREP export."""
    builder = TopoDS_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for s in shapes:
        builder.Add(compound, _unwrap(s))
    return compound


def _write_brep(compound: Any, path: str) -> None:
    """
    Write *compound* (as returned by :func:`_make_compound`) to *path*: format
    version 1, which gmsh's bundled OCCT reads, and without any triangulation the
    shapes carry (e.g. after being shown in a viewer), which gmsh doesn't use.
    """
    BRepTools.Write_s(
        compound,
        path,
        False,  # no triangulation
        False,  # no normals
        TopTools_FormatVersion.TopTools_FormatVersion_VERSION_1,
        Message_ProgressRange(),
    )


def _iter_leaves(occ: Any, containers: tuple[Any, ...] = _CONTAINERS) -> Any:
    """
    Yield *occ* itself, or its members recursively if its type is one of
    *containers*: by default the solids, faces, edges and vertices that
    ``ShapeIndex`` indexes, e.g. the faces of a shell.
    """
    if occ.ShapeType() in containers:
        it = TopoDS_Iterator(occ)
        while it.More():
            yield from _iter_leaves(it.Value(), containers)
            it.Next()
    else:
        yield occ


def _count_parts(compound: Any) -> int:
    """Number of non-compound shapes in *compound*, e.g. the parts of an assembly."""
    return sum(1 for _ in _iter_leaves(compound, (TopAbs_COMPOUND,)))


class ShapeIndex:
    """
    Resolves OCC sub-shapes to gmsh ``(dim, tag)`` pairs without pointer identity.

    ``TopExp.MapShapes_s`` assigns each sub-shape the same index that
    ``BRepTools_ShapeSet`` uses when writing/reading BREP, so the index computed
    here matches the gmsh tag assigned when the same compound is imported from a
    BREP file -- this holds even across independently built OCC/OCCT libraries,
    unlike ``importShapesNativePointer``.
    """

    def __init__(self, compound: Any, converted: dict[int, Any] | None = None) -> None:
        # Input objects already converted for *compound*, by id(): converting a
        # __cad_interface__ object again may give a new, unresolvable shape.
        self._converted = converted or {}
        self._maps: dict[int, Any] = {}
        for dim, topabs in _TOPABS_BY_DIM.items():
            m = _IndexedMapOfShape()
            TopExp.MapShapes_s(compound, topabs, m)
            self._maps[dim] = m
        self._by_tshape: dict[int, list[tuple[Any, int, int]]] | None = None

    def resolve(self, shape: Shape | list[Shape]) -> list[tuple[int, int]]:
        """Return ``(dim, tag)`` for *shape*, flattening any compound or list."""
        occ = self._converted.get(id(shape))
        if occ is None:
            if isinstance(shape, list) or (
                not hasattr(shape, "wrapped")
                and not hasattr(shape, "__cad_interface__")
                and not _adapters.is_assembly(shape)
                and hasattr(shape, "__iter__")
            ):
                members: Any = shape
                return [dt for s in members for dt in self.resolve(s)]
            occ = _unwrap(shape)
        results: list[tuple[int, int]] = []
        for leaf in _iter_leaves(occ):
            dim_tag = self._find(leaf)
            if dim_tag is not None:
                results.append(dim_tag)
        return results

    def _find(self, leaf: Any) -> tuple[int, int] | None:
        for dim, m in self._maps.items():
            idx = m.FindIndex(leaf)
            if idx:
                return dim, idx
        # An assembly's placements are rebuilt from matrices, which gives new
        # locations: a part's own faces are then the same geometry at the same
        # place, but no longer the same shape.
        for other, dim, idx in self._partners().get(_tshape_key(leaf), []):
            if other.IsPartner(leaf) and _same_place(other, leaf):
                return dim, idx
        return None

    def _partners(self) -> dict[int, list[tuple[Any, int, int]]]:
        """Every indexed shape by its geometry, built on first use."""
        if self._by_tshape is None:
            self._by_tshape = {}
            for dim, m in self._maps.items():
                for idx in range(1, m.Extent() + 1):
                    s = m.FindKey(idx)
                    self._by_tshape.setdefault(_tshape_key(s), []).append((s, dim, idx))
        return self._by_tshape


def _tshape_key(shape: Any) -> int:
    """A hash of the geometry of *shape*, regardless of location and orientation."""
    return hash(shape.Located(TopLoc_Location()))


def _same_place(a: Any, b: Any) -> bool:
    ta, tb = a.Location().Transformation(), b.Location().Transformation()
    return all(
        math.isclose(ta.Value(i, j), tb.Value(i, j), rel_tol=1e-9, abs_tol=1e-9)
        for i in range(1, 4)
        for j in range(1, 5)
    )
