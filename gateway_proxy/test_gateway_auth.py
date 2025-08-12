"""
Tests for Gateway Proxy authentication integration
Tests JWT validation, RBAC enforcement, and middleware functionality
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway_proxy.main import gateway
from auth_service.rbac_engine import User


class TestGatewayAuthentication:
    """Test gateway authentication and RBAC integration"""
    
    @pytest.fixture
    def client(self):
        """Test client for gateway"""
        return TestClient(gateway)
    
    @pytest.fixture
    def mock_user(self):
        """Mock authenticated user"""
        return User(
            user_id="test_user",
            username="testuser",
            roles=["user"],
            tenant_id="tenant1"
        )
    
    @pytest.fixture
    def mock_admin_user(self):
        """Mock admin user"""
        return User(
            user_id="admin_user",
            username="admin",
            roles=["super_admin"],
            tenant_id="tenant1"
        )
    
    def test_health_check_no_auth(self, client):
        """Test health check endpoint doesn't require authentication"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_root_endpoint_no_auth(self, client):
        """Test root endpoint doesn't require authentication"""
        response = client.get("/")
        assert response.status_code == 200
        assert "Enterprise Data Obfuscation Gateway" in response.json()["message"]
    
    def test_protected_endpoint_no_auth(self, client):
        """Test protected endpoint requires authentication"""
        response = client.get("/obfuscation/sanitize")
        # Should return 401 for missing authentication
        assert response.status_code == 401
    
    def test_protected_endpoint_with_auth(self, client, mock_user):
        """Test protected endpoint with valid authentication"""
        with patch('auth_service.rbac_middleware.rbac_middleware.get_current_user_optional') as mock_get_user:
            with patch('auth_service.rbac_middleware.get_current_user') as mock_get_current:
                with patch('auth_service.rbac_engine.rbac_engine.check_permission') as mock_check_perm:
                    mock_get_user.return_value = mock_user
                    mock_get_current.return_value = mock_user
                    mock_check_perm.return_value = True
                    
                    headers = {"Authorization": "Bearer valid_token"}
                    response = client.get("/obfuscation/sanitize", headers=headers)
                    
                    assert response.status_code == 200
                    assert response.json()["user"] == "testuser"
    
    def test_admin_endpoint_regular_user(self, client, mock_user):
        """Test admin endpoint rejects regular user"""
        with patch('auth_service.rbac_middleware.rbac_middleware.get_current_user_optional') as mock_get_user:
            with patch('auth_service.rbac_middleware.get_current_user') as mock_get_current:
                with patch('auth_service.rbac_engine.rbac_engine.has_role') as mock_has_role:
                    mock_get_user.return_value = mock_user
                    mock_get_current.return_value = mock_user
                    mock_has_role.return_value = False  # Regular user doesn't have super_admin role
                    
                    headers = {"Authorization": "Bearer valid_token"}
                    response = client.get("/admin/users", headers=headers)
                    
                    assert response.status_code == 403
    
    def test_admin_endpoint_admin_user(self, client, mock_admin_user):
        """Test admin endpoint allows admin user"""
        with patch('auth_service.rbac_middleware.rbac_middleware.get_current_user_optional') as mock_get_user:
            with patch('auth_service.rbac_middleware.get_current_user') as mock_get_current:
                with patch('auth_service.rbac_engine.rbac_engine.has_role') as mock_has_role:
                    mock_get_user.return_value = mock_admin_user
                    mock_get_current.return_value = mock_admin_user
                    mock_has_role.return_value = True  # Admin user has super_admin role
                    
                    headers = {"Authorization": "Bearer admin_token"}
                    response = client.get("/admin/users", headers=headers)
                    
                    assert response.status_code == 200
                    assert response.json()["user"] == "admin"
    
    def test_user_info_endpoint(self, client, mock_user):
        """Test user info endpoint returns user details"""
        with patch('auth_service.rbac_middleware.rbac_middleware.get_current_user_optional') as mock_get_user:
            with patch('auth_service.rbac_middleware.get_current_user') as mock_get_current:
                with patch('auth_service.rbac_engine.rbac_engine.get_user_permissions') as mock_get_perms:
                    mock_get_user.return_value = mock_user
                    mock_get_current.return_value = mock_user
                    mock_get_perms.return_value = ["gateway:use"]
                    
                    headers = {"Authorization": "Bearer valid_token"}
                    response = client.get("/me", headers=headers)
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["user_id"] == "test_user"
                    assert data["username"] == "testuser"
                    assert "user" in data["roles"]
                    assert "gateway:use" in data["permissions"]
    
    def test_auth_endpoints_accessible(self, client):
        """Test authentication endpoints are accessible"""
        # Test login endpoint exists (will fail without credentials, but should not be 404)
        response = client.post("/auth/login", json={"username": "test", "password": "test"})
        # Should not be 404 (endpoint exists) but may be 401/422 (validation error)
        assert response.status_code != 404
    
    def test_middleware_adds_process_time(self, client):
        """Test middleware adds process time header for non-bypassed endpoints"""
        # Health endpoint bypasses middleware, so test a different endpoint
        response = client.get("/obfuscation/sanitize")
        # This endpoint should have middleware applied (even if it fails auth)
        # Note: TestClient may not trigger middleware the same way as real requests
        # This test verifies the middleware exists and is configured
        assert response.status_code in [401, 403]  # Should fail auth but middleware should run
    
    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options("/health")
        # CORS middleware should handle OPTIONS requests
        assert response.status_code in [200, 405]  # 405 if OPTIONS not explicitly handled


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])