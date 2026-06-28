# The Wolves' World Cup Superforecaster

World Cup 2026 forecasting app.

This repo always uses the `jonahanton` GitHub account, on every machine. Some machines
switch between two accounts via the gh CLI: before the first commit or push of a session,
check `gh auth status` and `gh auth switch --user jonahanton` if the other account is
active, and make sure `git config user.name`/`user.email` give
`Jonah Anton <88099788+jonahanton@users.noreply.github.com>` (set locally if not).

## Commands

- `make app/up` / `make app/down` to start/stop the stack. Never run `docker compose` directly.
- `make lint`, `make format`, `make test`, `make frontend/lint`.
- Agent-run logs are in Logfire (read token `LOGFIRE_READ_TOKEN`, in `.env`). `python scripts/logfire_runs.py runs [--days N]` lists recent runs with outcome (submitted/STRANDED/degraded) and spend; `python scripts/logfire_runs.py show <run-id>` prints one run's wave-by-wave decision trail (master plans, admission drops, node failures, submission result).
- Worktree runs: `runs/` is gitignored, so a fresh worktree has no `runs/datasets` or `runs/models` and the forecaster falls back to Elo. Copy both from the main checkout (optionally `runs/agent-state/lessons.jsonl`) before any non-trivial run.
- S3 dev bucket: `wolves-superforecaster-dev`. `runs/` holds raw agent working data (events, artifacts, ledger) — the app never reads these. `snapshots/` holds the published sim outputs (probability distributions, bracket samples, etc.) that the backend serves and the frontend displays — anything left here will appear in the run picker; `latest.json` always points to the current live snapshot. Retire unwanted snapshots to `snapshots-backup/` and run dirs to `runs-backup/`.
- Retire a forecast: `python scripts/retire_forecast.py <run-id> --env prod` moves the snapshot and its sidecars to `snapshots-backup/` so the app serves the previous agent forecast (`--with-run-dir` also backs up the raw run, `--dry-run` previews).
- Launch/stop runs remotely: `gh workflow run run-engine.yml -f mode=agent [-f ceiling_usd=5]` starts a run; `gh workflow run admin-control.yml -f action=active-runs` (or `-f action=stop-all`) lists or cancels in-flight tasks, read with `gh run view`.

## Git

- Single author: Jonah Anton, always. No Co-Authored-By trailers, no Claude attribution, no generated-with footers, in commits or PRs.
- Commit messages: one concise imperative line. PR descriptions: a few short lines.
- Commit logically grouped changes as you go; never one giant commit.
- Releases are opt-in: label a PR `release` before merge and `tag-release.yml` tags the next `prod-x.y.z` patch, firing `release.yml`; unlabelled merges deploy nothing.

## Style

British English. No em-dashes anywhere: code, prose, commits, UI copy, generated narrative. Code is required to be very high quality and well structured. Extendable and maintainable.

Comments are rare and only state a why the code cannot: a contract, race, platform quirk, or deliberate decision. Never narrate structure or what a line does. Same rule in configs. If a comment explains what the next line does, delete it.

Comments and docstrings never reference plan phases, milestones, or workstreams (M0, WS-A, "Phase 2 adds..."). Code describes itself as it is; the plan lives in the plan note.

Small focused files. Logic lives in pure modules, not in entrypoints or components. Name things so comments are unnecessary. No dead code, no commented-out code, no speculative abstractions or options nobody asked for.

When a change supersedes something, delete the superseded thing in the same change: interim scaffolding, parallel implementations, unused vendored modules, settings nobody reads. Every merge leaves the tree simpler than it found it.

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

A test exists only to pin a contract, invariant, race, or regression, and its filename states the behaviour (`test_thirds_table_matches_fifa_annexe.py`). Nothing a type checker already proves. If no plausible regression would make it fail, delete it.

`engine/tests/` mirrors the package layout (`tests/sim/`, `tests/observability/`, ...), one behaviour per file. Near-identical cases become one parametrised table, never enumerated copies. Each file stays small; setup shared via local fixtures, not conftest sprawl.

No frontend test files: TS strict + eslint + browser verification instead; cross-language contracts pinned by Python parity tests that parse the TS source. Live-API tests behind the `smoke` pytest marker, opt-in only.
