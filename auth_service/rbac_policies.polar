# RBAC Policies for Enterprise Data Obfuscation Gateway
# Defines role hierarchy, permissions, and access control rules

# Role hierarchy - higher roles inherit permissions from lower roles
role_hierarchy("super_admin", "security_admin");
role_hierarchy("super_admin", "data_scientist");
role_hierarchy("super_admin", "operator");
role_hierarchy("super_admin", "user");
role_hierarchy("security_admin", "operator");
role_hierarchy("security_admin", "user");
role_hierarchy("data_scientist", "user");
role_hierarchy("operator", "user");

# Helper rule to check if user has a role (direct or inherited)
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
allow(user: User, "policy:admin", _resource) if 
    has_role(user, "security_admin");
allow(user: User, "audit:read", _resource) if 
    has_role(user, "security_admin");
allow(user: User, "audit:admin", _resource) if 
    has_role(user, "security_admin");
allow(user: User, "rbac:read", _resource) if 
    has_role(user, "security_admin");
allow(user: User, "rbac:manage", _resource) if 
    has_role(user, "security_admin");
allow(user: User, "gateway:read", _resource) if 
    has_role(user, "security_admin");
allow(user: User, "monitoring:read", _resource) if 
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
allow(user: User, "gateway:read", _resource) if 
    has_role(user, "data_scientist");

# Operator permissions
allow(user: User, "gateway:read", _resource) if 
    has_role(user, "operator");
allow(user: User, "monitoring:read", _resource) if 
    has_role(user, "operator");
allow(user: User, "audit:read", _resource) if 
    has_role(user, "operator");

# User permissions (base level)
allow(user: User, "gateway:use", _resource) if 
    has_role(user, "user");

# Tenant isolation - users can only access resources in their tenant
allow(user: User, action, resource: RBACResource) if 
    user.tenant_id = resource.tenant_id and
    allow_base(user, action, resource);

# Base permission check without tenant isolation
allow_base(user: User, action, resource) if allow(user, action, resource);

# Resource-specific permissions
# Policy resources
allow(user: User, "policy:read", resource: RBACResource) if 
    resource.resource_type = "policy" and
    has_role(user, "data_scientist");

allow(user: User, "policy:write", resource: RBACResource) if 
    resource.resource_type = "policy" and
    has_role(user, "security_admin");

# Model resources
allow(user: User, "model:read", resource: RBACResource) if 
    resource.resource_type = "model" and
    has_role(user, "data_scientist");

allow(user: User, "model:fine_tune", resource: RBACResource) if 
    resource.resource_type = "model" and
    has_role(user, "data_scientist");

allow(user: User, "model:deploy", resource: RBACResource) if 
    resource.resource_type = "model" and
    has_role(user, "security_admin");

# Audit resources
allow(user: User, "audit:read", resource: RBACResource) if 
    resource.resource_type = "audit" and
    (has_role(user, "security_admin") or has_role(user, "operator"));

# Gateway resources
allow(user: User, "gateway:use", resource: RBACResource) if 
    resource.resource_type = "gateway" and
    has_role(user, "user");

allow(user: User, "gateway:admin", resource: RBACResource) if 
    resource.resource_type = "gateway" and
    has_role(user, "super_admin");

# Context-aware permissions
# Time-based access (example: only during business hours)
allow(user: User, action, resource) if 
    allow_base(user, action, resource) and
    business_hours();

# IP-based access (example: only from trusted networks)
allow(user: User, action, resource) if 
    allow_base(user, action, resource) and
    trusted_network(user);

# Helper rules (would be implemented in Python)
business_hours() if true;  # Placeholder - implement in Python
trusted_network(_user: User) if true;  # Placeholder - implement in Python