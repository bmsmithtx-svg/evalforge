FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system evalforge && useradd --system --gid evalforge evalforge

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY alembic ./alembic

RUN pip install --no-cache-dir .

USER evalforge

EXPOSE 8000

CMD ["uvicorn", "evalforge_api.asgi:app", "--host", "0.0.0.0", "--port", "8000"]
