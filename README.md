# Stonks

**A self-hostable market terminal: open signals with public track records, an AI analyst desk that debates every stock, and paper trading through your own broker.**

[![CI](https://github.com/harsharahul/stonks/actions/workflows/ci.yml/badge.svg)](https://github.com/harsharahul/stonks/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/harsharahul/stonks)](https://github.com/harsharahul/stonks/releases/latest)
[![Docker](https://img.shields.io/badge/ghcr.io-stonks--backend-2496ed?logo=docker&logoColor=white)](https://github.com/harsharahul/stonks/pkgs/container/stonks-backend)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white)](requirements.txt)
[![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)](LICENSE)

Stonks ingests news, social chatter, filings, and prices for the tickers you
track, turns them into signals whose accuracy is measured in public, runs a
multi-agent AI desk over each name every night, and blends everything into one
ranked list with the reasoning attached. When you want to act, the trade
ticket is prefilled and sent to your own Alpaca account, paper by default.

> Stonks is software for research and education. Nothing it produces is
> investment advice, every signal source carries a measured win rate that is
> often below fifty percent, and any order you place is your own decision.

## What it does

- **Signal sources as plugins, judged in public.** Every source is a small
  Python module behind one interface. Sources ship with the platform for
  Reddit momentum, congressional trades, tracked public-figure news, board-seat
  positioning, and institutional 13F holdings, and anyone can add one. A
  nightly scorer records each signal's five-day realized return, so every
  source has a public win rate and average return that the rest of the system
  uses as its weight. See [docs/signal-plugins.md](docs/signal-plugins.md).
- **AI Trading Desk.** A twelve-agent pipeline (market, social, news, and
  fundamentals analysts; bull and bear researchers; a research manager; a
  trader; three risk debaters; a portfolio manager) debates each ticker in the
  desk universe and lands on a decision with the full transcript kept. Past
  decisions are scored against what the price did next. Runs on local models
  through Ollama by default. See [docs/trading-desk.md](docs/trading-desk.md).
- **Consolidated rankings.** Signal consensus (weighted by each source's
  verified record), the desk's verdict and conviction, and the quantitative
  recommendation are blended into one score per ticker, with the breakdown
  shown rather than hidden. One click opens a prefilled trade ticket; the
  platform never trades on its own.
- **Broker integration.** Link an Alpaca account per user; keys are encrypted
  at rest and never shown again. Market and limit orders with optional
  bracket stops, pre-trade sanity gates that fail closed for live accounts,
  risk-budgeted size suggestions, a portfolio page, and a global kill switch.
  See [docs/broker.md](docs/broker.md).
- **Strategies.** Publish a strategy, tag your orders to it, and let others
  follow it. Track records are computed nightly from real fills and shown with
  mandatory disclosures. Followers can mirror trades into their own paper
  account with independent sizing; live auto-copy is not offered.
- **Data pipeline.** RSS news with sentiment every ten minutes, Reddit every
  thirty, SEC EDGAR filings every two hours, an earnings calendar daily, and
  hourly prices during market hours. Daily per-ticker features (sentiment,
  momentum, novelty, volume anomalies, retail buzz), anomaly detection every
  fifteen minutes, rule-based signals, and alerts pushed over WebSocket.
- **Terminal UI.** Dashboard, stock list and detail (candlesticks, RSI, MACD,
  Bollinger bands, pattern detection), market intelligence, signals explorer,
  anomaly explorer, strategies, portfolio, watchlist, and an admin console for
  every scheduled job. Command palette on Ctrl+K, dark and light themes.
- **Identity.** OpenID Connect with PKCE against any provider (Authentik is
  the reference), per-user watchlists and alert subscriptions, an admin
  allowlist. Everything public stays readable without signing in.

## Quick start

Requirements: Docker with Compose. For the AI desk, an
[Ollama](https://ollama.com) host with a model pulled (the default is
`qwen3:14b`); everything else works without it.

```bash
git clone https://github.com/harsharahul/stonks.git
cd stonks
cp .env.example .env            # fill in what you have; every key is optional
docker compose up -d            # postgres, redis, backend (api + workers + beat), frontend
open http://localhost:3000
```

The first start creates the schema and seeds a small ticker universe. Add
tickers from the Stocks page or the watchlist; history is backfilled
automatically. The admin console at `/admin` lists every scheduled job with a
Run Now button (open without sign-in in the development environment).

To develop against the stack instead of running it in containers:

```bash
docker compose up -d postgres redis
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8080          # API
celery -A app.worker worker -Q celery,compute,ingestion,analytics --loglevel=info
celery -A app.celery_beat_app beat --loglevel=info  # scheduler, exactly one instance
cd frontend && npm ci && npm run dev                # http://localhost:3000, proxies /api
pytest                                              # backend unit tests
```

## Configuration

Everything is an environment variable, documented in
[`.env.example`](.env.example) and [docs/configuration.md](docs/configuration.md):
database and Redis, the LLM provider (`none`, `ollama`, or `openai`), market
data keys (Alpha Vantage, Polygon), Reddit API credentials, the SEC contact
address, OpenID Connect issuer and client, the admin allowlist, the broker
encryption key, and the trading kill switch.

## Documentation

- [docs/architecture.md](docs/architecture.md): services, data flow, schedules
- [docs/signal-plugins.md](docs/signal-plugins.md): writing a signal source
- [docs/trading-desk.md](docs/trading-desk.md): the multi-agent pipeline
- [docs/broker.md](docs/broker.md): account linking, orders, gates, strategies
- [docs/configuration.md](docs/configuration.md): every setting
- [docs/deployment.md](docs/deployment.md): images, Compose, Kubernetes notes
- [ROADMAP.md](ROADMAP.md): what is next
- [CHANGELOG.md](CHANGELOG.md): what shipped

## Contributing

Signal plugins are the easiest place to start; the guide in
[docs/signal-plugins.md](docs/signal-plugins.md) walks through one. Read
[CONTRIBUTING.md](CONTRIBUTING.md) for the principles and the development
loop, and [CLA.md](CLA.md) for the terms every contribution is made under.

## License

AGPL-3.0-only. See [LICENSE](LICENSE). Third-party components and data
sources are listed in [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).
