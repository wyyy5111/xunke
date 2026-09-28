"""密码哈希与 JWT 工具。"""
from __future__ import annotations
import base64
import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
import bcrypt

from app.core.config import settings

PBKDF2_ROUNDS = 600_000
PBKDF2_SALT_BYTES = 16


def _ab64_encode(data: bytes) -> str:
    return base64.b64encode(data).rstrip(b"=").replace(b"+", b".").decode("ascii")


def _ab64_decode(value: str) -> bytes:
    raw = value.encode("ascii").replace(b".", b"+")
    raw += b"=" * (-len(raw) % 4)
    return base64.b64decode(raw, validate=True)


def hash_password(raw: str, rounds: int | None = None) -> str:
    rounds = int(rounds or PBKDF2_ROUNDS)
    if not 10_000 <= rounds <= 2_000_000:
        raise ValueError("PBKDF2 rounds 超出安全范围")
    salt = os.urandom(PBKDF2_SALT_BYTES)
    checksum = hashlib.pbkdf2_hmac(
        "sha256", raw.encode("utf-8"), salt, rounds, dklen=32
    )
    return (
        f"$pbkdf2-sha256${rounds}$"
        f"{_ab64_encode(salt)}${_ab64_encode(checksum)}"
    )


def verify_password(raw: str, hashed: str) -> bool:
    try:
        if hashed.startswith("$pbkdf2-sha256$"):
            parts = hashed.split("$")
            if len(parts) != 5:
                return False
            rounds = int(parts[2])
            if not 1_000 <= rounds <= 2_000_000:
                return False
            salt = _ab64_decode(parts[3])
            expected = _ab64_decode(parts[4])
            actual = hashlib.pbkdf2_hmac(
                "sha256", raw.encode("utf-8"), salt, rounds, dklen=len(expected)
            )
            return hmac.compare_digest(actual, expected)
        if hashed.startswith(("$2a$", "$2b$", "$2y$")):
            return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("ascii"))
        return False
    except (ValueError, TypeError, UnicodeError):
        return False


def password_needs_rehash(hashed: str) -> bool:
    """Return whether a valid legacy password hash should be upgraded on login."""
    try:
        if hashed.startswith("$pbkdf2-sha256$"):
            parts = hashed.split("$")
            return len(parts) != 5 or int(parts[2]) < PBKDF2_ROUNDS
        # Existing bcrypt rows remain verifiable, but successful authentication
        # migrates them to the single current PBKDF2 policy.
        return hashed.startswith(("$2a$", "$2b$", "$2y$"))
    except (TypeError, ValueError):
        return True


def create_access_token(subject: str | int, extra: Optional[dict[str, Any]] = None) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    # Standard claims are written last so a caller cannot override token
    # lifetime, audience, issuer, or subject through ``extra``.
    payload: dict[str, Any] = dict(extra or {})
    payload.update({
        "sub": str(subject),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": expire,
        "jti": uuid.uuid4().hex,
    })
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict[str, Any]]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=["HS256"],
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            options={"require": ["sub", "iss", "aud", "exp", "iat", "nbf", "jti"]},
        )
        if not str(payload.get("sub") or "").isdigit():
            return None
        return payload
    except (jwt.PyJWTError, TypeError, ValueError):
        return None
