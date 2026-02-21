#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application on port 8080..."
exec gunicorn \
  --bind 0.0.0.0:8080 \
  --workers 2 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  app:app
