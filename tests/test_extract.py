import gmsh
import numpy as np
import pytest

from cadgmsh._extract import _to_meshio


@pytest.fixture
def box_mesh():
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("test")
    gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
    gmsh.model.occ.synchronize()
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 0.5)
    gmsh.model.mesh.generate(3)
    yield
    gmsh.finalize()


@pytest.fixture
def box_mesh_with_physical():
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("test")
    vol_tag = gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
    gmsh.model.occ.synchronize()
    pg_vol = gmsh.model.addPhysicalGroup(3, [vol_tag])
    gmsh.model.setPhysicalName(3, pg_vol, "volume")
    face_tags = [t for _, t in gmsh.model.getEntities(2)[:2]]
    pg_face = gmsh.model.addPhysicalGroup(2, face_tags)
    gmsh.model.setPhysicalName(2, pg_face, "surface")
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 0.5)
    gmsh.model.mesh.generate(3)
    yield
    gmsh.finalize()


def test_points_shape(box_mesh):
    m = _to_meshio()
    assert m.points.ndim == 2
    assert m.points.shape[1] == 3


def test_points_nonempty(box_mesh):
    m = _to_meshio()
    assert len(m.points) > 0


def test_cells_nonempty(box_mesh):
    m = _to_meshio()
    assert len(m.cells) > 0
    assert sum(len(cb.data) for cb in m.cells) > 0


def test_no_physical_groups(box_mesh):
    m = _to_meshio()
    assert m.cell_sets == {}


def test_physical_group_names(box_mesh_with_physical):
    m = _to_meshio()
    assert "volume" in m.cell_sets
    assert "surface" in m.cell_sets


def test_physical_group_nonempty(box_mesh_with_physical):
    m = _to_meshio()
    volume_arrays = [a for a in m.cell_sets["volume"] if a is not None]
    assert len(volume_arrays) > 0
    assert sum(len(a) for a in volume_arrays) > 0


def test_node_indices_are_consecutive(box_mesh):
    idx, _, _ = gmsh.model.mesh.getNodes()
    idx -= 1
    srt = np.argsort(idx)
    assert np.all(idx[srt] == np.arange(len(idx)))
