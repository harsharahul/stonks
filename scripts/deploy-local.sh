#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

SKIP_SEED=false
for arg in "$@"; do
  case "$arg" in
    --no-seed) SKIP_SEED=true ;;
  esac
done

echo ""
echo "━━━ Stonks: Build & Deploy (Local Docker) ━━━"
echo ""

# Start infra
echo "→ Starting postgres + redis..."
docker-compose up -d postgres redis
until docker-compose ps postgres 2>/dev/null | grep -q "healthy"; do sleep 1; done
echo "✓ Infrastructure ready"

# Build all
echo "→ Building stonks-api..."
docker-compose build --quiet stonks-api
echo "→ Building stonks-frontend..."
docker-compose build --quiet stonks-frontend
echo "✓ Images built"

# Deploy
echo "→ Deploying..."
docker-compose up -d stonks-api stonks-frontend
for svc in stonks-api stonks-frontend; do
    for i in {1..60}; do
        docker-compose ps "$svc" 2>/dev/null | grep -q "healthy" && break
        sleep 1
    done
done
echo "✓ Containers healthy"

# Smoke test
echo "→ Smoke test..."
curl -sf http://localhost:8080/health >/dev/null && echo "✓ API OK" || echo "✗ API not responding"
curl -sf http://localhost:3000/ >/dev/null && echo "✓ Frontend OK" || echo "✗ Frontend not responding"

# Seed initial data — trigger ingestion + feature calculation
if [ "$SKIP_SEED" = true ]; then
  echo "→ Skipping data seeding (--no-seed)"
else
  API_KEY="${API_KEY:-dev_local_key_change_me}"
  echo "→ Seeding data (ingestion + features)..."
  curl -sf -X POST "http://localhost:8080/api/v1/feed/ingest/wsb-enhanced?limit=50&sort=hot" \
    -H "X-API-Key: $API_KEY" >/dev/null 2>&1 && echo "  ✓ WSB Enhanced ingestion triggered" || echo "  ⚠ WSB ingestion failed"
  curl -sf -X POST "http://localhost:8080/api/v1/feed/ingest/wsb-hot?limit=50" \
    -H "X-API-Key: $API_KEY" >/dev/null 2>&1 && echo "  ✓ WSB Hot posts ingestion triggered" || echo "  ⚠ WSB hot ingestion failed"
  curl -sf -X POST "http://localhost:8080/api/v1/feed/ingest/rss-automated" \
    -H "X-API-Key: $API_KEY" >/dev/null 2>&1 && echo "  ✓ RSS news ingestion triggered" || echo "  ⚠ RSS ingestion failed"

  # Wait for ingestion to complete, then calculate features
  echo "  ⏳ Waiting 20s for ingestion to complete..."
  sleep 20
  curl -sf -X POST "http://localhost:8080/api/v1/features/calculate/daily" \
    -H "X-API-Key: $API_KEY" >/dev/null 2>&1 && echo "  ✓ Daily feature calculation triggered" || echo "  ⚠ Feature calculation failed"
  echo "  (Features will compute in ~30s — sentiment, returns, WSB metrics)"
fi

echo ""
echo "Frontend:  http://localhost:3000"
echo "API:       http://localhost:8080"
echo "API Docs:  http://localhost:8080/docs"
echo "WSB Board: http://localhost:3000/wsb-trending"
echo ""
echo "✓ Done!"
