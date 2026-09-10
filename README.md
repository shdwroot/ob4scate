# ob4scate

`ob4scate` is a Python/FastAPI privacy gateway for enterprises that need to use shared or
public LLM APIs without exposing identifiable client data to the model provider. Its primary
use case is an organization that does not have a dedicated, isolated LLM tenant and therefore
needs to remove or replace sensitive values before a prompt crosses the enterprise boundary.

The intended request path is:

```text
Enterprise application
        |
        | prompt containing client or customer data
        v
Ob4scate inside the enterprise-controlled boundary
        |
        | redacted or tokenized prompt
        v
Organization-approved shared/public LLM API
```

Ob4scate provides authentication and tenant-aware RBAC, policy-based detection and redaction,
encrypted token mappings, LLM routing components, and tamper-evident audit storage. A local
model is used only as a development or detection component where configured; it is not the
system that the product is primarily intended to protect prompts from.

This codebase is an actively developed foundation. It contains the individual security and
redaction services, but the complete production workflow that sanitizes a prompt, sends it to
a public provider, and safely restores authorized values in the response is not yet wired end
to end. The checked-in [implementation plan](./IMPLEMENTATION_PLAN.md) lists that work and
other unfinished enterprise capabilities, including external identity providers, Kubernetes
deployment, distributed tracing, provider failover, and model fine-tuning.

## What is protected by default

The policy engine enables defaults for common credentials, government identifiers, financial
details, health and insurance information, identity and contact details, addresses, and
network or device identifiers. These include email addresses, phone numbers, names, dates of
birth, South African identity numbers, passports, payment cards, bank details, medical
records, API secrets, IP addresses, device IDs, and precise locations.

Run the policy service to inspect the full detector catalog and try the built-in example:

```bash
./scripts/uv-local run uvicorn policy_engine.main:app --reload --port 8004
```

Open <http://127.0.0.1:8004/admin>. Deterministic detectors are enabled without an external
service. Free-form name and location recognition is extended when the optional local spaCy
model is installed. No automated detector can guarantee that every sensitive value in
arbitrary text will be found, so enterprise-specific formats and human review remain
important for high-risk workflows.

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
litellm_integration/   Ollama-compatible development connector and routing rules
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
Ollama is the repository's current development upstream so the flow can be exercised without
sending test data to a third party. It is not the product's target LLM deployment model;
production multi-provider routing to approved public/shared LLM APIs remains planned work.

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
