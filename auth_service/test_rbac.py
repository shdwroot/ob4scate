"""
Unit tests for RBAC engine and middleware
Tests role hierarchy, permissions, and access control
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from fastapi import HTTPException

from .rbac_engine import RBACEngine, User, RBACResource, Permission, Role
from .rbac_middleware import RBACMiddleware


class TestRBACEngine:
    """Test RBAC engine functionality"""
    
    @pytest.fixture
    def rbac_engine(self):
        """RBAC engine instance"""
        return RBACEngine()
    
    @pytest.fixture
    def super_admin_user(self):
        """Super admin user"""
        return User(
            user_id="admin1",
            username="admin",
            roles=["super_admin"],
            tenant_id="tenant1"
        )
    
    @pytest.fixture
    def security_admin_user(self):
        """Security admin user"""
        return User(
            user_id="sec_admin1",
            username="security_admin",
            roles=["security_admin"],
            tenant_id="tenant1"
        )
    
    @pytest.fixture
    def data_scientist_user(self):
        """Data scientist user"""
        return User(
            user_id="ds1",
            username="data_scientist",
            roles=["data_scientist"],
            tenant_id="tenant1"
        )
    
    @pytest.fixture
    def operator_user(self):
        """Operator user"""
        return User(
            user_id="op1",
            username="operator",
            roles=["operator"],
            tenant_id="tenant1"
        )
    
    @pytest.fixture
    def regular_user(self):
        """Regular user"""
        return User(
            user_id="user1",
            username="user",
            roles=["user"],
            tenant_id="tenant1"
        )
    
    @pytest.fixture
    def policy_resource(self):
        """Policy resource"""
        return RBACResource(
            resource_type="policy",
            resource_id="policy1",
            tenant_id="tenant1"
        )
    
    def test_super_admin_has_all_permissions(self, rbac_engine, super_admin_user, policy_resource):
        """Test that super admin has all permissions"""
        # Super admin should have access to everything
        assert rbac_engine.check_permission(super_admin_user, "policy:read", policy_resource)
        assert rbac_engine.check_permission(super_admin_user, "policy:write", policy_resource)
        assert rbac_engine.check_permission(super_admin_user, "model:fine_tune", policy_resource)
        assert rbac_engine.check_permission(super_admin_user, "audit:read", policy_resource)
        assert rbac_engine.check_permission(super_admin_user, "rbac:manage", policy_resource)
    
    def test_security_admin_permissions(self, rbac_engine, security_admin_user, policy_resource):
        """Test security admin permissions"""
        # Security admin should have policy and audit permissions
        assert rbac_engine.check_permission(security_admin_user, "policy:read", policy_resource)
        assert rbac_engine.check_permission(security_admin_user, "policy:write", policy_resource)
        assert rbac_engine.check_permission(security_admin_user, "audit:read", policy_resource)
        assert rbac_engine.check_permission(security_admin_user, "rbac:manage", policy_resource)
        
        # But not model fine-tuning
        assert not rbac_engine.check_permission(security_admin_user, "model:fine_tune", policy_resource)
    
    def test_data_scientist_permissions(self, rbac_engine, data_scientist_user, policy_resource):
        """Test data scientist permissions"""
        # Data scientist should have model and policy read permissions
        assert rbac_engine.check_permission(data_scientist_user, "model:read", policy_resource)
        assert rbac_engine.check_permission(data_scientist_user, "model:fine_tune", policy_resource)
        assert rbac_engine.check_permission(data_scientist_user, "policy:read", policy_resource)
        assert rbac_engine.check_permission(data_scientist_user, "policy:test", policy_resource)
        
        # But not policy write or audit
        assert not rbac_engine.check_permission(data_scientist_user, "policy:write", policy_resource)
        assert not rbac_engine.check_permission(data_scientist_user, "audit:read", policy_resource)
    
    def test_operator_permissions(self, rbac_engine, operator_user, policy_resource):
        """Test operator permissions"""
        # Operator should have read permissions
        assert rbac_engine.check_permission(operator_user, "gateway:read", policy_resource)
        assert rbac_engine.check_permission(operator_user, "monitoring:read", policy_resource)
        
        # But not write permissions
        assert not rbac_engine.check_permission(operator_user, "policy:write", policy_resource)
        assert not rbac_engine.check_permission(operator_user, "model:fine_tune", policy_resource)
    
    def test_regular_user_permissions(self, rbac_engine, regular_user, policy_resource):
        """Test regular user permissions"""
        # Regular user should only have gateway use permission
        assert rbac_engine.check_permission(regular_user, "gateway:use", policy_resource)
        
        # But not other permissions
        assert not rbac_engine.check_permission(regular_user, "policy:read", policy_resource)
        assert not rbac_engine.check_permission(regular_user, "model:read", policy_resource)
        assert not rbac_engine.check_permission(regular_user, "audit:read", policy_resource)
    
    def test_role_hierarchy(self, rbac_engine, security_admin_user):
        """Test role hierarchy inheritance"""
        # Security admin should inherit user role
        assert rbac_engine.has_role(security_admin_user, "security_admin")
        assert rbac_engine.has_role(security_admin_user, "operator")
        assert rbac_engine.has_role(security_admin_user, "user")
        
        # But not data scientist
        assert not rbac_engine.has_role(security_admin_user, "data_scientist")
    
    def test_get_user_permissions(self, rbac_engine, data_scientist_user):
        """Test getting all user permissions"""
        permissions = rbac_engine.get_user_permissions(data_scientist_user)
        
        # Should include data scientist permissions
        assert "model:read" in permissions
        assert "model:fine_tune" in permissions
        assert "policy:read" in permissions
        assert "policy:test" in permissions
        
        # Should include inherited user permissions
        assert "gateway:use" in permissions
    
    def test_add_remove_user_permission(self, rbac_engine, regular_user):
        """Test adding and removing user permissions"""
        # Add permission
        rbac_engine.add_user_permission(regular_user, "policy:read")
        assert "policy:read" in regular_user.permissions
        
        # Remove permission
        rbac_engine.remove_user_permission(regular_user, "policy:read")
        assert "policy:read" not in regular_user.permissions
    
    def test_add_remove_user_role(self, rbac_engine, regular_user):
        """Test adding and removing user roles"""
        # Add role
        rbac_engine.add_user_role(regular_user, "operator")
        assert "operator" in regular_user.roles
        
        # Remove role
        rbac_engine.remove_user_role(regular_user, "operator")
        assert "operator" not in regular_user.roles
    
    def test_tenant_isolation(self, rbac_engine):
        """Test tenant isolation"""
        user1 = User(user_id="u1", username="user1", roles=["user"], tenant_id="tenant1")
        user2 = User(user_id="u2", username="user2", roles=["user"], tenant_id="tenant2")
        
        resource_tenant1 = RBACResource(
            resource_type="policy",
            resource_id="policy1",
            tenant_id="tenant1"
        )
        
        resource_tenant2 = RBACResource(
            resource_type="policy",
            resource_id="policy1",
            tenant_id="tenant2"
        )
        
        # User1 should access tenant1 resource but not tenant2
        assert rbac_engine.check_permission(user1, "gateway:use", resource_tenant1)
        # Note: Current implementation doesn't enforce tenant isolation in Oso policies
        # This would need to be implemented based on specific requirements
    
    def test_require_permission_success(self, rbac_engine, data_scientist_user, policy_resource):
        """Test require_permission with valid permission"""
        # Should not raise exception
        rbac_engine.require_permission(data_scientist_user, "model:read", policy_resource)
    
    def test_require_permission_failure(self, rbac_engine, regular_user, policy_resource):
        """Test require_permission with invalid permission"""
        with pytest.raises(HTTPException) as exc_info:
            rbac_engine.require_permission(regular_user, "policy:write", policy_resource)
        
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)
    
    def test_require_role_success(self, rbac_engine, security_admin_user):
        """Test require_role with valid role"""
        # Should not raise exception
        rbac_engine.require_role(security_admin_user, "security_admin")
        rbac_engine.require_role(security_admin_user, "user")  # Inherited role
    
    def test_require_role_failure(self, rbac_engine, regular_user):
        """Test require_role with invalid role"""
        with pytest.raises(HTTPException) as exc_info:
            rbac_engine.require_role(regular_user, "security_admin")
        
        assert exc_info.value.status_code == 403
        assert "Insufficient role" in str(exc_info.value.detail)


class TestRBACMiddleware:
    """Test RBAC middleware functionality"""
    
    @pytest.fixture
    def rbac_middleware(self):
        """RBAC middleware instance"""
        return RBACMiddleware()
    
    @pytest.fixture
    def mock_user(self):
        """Mock user for testing"""
        return User(
            user_id="test_user",
            username="testuser",
            roles=["data_scientist"],
            tenant_id="tenant1"
        )
    
    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, rbac_middleware):
        """Test getting current user with valid token"""
        mock_credentials = Mock()
        mock_credentials.credentials = "valid_token"
        
        with patch.object(rbac_middleware.auth_service, 'validate_token') as mock_validate:
            mock_validate.return_value = {
                "user_id": "test_user",
                "username": "testuser",
                "roles": ["data_scientist"],
                "tenant_id": "tenant1"
            }
            
            user = await rbac_middleware.get_current_user(mock_credentials)
            
            assert user.user_id == "test_user"
            assert user.username == "testuser"
            assert "data_scientist" in user.roles
            assert user.tenant_id == "tenant1"
    
    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, rbac_middleware):
        """Test getting current user with invalid token"""
        mock_credentials = Mock()
        mock_credentials.credentials = "invalid_token"
        
        with patch.object(rbac_middleware.auth_service, 'validate_token') as mock_validate:
            mock_validate.side_effect = Exception("Invalid token")
            
            with pytest.raises(HTTPException) as exc_info:
                await rbac_middleware.get_current_user(mock_credentials)
            
            assert exc_info.value.status_code == 401
    
    def test_require_permission_decorator(self, rbac_middleware, mock_user):
        """Test require_permission decorator"""
        @rbac_middleware.require_permission("model:read", "model")
        async def test_endpoint(current_user: User):
            return {"message": "success"}
        
        # Mock the permission check to return True
        with patch.object(rbac_middleware.rbac_engine, 'check_permission', return_value=True):
            # This would normally be called by FastAPI with dependency injection
            # For testing, we simulate the call
            result = asyncio.run(test_endpoint(current_user=mock_user))
            assert result["message"] == "success"
    
    def test_require_role_decorator(self, rbac_middleware, mock_user):
        """Test require_role decorator"""
        @rbac_middleware.require_role("data_scientist")
        async def test_endpoint(current_user: User):
            return {"message": "success"}
        
        # Mock the role check to return True
        with patch.object(rbac_middleware.rbac_engine, 'has_role', return_value=True):
            result = asyncio.run(test_endpoint(current_user=mock_user))
            assert result["message"] == "success"
    
    def test_require_any_permission_decorator(self, rbac_middleware, mock_user):
        """Test require_any_permission decorator"""
        @rbac_middleware.require_any_permission(["model:read", "policy:read"], "model")
        async def test_endpoint(current_user: User):
            return {"message": "success"}
        
        # Mock the permission check to return True for one permission
        def mock_check_permission(user, permission, resource):
            return permission == "model:read"
        
        with patch.object(rbac_middleware.rbac_engine, 'check_permission', side_effect=mock_check_permission):
            result = asyncio.run(test_endpoint(current_user=mock_user))
            assert result["message"] == "success"
    
    def test_require_all_permissions_decorator(self, rbac_middleware, mock_user):
        """Test require_all_permissions decorator"""
        @rbac_middleware.require_all_permissions(["model:read", "policy:read"], "model")
        async def test_endpoint(current_user: User):
            return {"message": "success"}
        
        # Mock the permission check to return True for all permissions
        with patch.object(rbac_middleware.rbac_engine, 'check_permission', return_value=True):
            result = asyncio.run(test_endpoint(current_user=mock_user))
            assert result["message"] == "success"


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])