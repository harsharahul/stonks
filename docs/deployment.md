# Deployment

## Images

Two images, published for `linux/amd64` and `linux/arm64` on every release
and on every push to `main`:

- `ghcr.io/harsharahul/stonks-backend`: API, workers, and Beat. The default
  command runs all of them under supervisord; a command override runs one
  role.
- `ghcr.io/harsharahul/stonks-frontend`: nginx serving the UI and proxying
  `/api/` to `stonks-api:8080`.

Tags: `latest` for main, the semantic version for releases (`2.0.0`), and
the short commit sha.

Build locally:

```bash
docker build -f Dockerfile.backend  -t stonks-backend  .
docker build -f Dockerfile.frontend -t stonks-frontend .
```

## Docker Compose

`docker-compose.yml` runs PostgreSQL, Redis, the backend (all roles), and
the frontend on port 3000. `docker compose --profile llm up -d` adds a local
Ollama. The backend entrypoint bootstraps the database as described below.

## Kubernetes

The backend image runs once per role:

| Role | Command | Replicas |
|---|---|---|
| API | `uvicorn app.main:app --host 0.0.0.0 --port 8080` | any |
| Fast worker | `celery -A app.worker worker -Q celery,compute,ingestion --concurrency=2` | any |
| LLM worker | `celery -A app.worker worker -Q analytics --concurrency=1` | any |
| Beat | `celery -A app.celery_beat_app beat` | exactly one, `strategy: Recreate` |

Running all roles in one pod with the default supervisord command is also
fine for a single-node cluster; keep it at one replica because of Beat.

Notes that matter in practice:

- The API's liveness and readiness endpoint is `/health`. The frontend
  container answers `/health` itself.
- WebSocket alerts are served under `/api/v1/ws/`; the ingress must allow
  upgrades on that path.
- Set `CORS_ORIGINS` to the public origin(s) and `ENVIRONMENT=production`.
- Put `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `BROKER_CREDS_ENCRYPTION_KEY`,
  and any API keys in a Secret; everything else can be a ConfigMap.
- LLM calls stream. If a reverse proxy or CDN sits in front of the Ollama
  host, make sure it does not buffer or cut long responses.
- Frontend OIDC settings are compile-time; build the frontend image with
  the build arguments in [configuration.md](configuration.md) for your
  identity provider.

## Database

The backend container runs `python -m app.core.bootstrap` before starting
any process: it waits for PostgreSQL, creates the schema from the models on
an empty database and stamps the Alembic head (the earliest migration only
alters tables, so a fresh install cannot replay history), runs
`alembic upgrade head` on an existing database, and seeds a starter
universe of twenty large caps when the stocks table is empty
(`STONKS_SKIP_SEED=1` disables the seed). Backups are the operator's
responsibility; every table lives in the one PostgreSQL database.

## Releases

Releases are cut from `main` with a version tag that matches the `VERSION`
file (`v2.0.0`). The release workflow verifies the tag, the changelog
entry, the tests, and the frontend build, and CI publishes the images.
