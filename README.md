# ob4scate

`ob4scate` is a Python/FastAPI gateway for redacting sensitive text before it is sent to a
local or private LLM. The repository contains authentication and RBAC, policy-based
redaction, encrypted token mappings, LLM routing, and tamper-evident audit storage.

This codebase is an actively developed foundation. The checked-in
[implementation plan](./IMPLEMENTATION_PLAN.md) lists larger enterprise features that are
not yet complete, including external identity providers, Kubernetes deployment, distributed
tracing, provider failover, and model fine-tuning.

## Security model

- No built-in username or password is enabled. A bootstrap administrator is created only
  when `BOOTSTRAP_ADMIN_PASSWORD` is explicitly configured.
- Access and refresh tokens are audience- and issuer-bound. Refresh tokens rotate after use
  and are tied to a server-side session.
- RBAC checks fail closed for unknown permissions and prevent cross-tenant resource access.
- Sanitization endpoints return only redacted output, never the original input.
- Token-vault originals are encrypted with a Fernet key before PostgreSQL storage.
- Audit rows are HMAC chained. `/verify` reports the first row whose contents or chain link
  has been modified.
- Docker publishes only the gateway on `127.0.0.1`; backing services stay on the Compose
  network.

TLS termination, secret management, rate limiting, and an external identity provider are
deployment responsibilities and must be configured before exposing the gateway publicly.

## Repository layout

```text
gateway_proxy/         Unified API and authorization boundary
auth_service/          JWT, sessions, password hashing, and RBAC
obfuscation_engine/    Email and named-entity redaction
policy_engine/         Validated, hot-reloadable redaction rules and admin UI
tokenization_vault/    Encrypted token mappings in PostgreSQL
litellm_integration/   Async Ollama-compatible LLM connector and routing rules
audit_logging/         HMAC-chained SQLite audit events
```

## Local development

Prerequisites: Python 3.11, [uv](https://docs.astral.sh/uv/), and optionally Docker Desktop.

```bash
./scripts/uv-local sync --all-groups
cp .env.example .env
```

Replace every placeholder in `.env`. Generate strong values with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
./scripts/uv-local run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Load the environment and start the unified gateway:

```bash
set -a
source .env
set +a
./scripts/uv-local run uvicorn gateway_proxy.main:app --reload --port 8000
```

The API documentation is at <http://127.0.0.1:8000/docs> and health is at
<http://127.0.0.1:8000/health>.

## Validation

```bash
./scripts/uv-local run ruff check .
./scripts/uv-local run ruff format --check .
./scripts/uv-local run bandit -c pyproject.toml -x "*/test_*.py" -r audit_logging auth_service gateway_proxy \
  litellm_integration obfuscation_engine policy_engine tokenization_vault
./scripts/uv-local run pip-audit
APP_ENV=test \
JWT_SECRET_KEY=test-only-secret-key-with-at-least-32-characters \
AUDIT_LOG_SIGNING_KEY=test-only-audit-key-with-at-least-32-characters \
./scripts/uv-local run pytest --cov
```

CI runs the same lint, format, security, and test gates on every pull request.

## Docker Compose

After configuring `.env`:

```bash
docker compose up --build
docker compose exec ollama ollama pull mistral
```

Only `http://127.0.0.1:8000` is published to the host. PostgreSQL, Redis, Ollama,
and the service-specific FastAPI processes are reachable only inside the Compose network.

Stop the stack without deleting its data:

```bash
docker compose down
```

## Authentication example

```bash
curl -sS http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"YOUR_BOOTSTRAP_PASSWORD"}'
```

Use the returned access token as `Authorization: Bearer <token>`. The refresh endpoint
returns a new refresh token each time; the previous refresh token cannot be reused.

## License

See [LICENSE](./LICENSE).
