-include .env
-include .env.worktree
export

.PHONY: setup venv lint format test precommit db/init release \
        app/up app/down app/restart app/logs \
        frontend/install frontend/dev frontend/build frontend/lint

setup: venv frontend/install

venv:
	rm -rf engine/.venv backend/.venv || true
	cd engine && uv venv && uv pip install -e ".[dev]"
	cd backend && uv venv && uv pip install -e ".[dev]"
	@echo "Done. Activate with: source engine/.venv/bin/activate"

lint:
	cd engine && .venv/bin/ruff check .
	cd backend && .venv/bin/ruff check .

format:
	cd engine && .venv/bin/ruff format . && .venv/bin/ruff check . --fix
	cd backend && .venv/bin/ruff format . && .venv/bin/ruff check . --fix

test:
	cd engine && .venv/bin/pytest tests/ -q
	cd backend && .venv/bin/pytest tests/ -q

precommit:
	pre-commit run --all-files

release:
	@scripts/release.sh $(env)

db/init:
	cd engine && \
	AWS_ACCESS_KEY_ID=$${AWS_ACCESS_KEY_ID:-local} AWS_SECRET_ACCESS_KEY=$${AWS_SECRET_ACCESS_KEY:-local} \
	DYNAMO_ENDPOINT=$${DYNAMO_ENDPOINT:-http://localhost:$${DB_PORT:-8000}} \
	.venv/bin/python -m wolves.store.init

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

frontend/install:
	cd web && npm install

frontend/dev:
	cd web && npm run dev

frontend/build:
	cd web && npm run build

frontend/lint:
	cd web && npm run lint && npx tsc --noEmit
