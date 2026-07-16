import os
import json
import uuid
import logging
import contextvars
from typing import Dict, Any, Optional
import jwt
import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from backend.config import settings
from backend.db import get_db_pool

logger = logging.getLogger("backend-auth")

# Context variables to hold user session info securely across async task chains
current_user_id: contextvars.ContextVar[Optional[uuid.UUID]] = contextvars.ContextVar("current_user_id", default=None)
current_user_permissions: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("current_user_permissions", default=None)

# Global Redis client
_redis_client: Optional[aioredis.Redis] = None

def get_redis_client() -> aioredis.Redis:
    """Retrieves or initializes the global asynchronous Redis client."""
    global _redis_client
    if _redis_client is None:
        logger.info(f"Initializing Redis client for URL: {settings.REDIS_URL}")
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client

async def get_current_user_context(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
) -> Dict[str, Any]:
    """
    FastAPI dependency that:
    1. Extracts and validates the JWT from Authorization header.
    2. Checks Redis for cached user role and permissions.
    3. Falls back to PostgreSQL if cache is missed, caching the result in Redis.
    4. Sets the contextvars for current_user_id and current_user_permissions.
    """
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        user_id_str = payload.get("user_id")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: user_id is missing."
            )
        user_uuid = uuid.UUID(user_id_str)
    except jwt.PyJWTError as jwt_err:
        logger.warning(f"JWT decoding failed: {jwt_err}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(jwt_err)}"
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: user_id is not a valid UUID."
        )

    redis_client = get_redis_client()
    cache_key = f"user_permissions:{user_id_str}"

    role_id = None
    permissions = None

    try:
        # Try fetching cached permissions
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            data = json.loads(cached_data)
            role_id = data.get("role_id")
            permissions = data.get("permissions")
            logger.debug(f"Permissions cache hit for user: {user_id_str}")
    except Exception as redis_err:
        logger.error(f"Redis operation failed: {redis_err}")
        # Continue to DB fallback if Redis is down

    if permissions is None:
        logger.info(f"Permissions cache miss for user: {user_id_str}. Querying PostgreSQL...")
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT u.role_id, r.permissions
                FROM users u
                JOIN roles r ON u.role_id = r.id
                WHERE u.id = $1
                """,
                user_uuid
            )
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="User or role not found in database."
                )
            
            role_id = row["role_id"]
            # Parse permissions JSON if it is stored as text, or use directly if parsed as dict by asyncpg
            raw_perms = row["permissions"]
            if isinstance(raw_perms, str):
                permissions = json.loads(raw_perms)
            else:
                permissions = dict(raw_perms)

        # Attempt to cache the retrieved permissions in Redis
        try:
            cache_payload = {
                "role_id": role_id,
                "permissions": permissions
            }
            await redis_client.setex(cache_key, 3600, json.dumps(cache_payload))
            logger.info(f"Cached permissions for user: {user_id_str} in Redis.")
        except Exception as redis_err:
            logger.error(f"Failed to save permissions to Redis: {redis_err}")

    # Set context variables for this task/request thread
    current_user_id.set(user_uuid)
    current_user_permissions.set(permissions)

    return {
        "user_id": user_uuid,
        "role_id": role_id,
        "permissions": permissions
    }
