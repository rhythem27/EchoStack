import uuid
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.db import get_db_pool
from backend.auth import require_super_admin, get_redis_client

logger = logging.getLogger("super-admin-api")

router = APIRouter(prefix="/admin", tags=["Super Admin"])

class RoleUpdateSchema(BaseModel):
    role_id: int

class UserItemResponse(BaseModel):
    id: str
    email: str
    role_id: int
    role_name: str
    permissions: Dict[str, Any]
    created_at: str

@router.get("/users", response_model=List[UserItemResponse])
async def list_all_users(
    admin_context: Dict[str, Any] = Depends(require_super_admin)
):
    """
    Super Admin endpoint to list all registered users, their assigned roles, and permission scopes.
    Requires Role ID: 0 (Super Admin).
    """
    logger.info(f"Super Admin user {admin_context['user_id']} requesting user management list.")
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT 
                u.id, 
                u.email, 
                u.role_id, 
                r.role_name, 
                r.permissions, 
                u.created_at
            FROM users u
            JOIN roles r ON u.role_id = r.id
            ORDER BY u.created_at DESC
            """
        )
    
    users = []
    for row in rows:
        perms = row["permissions"]
        if isinstance(perms, str):
            import json
            perms = json.loads(perms)
        else:
            perms = dict(perms)
            
        users.append(
            UserItemResponse(
                id=str(row["id"]),
                email=row["email"],
                role_id=row["role_id"],
                role_name=row["role_name"],
                permissions=perms,
                created_at=row["created_at"].isoformat() if row["created_at"] else ""
            )
        )
    return users

@router.put("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    payload: RoleUpdateSchema,
    admin_context: Dict[str, Any] = Depends(require_super_admin)
):
    """
    Super Admin endpoint to assign or modify a target user's role_id.
    Immediately updates PostgreSQL and purges the target user's Redis permissions cache.
    """
    try:
        target_uuid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid user_id format: '{user_id}' is not a valid UUID."
        )

    # Validate target role existence
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        role_row = await conn.fetchrow("SELECT id, role_name FROM roles WHERE id = $1", payload.role_id)
        if not role_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Target role_id {payload.role_id} does not exist."
            )
        
        # Update user in PostgreSQL
        update_result = await conn.fetchrow(
            """
            UPDATE users 
            SET role_id = $1 
            WHERE id = $2 
            RETURNING id, email, role_id
            """,
            payload.role_id,
            target_uuid
        )
        if not update_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID '{user_id}' not found."
            )

    # Instant Redis Cache Invalidation
    redis_client = get_redis_client()
    cache_key = f"user_permissions:{user_id}"
    try:
        await redis_client.delete(cache_key)
        logger.info(f"Invalidated Redis permissions cache for user: {user_id}")
    except Exception as redis_err:
        logger.error(f"Failed to invalidate Redis cache for {user_id}: {redis_err}")

    return {
        "status": "success",
        "message": f"Updated user {update_result['email']} to role '{role_row['role_name']}' (ID: {payload.role_id}).",
        "user_id": str(update_result["id"]),
        "email": update_result["email"],
        "new_role_id": update_result["role_id"],
        "cache_invalidated": True
    }
