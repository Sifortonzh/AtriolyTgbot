from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

log = logging.getLogger(__name__)

THREADS_FILE: Path = settings.data_path / "private_threads.json"
MAX_THREADS = 300


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate(value: Any, limit: int = 800) -> str:
    return str(value or "")[:limit]


class PrivateThreads:
    def __init__(self, path: Path = THREADS_FILE):
        self.path = path

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as error:  # noqa: BLE001
            log.warning("Failed to load private threads from %s: %s", self.path, error)
            return {}

        if isinstance(data, dict):
            return {str(key): value for key, value in data.items() if isinstance(value, dict)}
        if isinstance(data, list):
            return {
                str(item["thread_id"]): item
                for item in data
                if isinstance(item, dict) and item.get("thread_id")
            }
        log.warning("Private threads file %s has unexpected shape; starting empty.", self.path)
        return {}

    def _save(self, threads: dict[str, dict[str, Any]]) -> None:
        ordered = sorted(threads.values(), key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        trimmed = {str(item["thread_id"]): item for item in ordered[:MAX_THREADS] if item.get("thread_id")}

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(trimmed, handle, ensure_ascii=False, indent=2)
        except Exception as error:  # noqa: BLE001
            log.error("Failed to save private threads to %s: %s", self.path, error, exc_info=error)

    def add_or_update(
        self,
        *,
        user_id: int,
        user_name: str,
        username: str | None,
        category: str,
        priority: str,
        summary: str,
        message_preview: str,
        owner_message_id: int,
        user_message_id: int,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        threads = self._load()
        resolved_existing = None
        for item in threads.values():
            if item.get("user_id") == user_id and item.get("status") == "open":
                resolved_existing = item
                break

        target_thread_id = thread_id or (resolved_existing or {}).get("thread_id") or f"private_{user_id}_{owner_message_id}"
        now = _now_iso()
        record = threads.get(str(target_thread_id)) or resolved_existing or {
            "thread_id": target_thread_id,
            "user_id": user_id,
            "user_name": user_name,
            "username": username,
            "status": "open",
            "category": category,
            "priority": priority,
            "summary": _truncate(summary),
            "message_preview": _truncate(message_preview),
            "owner_message_id": owner_message_id,
            "user_message_id": user_message_id,
            "created_at": now,
            "updated_at": now,
            "resolved_at": None,
        }

        record.update(
            {
                "user_id": user_id,
                "user_name": user_name,
                "username": username,
                "status": "open",
                "category": category,
                "priority": priority,
                "summary": _truncate(summary),
                "message_preview": _truncate(message_preview),
                "owner_message_id": owner_message_id,
                "user_message_id": user_message_id,
                "updated_at": now,
                "resolved_at": None,
            }
        )
        threads[str(record["thread_id"])] = record
        self._save(threads)
        return record

    def get(self, thread_id: str) -> dict[str, Any] | None:
        return self._load().get(str(thread_id))

    def get_by_owner_message_id(self, message_id: int) -> dict[str, Any] | None:
        for item in self._load().values():
            if item.get("owner_message_id") == message_id:
                return item
        return None

    def mark_resolved(self, thread_id: str) -> dict[str, Any] | None:
        threads = self._load()
        record = threads.get(str(thread_id))
        if not record:
            return None
        now = _now_iso()
        record["status"] = "resolved"
        record["updated_at"] = now
        record["resolved_at"] = now
        threads[str(thread_id)] = record
        self._save(threads)
        return record

    def open_threads(self, limit: int = 10) -> list[dict[str, Any]]:
        threads = [item for item in self._load().values() if item.get("status") == "open"]
        threads.sort(key=lambda item: str(item.get("updated_at") or ""), reverse=True)
        return threads[: max(0, limit)]

    def count_open(self) -> int:
        return len([item for item in self._load().values() if item.get("status") == "open"])


private_threads = PrivateThreads()
