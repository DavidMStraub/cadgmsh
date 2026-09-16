"""Tests driven by raw OCP shapes, with no CAD library involved.

These exercise the same code paths as the build123d tests but depend only on
``OCP`` itself, so they run against any supported OCCT version -- including
ones that ``build123d``/``cadquery`` do not yet support.
"""

import meshio
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,  # pyright: ignore[reportAttributeAccessIssue]
)
from OCP.gp import gp_Pnt  # pyright: ignore[reportAttributeAccessIssue]

import cadgmsh
from cadgmsh._occ import ShapeIndex, _make_compound


def box(x: float = 0.0) -> object:
    return BRepPrimAPI_MakeBox(gp_Pnt(x, 0, 0), 1, 1, 1).Shape()


def test_shape_index_resolves_solid():
    b = box()
    index = ShapeIndex(_make_compound([b]))
    assert index.resolve(b) == [(3, 1)]


def test_shape_index_multi_shape_offsets():
    b1, b2 = box(), box(5)
    index = ShapeIndex(_make_compound([b1, b2]))
    assert index.resolve(b1) == [(3, 1)]
    assert index.resolve(b2) == [(3, 2)]


def test_mesh_roundtrip():
    result = cadgmsh.mesh(box(), lc=0.5)
    assert isinstance(result, meshio.Mesh)
    assert result.points.shape[1] == 3
    assert len(result.points) > 0
    assert len(result.cells) > 0


def test_physical_volume():
    b = box()
    result = cadgmsh.mesh(b, lc=0.5, physical={"body": b})
    assert "body" in result.cell_sets
    assert sum(len(ids) for ids in result.cell_sets["body"]) > 0
