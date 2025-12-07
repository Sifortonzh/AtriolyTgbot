import json
import os
from datetime import datetime, timedelta
from typing import List, Dict

DB_FILE = "/app/data/memberships.json"

class MembershipManager:
	def __init__(self):
		self.memberships = self._load_db()

	def _load_db(self) -> List[Dict]:
		if not os.path.exists(DB_FILE): return []
		try:
			with open(DB_FILE, 'r') as f: return json.load(f)
		except: return []

	def save_db(self):
		os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
		with open(DB_FILE, 'w') as f: json.dump(self.memberships, f, indent=2)

	def add_membership(self, platform: str, expiry: str):
		self.memberships.append({"platform": platform, "expiry": expiry, "status": "active"})
		self.save_db()

	def get_active(self) -> List[Dict]:
		return [m for m in self.memberships if m['status'] == 'active']

manager = MembershipManager()
