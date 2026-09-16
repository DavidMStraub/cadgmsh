# cadgmsh — agent context

Pythonic gmsh wrapper for meshing OCC-based CAD (cadquery / build123d). No exposed `initialize`/`finalize`.

## Architecture

```
src/cadgmsh/
├── __init__.py    — public API: mesh(), OccShape, Shape
├── _types.py      — Shape alias + OccShape Protocol (centralized types)
├── _occ.py        — _unwrap(), _make_compound(), ShapeIndex (BREP-index-based tag resolution)
│                    also the single OCP import boundary + the OCCT 7/8 shim
├── _extract.py    — _to_meshio()           (gmsh → meshio.Mesh)
└── _mesh.py       — mesh()                 (public entry point)
```

## Key design decisions

**BREP import, not native pointer.** `mesh()` bundles all input shapes into one `TopoDS_Compound`, writes it to a temp `.brep` file, and imports it via `gmsh.model.occ.importShapes()`.

We previously used `gmsh.model.occ.importShapesNativePointer()` to import OCC topology by memory pointer, avoiding any temp file. This broke whenever gmsh's statically-linked OCCT version differs from the CAD library's (e.g. gmsh 4.15.2 bundles OCCT 7.8, `cadquery-ocp` ships 7.9.3.1) — passing a raw pointer between two independently compiled OCCT builds works for most shapes but corrupts periodic-surface continuity data, raising `GeomAdaptor_Surface::UContinuity`. A BREP file round-trip sidesteps the ABI mismatch entirely (each library reads/writes with its own OCCT, and BREP is a stable serialization contract), at the cost of one small temp file per `mesh()` call.

**Physical group resolution.** Sub-shape → gmsh tag resolution no longer relies on pointer identity (which a file round-trip destroys). Instead, `ShapeIndex` builds a `TopTools_IndexedMapOfShape` per dimension via `TopExp.MapShapes_s` over the same compound that gets written to BREP. This is the same canonical indexing algorithm `BRepTools_ShapeSet` uses internally when writing/reading BREP, so a sub-shape's index here is guaranteed to equal the gmsh tag assigned when importing that BREP file — no geometric search, no pointer identity, and it survives the OCCT-version mismatch that broke the old approach.

**Lifecycle.** `gmsh.initialize()` / `gmsh.finalize()` are scoped inside `mesh()` via `try/finally`. Callers never touch them.

**OCCT 7 / OCCT 8 dual support.** `cadquery-ocp` 8 (OCCT 8.0) is a breaking change for
downstream code: OCCT 8 stopped exposing the ready-made `NCollection` typedefs as module
attributes and publishes the template instantiations under a new `OCP.collections` module
instead. The only one cadgmsh touches is the indexed shape map —
`OCP.TopTools.TopTools_IndexedMapOfShape` (OCCT 7) vs
`OCP.collections.IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher` (OCCT 8) — so `_occ.py`
aliases whichever is importable to `_IndexedMapOfShape`. Everything else we use
(`BRepTools.Write_s`, `TopExp.MapShapes_s`, `TopoDS_Builder/Compound/Iterator`, the
`TopAbs_*` enums) is unchanged across the two.

`BRepTools.Write_s(shape, path)` defaults to `TopTools_FormatVersion_VERSION_1` on both,
so OCCT 8 still emits a BREP that gmsh's bundled OCCT 7.8 can read, and the
`ShapeIndex` → gmsh tag correspondence survives the version gap (verified end-to-end by
`tests/test_raw_occ.py` under OCCT 8).

**Type system.** `Shape` is `build123d.Shape | cadquery.Shape | OccShape` under `TYPE_CHECKING`; at runtime it resolves to `OccShape` (a `runtime_checkable Protocol`). `Any` is intentionally limited to `_occ.py` where OCP has no stubs.

## Known limitations

- `imprint=True` with coincident/touching faces triggers a segfault inside OCC's Boolean kernel that cannot be caught as a Python exception. Verified safe with non-overlapping and gapped shapes.
- Face tagging + `imprint=True`: `fragment` creates new entities for any interface it touches, so the pre-fragment `ShapeIndex` can't resolve those faces to the fragmented result. Volume tagging + imprinting is confirmed correct.
- Python 3.11–3.14 (`requires-python = ">=3.11,<3.15"`). The floor is 3.11 because `cadquery` and `cadquery-ocp` 8 both require it; the ceiling tracks `cadquery-ocp`'s own `<3.15`.
- `build123d` and `cadquery` both still pin `cadquery-ocp<8.0`, so an environment with either of them installed resolves to OCCT 7 no matter what cadgmsh allows. OCCT 8 is only reachable today by installing cadgmsh without them and driving it with raw OCP shapes — which is exactly what the `test-occt8` CI job does. Lift nothing here when they catch up; the shim handles both.

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
- `test_raw_occ.py` — same paths driven by raw `OCP` shapes only, so it runs on any supported OCCT version (this is the OCCT 8 coverage)

## CI

GitHub Actions runs `lint` (ruff + pyright), `test` (pytest) on Python 3.11 and 3.14 against OCCT 7, and `test-occt8` (OCCT 8, no build123d/cadquery). A separate `release` workflow publishes to PyPI on `v*` tags via OIDC trusted publishing.
