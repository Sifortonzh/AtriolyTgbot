from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import RedirectResponse

COOKIE_NAME = "atrioly_dashboard_token"
TOKEN_WARNING = "Dashboard token is not configured. Do not expose this service publicly."


@dataclass(frozen=True)
class DashboardAccess:
    unlocked: bool
    token_configured: bool
    warning: str | None = None


def get_dashboard_token() -> str | None:
    token = os.getenv("DASHBOARD_TOKEN", "").strip()
    return token or None


def is_dashboard_unlocked(request: Request) -> bool:
    token = get_dashboard_token()
    if not token:
        return True
    return request.cookies.get(COOKIE_NAME) == token


def require_dashboard_access(request: Request) -> DashboardAccess | RedirectResponse:
    token = get_dashboard_token()
    if not token:
        return DashboardAccess(unlocked=True, token_configured=False, warning=TOKEN_WARNING)
    if is_dashboard_unlocked(request):
        return DashboardAccess(unlocked=True, token_configured=True)
    return RedirectResponse(url="/login", status_code=303)
