from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import settings

log = logging.getLogger(__name__)

CONTACTS_FILE: Path = settings.data_path / "private_contacts.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_name(user: Any) -> str:
    return str(getattr(user, "full_name", None) or getattr(user, "first_name", None) or "Unknown")


class PrivateContacts:
    def __init__(self, path: Path = CONTACTS_FILE):
        self.path = path

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as error:  # noqa: BLE001
            log.warning("Failed to load private contacts from %s: %s", self.path, error)
            return {}

        if isinstance(data, dict):
            return {str(key): value for key, value in data.items() if isinstance(value, dict)}
        if isinstance(data, list):
            return {
                str(item["user_id"]): item
                for item in data
                if isinstance(item, dict) and item.get("user_id") is not None
            }
        log.warning("Private contacts file %s has unexpected shape; starting empty.", self.path)
        return {}

    def _save(self, contacts: dict[str, dict[str, Any]]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(contacts, handle, ensure_ascii=False, indent=2)
        except Exception as error:  # noqa: BLE001
            log.error("Failed to save private contacts to %s: %s", self.path, error, exc_info=error)

    def upsert_from_user(
        self,
        user: Any,
        category: str | None = None,
        priority: str | None = None,
        summary: str | None = None,
    ) -> dict[str, Any]:
        contacts = self._load()
        user_id = int(getattr(user, "id"))
        key = str(user_id)
        now = _now_iso()

        record = contacts.get(key) or {
            "user_id": user_id,
            "name": _display_name(user),
            "username": getattr(user, "username", None),
            "first_seen": now,
            "last_seen": now,
            "message_count": 0,
            "last_category": None,
            "last_priority": None,
            "last_summary": None,
            "notes": [],
        }

        record["name"] = _display_name(user)
        record["username"] = getattr(user, "username", None)
        record["last_seen"] = now
        record["message_count"] = int(record.get("message_count") or 0) + 1
        if category is not None:
            record["last_category"] = str(category)
        if priority is not None:
            record["last_priority"] = str(priority)
        if summary is not None:
            record["last_summary"] = str(summary)[:800]
        if not isinstance(record.get("notes"), list):
            record["notes"] = []

        contacts[key] = record
        self._save(contacts)
        return record

    def get(self, user_id: int) -> dict[str, Any] | None:
        return self._load().get(str(user_id))

    def recent(self, limit: int = 10) -> list[dict[str, Any]]:
        contacts = list(self._load().values())
        contacts.sort(key=lambda item: str(item.get("last_seen") or ""), reverse=True)
        return contacts[: max(0, limit)]

    def count(self) -> int:
        return len(self._load())


private_contacts = PrivateContacts()
