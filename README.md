Stonks – Stock Tracker & Analyzer

Stonks is a web application that aggregates market data and public signals (news, social, pricing) to analyze stocks and generate daily buy suggestions. The system ingests data via crawlers and APIs, stores it in PostgreSQL, runs analytics to compute metrics and scores, and serves a feed and insights via a micro‑frontend web UI.

Key docs:

- docs/architecture.md – high‑level system architecture
- project-plan.md – step‑by‑step plan, milestones, and acceptance criteria
- docs/frontend-plan.md – micro‑frontend plan and pages
- docs/api-design.md – API endpoints and payloads
- db/schema.sql – PostgreSQL schema
- docs/data-pipeline.md – ingestion, scraping, and ETL plan
- docs/analytics-and-recommendations.md – scoring model and daily recommendations
- docs/project-tracker.md – live checklist to track progress

Tech choices (initial):

- Backend: Python 3.11 + FastAPI, Celery for async jobs, Redis for queue/cache
- Database: PostgreSQL 16
- Frontend: React + Vite micro‑frontends using Module Federation (inspired by 1fe.com patterns)

Status: Inception planning complete. See project-plan.md to begin execution.

Dev → Prod

- Local dev: docker-compose for DB, Redis, and optional Ollama; create a `.env` using keys in `docs/configuration.md`
- Staging/Prod: k3s manifests with Kustomize overlays; images built via Gitea Actions
- Optional analytics enrichment via OpenAI or Ollama; disabled by default


