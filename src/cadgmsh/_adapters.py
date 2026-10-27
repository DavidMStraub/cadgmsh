"""
CadQuery and build123d assemblies as ``__cad_interface__`` dicts in the ``ocp``
format, so they take the same path as assemblies from any other library.
Ported from cadglue (https://github.com/DavidMStraub/cadglue), without the
encoders.

A CAD library is only imported when the object comes from it.
"""

from __future__ import annotations

import uuid
from typing import Any

from OCP.TopLoc import TopLoc_Location  # pyright: ignore[reportAttributeAccessIssue]


def interface(obj: Any) -> dict[str, Any] | None:
    """The interface dict of a CadQuery or build123d assembly, else ``None``."""
    library = _library(obj)
    if library == "cadquery":
        import cadquery as cq  # pyright: ignore[reportMissingImports]

        if isinstance(obj, cq.Assembly):
            return _cadquery(obj)
    elif library == "build123d":
        import build123d as bd

        if _has_children(obj, bd):
            return _build123d(obj)
    return None


def is_assembly(obj: Any) -> bool:
    """Whether :func:`interface` turns *obj* into an assembly dict."""
    library = _library(obj)
    if library == "cadquery":
        import cadquery as cq  # pyright: ignore[reportMissingImports]

        return isinstance(obj, cq.Assembly)
    if library == "build123d":
        import build123d as bd

        return _has_children(obj, bd)
    return False


def _library(obj: Any) -> str | None:
    # The MRO also catches user subclasses defined in their own modules.
    for cls in type(obj).__mro__:
        library = cls.__module__.partition(".")[0]
        if library in ("cadquery", "build123d"):
            return library
    return None


def _cadquery(root: Any) -> dict[str, Any]:
    import cadquery as cq  # pyright: ignore[reportMissingImports]

    table = _ShapeTable()

    def as_shape(obj: Any) -> Any:
        """Assembly nodes may hold a Shape, a Workplane or a Sketch."""
        if isinstance(obj, cq.Shape):
            return obj
        if isinstance(obj, cq.Sketch):
            return obj._faces
        if isinstance(obj, cq.Workplane):
            shapes = [
                as_shape(v) for v in obj.vals() if isinstance(v, cq.Shape | cq.Sketch)
            ]
            if not shapes:
                raise ValueError("Workplane contains no shapes")
            return shapes[0] if len(shapes) == 1 else cq.Compound.makeCompound(shapes)
        raise TypeError(f"Unsupported CadQuery object {type(obj).__name__}")

    def node(a: Any) -> dict[str, Any]:
        return {
            "name": _user_name(a.name),
            "location": _matrix(a.loc.wrapped),
            "color": None,
            "shape": None if a.obj is None else table.add(as_shape(a.obj).wrapped),
            "children": [node(c) for c in a.children],
        }

    return _assembly(table, node(root))


def _build123d(root: Any) -> dict[str, Any]:
    import build123d as bd

    table = _ShapeTable()

    def node(n: Any) -> dict[str, Any]:
        if _has_children(n, bd):
            # build123d nodes with children have no geometry of their own
            location, shape = _matrix(n.wrapped.Location()), None
            children = [node(c) for c in n.children]
        else:
            # without its location, so copies of one part share a table entry
            local = n.wrapped.Located(TopLoc_Location())
            location, shape = _matrix(n.wrapped.Location()), table.add(local)
            children = []
        return {
            "name": n.label or None,
            "location": location,
            "color": None,
            "shape": shape,
            "children": children,
        }

    return _assembly(table, node(root))


def _has_children(obj: Any, bd: Any) -> bool:
    return isinstance(obj, bd.Compound) and bool(obj.children)


def _assembly(table: _ShapeTable, root: dict[str, Any]) -> dict[str, Any]:
    return {"version": 1, "type": "assembly", "shapes": table.shapes, "root": root}


class _ShapeTable:
    """The ``shapes`` list of an assembly dict, with each geometry once."""

    def __init__(self) -> None:
        self.shapes: list[dict[str, Any]] = []
        self._index: dict[int, list[tuple[Any, int]]] = {}

    def add(self, shape: Any) -> int:
        """Return the index of *shape*, adding it if it's new."""
        bucket = self._index.setdefault(hash(shape), [])
        for other, i in bucket:
            if other.IsEqual(shape):
                return i
        bucket.append((shape, len(self.shapes)))
        self.shapes.append(
            {"version": 1, "type": "shape", "format": "ocp", "data": shape}
        )
        return len(self.shapes) - 1


def _matrix(loc: Any) -> list[list[float]]:
    t = loc.Transformation()
    return [[t.Value(i, j) for j in range(1, 5)] for i in range(1, 4)] + [
        [0.0, 0.0, 0.0, 1.0]
    ]


def _user_name(name: str) -> str | None:
    """``None`` for the UUIDs that CadQuery generates for unnamed nodes."""
    try:
        generated = str(uuid.UUID(name)) == name
    except ValueError:
        generated = False
    return None if generated else name
