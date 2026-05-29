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

    CHINESE_GAMBLING_CASINO_RE = re.compile(
        r"博彩|赌博|赌场|棋牌|彩票|真人|视讯|娱乐城|娱乐平台|赌博平台|购彩平台",
        re.IGNORECASE,
    )
    REGISTRATION_PROMO_RE = re.compile(
        r"注册送|注册送彩金|送彩金|首存|首充|充值送|返利|返水|包赔|包赢|稳赚|日赚|躺赚",
        re.IGNORECASE,
    )
    BETTING_TERMS_RE = re.compile(
        r"走地|上分|下分|盘口|赔率|下注|投注|庄家|开奖|六合彩",
        re.IGNORECASE,
    )
    AD_PROMOTION_RE = re.compile(
        r"老哥网广|网广|广告投放|平台招商|推广合作|商务合作|渠道合作|拉新|引流",
        re.IGNORECASE,
    )
    SUSPICIOUS_FINANCE_RE = re.compile(
        r"USDT|币圈|虚拟币|投资群|带单|稳赚不赔",
        re.IGNORECASE,
    )

    URL_TOKEN_RE = re.compile(
        r"(?i)(https?://[^\s]+|www\.[^\s]+|\b[a-z0-9][a-z0-9-]{1,62}\.(?:com|net|org|cc|vip|top|xyz|icu|bet|fun|site|online|app|io|me|tv|club|cn)\b)",
        re.IGNORECASE,
    )

    @staticmethod
    def _count_url_like_tokens(text: str) -> int:
        return len(SafetyFilter.URL_TOKEN_RE.findall(text or ""))

    @staticmethod
    def check_obvious_spam(text: str) -> tuple[bool, str | None]:
        original = text or ""
        lowered = original.lower()

        has_gambling = bool(SafetyFilter.CHINESE_GAMBLING_CASINO_RE.search(original))
        has_registration_promo = bool(SafetyFilter.REGISTRATION_PROMO_RE.search(original))
        has_betting = bool(SafetyFilter.BETTING_TERMS_RE.search(original))
        has_ad_promo = bool(SafetyFilter.AD_PROMOTION_RE.search(original))
        has_suspicious_finance = bool(SafetyFilter.SUSPICIOUS_FINANCE_RE.search(original))
        url_count = SafetyFilter._count_url_like_tokens(original)

        has_any_gambling_promo = any(
            [has_gambling, has_registration_promo, has_betting, has_ad_promo, has_suspicious_finance]
        )

        if has_gambling and url_count >= 2:
            return True, "heuristic: gambling keyword + multi-url"
        if has_registration_promo and url_count >= 2:
            return True, "heuristic: gambling keyword + multi-url"
        if has_betting and url_count >= 2:
            return True, "heuristic: gambling keyword + multi-url"
        if has_ad_promo and url_count >= 2:
            return True, "heuristic: gambling keyword + multi-url"
        if has_suspicious_finance and url_count >= 2:
            return True, "heuristic: gambling keyword + multi-url"

        if has_gambling:
            return True, "heuristic: chinese gambling keyword"
        if has_registration_promo:
            return True, "heuristic: registration bonus keyword"
        if has_betting:
            return True, "heuristic: betting keyword"
        if has_ad_promo:
            return True, "heuristic: ad promotion keyword"
        if has_suspicious_finance:
            return True, "heuristic: suspicious finance keyword"

        if url_count >= 5:
            return True, "heuristic: multi-url advertisement"

        if url_count >= 2 and has_any_gambling_promo:
            return True, "heuristic: gambling keyword + multi-url"

        for pattern in SafetyFilter.SPAM_PATTERNS:
            if re.search(pattern, lowered):
                return True, "heuristic: legacy spam pattern"

        return False, None

    @staticmethod
    def is_obvious_spam(text: str) -> bool:
        spam, _reason = SafetyFilter.check_obvious_spam(text)
        return spam


safety_filter = SafetyFilter()
