-include .env
-include .env.worktree
export

.PHONY: setup venv lint format test precommit db/init \
        app/up app/down app/restart app/logs \
        archive/up archive/down archive/image archive/deploy \
        demo/on demo/off \
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

archive/up:
	@[ -f .worktree/allocate-ports.sh ] && .worktree/allocate-ports.sh || true
	@set -a; [ -f .env.worktree ] && . ./.env.worktree; set +a; \
	docker compose --project-name "$${WORKSPACE_NAME:-wolves-ai-archive}" \
		-f web/docker-compose-archive.yml up -d --build; \
	echo "Archive: http://localhost:$${FRONTEND_PORT:-3000}"

archive/down:
	@set -a; [ -f .env.worktree ] && . ./.env.worktree; set +a; \
	docker compose --project-name "$${WORKSPACE_NAME:-wolves-ai-archive}" \
		-f web/docker-compose-archive.yml down

archive/image:
	@test -n "$${STATIC_ARCHIVE_DIR}" || { echo "STATIC_ARCHIVE_DIR is required"; exit 2; }
	docker build --target production \
		--build-context archive-source="$${STATIC_ARCHIVE_DIR}" \
		-t "$${ARCHIVE_IMAGE:-wolves-static-archive}" web

archive/deploy:
	@scripts/deploy_static_archive.sh

# Back up the real live state, write the demo scenario, and park the poller.
demo/on:
	.venv/bin/python scripts/demo_fixtures.py on
	@scripts/set_env.sh JOBS_ENABLED false
	@set -a; [ -f .env.worktree ] && . ./.env.worktree; set +a; \
	AWS_PROFILE=$${AWS_PROFILE:-default} docker compose up -d --force-recreate backend
	@echo "Demo fixtures live; poller parked. Run 'make demo/off' to restore real data."

# Restore the real live state and re-enable the poller.
demo/off:
	.venv/bin/python scripts/demo_fixtures.py off
	@scripts/set_env.sh JOBS_ENABLED true
	@set -a; [ -f .env.worktree ] && . ./.env.worktree; set +a; \
	AWS_PROFILE=$${AWS_PROFILE:-default} docker compose up -d --force-recreate backend
	@echo "Real live state restored; poller re-enabled."

frontend/install:
	cd web && npm install

frontend/dev:
	cd web && npm run dev

frontend/build:
	cd web && npm run build

frontend/lint:
	cd web && npm run lint && npx tsc --noEmit
