from __future__ import annotations

from fastapi import HTTPException, Request


def require_admin(request: Request) -> None:
    """Placeholder until real auth lands: deny everything unless the dev
    bypass flag is set, and never honour the flag in production."""
    settings = request.app.state.settings
    if settings.environment != "production" and settings.admin_dev_bypass:
        return
    raise HTTPException(status_code=403, detail="forbidden")
