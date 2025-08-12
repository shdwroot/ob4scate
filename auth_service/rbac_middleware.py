"""
RBAC Middleware for FastAPI endpoints
Provides decorators and middleware for role-based access control
"""
from functools import wraps
from typing import Optional, List, Callable, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncio

from .auth_core import auth_service
from .rbac_engine import rbac_engine, User, RBACResource, Permission


security = HTTPBearer()


class RBACMiddleware:
    """RBAC Middleware for FastAPI"""
    
    def __init__(self):
        self.rbac_engine = rbac_engine
        self.auth_service = auth_service
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
        """Get current authenticated user"""
        try:
            token = credentials.credentials
            user_info = await self.auth_service.validate_token(token)
            
            return User(
                user_id=user_info["user_id"],
                username=user_info["username"],
                roles=user_info["roles"],
                tenant_id=user_info.get("tenant_id")
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    
    async def get_current_user_optional(self, request: Request) -> Optional[User]:
        """Get current user if authenticated, None otherwise"""
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
            
            token = auth_header.split(" ")[1]
            user_info = await self.auth_service.validate_token(token)
            
            return User(
                user_id=user_info["user_id"],
                username=user_info["username"],
                roles=user_info["roles"],
                tenant_id=user_info.get("tenant_id")
            )
        except Exception:
            return None
    
    def require_permission(self, permission: str, resource_type: Optional[str] = None):
        """Decorator to require specific permission"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user from kwargs or get from request
                user = kwargs.get('current_user')
                if not user:
                    # Try to get user from dependencies
                    for arg in args:
                        if isinstance(arg, User):
                            user = arg
                            break
                
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                # Create resource if resource_type specified
                resource = None
                if resource_type:
                    resource_id = kwargs.get('resource_id', 'default')
                    resource = RBACResource(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        tenant_id=user.tenant_id
                    )
                
                # Check permission
                if not self.rbac_engine.check_permission(user, permission, resource):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Required: {permission}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_role(self, role: str):
        """Decorator to require specific role"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract user from kwargs or get from request
                user = kwargs.get('current_user')
                if not user:
                    # Try to get user from dependencies
                    for arg in args:
                        if isinstance(arg, User):
                            user = arg
                            break
                
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                # Check role
                if not self.rbac_engine.has_role(user, role):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient role. Required: {role}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_any_permission(self, permissions: List[str], resource_type: Optional[str] = None):
        """Decorator to require any of the specified permissions"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                user = kwargs.get('current_user')
                if not user:
                    for arg in args:
                        if isinstance(arg, User):
                            user = arg
                            break
                
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                # Create resource if resource_type specified
                resource = None
                if resource_type:
                    resource_id = kwargs.get('resource_id', 'default')
                    resource = RBACResource(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        tenant_id=user.tenant_id
                    )
                
                # Check if user has any of the required permissions
                has_permission = False
                for permission in permissions:
                    if self.rbac_engine.check_permission(user, permission, resource):
                        has_permission = True
                        break
                
                if not has_permission:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Insufficient permissions. Required one of: {', '.join(permissions)}"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_all_permissions(self, permissions: List[str], resource_type: Optional[str] = None):
        """Decorator to require all of the specified permissions"""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            async def wrapper(*args, **kwargs):
                user = kwargs.get('current_user')
                if not user:
                    for arg in args:
                        if isinstance(arg, User):
                            user = arg
                            break
                
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                # Create resource if resource_type specified
                resource = None
                if resource_type:
                    resource_id = kwargs.get('resource_id', 'default')
                    resource = RBACResource(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        tenant_id=user.tenant_id
                    )
                
                # Check if user has all required permissions
                for permission in permissions:
                    if not self.rbac_engine.check_permission(user, permission, resource):
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"Insufficient permissions. Required: {permission}"
                        )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


# Global middleware instance
rbac_middleware = RBACMiddleware()

# Convenience functions for dependency injection
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Dependency to get current authenticated user"""
    return await rbac_middleware.get_current_user(credentials)

async def get_current_user_optional(request: Request) -> Optional[User]:
    """Dependency to get current user if authenticated"""
    return await rbac_middleware.get_current_user_optional(request)

# Permission decorators
def require_permission(permission: str, resource_type: Optional[str] = None):
    """Decorator to require specific permission"""
    return rbac_middleware.require_permission(permission, resource_type)

def require_role(role: str):
    """Decorator to require specific role"""
    return rbac_middleware.require_role(role)

def require_any_permission(permissions: List[str], resource_type: Optional[str] = None):
    """Decorator to require any of the specified permissions"""
    return rbac_middleware.require_any_permission(permissions, resource_type)

def require_all_permissions(permissions: List[str], resource_type: Optional[str] = None):
    """Decorator to require all of the specified permissions"""
    return rbac_middleware.require_all_permissions(permissions, resource_type)

# Common permission checks
def require_gateway_use():
    """Require gateway use permission"""
    return require_permission(Permission.GATEWAY_USE.value, "gateway")

def require_policy_read():
    """Require policy read permission"""
    return require_permission(Permission.POLICY_READ.value, "policy")

def require_policy_write():
    """Require policy write permission"""
    return require_permission(Permission.POLICY_WRITE.value, "policy")

def require_model_fine_tune():
    """Require model fine-tune permission"""
    return require_permission(Permission.MODEL_FINE_TUNE.value, "model")

def require_audit_read():
    """Require audit read permission"""
    return require_permission(Permission.AUDIT_READ.value, "audit")

def require_security_admin():
    """Require security admin role"""
    return require_role("security_admin")

def require_super_admin():
    """Require super admin role"""
    return require_role("super_admin")
