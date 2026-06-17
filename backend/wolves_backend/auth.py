from __future__ import annotations

import secrets
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request

if TYPE_CHECKING:
    from wolves_backend.config import Settings

FRONTEND_KEY_HEADER = "X-Wolves-Key"


def has_frontend_key(settings: Settings, request: Request) -> bool:
    """True when the shared frontend key matches, or no key is configured. An
    empty configured key leaves the gate open, the safe default for local dev."""
    if not settings.frontend_key:
        return True
    presented = request.headers.get(FRONTEND_KEY_HEADER, "")
    return secrets.compare_digest(presented.encode(), settings.frontend_key.encode())


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
