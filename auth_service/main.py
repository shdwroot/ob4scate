"""
Authentication Service
Provides JWT-based authentication, password hashing, and session management
"""

import logging

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, SecretStr

from .auth_core import auth_service
from .rbac_engine import User
from .rbac_middleware import get_current_user

logger = logging.getLogger(__name__)

app = FastAPI(title="Authentication Service", version="1.0.0")
security = HTTPBearer()


# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "auth_service"}


# Authentication models
class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=32, max_length=8192)


# Authentication endpoints
@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login endpoint"""
    try:
        return await auth_service.login(request.username, request.password.get_secret_value())
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Login failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed",
        ) from exc


@app.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout endpoint"""
    try:
        if not current_user.session_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session information is missing",
            )
        success = await auth_service.logout(current_user.session_id, current_user.user_id)
        return {"message": "Logged out successfully", "success": success}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Logout failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed",
        ) from exc


@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Token refresh endpoint"""
    try:
        return await auth_service.refresh_token(request.refresh_token)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Token refresh failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed",
        ) from exc


@app.get("/validate")
async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Token validation endpoint"""
    try:
        token = credentials.credentials
        user_info = await auth_service.validate_token(token)
        return {"valid": True, "user": user_info}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Token validation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation failed",
        ) from exc
