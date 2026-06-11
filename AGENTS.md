# cadgmsh — agent context

Pythonic gmsh wrapper for meshing OCC-based CAD (cadquery / build123d). No temp files, no exposed `initialize`/`finalize`.

## Architecture

```
src/cadgmsh/
├── __init__.py    — public API: mesh(), OccShape, Shape
├── _types.py      — Shape alias + OccShape Protocol (centralized types)
├── _occ.py        — _unwrap(), _pointer()  (OCC pointer extraction)
├── _resolve.py    — _resolve_tags()        (gmsh tag lookup by OCC pointer)
├── _extract.py    — _to_meshio()           (gmsh → meshio.Mesh)
└── _mesh.py       — mesh()                 (public entry point)
```

## Key design decisions

**No temp files.** `gmsh.model.occ.importShapesNativePointer(shape.wrapped._address())` imports OCC topology by memory pointer. OCP (pybind11) exposes `._address()` on `TopoDS_*` objects.

**Physical group resolution.** After `synchronize()`, re-importing a sub-shape pointer returns existing gmsh tags (gmsh tracks topology by `TShape` pointer identity). No geometric search needed.

**Lifecycle.** `gmsh.initialize()` / `gmsh.finalize()` are scoped inside `mesh()` via `try/finally`. Callers never touch them.

**Type system.** `Shape` is `build123d.Shape | cadquery.Shape | OccShape` under `TYPE_CHECKING`; at runtime it resolves to `OccShape` (a `runtime_checkable Protocol`). `Any` is intentionally limited to `_occ.py` where OCP has no stubs.

## Known limitations

- `imprint=True` with coincident/touching faces triggers a segfault inside OCC's Boolean kernel that cannot be caught as a Python exception. Verified safe with non-overlapping and gapped shapes.
- Face tagging + `imprint=True`: interface faces have their `TShape` pointer invalidated by `fragment`. Volume tagging + imprinting is confirmed correct.

## Development commands

```bash
pytest                              # run all tests (requires build123d)
pytest tests/test_occ.py            # pure unit tests, no heavy deps
pyright src/                        # type check (must pass with 0 errors)
ruff check src/ tests/              # lint (must pass clean)
ruff format src/ tests/             # format in-place
ruff format --check src/ tests/     # format check only
```

Test matrix:
- `test_occ.py` — mock-based, no gmsh or OCC required
- `test_extract.py` — real gmsh session, no OCC shapes
- `test_mesh.py` — full integration, requires build123d (skipped if absent)

## CI

GitHub Actions runs `lint` (ruff + pyright) and `test` (pytest) on Python 3.10 and 3.13. A separate `release` workflow publishes to PyPI on `v*` tags via OIDC trusted publishing.
