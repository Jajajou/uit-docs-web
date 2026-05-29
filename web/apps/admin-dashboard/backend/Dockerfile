FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system deps required by some Python wheels (psycopg2 build, healthcheck curl).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first so docker layer cache stays warm across code edits.
COPY requirements.txt requirements-dev.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir \
        "fastapi>=0.115.0" \
        "uvicorn[standard]>=0.32.0" \
        "python-multipart>=0.0.12" \
        "python-dotenv>=1.0.1" \
        "requests>=2.31.0" \
        "pydantic>=2.9.0" \
        "aiofiles>=24.1.0" \
        "sqlalchemy>=2.0.0" \
        "psycopg2-binary>=2.9.0" \
        "alembic>=1.13.0"

# Copy application source.
COPY api/ ./api/
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Render's filesystem is ephemeral; default UPLOAD_DIR points at /tmp/uploads
# unless overridden by the environment.
RUN mkdir -p /tmp/uploads /app/data

EXPOSE 8001

# Render healthcheck contract (also useful for compose/runner setups).
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8001}/health" || exit 1

# Render injects $PORT at runtime; fall back to 8001 for local docker run.
# Run alembic migrations before starting the API so schema is always current.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8001}"]
