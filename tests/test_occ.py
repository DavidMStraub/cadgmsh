import pytest

from cadgmsh._occ import _pointer, _unwrap


class _WithAddress:
    def _address(self):
        return 42


class _WithThis:
    this = 99


def test_unwrap_passthrough():
    obj = object()
    assert _unwrap(obj) is obj


def test_unwrap_unwraps():
    inner = object()

    class Wrapped:
        wrapped = inner

    assert _unwrap(Wrapped()) is inner


def test_pointer_address():
    assert _pointer(_WithAddress()) == 42


def test_pointer_this():
    assert _pointer(_WithThis()) == 99


def test_pointer_wrapped_address():
    class Shape:
        wrapped = _WithAddress()

    assert _pointer(Shape()) == 42


def test_pointer_wrapped_this():
    class Shape:
        wrapped = _WithThis()

    assert _pointer(Shape()) == 99


def test_pointer_raises_on_unknown():
    with pytest.raises(TypeError):
        _pointer(object())


def test_pointer_raises_on_wrapped_unknown():
    class Shape:
        wrapped = object()

    with pytest.raises(TypeError):
        _pointer(Shape())
