from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from wolves_backend.config import Settings


def is_admin(settings: Settings, request: Request) -> bool:
    """True when a bearer token matching ADMIN_TOKEN was presented. An empty
    configured token denies everything, the safe default."""
    if not settings.admin_token:
        return False
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return False
    return secrets.compare_digest(token.encode(), settings.admin_token.encode())


def require_admin(request: Request) -> None:
    settings = request.app.state.settings
    if is_admin(settings, request):
        return
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=401, detail="authentication required", headers={"WWW-Authenticate": "Bearer"}
        )
    raise HTTPException(status_code=403, detail="forbidden")
