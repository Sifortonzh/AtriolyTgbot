import json
import os
import logging
from datetime import datetime
from typing import List, Dict

from src.services.scheduler import scheduler_service

log = logging.getLogger(__name__)

# 与其他 JSON 存储保持风格一致
DB_FILE = "/app/data/tasks.json"


class TaskManager:
    """
    统一管理四类任务：
      - todo       : 普通待办
      - reminder   : 有具体时间点的提醒（会提前 15 分钟推送）
      - days       : 特殊日期（当天 7:00 推送）
      - annis      : 周年/纪念日（当天 7:00 推送）
    """

    def __init__(self):
        self.data = self._load_db()
        self._ensure_keys()
        self._reschedule_reminders()

    # ---------- 基础存取 ----------

    def _ensure_keys(self):
        for k in ("todo", "reminder", "days", "annis"):
            self.data.setdefault(k, [])

    def _load_db(self) -> Dict[str, List[dict]]:
        if not os.path.exists(DB_FILE):
            return {"todo": [], "reminder": [], "days": [], "annis": []}
        try:
            with open(DB_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Failed to load tasks DB: {e}")
            return {"todo": [], "reminder": [], "days": [], "annis": []}

    def _save_db(self):
        os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
        try:
            with open(DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.error(f"Failed to save tasks DB: {e}")

    # ---------- CRUD 接口 ----------

    def add_entry(self, category: str, entry: dict):
        """
        新增任务：
        - 保证 entry 有唯一 id（秒级时间戳）
        - 对 reminder 会自动挂到 scheduler 上
        """
        if category not in self.data:
            log.warning(f"Unknown task category: {category}")
            self.data[category] = []

        if "id" not in entry:
            entry["id"] = int(datetime.now().timestamp())

        self.data[category].append(entry)
        self._save_db()

        if category == "reminder" and entry.get("datetime"):
            scheduler_service.schedule_reminder(entry)

    def delete_entry(self, category: str, entry_id: int) -> bool:
        """
        删除任务：
        - 如果是 reminder，会同时取消对应的定时任务
        """
        items = self.data.get(category, [])
        for i, item in enumerate(items):
            if item.get("id") == entry_id:
                del items[i]
                self._save_db()
                if category == "reminder":
                    scheduler_service.cancel_reminder(entry_id)
                return True
        return False

    def update_entry(self, category: str, entry_id: int, new_data: dict) -> bool:
        """
        更新任务：
        - 如果是 reminder 且时间发生变化，会重新挂载
        """
        items = self.data.get(category, [])
        for item in items:
            if item.get("id") == entry_id:
                item.update(new_data)
                self._save_db()
                if category == "reminder" and item.get("datetime"):
                    scheduler_service.schedule_reminder(item)
                return True
        return False

    def get_entries(self, category: str) -> List[Dict]:
        return self.data.get(category, [])

    # ---------- 启动时重挂 reminder ----------

    def _reschedule_reminders(self):
        """
        进程重启后，把未来的 reminder 重新挂载一遍。
        """
        now = datetime.now()
        count = 0
        for r in self.data.get("reminder", []):
            try:
                if not r.get("datetime"):
                    continue
                event_time = datetime.fromisoformat(r["datetime"])
                # scheduler 内部会自己减 15 分钟，这里只看事件是否仍在未来
                if event_time > now:
                    scheduler_service.schedule_reminder(r)
                    count += 1
            except Exception as e:
                log.error(f"Failed to reschedule reminder {r}: {e}")
        if count:
            log.info(f"🔄 Rescheduled {count} pending reminders.")


task_manager = TaskManager()
