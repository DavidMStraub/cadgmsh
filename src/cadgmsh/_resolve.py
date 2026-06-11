from __future__ import annotations

import gmsh

from cadgmsh._occ import _pointer
from cadgmsh._types import Shape


def _resolve_tags(shape: Shape) -> list[tuple[int, int]]:
    """
    Return the gmsh ``(dim, tag)`` pairs for *shape* by re-importing its OCC pointer.

    gmsh tracks topology by TShape pointer identity, so importing a sub-shape that
    is already part of the model returns existing tags rather than creating new ones.
    Must be called after ``gmsh.model.occ.synchronize()``.
    """
    return list(
        gmsh.model.occ.importShapesNativePointer(_pointer(shape), highestDimOnly=True)
    )
