from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import jwt

# Centralised application settings
from src.core.config import get_settings

# Load settings once (cached by lru_cache inside get_settings)
settings = get_settings()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ALGORITHM: str = settings.ALGORITHM
SECRET_KEY: str = settings.SECRET_KEY


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed JWT access token using the configured SECRET_KEY.

    Args:
        data: Arbitrary payload to embed inside the token. Typical fields include
              a subject identifier under the key "sub".
        expires_delta: Optional timedelta specifying token lifetime. Falls back
                        to the global ``ACCESS_TOKEN_EXPIRE_MINUTES`` setting.

    Returns:
        A JWT string signed with HMAC-SHA256 (or the algorithm configured via
        the ``ALGORITHM`` env variable).
    """

    to_encode = data.copy()
    if expires_delta is not None:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt 