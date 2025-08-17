Architecture – Stonks

System Components

- **AI-Powered Signal Intelligence**: LangGraph-based multi-step AI workflows for intelligent signal processing
- **Expandable Signal Sources**: Plugin-based architecture supporting unlimited data sources (political trades, social media, news, regulatory filings)
- **Self-Correcting Data System**: LLM-powered validation and automatic error correction
- **Intelligent Signal Routing**: AI-driven prioritization and multi-channel distribution
- **Politician Trades Monitoring**: Real-time Congressional and Senate stock disclosure tracking
- **Data Sources**: price APIs (Yahoo Finance/Alpha Vantage), news feeds (RSS/finance portals), political disclosures, social media
- **Ingestion Service**: scheduled fetchers, parsers, normalizers, deduplicators with AI enhancement
- **Analytics Service**: batch jobs computing metrics/signals and daily recommendations with LLM synthesis
- **API Backend**: FastAPI serving `/api/v1` for feed, stocks, recommendations, signals, and intelligent signal processing
- **Real-Time System**: WebSocket infrastructure for live alerts and market updates
- **Error Handling**: Comprehensive error management with user-friendly messaging
- **Task Queue & Cache**: Redis (Celery broker + cache)
- **Database**: PostgreSQL 16 as the system of record with enhanced signal storage
- **Frontend**: React micro‑frontends (Vite Module Federation) hosted by an app shell with real-time AI insights

Data Flow (Enhanced AI Pipeline)

1. **Signal Ingestion**: Multi-source data collection (news, political trades, social media, market data)
2. **LangGraph Processing**: AI-powered analysis, validation, and enrichment through multi-step workflows
3. **Self-Correcting Writes**: Automatic error detection and correction before database persistence
4. **Intelligent Routing**: AI-driven signal prioritization and multi-channel distribution
5. **Real-Time Distribution**: WebSocket broadcasts, alerts, API responses, and dashboard updates
6. **Quality Monitoring**: Continuous assessment and improvement of signal processing accuracy

Traditional Flow (Still Supported):
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
- Comprehensive error handling with user-friendly messaging
- Request tracking with unique IDs for support and debugging
- WebSocket connection monitoring and automatic recovery

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

- Environments: `dev` (local via docker-compose), `prod` (k3s deployment)
- Images: Dockerfiles per service; images published to container registry on CI
- Deploy: k8s manifests (manifests/*.yaml) with Kustomize overlays for prod
- Database: managed PostgreSQL (preferred) or statefulset with backup jobs; migrations via Alembic
- CI/CD: Gitea Actions pipeline builds, tests, scans, and deploys on git tags

## System Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │      API        │    │     Worker      │
│   (React MF)    │    │   (FastAPI)     │    │   (Celery)      │
│   Port 80       │    │   Port 8080     │    │   Background    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Ingress       │    │   PostgreSQL    │    │     Redis       │
│   / → Frontend  │    │   (Database)    │    │   (Queue/Cache) │
│   /api → API    │    └─────────────────┘    └─────────────────┘
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   CronJob       │
│   Analytics     │
│   Daily 00:30   │
└─────────────────┘
```

## Request Routing Flow

- **`/`** → Frontend (React micro-frontend app shell)
- **`/api/*`** → API Backend (FastAPI with `/api/v1` endpoints)
- **Background**: Worker processes + Analytics CronJob

## Service Responsibilities

- **Frontend**: React micro-frontend app shell, routing, shared components
- **API**: FastAPI serving `/api/v1` endpoints, health checks, data access
- **Worker**: Celery background tasks, data ingestion, ETL processing
- **Analytics CronJob**: Daily scheduled analytics and recommendations generation


