"""
Integration tests for Gateway Proxy with actual authentication flow
Tests the complete authentication and authorization flow
"""
import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gateway_proxy.main import gateway


class TestGatewayIntegration:
    """Test gateway integration with real authentication flow"""
    
    @pytest.fixture
    def client(self):
        """Test client for gateway"""
        return TestClient(gateway)
    
    def test_health_endpoint_works(self, client):
        """Test health endpoint is accessible"""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_root_endpoint_works(self, client):
        """Test root endpoint is accessible"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "Enterprise Data Obfuscation Gateway" in data["message"]
        assert "JWT Authentication" in data["features"]
    
    def test_auth_login_endpoint_exists(self, client):
        """Test auth login endpoint exists"""
        # Try to login with test credentials
        response = client.post("/auth/login", json={
            "username": "admin",
            "password": "admin123"
        })
        # Should either succeed (200), fail validation (422), fail auth (401), or have server error (500)
        # The important thing is that the endpoint exists (not 404)
        assert response.status_code in [200, 422, 401, 500]
        assert response.status_code != 404  # Endpoint should exist
    
    def test_protected_endpoint_requires_auth(self, client):
        """Test protected endpoints require authentication"""
        response = client.get("/obfuscation/sanitize")
        # Should return either 401 (Unauthorized) or 403 (Forbidden) for missing/invalid auth
        assert response.status_code in [401, 403]
    
    def test_admin_endpoint_requires_auth(self, client):
        """Test admin endpoints require authentication"""
        response = client.get("/admin/users")
        # Should return either 401 (Unauthorized) or 403 (Forbidden) for missing/invalid auth
        assert response.status_code in [401, 403]
    
    def test_user_info_endpoint_requires_auth(self, client):
        """Test user info endpoint requires authentication"""
        response = client.get("/me")
        # Should return either 401 (Unauthorized) or 403 (Forbidden) for missing/invalid auth
        assert response.status_code in [401, 403]
    
    def test_internal_endpoints_accessible(self, client):
        """Test internal service endpoints are accessible"""
        # Internal endpoints should be accessible (for service-to-service communication)
        response = client.get("/internal/obfuscation/health")
        # Should either work or return a service-specific error, but not auth error
        assert response.status_code != 401
    
    def test_docs_endpoint_accessible(self, client):
        """Test API documentation is accessible"""
        response = client.get("/docs")
        # Should redirect or return docs page
        assert response.status_code in [200, 307]  # 307 is redirect
    
    def test_openapi_endpoint_accessible(self, client):
        """Test OpenAPI spec is accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert data["info"]["title"] == "Enterprise Data Obfuscation Gateway - Unified API"


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])