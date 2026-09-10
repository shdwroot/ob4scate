"""Authentication primitives for JWTs, password hashes, and sessions."""

from __future__ import annotations

import asyncio
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from redis.asyncio import Redis
from redis.exceptions import WatchError

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
SESSION_BACKEND = os.getenv("SESSION_BACKEND", "memory").lower()
JWT_ISSUER = os.getenv("JWT_ISSUER", "ob4scate-auth")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "ob4scate-api")
BEARER = "bearer"


def _load_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET_KEY")
    if secret:
        if len(secret) < 32:
            raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters")
        return secret
    if os.getenv("APP_ENV", "development").lower() in {"development", "test"}:
        return secrets.token_urlsafe(48)
    raise RuntimeError("JWT_SECRET_KEY is required outside development and test")


SECRET_KEY = _load_jwt_secret()
password_hash = PasswordHash.recommended()


class AuthenticationError(Exception):
    """Raised when a credential or session cannot be authenticated."""


class JWTManager:
    """Create and validate signed access and refresh tokens."""

    @staticmethod
    def _create_token(data: dict[str, Any], token_type: str, expires_delta: timedelta) -> str:
        now = datetime.now(UTC)
        claims = data.copy()
        claims.update(
            {
                "aud": JWT_AUDIENCE,
                "exp": now + expires_delta,
                "iat": now,
                "iss": JWT_ISSUER,
                "jti": claims.get("jti", secrets.token_urlsafe(24)),
                "nbf": now,
                "type": token_type,
            }
        )
        return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)

    @classmethod
    def create_access_token(
        cls, data: dict[str, Any], expires_delta: timedelta | None = None
    ) -> str:
        return cls._create_token(
            data,
            "access",
            expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    @classmethod
    def create_refresh_token(cls, data: dict[str, Any]) -> str:
        return cls._create_token(data, "refresh", timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

    @staticmethod
    def verify_token(token: str, expected_kind: str = "access") -> dict[str, Any]:
        try:
            payload = jwt.decode(
                token,
                SECRET_KEY,
                algorithms=[ALGORITHM],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
                options={"require": ["exp", "iat", "sub"]},
            )
        except InvalidTokenError as exc:
            raise AuthenticationError("Token validation failed") from exc
        if payload.get("type") != expected_kind:
            raise AuthenticationError(f"Invalid token type. Expected {expected_kind}")
        if not payload.get("session_id") or not payload.get("jti"):
            raise AuthenticationError("Token is missing required session claims")
        return payload


class PasswordManager:
    """Hash and verify passwords using pwdlib's recommended Argon2 settings."""

    @staticmethod
    def hash_password(password: str) -> str:
        return password_hash.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        try:
            return password_hash.verify(plain_password, hashed_password)
        except (TypeError, UnknownHashError, ValueError):
            return False


class SessionManager:
    """Manage fixed-lifetime sessions in Redis or an explicit memory backend."""

    def __init__(self, redis_client: Redis | None = None) -> None:
        if SESSION_BACKEND not in {"memory", "redis"}:
            raise RuntimeError("SESSION_BACKEND must be either 'memory' or 'redis'")
        self.redis_client = redis_client
        if self.redis_client is None and SESSION_BACKEND == "redis":
            self.redis_client = Redis.from_url(REDIS_URL, decode_responses=True)
        self.session_prefix = "session:"
        self.user_sessions_prefix = "user_sessions:"
        self._memory_sessions: dict[str, dict[str, Any]] = {}
        self._memory_user_sessions: dict[str, set[str]] = {}
        self._memory_lock = asyncio.Lock()
        self._ttl_seconds = int(timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())

    async def create_session(self, user_id: str, session_data: dict[str, Any]) -> str:
        session_id = secrets.token_urlsafe(32)
        stored_data = {
            **session_data,
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now(UTC).isoformat(),
        }
        if self.redis_client is not None:
            session_key = f"{self.session_prefix}{session_id}"
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            try:
                async with self.redis_client.pipeline(transaction=True) as pipe:
                    pipe.set(session_key, json.dumps(stored_data), ex=self._ttl_seconds)
                    pipe.sadd(user_sessions_key, session_id)
                    pipe.expire(user_sessions_key, self._ttl_seconds)
                    await pipe.execute()
            except Exception as exc:
                raise AuthenticationError("Session creation failed") from exc
        else:
            async with self._memory_lock:
                self._memory_sessions[session_id] = stored_data
                self._memory_user_sessions.setdefault(user_id, set()).add(session_id)
        return session_id

    async def get_session(self, session_id: str | None) -> dict[str, Any] | None:
        if not session_id:
            return None
        if self.redis_client is not None:
            try:
                session_data = await self.redis_client.get(f"{self.session_prefix}{session_id}")
                return json.loads(session_data) if session_data else None
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise AuthenticationError("Stored session data is invalid") from exc
            except Exception as exc:
                raise AuthenticationError("Session retrieval failed") from exc
        async with self._memory_lock:
            data = self._memory_sessions.get(session_id)
            return data.copy() if data else None

    async def rotate_refresh_token(self, session_id: str, expected_jti: str, new_jti: str) -> bool:
        """Atomically replace the refresh-token identifier for one session."""
        if self.redis_client is not None:
            session_key = f"{self.session_prefix}{session_id}"
            for _ in range(3):
                try:
                    async with self.redis_client.pipeline(transaction=True) as pipe:
                        await pipe.watch(session_key)
                        raw_data = await pipe.get(session_key)
                        if not raw_data:
                            return False
                        data = json.loads(raw_data)
                        if not secrets.compare_digest(
                            str(data.get("refresh_jti", "")), expected_jti
                        ):
                            return False
                        data["refresh_jti"] = new_jti
                        pipe.multi()
                        pipe.set(session_key, json.dumps(data), ex=self._ttl_seconds)
                        await pipe.execute()
                        return True
                except WatchError:
                    continue
                except Exception as exc:
                    raise AuthenticationError("Refresh token rotation failed") from exc
            return False
        async with self._memory_lock:
            data = self._memory_sessions.get(session_id)
            if not data or not secrets.compare_digest(
                str(data.get("refresh_jti", "")), expected_jti
            ):
                return False
            data["refresh_jti"] = new_jti
            return True

    async def invalidate_session(
        self, session_id: str, expected_user_id: str | None = None
    ) -> bool:
        if self.redis_client is not None:
            session_key = f"{self.session_prefix}{session_id}"
            try:
                raw_data = await self.redis_client.get(session_key)
                if not raw_data:
                    return False
                data = json.loads(raw_data)
                user_id = data.get("user_id")
                if expected_user_id and user_id != expected_user_id:
                    return False
                async with self.redis_client.pipeline(transaction=True) as pipe:
                    if user_id:
                        pipe.srem(f"{self.user_sessions_prefix}{user_id}", session_id)
                    pipe.delete(session_key)
                    results = await pipe.execute()
                return bool(results[-1])
            except Exception as exc:
                raise AuthenticationError("Session invalidation failed") from exc
        async with self._memory_lock:
            data = self._memory_sessions.get(session_id)
            if not data:
                return False
            user_id = data.get("user_id")
            if expected_user_id and user_id != expected_user_id:
                return False
            del self._memory_sessions[session_id]
            if user_id in self._memory_user_sessions:
                self._memory_user_sessions[user_id].discard(session_id)
            return True

    async def invalidate_user_sessions(self, user_id: str) -> int:
        if self.redis_client is not None:
            user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
            try:
                session_ids = await self.redis_client.smembers(user_sessions_key)
                async with self.redis_client.pipeline(transaction=True) as pipe:
                    for session_id in session_ids:
                        pipe.delete(f"{self.session_prefix}{session_id}")
                    pipe.delete(user_sessions_key)
                    results = await pipe.execute()
                return sum(bool(result) for result in results[:-1])
            except Exception as exc:
                raise AuthenticationError("User session invalidation failed") from exc
        async with self._memory_lock:
            session_ids = self._memory_user_sessions.pop(user_id, set())
            for session_id in session_ids:
                self._memory_sessions.pop(session_id, None)
            return len(session_ids)


class AuthService:
    """Authenticate configured users and issue session-bound tokens."""

    def __init__(
        self,
        users: dict[str, dict[str, Any]] | None = None,
        session_manager: SessionManager | None = None,
    ) -> None:
        self.jwt_manager = JWTManager()
        self.password_manager = PasswordManager()
        self.session_manager = session_manager or SessionManager()
        self._users = users if users is not None else self._load_bootstrap_user()
        self._dummy_password_hash = self.password_manager.hash_password(secrets.token_urlsafe(32))

    def _load_bootstrap_user(self) -> dict[str, dict[str, Any]]:
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
        if not password:
            return {}
        username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin")
        return {
            username: {
                "user_id": os.getenv("BOOTSTRAP_ADMIN_USER_ID", username),
                "username": username,
                "password_hash": self.password_manager.hash_password(password),
                "roles": ["super_admin"],
                "permissions": [],
                "tenant_id": os.getenv("BOOTSTRAP_ADMIN_TENANT", "default"),
            }
        }

    async def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        user = self._users.get(username)
        candidate_hash = user["password_hash"] if user else self._dummy_password_hash
        if not self.password_manager.verify_password(password, candidate_hash) or not user:
            return None
        return {key: value for key, value in user.items() if key != "password_hash"}

    async def login(self, username: str, password: str) -> dict[str, Any]:
        user = await self.authenticate_user(username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        refresh_jti = secrets.token_urlsafe(24)
        session_id = await self.session_manager.create_session(
            user["user_id"],
            {
                "username": user["username"],
                "roles": user["roles"],
                "tenant_id": user.get("tenant_id"),
                "refresh_jti": refresh_jti,
            },
        )
        token_data = {
            "sub": user["user_id"],
            "username": user["username"],
            "roles": user["roles"],
            "tenant_id": user.get("tenant_id"),
            "session_id": session_id,
        }
        return {
            "access_token": self.jwt_manager.create_access_token(token_data),
            "refresh_token": self.jwt_manager.create_refresh_token(
                {**token_data, "jti": refresh_jti}
            ),
            "token_type": BEARER,
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    async def logout(self, session_id: str, user_id: str | None = None) -> bool:
        return await self.session_manager.invalidate_session(session_id, user_id)

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        try:
            payload = self.jwt_manager.verify_token(refresh_token, "refresh")
            session_id = payload["session_id"]
            session_data = await self.session_manager.get_session(session_id)
            if not session_data or session_data.get("user_id") != payload.get("sub"):
                raise AuthenticationError("Session expired")
            old_jti = str(payload["jti"])
            new_jti = secrets.token_urlsafe(24)
            if not await self.session_manager.rotate_refresh_token(session_id, old_jti, new_jti):
                raise AuthenticationError("Refresh token has already been used")
            token_data = {
                "sub": payload["sub"],
                "username": session_data["username"],
                "roles": session_data["roles"],
                "tenant_id": session_data.get("tenant_id"),
                "session_id": session_id,
            }
            return {
                "access_token": self.jwt_manager.create_access_token(token_data),
                "refresh_token": self.jwt_manager.create_refresh_token(
                    {**token_data, "jti": new_jti}
                ),
                "token_type": BEARER,
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            }
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    async def validate_token(self, token: str) -> dict[str, Any]:
        try:
            payload = self.jwt_manager.verify_token(token, "access")
            session_id = payload["session_id"]
            session_data = await self.session_manager.get_session(session_id)
            if not session_data or session_data.get("user_id") != payload.get("sub"):
                raise AuthenticationError("Session expired")
            return {
                "user_id": payload["sub"],
                "username": session_data["username"],
                "roles": session_data["roles"],
                "tenant_id": session_data.get("tenant_id"),
                "session_id": session_id,
            }
        except AuthenticationError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


auth_service = AuthService()
