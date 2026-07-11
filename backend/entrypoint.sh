#!/bin/sh
# Container entrypoint: apply database migrations, then start the API.
set -e

echo "Applying database migrations..."
python -m app.migrate

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
