from __future__ import annotations

import secrets
from typing import Any

from fastapi import Cookie, HTTPException, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import get_settings
from app.db import get_database


def _serializer() -> URLSafeTimedSerializer:
    settings = get_settings()
    return URLSafeTimedSerializer(settings.session_secret, salt="admin-session")


def create_session_token(admin_id: str) -> str:
    return _serializer().dumps({"admin_id": admin_id})


def read_session_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return _serializer().loads(token, max_age=settings.session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


async def get_current_admin(session: str | None = Cookie(default=None)) -> dict:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요해요.")
    data = read_session_token(session)
    if not data:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 만료됐어요.")
    db = get_database()
    admin = await db.admin_users.find_one({"_id": data["admin_id"]})
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 만료됐어요.")
    return admin


def generate_recovery_codes(count: int = 8) -> list[str]:
    return ["-".join([secrets.token_hex(2) for _ in range(3)]) for _ in range(count)]


def generate_device_code() -> str:
    alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "".join(secrets.choice(alphabet) for _ in range(6))


def hash_token(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()
