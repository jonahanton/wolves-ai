FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS development

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_INSTALL_DIR=/python
ENV UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app/backend

COPY backend/.python-version .
RUN uv python install

COPY backend/pyproject.toml ./
COPY backend/wolves_backend/__init__.py wolves_backend/
RUN uv venv && uv pip install -e ".[dev]"

COPY backend/ .

ENV PATH="/app/backend/.venv/bin:$PATH"

ENTRYPOINT ["sh", "entrypoint.dev.sh"]
CMD ["uvicorn", "wolves_backend.main:build", "--factory", "--host", "0.0.0.0", "--port", "8080", "--reload"]


FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS production

COPY --from=development /python /python

WORKDIR /app/backend
COPY --from=development /app/backend/ /app/backend/

ENV PATH="/app/backend/.venv/bin:$PATH"

EXPOSE 8080
ENTRYPOINT ["uvicorn", "wolves_backend.main:build", "--factory", "--host", "0.0.0.0", "--port", "8080"]
