# QuantSys V2 Repository Guidelines

This file defines project-local conventions for agents and contributors working
inside `quantsys-v2/`. Follow these rules for new files, renames, and cleanup.

## Canonical Entry Points

- HTTP API: `api/server.py`
- WebSocket API: `api/server_websocket.py`
- CLI: `cli/main.py`
- Tests: `tests/`

Do not add alternate entry points with suffixes such as `_v2`, `_new`, `_old`,
`_backup`, `_copy`, or `_temp`. If an entry point must be replaced, update the
canonical file and adjust imports, tests, and documentation in the same change.

## Directory Ownership

- `api/`: production HTTP/WebSocket API modules only.
- `services/`: application services and orchestration logic.
- `repositories/`: database access repositories only.
- `core/`: shared abstractions, validation, pipeline primitives.
- `quant/`: quantitative engines, factors, strategies, risk, and backtesting.
- `cli/`: CLI command wiring and command implementations.
- `scripts/`: maintenance, migration, data repair, and one-off operational scripts.
- `examples/`: runnable examples and demos.
- `tests/`: all pytest tests.
- `docs/`: durable documentation.
- `docs/reports/`: status reports, summaries, scorecards, completion notes.
- `docs/archive/`: obsolete documents, superseded examples, and removed design drafts.

Keep the repository root limited to project metadata and top-level controls:
`README.md`, `AGENTS.md`, `requirements.txt`, `pytest.ini`, `conftest.py`,
environment examples, and similar configuration files.

## File Naming Rules

- Use lowercase snake_case for Python files.
- Use descriptive purpose names: `backfill_volume.py`, `generate_signals.py`,
  `verify_schema.py`.
- Avoid process-state names: `final`, `complete`, `fixed`, `optimized`,
  `refactored`, `new`, `old`, `backup`, `copy`, `v2`.
- Do not place examples in production packages. Use `examples/` or
  `docs/examples/`.
- Do not place tests outside `tests/`.
- Do not commit generated artifacts such as coverage HTML, local signal dumps,
  cache directories, or timestamped output files unless explicitly required.

## Cleanup And Archival

When replacing code:

1. Prefer deleting obsolete files when tests and references confirm they are unused.
2. If deletion is risky, move documentation to `docs/archive/`; avoid keeping
   obsolete source files in active packages.
3. Never leave backup files in active packages such as `api/`, `services/`, or
   `repositories/`.
4. Update imports, commands, README snippets, and tests after any rename.

When adding reports or implementation notes:

- Put reports and summaries in `docs/reports/`.
- Put long-term design docs in `docs/`.
- Put temporary or superseded docs in `docs/archive/`.

## Before Finishing Changes

- Run the smallest relevant verification command.
- For renames or moves, search references with `rg` and update stale paths.
- Report any files intentionally archived or left untouched.
