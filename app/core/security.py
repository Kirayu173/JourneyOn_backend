from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, cast

from passlib.context import CryptContext
from jose import JWTError, jwt

from app.core.config import settings

# Password hashing
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash plaintext password using bcrypt."""
    hashed = _pwd_context.hash(password)
    return cast(str, hashed)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored bcrypt hash."""
    try:
        return bool(_pwd_context.verify(plain_password, hashed_password))
    except Exception:
        return False


# JWT utilities
_ALGORITHM = "HS256"
_DEFAULT_EXPIRES_MINUTES = 60


def create_access_token(data: Dict[str, Any], expires_minutes: int = _DEFAULT_EXPIRES_MINUTES) -> str:
    """Create a JWT access token with an expiration."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=_ALGORITHM)
    return cast(str, token)


def verify_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token, returning its payload.

    Raises JWTError on invalid signature/expired token.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])
        return cast(Dict[str, Any], payload)
    except JWTError as e:
        # Bubble up to be handled by caller (e.g., dependency raising 401)
        raise