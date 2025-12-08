import json
import os
import logging
from typing import Dict, Optional

from src.config import settings

log = logging.getLogger(__name__)

# 如果 settings 里有 DATA_DIR 就用，没有就退回到 /app/data
DATA_DIR = getattr(settings, "DATA_DIR", "/app/data")
MODE_FILE = os.path.join(DATA_DIR, "chat_modes.json")


class StateManager:
    def __init__(self):
        # Persistent: Chat Modes (user_id -> "chat" | "forward")
        self.modes: Dict[str, str] = self._load_modes()
        # Ephemeral: Reply Bridge (admin_msg_id -> original_user_id)
        # 不持久化，重启后清空
        self.reply_map: Dict[int, int] = {}

    # ---------- 持久化 Chat Mode ----------

    def _load_modes(self) -> Dict[str, str]:
        if not os.path.exists(MODE_FILE):
            return {}
        try:
            with open(MODE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
        except Exception as e:
            log.error("Failed to load chat modes from %s: %s", MODE_FILE, e)
            return {}

    def _save_modes(self) -> None:
        try:
            os.makedirs(os.path.dirname(MODE_FILE), exist_ok=True)
            with open(MODE_FILE, "w", encoding="utf-8") as f:
                json.dump(self.modes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            log.error("Failed to save chat modes to %s: %s", MODE_FILE, e)

    def set_mode(self, user_id: int, mode: str) -> None:
        """Set mode: 'chat' (AI Auto-Reply) or 'forward' (Human Support)."""
        self.modes[str(user_id)] = mode
        self._save_modes()

    def get_mode(self, user_id: int) -> str:
        """Default to 'forward' for safety."""
        return self.modes.get(str(user_id), "forward")

    # ---------- Reply Bridge 逻辑 ----------

    def register_forward(self, admin_msg_id: int, original_user_id: int) -> None:
        """记录：管理员这条转发消息对应的原始用户 ID。"""
        self.reply_map[admin_msg_id] = original_user_id

    def get_original_sender(self, admin_msg_id: int) -> Optional[int]:
        """根据管理员回复的那条消息 ID 找回原始用户。"""
        return self.reply_map.get(admin_msg_id)


state_manager = StateManager()
