from __future__ import annotations

from typing import Any

from cadgmsh._types import Shape


def _unwrap(shape: Shape) -> Any:
    """Return the raw OCP ``TopoDS_*`` object, or pass through if already unwrapped."""
    return shape.wrapped if hasattr(shape, "wrapped") else shape


def _pointer(shape: Shape) -> int:
    """
    Return the integer memory address of a ``TopoDS_Shape``.

    Compatible with ``gmsh.model.occ.importShapesNativePointer``.
    Supports OCP (pybind11) via ``._address()`` and PythonOCC (SWIG) via ``.this``.
    """
    occ: Any = _unwrap(shape)
    if hasattr(occ, "_address"):
        return int(occ._address())
    if hasattr(occ, "this"):
        return int(occ.this)
    raise TypeError(f"Cannot extract OCC pointer from {type(shape)}")
