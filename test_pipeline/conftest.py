import os
import sys
import uuid
import json
import asyncio
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import jwt
from httpx import AsyncClient, ASGITransport

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import settings
from backend.main import app

# Register custom failure logger plugin automatically
pytest_plugins = ["test_pipeline.logging_plugin"]


class MockRedis:
    """In-memory Async Redis Mock for testing authorization cache and fast operations."""
    def __init__(self):
        self._store: Dict[str, str] = {}

    async def get(self, key: str):
        return self._store.get(key)

    async def set(self, key: str, value: str):
        self._store[key] = value
        return True

    async def setex(self, key: str, time: int, value: str):
        self._store[key] = value
        return True

    async def delete(self, key: str):
        self._store.pop(key, None)
        return True

    async def ping(self):
        return True


class MockAsyncpgConnection:
    """Mock asyncpg connection returning predefined fixture rows for database queries."""
    async def fetchrow(self, query: str, *args):
        # Handle user context lookup by user UUID
        if "FROM users" in query or "users u" in query:
            user_uuid = args[0] if args else uuid.uuid4()
            admin_id_str = settings.SUPER_ADMIN_ID
            try:
                admin_uuid = uuid.UUID(admin_id_str)
            except ValueError:
                admin_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, admin_id_str)

            if str(user_uuid) == str(admin_uuid):
                return {
                    "id": user_uuid,
                    "email": "super_admin@echostack.io",
                    "full_name": "Echo Admin",
                    "username": "echo_admin",
                    "role_id": 0,
                    "role_name": "super_admin",
                    "permissions": json.dumps({
                        "is_super_admin": True,
                        "can_manage_users": True,
                        "can_access_admin_tools": True,
                        "can_query_analytics": True,
                        "can_write_knowledge": True,
                        "can_chat_live": True
                    })
                }
            else:
                return {
                    "id": user_uuid,
                    "email": "user@echostack.io",
                    "full_name": "Standard User",
                    "username": "std_user",
                    "role_id": 1,
                    "role_name": "user",
                    "permissions": json.dumps({
                        "is_super_admin": False,
                        "can_chat": True
                    })
                }
        return None

    async def fetch(self, query: str, *args):
        if "FROM users" in query or "users u" in query:
            return [
                {
                    "id": uuid.uuid4(),
                    "email": "super_admin@echostack.io",
                    "full_name": "Echo Admin",
                    "username": "echo_admin",
                    "role_id": 0,
                    "role_name": "super_admin",
                    "permissions": {"is_super_admin": True},
                    "created_at": None
                },
                {
                    "id": uuid.uuid4(),
                    "email": "user@echostack.io",
                    "full_name": "Standard User",
                    "username": "std_user",
                    "role_id": 1,
                    "role_name": "user",
                    "permissions": {"can_chat": True},
                    "created_at": None
                }
            ]
        if "FROM roles" in query:
            return [
                {"id": 0, "role_name": "super_admin", "permissions": {"is_super_admin": True}},
                {"id": 1, "role_name": "user", "permissions": {"can_chat": True}}
            ]
        return []

    async def execute(self, query: str, *args):
        return "EXECUTE 1"

    async def fetchval(self, query: str, *args):
        return 1


class MockAsyncpgPool:
    """Mock asyncpg connection pool."""
    def acquire(self):
        return self

    async def __aenter__(self):
        return MockAsyncpgConnection()

    async def __aexit__(self, exc_type, exc, tb):
        pass


@pytest.fixture(scope="session")
def mock_redis():
    return MockRedis()


@pytest.fixture(scope="session")
def mock_db_pool():
    return MockAsyncpgPool()


@pytest.fixture(autouse=True)
def global_mocks(mock_redis, mock_db_pool):
    """Globally patch get_db_pool and get_redis_client for all tests."""
    with patch("backend.db.get_db_pool", AsyncMock(return_value=mock_db_pool)), \
         patch("backend.auth.get_db_pool", AsyncMock(return_value=mock_db_pool)), \
         patch("backend.auth.get_redis_client", return_value=mock_redis), \
         patch("backend.websocket.get_db_pool", AsyncMock(return_value=mock_db_pool)), \
         patch("backend.websocket.get_redis_client", return_value=mock_redis), \
         patch("backend.api.super_admin.get_db_pool", AsyncMock(return_value=mock_db_pool)), \
         patch("backend.api.users.get_db_pool", AsyncMock(return_value=mock_db_pool)), \
         patch("backend.api.users.get_redis_client", return_value=mock_redis), \
         patch("backend.agent.get_db_pool", AsyncMock(return_value=mock_db_pool)):
        yield


@pytest.fixture
def super_admin_token() -> str:
    """Generates a valid JWT token for a Super Admin user."""
    admin_id = settings.SUPER_ADMIN_ID
    try:
        admin_uuid = str(uuid.UUID(admin_id))
    except ValueError:
        admin_uuid = str(uuid.uuid5(uuid.NAMESPACE_DNS, admin_id))

    payload = {
        "user_id": admin_uuid,
        "email": settings.SUPER_ADMIN_EMAIL or "admin@echostack.io",
        "role_id": 0
    }
    return jwt.encode(payload, settings.SECRET_KEY or "test_secret_key", algorithm="HS256")


@pytest.fixture
def standard_user_token() -> str:
    """Generates a valid JWT token for a regular non-admin user."""
    user_uuid = str(uuid.uuid4())
    payload = {
        "user_id": user_uuid,
        "email": "user@echostack.io",
        "role_id": 1
    }
    return jwt.encode(payload, settings.SECRET_KEY or "test_secret_key", algorithm="HS256")


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """
    HTTP AsyncClient fixture configured for API testing.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
