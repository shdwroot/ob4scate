# Small Business Data Obfuscation Gateway

A Python/FastAPI-based reverse proxy and microservice suite for secure, context-preserving use of external LLMs in enterprise environments.  
Implements PII obfuscation, tokenization, policy enforcement, LiteLLM routing, and immutable audit logging.

## 📂 Project Structure
```
gateway_proxy/         # API Gateway entrypoint
obfuscation_engine/    # PII/quasi-identifier detection & obfuscation
tokenization_vault/    # Secure mapping storage (PostgreSQL + pgcrypto)
litellm_integration/   # LiteLLM unified API connector
policy_engine/         # Configurable obfuscation rules
audit_logging/         # Immutable logging service
IMPLEMENTATION_PLAN.md # Full architecture & roadmap
```

---

## 🛠 Development Setup

### 1. Clone repository
```bash
git clone <repo_url>
cd <project_dir>
```

### 2. Install dependencies
Make sure you have Python 3.10+  
It's recommended to use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

pip install fastapi uvicorn spacy psycopg2 requests
python -m spacy download en_core_web_sm
```

### 3. Run microservices locally
Open **six terminals** or run them in background mode:
```bash
uvicorn gateway_proxy.main:app --reload --port 8000
uvicorn obfuscation_engine.main:app --reload --port 8001
uvicorn tokenization_vault.main:app --reload --port 8002
uvicorn litellm_integration.main:app --reload --port 8003
uvicorn policy_engine.main:app --reload --port 8004
uvicorn audit_logging.main:app --reload --port 8005
```

### 4. Test services
```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8001/sanitize -H "Content-Type: application/json" -d '{"text": "Email me at test@example.com"}'
```

---

## 📦 Deployment

### Docker Compose (Recommended for Dev)
1. Create a `Dockerfile` in each microservice directory.
2. Create a `docker-compose.yml` file referencing all six services.
3. Run:
```bash
docker compose up --build
```
Only `gateway_proxy` will be exposed publicly; others communicate internally.

### Kubernetes (Production)
- Package each service into its own Docker image.
- Write Kubernetes manifests for:
  - **Deployments** (one per service)
  - **Services** (ClusterIP for internal, LoadBalancer/Ingress for gateway)
- Use an **Ingress Controller** or API Gateway (NGINX, Istio, Traefik) to route traffic.
- Apply manifests:
```bash
kubectl apply -f k8s/
```

---

## 🔐 Security Notes
- Always enable TLS (end-to-end encryption).
- Restrict internal service traffic using network policies.
- Use external secret management (e.g., HashiCorp Vault) for credentials.

---

## 📈 Roadmap
See [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) for phased roadmap and architecture diagram.