FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS development

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_INSTALL_DIR=/python
ENV UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app

COPY engine/.python-version .
RUN uv python install

COPY pyproject.toml uv.lock ./
COPY engine/pyproject.toml engine/
COPY engine/wolves/__init__.py engine/wolves/
COPY backend/pyproject.toml backend/
COPY backend/wolves_backend/__init__.py backend/wolves_backend/
RUN uv sync --frozen --package wolves --extra dev

COPY engine/ engine/
COPY data/ data/

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/engine
ENTRYPOINT ["sh", "entrypoint.dev.sh"]
CMD ["python", "-m", "wolves.run"]


FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS production

COPY --from=development /python /python

WORKDIR /app
COPY --from=development /app/ /app/

ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app/engine
ENTRYPOINT ["python", "-m"]
CMD ["wolves.run"]
