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


def group_elements(dim, tag):
    """Node sets (0-based) of every element gmsh assigns to a physical group."""
    out = set()
    for entity in gmsh.model.getEntitiesForPhysicalGroup(dim, tag):
        for etags in gmsh.model.mesh.getElements(dim, entity)[1]:
            for etag in etags:
                nodes = gmsh.model.mesh.getElement(etag)[1]
                out.add(frozenset(int(n) - 1 for n in nodes))
    return out


def cell_set_elements(m, name):
    return {
        frozenset(int(n) for n in cb.data[i])
        for cb, ids in zip(m.cells, m.cell_sets[name], strict=True)
        for i in ids
    }


def test_cell_sets_hold_the_group_elements(box_mesh_with_physical):
    """Cell set entries are positions in their cell block, not gmsh element tags."""
    m = _to_meshio()
    for name, (dim, tag) in [("volume", (3, 1)), ("surface", (2, 2))]:
        assert cell_set_elements(m, name) == group_elements(dim, tag)


def test_same_name_across_dimensions_is_merged(box_mesh_with_physical):
    faces = [t for _, t in gmsh.model.getEntities(2)[:2]]
    pg = gmsh.model.addPhysicalGroup(2, faces)
    gmsh.model.setPhysicalName(2, pg, "volume")
    m = _to_meshio()
    assert cell_set_elements(m, "volume") == group_elements(3, 1) | group_elements(
        2, pg
    )


# Higher-order nodes in meshio (VTK) order, as the corner nodes they sit
# between: edge midpoints, face centres and the cell centre.
# fmt: off
HIGHER_ORDER_NODES = {
    "line3": [(0, 1)],
    "triangle6": [(0, 1), (1, 2), (2, 0)],
    "quad9": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 1, 2, 3)],
    "tetra10": [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)],
    "hexahedron27": [
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
        (0, 3, 7, 4), (1, 2, 6, 5), (0, 1, 5, 4), (3, 2, 6, 7),
        (0, 1, 2, 3), (4, 5, 6, 7), tuple(range(8)),
    ],
}
# fmt: on
HIGHER_ORDER_NODES["hexahedron20"] = HIGHER_ORDER_NODES["hexahedron27"][:12]


def check_higher_order_nodes(m):
    """On straight-sided cells, each higher-order node is the mean of its corners."""
    checked = set()
    for cb in m.cells:
        if cb.type not in HIGHER_ORDER_NODES:
            continue
        nodes = HIGHER_ORDER_NODES[cb.type]
        first = cb.data.shape[1] - len(nodes)
        for k, corners in enumerate(nodes):
            expected = m.points[cb.data[:, list(corners)]].mean(axis=1)
            actual = m.points[cb.data[:, first + k]]
            np.testing.assert_allclose(
                actual, expected, atol=1e-12, err_msg=f"{cb.type} node {first + k}"
            )
        checked.add(cb.type)
    return checked


def test_tetra10_node_order(box_mesh):
    gmsh.model.mesh.setOrder(2)
    checked = check_higher_order_nodes(_to_meshio())
    assert {"line3", "triangle6", "tetra10"} <= checked


@pytest.mark.parametrize(
    ("incomplete", "cell_type"), [(0, "hexahedron27"), (1, "hexahedron20")]
)
def test_hexahedron_node_order(incomplete, cell_type):
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("test")
        gmsh.model.occ.addBox(0, 0, 0, 1, 2, 3)
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.MeshSizeMax", 0.6)
        gmsh.option.setNumber("Mesh.RecombineAll", 1)
        gmsh.option.setNumber("Mesh.SecondOrderIncomplete", incomplete)
        gmsh.model.mesh.setTransfiniteAutomatic()
        gmsh.model.mesh.generate(3)
        gmsh.model.mesh.setOrder(2)
        checked = check_higher_order_nodes(_to_meshio())
    finally:
        gmsh.finalize()
    assert cell_type in checked


def test_node_indices_are_consecutive(box_mesh):
    idx, _, _ = gmsh.model.mesh.getNodes()
    idx -= 1
    srt = np.argsort(idx)
    assert np.all(idx[srt] == np.arange(len(idx)))
