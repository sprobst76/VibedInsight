"""
Authentication router with security best practices.

Endpoints:
- POST /register - Create new account (returns recovery codes!)
- POST /login - Get access + refresh tokens + vault_key_salt
- POST /refresh - Get new access token
- POST /logout - Revoke refresh token
- POST /logout-all - Revoke all sessions
- GET /me - Get current user info
- PUT /password - Change password
- POST /recover - Recover account with recovery code
- DELETE /account - Delete account (GDPR)
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_active_user
from app.models.user import User
from app.schemas import (
    AccountDeleteRequest,
    LoginResponse,
    MessageResponse,
    PasswordChangeRequest,
    RecoveryRequest,
    RecoveryResponse,
    RefreshTokenRequest,
    RegistrationResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth import (
    authenticate_user,
    change_password,
    create_access_token,
    create_refresh_token,
    create_user,
    delete_user_account,
    get_user_by_email,
    get_user_by_id,
    recover_account,
    revoke_all_user_tokens,
    revoke_refresh_token,
    store_refresh_token,
    validate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _get_client_info(request: Request) -> tuple[str | None, str | None]:
    """Extract client info from request for token tracking."""
    user_agent = request.headers.get("User-Agent")
    # Get real IP, considering reverse proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip_address = forwarded.split(",")[0].strip()
    else:
        ip_address = request.client.host if request.client else None
    return user_agent, ip_address


@router.post(
    "/register", response_model=RegistrationResponse, status_code=status.HTTP_201_CREATED
)
async def register(
    data: UserRegister,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Register a new user account.

    Returns:
    - user: Basic user info
    - tokens: Access and refresh tokens
    - vault_key_salt: Salt for deriving vault encryption key
    - recovery_codes: 10 codes for account recovery (SAVE THESE!)

    IMPORTANT: Recovery codes are shown ONCE and never again!
    The user MUST save them securely.
    """
    # Check if user already exists
    existing = await get_user_by_email(db, data.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Validate password length (schema also validates, but double-check)
    if len(data.password) < settings.min_password_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    user, recovery_codes = await create_user(db, data.email, data.password)

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()

    # Store refresh token
    user_agent, ip_address = _get_client_info(request)
    await store_refresh_token(db, user.id, refresh_token, user_agent, ip_address)

    return RegistrationResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        ),
        vault_key_salt=user.vault_key_salt,
        recovery_codes=recovery_codes,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    data: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Login with email and password.

    Returns:
    - user: Basic user info
    - tokens: Access and refresh tokens
    - vault_key_salt: Salt for deriving vault encryption key
    """
    user = await authenticate_user(db, data.email, data.password)
    if user is None:
        # Generic message to prevent email enumeration
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create tokens
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token()

    # Store refresh token
    user_agent, ip_address = _get_client_info(request)
    await store_refresh_token(db, user.id, refresh_token, user_agent, ip_address)

    return LoginResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        ),
        vault_key_salt=user.vault_key_salt,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    data: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Get a new access token using a refresh token.

    The old refresh token is revoked and a new one is issued.
    This is "refresh token rotation" - enhances security.
    """
    # Validate the refresh token
    token_record = await validate_refresh_token(db, data.refresh_token)
    if token_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Get the user
    user = await get_user_by_id(db, token_record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Revoke the old refresh token
    await revoke_refresh_token(db, data.refresh_token)

    # Create new tokens
    access_token = create_access_token(user.id)
    new_refresh_token = create_refresh_token()

    # Store new refresh token
    user_agent, ip_address = _get_client_info(request)
    await store_refresh_token(db, user.id, new_refresh_token, user_agent, ip_address)

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
        "expires_in": settings.jwt_access_token_expire_minutes * 60,
    }


@router.post("/logout", response_model=MessageResponse)
async def logout(
    data: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Logout by revoking the refresh token.

    The access token will remain valid until it expires (short time).
    For immediate invalidation, keep access tokens short-lived.
    """
    success = await revoke_refresh_token(db, data.refresh_token)
    if not success:
        # Don't reveal if token existed - just acknowledge
        pass

    return {"message": "Logged out successfully"}


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Logout from all devices by revoking all refresh tokens.

    Requires authentication.
    Useful if user suspects account compromise.
    """
    count = await revoke_all_user_tokens(db, user.id)
    return {"message": f"Logged out from {count} session(s)"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_active_user),
) -> User:
    """
    Get current user information.

    Requires authentication.
    """
    return user


@router.put("/password")
async def update_password(
    data: PasswordChangeRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Change the current user's password.

    Requires current password for verification.
    All sessions (refresh tokens) are revoked after password change.

    Returns the new vault_key_salt - client must re-encrypt all vault entries!
    """
    new_salt = await change_password(db, user, data.current_password, data.new_password)
    if new_salt is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    return {
        "message": "Password changed successfully. Please login again.",
        "vault_key_salt": new_salt,
    }


@router.post("/recover", response_model=RecoveryResponse)
async def recover_with_code(
    data: RecoveryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Recover account using a recovery code.

    This allows setting a new password without knowing the old one.
    Each recovery code can only be used once.

    WARNING: Old vault entries cannot be decrypted after recovery
    (unless the client has cached the old vault key).
    """
    result = await recover_account(db, data.email, data.recovery_code, data.new_password)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or recovery code",
        )

    _, new_salt = result

    return RecoveryResponse(
        message="Account recovered successfully. Old vault entries may be unreadable.",
        vault_key_salt=new_salt,
    )


@router.delete("/account", response_model=MessageResponse)
async def delete_account(
    data: AccountDeleteRequest,
    user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete the user account and all associated data.

    GDPR compliance: Complete removal of all user data.
    This action is IRREVERSIBLE.

    Requires:
    - Password confirmation
    - confirm=true in request body
    """
    if not data.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please confirm deletion by setting confirm=true",
        )

    success = await delete_user_account(db, user, data.password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is incorrect",
        )

    return {"message": "Account and all data deleted successfully"}
