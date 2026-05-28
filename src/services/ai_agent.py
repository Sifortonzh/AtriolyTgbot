
from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from anthropic import Anthropic
from openai import OpenAI

from src.config import settings

log = logging.getLogger(__name__)


class AIAgent:
    """
    Unified AI agent for:
    - Group messages: SPAM + Streaming Membership detection
    - Private messages: Category + Tags + Summary + Spam
    - Owner intent parsing: todo / reminder / days / annis / none
    - Task management from chat (create / update / delete / list)
    - Greeting generation for festivals / anniversaries
    """

    GROUP_SCHEMA: Dict[str, Any] = {
        "is_spam": False,
        "spam_reason": None,
        "is_membership": False,
        "intent": "irrelevant",
        "platform": None,
        "price": None,
        "currency": None,
        "region": None,
        "risk_score": 0,
        "confidence": 0.0,
        "summary": "",
        "reason": "No analysis available.",
        "action": "ignore",
    }

    HARD_SPAM_MARKERS = (
        "phishing",
        "phish",
        "crypto",
        "usdt",
        "赌博",
        "博彩",
        "gambling",
        "porn",
        "nsfw",
        "malware",
        "virus",
        "fraud",
        "scam",
        "钓鱼",
        "诈骗",
        "木马",
        "病毒",
        "色情",
        "引流",
    )

    MEMBERSHIP_KEYWORDS = (
        "netflix",
        "disney",
        "youtube",
        "spotify",
        "hbo",
        "prime",
        "apple tv",
        "apple one",
        "paramount",
        "peacock",
        "hulu",
        "max",
        "合租",
        "拼车",
        "车位",
        "上车",
        "求租",
        "出车",
        "会员",
        "月付",
        "季付",
        "年付",
        "共享",
    )

    def __init__(self) -> None:
        self._provider = (settings.AI_PROVIDER or "openai").strip().lower().replace("-", "_")
        self._cache: dict[str, tuple[float, Any]] = {}
        self._openai_like_client: OpenAI | None = self._build_openai_like_client()
        self._anthropic_client: Anthropic | None = self._build_anthropic_client()

    # ========== Common Helper ==========

    def _build_openai_like_client(self) -> OpenAI | None:
        provider = self._provider

        if provider == "openai":
            api_key = settings.effective_openai_key
            if not api_key:
                return None
            base_url = settings.OPENAI_BASE_URL or settings.AI_BASE_URL
            if base_url:
                return OpenAI(api_key=api_key, base_url=base_url, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS)
            return OpenAI(api_key=api_key, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS)

        if provider == "deepseek":
            api_key = settings.effective_deepseek_key
            if not api_key:
                return None
            return OpenAI(api_key=api_key, base_url=settings.DEEPSEEK_BASE_URL, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS)

        if provider == "openai_compatible":
            api_key = settings.effective_openai_compatible_key
            base_url = settings.OPENAI_COMPATIBLE_BASE_URL
            if not api_key or not base_url:
                return None
            return OpenAI(api_key=api_key, base_url=base_url, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS)

        return None

    def _build_anthropic_client(self) -> Anthropic | None:
        if self._provider != "anthropic":
            return None
        api_key = settings.effective_anthropic_key
        if not api_key:
            return None
        return Anthropic(api_key=api_key, timeout=settings.AI_REQUEST_TIMEOUT_SECONDS)

    def _model_for_task(self, task: str, model: str | None = None) -> str:
        if model:
            return model
        return settings.get_model_for_task(task)

    def _cache_get(self, cache_key: str) -> Any | None:
        ttl = max(0, settings.AI_CACHE_TTL_SECONDS)
        if ttl <= 0:
            return None
        cached = self._cache.get(cache_key)
        if not cached:
            return None
        expire_at, value = cached
        if expire_at < time.time():
            self._cache.pop(cache_key, None)
            return None
        if isinstance(value, dict):
            copied = dict(value)
            copied["_cached"] = True
            return copied
        return value

    def _cache_set(self, cache_key: str, value: Any) -> None:
        ttl = max(0, settings.AI_CACHE_TTL_SECONDS)
        if ttl <= 0:
            return
        self._cache[cache_key] = (time.time() + ttl, value)
        if len(self._cache) > 512:
            oldest_key = min(self._cache, key=lambda key: self._cache[key][0])
            self._cache.pop(oldest_key, None)

    @staticmethod
    def _safe_text(text: str, limit: int | None = None) -> str:
        value = (text or "").strip()
        max_length = limit or settings.MAX_MESSAGE_LENGTH
        return value[:max_length]

    @staticmethod
    def _extract_json_object(text: str) -> Dict[str, Any]:
        if not text:
            raise ValueError("Empty AI response")

        cleaned = text.strip()
        fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
        if fence:
            cleaned = fence.group(1).strip()

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if not match:
            raise ValueError("No JSON object found")

        parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise ValueError("JSON content is not an object")
        return parsed

    async def _call_gpt(
        self,
        system_prompt: str,
        user_text: str,
        model: str | None = None,
        *,
        task: str = "radar",
    ) -> Dict[str, Any]:
        """Call current provider and parse JSON."""
        model_name = self._model_for_task(task, model)
        safe_user_text = self._safe_text(user_text)
        cache_key = json.dumps(
            {
                "provider": self._provider,
                "model": model_name,
                "system": system_prompt,
                "user": safe_user_text,
                "mode": "json",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached

        retries = max(0, settings.AI_RETRY_TIMES)
        delay_seconds = 0.6
        started = time.perf_counter()

        for attempt in range(retries + 1):
            try:
                if self._provider == "anthropic":
                    if not self._anthropic_client:
                        return {"error": "Anthropic API key not configured"}
                    response = self._anthropic_client.messages.create(
                        model=model_name,
                        max_tokens=1200,
                        temperature=settings.AI_TEMPERATURE,
                        system=system_prompt,
                        messages=[
                            {
                                "role": "user",
                                "content": f"{safe_user_text}\n\nReturn exactly one valid JSON object. Do not use Markdown.",
                            }
                        ],
                    )
                    text_content = "".join(
                        block.text for block in response.content if getattr(block, "type", "") == "text"
                    )
                    result = self._extract_json_object(text_content)
                else:
                    if not self._openai_like_client:
                        return {"error": "AI provider credentials not configured"}
                    response = self._openai_like_client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": safe_user_text},
                        ],
                        temperature=settings.AI_TEMPERATURE,
                        response_format={"type": "json_object"},
                    )
                    content = response.choices[0].message.content or ""
                    result = self._extract_json_object(content)

                result.setdefault("_provider", self._provider)
                result.setdefault("_model", model_name)
                result.setdefault("_cached", False)
                result.setdefault("_elapsed_ms", int((time.perf_counter() - started) * 1000))
                self._cache_set(cache_key, result)
                return result
            except Exception as exc:  # noqa: BLE001
                log.warning("AI call failed (attempt %s/%s): %s", attempt + 1, retries + 1, exc)
                if attempt >= retries:
                    return {
                        "error": str(exc),
                        "_provider": self._provider,
                        "_model": model_name,
                        "_cached": False,
                        "_elapsed_ms": int((time.perf_counter() - started) * 1000),
                    }
                await asyncio.sleep(delay_seconds * (attempt + 1))

        return {"error": "Unknown AI error"}

    async def _call_text(
        self,
        system_prompt: str,
        user_text: str,
        model: str | None = None,
        max_tokens: int = 500,
        *,
        task: str = "chat",
    ) -> str:
        model_name = self._model_for_task(task, model)
        safe_user_text = self._safe_text(user_text)
        cache_key = json.dumps(
            {
                "provider": self._provider,
                "model": model_name,
                "system": system_prompt,
                "user": safe_user_text,
                "mode": "text",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cached = self._cache_get(cache_key)
        if isinstance(cached, str):
            return cached

        retries = max(0, settings.AI_RETRY_TIMES)
        delay_seconds = 0.6

        for attempt in range(retries + 1):
            try:
                if self._provider == "anthropic":
                    if not self._anthropic_client:
                        return ""
                    response = self._anthropic_client.messages.create(
                        model=model_name,
                        max_tokens=max_tokens,
                        temperature=settings.AI_TEMPERATURE,
                        system=system_prompt,
                        messages=[{"role": "user", "content": safe_user_text}],
                    )
                    content = "".join(
                        block.text for block in response.content if getattr(block, "type", "") == "text"
                    ).strip()
                else:
                    if not self._openai_like_client:
                        return ""
                    response = self._openai_like_client.chat.completions.create(
                        model=model_name,
                        temperature=settings.AI_TEMPERATURE,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": safe_user_text},
                        ],
                    )
                    content = (response.choices[0].message.content or "").strip()

                self._cache_set(cache_key, content)
                return content
            except Exception as exc:  # noqa: BLE001
                log.warning("AI text call failed (attempt %s/%s): %s", attempt + 1, retries + 1, exc)
                if attempt >= retries:
                    return ""
                await asyncio.sleep(delay_seconds * (attempt + 1))

        return ""

    # ========== Group Logic (Streaming + Spam) ==========

    def _guess_platform(self, text: str) -> str | None:
        compact = text.lower().replace(" ", "")
        platform_map = {
            "netflix": "Netflix",
            "奈飞": "Netflix",
            "nf": "Netflix",
            "disney": "Disney+",
            "迪士尼": "Disney+",
            "youtube": "YouTube",
            "ytb": "YouTube",
            "spotify": "Spotify",
            "hbo": "HBO Max",
            "max": "Max",
            "prime": "Prime Video",
            "appletv": "Apple TV+",
            "appleone": "Apple One",
            "hulu": "Hulu",
        }
        for keyword, platform in platform_map.items():
            if keyword in compact:
                return platform
        return None

    def _guess_price(self, text: str) -> tuple[float | None, str | None]:
        match = re.search(r"(?P<price>\d+(?:\.\d+)?)\s*(?P<currency>元|块|rmb|cny|¥|usd|\$)?", text, re.I)
        if not match:
            return None, None
        try:
            price = float(match.group("price"))
        except ValueError:
            return None, None
        raw_currency = (match.group("currency") or "").lower()
        if raw_currency in {"元", "块", "rmb", "cny", "¥"}:
            return price, "CNY"
        if raw_currency in {"usd", "$"}:
            return price, "USD"
        return price, None

    def _guess_membership_intent(self, text: str) -> str:
        lowered = text.lower()
        if any(token in lowered for token in ("求", "求租", "找", "有没有", "need", "looking for")):
            return "request"
        if any(token in lowered for token in ("换", "exchange", "互换")):
            return "exchange"
        if any(token in lowered for token in ("出", "有车位", "车位还有", "slot", "share", "offer")):
            return "offer"
        return "offer"

    def _normalize_group_analysis(self, data: Dict[str, Any], source_text: str = "") -> Dict[str, Any]:
        normalized = dict(self.GROUP_SCHEMA)
        if isinstance(data, dict):
            for key in normalized:
                if key in data:
                    normalized[key] = data[key]

        intent = str(normalized.get("intent") or "irrelevant").strip().lower()
        if intent not in {"offer", "request", "exchange", "scam", "irrelevant"}:
            intent = "irrelevant"
        normalized["intent"] = intent

        action = str(normalized.get("action") or "ignore").strip().lower()
        if action not in {"ignore", "forward", "warn", "ban_candidate"}:
            action = "ignore"
        normalized["action"] = action

        for key in ("platform", "currency", "region", "spam_reason", "summary", "reason"):
            value = normalized.get(key)
            normalized[key] = str(value).strip() if value not in (None, "") else None

        if normalized["currency"]:
            normalized["currency"] = normalized["currency"].upper()

        try:
            normalized["price"] = float(normalized["price"]) if normalized.get("price") is not None else None
        except (TypeError, ValueError):
            normalized["price"] = None

        try:
            normalized["risk_score"] = max(0, min(int(normalized.get("risk_score") or 0), 100))
        except (TypeError, ValueError):
            normalized["risk_score"] = 0

        try:
            normalized["confidence"] = max(0.0, min(float(normalized.get("confidence") or 0.0), 1.0))
        except (TypeError, ValueError):
            normalized["confidence"] = 0.0

        normalized["is_spam"] = bool(normalized.get("is_spam"))
        normalized["is_membership"] = bool(normalized.get("is_membership"))

        source_lower = source_text.lower()
        if not normalized["is_membership"] and any(keyword in source_lower for keyword in self.MEMBERSHIP_KEYWORDS):
            normalized["is_membership"] = True

        if normalized["is_membership"]:
            normalized["platform"] = normalized["platform"] or self._guess_platform(source_text)
            if normalized["intent"] == "irrelevant":
                normalized["intent"] = self._guess_membership_intent(source_text)
            if normalized["price"] is None:
                price, currency = self._guess_price(source_text)
                normalized["price"] = price
                normalized["currency"] = normalized["currency"] or currency

        spam_reason_text = str(normalized.get("spam_reason") or "").lower()
        has_hard_spam_reason = any(marker in spam_reason_text for marker in self.HARD_SPAM_MARKERS)
        has_hard_spam_text = any(marker in source_lower for marker in self.HARD_SPAM_MARKERS)

        if normalized["is_membership"] and normalized["intent"] in {"offer", "request", "exchange"} and not has_hard_spam_reason:
            normalized["is_spam"] = False
            normalized["spam_reason"] = None

        if has_hard_spam_text and not normalized["is_membership"]:
            normalized["is_spam"] = True
            normalized["intent"] = "scam"
            normalized["risk_score"] = max(int(normalized["risk_score"]), 80)
            normalized["confidence"] = max(float(normalized["confidence"]), 0.75)
            normalized["spam_reason"] = normalized["spam_reason"] or "Hard spam/scam keyword detected."

        if normalized["is_spam"]:
            if normalized["risk_score"] >= 85:
                normalized["action"] = "ban_candidate"
            elif normalized["action"] == "ignore":
                normalized["action"] = "warn"
        elif normalized["is_membership"]:
            if normalized["confidence"] < settings.MIN_CONFIDENCE_TO_FORWARD:
                normalized["confidence"] = max(float(normalized["confidence"]), 0.70)
            if normalized["risk_score"] >= settings.HIGH_RISK_THRESHOLD:
                normalized["action"] = "warn"
            else:
                normalized["action"] = "forward"

        if not normalized.get("summary"):
            normalized["summary"] = source_text[:160] or "No summary."
        if not normalized.get("reason"):
            normalized["reason"] = "Normalized by Atrioly AI router."

        return normalized

    async def analyze_message(self, text: str) -> Dict[str, Any]:
        """
        Analyze group message and always return the full radar schema:
        is_spam, spam_reason, is_membership, intent, platform, price,
        currency, region, risk_score, confidence, summary, reason, action.
        """
        text = self._safe_text(text)

        has_client = self._anthropic_client is not None if self._provider == "anthropic" else self._openai_like_client is not None
        if not has_client:
            return self._fallback_group_analysis(text, "No AI credentials configured")

        if len((text or "").strip()) < settings.MIN_TEXT_LENGTH_FOR_AI:
            return self._normalize_group_analysis(
                {
                    "summary": "Message too short to analyze.",
                    "reason": "too_short",
                    "action": "ignore",
                },
                text,
            )

        system_prompt = (
            "You are Atrioly · Wanatring, a Telegram intelligence filter for streaming membership sharing.\n"
            "Detect useful streaming membership messages and obvious spam/scam messages.\n\n"
            "Important business rule:\n"
            "A normal streaming membership offer/request/exchange is NOT spam by itself.\n"
            "Only mark spam for phishing, crypto scams, gambling, NSFW ads, malware, bot spam, mass invite ads, or obvious fraud.\n\n"
            "Membership examples include: 出车位, 有车位, Netflix 车位还有一个, 求租, 上车, 有没有位置, 拼车, 合租, group buy, share slot.\n\n"
            "Return JSON only with exactly this schema:\n"
            "{\n"
            "  \"is_spam\": boolean,\n"
            "  \"spam_reason\": string or null,\n"
            "  \"is_membership\": boolean,\n"
            "  \"intent\": \"offer\" | \"request\" | \"exchange\" | \"scam\" | \"irrelevant\",\n"
            "  \"platform\": string or null,\n"
            "  \"price\": number or null,\n"
            "  \"currency\": string or null,\n"
            "  \"region\": string or null,\n"
            "  \"risk_score\": integer from 0 to 100,\n"
            "  \"confidence\": number from 0 to 1,\n"
            "  \"summary\": string,\n"
            "  \"reason\": string,\n"
            "  \"action\": \"ignore\" | \"forward\" | \"warn\" | \"ban_candidate\"\n"
            "}\n"
            "Use action=forward for credible membership signals with confidence >= 0.65 and risk_score < 75."
        )

        result = await self._call_gpt(system_prompt, text, task="radar")
        if "error" in result:
            log.error("AI Analysis Failed (group): %s", result["error"])
            return self._fallback_group_analysis(text, result["error"])

        merged = self._normalize_group_analysis(result, text)
        merged["_provider"] = result.get("_provider", self._provider)
        merged["_model"] = result.get("_model", self._model_for_task("radar"))
        merged["_cached"] = result.get("_cached", False)
        merged["_elapsed_ms"] = result.get("_elapsed_ms")
        return merged

    def _fallback_group_analysis(self, text: str, error: str | None = None) -> Dict[str, Any]:
        source_lower = text.lower()
        is_membership = any(keyword in source_lower for keyword in self.MEMBERSHIP_KEYWORDS)
        has_hard_spam = any(marker in source_lower for marker in self.HARD_SPAM_MARKERS)
        price, currency = self._guess_price(text)

        data = {
            "is_spam": bool(has_hard_spam and not is_membership),
            "spam_reason": "Hard spam/scam keyword detected." if has_hard_spam and not is_membership else None,
            "is_membership": is_membership,
            "intent": "scam" if has_hard_spam and not is_membership else (self._guess_membership_intent(text) if is_membership else "irrelevant"),
            "platform": self._guess_platform(text),
            "price": price,
            "currency": currency,
            "region": None,
            "risk_score": 80 if has_hard_spam and not is_membership else (35 if is_membership else 0),
            "confidence": 0.75 if has_hard_spam else (0.70 if is_membership else 0.0),
            "summary": text[:160] or "AI fallback analysis.",
            "reason": f"Fallback analysis used. {error or ''}".strip(),
            "action": "warn" if has_hard_spam and not is_membership else ("forward" if is_membership else "ignore"),
        }
        return self._normalize_group_analysis(data, text)

    # ========== Private Logic (DM 分类 / 标签 / Summary) ==========

    async def analyze_private_message(self, text: str) -> Dict[str, Any]:
        has_client = self._anthropic_client is not None if self._provider == "anthropic" else self._openai_like_client is not None
        if not has_client:
            return {
                "is_spam": False,
                "category": "general_chat",
                "tags": [],
                "summary": "AI disabled (no API key).",
                "error": "No API key configured",
            }

        system_prompt = (
            "You are Atrioly's Service Desk AI. Analyze this private message.\n"
            "Classify category as one of: membership_sharing, general_chat, support, billing, other.\n"
            "Generate 1-3 short tags and one concise admin-facing summary.\n"
            "Return JSON: {\"is_spam\": bool, \"category\": str, \"tags\": [str], \"summary\": str}"
        )

        result = await self._call_gpt(system_prompt, text, task="private")
        if "error" in result:
            log.error("AI Analysis Failed (private): %s", result["error"])
            return {
                "is_spam": False,
                "category": "other",
                "tags": [],
                "summary": "AI error; fallback classification.",
                "error": result["error"],
            }

        tags = result.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]

        return {
            "is_spam": bool(result.get("is_spam", False)),
            "category": str(result.get("category") or "other"),
            "tags": [str(tag) for tag in tags[:3]],
            "summary": str(result.get("summary") or "No summary."),
        }

    # ========== Owner Intent (todo / reminder / days / annis) ==========

    async def analyze_owner_intent(self, text: str) -> Dict[str, Any]:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        system_prompt = (
            f"你是一个严谨的中文私人秘书，现在时间是 {now_str}。\n"
            "用户会用自然语言描述自己的计划或想法，请判断是否需要创建一条任务。\n"
            "任务类型：todo/reminder/days/annis/none。\n"
            "输出 JSON：{\"action\": \"todo\"|\"reminder\"|\"days\"|\"annis\"|\"none\", \"title\": str, \"note\": str, \"datetime\": str|null, \"date\": str|null, \"tags\": [str]}"
        )

        res = await self._call_gpt(system_prompt, text, task="task")
        if not res or not isinstance(res, dict) or "error" in res:
            log.error("AI owner-intent analysis failed: %s", res)
            return {"action": "none", "title": "", "note": "", "datetime": None, "date": None, "tags": []}

        res.setdefault("action", "none")
        res.setdefault("title", "")
        res.setdefault("note", "")
        res.setdefault("datetime", None)
        res.setdefault("date", None)
        res.setdefault("tags", [])

        if not isinstance(res["tags"], list):
            res["tags"] = [str(res["tags"])]

        return res

    # ========== Owner Task Management (create / update / delete / list) ==========

    async def manage_tasks_from_chat(
        self,
        text: str,
        todos: List[dict],
        reminders: List[dict],
        days: Optional[List[dict]] = None,
        annis: Optional[List[dict]] = None,
    ) -> Dict[str, Any]:
        days = days or []
        annis = annis or []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        context_obj = {
            "todos": [{"id": t.get("id"), "title": t.get("title")} for t in todos],
            "reminders": [
                {"id": r.get("id"), "title": r.get("title"), "time": r.get("datetime")}
                for r in reminders
            ],
            "days": [
                {"id": d.get("id"), "title": d.get("title"), "date": d.get("date") or d.get("datetime")}
                for d in days
            ],
            "annis": [
                {"id": a.get("id"), "title": a.get("title"), "date": a.get("date") or a.get("datetime")}
                for a in annis
            ],
        }
        context_str = json.dumps(context_obj, ensure_ascii=False)

        system_prompt = (
            f"你是一个会直接操作数据库的中文私人秘书助手，现在时间是 {now_str}。\n"
            f"下面是当前已经存在的任务列表（仅供参考，不要重复创建）：\n{context_str}\n\n"
            "把用户任务管理请求转化为结构化操作。\n"
            "支持 target: todo/reminder/days/annis。支持 op: create/update/delete/list。\n"
            "输出 JSON：{\"ok\": bool, \"operations\": [{\"op\": str, \"target\": str, \"id\": int|null, \"data\": object}], \"reply_text\": str}"
        )

        res = await self._call_gpt(system_prompt, text, task="task")
        if not res or not isinstance(res, dict) or "error" in res:
            log.error("AI manage-tasks analysis failed: %s", res)
            return {"ok": False, "operations": [], "reply_text": "AI 解析失败，未对任务做任何修改。"}

        res.setdefault("ok", False)
        res.setdefault("operations", [])
        res.setdefault("reply_text", "")

        if not isinstance(res["operations"], list):
            res["operations"] = []

        return res

    # ========== Greeting Generation ==========

    async def generate_greeting(self, event_name: str) -> str:
        system_prompt = (
            "你是一个文艺但不过分矫情的中文文案助手。\n"
            "为指定的节日或纪念日生成一条适合作为 Telegram 早安通知的问候语。\n"
            "风格温暖、简洁、有一点美感，不要太长。\n"
            "输出 JSON：{\"text\": \"...\"}"
        )

        result = await self._call_gpt(system_prompt, event_name, task="chat")
        if not result or "error" in result:
            log.error("AI greeting generation failed: %s", result)
            return f"祝你 {event_name} 快乐。"

        text = result.get("text") or ""
        return text.strip() or f"祝你 {event_name} 快乐。"

    # ========== Image Analysis (Vision) ==========

    async def analyze_image(self, image_path: str, caption: str | None = None) -> Dict[str, Any]:
        if self._provider == "anthropic":
            return {
                "summary": "当前 Anthropic Vision 通道尚未启用。",
                "tags": [],
                "risk": "unknown",
                "error": "Anthropic vision is not implemented in this bot yet.",
            }

        if not self._openai_like_client:
            return {"error": "Vision currently requires an OpenAI-compatible provider"}

        try:
            with open(image_path, "rb") as file_obj:
                base64_image = base64.b64encode(file_obj.read()).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            log.error("Image read failed: %s", exc)
            return {"error": f"Image read failed: {exc}"}

        system_prompt = (
            "You are a helpful assistant analyzing images sent to a Telegram bot.\n"
            "Respond in Chinese.\n"
            "Return JSON: {\"summary\": str, \"tags\": [str], \"risk\": \"safe\"|\"nsfw\"|\"sensitive\"}"
        )

        user_content = [
            {"type": "text", "text": caption or "请帮我分析这张图片。"},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
        ]

        retries = max(0, settings.AI_RETRY_TIMES)
        for attempt in range(retries + 1):
            try:
                response = self._openai_like_client.chat.completions.create(
                    model=settings.get_model_for_task("vision"),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    temperature=settings.AI_TEMPERATURE,
                    response_format={"type": "json_object"},
                )
                content = response.choices[0].message.content or ""
                data = self._extract_json_object(content)
                tags = data.get("tags") or []
                if not isinstance(tags, list):
                    tags = [str(tags)]
                return {
                    "summary": data.get("summary") or "未能识别图片内容。",
                    "tags": [str(tag) for tag in tags],
                    "risk": data.get("risk") or "safe",
                }
            except Exception as exc:  # noqa: BLE001
                if attempt >= retries:
                    log.error("Vision API Error: %s", exc)
                    return {
                        "summary": "图片分析失败。",
                        "tags": [],
                        "risk": "unknown",
                        "error": str(exc),
                    }
                await asyncio.sleep(0.6 * (attempt + 1))

        return {"summary": "图片分析失败。", "tags": [], "risk": "unknown"}

    # ========== Simple Chat Reply (for Chat Mode) ==========

    async def chat_reply(self, user_text: str) -> str:
        has_client = self._anthropic_client is not None if self._provider == "anthropic" else self._openai_like_client is not None
        if not has_client:
            return "⚠️ 当前未配置 AI Provider API Key，无法进行 AI 对话。"

        system_prompt = (
            "You are AtriolyTgbot's private chat assistant.\n"
            "Try to reply in the same language as the user.\n"
            "答案要简洁、有条理，可以使用少量 Markdown，但不要输出 JSON，直接给出自然语言回复。"
        )

        content = await self._call_text(system_prompt, user_text, max_tokens=800, task="chat")
        return content or "⚠️ 调用 AI 聊天接口失败，请稍后再试。"


agent = AIAgent()
