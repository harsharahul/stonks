Architecture – Stonks

System Components

- Data Sources: price APIs (Yahoo Finance/Alpha Vantage), news feeds (RSS/finance portals)
- Ingestion Service: scheduled fetchers, parsers, normalizers, deduplicators
- Analytics Service: batch jobs computing metrics/signals and daily recommendations
- LLM Adapter (optional): integrates OpenAI or Ollama to enrich analytics with contextual rationale; strictly optional with safe fallback
- API Backend: FastAPI serving `/api/v1` for feed, stocks, recommendations, signals
- Task Queue & Cache: Redis (Celery broker + cache)
- Database: PostgreSQL 16 as the system of record
- Frontend: React micro‑frontends (Vite Module Federation) hosted by an app shell

Data Flow

1. Ingestion fetchers pull data on schedules (Celery Beat)
2. Raw content is parsed and normalized (ticker extraction, timestamps, source attribution)
3. Records are upserted into PostgreSQL with idempotent keys (hashes, unique constraints)
4. Analytics jobs aggregate features and write `signals`
5. Daily job ranks stocks and writes to `recommendations`
6. API reads from PostgreSQL, caches hot queries in Redis if needed
7. Frontend queries APIs and renders the feed and insights

Quality & Observability

- Structured logging with correlation IDs per job run
- `etl_job_runs` table records every batch with status and metrics
- Health (`/health`) and readiness (`/ready`) endpoints

Scalability

- Horizontal scale of Celery workers for fetch and analytics
- Read replicas for PostgreSQL (later) if read traffic grows
- Caching popular endpoints (feed, top recommendations)
- Sharding/partitioning `prices` by date (future work) if needed
- LLM usage is budgeted and cached; local Ollama enables offline scaling when GPUs/CPUs available

Security

- Use API keys or basic auth for admin endpoints initially
- Validate and sanitize all external input (URLs, HTML) during ingestion
- Least‑privilege DB roles for app and worker
- Secrets via env or Kubernetes Secrets; LLM keys never logged; redact PII

Frontend Micro‑Frontend Topology

- App Shell: routing, layout, authentication, shared libs
- Remotes: `feed-mf`, `stock-mf`, `recs-mf`, `admin-mf`
- Shared UI kit and data layer abstractions

Dev → Prod Strategy

- Environments: `dev` (local via docker-compose), `staging` (single‑node k3s), `prod` (k3s HA optional later)
- Images: Dockerfiles per service; images published to container registry on CI
- Deploy: k8s manifests (manifests/*.yaml) with Kustomize overlays for `staging` and `prod`
- Database: managed PostgreSQL (preferred) or statefulset with backup jobs; migrations via Alembic
- CI/CD: Gitea Actions pipeline builds, tests, scans, and deploys on tag or main branch


