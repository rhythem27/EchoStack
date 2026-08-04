import pytest
from httpx import AsyncClient

@pytest.mark.api
async def test_admin_list_users_forbidden_for_standard_user(async_client: AsyncClient, standard_user_token: str):
    """Verify standard users cannot access Super Admin endpoints (403 Forbidden)."""
    headers = {"Authorization": f"Bearer {standard_user_token}"}
    response = await async_client.get("/admin/users", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert "Super Admin privileges required" in data["detail"]

@pytest.mark.api
async def test_admin_list_users_success_for_super_admin(async_client: AsyncClient, super_admin_token: str):
    """Verify Super Admin user can access user management list."""
    headers = {"Authorization": f"Bearer {super_admin_token}"}
    response = await async_client.get("/admin/users", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0
    assert data[0]["role_id"] == 0
