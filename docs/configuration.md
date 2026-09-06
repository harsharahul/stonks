# Configuration

Every setting is an environment variable read by `app/core/config.py`
(Pydantic Settings, `.env` honored in development). `.env.example` lists them
all with placeholders. Nothing is required beyond the database and Redis;
every integration degrades to "skipped" when its key is absent.

## Core

| Variable | Meaning | Default |
|---|---|---|
| `ENVIRONMENT` | `development`, `staging`, or `production`; validated at startup | `development` |
| `DEBUG` | verbose logging | `false` |
| `API_HOST`, `API_PORT` | bind address for uvicorn | `0.0.0.0`, `8080` |
| `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | database | `postgres`, `5432`, `stonks`, none, `stonks` |
| `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, `REDIS_PASSWORD` | broker and pub/sub; passwords with special characters are URL-encoded internally | `redis`, `6379`, `0`, none |
| `CORS_ORIGINS` | comma-separated browser origins allowed in production (localhost origins are always allowed) | empty |
| `ENABLE_RATE_LIMIT`, `RATE_LIMIT_PER_MINUTE` | per-client API rate limit | `true`, `60` |
| `API_KEY` | optional shared key for machine clients | none |

## LLM

| Variable | Meaning | Default |
|---|---|---|
| `ANALYTICS_LLM_PROVIDER` | `none`, `ollama`, or `openai` | `none` |
| `OLLAMA_HOST` | Ollama base URL | `http://localhost:11434` |
| `OLLAMA_MODEL` | quick-tier model for analysts, debate, and knowledge distillation | `qwen3:14b` |
| `OLLAMA_DEEP_MODEL` | deep-tier model for the research manager, trader, and portfolio manager | same as `OLLAMA_MODEL` |
| `OPENAI_API_KEY` | used when the provider is `openai` | none |

## Data sources

| Variable | Meaning |
|---|---|
| `ALPHA_VANTAGE_API_KEY` | earnings calendar; without it the task skips |
| `POLYGON_API_KEY` | reserved for market data; prices currently come from yfinance |
| `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USER_AGENT` | Reddit API application (script type); without it Reddit ingestion skips |
| `SEC_CONTACT_EMAIL` | contact address declared to SEC EDGAR, as its fair-access policy requires |

## Identity

| Variable | Meaning |
|---|---|
| `OIDC_ISSUER_URL` | OpenID Connect issuer; tokens are validated against its JWKS with the issuer from the discovery document |
| `OIDC_CLIENT_ID` | the public client id; also the audience unless `OIDC_AUDIENCE` is set |
| `OIDC_AUDIENCE` | override the expected audience |
| `ADMIN_EMAILS` | comma-separated operator addresses; compared in constant time |
| `VITE_OIDC_AUTHORITY`, `VITE_OIDC_CLIENT_ID` | the same issuer and client id, compiled into the frontend bundle at build time |
| `VITE_API_BASE_URL` | frontend API base; defaults to `/api/v1` behind the nginx proxy |

Both issuer and client id must be set, or neither. With neither set, the
API runs without authentication and the admin console is open, which is
allowed only in the development environment; production without OIDC
returns 401 on protected routes.

## Trading

| Variable | Meaning |
|---|---|
| `BROKER_CREDS_ENCRYPTION_KEY` | Fernet key for stored broker credentials; generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `BROKER_TRADING_HALTED` | `true` refuses every order |

## Frontend build arguments

The frontend image compiles `VITE_OIDC_AUTHORITY` and `VITE_OIDC_CLIENT_ID`
into the bundle:

```bash
docker build -f Dockerfile.frontend \
  --build-arg VITE_OIDC_AUTHORITY=https://auth.example.com/application/o/stonks/ \
  --build-arg VITE_OIDC_CLIENT_ID=your-client-id \
  -t stonks-frontend .
```

The published image is built without them, which yields a frontend with
sign-in disabled. Runtime configuration is on the roadmap.
