import json
import uuid
import pytest
from unittest.mock import patch, AsyncMock
from backend.agent import format_dual_payload, query_user_analytics, current_user_id, current_user_permissions

@pytest.mark.integration
def test_format_dual_payload():
    """Verify format_dual_payload returns structured voice + ui_card JSON."""
    voice_msg = "Here are your analytics summary."
    comp_name = "AnalyticsMetricsCard"
    data_payload = {"total_interactions": 42, "top_topics": ["RAG", "LLM"]}

    raw_json = format_dual_payload(voice_msg, comp_name, data_payload)
    parsed = json.loads(raw_json)

    assert parsed["voice_text"] == voice_msg
    assert parsed["ui_card"]["component"] == comp_name
    assert parsed["ui_card"]["data"] == data_payload

@pytest.mark.integration
async def test_query_user_analytics_rbac_denied():
    """Verify tool returns Authorization Failure when user lacks can_query_analytics permission."""
    test_user = uuid.uuid4()
    token_id = current_user_id.set(test_user)
    token_perms = current_user_permissions.set({"can_query_analytics": False})

    try:
        res = await query_user_analytics.ainvoke({})
        assert "Authorization Failure" in res
    finally:
        current_user_id.reset(token_id)
        current_user_permissions.reset(token_perms)

@pytest.mark.integration
async def test_query_user_analytics_no_user_context():
    """Verify tool returns error when user_id context variable is None."""
    token_id = current_user_id.set(None)
    token_perms = current_user_permissions.set(None)

    try:
        res = await query_user_analytics.ainvoke({})
        assert "Authorization Failure" in res or "User context is missing" in res
    finally:
        current_user_id.reset(token_id)
        current_user_permissions.reset(token_perms)
