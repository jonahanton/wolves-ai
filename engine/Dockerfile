FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS development

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
ENV UV_PYTHON_INSTALL_DIR=/python
ENV UV_PYTHON_PREFERENCE=only-managed

WORKDIR /app/engine

COPY engine/.python-version .
RUN uv python install

COPY engine/pyproject.toml ./
COPY engine/wolves/__init__.py wolves/
RUN uv venv && uv pip install -e ".[dev]"

COPY engine/ .

ENV PATH="/app/engine/.venv/bin:$PATH"

ENTRYPOINT ["sh", "entrypoint.dev.sh"]
CMD ["python", "-m", "wolves.run"]


FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS production

COPY --from=development /python /python

WORKDIR /app/engine
COPY --from=development /app/engine/ /app/engine/

ENV PATH="/app/engine/.venv/bin:$PATH"

ENTRYPOINT ["python", "-m"]
CMD ["wolves.run"]
