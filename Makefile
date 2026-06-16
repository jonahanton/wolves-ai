-include .env
-include .env.worktree
export

.PHONY: setup venv lint format test precommit db/init release \
        app/up app/down app/restart app/logs \
        demo/save demo/on demo/off \
        frontend/install frontend/dev frontend/build frontend/lint

setup: venv frontend/install

venv:
	rm -rf .venv engine/.venv backend/.venv || true
	uv sync --all-packages --all-extras
	@echo "Done. Activate with: source .venv/bin/activate"

lint:
	cd engine && ../.venv/bin/ruff check .
	cd backend && ../.venv/bin/ruff check .

format:
	cd engine && ../.venv/bin/ruff format . && ../.venv/bin/ruff check . --fix
	cd backend && ../.venv/bin/ruff format . && ../.venv/bin/ruff check . --fix

test:
	cd engine && ../.venv/bin/pytest tests/ -q
	cd backend && ../.venv/bin/pytest tests/ -q

precommit:
	pre-commit run --all-files

release:
	@scripts/release.sh $(env)

db/init:
	AWS_ACCESS_KEY_ID=$${AWS_ACCESS_KEY_ID:-local} AWS_SECRET_ACCESS_KEY=$${AWS_SECRET_ACCESS_KEY:-local} \
	DYNAMO_ENDPOINT=$${DYNAMO_ENDPOINT:-http://localhost:$${DB_PORT:-8000}} \
	.venv/bin/python -m wolves.s3.init

app/up:
	@[ -f .worktree/allocate-ports.sh ] && .worktree/allocate-ports.sh || true
	@set -a; [ -f .env.worktree ] && . ./.env.worktree; set +a; \
	docker compose up -d --build; \
	echo "Web: http://localhost:$${FRONTEND_PORT:-3000}"

app/down:
	docker compose down --remove-orphans

app/restart:
	docker compose restart

app/logs:
	open http://localhost:$${DOZZLE_PORT:-9999} || true

# Snapshot the current runs/live state as the reusable demo fixtures (gitignored).
demo/save:
	@mkdir -p runs/demo
	@cp runs/live/state.json runs/live/results.json runs/demo/
	@echo "Saved current live state to runs/demo/"

# Load the demo fixtures and park the poller so it cannot overwrite them.
demo/on:
	.venv/bin/python scripts/demo_fixtures.py
	@set -a; [ -f .env.worktree ] && . ./.env.worktree; set +a; \
	JOBS_ENABLED=false AWS_PROFILE=$${AWS_PROFILE:-default} docker compose up -d backend
	@echo "Demo fixtures live; poller parked. Run 'make demo/off' to restore real data."

# Re-enable the poller; the next poll repopulates runs/live with real data.
demo/off:
	@set -a; [ -f .env.worktree ] && . ./.env.worktree; set +a; \
	JOBS_ENABLED=true AWS_PROFILE=$${AWS_PROFILE:-default} docker compose up -d backend
	@echo "Poller re-enabled; real live data will repopulate on the next poll."

frontend/install:
	cd web && npm install

frontend/dev:
	cd web && npm run dev

frontend/build:
	cd web && npm run build

frontend/lint:
	cd web && npm run lint && npx tsc --noEmit
