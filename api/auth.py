"""Telegram WebApp initData + Login Widget verification, JWT sessions."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Optional
from urllib.parse import parse_qsl

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api import config

_bearer = HTTPBearer(auto_error=False)


def _secret_key() -> bytes:
    return hashlib.sha256(config.BOT_TOKEN.encode()).digest()


def validate_webapp_init_data(init_data: str, max_age_sec: int = 86400) -> dict[str, Any]:
    """Validate Telegram Mini App initData; return parsed fields including user."""
    if not config.BOT_TOKEN:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "BOT_TOKEN not configured")
    if not init_data or not init_data.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "initData required")

    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing hash")

    data_check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", config.BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid initData signature")

    auth_date = int(pairs.get("auth_date") or 0)
    if auth_date and time.time() - auth_date > max_age_sec:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "initData expired")

    user_raw = pairs.get("user")
    if not user_raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No user in initData")
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid user JSON") from e
    if not user.get("id"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid user id")
    return {"user": user, "raw": pairs}


def validate_login_widget(payload: dict[str, Any], max_age_sec: int = 86400) -> dict[str, Any]:
    """Validate Telegram Login Widget callback fields."""
    if not config.BOT_TOKEN:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "BOT_TOKEN not configured")

    data = {k: str(v) for k, v in payload.items() if v is not None and k != "hash"}
    received_hash = payload.get("hash")
    if not received_hash:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing hash")

    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hashlib.sha256(config.BOT_TOKEN.encode()).digest()
    calculated = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, str(received_hash)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid login signature")

    auth_date = int(data.get("auth_date") or 0)
    if auth_date and time.time() - auth_date > max_age_sec:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login data expired")

    user_id = data.get("id")
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing user id")
    return {
        "user": {
            "id": int(user_id),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
            "username": data.get("username"),
            "photo_url": data.get("photo_url"),
            "language_code": data.get("language_code"),
        }
    }


def issue_token(user: dict[str, Any]) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user["id"]),
        "username": user.get("username"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "photo_url": user.get("photo_url"),
        "iat": now,
        "exp": now + config.JWT_TTL_SEC,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired") from e
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from e


def sign_file_token(path: str, user_id: str, kind: str = "audio") -> str:
    now = int(time.time())
    payload = {
        "path": path,
        "uid": str(user_id),
        "kind": kind,
        "exp": now + config.FILE_URL_TTL_SEC,
        "iat": now,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")


def decode_file_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError as e:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired file link") from e


async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict[str, Any]:
    if not creds or not creds.credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authorization required")
    claims = decode_token(creds.credentials)
    return {
        "id": str(claims["sub"]),
        "username": claims.get("username"),
        "first_name": claims.get("first_name"),
        "last_name": claims.get("last_name"),
        "photo_url": claims.get("photo_url"),
        "is_admin": bool(config.ADMIN_ID) and str(claims["sub"]) == str(config.ADMIN_ID),
    }


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
