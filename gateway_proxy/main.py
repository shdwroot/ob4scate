import os
import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from audit_logging import main as audit_main
from auth_service import main as auth_main
from auth_service.rbac_engine import RBACResource, User, rbac_engine
from auth_service.rbac_middleware import get_current_user
from litellm_integration import main as litellm_main
from obfuscation_engine import main as obfuscation_main
from policy_engine import main as policy_main
from tokenization_vault import main as tokenization_main

gateway = FastAPI(
    title="Enterprise Data Obfuscation Gateway - Unified API",
    version="2.0.0",
    description=("Privacy gateway with authentication, RBAC, and protected internal services"),
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",")
    if origin.strip()
]
if "*" in allowed_origins and os.getenv("APP_ENV", "development") == "production":
    raise RuntimeError("Wildcard CORS origins are not allowed in production")

gateway.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials="*" not in allowed_origins,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@gateway.middleware("http")
async def response_metadata_middleware(request: Request, call_next):
    """Attach stable request and timing metadata without authenticating twice."""
    start_time = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Process-Time"] = f"{time.perf_counter() - start_time:.6f}"
    response.headers["X-Request-ID"] = request_id
    return response


@gateway.get("/health")
async def health_check():
    """Health check endpoint - no authentication required"""
    return {"status": "ok", "service": "gateway_proxy", "version": "2.0.0"}


# Include authentication service
gateway.include_router(auth_main.app.router, prefix="/auth", tags=["Authentication"])


# Protected service endpoints with RBAC
@gateway.get("/obfuscation/sanitize")
async def obfuscation_sanitize(current_user: User = Depends(get_current_user)):
    """Obfuscation endpoint - requires gateway use permission"""
    resource = RBACResource(
        resource_type="gateway", resource_id="obfuscation", tenant_id=current_user.tenant_id
    )
    rbac_engine.require_permission(current_user, "gateway:use", resource)

    # This would proxy to the obfuscation service
    return {"message": "Obfuscation service", "user": current_user.username}


@gateway.get("/policy/rules")
async def policy_rules(current_user: User = Depends(get_current_user)):
    """Policy rules endpoint - requires policy read permission"""
    resource = RBACResource(
        resource_type="policy", resource_id="rules", tenant_id=current_user.tenant_id
    )
    rbac_engine.require_permission(current_user, "policy:read", resource)

    return {"message": "Policy rules", "user": current_user.username}


@gateway.post("/policy/rules")
async def create_policy_rule(current_user: User = Depends(get_current_user)):
    """Create policy rule - requires policy write permission"""
    resource = RBACResource(
        resource_type="policy", resource_id="rules", tenant_id=current_user.tenant_id
    )
    rbac_engine.require_permission(current_user, "policy:write", resource)

    return {"message": "Policy rule created", "user": current_user.username}


@gateway.get("/audit/logs")
async def audit_logs(current_user: User = Depends(get_current_user)):
    """Audit logs endpoint - requires audit read permission"""
    resource = RBACResource(
        resource_type="audit", resource_id="logs", tenant_id=current_user.tenant_id
    )
    rbac_engine.require_permission(current_user, "audit:read", resource)

    return {"message": "Audit logs", "user": current_user.username}


@gateway.get("/admin/users")
async def admin_users(current_user: User = Depends(get_current_user)):
    """Admin users endpoint - requires super admin role"""
    rbac_engine.require_role(current_user, "super_admin")

    return {"message": "Admin users", "user": current_user.username}


async def require_internal_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Restrict raw internal service routes to super administrators."""
    rbac_engine.require_role(current_user, "super_admin")
    return current_user


internal_dependencies = [Depends(require_internal_admin)]
gateway.include_router(
    obfuscation_main.app.router,
    prefix="/internal/obfuscation",
    tags=["Internal - Obfuscation Engine"],
    dependencies=internal_dependencies,
)
gateway.include_router(
    tokenization_main.app.router,
    prefix="/internal/tokenization",
    tags=["Internal - Tokenization Vault"],
    dependencies=internal_dependencies,
)
gateway.include_router(
    litellm_main.app.router,
    prefix="/internal/litellm",
    tags=["Internal - LLM Gateway"],
    dependencies=internal_dependencies,
)
gateway.include_router(
    policy_main.app.router,
    prefix="/internal/policy",
    tags=["Internal - Policy Engine"],
    dependencies=internal_dependencies,
)
gateway.include_router(
    audit_main.app.router,
    prefix="/internal/audit",
    tags=["Internal - Audit Logging"],
    dependencies=internal_dependencies,
)


@gateway.get("/")
async def root():
    """Root endpoint with service information"""
    return JSONResponse(
        content={
            "message": "Enterprise Data Obfuscation Gateway",
            "version": "2.0.0",
            "features": [
                "JWT Authentication",
                "Role-Based Access Control (RBAC)",
                "Multi-LLM Routing",
                "Policy Management",
                "Audit Logging",
                "Data Obfuscation",
            ],
            "endpoints": {
                "Authentication": "/auth",
                "Documentation": "/docs",
                "Health Check": "/health",
            },
            "protected_services": {
                "Obfuscation": "/obfuscation",
                "Policy Management": "/policy",
                "Audit Logs": "/audit",
                "Admin": "/admin",
            },
            "internal_services": {
                "Obfuscation Engine": "/internal/obfuscation",
                "Tokenization Vault": "/internal/tokenization",
                "LiteLLM Gateway": "/internal/litellm",
                "Policy Engine": "/internal/policy",
                "Audit Logging": "/internal/audit",
            },
        }
    )


# User info endpoint
@gateway.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    permissions = rbac_engine.get_user_permissions(current_user)

    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "roles": current_user.roles,
        "permissions": permissions,
        "tenant_id": current_user.tenant_id,
    }


app = gateway
