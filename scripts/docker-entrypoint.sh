#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head || echo "WARNING: Migration failed (DB may not be ready yet or already up to date)"

echo "Starting application..."
exec "$@"
