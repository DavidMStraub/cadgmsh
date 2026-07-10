from __future__ import annotations

from typing import Any

from OCP.BRepTools import BRepTools  # pyright: ignore[reportAttributeAccessIssue]
from OCP.TopAbs import (
    TopAbs_COMPOUND,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_EDGE,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_FACE,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_SOLID,  # pyright: ignore[reportAttributeAccessIssue]
    TopAbs_VERTEX,  # pyright: ignore[reportAttributeAccessIssue]
)
from OCP.TopExp import TopExp  # pyright: ignore[reportAttributeAccessIssue]
from OCP.TopoDS import (
    TopoDS_Builder,  # pyright: ignore[reportAttributeAccessIssue]
    TopoDS_Compound,  # pyright: ignore[reportAttributeAccessIssue]
    TopoDS_Iterator,  # pyright: ignore[reportAttributeAccessIssue]
)
from OCP.TopTools import (
    TopTools_IndexedMapOfShape,  # pyright: ignore[reportAttributeAccessIssue]
)

from cadgmsh._types import Shape

_TOPABS_BY_DIM = {3: TopAbs_SOLID, 2: TopAbs_FACE, 1: TopAbs_EDGE, 0: TopAbs_VERTEX}


def _unwrap(shape: Shape) -> Any:
    """Return the raw OCP ``TopoDS_*`` object, or pass through if already unwrapped."""
    return shape.wrapped if hasattr(shape, "wrapped") else shape


def _make_compound(shapes: list[Shape]) -> Any:
    """Bundle *shapes* into a single ``TopoDS_Compound`` for a one-shot BREP export."""
    builder = TopoDS_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for s in shapes:
        builder.Add(compound, _unwrap(s))
    return compound


def _write_brep(compound: Any, path: str) -> None:
    """Write *compound* (as returned by :func:`_make_compound`) to *path*."""
    BRepTools.Write_s(compound, path)


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

    def __init__(self, compound: Any) -> None:
        self._maps: dict[int, TopTools_IndexedMapOfShape] = {}
        for dim, topabs in _TOPABS_BY_DIM.items():
            m = TopTools_IndexedMapOfShape()
            TopExp.MapShapes_s(compound, topabs, m)
            self._maps[dim] = m

    def resolve(self, shape: Shape | list[Shape]) -> list[tuple[int, int]]:
        """Return ``(dim, tag)`` for *shape*, flattening any compound or list."""
        if isinstance(shape, list) or (
            not hasattr(shape, "wrapped") and hasattr(shape, "__iter__")
        ):
            members: Any = shape
            return [dt for s in members for dt in self.resolve(s)]
        results: list[tuple[int, int]] = []
        for leaf in _iter_leaves(_unwrap(shape)):
            for dim, m in self._maps.items():
                idx = m.FindIndex(leaf)
                if idx:
                    results.append((dim, idx))
                    break
        return results
