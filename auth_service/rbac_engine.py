"""
RBAC Engine with Oso integration
Provides role-based access control with hierarchical roles and permissions
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import os
from oso import Oso
from fastapi import HTTPException, status


class Permission(Enum):
    """System permissions"""
    # Gateway permissions
    GATEWAY_USE = "gateway:use"
    GATEWAY_READ = "gateway:read"
    GATEWAY_ADMIN = "gateway:admin"
    
    # Policy permissions
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    POLICY_TEST = "policy:test"
    POLICY_ADMIN = "policy:admin"
    
    # Model permissions
    MODEL_READ = "model:read"
    MODEL_FINE_TUNE = "model:fine_tune"
    MODEL_DEPLOY = "model:deploy"
    MODEL_ADMIN = "model:admin"
    
    # Audit permissions
    AUDIT_READ = "audit:read"
    AUDIT_WRITE = "audit:write"
    AUDIT_ADMIN = "audit:admin"
    
    # RBAC permissions
    RBAC_READ = "rbac:read"
    RBAC_MANAGE = "rbac:manage"
    
    # Monitoring permissions
    MONITORING_READ = "monitoring:read"
    MONITORING_ADMIN = "monitoring:admin"
    
    # System admin permissions
    SYSTEM_ADMIN = "*"


class Role(Enum):
    """System roles with hierarchy"""
    USER = "user"
    OPERATOR = "operator"
    DATA_SCIENTIST = "data_scientist"
    SECURITY_ADMIN = "security_admin"
    SUPER_ADMIN = "super_admin"


@dataclass
class User:
    """User model for RBAC"""
    user_id: str
    username: str
    roles: List[str]
    permissions: List[str] = None
    tenant_id: Optional[str] = None
    
    def __post_init__(self):
        if self.permissions is None:
            self.permissions = []


@dataclass
class RBACResource:
    """Resource model for RBAC"""
    resource_type: str
    resource_id: str
    tenant_id: Optional[str] = None
    attributes: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}


class RBACEngine:
    """Role-Based Access Control Engine using Oso"""
    
    def __init__(self):
        self.oso = Oso()
        self._setup_oso_policies()
        self._role_hierarchy = self._define_role_hierarchy()
        self._role_permissions = self._define_role_permissions()
    
    def _setup_oso_policies(self):
        """Setup Oso policies and register classes"""
        # Register classes with Oso
        self.oso.register_class(User)
        self.oso.register_class(RBACResource, name="RBACResource")
        
        # Load inline policies for now (simpler than file-based)
        self._load_inline_policies()
    
    def _load_inline_policies(self):
        """Load inline Oso policies"""
        policies = """
        # Role hierarchy rules
        role_hierarchy("super_admin", "security_admin");
        role_hierarchy("super_admin", "data_scientist");
        role_hierarchy("super_admin", "operator");
        role_hierarchy("super_admin", "user");
        role_hierarchy("security_admin", "operator");
        role_hierarchy("security_admin", "user");
        role_hierarchy("data_scientist", "user");
        role_hierarchy("operator", "user");
        
        # Permission inheritance through role hierarchy
        has_role(user: User, role) if role in user.roles;
        has_role(user: User, role) if 
            parent_role in user.roles and
            role_hierarchy(parent_role, role);
        
        # Super admin has all permissions
        allow(user: User, _action, _resource) if 
            has_role(user, "super_admin");
        
        # Security admin permissions
        allow(user: User, "policy:read", _resource) if 
            has_role(user, "security_admin");
        allow(user: User, "policy:write", _resource) if 
            has_role(user, "security_admin");
        allow(user: User, "audit:read", _resource) if 
            has_role(user, "security_admin");
        allow(user: User, "rbac:manage", _resource) if 
            has_role(user, "security_admin");
        
        # Data scientist permissions
        allow(user: User, "model:read", _resource) if 
            has_role(user, "data_scientist");
        allow(user: User, "model:fine_tune", _resource) if 
            has_role(user, "data_scientist");
        allow(user: User, "policy:read", _resource) if 
            has_role(user, "data_scientist");
        allow(user: User, "policy:test", _resource) if 
            has_role(user, "data_scientist");
        
        # Operator permissions
        allow(user: User, "gateway:read", _resource) if 
            has_role(user, "operator");
        allow(user: User, "monitoring:read", _resource) if 
            has_role(user, "operator");
        
        # User permissions
        allow(user: User, "gateway:use", _resource) if 
            has_role(user, "user");
        """
        
        self.oso.load_str(policies)
    
    def _define_role_hierarchy(self) -> Dict[str, List[str]]:
        """Define role hierarchy mapping"""
        return {
            Role.SUPER_ADMIN.value: [
                Role.SECURITY_ADMIN.value,
                Role.DATA_SCIENTIST.value,
                Role.OPERATOR.value,
                Role.USER.value
            ],
            Role.SECURITY_ADMIN.value: [
                Role.OPERATOR.value,
                Role.USER.value
            ],
            Role.DATA_SCIENTIST.value: [
                Role.USER.value
            ],
            Role.OPERATOR.value: [
                Role.USER.value
            ],
            Role.USER.value: []
        }
    
    def _define_role_permissions(self) -> Dict[str, List[str]]:
        """Define role to permissions mapping"""
        return {
            Role.SUPER_ADMIN.value: [Permission.SYSTEM_ADMIN.value],
            Role.SECURITY_ADMIN.value: [
                Permission.POLICY_READ.value,
                Permission.POLICY_WRITE.value,
                Permission.POLICY_ADMIN.value,
                Permission.AUDIT_READ.value,
                Permission.AUDIT_ADMIN.value,
                Permission.RBAC_READ.value,
                Permission.RBAC_MANAGE.value,
                Permission.GATEWAY_READ.value,
                Permission.MONITORING_READ.value
            ],
            Role.DATA_SCIENTIST.value: [
                Permission.MODEL_READ.value,
                Permission.MODEL_FINE_TUNE.value,
                Permission.POLICY_READ.value,
                Permission.POLICY_TEST.value,
                Permission.GATEWAY_READ.value
            ],
            Role.OPERATOR.value: [
                Permission.GATEWAY_READ.value,
                Permission.MONITORING_READ.value,
                Permission.AUDIT_READ.value
            ],
            Role.USER.value: [
                Permission.GATEWAY_USE.value
            ]
        }
    
    def check_permission(self, user: User, permission: str, resource: Optional[RBACResource] = None) -> bool:
        """Check if user has permission for resource"""
        try:
            # Create default resource if none provided
            if resource is None:
                resource = RBACResource(
                    resource_type="default",
                    resource_id="default",
                    tenant_id=user.tenant_id
                )
            
            # Use Oso to check permission
            return self.oso.is_allowed(user, permission, resource)
        except Exception as e:
            # Log error and deny access by default
            print(f"RBAC permission check error: {e}")
            return False
    
    def get_user_permissions(self, user: User) -> List[str]:
        """Get all permissions for a user based on their roles"""
        permissions = set()
        
        # Add direct permissions
        permissions.update(user.permissions)
        
        # Add role-based permissions
        for role in user.roles:
            if role in self._role_permissions:
                permissions.update(self._role_permissions[role])
            
            # Add inherited permissions from role hierarchy
            inherited_roles = self._get_inherited_roles(role)
            for inherited_role in inherited_roles:
                if inherited_role in self._role_permissions:
                    permissions.update(self._role_permissions[inherited_role])
        
        return list(permissions)
    
    def _get_inherited_roles(self, role: str) -> List[str]:
        """Get all roles inherited by the given role"""
        inherited = []
        if role in self._role_hierarchy:
            for child_role in self._role_hierarchy[role]:
                inherited.append(child_role)
                inherited.extend(self._get_inherited_roles(child_role))
        return inherited
    
    def has_role(self, user: User, role: str) -> bool:
        """Check if user has a specific role (including inherited roles)"""
        if role in user.roles:
            return True
        
        # Check inherited roles
        for user_role in user.roles:
            inherited_roles = self._get_inherited_roles(user_role)
            if role in inherited_roles:
                return True
        
        return False
    
    def require_permission(self, user: User, permission: str, resource: Optional[RBACResource] = None):
        """Require permission or raise HTTPException"""
        if not self.check_permission(user, permission, resource):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}"
            )
    
    def require_role(self, user: User, role: str):
        """Require role or raise HTTPException"""
        if not self.has_role(user, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {role}"
            )
    
    def get_accessible_resources(self, user: User, resource_type: str, permission: str) -> List[str]:
        """Get list of resource IDs that user can access with given permission"""
        # This would typically query a database
        # For now, return empty list as placeholder
        return []
    
    def add_user_permission(self, user: User, permission: str):
        """Add direct permission to user"""
        if permission not in user.permissions:
            user.permissions.append(permission)
    
    def remove_user_permission(self, user: User, permission: str):
        """Remove direct permission from user"""
        if permission in user.permissions:
            user.permissions.remove(permission)
    
    def add_user_role(self, user: User, role: str):
        """Add role to user"""
        if role not in user.roles:
            user.roles.append(role)
    
    def remove_user_role(self, user: User, role: str):
        """Remove role from user"""
        if role in user.roles:
            user.roles.remove(role)


# Global RBAC engine instance
rbac_engine = RBACEngine()