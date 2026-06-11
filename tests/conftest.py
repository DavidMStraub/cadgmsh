import gmsh
import pytest


@pytest.fixture
def gmsh_session():
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    gmsh.model.add("test")
    yield
    gmsh.finalize()
