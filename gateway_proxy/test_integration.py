"""End-to-end tests for the gateway authentication lifecycle."""

import pytest
from fastapi.testclient import TestClient

import auth_service.main as auth_api
from auth_service.auth_core import AuthService, PasswordManager, SessionManager
from auth_service.rbac_middleware import rbac_middleware
from gateway_proxy.main import gateway


@pytest.fixture
def auth_service(monkeypatch):
    service = AuthService(
        users={
            "admin": {
                "user_id": "admin-id",
                "username": "admin",
                "password_hash": PasswordManager.hash_password("test-admin-password"),
                "roles": ["super_admin"],
                "permissions": [],
                "tenant_id": "tenant1",
            }
        },
        session_manager=SessionManager(),
    )
    monkeypatch.setattr(auth_api, "auth_service", service)
    monkeypatch.setattr(rbac_middleware, "auth_service", service)
    return service


@pytest.fixture
def client(auth_service):
    gateway.dependency_overrides.clear()
    with TestClient(gateway) as test_client:
        yield test_client
    gateway.dependency_overrides.clear()


def test_authentication_lifecycle(client):
    login = client.post(
        "/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert login.status_code == 200
    tokens = login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    identity = client.get("/me", headers=headers)
    assert identity.status_code == 200
    assert identity.json()["tenant_id"] == "tenant1"

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

    reuse = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert reuse.status_code == 401

    refreshed_headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
    logout = client.post("/auth/logout", headers=refreshed_headers)
    assert logout.status_code == 200

    assert client.get("/me", headers=refreshed_headers).status_code == 401


def test_invalid_login_is_rejected_without_server_error(client):
    response = client.post("/auth/login", json={"username": "admin", "password": "wrong-password"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_openapi_lists_security_scheme(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    document = response.json()
    assert "HTTPBearer" in document["components"]["securitySchemes"]
