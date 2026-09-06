# Third-party notices

Stonks is licensed AGPL-3.0-only (see [LICENSE](LICENSE)). This file records
the third-party components the project redistributes and the licenses they
carry. Dependencies installed at build time from PyPI and npm keep their own
licenses as declared by each package.

## Vendored in this repository

- `app/agents/tradingagents/` is a subset of
  [TradingAgents](https://github.com/TauricResearch/TradingAgents) by
  TauricResearch, Apache License 2.0. The pinned upstream commit, the license,
  and the list of local modifications are recorded in
  `app/agents/tradingagents/NOTICE` and `app/agents/tradingagents/LICENSE`.

## Principal runtime dependencies

Backend (Python): FastAPI (MIT), Starlette (BSD-3), Uvicorn (BSD-3),
SQLAlchemy (MIT), Alembic (MIT), psycopg2 (LGPL-3.0), Celery (BSD-3),
redis-py (MIT), httpx (BSD-3), aiohttp (Apache-2.0), python-jose (MIT),
pydantic (MIT), yfinance (Apache-2.0), pandas (BSD-3), NumPy (BSD-3),
vaderSentiment (MIT), LangChain and LangGraph (MIT), openai (Apache-2.0),
ollama (MIT), feedparser (BSD-2), Beautiful Soup (MIT), lxml (BSD-3),
structlog (MIT or Apache-2.0), prometheus-client (Apache-2.0), alpaca-py
(Apache-2.0), python-dotenv (BSD-3).

Frontend (JavaScript): React and React DOM (MIT), React Router (MIT),
TanStack Query (MIT), Axios (MIT), Tailwind CSS (MIT), Headless UI (MIT),
Heroicons (MIT), Lucide (ISC), cmdk (MIT), date-fns (MIT), Recharts (MIT),
oidc-client-ts (Apache-2.0), react-oidc-context (MIT), Vite (MIT).

Container base images: `python:3.11-slim` (Debian), `node:22-alpine`,
`nginx:alpine`.

## Data sources

Each ingestion source is used under its own terms and none of the data is
redistributed by this repository:

- SEC EDGAR filings and RSS feeds (public domain; the SEC fair-access policy
  requires a declared contact, see `SEC_CONTACT_EMAIL`).
- Reddit (through the Reddit API with an operator-registered application).
- Google News RSS and other publisher RSS feeds (headlines and links only).
- Yahoo Finance quotes through yfinance, Alpha Vantage, and Polygon.io
  (operator API keys where required).
- Capitol Trades and SEC Form 13F filings for the political and fund-holding
  signal plugins.
- Alpaca Markets for brokerage (operator and user API keys).
