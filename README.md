# cadgmsh

Mesh [CadQuery](https://github.com/CadQuery/cadquery) / [build123d](https://github.com/gumyr/build123d) geometry with [gmsh](https://gmsh.info). No exposed `initialize`/`finalize`.

```python
import cadgmsh

mesh = cadgmsh.mesh(shape, lc=0.3)

mesh = cadgmsh.mesh(
    [box, sphere],
    physical={
        "steel": box,
        "rubber": sphere,
        "fixed": box.faces().sort_by(Axis.Z)[0],
    },
    imprint=True,
    lc=0.3,
)
```

Returns a [`meshio.Mesh`](https://github.com/nschloe/meshio). Works with [CadQuery](https://github.com/CadQuery/cadquery) and [build123d](https://github.com/gumyr/build123d) shapes interchangeably.

## Installation

```bash
pip install cadgmsh
```

Requires Python 3.11–3.14 and [CadQuery](https://github.com/CadQuery/cadquery) or [build123d](https://github.com/gumyr/build123d) in your environment — neither is a hard dependency of cadgmsh itself.

## API

```python
cadgmsh.mesh(
    shapes,                        # single shape or list of shapes
    *,
    physical=None,                 # dict[str, shape | list[shape]]
    dim=3,                         # max mesh dimension (1 / 2 / 3)
    order=1,                       # element order (1 = linear, 2 = quadratic, …)
    algorithm=None,                # gmsh algorithm number; None = default
    lc=None,                       # characteristic length (max element size)
    lc_min=None,                   # min characteristic length
    imprint=False,                 # boolean-fragment for conforming multi-body meshes
    options=None,                  # dict[str, float | str] of extra gmsh options
    verbose=False,                 # show gmsh output
) -> meshio.Mesh
```

**`physical`** maps string labels to shapes (solids, faces, edges, or vertices). Labels become named cell sets in the returned mesh, usable for boundary conditions and material assignment. An empty selection (e.g. `{"tip": []}`) raises `ValueError`.

**`options`** passes any other [gmsh option](https://gmsh.info/doc/texinfo/gmsh.html#Options), e.g. `{"Mesh.MeshSizeFromCurvature": 12}` to refine fillets and other curved faces. They are applied before the shapes are imported and override what `lc`, `lc_min` and `algorithm` set.

**`imprint`** runs `BooleanFragments` on all input shapes so that shared interfaces are meshed conformally. Required for multi-domain simulations. Note: `fragment` creates new entities for any interface it touches, so faces tagged in `physical` that lie on a shared interface won't resolve to the fragmented result — tag volumes instead.

## Custom shapes

cadgmsh accepts any shape whose `.wrapped` returns an [OCP](https://github.com/CadQuery/OCP) `TopoDS_Shape`:

```python
from cadgmsh import OccShape

class MyShape:
    @property
    def wrapped(self) -> object:  # an OCP TopoDS_Shape
        return self._occ_shape
```

It also accepts shapes and assemblies from any library that implements the proposed [`__cad_interface__`](https://github.com/DavidMStraub/cad-interface) protocol, in the formats `ocp`, `brep_text` or `brep_binary`. Named assembly nodes become physical groups containing every part below them; nodes with the same name share one group. A `physical` label with the same name is merged into it.

## License

MIT
