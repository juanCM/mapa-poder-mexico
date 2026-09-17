from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, status

from .settings import get_settings


def require_admin(authorization: Optional[str] = Header(default=None)) -> str:
    expected = get_settings().admin_api_token
    if not expected and get_settings().environment == "development":
        return "development-admin"
    if not authorization or authorization != f"Bearer {expected}":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin authentication required")
    return "configured-admin"
