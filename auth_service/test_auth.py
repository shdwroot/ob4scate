"""
Unit tests for authentication service
Tests JWT token generation/validation, password hashing, and session management
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import json

from .auth_core import (
    JWTManager, 
    PasswordManager, 
    SessionManager, 
    AuthService,
    AuthenticationError
)


class TestJWTManager:
    """Test JWT token generation and validation"""
    
    def test_create_access_token(self):
        """Test access token creation"""
        data = {"sub": "test_user", "username": "testuser"}
        token = JWTManager.create_access_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = JWTManager.verify_token(token, "access")
        assert payload["sub"] == "test_user"
        assert payload["username"] == "testuser"
        assert payload["type"] == "access"
    
    def test_create_refresh_token(self):
        """Test refresh token creation"""
        data = {"sub": "test_user", "username": "testuser"}
        token = JWTManager.create_refresh_token(data)
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token can be decoded
        payload = JWTManager.verify_token(token, "refresh")
        assert payload["sub"] == "test_user"
        assert payload["username"] == "testuser"
        assert payload["type"] == "refresh"
    
    def test_verify_token_invalid_type(self):
        """Test token verification with wrong type"""
        data = {"sub": "test_user"}
        access_token = JWTManager.create_access_token(data)
        
        with pytest.raises(AuthenticationError, match="Invalid token type"):
            JWTManager.verify_token(access_token, "refresh")
    
    def test_verify_token_invalid_token(self):
        """Test token verification with invalid token"""
        with pytest.raises(AuthenticationError, match="Token validation failed"):
            JWTManager.verify_token("invalid_token", "access")
    
    def test_token_expiration(self):
        """Test token expiration"""
        data = {"sub": "test_user"}
        # Create token with very short expiration
        expires_delta = timedelta(seconds=-1)  # Already expired
        token = JWTManager.create_access_token(data, expires_delta)
        
        with pytest.raises(AuthenticationError, match="Token validation failed"):
            JWTManager.verify_token(token, "access")


class TestPasswordManager:
    """Test password hashing and verification"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "test_password_123"
        hashed = PasswordManager.hash_password(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 0
        assert hashed != password  # Should be different from original
    
    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "test_password_123"
        hashed = PasswordManager.hash_password(password)
        
        assert PasswordManager.verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = PasswordManager.hash_password(password)
        
        assert PasswordManager.verify_password(wrong_password, hashed) is False
    
    def test_generate_salt(self):
        """Test salt generation"""
        salt1 = PasswordManager.generate_salt()
        salt2 = PasswordManager.generate_salt()
        
        assert isinstance(salt1, str)
        assert isinstance(salt2, str)
        assert len(salt1) == 32  # 16 bytes = 32 hex chars
        assert len(salt2) == 32
        assert salt1 != salt2  # Should be different


class TestSessionManager:
    """Test session management with Redis backend"""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        mock_client = Mock()
        mock_client.setex.return_value = True
        mock_client.sadd.return_value = 1
        mock_client.expire.return_value = True
        mock_client.get.return_value = None
        mock_client.delete.return_value = 1
        mock_client.smembers.return_value = set()
        mock_client.srem.return_value = 1
        return mock_client
    
    @pytest.fixture
    def session_manager(self, mock_redis):
        """Session manager with mocked Redis"""
        manager = SessionManager()
        manager.redis_client = mock_redis
        return manager
    
    @pytest.mark.asyncio
    async def test_create_session(self, session_manager, mock_redis):
        """Test session creation"""
        user_id = "test_user"
        session_data = {"username": "testuser", "roles": ["user"]}
        
        session_id = await session_manager.create_session(user_id, session_data)
        
        assert isinstance(session_id, str)
        assert len(session_id) > 0
        
        # Verify Redis calls
        mock_redis.setex.assert_called_once()
        mock_redis.sadd.assert_called_once()
        mock_redis.expire.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_session_exists(self, session_manager, mock_redis):
        """Test getting existing session"""
        session_id = "test_session_id"
        session_data = {
            "session_id": session_id,
            "user_id": "test_user",
            "username": "testuser",
            "created_at": datetime.utcnow().isoformat()
        }
        
        mock_redis.get.return_value = json.dumps(session_data)
        
        result = await session_manager.get_session(session_id)
        
        assert result is not None
        assert result["session_id"] == session_id
        assert result["user_id"] == "test_user"
        assert "last_accessed" in result
    
    @pytest.mark.asyncio
    async def test_get_session_not_exists(self, session_manager, mock_redis):
        """Test getting non-existent session"""
        session_id = "non_existent_session"
        mock_redis.get.return_value = None
        
        result = await session_manager.get_session(session_id)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_invalidate_session(self, session_manager, mock_redis):
        """Test session invalidation"""
        session_id = "test_session_id"
        session_data = {
            "session_id": session_id,
            "user_id": "test_user"
        }
        
        mock_redis.get.return_value = json.dumps(session_data)
        mock_redis.delete.return_value = 1
        
        result = await session_manager.invalidate_session(session_id)
        
        assert result is True
        mock_redis.delete.assert_called()
        mock_redis.srem.assert_called()
    
    @pytest.mark.asyncio
    async def test_invalidate_user_sessions(self, session_manager, mock_redis):
        """Test invalidating all user sessions"""
        user_id = "test_user"
        session_ids = {"session1", "session2", "session3"}
        
        mock_redis.smembers.return_value = session_ids
        mock_redis.delete.return_value = 1
        
        count = await session_manager.invalidate_user_sessions(user_id)
        
        assert count == 3  # Should delete 3 sessions
        assert mock_redis.delete.call_count == 4  # 3 sessions + 1 user sessions set


class TestAuthService:
    """Test main authentication service"""
    
    @pytest.fixture
    def auth_service(self):
        """Auth service instance"""
        return AuthService()
    
    @pytest.mark.asyncio
    async def test_authenticate_user_valid(self, auth_service):
        """Test user authentication with valid credentials"""
        user = await auth_service.authenticate_user("admin", "admin123")
        
        assert user is not None
        assert user["username"] == "admin"
        assert user["user_id"] == "admin"
        assert "roles" in user
        assert "permissions" in user
    
    @pytest.mark.asyncio
    async def test_authenticate_user_invalid(self, auth_service):
        """Test user authentication with invalid credentials"""
        user = await auth_service.authenticate_user("admin", "wrong_password")
        
        assert user is None
    
    @pytest.mark.asyncio
    async def test_login_success(self, auth_service):
        """Test successful login"""
        with patch.object(auth_service.session_manager, 'create_session', return_value="test_session_id"):
            result = await auth_service.login("admin", "admin123")
            
            assert "access_token" in result
            assert "refresh_token" in result
            assert result["token_type"] == "bearer"
            assert "expires_in" in result
    
    @pytest.mark.asyncio
    async def test_login_failure(self, auth_service):
        """Test failed login"""
        with pytest.raises(Exception):  # Should raise HTTPException
            await auth_service.login("admin", "wrong_password")
    
    @pytest.mark.asyncio
    async def test_logout(self, auth_service):
        """Test logout"""
        with patch.object(auth_service.session_manager, 'invalidate_session', return_value=True):
            result = await auth_service.logout("test_session_id")
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_refresh_token_valid(self, auth_service):
        """Test token refresh with valid refresh token"""
        # Create a valid refresh token
        token_data = {
            "sub": "test_user",
            "username": "testuser",
            "roles": ["user"],
            "session_id": "test_session_id"
        }
        refresh_token = auth_service.jwt_manager.create_refresh_token(token_data)
        
        with patch.object(auth_service.session_manager, 'get_session', return_value={"valid": True}):
            result = await auth_service.refresh_token(refresh_token)
            
            assert "access_token" in result
            assert result["refresh_token"] == refresh_token
            assert result["token_type"] == "bearer"
    
    @pytest.mark.asyncio
    async def test_validate_token_valid(self, auth_service):
        """Test token validation with valid token"""
        # Create a valid access token
        token_data = {
            "sub": "test_user",
            "username": "testuser",
            "roles": ["user"],
            "session_id": "test_session_id"
        }
        access_token = auth_service.jwt_manager.create_access_token(token_data)
        
        with patch.object(auth_service.session_manager, 'get_session', return_value={"valid": True}):
            result = await auth_service.validate_token(access_token)
            
            assert result["user_id"] == "test_user"
            assert result["username"] == "testuser"
            assert result["session_id"] == "test_session_id"


# Test runner
if __name__ == "__main__":
    pytest.main([__file__, "-v"])