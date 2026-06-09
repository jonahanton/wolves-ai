# The Wolves' World Cup Superforecaster

Private World Cup 2026 forecasting app: Python engine (`engine/`: Elo + Monte Carlo sim, high-autonomy forecast agent) writes daily snapshot JSON; Next.js app (`web/`) renders it, mobile-first. Infra in `infra/` (Terraform, AWS). Plan: Obsidian vault, `General/ClaudePlans/090626_2156-wolves-engerland-ai-world-cup-forecaster.md`.

## Commands

- `make app/up` / `make app/down` to start/stop the stack. Never run `docker compose` directly.
- `make lint`, `make format`, `make test`, `make frontend/lint`.

## Style

British English. No em-dashes anywhere, including generated prose and UI copy.

Comments are rare (~3 per 100 lines) and only state a why the code cannot: a contract, race, platform quirk, or deliberate decision. Never narrate structure or what a line does. Same rule in configs.

### Python (engine/)

- `from __future__ import annotations`; modern typing (`int | None`, PEP 695); keyword-only options (`*,`); async throughout.
- Pydantic v2 for data shapes; `BaseSettings` for config; narrow exceptions carrying structured context; stdlib `logging.getLogger(__name__)`.
- Layered packages: `clients/` (external I/O) never import domain logic; agent tools in `tools/` with `_private.py` infra modules.
- Docstrings: one-line imperative on public functions; design rationale only in infra module docstrings; nothing on trivial functions.

### TypeScript (web/)

- Kebab-case files, one main component each, most under 150 lines; complexity lives in one or two orchestrators.
- Local `interface XxxProps` above the component; never `React.FC`; `any` banned (cast through `unknown`).
- No barrel files; direct `@/` imports. State in the page-level orchestrator; logic in pure `lib/` modules and focused hooks; context only for theme-grade globals; static registries in `lib/` keep leaves pure.
- RSC by default; client islands only where interaction demands.

### Tests

A test exists only to pin a contract, invariant, race, or regression, and its filename states the behaviour (`test_thirds_table_matches_fifa_annexe.py`). No frontend test files: TS strict + eslint + browser verification instead. Live-API tests behind the `smoke` pytest marker.
