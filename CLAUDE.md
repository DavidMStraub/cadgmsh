See [AGENTS.md](AGENTS.md) for project context, architecture, and design decisions.

## Environment

- Python venv: `~/.venv/default` (has build123d, gmsh, meshio, ruff, pyright)
- Run tests: `~/.venv/default/bin/python -m pytest`
- Type check: `~/.venv/default/bin/python -m pyright src/`
- Lint: `~/.venv/default/bin/python -m ruff check src/ tests/`

## Author

David Straub
