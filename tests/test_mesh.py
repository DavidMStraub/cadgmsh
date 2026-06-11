import meshio
import pytest

bd = pytest.importorskip("build123d")


def box():
    return bd.Box(1, 1, 1)


def sphere():
    return bd.Sphere(0.4)


def test_returns_meshio_mesh():
    import cadgmsh
    result = cadgmsh.mesh(box(), lc=0.5)
    assert isinstance(result, meshio.Mesh)


def test_points_and_cells():
    import cadgmsh
    result = cadgmsh.mesh(box(), lc=0.5)
    assert result.points.shape[1] == 3
    assert len(result.points) > 0
    assert len(result.cells) > 0


def test_list_input():
    import cadgmsh
    result = cadgmsh.mesh([box()], lc=0.5)
    assert isinstance(result, meshio.Mesh)


def test_physical_volume():
    import cadgmsh
    b = box()
    result = cadgmsh.mesh(b, physical={"steel": b}, lc=0.5)
    assert "steel" in result.cell_sets
    volume_arrays = [a for a in result.cell_sets["steel"] if a is not None]
    assert len(volume_arrays) > 0


def test_physical_face():
    import cadgmsh
    b = box()
    bottom = b.faces().sort_by(bd.Axis.Z)[0]
    result = cadgmsh.mesh(b, physical={"bottom": bottom}, lc=0.5)
    assert "bottom" in result.cell_sets


def test_dim2():
    import cadgmsh
    result = cadgmsh.mesh(box(), dim=2, lc=0.5)
    cell_types = {cb.type for cb in result.cells}
    assert not any("tetra" in t for t in cell_types)


def test_order2():
    import cadgmsh
    result = cadgmsh.mesh(box(), order=2, lc=0.5)
    cell_types = {cb.type for cb in result.cells}
    assert "tetra10" in cell_types


def test_imprint_two_separated_boxes():
    import cadgmsh
    # imprint=True with non-touching shapes: exercises the code path without
    # triggering OCC Boolean failures on coincident faces
    b1 = bd.Box(1, 1, 1)
    b2 = bd.Location((2, 0, 0)) * bd.Box(1, 1, 1)
    result = cadgmsh.mesh([b1, b2], imprint=True, lc=0.5)
    assert isinstance(result, meshio.Mesh)
    assert len(result.points) > 0


def test_lc_affects_mesh_density():
    import cadgmsh
    coarse = cadgmsh.mesh(box(), lc=0.5)
    fine = cadgmsh.mesh(box(), lc=0.12)
    assert len(fine.points) > len(coarse.points)
