import pytest
import jwt
from backend.config import settings
from backend.websocket import authenticate_websocket, TOOL_PRIORITY

@pytest.mark.websocket
def test_websocket_tool_priority_configuration():
    """Verify WebSocket tool priority setup includes core EchoStack capabilities."""
    assert "rag_knowledge_search" in TOOL_PRIORITY
    assert "query_user_analytics" in TOOL_PRIORITY
    assert "python_code_interpreter" in TOOL_PRIORITY
    assert TOOL_PRIORITY["query_user_analytics"] == "WHEN_IDLE"

@pytest.mark.websocket
async def test_authenticate_websocket_missing_token():
    """Verify authenticate_websocket raises ValueError on empty token."""
    with pytest.raises(ValueError) as exc_info:
        await authenticate_websocket("")
    assert "Authentication token is missing" in str(exc_info.value)

@pytest.mark.websocket
async def test_authenticate_websocket_invalid_jwt():
    """Verify authenticate_websocket raises ValueError on corrupted token."""
    with pytest.raises(ValueError) as exc_info:
        await authenticate_websocket("corrupted_jwt_token_string")
    assert "Invalid or expired token" in str(exc_info.value)

@pytest.mark.websocket
async def test_authenticate_websocket_valid_token(mock_redis, mock_db_pool):
    """Verify authenticate_websocket resolves user context for valid token."""
    payload = {
        "user_id": settings.SUPER_ADMIN_ID if settings.SUPER_ADMIN_ID else "00000000-0000-0000-0000-000000000000",
        "role_id": 0
    }
    # Ensure user_id is a valid UUID
    import uuid
    try:
        uuid.UUID(payload["user_id"])
    except ValueError:
        payload["user_id"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, payload["user_id"]))

    valid_token = jwt.encode(payload, settings.SECRET_KEY or "secret", algorithm="HS256")
    ctx = await authenticate_websocket(valid_token)
    
    assert ctx["role_id"] == 0
    assert str(ctx["user_id"]) == payload["user_id"]
