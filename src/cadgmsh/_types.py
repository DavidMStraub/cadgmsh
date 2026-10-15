"""Centralized type definitions for cadgmsh."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from build123d.topology import Shape as _B3DShape
    from cadquery.occ_impl.shapes import Shape as _CQShape  # type: ignore


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


@runtime_checkable
class CadInterface(Protocol):
    """
    Shapes and assemblies from any library implementing the proposed
    ``__cad_interface__`` protocol (https://github.com/DavidMStraub/cad-interface).
    """

    def __cad_interface__(
        self, *, accept: Sequence[str] | None = None
    ) -> dict[str, Any]: ...


if TYPE_CHECKING:
    Shape = _B3DShape | _CQShape | OccShape | CadInterface
else:
    Shape = OccShape | CadInterface
