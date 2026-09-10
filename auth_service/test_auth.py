"""Authentication unit and lifecycle tests."""

from datetime import timedelta

import pytest
from fastapi import HTTPException

from .auth_core import (
    AuthenticationError,
    AuthService,
    JWTManager,
    PasswordManager,
    SessionManager,
)


def token_data(**overrides):
    data = {
        "sub": "test_user",
        "username": "testuser",
        "roles": ["user"],
        "tenant_id": "tenant1",
        "session_id": "test_session_id",
    }
    return {**data, **overrides}


class TestJWTManager:
    def test_create_and_verify_access_token(self):
        payload = JWTManager.verify_token(JWTManager.create_access_token(token_data()), "access")
        assert payload["sub"] == "test_user"
        assert payload["aud"] == "ob4scate-api"
        assert payload["iss"] == "ob4scate-auth"
        assert payload["type"] == "access"
        assert payload["jti"]

    def test_create_and_verify_refresh_token(self):
        payload = JWTManager.verify_token(JWTManager.create_refresh_token(token_data()), "refresh")
        assert payload["sub"] == "test_user"
        assert payload["type"] == "refresh"

    def test_rejects_wrong_token_type(self):
        access_token = JWTManager.create_access_token(token_data())
        with pytest.raises(AuthenticationError, match="Invalid token type"):
            JWTManager.verify_token(access_token, "refresh")

    def test_rejects_invalid_token(self):
        with pytest.raises(AuthenticationError, match="Token validation failed"):
            JWTManager.verify_token("invalid_token", "access")

    def test_rejects_expired_token(self):
        token = JWTManager.create_access_token(token_data(), expires_delta=timedelta(seconds=-1))
        with pytest.raises(AuthenticationError, match="Token validation failed"):
            JWTManager.verify_token(token, "access")

    def test_rejects_token_without_session(self):
        token = JWTManager.create_access_token({"sub": "test_user"})
        with pytest.raises(AuthenticationError, match="required session claims"):
            JWTManager.verify_token(token, "access")


class TestPasswordManager:
    def test_hash_and_verify_password(self):
        plain_text = "test_password_123"
        hashed = PasswordManager.hash_password(plain_text)
        assert hashed.startswith("$argon2")
        assert hashed != plain_text
        assert PasswordManager.verify_password(plain_text, hashed)
        assert not PasswordManager.verify_password("wrong_password", hashed)

    def test_rejects_malformed_hash(self):
        assert not PasswordManager.verify_password("password", "not-a-password-hash")


class TestSessionManager:
    @pytest.mark.asyncio
    async def test_session_lifecycle_and_refresh_rotation(self):
        manager = SessionManager()
        session_id = await manager.create_session(
            "test_user",
            {
                "username": "testuser",
                "roles": ["user"],
                "refresh_jti": "old-jti",
            },
        )
        session = await manager.get_session(session_id)
        assert session is not None
        assert session["user_id"] == "test_user"

        assert await manager.rotate_refresh_token(session_id, "old-jti", "new-jti")
        assert not await manager.rotate_refresh_token(session_id, "old-jti", "third-jti")
        assert not await manager.invalidate_session(session_id, "other_user")
        assert await manager.invalidate_session(session_id, "test_user")
        assert await manager.get_session(session_id) is None

    @pytest.mark.asyncio
    async def test_invalidates_all_user_sessions(self):
        manager = SessionManager()
        await manager.create_session("test_user", {"refresh_jti": "one"})
        await manager.create_session("test_user", {"refresh_jti": "two"})
        assert await manager.invalidate_user_sessions("test_user") == 2


@pytest.fixture
def configured_auth_service():
    return AuthService(
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


class TestAuthService:
    @pytest.mark.asyncio
    async def test_has_no_builtin_admin_account(self):
        service = AuthService(users={})
        assert await service.authenticate_user("admin", "admin123") is None

    @pytest.mark.asyncio
    async def test_login_validate_refresh_and_logout(self, configured_auth_service):
        tokens = await configured_auth_service.login("admin", "test-admin-password")
        identity = await configured_auth_service.validate_token(tokens["access_token"])
        assert identity["user_id"] == "admin-id"
        assert identity["tenant_id"] == "tenant1"

        refreshed = await configured_auth_service.refresh_token(tokens["refresh_token"])
        assert refreshed["refresh_token"] != tokens["refresh_token"]
        await configured_auth_service.validate_token(refreshed["access_token"])

        with pytest.raises(HTTPException) as reused:
            await configured_auth_service.refresh_token(tokens["refresh_token"])
        assert reused.value.status_code == 401

        payload = JWTManager.verify_token(refreshed["access_token"])
        assert await configured_auth_service.logout(payload["session_id"], "admin-id")
        with pytest.raises(HTTPException) as logged_out:
            await configured_auth_service.validate_token(refreshed["access_token"])
        assert logged_out.value.status_code == 401

    @pytest.mark.asyncio
    async def test_login_rejects_invalid_credentials(self, configured_auth_service):
        with pytest.raises(HTTPException) as invalid:
            await configured_auth_service.login("admin", "wrong-password")
        assert invalid.value.status_code == 401
