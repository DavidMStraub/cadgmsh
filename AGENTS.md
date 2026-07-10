# cadgmsh — agent context

Pythonic gmsh wrapper for meshing OCC-based CAD (cadquery / build123d). No exposed `initialize`/`finalize`.

## Architecture

```
src/cadgmsh/
├── __init__.py    — public API: mesh(), OccShape, Shape
├── _types.py      — Shape alias + OccShape Protocol (centralized types)
├── _occ.py        — _unwrap(), _make_compound(), ShapeIndex (BREP-index-based tag resolution)
├── _extract.py    — _to_meshio()           (gmsh → meshio.Mesh)
└── _mesh.py       — mesh()                 (public entry point)
```

## Key design decisions

**BREP import, not native pointer.** `mesh()` bundles all input shapes into one `TopoDS_Compound`, writes it to a temp `.brep` file, and imports it via `gmsh.model.occ.importShapes()`.

We previously used `gmsh.model.occ.importShapesNativePointer()` to import OCC topology by memory pointer, avoiding any temp file. This broke whenever gmsh's statically-linked OCCT version differs from the CAD library's (e.g. gmsh 4.15.2 bundles OCCT 7.8, `cadquery-ocp` ships 7.9.3.1) — passing a raw pointer between two independently compiled OCCT builds works for most shapes but corrupts periodic-surface continuity data, raising `GeomAdaptor_Surface::UContinuity`. A BREP file round-trip sidesteps the ABI mismatch entirely (each library reads/writes with its own OCCT, and BREP is a stable serialization contract), at the cost of one small temp file per `mesh()` call.

**Physical group resolution.** Sub-shape → gmsh tag resolution no longer relies on pointer identity (which a file round-trip destroys). Instead, `ShapeIndex` builds a `TopTools_IndexedMapOfShape` per dimension via `TopExp.MapShapes_s` over the same compound that gets written to BREP. This is the same canonical indexing algorithm `BRepTools_ShapeSet` uses internally when writing/reading BREP, so a sub-shape's index here is guaranteed to equal the gmsh tag assigned when importing that BREP file — no geometric search, no pointer identity, and it survives the OCCT-version mismatch that broke the old approach.

**Lifecycle.** `gmsh.initialize()` / `gmsh.finalize()` are scoped inside `mesh()` via `try/finally`. Callers never touch them.

**Type system.** `Shape` is `build123d.Shape | cadquery.Shape | OccShape` under `TYPE_CHECKING`; at runtime it resolves to `OccShape` (a `runtime_checkable Protocol`). `Any` is intentionally limited to `_occ.py` where OCP has no stubs.

## Known limitations

- `imprint=True` with coincident/touching faces triggers a segfault inside OCC's Boolean kernel that cannot be caught as a Python exception. Verified safe with non-overlapping and gapped shapes.
- Face tagging + `imprint=True`: `fragment` creates new entities for any interface it touches, so the pre-fragment `ShapeIndex` can't resolve those faces to the fragmented result. Volume tagging + imprinting is confirmed correct.
- `cadquery` is only installed in the `test`/`dev` extras on Python >=3.11 (`cadquery; python_version >= '3.11'` in `pyproject.toml`). The last `cadquery` release supporting 3.10 (`2.7.0`) hard-pins `cadquery-ocp<7.9`, which is incompatible with current `build123d` releases (`TopoDS.Vertex` vs `Vertex_s` naming) — installing both on 3.10 breaks collection before any cadgmsh code runs. No test currently imports `cadquery` directly, so this doesn't reduce coverage.

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
- `test_occ.py` — `ShapeIndex`/compound unit tests, requires build123d, no gmsh required
- `test_extract.py` — real gmsh session, no OCC shapes
- `test_mesh.py` — full integration, requires build123d (skipped if absent)

## CI

GitHub Actions runs `lint` (ruff + pyright) and `test` (pytest) on Python 3.10 and 3.13. A separate `release` workflow publishes to PyPI on `v*` tags via OIDC trusted publishing.
