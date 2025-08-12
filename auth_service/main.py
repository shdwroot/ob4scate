"""
Authentication Service
Provides JWT-based authentication, password hashing, and session management
"""
from fastapi import FastAPI, HTTPException, Depends, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import os

from .auth_core import auth_service

app = FastAPI(title="Authentication Service", version="1.0.0")
security = HTTPBearer()

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "auth_service"}

# Authentication models
class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    session_id: str

# Authentication endpoints
@app.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login endpoint"""
    try:
        return await auth_service.login(request.username, request.password)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@app.post("/logout")
async def logout(request: LogoutRequest):
    """Logout endpoint"""
    try:
        success = await auth_service.logout(request.session_id)
        return {"message": "Logged out successfully", "success": success}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """Token refresh endpoint"""
    try:
        return await auth_service.refresh_token(request.refresh_token)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )

@app.get("/validate")
async def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Token validation endpoint"""
    try:
        token = credentials.credentials
        user_info = await auth_service.validate_token(token)
        return {"valid": True, "user": user_info}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token validation failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)