FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml README.md .python-version alembic.ini ./
COPY alembic ./alembic
COPY src ./src
COPY agents ./agents
COPY data ./data

RUN pip install --no-cache-dir uv \
    && uv sync --no-dev --extra google --extra extract --extra export

ENV PYTHONPATH=/app/src

CMD ["/app/.venv/bin/python", "-m", "school_guardian", "serve"]
