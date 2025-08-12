from fastapi import FastAPI, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import sys
import os
import time

# Ensure parent directory is in Python path to import sibling services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obfuscation_engine import main as obfuscation_main
from tokenization_vault import main as tokenization_main
from litellm_integration import main as litellm_main
from policy_engine import main as policy_main
from audit_logging import main as audit_main
from auth_service import main as auth_main
from auth_service.rbac_middleware import (
    get_current_user, 
    get_current_user_optional,
    require_gateway_use,
    require_policy_read,
    require_policy_write,
    require_model_fine_tune,
    require_audit_read,
    require_security_admin,
    require_super_admin
)
from auth_service.rbac_engine import User

gateway = FastAPI(
    title="Enterprise Data Obfuscation Gateway - Unified API",
    version="2.0.0",
    description="Enterprise-ready API Gateway with authentication, RBAC, and comprehensive security controls"
)

# Add CORS middleware
gateway.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication middleware
@gateway.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Authentication and audit middleware"""
    start_time = time.time()
    
    # Skip authentication for health checks and auth endpoints
    if request.url.path in ["/health", "/", "/docs", "/openapi.json"] or request.url.path.startswith("/auth"):
        response = await call_next(request)
        return response
    
    # Get user if authenticated (optional for some endpoints)
    user = None
    try:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            from auth_service.rbac_middleware import rbac_middleware
            user = await rbac_middleware.get_current_user_optional(request)
    except Exception:
        pass  # User remains None for unauthenticated requests
    
    # Add user to request state for downstream use
    request.state.user = user
    
    # Process request
    response = await call_next(request)
    
    # Add processing time header
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    
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
    from auth_service.rbac_engine import rbac_engine, RBACResource
    
    # Check permission
    resource = RBACResource(resource_type="gateway", resource_id="obfuscation", tenant_id=current_user.tenant_id)
    rbac_engine.require_permission(current_user, "gateway:use", resource)
    
    # This would proxy to the obfuscation service
    return {"message": "Obfuscation service", "user": current_user.username}

@gateway.get("/policy/rules")
async def policy_rules(current_user: User = Depends(get_current_user)):
    """Policy rules endpoint - requires policy read permission"""
    from auth_service.rbac_engine import rbac_engine, RBACResource
    
    # Check permission
    resource = RBACResource(resource_type="policy", resource_id="rules", tenant_id=current_user.tenant_id)
    rbac_engine.require_permission(current_user, "policy:read", resource)
    
    return {"message": "Policy rules", "user": current_user.username}

@gateway.post("/policy/rules")
async def create_policy_rule(current_user: User = Depends(get_current_user)):
    """Create policy rule - requires policy write permission"""
    from auth_service.rbac_engine import rbac_engine, RBACResource
    
    # Check permission
    resource = RBACResource(resource_type="policy", resource_id="rules", tenant_id=current_user.tenant_id)
    rbac_engine.require_permission(current_user, "policy:write", resource)
    
    return {"message": "Policy rule created", "user": current_user.username}

@gateway.get("/audit/logs")
async def audit_logs(current_user: User = Depends(get_current_user)):
    """Audit logs endpoint - requires audit read permission"""
    from auth_service.rbac_engine import rbac_engine, RBACResource
    
    # Check permission
    resource = RBACResource(resource_type="audit", resource_id="logs", tenant_id=current_user.tenant_id)
    rbac_engine.require_permission(current_user, "audit:read", resource)
    
    return {"message": "Audit logs", "user": current_user.username}

@gateway.get("/admin/users")
async def admin_users(current_user: User = Depends(get_current_user)):
    """Admin users endpoint - requires super admin role"""
    from auth_service.rbac_engine import rbac_engine
    
    # Check role
    rbac_engine.require_role(current_user, "super_admin")
    
    return {"message": "Admin users", "user": current_user.username}

# Include service routers with authentication bypass for internal calls
# Note: In production, these would be properly secured with service-to-service auth
gateway.include_router(obfuscation_main.app.router, prefix="/internal/obfuscation", tags=["Internal - Obfuscation Engine"])
gateway.include_router(tokenization_main.app.router, prefix="/internal/tokenization", tags=["Internal - Tokenization Vault"])
gateway.include_router(litellm_main.app.router, prefix="/internal/litellm", tags=["Internal - LiteLLM Gateway"])
gateway.include_router(policy_main.app.router, prefix="/internal/policy", tags=["Internal - Policy Engine"])
gateway.include_router(audit_main.app.router, prefix="/internal/audit", tags=["Internal - Audit Logging"])

@gateway.get("/")
async def root():
    """Root endpoint with service information"""
    return JSONResponse(content={
        "message": "Enterprise Data Obfuscation Gateway",
        "version": "2.0.0",
        "features": [
            "JWT Authentication",
            "Role-Based Access Control (RBAC)",
            "Multi-LLM Routing",
            "Policy Management",
            "Audit Logging",
            "Data Obfuscation"
        ],
        "endpoints": {
            "Authentication": "/auth",
            "Documentation": "/docs",
            "Health Check": "/health"
        },
        "protected_services": {
            "Obfuscation": "/obfuscation",
            "Policy Management": "/policy",
            "Audit Logs": "/audit",
            "Admin": "/admin"
        },
        "internal_services": {
            "Obfuscation Engine": "/internal/obfuscation",
            "Tokenization Vault": "/internal/tokenization",
            "LiteLLM Gateway": "/internal/litellm",
            "Policy Engine": "/internal/policy",
            "Audit Logging": "/internal/audit"
        }
    })

# User info endpoint
@gateway.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    from auth_service.rbac_engine import rbac_engine
    permissions = rbac_engine.get_user_permissions(current_user)
    
    return {
        "user_id": current_user.user_id,
        "username": current_user.username,
        "roles": current_user.roles,
        "permissions": permissions,
        "tenant_id": current_user.tenant_id
    }

app = gateway