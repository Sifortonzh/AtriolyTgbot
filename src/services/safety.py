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
    RANKING_TRAFFIC_RE = re.compile(
        r"上榜|榜费|大群|工兵|进大群|上榜商务|上榜方式|排名|冲榜|引流|推广|资源合作",
        re.IGNORECASE,
    )
    PAYMENT_ESCROW_RE = re.compile(
        r"代收|课费代收|一对一担保|上押|资金结算|RMB|USDT|支付频道|收款|跑分|结算|担保交易",
        re.IGNORECASE,
    )
    AGGRESSIVE_PROMO_RE = re.compile(
        r"免费|安全无忧|详情做选择|多种多样|全国大中小|外卖资源|客服账账|负责人",
        re.IGNORECASE,
    )
    TELEGRAM_LINK_RE = re.compile(r"(?i)(?:https?://)?(?:t\.me|telegram\.me)/[^\s，。；,;]+")
    TELEGRAM_USERNAME_RE = re.compile(r"(?<![\w])@[A-Za-z0-9_]{3,32}\b")
    TELEGRAM_BOT_RE = re.compile(r"(?<![\w])@[A-Za-z0-9_]*bot\b", re.IGNORECASE)

    URL_TOKEN_RE = re.compile(
        r"(?i)(https?://[^\s]+|www\.[^\s]+|\b[a-z0-9][a-z0-9-]{1,62}\.(?:com|net|org|cc|vip|top|xyz|icu|bet|fun|site|online|app|io|me|tv|club|cn)\b)",
        re.IGNORECASE,
    )

    @staticmethod
    def _count_url_like_tokens(text: str) -> int:
        return len(SafetyFilter.URL_TOKEN_RE.findall(text or ""))

    @staticmethod
    def analyze_spam(text: str) -> dict:
        original = text or ""
        lowered = original.lower()
        score = 0
        signals: list[str] = []
        reasons: list[str] = []

        has_gambling = bool(SafetyFilter.CHINESE_GAMBLING_CASINO_RE.search(original))
        has_registration_promo = bool(SafetyFilter.REGISTRATION_PROMO_RE.search(original))
        has_betting = bool(SafetyFilter.BETTING_TERMS_RE.search(original))
        has_ad_promo = bool(SafetyFilter.AD_PROMOTION_RE.search(original))
        has_suspicious_finance = bool(SafetyFilter.SUSPICIOUS_FINANCE_RE.search(original))
        has_ranking_traffic = bool(SafetyFilter.RANKING_TRAFFIC_RE.search(original))
        has_payment_escrow = bool(SafetyFilter.PAYMENT_ESCROW_RE.search(original))
        has_aggressive_promo = bool(SafetyFilter.AGGRESSIVE_PROMO_RE.search(original))
        url_count = SafetyFilter._count_url_like_tokens(original)
        t_me_count = len(SafetyFilter.TELEGRAM_LINK_RE.findall(original))
        username_count = len(SafetyFilter.TELEGRAM_USERNAME_RE.findall(original))
        bot_username_count = len(SafetyFilter.TELEGRAM_BOT_RE.findall(original))
        free_count = len(re.findall(r"免费", original))

        def add(points: int, signal: str, reason: str) -> None:
            nonlocal score
            score += points
            if signal not in signals:
                signals.append(signal)
            if reason not in reasons:
                reasons.append(reason)

        if has_gambling:
            add(5, "chinese_gambling", "chinese gambling keyword")
        if has_registration_promo:
            add(4, "registration_promo", "registration bonus keyword")
        if has_betting:
            add(4, "betting_terms", "betting keyword")
        if has_ad_promo:
            add(3, "ad_promotion", "ad promotion keyword")
        if has_suspicious_finance:
            add(3, "suspicious_finance", "suspicious finance keyword")
        if has_ranking_traffic:
            add(4, "ranking_traffic_spam", "ranking/traffic boosting spam")
        if has_payment_escrow:
            add(4, "payment_escrow", "payment/escrow/proxy collection spam")
        if has_aggressive_promo:
            add(2, "aggressive_promo", "aggressive promotional phrase")
        if t_me_count:
            add(3 + min(t_me_count, 3), "t_me_link", "Telegram ad link")
        if username_count >= 2:
            add(4, "multiple_telegram_usernames", "multiple Telegram usernames")
        elif username_count == 1:
            add(1, "telegram_username", "Telegram username")
        if bot_username_count:
            add(4, "telegram_bot_promo", "Telegram bot promotion")
        if url_count >= 5:
            add(5, "multi_url_advertisement", "multi-url advertisement")
        elif url_count >= 2:
            add(2, "multi_url", "multiple links")
        if free_count >= 3:
            add(3, "repeated_free", "repeated free promotion")

        has_any_gambling_promo = any(
            [has_gambling, has_registration_promo, has_betting, has_ad_promo, has_suspicious_finance]
        )

        high_confidence = False
        if has_any_gambling_promo and url_count >= 2:
            add(4, "promo_keyword_multi_url", "promo keyword + multi-url")
            high_confidence = True
        if t_me_count and has_payment_escrow:
            add(5, "t_me_payment_combo", "Telegram link + payment/escrow keyword")
            high_confidence = True
        if t_me_count and has_ranking_traffic:
            add(5, "t_me_ranking_combo", "Telegram link + ranking/traffic keyword")
            high_confidence = True
        if t_me_count and free_count >= 3:
            add(4, "t_me_repeated_free_combo", "repeated free promotion + Telegram link")
            high_confidence = True
        if username_count >= 2 or bot_username_count:
            high_confidence = True

        for pattern in SafetyFilter.SPAM_PATTERNS:
            if re.search(pattern, lowered):
                add(3, "legacy_spam_pattern", "legacy spam pattern")
                break

        if has_gambling or has_registration_promo or has_betting:
            high_confidence = True

        is_spam = high_confidence or score >= 8

        return {
            "is_spam": is_spam,
            "action": "drop" if is_spam else "ignore",
            "reason": "heuristic: " + "; ".join(reasons) if is_spam and reasons else None,
            "score": score,
            "signals": signals,
            "high_confidence": bool(is_spam and (high_confidence or score >= 10)),
        }

    @staticmethod
    def check_obvious_spam(text: str) -> tuple[bool, str | None]:
        result = SafetyFilter.analyze_spam(text)
        return bool(result["is_spam"]), result["reason"]

    @staticmethod
    def is_obvious_spam(text: str) -> bool:
        spam, _reason = SafetyFilter.check_obvious_spam(text)
        return spam


safety_filter = SafetyFilter()
