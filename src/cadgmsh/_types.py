"""Centralized type definitions for cadgmsh."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from build123d import Shape as _B3DShape
    from cadquery.occ_impl.shapes import (
        Shape as _CQShape,  # type: ignore[import-untyped]
    )


@runtime_checkable
class OccShape(Protocol):
    """
    Structural protocol for OCC-backed shapes accepted by cadgmsh.

    Satisfied by cadquery and build123d shapes.
    Implement ``.wrapped`` pointing to an OCC ``TopoDS_Shape`` to integrate
    custom shape types without depending on either library.
    """

    @property
    def wrapped(self) -> object: ...


if TYPE_CHECKING:
    Shape = _B3DShape | _CQShape | OccShape
else:
    Shape = OccShape
