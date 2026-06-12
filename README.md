# cadgmsh

Mesh [CadQuery](https://github.com/CadQuery/cadquery) / [build123d](https://github.com/gumyr/build123d) geometry with [gmsh](https://gmsh.info). No temp files, no exposed `initialize`/`finalize`.

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

Requires [CadQuery](https://github.com/CadQuery/cadquery) or [build123d](https://github.com/gumyr/build123d) in your environment — neither is a hard dependency of cadgmsh itself.

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
    verbose=False,                 # show gmsh output
) -> meshio.Mesh
```

**`physical`** maps string labels to shapes (solids, faces, edges, or vertices). Labels become named cell sets in the returned mesh, usable for boundary conditions and material assignment.

**`imprint`** runs `BooleanFragments` on all input shapes so that shared interfaces are meshed conformally. Required for multi-domain simulations. Note: interface faces tagged in `physical` will have their OCCT TShape pointer invalidated by the fragment operation — tag volumes instead.

## Custom shapes

cadgmsh accepts any shape whose `.wrapped` exposes `._address()` — the OCCT native pointer [OCP](https://github.com/CadQuery/OCP) provides on `TopoDS_*` objects:

```python
from cadgmsh import OccShape

class MyShape:
    @property
    def wrapped(self) -> object:  # must have ._address()
        return self._occ_shape
```

## License

MIT
