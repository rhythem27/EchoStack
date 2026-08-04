import pytest
from httpx import AsyncClient

@pytest.mark.api
async def test_get_card_templates_unauthorized(async_client: AsyncClient):
    """Verify card templates endpoint requires authorization."""
    response = await async_client.get("/api/cards/templates")
    assert response.status_code in [401, 403]

@pytest.mark.api
async def test_get_card_templates_authorized(async_client: AsyncClient, standard_user_token: str):
    """Verify card templates endpoint returns supported dynamic UI card definitions."""
    headers = {"Authorization": f"Bearer {standard_user_token}"}
    response = await async_client.get("/api/cards/templates", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "AnalyticsMetricsCard" in data["schemas"]
    assert "DocumentSearchCard" in data["schemas"]
    assert "PythonResultCard" in data["schemas"]

@pytest.mark.api
async def test_get_specific_card_schema_success(async_client: AsyncClient, standard_user_token: str):
    """Verify card schema for AnalyticsMetricsCard component."""
    headers = {"Authorization": f"Bearer {standard_user_token}"}
    response = await async_client.get("/api/cards/schemas/AnalyticsMetricsCard", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["component"] == "AnalyticsMetricsCard"
    assert "properties" in data["schema"]

@pytest.mark.api
async def test_get_specific_card_schema_not_found(async_client: AsyncClient, standard_user_token: str):
    """Verify 404 returned for unknown dynamic card component."""
    headers = {"Authorization": f"Bearer {standard_user_token}"}
    response = await async_client.get("/api/cards/schemas/NonExistentCardComponent", headers=headers)
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"]
