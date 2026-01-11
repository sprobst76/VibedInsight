"""
Authentication service with security best practices.

Security measures:
- bcrypt for password hashing (resistant to rainbow tables, GPU attacks)
- JWT with short-lived access tokens + long-lived refresh tokens
- Refresh token rotation (new token issued on refresh)
- Token revocation support via database
- No sensitive data in JWT payload
- Recovery codes for account recovery (like 2FA backup codes)
- Vault key salt for client-side encryption
"""

import base64
import hashlib
import secrets
from datetime import datetime, timedelta

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import RefreshToken, User

# Password hashing context
# bcrypt with automatic salt, work factor auto-adjusts
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Characters for recovery codes (no ambiguous chars like 0/O, 1/I/L)
RECOVERY_CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def generate_vault_key_salt() -> str:
    """
    Generate a random salt for vault key derivation.

    The client uses this salt with the user's password to derive
    the vault encryption key via PBKDF2.
    """
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def generate_recovery_codes() -> tuple[list[str], list[str]]:
    """
    Generate 10 recovery codes.

    Returns:
        (plain_codes, hashed_codes)
        - plain_codes: Show to user ONCE, format XXXX-XXXX-XXXX
        - hashed_codes: Store in database (bcrypt hashed)
    """
    plain_codes = []
    hashed_codes = []

    for _ in range(10):
        # Generate code in format XXXX-XXXX-XXXX
        parts = []
        for _ in range(3):
            part = "".join(secrets.choice(RECOVERY_CODE_CHARS) for _ in range(4))
            parts.append(part)
        code = "-".join(parts)

        plain_codes.append(code)
        # Hash without dashes for verification
        hashed_codes.append(hash_recovery_code(code))

    return plain_codes, hashed_codes


def hash_recovery_code(code: str) -> str:
    """
    Hash a recovery code using bcrypt.

    We use bcrypt (slow) because recovery codes are user-typeable
    and could be brute-forced if we used fast hashing.
    """
    # Normalize: remove dashes, uppercase
    normalized = code.replace("-", "").upper()
    return pwd_context.hash(normalized)


