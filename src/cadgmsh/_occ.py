from __future__ import annotations

import io
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
    TopAbs_EDGE,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_FACE,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_SOLID,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_VERTEX,  # pyright: ignore[reportAttributeAccessIssue]
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

from cadgmsh._types import Shape

_TOPABS_BY_DIM = {3: TopAbs_SOLID, 2: TopAbs_FACE, 1: TopAbs_EDGE, 0: TopAbs_VERTEX}

# __cad_interface__ formats cadgmsh can turn into an OCP shape, most preferred first
_ACCEPT = ("ocp", "brep_text", "brep_binary")


def _unwrap(shape: Shape) -> Any:
    """Return the raw OCP ``TopoDS_*`` object, or pass through if already unwrapped."""
    if hasattr(shape, "__cad_interface__"):
        return _convert(shape)[0]
    return shape.wrapped if hasattr(shape, "wrapped") else shape  # pyright: ignore[reportAttributeAccessIssue]


def _convert(shape: Shape) -> tuple[Any, dict[str, list[Any]]]:
    """
    Return the raw OCP shape for *shape*, plus the placed shapes below each named
    node if it is an assembly (``__cad_interface__``).
    """
    if not hasattr(shape, "__cad_interface__"):
        return _unwrap(shape), {}
    d = shape.__cad_interface__(accept=_ACCEPT)  # pyright: ignore[reportAttributeAccessIssue]
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


def _iter_leaves(occ: Any) -> Any:
    """Yield *occ* itself, or its members recursively if it is a compound."""
    if occ.ShapeType() == TopAbs_COMPOUND:
        it = TopoDS_Iterator(occ)
        while it.More():
            yield from _iter_leaves(it.Value())
            it.Next()
    else:
        yield occ


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

    def resolve(self, shape: Shape | list[Shape]) -> list[tuple[int, int]]:
        """Return ``(dim, tag)`` for *shape*, flattening any compound or list."""
        if isinstance(shape, list) or (
            not hasattr(shape, "wrapped")
            and not hasattr(shape, "__cad_interface__")
            and hasattr(shape, "__iter__")
        ):
            members: Any = shape
            return [dt for s in members for dt in self.resolve(s)]
        occ = self._converted.get(id(shape))
        if occ is None:
            occ = _unwrap(shape)
        results: list[tuple[int, int]] = []
        for leaf in _iter_leaves(occ):
            for dim, m in self._maps.items():
                idx = m.FindIndex(leaf)
                if idx:
                    results.append((dim, idx))
                    break
        return results
