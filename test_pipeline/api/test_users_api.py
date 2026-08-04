import pytest
from httpx import AsyncClient

@pytest.mark.api
async def test_register_user_invalid_username_format(async_client: AsyncClient):
    """Verify registration fails with 400 when username contains uppercase or spaces."""
    payload = {
        "full_name": "Test User",
        "username": "Invalid Username",
        "email": "test@echostack.io",
        "password": "Password123!"
    }
    response = await async_client.post("/api/users/register", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "Username must be all lowercase" in data["detail"]

@pytest.mark.api
async def test_register_user_invalid_fullname_format(async_client: AsyncClient):
    """Verify registration fails with 400 when full name contains symbols or digits."""
    payload = {
        "full_name": "Test User 123!",
        "username": "testuser",
        "email": "test@echostack.io",
        "password": "Password123!"
    }
    response = await async_client.post("/api/users/register", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert "Full name can only contain letters and spaces" in data["detail"]

@pytest.mark.api
async def test_get_current_user_unauthorized(async_client: AsyncClient):
    """Verify /api/users/me returns 403 Forbidden when no auth header is provided."""
    response = await async_client.get("/api/users/me")
    assert response.status_code in [401, 403]
