#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

# Stop API
if [[ -f .uvicorn.pid ]]; then
  PID=$(cat .uvicorn.pid || true)
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID" || true
    echo "Stopped API (PID $PID)"
  fi
  rm -f .uvicorn.pid
fi

# Stop infra
docker-compose down
