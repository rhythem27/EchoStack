import re
import uuid
import json
import logging
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.config import settings
from backend.db import get_db_pool
from backend.auth import get_redis_client, get_current_user_context

logger = logging.getLogger("users-api")

router = APIRouter(prefix="/api/users", tags=["Users & Auth"])

class UserRegisterSchema(BaseModel):
    full_name: str
    username: str
    email: str
    password: str

class UserLoginSchema(BaseModel):
    identifier: str  # Can be username or email
    password: str

class UserItem(BaseModel):
    id: str
    full_name: Optional[str] = ""
    username: Optional[str] = ""
    email: str
    role_id: int
    role_name: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserItem

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserRegisterSchema):
    """
    Registers a new user with full name, username, email, and password.
    Validation:
    - Username must be all lowercase with no spaces allowed.
    - Full Name must contain only letters and spaces (no symbols).
    - Uniqueness: If email or username already exists, returns error "user already exists".
    - Default Role: Assigned role_id = 3 ('standard').
    """
    full_name = payload.full_name.strip()
    username = payload.username.strip()
    email = payload.email.strip().lower()
    password = payload.password

    # 1. Validate username: all lowercase, no spaces allowed
    if username != username.lower() or " " in username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be all lowercase and contain no spaces."
        )
    if not re.match(r"^[a-z0-9_.-]+$", username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username contains invalid characters. Use lowercase letters, numbers, underscores, dots, or hyphens."
        )

    # 2. Validate full_name: letters and spaces only, no symbols
    if not re.match(r"^[A-Za-z\s]+$", full_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Full name can only contain letters and spaces (no symbols or numbers)."
        )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # 3. Uniqueness Check: email or username in DB
        existing_user = await conn.fetchrow(
            """
            SELECT id FROM users 
            WHERE LOWER(email) = $1 OR LOWER(username) = $2
            """,
            email, username.lower()
        )
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user already exists"
            )

        # 4. Hash password using bcrypt
        hashed_bytes = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        hashed_password = hashed_bytes.decode("utf-8")

        # 5. Insert new user with default standard role (role_id = 3)
        user_uuid = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO users (id, email, password_hash, role_id, full_name, username)
            VALUES ($1, $2, $3, 3, $4, $5)
            """,
            user_uuid, email, hashed_password, full_name, username
        )

        # 6. Seed initial profile & analytics rows
        await conn.execute(
            "INSERT INTO user_profiles (user_id, usage_tier) VALUES ($1, 'standard') ON CONFLICT DO NOTHING;",
            user_uuid
        )
        await conn.execute(
            "INSERT INTO user_analytics (user_id) VALUES ($1) ON CONFLICT DO NOTHING;",
            user_uuid
        )

        # 7. Fetch role_name for response
        role_row = await conn.fetchrow("SELECT role_name FROM roles WHERE id = 3")
        role_name = role_row["role_name"] if role_row else "standard"

    # 8. Generate JWT token
    jwt_payload = {
        "user_id": str(user_uuid),
        "email": email,
        "username": username,
        "role_id": 3
    }
    token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm="HS256")

    user_info = UserItem(
        id=str(user_uuid),
        full_name=full_name,
        username=username,
        email=email,
        role_id=3,
        role_name=role_name
    )

    logger.info(f"Successfully registered user '{username}' ({email}) with standard role.")
    return TokenResponse(access_token=token, user=user_info)


@router.post("/login", response_model=TokenResponse)
async def login_user(payload: UserLoginSchema):
    """
    Logs in a user via either username OR email with password verification.
    Caches user permissions in Redis on successful authentication.
    """
    identifier = payload.identifier.strip().lower()
    password = payload.password

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Query user by email OR username
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.full_name, u.username, u.password_hash, u.role_id, r.role_name, r.permissions
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE LOWER(u.email) = $1 OR LOWER(u.username) = $1
            """,
            identifier
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/username or password."
        )

    # Verify password hash
    stored_hash = row["password_hash"]
    if not stored_hash or not bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/username or password."
        )

    user_id_str = str(row["id"])
    role_id = row["role_id"]

    # Cache permissions in Redis
    redis_client = get_redis_client()
    cache_key = f"user_permissions:{user_id_str}"
    try:
        perms = row["permissions"]
        if isinstance(perms, str):
            perms = json.loads(perms)
        else:
            perms = dict(perms)

        cache_payload = {
            "role_id": role_id,
            "permissions": perms
        }
        await redis_client.setex(cache_key, 3600, json.dumps(cache_payload))
        logger.info(f"Cached Redis permissions for user {user_id_str}")
    except Exception as redis_err:
        logger.error(f"Failed caching Redis permissions during login: {redis_err}")

    # Generate JWT
    jwt_payload = {
        "user_id": user_id_str,
        "email": row["email"],
        "username": row["username"],
        "role_id": role_id
    }
    token = jwt.encode(jwt_payload, settings.SECRET_KEY, algorithm="HS256")

    user_info = UserItem(
        id=user_id_str,
        full_name=row["full_name"] or "",
        username=row["username"] or "",
        email=row["email"],
        role_id=role_id,
        role_name=row["role_name"]
    )

    return TokenResponse(access_token=token, user=user_info)


@router.get("/me", response_model=UserItem)
async def get_current_user_profile(user_context: dict = Depends(get_current_user_context)):
    """
    Returns the currently logged-in user profile details.
    """
    user_id = user_context["user_id"]
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.email, u.full_name, u.username, u.role_id, r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.id
            WHERE u.id = $1
            """,
            user_id
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found."
        )

    return UserItem(
        id=str(row["id"]),
        full_name=row["full_name"] or "",
        username=row["username"] or "",
        email=row["email"],
        role_id=row["role_id"],
        role_name=row["role_name"]
    )
