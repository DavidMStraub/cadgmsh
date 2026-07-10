import pytest

bd = pytest.importorskip("build123d")

from cadgmsh._occ import ShapeIndex, _make_compound, _unwrap  # noqa: E402


def test_unwrap_passthrough():
    obj = object()
    assert _unwrap(obj) is obj


def test_unwrap_unwraps():
    inner = object()

    class Wrapped:
        wrapped = inner

    assert _unwrap(Wrapped()) is inner


def _box():
    return bd.Box(1, 1, 1)


def test_shape_index_resolves_solid():
    box = _box()
    compound = _make_compound([box])
    index = ShapeIndex(compound)
    assert index.resolve(box) == [(3, 1)]


def test_shape_index_resolves_face():
    box = _box()
    compound = _make_compound([box])
    index = ShapeIndex(compound)
    face = box.faces()[0]
    [(dim, tag)] = index.resolve(face)
    assert dim == 2
    assert tag > 0


def test_shape_index_resolves_compound_of_faces():
    box = _box()
    compound = _make_compound([box])
    index = ShapeIndex(compound)
    faces = box.faces()
    assert index.resolve(faces) == [index.resolve(f)[0] for f in faces]


def test_shape_index_multi_shape_offsets():
    box1 = _box()
    box2 = bd.Location((5, 0, 0)) * _box()
    compound = _make_compound([box1, box2])
    index = ShapeIndex(compound)
    assert index.resolve(box1) == [(3, 1)]
    assert index.resolve(box2) == [(3, 2)]
