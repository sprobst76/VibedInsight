"""
FastAPI dependencies for authentication and authorization.

Usage:
    from app.dependencies import get_current_user, get_current_active_user

    @router.get("/protected")
    async def protected_route(user: User = Depends(get_current_active_user)):
        return {"user_id": user.id}

For development (no auth required):
    from app.dependencies import get_dev_or_current_user

    @router.get("/items")
    async def list_items(user: User = Depends(get_dev_or_current_user)):
        # Uses dev user if no token provided
        return user.items
"""

import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth import decode_access_token, get_user_by_id

logger = logging.getLogger(__name__)

# Security scheme for Swagger UI
# Uses Bearer token authentication
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current authenticated user from the JWT token.

    Raises HTTPException 401 if:
    - No token provided
    - Token is invalid or expired
    - User not found

    Usage:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_user)):
            return user
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        raise credentials_exception

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        user_id = int(user_id)
    except ValueError:
        raise credentials_exception

    user = await get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get the current user and verify they are active.

    Raises HTTPException 403 if user is deactivated.

    Usage:
        @router.get("/me")
        async def get_me(user: User = Depends(get_current_active_user)):
            return user
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    Get the current user if authenticated, None otherwise.

    Useful for endpoints that work both with and without authentication.

    Usage:
        @router.get("/items")
        async def list_items(user: User | None = Depends(get_optional_user)):
            if user:
                # Return user's items
            else:
                # Return public items
    """
    if credentials is None:
        return None

    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    try:
        user_id = int(user_id)
    except ValueError:
        return None

    return await get_user_by_id(db, user_id)


# Development user email - used when no auth token provided
DEV_USER_EMAIL = "dev@vibedinsight.local"


async def get_or_create_dev_user(db: AsyncSession) -> User:
    """
    Get or create a development user.

    This user is used when no auth token is provided, allowing
    the app to work without authentication during development.
    """
    from app.services.auth import hash_password

    # Try to find existing dev user
    result = await db.execute(select(User).where(User.email == DEV_USER_EMAIL))
    user = result.scalar_one_or_none()

    if user:
        return user

    # Create dev user
    logger.info(f"Creating development user: {DEV_USER_EMAIL}")
    user = User(
        email=DEV_USER_EMAIL,
        password_hash=hash_password("devpassword123"),
        vault_key_salt="dev_salt_not_secure_for_production",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


async def get_dev_or_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Get the current user if authenticated, otherwise return dev user.

    This is a development convenience - allows the app to work without
    authentication while still supporting auth when tokens are provided.

    In production, you should use get_current_active_user instead.

    Usage:
        @router.get("/items")
        async def list_items(user: User = Depends(get_dev_or_current_user)):
            return user.items
    """
    # If token provided, try to authenticate
    if credentials is not None:
        token = credentials.credentials
        payload = decode_access_token(token)

        if payload is not None:
            user_id = payload.get("sub")
            if user_id is not None:
                try:
                    user_id = int(user_id)
                    user = await get_user_by_id(db, user_id)
                    if user and user.is_active:
                        return user
                except ValueError:
                    pass

    # No valid token - return dev user
    return await get_or_create_dev_user(db)
