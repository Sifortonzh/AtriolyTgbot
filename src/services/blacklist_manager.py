import json
import os
import logging
from typing import Dict

log = logging.getLogger(__name__)
DB_FILE = "/app/data/blacklist.json"

class BlacklistManager:
	def __init__(self):
		self.data = self._load_db()

	def _load_db(self) -> Dict:
		if not os.path.exists(DB_FILE):
			return {"banned": [], "warnings": {}}
		try:
			with open(DB_FILE, 'r') as f: return json.load(f)
		except: return {"banned": [], "warnings": {}}

	def _save_db(self):
		os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
		with open(DB_FILE, 'w') as f: json.dump(self.data, f, indent=2)

	def is_banned(self, user_id: int) -> bool:
		return user_id in self.data["banned"]

	def ban_user(self, user_id: int):
		if user_id not in self.data["banned"]:
			self.data["banned"].append(user_id)
			if str(user_id) in self.data["warnings"]: del self.data["warnings"][str(user_id)]
			self._save_db()

	def unban_user(self, user_id: int):
		if user_id in self.data["banned"]:
			self.data["banned"].remove(user_id)
			self._save_db()
			return True
		return False

	def add_strike(self, user_id: int, max_strikes: int = 3) -> str:
		uid_str = str(user_id)
		current = self.data["warnings"].get(uid_str, 0) + 1
		if current >= max_strikes:
			self.ban_user(user_id)
			return "banned"
		self.data["warnings"][uid_str] = current
		self._save_db()
		return "warned"

	def get_strike_count(self, user_id: int) -> int:
		return self.data["warnings"].get(str(user_id), 0)

blacklist = BlacklistManager()
