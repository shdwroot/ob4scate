# Technology Stack

## Core Technologies
- **Language**: Python 3.11+
- **Framework**: FastAPI for all microservices
- **Server**: Uvicorn ASGI server
- **Database**: PostgreSQL with pgcrypto extension
- **ML/NLP**: spaCy, HuggingFace Transformers
- **LLM Integration**: LiteLLM, Ollama (local GPU inference)

## Key Dependencies
```
fastapi
uvicorn
requests
spacy
psycopg2-binary
```

## Development Commands

### Local Development Setup
```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### Running Services Locally
Each service runs on a different port:
```bash
uvicorn gateway_proxy.main:app --reload --port 8000
uvicorn obfuscation_engine.main:app --reload --port 8001
uvicorn tokenization_vault.main:app --reload --port 8002
uvicorn litellm_integration.main:app --reload --port 8003
uvicorn policy_engine.main:app --reload --port 8004
uvicorn audit_logging.main:app --reload --port 8005
```

### Docker Development
```bash
# Build and run all services
docker compose up --build

# View logs
docker compose logs -f [service_name]
```

### Testing
```bash
# Health check
curl http://localhost:8000/health

# Test obfuscation
curl -X POST http://localhost:8001/sanitize -H "Content-Type: application/json" -d '{"text": "Email me at test@example.com"}'
```

## Build System
- **Containerization**: Docker with shared Dockerfile
- **Orchestration**: Docker Compose for development, Kubernetes for production
- **Port Allocation**: Services use ports 8000-8005
- **Volume Mounts**: `./logs` directory for persistent audit logs