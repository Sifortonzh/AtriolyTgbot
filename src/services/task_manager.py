import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from src.config import settings
from src.services.scheduler import scheduler_service

log = logging.getLogger(__name__)
DB_FILE = os.path.join(settings.DATA_DIR, "tasks.json")

class TaskManager:
    def __init__(self):
        # Structure: {"todo": [], "reminder": [], "days": [], "annis": []}
        self.data = self._load_db()
        self._reschedule_all()

    def _load_db(self) -> Dict[str, List]:
        if not os.path.exists(DB_FILE):
            return {"todo": [], "reminder": [], "days": [], "annis": []}
        try:
            with open(DB_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {"todo": [], "reminder": [], "days": [], "annis": []}

    def _save_db(self):
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        with open(DB_FILE, 'w') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def add_entry(self, category: str, entry: dict):
        """
        Category: 'todo', 'reminder', 'days', 'annis'
        Entry: {title, datetime, note, tags...}
        """
        if category not in self.data:
            self.data[category] = []
        
        # Generate simple ID
        entry['id'] = int(datetime.now().timestamp())
        self.data[category].append(entry)
        self._save_db()
        
        # If it's a one-shot reminder, schedule it immediately
        if category == 'reminder' and entry.get('datetime'):
            scheduler_service.schedule_one_off(entry)

    def get_entries(self, category: str) -> List[Dict]:
        return self.data.get(category, [])

    def _reschedule_all(self):
        """Reschedule active reminders on bot startup."""
        now = datetime.now()
        count = 0
        for r in self.data.get('reminder', []):
            try:
                dt = datetime.fromisoformat(r['datetime'])
                if dt > now:
                    scheduler_service.schedule_one_off(r)
                    count += 1
            except Exception as e:
                log.error(f"Failed to reschedule reminder {r}: {e}")
        log.info(f"🔄 Rescheduled {count} pending reminders.")

task_manager = TaskManager()