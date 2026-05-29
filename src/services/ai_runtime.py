from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from src.config import settings

ALLOWED_PROVIDERS = {"openai", "deepseek", "anthropic", "openai_compatible"}


def _runtime_path():
    return settings.data_path / "ai_runtime.json"


def _normalize_provider(provider: str | None) -> str:
    value = str(provider or "openai").strip().lower().replace("-", "_")
    return value if value in ALLOWED_PROVIDERS else "openai"


def _default_model_for_provider(provider: str) -> str:
    if provider == "deepseek":
        return settings.DEEPSEEK_MODEL
    if provider == "anthropic":
        return settings.ANTHROPIC_MODEL
    if provider == "openai_compatible":
        return settings.OPENAI_COMPATIBLE_MODEL or settings.DEFAULT_MODEL
    return settings.DEFAULT_MODEL


def _default_payload(provider: str | None = None) -> dict[str, Any]:
    p = _normalize_provider(provider or settings.AI_PROVIDER)
    model = _default_model_for_provider(p)
    return {
        "provider": p,
        "model": model,
        "radar_model": model,
        "private_model": model,
        "task_model": model,
        "chat_model": model,
        "vision_model": model,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _safe_read_json(path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _api_key_configured(provider: str) -> bool:
    return bool(settings.get_api_key_for_provider(provider))


def _provider_ready(provider: str) -> bool:
    if not _api_key_configured(provider):
        return False
    if provider == "openai_compatible" and not settings.OPENAI_COMPATIBLE_BASE_URL:
        return False
    return True


def get() -> dict[str, Any]:
    raw = _safe_read_json(_runtime_path())
    if not raw:
        return {}

    provider = _normalize_provider(raw.get("provider") or settings.AI_PROVIDER)
    defaults = _default_payload(provider)
    merged = {**defaults, **raw}
    merged["provider"] = provider
    return merged


def set_provider(provider: str, model: str | None = None) -> dict[str, Any]:
    p = _normalize_provider(provider)
    payload = _default_payload(p)

    if model:
        m = str(model).strip()
        if m:
            payload["model"] = m
            payload["radar_model"] = m
            payload["private_model"] = m
            payload["task_model"] = m
            payload["chat_model"] = m
            payload["vision_model"] = m

    settings.ensure_data_dir()
    path = _runtime_path()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def clear() -> dict[str, Any]:
    path = _runtime_path()
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass
    return {}


def effective_provider() -> str:
    runtime = get()
    if runtime.get("provider"):
        return _normalize_provider(runtime["provider"])
    return _normalize_provider(settings.AI_PROVIDER)


def effective_model_for_task(task: str) -> str:
    runtime = get()
    task_name = str(task or "").strip().lower()

    if runtime:
        if task_name == "radar" and runtime.get("radar_model"):
            return str(runtime["radar_model"])
        if task_name == "private" and runtime.get("private_model"):
            return str(runtime["private_model"])
        if task_name == "task" and runtime.get("task_model"):
            return str(runtime["task_model"])
        if task_name == "chat" and runtime.get("chat_model"):
            return str(runtime["chat_model"])
        if task_name == "vision" and runtime.get("vision_model"):
            return str(runtime["vision_model"])
        if runtime.get("model"):
            return str(runtime["model"])

    provider = effective_provider()
    if task_name == "vision":
        return settings.effective_vision_model
    if provider == settings.AI_PROVIDER:
        return settings.get_model_for_task(task_name)
    if task_name == "radar" and settings.RADAR_MODEL:
        return settings.RADAR_MODEL
    if task_name == "private" and settings.PRIVATE_MODEL:
        return settings.PRIVATE_MODEL
    if task_name == "task" and settings.TASK_MODEL:
        return settings.TASK_MODEL
    if task_name == "chat" and settings.CHAT_MODEL:
        return settings.CHAT_MODEL
    return _default_model_for_provider(provider)


def summary() -> dict[str, Any]:
    runtime = get()
    active = bool(runtime)
    provider = effective_provider()
    model = effective_model_for_task("chat")
    fallback_chain = settings.get_ai_provider_fallback_chain(provider)

    return {
        "runtime_override_active": active,
        "runtime": runtime,
        "provider": provider,
        "model": model,
        "default_provider": settings.AI_PROVIDER,
        "api_key_configured": _api_key_configured(provider),
        "provider_ready": _provider_ready(provider),
        "fallback_chain": fallback_chain,
    }
