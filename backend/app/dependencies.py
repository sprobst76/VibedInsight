"""
FastAPI dependencies for authentication and authorization.

Usage:
    from app.dependencies import get_current_user, get_current_active_user

    @router.get("/protected")
    async def protected_route(user: User = Depends(get_current_active_user)):
        return {"user_id": user.id}
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.services.auth import decode_access_token, get_user_by_id

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
