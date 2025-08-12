# Project Structure

## Directory Organization
Each microservice follows a consistent structure with its own directory containing a `main.py` FastAPI application.

```
├── gateway_proxy/          # API Gateway - orchestrates all services
├── obfuscation_engine/     # PII detection and transformation
├── tokenization_vault/     # Secure mapping storage
├── litellm_integration/    # Multi-provider LLM routing
├── policy_engine/          # Rule management with admin UI
│   └── templates/          # Jinja2 templates for web UI
├── audit_logging/          # Compliance and audit trails
├── assets/                 # Static files for web UIs
├── logs/                   # Persistent log storage (Docker mount)
├── .kiro/                  # Kiro configuration and steering
└── .vscode/                # VS Code workspace settings
```

## Service Architecture Patterns

### FastAPI Application Structure
Each service follows this pattern:
```python
from fastapi import FastAPI

app = FastAPI(title="Service Name", version="x.x.x")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

# Service-specific endpoints...
```

### Gateway Integration
The gateway proxy includes all service routers:
```python
gateway.include_router(service.app.router, prefix="/service", tags=["Service"])
```

### Path Resolution
Services use absolute path resolution to work both standalone and when mounted via gateway:
```python
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__)))
```

## Configuration Files
- `docker-compose.yml`: Multi-service orchestration
- `Dockerfile`: Shared container definition
- `requirements.txt`: Python dependencies
- `IMPLEMENTATION_PLAN.md`: Architecture and roadmap
- `RESEARCH.md`: Strategic context

## Naming Conventions
- **Services**: snake_case directory names
- **Endpoints**: RESTful patterns (`/health`, `/sanitize`, `/rules`)
- **Environment Variables**: UPPER_CASE with service prefixes
- **Docker Services**: Match directory names exactly