"""Objects implementing ``__cad_interface__``, from a producer built on raw OCP.

Like ``test_raw_occ.py``, these need no CAD library, so they run on any
supported OCCT version.
"""

import io

import pytest
from OCP.BinTools import BinTools  # pyright: ignore[reportAttributeAccessIssue]
from OCP.BRepPrimAPI import (
    BRepPrimAPI_MakeBox,  # pyright: ignore[reportAttributeAccessIssue]
)
from OCP.BRepTools import BRepTools  # pyright: ignore[reportAttributeAccessIssue]

import cadgmsh
from cadgmsh._occ import _write_brep


def box() -> object:
    return BRepPrimAPI_MakeBox(1, 1, 1).Shape()


def encode(shape, fmt):
    data = shape
    if fmt != "ocp":
        buf = io.BytesIO()
        (BRepTools if fmt == "brep_text" else BinTools).Write_s(shape, buf)
        data = buf.getvalue()
    return {"version": 1, "type": "shape", "format": fmt, "data": data}


class Part:
    def __init__(self, fmt="ocp"):
        self.shape, self.fmt = box(), fmt
        self.requested = None

    def __cad_interface__(self, *, accept=None):
        self.requested = list(accept or ())
        return encode(self.shape, self.fmt)


def at(x):
    m = [[1.0, 0, 0, x], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]]
    return [[float(v) for v in row] for row in m]


def node(name, x=0, shape=None, children=()):
    return {
        "name": name,
        "location": at(x),
        "color": None,
        "shape": shape,
        "children": list(children),
    }


class Assembly:
    """Two wheels sharing one geometry, and a body, under a named axle node."""

    def __cad_interface__(self, *, accept=None):
        root = node(
            "car",
            children=[
                node("body", 10, shape=0),
                node("axle", children=[node("wheel", 0, 0), node("wheel", 3, 0)]),
            ],
        )
        shapes = [encode(box(), "ocp")]
        return {"version": 1, "type": "assembly", "shapes": shapes, "root": root}


class Skin:
    """An assembly whose only part is a shell."""

    def __cad_interface__(self, *, accept=None):
        shell = BRepPrimAPI_MakeBox(1, 1, 1).Shell()
        root = node("skin", shape=0)
        shapes = [encode(shell, "ocp")]
        return {"version": 1, "type": "assembly", "shapes": shapes, "root": root}


def n_cells(mesh, label):
    return sum(len(ids) for ids in mesh.cell_sets[label])


@pytest.mark.parametrize("fmt", ["ocp", "brep_text", "brep_binary"])
def test_shape(fmt):
    part = Part(fmt)
    result = cadgmsh.mesh(part, lc=0.5, physical={"body": part})
    assert part.requested == ["ocp", "brep_text", "brep_binary"]
    assert n_cells(result, "body") > 0


def test_assembly_names_become_physical_groups():
    result = cadgmsh.mesh(Assembly(), lc=0.5)
    assert {"car", "body", "axle", "wheel"} <= set(result.cell_sets)
    # the two wheels share one group, the axle holds both, the car everything
    assert n_cells(result, "axle") == n_cells(result, "wheel")
    assert n_cells(result, "car") == n_cells(result, "wheel") + n_cells(result, "body")


def test_single_assembly_is_imprinted(monkeypatch):
    import gmsh

    calls = []
    fragment = gmsh.model.occ.fragment
    monkeypatch.setattr(
        gmsh.model.occ,
        "fragment",
        lambda *args, **kwargs: calls.append(args) or fragment(*args, **kwargs),
    )
    cadgmsh.mesh(Assembly(), imprint=True, lc=0.5)  # parts don't touch
    assert len(calls) == 1


def test_shell_parts_resolve_to_faces():
    result = cadgmsh.mesh(Skin(), dim=2, lc=0.5)
    assert n_cells(result, "skin") > 0


def test_assembly_parts_are_placed():
    result = cadgmsh.mesh(Assembly(), lc=0.5)
    xs = result.points[:, 0]
    assert xs.min() == pytest.approx(0) and xs.max() == pytest.approx(11)


def test_unsupported_version():
    class Future(Part):
        def __cad_interface__(self, *, accept=None):
            return {**super().__cad_interface__(accept=accept), "version": 2}

    with pytest.raises(ValueError, match="version"):
        cadgmsh.mesh(Future(), lc=0.5)


def test_brep_has_no_triangulation(tmp_path):
    from OCP.BRepMesh import (
        BRepMesh_IncrementalMesh,  # pyright: ignore[reportAttributeAccessIssue]
    )

    b = box()
    BRepMesh_IncrementalMesh(b, 0.01)  # e.g. after being shown in a viewer
    path = tmp_path / "shape.brep"
    _write_brep(b, str(path))
    data = path.read_bytes()
    assert b"CASCADE Topology V1" in data
    assert b"\nTriangulations 0\n" in data
