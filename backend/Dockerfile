FROM python:3.12-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.32.0" \
    "sqlalchemy>=2.0.0" \
    "asyncpg>=0.30.0" \
    "pydantic>=2.0.0" \
    "pydantic-settings>=2.0.0" \
    "httpx>=0.28.0" \
    "trafilatura>=2.0.0" \
    "ollama>=0.4.0" \
    "python-multipart>=0.0.18" \
    "alembic>=1.14.0"

# Copy application code
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
