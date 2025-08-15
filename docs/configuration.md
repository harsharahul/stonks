Configuration

Create a `.env` at the repo root for local dev with the following keys:

```
# Core services
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=stonks
POSTGRES_USER=stonks
POSTGRES_PASSWORD=stonks_password_change_me

REDIS_HOST=redis
REDIS_PORT=6379

# API
API_HOST=0.0.0.0
API_PORT=8080

# LLM Analytics (optional)
ANALYTICS_LLM_PROVIDER=none # none | openai | ollama
OPENAI_API_KEY=
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL=llama3:8b
```

For k3s, use Kubernetes Secrets for sensitive values and ConfigMaps for non‑secrets. See `manifests/base/configmap.yaml` for defaults.


