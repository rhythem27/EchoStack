import uuid
import pytest
import jwt
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from backend.config import settings
from backend.auth import get_current_user_context, require_super_admin, current_user_id, current_user_permissions

@pytest.mark.unit
async def test_auth_invalid_jwt_format(mock_redis, mock_db_pool):
    """Verify that an invalid JWT string raises a 401 Unauthorized HTTP exception."""
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid_jwt_token_format")
    
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_context(credentials=creds)
        
    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Invalid or expired token" in exc_info.value.detail

@pytest.mark.unit
async def test_auth_missing_user_id(mock_redis, mock_db_pool):
    """Verify that a JWT payload missing user_id raises 401 Unauthorized."""
    payload = {"email": "test@echostack.io"}
    token = jwt.encode(payload, settings.SECRET_KEY or "secret", algorithm="HS256")
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user_context(credentials=creds)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert "user_id is missing" in exc_info.value.detail

@pytest.mark.unit
async def test_require_super_admin_success():
    """Verify require_super_admin accepts a context with role_id == 0."""
    admin_ctx = {
        "user_id": uuid.uuid4(),
        "role_id": 0,
        "permissions": {"is_super_admin": True}
    }
    result = await require_super_admin(user_context=admin_ctx)
    assert result == admin_ctx

@pytest.mark.unit
async def test_require_super_admin_forbidden():
    """Verify require_super_admin rejects non-admin users with 403 Forbidden."""
    user_ctx = {
        "user_id": uuid.uuid4(),
        "role_id": 1,
        "permissions": {"is_super_admin": False}
    }
    with pytest.raises(HTTPException) as exc_info:
        await require_super_admin(user_context=user_ctx)
        
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Super Admin privileges required" in exc_info.value.detail
