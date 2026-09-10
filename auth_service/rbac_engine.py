"""Tenant-aware role-based access control."""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from fastapi import HTTPException, status


class Permission(StrEnum):
    GATEWAY_USE = "gateway:use"
    GATEWAY_READ = "gateway:read"
    GATEWAY_ADMIN = "gateway:admin"
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    POLICY_TEST = "policy:test"
    POLICY_ADMIN = "policy:admin"
    MODEL_READ = "model:read"
    MODEL_FINE_TUNE = "model:fine_tune"
    MODEL_DEPLOY = "model:deploy"
    MODEL_ADMIN = "model:admin"
    AUDIT_READ = "audit:read"
    AUDIT_WRITE = "audit:write"
    AUDIT_ADMIN = "audit:admin"
    RBAC_READ = "rbac:read"
    RBAC_MANAGE = "rbac:manage"
    MONITORING_READ = "monitoring:read"
    MONITORING_ADMIN = "monitoring:admin"
    SYSTEM_ADMIN = "*"


class Role(StrEnum):
    USER = "user"
    OPERATOR = "operator"
    DATA_SCIENTIST = "data_scientist"
    SECURITY_ADMIN = "security_admin"
    SUPER_ADMIN = "super_admin"


@dataclass
class User:
    user_id: str
    username: str
    roles: list[str]
    permissions: list[str] = field(default_factory=list)
    tenant_id: str | None = None
    session_id: str | None = None


@dataclass
class RBACResource:
    resource_type: str
    resource_id: str
    tenant_id: str | None = None
    attributes: dict[str, Any] = field(default_factory=dict)


class RBACEngine:
    """Resolve inherited permissions and enforce tenant boundaries."""

    def __init__(self) -> None:
        self._role_hierarchy: dict[str, tuple[str, ...]] = {
            Role.SUPER_ADMIN: (
                Role.SECURITY_ADMIN,
                Role.DATA_SCIENTIST,
                Role.OPERATOR,
                Role.USER,
            ),
            Role.SECURITY_ADMIN: (Role.OPERATOR, Role.USER),
            Role.DATA_SCIENTIST: (Role.USER,),
            Role.OPERATOR: (Role.USER,),
            Role.USER: (),
        }
        self._role_permissions: dict[str, tuple[str, ...]] = {
            Role.SUPER_ADMIN: (Permission.SYSTEM_ADMIN,),
            Role.SECURITY_ADMIN: (
                Permission.POLICY_READ,
                Permission.POLICY_WRITE,
                Permission.POLICY_ADMIN,
                Permission.AUDIT_READ,
                Permission.AUDIT_ADMIN,
                Permission.RBAC_READ,
                Permission.RBAC_MANAGE,
                Permission.GATEWAY_READ,
                Permission.MONITORING_READ,
            ),
            Role.DATA_SCIENTIST: (
                Permission.MODEL_READ,
                Permission.MODEL_FINE_TUNE,
                Permission.POLICY_READ,
                Permission.POLICY_TEST,
                Permission.GATEWAY_READ,
            ),
            Role.OPERATOR: (
                Permission.GATEWAY_READ,
                Permission.MONITORING_READ,
                Permission.AUDIT_READ,
            ),
            Role.USER: (Permission.GATEWAY_USE,),
        }
        self._known_permissions = {permission.value for permission in Permission}
        self._known_roles = {role.value for role in Role}

    def _get_inherited_roles(self, role: str) -> list[str]:
        inherited: list[str] = []
        pending = list(self._role_hierarchy.get(role, ()))
        visited: set[str] = set()
        while pending:
            inherited_role = pending.pop()
            if inherited_role in visited:
                continue
            visited.add(inherited_role)
            inherited.append(inherited_role)
            pending.extend(self._role_hierarchy.get(inherited_role, ()))
        return inherited

    def get_user_permissions(self, user: User) -> list[str]:
        permissions = set(user.permissions)
        for role in user.roles:
            permissions.update(self._role_permissions.get(role, ()))
            for inherited_role in self._get_inherited_roles(role):
                permissions.update(self._role_permissions.get(inherited_role, ()))
        return sorted(permissions)

    def check_permission(
        self,
        user: User,
        permission: str,
        resource: RBACResource | None = None,
    ) -> bool:
        if permission not in self._known_permissions:
            return False
        if (
            resource is not None
            and resource.tenant_id is not None
            and user.tenant_id != resource.tenant_id
        ):
            return False
        permissions = self.get_user_permissions(user)
        return Permission.SYSTEM_ADMIN in permissions or permission in permissions

    def has_role(self, user: User, role: str) -> bool:
        if role not in self._known_roles:
            return False
        return role in user.roles or any(
            role in self._get_inherited_roles(user_role) for user_role in user.roles
        )

    def require_permission(
        self,
        user: User,
        permission: str,
        resource: RBACResource | None = None,
    ) -> None:
        if not self.check_permission(user, permission, resource):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {permission}",
            )

    def require_role(self, user: User, role: str) -> None:
        if not self.has_role(user, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {role}",
            )

    def add_user_permission(self, user: User, permission: str) -> None:
        if permission not in self._known_permissions:
            raise ValueError(f"Unknown permission: {permission}")
        if permission not in user.permissions:
            user.permissions.append(permission)

    @staticmethod
    def remove_user_permission(user: User, permission: str) -> None:
        if permission in user.permissions:
            user.permissions.remove(permission)

    def add_user_role(self, user: User, role: str) -> None:
        if role not in self._known_roles:
            raise ValueError(f"Unknown role: {role}")
        if role not in user.roles:
            user.roles.append(role)

    @staticmethod
    def remove_user_role(user: User, role: str) -> None:
        if role in user.roles:
            user.roles.remove(role)


rbac_engine = RBACEngine()
