#!/usr/bin/env bash
set -euo pipefail

# repo root
cd "$(dirname "$0")/.."

# Start infra
docker-compose up -d

# Wait for Postgres
printf "Waiting for Postgres to be ready"
for i in {1..30}; do
  if docker exec stonks-postgres-1 pg_isready -U stonks -d stonks >/dev/null 2>&1; then
    echo " - ready"; break
  fi
  printf "."; sleep 1
  if [[ "$i" == "30" ]]; then echo "\nPostgres not ready"; exit 1; fi
done

# Enable uuid-ossp extension
docker exec -i stonks-postgres-1 psql -U stonks -d stonks -c 'CREATE EXTENSION IF NOT EXISTS "uuid-ossp";' >/dev/null

# Python venv
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -U pip >/dev/null
pip install -r requirements.txt >/dev/null

# Create tables
python - <<'PY'
from app.core.database import engine
from app.models.base import Base
import importlib
for m in [
    "app.models.stock",
    "app.models.data_source",
    "app.models.article",
    "app.models.price",
    "app.models.signal",
    "app.models.recommendation",
    "app.models.etl_job_run",
]:
    importlib.import_module(m)
Base.metadata.create_all(bind=engine)
print("DB tables ready")
PY

# Start API
if [[ -f .uvicorn.pid ]] && kill -0 $(cat .uvicorn.pid) 2>/dev/null; then
  echo "API already running (PID $(cat .uvicorn.pid))"
else
  nohup uvicorn app.main:app --host 0.0.0.0 --port 8080 --log-level info > .uvicorn.log 2>&1 & echo $! > .uvicorn.pid
  echo "API started on http://localhost:8080 (PID $(cat .uvicorn.pid))"
fi

# Smoke check
sleep 1
curl -sS http://localhost:8080/health || true
