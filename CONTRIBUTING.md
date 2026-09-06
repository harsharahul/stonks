# Contributing to Stonks

Thanks for your interest. Stonks is a market terminal whose value rests on
being measurable and honest; contributions that keep it that way are very
welcome.

## Principles

- **Signals are public facts with a public record.** A signal source
  computes once for everyone and its accuracy is scored nightly on realized
  returns. Never fork signal computation per user, never tune a source to
  look good in hindsight, and never describe a signal in advice language
  ("buy now"); stances are bullish, bearish, or neutral with the evidence
  attached.
- **The platform never trades on its own.** Every order is placed by a
  signed-in user from a ticket they confirmed. Copy-trading mirrors are paper
  only. Any change that removes a gate, a confirmation, or the kill switch is
  out of scope.
- **Fail honestly.** When a provider is down or a key is missing, the task
  skips and says so. No fabricated rows, no canned analysis presented as
  live, no silent fallbacks.
- **No secrets in code.** Keys arrive through environment variables or the
  plugin `required_config` mechanism. Nothing credential-shaped is ever
  hardcoded, logged, or committed.
- **Every change lands with tests.** The backend suite runs in seconds with
  no database. New behavior gets a test that fails before the change and
  passes after.

## Development

```bash
docker compose up -d postgres redis
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8080
celery -A app.worker worker -Q celery,compute,ingestion,analytics --loglevel=info
celery -A app.celery_beat_app beat --loglevel=info
cd frontend && npm ci && npm run dev
```

Checks before a pull request:

```bash
pytest                                  # backend unit tests
pip-audit                               # known vulnerabilities in Python deps
cd frontend && npm run build && npm audit --omit=dev
```

The repository layout:

```
app/api/v1/endpoints/   FastAPI routers, one per resource
app/core/               settings, database, auth, signal framework
app/models/             SQLAlchemy models (schema changes go through Alembic)
app/services/           broker, consolidation, alerts, anomaly detection
app/signals/            signal source plugins
app/tasks/              Celery tasks (ingestion, features, signals, desk)
app/agents/             AI Trading Desk (vendored TradingAgents plus adapters)
frontend/src/           React + TypeScript + Tailwind terminal UI
alembic/                migrations
tests/                  backend unit tests
docs/                   shipped behavior, present tense
```

Conventions: async database access, Pydantic models for request and
response bodies, type hints everywhere. New endpoints are mounted in
`app/api/v1/api.py`; new Celery tasks are imported in `app/worker.py` and
scheduled in `app/celery_beat_config.py`. Schema changes always ship with an
Alembic revision. Frontend server state goes through React Query and the
shared Axios client; every new screen supports both themes and small
viewports.

## Signal plugins

The most useful contribution is a new signal source. The full guide, with a
copyable template and the review criteria, is
[docs/signal-plugins.md](docs/signal-plugins.md).

## Pull requests

- One change per pull request, described in terms of what it does for the
  operator or the user.
- Commit messages in the form `type: short description` with `feat`, `fix`,
  `docs`, `refactor`, `chore`, or `test`.
- Add a line under the Unreleased heading in `CHANGELOG.md`.
- For user-visible changes to the UI, include a screenshot in both themes.
- By opening a pull request you agree to the terms in [CLA.md](CLA.md).

## Reporting problems

Bugs and feature requests go to the issue tracker. Anything exploitable goes
to the address in [SECURITY.md](SECURITY.md) instead.
