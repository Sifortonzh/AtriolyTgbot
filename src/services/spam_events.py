from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path
from typing import Any

from src.config import settings

log = logging.getLogger(__name__)

SPAM_EVENTS_FILE: Path = settings.data_path / "spam_events.json"
MAX_EVENTS = 500


class SpamEvents:
    def __init__(self, path: Path = SPAM_EVENTS_FILE):
        self.path = path

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001
            log.warning("Failed to load spam events from %s: %s", self.path, error)
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        log.warning("Spam events file %s has unexpected shape; starting empty.", self.path)
        return []

    def _save(self, events: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        trimmed = events[:MAX_EVENTS]
        self.path.write_text(json.dumps(trimmed, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_event(
        self,
        *,
        user_id: int,
        username: str | None,
        display_name: str | None,
        chat_id: int | None,
        chat_title: str | None,
        reason: str,
        score: int,
        signals: list[str],
        action: str,
        deleted: bool,
        message_preview: str,
    ) -> dict[str, Any]:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        event = {
            "event_id": f"spam_{now}_{user_id}",
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "chat_id": chat_id,
            "chat_title": chat_title,
            "reason": reason,
            "score": score,
            "signals": signals,
            "action": action,
            "deleted": deleted,
            "message_preview": message_preview,
            "created_at": now,
        }
        events = [event, *self._load()]
        self._save(events)
        return event

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        return self._load()[: max(0, limit)]

    def count(self) -> int:
        return len(self._load())


spam_events = SpamEvents()
