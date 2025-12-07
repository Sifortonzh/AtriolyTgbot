import re

class SafetyFilter:
	SPAM_PATTERNS = [
		r"t\.me\/[\w_]+\?start=", r"crypto|bitcoin|usdt", r"win (a )?prize",
		r"investment", r"casino|gambling", r"click here", r"hot.*girl"
	]

	@staticmethod
	def is_obvious_spam(text: str) -> bool:
		text = text.lower()
		for pattern in SafetyFilter.SPAM_PATTERNS:
			if re.search(pattern, text):
				return True
		return False

safety_filter = SafetyFilter()
