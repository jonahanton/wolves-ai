# The Wolves' World Cup Superforecaster

World Cup 2026 forecasting app.

## Commands

- `make app/up` / `make app/down` to start/stop the stack. Never run `docker compose` directly.
- `make lint`, `make format`, `make test`, `make frontend/lint`.

## Git

- Single author: Jonah Anton, always. No Co-Authored-By trailers, no Claude attribution, no generated-with footers, in commits or PRs.
- Commit messages: one concise imperative line. PR descriptions: a few short lines.
- Commit logically grouped changes as you go; never one giant commit.

## Style

British English. No em-dashes anywhere: code, prose, commits, UI copy, generated narrative. Code is required to be very high quality and well structured. Extendable and maintainable.

Comments are rare and only state a why the code cannot: a contract, race, platform quirk, or deliberate decision. Never narrate structure or what a line does. Same rule in configs. If a comment explains what the next line does, delete it.

Small focused files. Logic lives in pure modules, not in entrypoints or components. Name things so comments are unnecessary. No dead code, no commented-out code, no speculative abstractions or options nobody asked for.

### Python (engine/)

- `from __future__ import annotations`; modern typing (`int | None`, PEP 695 generics, no `typing.Optional`); keyword-only options (`*,`); async throughout; fully typed public signatures.
- Pydantic v2 for data shapes; `BaseSettings` for all config (env-driven, every knob a field, no scattered `os.environ`); narrow exceptions carrying structured context (`ToolTimeoutError(tool_name, timeout_s)`), never bare `except`; re-raise rather than swallow; stdlib `logging.getLogger(__name__)`, no print.
- Layered packages: `clients/` (external I/O, typed, retry-wrapped) never import domain logic; domain logic never does I/O directly; agent tools in `tools/` with `_private.py` infra modules. Third-party types stay contained at the adapter boundary.
- Docstrings: one-line imperative on public functions; design rationale only in infra module docstrings; nothing on trivial functions.
- Ruff is the only gate (line 120, `E F I N UP B A SIM TCH RUF`); every per-file-ignore carries a why.

### TypeScript (web/)

- Kebab-case files, one main component each, most under 150 lines; complexity concentrated in one or two orchestrators, everything below small and pure.
- Local `interface XxxProps` directly above the component; never `React.FC`; props types unexported unless reused; `any` banned, casts go through `unknown`; TS strict.
- No barrel files; direct `@/` imports only.
- State lives in the page-level orchestrator and flows down as props; derived state in focused hooks; logic extracted to pure `lib/` modules; context only for theme-grade globals; static registries in `lib/` keep leaf components pure functions of registry + props.
- RSC by default; `"use client"` only where interaction demands it. Errors map to a typed category union rendered by one dedicated component; all fetches go through one typed wrapper.

### Tests

A test exists only to pin a contract, invariant, race, or regression, and its filename states the behaviour (`test_thirds_table_matches_fifa_annexe.py`). Nothing a type checker already proves. No frontend test files: TS strict + eslint + browser verification instead; cross-language contracts pinned by Python parity tests that parse the TS source. Live-API tests behind the `smoke` pytest marker, opt-in only.
