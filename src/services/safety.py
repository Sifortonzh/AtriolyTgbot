import re


class SafetyFilter:
	SPAM_PATTERNS = [
		r"t\.me\/[\w_]+\?start=",
		r"crypto|bitcoin|usdt",
		r"win (a )?prize",
		r"investment",
		r"casino|gambling",
		r"click here",
		r"hot.*girl",
	]

	# High-confidence Chinese gambling / promo ad terms.
	GAMBLING_PROMO_KEYWORDS = (
		"博彩",
		"赌博",
		"赌场",
		"棋牌",
		"彩票",
		"真人",
		"视讯",
		"娱乐平台",
		"注册送",
		"注册送彩金",
		"首存",
		"返利",
		"返水",
		"包赔",
		"包赢",
		"稳赚",
		"走地",
		"上分",
		"下分",
		"盘口",
		"赔率",
		"老哥网广",
		"网广",
		"广告投放",
		"平台招商",
		"推广合作",
	)

	# URL-like tokens: full URLs, t.me style links, or plain domains.
	URL_TOKEN_RE = re.compile(
		r"(?:https?://\S+|www\.\S+|t\.me/\S+|[a-z0-9][a-z0-9\-]{0,61}\.[a-z]{2,}(?:/\S*)?)",
		re.IGNORECASE,
	)

	@staticmethod
	def _count_url_like_tokens(text: str) -> int:
		return len(SafetyFilter.URL_TOKEN_RE.findall(text or ""))

	@staticmethod
	def _contains_gambling_promo_keyword(text: str) -> bool:
		return any(keyword in text for keyword in SafetyFilter.GAMBLING_PROMO_KEYWORDS)

	@staticmethod
	def is_obvious_spam(text: str) -> bool:
		original = text or ""
		text = original.lower()

		url_count = SafetyFilter._count_url_like_tokens(original)
		contains_gambling_promo = SafetyFilter._contains_gambling_promo_keyword(original)

		# Rule 1: very high URL/domain density.
		if url_count >= 5:
			return True

		# Rule 2: multiple links + gambling/promo language.
		if url_count >= 2 and contains_gambling_promo:
			return True

		# Rule 3: direct gambling/promo ad terms.
		if contains_gambling_promo:
			return True

		for pattern in SafetyFilter.SPAM_PATTERNS:
			if re.search(pattern, text):
				return True
		return False


safety_filter = SafetyFilter()
