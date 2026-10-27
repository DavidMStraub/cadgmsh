"""CadQuery and build123d assemblies, through the internal adapters.

Each library's tests skip when it isn't installed, so this runs in an
environment with either one.
"""

import pytest

import cadgmsh


def n_cells(mesh, label):
    return sum(len(ids) for ids in mesh.cell_sets[label])


def bounds(mesh):
    lo, hi = mesh.points.min(axis=0), mesh.points.max(axis=0)
    return pytest.approx(list(lo)), pytest.approx(list(hi))


class TestCadQuery:
    @pytest.fixture(autouse=True)
    def _cq(self):
        self.cq = pytest.importorskip("cadquery")

    def car(self):
        """A body, and two wheels that share one geometry under an axle."""
        cq = self.cq
        wheel = cq.Workplane().box(1, 1, 1)
        axle = (
            cq.Assembly(name="axle", loc=cq.Location((0, 3, 0)))
            .add(wheel, name="left", loc=cq.Location((0, 0, 0)))
            .add(wheel, name="right", loc=cq.Location((3, 0, 0)))
        )
        body = cq.Workplane().box(1, 1, 1)
        return (
            cq.Assembly(name="car")
            .add(body, name="body", loc=cq.Location((10, 0, 0)))
            .add(axle)
        )

    def test_named_nodes_become_physical_groups(self):
        result = cadgmsh.mesh(self.car(), lc=0.5)
        assert {"car", "body", "axle", "left", "right"} <= set(result.cell_sets)
        assert n_cells(result, "axle") == n_cells(result, "left") + n_cells(
            result, "right"
        )
        assert n_cells(result, "car") == n_cells(result, "axle") + n_cells(
            result, "body"
        )

    def test_shared_geometry_is_meshed_at_each_location(self):
        result = cadgmsh.mesh(self.car(), lc=0.5)
        assert n_cells(result, "left") > 0 and n_cells(result, "right") > 0
        assert bounds(result) == ([-0.5, -0.5, -0.5], [10.5, 3.5, 0.5])

    def test_generated_names_are_not_groups(self):
        cq = self.cq
        assy = cq.Assembly().add(cq.Workplane().box(1, 1, 1))  # names are UUIDs
        result = cadgmsh.mesh(assy, lc=0.5)
        assert not result.cell_sets

    def test_face_of_unplaced_part(self):
        cq = self.cq
        box = cq.Workplane().box(1, 1, 1)
        assy = cq.Assembly(name="assy").add(box, name="box")
        result = cadgmsh.mesh(assy, lc=0.5, physical={"top": box.faces(">Z").val()})
        assert n_cells(result, "top") > 0

    def test_subassembly_as_physical_entry(self):
        car = self.car()
        result = cadgmsh.mesh(car, lc=0.5, physical={"wheels": car.children[1]})
        assert n_cells(result, "wheels") == n_cells(result, "axle")


class TestBuild123d:
    @pytest.fixture(autouse=True)
    def _bd(self):
        self.bd = pytest.importorskip("build123d")

    def car(self):
        """A body, and two wheels that share one geometry under an axle."""
        bd = self.bd
        wheel = bd.Box(1, 1, 1)
        left = wheel.moved(bd.Location((0, 0, 0)))
        left.label = "left"
        right = wheel.moved(bd.Location((3, 0, 0)))
        right.label = "right"
        axle = bd.Compound(children=[left, right], label="axle")
        axle.location = bd.Location((0, 3, 0))
        body = bd.Box(1, 1, 1)
        body.label = "body"
        body.location = bd.Location((10, 0, 0))
        return bd.Compound(children=[body, axle], label="car")

    def test_named_nodes_become_physical_groups(self):
        result = cadgmsh.mesh(self.car(), lc=0.5)
        assert {"car", "body", "axle", "left", "right"} <= set(result.cell_sets)
        assert n_cells(result, "axle") == n_cells(result, "left") + n_cells(
            result, "right"
        )
        assert n_cells(result, "car") == n_cells(result, "axle") + n_cells(
            result, "body"
        )

    def test_shared_geometry_is_meshed_at_each_location(self):
        result = cadgmsh.mesh(self.car(), lc=0.5)
        assert n_cells(result, "left") > 0 and n_cells(result, "right") > 0
        assert bounds(result) == ([-0.5, -0.5, -0.5], [10.5, 3.5, 0.5])

    def test_compound_without_children_is_a_shape(self):
        bd = self.bd
        box = bd.Compound([bd.Box(1, 1, 1)], label="box")
        result = cadgmsh.mesh(box, lc=0.5)
        assert not result.cell_sets

    @pytest.mark.parametrize("moved", [False, True])
    def test_face_of_part(self, moved):
        bd = self.bd
        car = self.car()
        if moved:
            car.location = bd.Location((0, 0, 5))
        body = car.children[0]
        face = (car.faces() if moved else body.faces()).sort_by(bd.Axis.X)[-1]
        result = cadgmsh.mesh(car, lc=0.5, physical={"front": face})
        assert n_cells(result, "front") > 0

    def test_subassembly_as_physical_entry(self):
        car = self.car()
        result = cadgmsh.mesh(car, lc=0.5, physical={"wheels": car.children[1]})
        assert n_cells(result, "wheels") == n_cells(result, "axle")
