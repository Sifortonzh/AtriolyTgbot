import json
import logging
from typing import Dict, Any
from datetime import datetime

from openai import OpenAI
from src.config import settings

log = logging.getLogger(__name__)


class AIAgent:
    """
    Unified AI agent for:
    - Group messages: SPAM + Streaming Membership detection
    - Private messages: Category + Tags + Summary + Spam
    - Owner intent parsing: todo / reminder / days / annis / none
    - Greeting generation for festivals / anniversaries
    """

    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

    # ========== Common Helper ==========

    async def _call_gpt(
        self,
        system_prompt: str,
        user_text: str,
        model: str | None = None,
    ) -> Dict[str, Any]:
        """
        Helper to call OpenAI and parse JSON.
        Returns a dict; if error, it will contain {"error": "..."}.
        """
        if not self.client:
            return {"error": "No API Key configured"}

        try:
            response = self.client.chat.completions.create(
                model=model or settings.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                # 强制要求 JSON 输出，方便后续解析
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            log.error(f"❌ AI call failed: {e}")
            return {"error": str(e)}

    # ========== Group Logic (Streaming + Spam) ==========

    async def analyze_message(self, text: str) -> Dict[str, Any]:
        """
        分析【群消息】：
        - is_spam: bool
        - spam_reason: str | null
        - is_membership: bool
        - platform: str | null
        - summary: str
        """
        # 1) 无 API Key 时的兜底
        if not self.client:
            return {
                "is_spam": False,
                "is_membership": False,
                "error": "No API Key configured",
            }

        # 2) 简单启发式：太短直接当垃圾
        if len(text) < 2:
            return {
                "is_spam": True,
                "spam_reason": "Too short",
                "is_membership": False,
            }

        # 3) 系统提示词：合租嗅探 + Spam 检测
        system_prompt = (
            "You are the Atrioly Intelligent Filter. Your goal is to detect Streaming Membership Sharing.\n"
            "1. SECURITY: Detect SPAM (phishing, crypto, ads, NSFW, scam links, bot spam).\n"
            "2. INTELLIGENCE: Focus on streaming memberships: Netflix, HBO, Disney+, YouTube, Spotify, Apple TV, etc.\n"
            "   - Look for INTENT: 'Offering a slot' (招租/出车位/有车位), "
            "     'Requesting a slot' (求租/上车/有没有位置), 'Group buy' (拼车/合租).\n"
            "   - Keywords: 'Netflix', 'HBO', 'Disney', '上车', '合租', '车位', "
            "     '拼车', '长期', '月付', '季付', '年付'.\n"
            "3. If the message implies looking for or offering a shared account, set 'is_membership': true.\n\n"
            "Output PURE JSON exactly as:\n"
            "{"
            "  'is_spam': bool,"
            "  'spam_reason': str | null,"
            "  'is_membership': bool,"
            "  'platform': str | null,"
            "  'summary': str"
            "}"
        )

        try:
            result = await self._call_gpt(system_prompt, text)

            # 如果 _call_gpt 本身失败（返回 error），走兜底逻辑
            if "error" in result:
                raise RuntimeError(result["error"])

            return result

        except Exception as e:
            # --- FAIL-SAFE 兜底：关键词匹配 ---
            log.error(f"❌ AI Analysis Failed (group): {e}")
            keywords = ["hbo", "netflix", "disney", "share", "上车", "合租", "车位"]
            if any(k in text.lower() for k in keywords):
                log.warning(
                    "⚠️ AI failed, but membership keywords detected. Fallback to manual flag."
                )
                return {
                    "is_spam": False,
                    "is_membership": True,
                    "platform": "Unknown (AI Fail)",
                    "summary": f"AI error: {str(e)}. Keywords detected in text.",
                }

            return {
                "is_spam": False,
                "is_membership": False,
                "error": str(e),
            }

    # ========== Private Logic (DM 分类 / 标签 / Summary) ==========

    async def analyze_private_message(self, text: str) -> Dict[str, Any]:
        """
        分析【私聊消息】：
        - category: membership_sharing / general_chat / support / billing / other
        - tags: 1–3 个短标签
        - summary: 给管理员看的简短摘要
        - is_spam: 是否明显垃圾

        返回 JSON：
        {
          "is_spam": bool,
          "category": str,
          "tags": [str],
          "summary": str
        }
        """
        if not self.client:
            # 没有 API Key 时，简单兜底：当普通聊天 + 非 spam
            return {
                "is_spam": False,
                "category": "general_chat",
                "tags": [],
                "summary": "AI disabled (no API key).",
                "error": "No API Key configured",
            }

        system_prompt = (
            "You are Atrioly's Service Desk AI. Analyze this private message.\n"
            "1. CLASSIFY: Category must be one of: "
            "   'membership_sharing', 'general_chat', 'support', 'billing', 'other'.\n"
            "2. TAG: Generate 1-3 short tags (e.g., 'Netflix', 'Urgent', 'Bug').\n"
            "3. SUMMARIZE: One concise sentence summary for the admin.\n"
            "4. SPAM CHECK: Is this obvious spam? (crypto scams, ads, bots, phishing, etc.).\n"
            "Output JSON EXACTLY in this shape:\n"
            "{"
            "  'is_spam': bool,"
            "  'category': str,"
            "  'tags': [str],"
            "  'summary': str"
            "}"
        )

        result = await self._call_gpt(system_prompt, text)

        # 给一点默认兜底，防止模型没完全遵守 schema
        if "error" in result:
            log.error(f"❌ AI Analysis Failed (private): {result['error']}")
            return {
                "is_spam": False,
                "category": "other",
                "tags": [],
                "summary": "AI error; fallback classification.",
                "error": result["error"],
            }

        # 保守校验字段，缺啥就补默认值，避免上层代码 KeyError
        is_spam = bool(result.get("is_spam", False))
        category = result.get("category") or "other"
        tags = result.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        summary = result.get("summary") or "No summary."

        return {
            "is_spam": is_spam,
            "category": category,
            "tags": tags,
            "summary": summary,
        }

    # ========== Owner Intent (todo / reminder / days / annis) ==========

    async def analyze_owner_intent(self, text: str) -> Dict[str, Any]:
        """
        分析 Owner 发送的自然语言，判断是否需要转成：
        - todo
        - reminder
        - days
        - annis
        - none（无动作）

        期望返回结构示例：
        {
          "action": "todo" | "reminder" | "days" | "annis" | "none",
          "title": "字符串标题",
          "note": "补充说明",
          "datetime": "ISO8601 字符串或 null",
          "tags": ["#todo"]
        }
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_prompt = (
            f"You are a meticulous personal secretary. Current time: {now_str}.\n"
            "Analyze the user's Chinese message and decide whether it should become a task.\n"
            "Categories:\n"
            "- 'todo': General task (no precise time required or just a rough date).\n"
            "- 'reminder': One-off alert at a specific time.\n"
            "- 'days': Special day / countdown type event.\n"
            "- 'annis': Recurring anniversary (yearly meaningful date).\n"
            "- 'none': Casual chat or irrelevant, do NOT create anything.\n\n"
            "When you DO create something, extract:\n"
            "- title: short, suitable as task title.\n"
            "- note: optional extra note or details.\n"
            "- datetime: ISO8601 string if there is a clear execution/alert time, otherwise null.\n"
            "- tags: 1-3 short tags like '#todo', '#reminder', '#study'.\n\n"
            "Output strict JSON:\n"
            "{\n"
            "  \"action\": \"todo\"|\"reminder\"|\"days\"|\"annis\"|\"none\",\n"
            "  \"title\": \"...\",\n"
            "  \"note\": \"...\",\n"
            "  \"datetime\": \"YYYY-MM-DDTHH:MM\" or null,\n"
            "  \"tags\": [\"...\"]\n"
            "}"
        )

        result = await self._call_gpt(system_prompt, text)

        if not result or "error" in result:
            # 出错或模型没返回有效结构时，默认不做处理
            log.error(f"❌ AI owner-intent analysis failed: {result}")
            return {"action": "none"}

        # 最起码保证 action 字段存在
        action = result.get("action") or "none"
        title = result.get("title") or ""
        note = result.get("note") or ""
        dt = result.get("datetime", None)
        tags = result.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]

        return {
            "action": action,
            "title": title,
            "note": note,
            "datetime": dt,
            "tags": tags,
        }

    # ========== Greeting Generation ==========

    async def generate_greeting(self, event_name: str) -> str:
        """
        为节日 / 纪念日生成一条简短、文艺的中文问候语。
        返回纯文本字符串。
        """
        system_prompt = (
            "你是一个文艺但不过分矫情的中文文案助手。\n"
            "为指定的节日或纪念日生成一条适合作为 Telegram 早安通知的问候语：\n"
            "- 风格温暖、简洁、有一点美感。\n"
            "- 不要太长，控制在一两句话之内。\n"
            "- 不要使用表情符号以外的复杂格式。\n"
            "输出 JSON：{\"text\": \"...\"}"
        )

        result = await self._call_gpt(system_prompt, event_name)

        if not result or "error" in result:
            log.error(f"❌ AI greeting generation failed: {result}")
            return f"祝你 {event_name} 快乐。"

        text = result.get("text") or ""
        if not text.strip():
            return f"祝你 {event_name} 快乐。"
        return text.strip()


agent = AIAgent()
