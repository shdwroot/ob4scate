"""
Core authentication functionality
Handles JWT tokens, password hashing, and session management
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
import hashlib
import redis
import json
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
import os

# Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Redis client for session management
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None  # Fallback for development without Redis


class AuthenticationError(Exception):
    """Custom authentication error"""
    pass


class JWTManager:
    """JWT token generation and validation"""
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != token_type:
                raise AuthenticationError(f"Invalid token type. Expected {token_type}")
            return payload
        except JWTError as e:
            raise AuthenticationError(f"Token validation failed: {str(e)}")


class PasswordManager:
    """Password hashing and verification utilities"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        return pwd_context.hash(password)
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def generate_salt() -> str:
        """Generate a random salt for additional security"""
        return secrets.token_hex(16)


class SessionManager:
    """User session management with Redis backend"""
    
    def __init__(self):
        self.redis_client = redis_client
        self.session_prefix = "session:"
        self.user_sessions_prefix = "user_sessions:"
    
    async def create_session(self, user_id: str, session_data: Dict[str, Any]) -> str:
        """Create a new user session"""
        session_id = secrets.token_urlsafe(32)
        session_key = f"{self.session_prefix}{session_id}"
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        
        # Add session metadata
        session_data.update({
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat()
        })
        
        if self.redis_client:
            try:
                # Store session data
                self.redis_client.setex(
                    session_key, 
                    timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds(),
                    json.dumps(session_data)
                )
                
                # Track user sessions
                self.redis_client.sadd(user_sessions_key, session_id)
                self.redis_client.expire(user_sessions_key, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds())
                
            except Exception as e:
                raise AuthenticationError(f"Session creation failed: {str(e)}")
        
        return session_id
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve session data"""
        if not self.redis_client:
            return None
            
        session_key = f"{self.session_prefix}{session_id}"
        
        try:
            session_data = self.redis_client.get(session_key)
            if session_data:
                data = json.loads(session_data)
                # Update last accessed time
                data["last_accessed"] = datetime.utcnow().isoformat()
                self.redis_client.setex(
                    session_key,
                    timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS).total_seconds(),
                    json.dumps(data)
                )
                return data
        except Exception as e:
            raise AuthenticationError(f"Session retrieval failed: {str(e)}")
        
        return None
    
    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a specific session"""
        if not self.redis_client:
            return True
            
        session_key = f"{self.session_prefix}{session_id}"
        
        try:
            # Get session to find user_id
            session_data = self.redis_client.get(session_key)
            if session_data:
                data = json.loads(session_data)
                user_id = data.get("user_id")
                
                # Remove from user sessions set
                if user_id:
                    user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
                    self.redis_client.srem(user_sessions_key, session_id)
            
            # Delete session
            return bool(self.redis_client.delete(session_key))
        except Exception as e:
            raise AuthenticationError(f"Session invalidation failed: {str(e)}")
    
    async def invalidate_user_sessions(self, user_id: str) -> int:
        """Invalidate all sessions for a user"""
        if not self.redis_client:
            return 0
            
        user_sessions_key = f"{self.user_sessions_prefix}{user_id}"
        
        try:
            session_ids = self.redis_client.smembers(user_sessions_key)
            count = 0
            
            for session_id in session_ids:
                session_key = f"{self.session_prefix}{session_id}"
                if self.redis_client.delete(session_key):
                    count += 1
            
            # Clear user sessions set
            self.redis_client.delete(user_sessions_key)
            return count
        except Exception as e:
            raise AuthenticationError(f"User session invalidation failed: {str(e)}")


class AuthService:
    """Main authentication service class"""
    
    def __init__(self):
        self.jwt_manager = JWTManager()
        self.password_manager = PasswordManager()
        self.session_manager = SessionManager()
    
    async def authenticate_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user credentials - placeholder for database integration"""
        # TODO: Integrate with user database
        # For now, return a mock user for testing
        if username == "admin" and password == "admin123":
            return {
                "user_id": "admin",
                "username": "admin",
                "roles": ["super_admin"],
                "permissions": ["*"]
            }
        return None
    
    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """Login user and create tokens"""
        user = await self.authenticate_user(username, password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Create session
        session_id = await self.session_manager.create_session(
            user["user_id"], 
            {"username": username, "roles": user["roles"]}
        )
        
        # Create tokens
        token_data = {
            "sub": user["user_id"],
            "username": username,
            "roles": user["roles"],
            "session_id": session_id
        }
        
        access_token = self.jwt_manager.create_access_token(token_data)
        refresh_token = self.jwt_manager.create_refresh_token(token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
    
    async def logout(self, session_id: str) -> bool:
        """Logout user and invalidate session"""
        return await self.session_manager.invalidate_session(session_id)
    
    async def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token"""
        try:
            payload = self.jwt_manager.verify_token(refresh_token, "refresh")
            session_id = payload.get("session_id")
            
            # Verify session is still valid
            session_data = await self.session_manager.get_session(session_id)
            if not session_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired"
                )
            
            # Create new access token
            token_data = {
                "sub": payload["sub"],
                "username": payload["username"],
                "roles": payload["roles"],
                "session_id": session_id
            }
            
            access_token = self.jwt_manager.create_access_token(token_data)
            
            return {
                "access_token": access_token,
                "refresh_token": refresh_token,  # Keep same refresh token
                "token_type": "bearer",
                "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
            
        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )
    
    async def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate access token and return user info"""
        try:
            payload = self.jwt_manager.verify_token(token, "access")
            session_id = payload.get("session_id")
            
            # Verify session is still valid
            session_data = await self.session_manager.get_session(session_id)
            if not session_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session expired"
                )
            
            return {
                "user_id": payload["sub"],
                "username": payload["username"],
                "roles": payload["roles"],
                "session_id": session_id
            }
            
        except AuthenticationError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(e)
            )


# Global auth service instance
auth_service = AuthService()