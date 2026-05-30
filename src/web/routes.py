from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.config import settings
from src.web.auth import COOKIE_NAME, get_dashboard_token, require_dashboard_access

router = APIRouter()
templates = Jinja2Templates(directory="src/web/templates")

SENSITIVE_MARKERS = ("key", "token", "secret", "password")


def _json_path(name: str) -> Path:
    return settings.data_path / name


def _safe_json(path: Path, default: Any) -> tuple[Any, str | None, bool]:
    if not path.exists():
        return default, None, False
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception as error:  # noqa: BLE001
        return default, f"{path.name} could not be read: {error}", True
    return data, None, True


def _records(value: Any, id_key: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        rows = value.values()
    elif isinstance(value, list):
        rows = value
    else:
        rows = []

    normalized = []
    for item in rows:
        if isinstance(item, dict):
            copy = dict(item)
            if id_key not in copy and "id" in copy:
                copy[id_key] = copy["id"]
            normalized.append(copy)
    return normalized


def _sort_desc(items: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: str(item.get(field) or ""), reverse=True)


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(marker in key_text.lower() for marker in SENSITIVE_MARKERS):
                if isinstance(item, bool) or item is None:
                    safe[key_text] = item
                else:
                    safe[key_text] = "[hidden]"
                continue
            safe[key_text] = _sanitize(item)
        return safe
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _template_context(request: Request, **extra: Any) -> dict[str, Any]:
    access = extra.pop("access", None)
    warning = getattr(access, "warning", None)
    return {
        "request": request,
        "token_warning": warning,
        "path": request.url.path,
        **extra,
    }


def _access_or_redirect(request: Request):
    return require_dashboard_access(request)


@router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"ok": True, "service": "atrioly-dashboard", "version": "v4.0-alpha.1"})


@router.get("/login", response_class=HTMLResponse)
async def login(request: Request, token: str | None = None):
    expected = get_dashboard_token()
    if not expected:
        access = require_dashboard_access(request)
        return templates.TemplateResponse(
            "login.html",
            _template_context(
                request,
                access=access,
                error=None,
                token_configured=False,
            ),
        )

    if token is not None:
        if token == expected:
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax")
            return response
        return templates.TemplateResponse(
            "login.html",
            _template_context(request, error="Invalid dashboard token.", token_configured=True),
            status_code=401,
        )

    return templates.TemplateResponse(
        "login.html",
        _template_context(request, error=None, token_configured=True),
    )


@router.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(COOKIE_NAME)
    return response


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    access = _access_or_redirect(request)
    if isinstance(access, RedirectResponse):
        return access

    contacts_raw, contacts_warning, contacts_exists = _safe_json(_json_path("private_contacts.json"), {})
    threads_raw, threads_warning, threads_exists = _safe_json(_json_path("private_threads.json"), {})
    runtime_raw, runtime_warning, runtime_exists = _safe_json(_json_path("ai_runtime.json"), {})

    contacts = _records(contacts_raw, "user_id")
    threads = _records(threads_raw, "thread_id")
    open_threads = [item for item in threads if item.get("status") == "open"]
    resolved_threads = [item for item in threads if item.get("status") == "resolved"]

    warnings = [warning for warning in (contacts_warning, threads_warning, runtime_warning) if warning]
    return templates.TemplateResponse(
        "index.html",
        _template_context(
            request,
            access=access,
            data_dir=str(settings.data_path),
            contacts_count=len(contacts),
            open_threads_count=len(open_threads),
            resolved_threads_count=len(resolved_threads),
            total_threads_count=len(threads),
            runtime_exists=runtime_exists,
            runtime_provider=(runtime_raw or {}).get("provider") if isinstance(runtime_raw, dict) else None,
            file_status={
                "private_contacts.json": contacts_exists,
                "private_threads.json": threads_exists,
                "ai_runtime.json": runtime_exists,
            },
            warnings=warnings,
        ),
    )


@router.get("/inbox", response_class=HTMLResponse)
async def inbox(request: Request):
    access = _access_or_redirect(request)
    if isinstance(access, RedirectResponse):
        return access

    raw, warning, _exists = _safe_json(_json_path("private_threads.json"), {})
    threads = _sort_desc(_records(raw, "thread_id"), "updated_at")
    return templates.TemplateResponse(
        "inbox.html",
        _template_context(request, access=access, threads=threads, warnings=[warning] if warning else []),
    )


@router.get("/contacts", response_class=HTMLResponse)
async def contacts(request: Request):
    access = _access_or_redirect(request)
    if isinstance(access, RedirectResponse):
        return access

    raw, warning, _exists = _safe_json(_json_path("private_contacts.json"), {})
    contacts_data = _sort_desc(_records(raw, "user_id"), "last_seen")
    return templates.TemplateResponse(
        "contacts.html",
        _template_context(request, access=access, contacts=contacts_data, warnings=[warning] if warning else []),
    )


@router.get("/runtime", response_class=HTMLResponse)
async def runtime(request: Request):
    access = _access_or_redirect(request)
    if isinstance(access, RedirectResponse):
        return access

    raw, warning, exists = _safe_json(_json_path("ai_runtime.json"), {})
    runtime_json = _sanitize(raw if isinstance(raw, dict) else {})
    summary = _sanitize(settings.public_runtime_summary())
    ai = summary.get("ai", {}) if isinstance(summary.get("ai"), dict) else {}
    safe_config = {
        "provider": summary.get("provider"),
        "model": summary.get("model"),
        "ready_providers": ai.get("ready_providers"),
        "fallback_chain": ai.get("fallback_chain"),
        "data_dir": summary.get("data_dir"),
        "log_level": summary.get("log_level"),
        "owners_count": summary.get("owners"),
        "forward_targets_count": summary.get("forward_targets"),
        "heuristic_filter": summary.get("heuristic_filter"),
        "ai_filter": summary.get("ai_filter"),
    }

    return templates.TemplateResponse(
        "runtime.html",
        _template_context(
            request,
            access=access,
            runtime_exists=exists,
            runtime_json=runtime_json,
            runtime_json_pretty=json.dumps(runtime_json, ensure_ascii=False, indent=2),
            safe_config=safe_config,
            warnings=[warning] if warning else [],
        ),
    )
