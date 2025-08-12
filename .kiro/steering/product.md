# Product Overview

Enterprise Data Obfuscation Gateway is a Python/FastAPI-based reverse proxy and microservice suite designed for secure, context-preserving use of external LLMs in enterprise environments.

## Core Functionality
- **PII Obfuscation**: Detects and transforms sensitive data using regex, spaCy NER, and ML models
- **Tokenization**: Secure mapping storage for original ↔ token ↔ synthetic data relationships
- **LLM Routing**: Unified API gateway via LiteLLM for multiple LLM providers
- **Policy Enforcement**: Configurable rules for sensitive data detection and obfuscation strategies
- **Audit Logging**: Immutable, tamper-evident logging of all transformations and access

## Target Use Case
Enables enterprises to safely use external LLMs (OpenAI, Anthropic, etc.) while maintaining data privacy and regulatory compliance (GDPR, CCPA, HIPAA).

## Architecture Pattern
Microservices architecture with 6 core services:
1. Gateway Proxy (orchestration)
2. Obfuscation Engine (PII detection/transformation)
3. Tokenization Vault (secure mapping storage)
4. LiteLLM Integration (multi-provider routing)
5. Policy Engine (rule management)
6. Audit Logging (compliance tracking)