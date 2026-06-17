FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS development

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_INSTALL_DIR=/python
ENV UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app

COPY backend/.python-version .
RUN uv python install

COPY pyproject.toml uv.lock ./
COPY engine/pyproject.toml engine/
COPY engine/wolves/__init__.py engine/wolves/
COPY backend/pyproject.toml backend/
COPY backend/wolves_backend/__init__.py backend/wolves_backend/
RUN uv sync --frozen --package wolves-backend --extra dev

COPY engine/ engine/
COPY backend/ backend/
COPY data/ data/

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/backend
ENTRYPOINT ["sh", "entrypoint.dev.sh"]
CMD ["uvicorn", "wolves_backend.main:build", "--factory", "--host", "0.0.0.0", "--port", "8080", "--reload"]


FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS production

COPY --from=development /python /python

WORKDIR /app
COPY --from=development /app/ /app/

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080
WORKDIR /app/backend
ENTRYPOINT ["uvicorn", "wolves_backend.main:build", "--factory", "--host", "0.0.0.0", "--port", "8080"]
