"""Gateway authentication and authorization tests."""

import pytest
from fastapi.testclient import TestClient

from auth_service.rbac_engine import User
from auth_service.rbac_middleware import get_current_user
from gateway_proxy.main import gateway


@pytest.fixture
def client():
    gateway.dependency_overrides.clear()
    with TestClient(gateway) as test_client:
        yield test_client
    gateway.dependency_overrides.clear()


def authenticate_as(user: User) -> None:
    async def override_current_user() -> User:
        return user

    gateway.dependency_overrides[get_current_user] = override_current_user


def regular_user() -> User:
    return User(
        user_id="test_user",
        username="testuser",
        roles=["user"],
        tenant_id="tenant1",
        session_id="session1",
    )


def admin_user() -> User:
    return User(
        user_id="admin_user",
        username="admin",
        roles=["super_admin"],
        tenant_id="tenant1",
        session_id="session2",
    )


def test_public_endpoints(client):
    assert client.get("/health").status_code == 200
    assert client.get("/").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_protected_endpoint_requires_authentication(client):
    assert client.get("/obfuscation/sanitize").status_code == 401


def test_user_can_access_gateway_and_identity(client):
    authenticate_as(regular_user())
    sanitized = client.get("/obfuscation/sanitize")
    identity = client.get("/me")
    assert sanitized.status_code == 200
    assert sanitized.json()["user"] == "testuser"
    assert identity.status_code == 200
    assert identity.json()["permissions"] == ["gateway:use"]


def test_admin_route_enforces_role(client):
    authenticate_as(regular_user())
    assert client.get("/admin/users").status_code == 403

    authenticate_as(admin_user())
    response = client.get("/admin/users")
    assert response.status_code == 200
    assert response.json()["user"] == "admin"


def test_internal_service_routes_are_admin_only(client):
    assert client.get("/internal/obfuscation/health").status_code == 401

    authenticate_as(regular_user())
    assert client.get("/internal/obfuscation/health").status_code == 403

    authenticate_as(admin_user())
    assert client.get("/internal/obfuscation/health").status_code == 200


def test_security_and_timing_headers(client):
    response = client.get("/health", headers={"X-Request-ID": "request-123"})
    assert response.headers["x-request-id"] == "request-123"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert float(response.headers["x-process-time"]) >= 0


def test_cors_allows_configured_local_origin(client):
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
