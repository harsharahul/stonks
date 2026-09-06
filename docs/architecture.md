# Architecture

## Services

| Service | Role |
|---|---|
| API | FastAPI on port 8080. Routers under `/api/v1/`, OpenAPI at `/api/v1/openapi.json`, health at `/health`, Prometheus metrics at `/api/v1/metrics/metrics`. |
| Workers | Celery. Queues: `celery` (default), `compute`, `ingestion`, `analytics`. The backend image runs two worker processes: one bound to `analytics` for LLM work (desk runs, knowledge distillation) and one bound to the fast queues, so a long desk run never delays ingestion. |
| Beat | The Celery scheduler, `app.celery_beat_app`. Exactly one instance may run. |
| PostgreSQL 16 | All state. Schema managed by Alembic. |
| Redis 7 | Celery broker and result backend, and the pub/sub channel behind WebSocket alerts. |
| Frontend | nginx serving the Vite bundle, proxying `/api/` to the API so the browser talks to one origin. |
| Ollama (optional) | Local LLM host for the analytics agent and the AI Trading Desk. |

One backend image (`Dockerfile.backend`) serves all backend roles. Under
Docker Compose, supervisord inside the container runs the API, both workers,
and Beat. Under Kubernetes the same image is run once per role with a command
override; see [deployment.md](deployment.md).

## Data flow

1. Ingestion tasks pull RSS news, Reddit, SEC EDGAR, the earnings calendar,
   and OHLCV prices into `articles`, `prices`, and related tables. Every
   article gets a sentiment score on the way in.
2. The daily feature calculator aggregates per ticker into
   `ticker_features_daily`: sentiment windows, sentiment shock, novelty,
   momentum, one- and five-day returns, volume z-score, Reddit mention
   counts, retail buzz, meme indicator, article counts.
3. Signal generation (rule-based, ten signal types), the anomaly detector,
   and the plugin dispatcher write `signals`; the alert engine turns
   qualifying signals into `alerts` and publishes them on Redis.
4. The WebSocket manager fans alerts out to connected browsers.
5. The AI Trading Desk runs its nightly batch over the desk universe and
   writes runs, briefs, and decisions.
6. Outcome scorers record what prices did after each signal and each desk
   decision. Strategy performance is computed from real fills.
7. The consolidation service reads all of the above and serves one ranked
   list per request, cached for a short window.

## Schedule (UTC)

| Task | When |
|---|---|
| RSS news ingestion | every 10 minutes |
| Post-ingest processing | every 15 minutes |
| Reddit ingestion | every 30 minutes |
| Signal plugin dispatch | every 30 minutes |
| Anomaly monitoring | every 15 minutes |
| Alert generation | every 5 minutes |
| Price OHLCV | hourly |
| SEC EDGAR filings | every 2 hours; CIK-to-ticker mapping 30 minutes later |
| Stock knowledge distillation | 02:30 daily |
| Article and job-run cleanup | 03:00 and 03:15 daily |
| Daily features | 05:00 daily |
| Daily signals | 06:00 daily |
| Daily recommendations | 06:30 daily |
| Earnings calendar | 07:00 daily |
| Desk nightly batch | 07:15 daily |
| Expired-signal cleanup | every 6 hours |
| Desk outcome scoring | 23:00 daily |
| Strategy performance | 23:30 daily |
| Signal outcome scoring | 23:45 daily |
| Desk universe refresh | Sunday 00:00 |

Every scheduled task also appears in the admin console with a Run Now
button and its job history.

## API surface

`/stocks`, `/stocks-enhanced`, `/prices`, `/feed`, `/features`, `/signals`,
`/anomalies`, `/recommendations`, `/market-analysis`, `/desk`,
`/consolidated`, `/strategies`, `/broker`, `/auth`, `/users`, `/admin`,
`/metrics`, and `/ws` for WebSocket channels. Public data is readable without
a token; anything about a user's own account requires a bearer token; the
admin routes require the operator allowlist.

## Frontend

React 18, TypeScript, Vite, Tailwind, React Router, React Query. Routes:
`/` dashboard, `/stocks`, `/stocks/:symbol`, `/desk` and `/desk/:ticker`,
`/intelligence`, `/signals`, `/strategies` and `/strategies/:slug`,
`/anomalies`, `/wsb-trending`, `/system`, and behind sign-in `/portfolio`,
`/watchlist`, `/profile`, `/admin`. The WebSocket hook reconnects with
exponential backoff. The command palette (Ctrl+K) covers navigation and
ticker search.

## Storage

Principal tables: `stocks`, `articles`, `prices`, `ticker_features_daily`,
`signals`, `signal_outcomes`, `signal_source_states`, `alerts`,
`recommendations`, `stock_knowledge`, `etl_job_runs`; the desk's
`agent_runs`, `agent_briefs`, `agent_decisions`, `agent_decision_outcomes`,
`agent_universe_membership`; and the user layer `users`, `watchlist_items`,
`user_broker_accounts`, `broker_orders`, `strategies`, `strategy_follows`,
`strategy_performance_daily`.