def verify_recovery_code(plain_code: str, hashed_code: str) -> bool:
    """Verify a recovery code against its hash."""
    normalized = plain_code.replace("-", "").upper()
    return pwd_context.verify(normalized, hashed_code)


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    """
    Create a short-lived JWT access token.

    Contains only user_id - no sensitive data.
    Short expiry (default 30 min) limits damage if token is compromised.
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    expire = datetime.utcnow() + expires_delta
    to_encode = {
        "sub": str(user_id),
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token() -> str:
    """
    Create a cryptographically secure refresh token.

    This is NOT a JWT - it's a random string that we store hashed in the database.
    This allows us to revoke tokens and track sessions.
    """
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    """
    Hash a refresh token for storage.

    We use SHA-256 here (not bcrypt) because:
    - Refresh tokens are already high-entropy random strings
    - We need fast lookups in the database
    - bcrypt is overkill for random tokens
    """
    return hashlib.sha256(token.encode()).hexdigest()


def decode_access_token(token: str) -> dict | None:
    """
    Decode and validate a JWT access token.

    Returns the payload if valid, None if invalid/expired.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        # Verify this is an access token
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    """Get a user by email address."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """Get a user by ID."""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession, email: str, password: str
) -> tuple[User, list[str]]:
    """
    Create a new user with hashed password, vault key salt, and recovery codes.

    Email is normalized to lowercase to prevent duplicate accounts.

    Returns:
        (user, recovery_codes)
        - recovery_codes are plain text, must be shown to user ONCE
    """
    # Generate vault key salt and recovery codes
    vault_key_salt = generate_vault_key_salt()
    plain_codes, hashed_codes = generate_recovery_codes()

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        vault_key_salt=vault_key_salt,
        recovery_codes_hash=hashed_codes,
        recovery_codes_used=[False] * 10,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user, plain_codes


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User | None:
    """
    Authenticate a user by email and password.

    Returns the user if credentials are valid, None otherwise.
    Updates last_login timestamp on success.
    """
    user = await get_user_by_email(db, email)
    if user is None:
        # Still run password verification to prevent timing attacks
        pwd_context.dummy_verify()
        return None

    if not user.is_active:
        return None

    if not verify_password(password, user.password_hash):
        return None

    # Update last login
    user.last_login = datetime.utcnow()
    await db.commit()

    return user


async def store_refresh_token(
    db: AsyncSession,
    user_id: int,
    token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> RefreshToken:
    """
    Store a refresh token in the database.

    The token is hashed before storage for security.
    """
    expires_at = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)

    refresh_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_refresh_token(token),
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(refresh_token)
    await db.commit()
    return refresh_token


async def validate_refresh_token(db: AsyncSession, token: str) -> RefreshToken | None:
    """
    Validate a refresh token.

    Returns the token record if valid, None if invalid/expired/revoked.
    """
    token_hash = hash_refresh_token(token)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.is_revoked == False,  # noqa: E712
            RefreshToken.expires_at > datetime.utcnow(),
        )
    )
    return result.scalar_one_or_none()


async def revoke_refresh_token(db: AsyncSession, token: str) -> bool:
    """
    Revoke a refresh token (logout).

    Returns True if token was found and revoked.
    """
    token_record = await validate_refresh_token(db, token)
    if token_record is None:
        return False

    token_record.is_revoked = True
    token_record.revoked_at = datetime.utcnow()
    await db.commit()
    return True


async def revoke_all_user_tokens(db: AsyncSession, user_id: int) -> int:
    """
    Revoke all refresh tokens for a user (logout everywhere).

    Returns the number of tokens revoked.
    """
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    )
    tokens = result.scalars().all()

    count = 0
    for token in tokens:
        token.is_revoked = True
        token.revoked_at = datetime.utcnow()
        count += 1

    await db.commit()
    return count


async def cleanup_expired_tokens(db: AsyncSession) -> int:
    """
    Delete expired/revoked tokens from the database.

    Should be run periodically to keep the database clean.
    """
    result = await db.execute(
        select(RefreshToken).where(
            (RefreshToken.expires_at < datetime.utcnow())
            | (RefreshToken.is_revoked == True)  # noqa: E712
        )
    )
    tokens = result.scalars().all()

    count = len(tokens)
    for token in tokens:
        await db.delete(token)

    await db.commit()
    return count


async def change_password(
    db: AsyncSession, user: User, current_password: str, new_password: str
) -> str | None:
    """
    Change a user's password.

    Requires current password for verification.
    Generates a new vault key salt (client must re-encrypt vault entries).
    Revokes all refresh tokens after password change for security.

    Returns:
        New vault_key_salt if successful, None if current password incorrect
    """
    if not verify_password(current_password, user.password_hash):
        return None

    # Generate new vault key salt
    # IMPORTANT: Client must re-encrypt all vault entries with new key!
    new_salt = generate_vault_key_salt()

    user.password_hash = hash_password(new_password)
    user.vault_key_salt = new_salt

    # Revoke all tokens - force re-login everywhere
    await revoke_all_user_tokens(db, user.id)

    await db.commit()
    return new_salt


async def recover_account(
    db: AsyncSession, email: str, recovery_code: str, new_password: str
) -> tuple[User, str] | None:
    """
    Recover an account using a recovery code.

    This allows the user to set a new password without knowing the old one.
    The recovery code is marked as used after successful recovery.

    Returns:
        (user, new_vault_key_salt) if successful, None if failed

    IMPORTANT: Since the vault key is derived from password, the client
    cannot decrypt old vault entries after recovery (unless they have
    the old key cached). This is by design for maximum security.
    """
    user = await get_user_by_email(db, email)
    if user is None or not user.is_active:
        # Run dummy verification to prevent timing attacks
        pwd_context.dummy_verify()
        return None

    if not user.recovery_codes_hash or not user.recovery_codes_used:
        return None

    # Find matching unused recovery code
    code_index = None
    for i, (hashed, used) in enumerate(
        zip(user.recovery_codes_hash, user.recovery_codes_used)
    ):
        if not used and verify_recovery_code(recovery_code, hashed):
            code_index = i
            break

    if code_index is None:
        return None

    # Mark code as used
    used_list = list(user.recovery_codes_used)
    used_list[code_index] = True
    user.recovery_codes_used = used_list

    # Set new password and generate new vault key salt
    new_salt = generate_vault_key_salt()
    user.password_hash = hash_password(new_password)
    user.vault_key_salt = new_salt

    # Revoke all tokens
    await revoke_all_user_tokens(db, user.id)

    await db.commit()
    await db.refresh(user)

    return user, new_salt


async def delete_user_account(db: AsyncSession, user: User, password: str) -> bool:
    """
    Delete a user account and all associated data (GDPR compliance).

    Requires password confirmation for security.
    This is a hard delete - data cannot be recovered.
    """
    if not verify_password(password, user.password_hash):
        return False

    # Delete user (cascades to refresh_tokens and content_items)
    await db.delete(user)
    await db.commit()
    return True
