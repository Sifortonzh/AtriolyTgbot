import json
import logging
import base64
from typing import Dict, Any, List, Optional
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
    - Task management from chat (create / update / delete / list)
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
                # 要求 JSON 输出，方便后续解析
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
        if not self.client:
            return {
                "is_spam": False,
                "is_membership": False,
                "error": "No API Key configured",
            }

        if len(text) < 2:
            return {
                "is_spam": True,
                "spam_reason": "Too short",
                "is_membership": False,
            }

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
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        except Exception as e:
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
        """
        if not self.client:
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

        if "error" in result:
            log.error(f"❌ AI Analysis Failed (private): {result['error']}")
            return {
                "is_spam": False,
                "category": "other",
                "tags": [],
                "summary": "AI error; fallback classification.",
                "error": result["error"],
            }

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
        分析 Owner 发来的“一句话”，判断是否需要创建任务：
        - 'todo'     : 普通待办
        - 'reminder' : 带具体时间点的提醒
        - 'days'     : 一次性的特殊日子/倒计时
        - 'annis'    : 纪念日（生日、周年）
        - 'none'     : 不创建任务

        返回示例：
        {
          "action": "todo" | "reminder" | "days" | "annis" | "none",
          "title": "字符串标题",
          "note": "补充说明",
          "datetime": "YYYY-MM-DD HH:MM" 或 null,
          "date": "YYYY-MM-DD" 或 null,
          "tags": ["标签1", "标签2"]
        }
        """
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        system_prompt = (
            f"你是一个严谨的中文私人秘书，现在时间是 {now_str}。\n"
            "用户会用自然语言描述自己的计划或想法，请你判断这句话是否需要“创建一条任务”。\n"
            "任务类型说明：\n"
            "1) 'todo'：普通待办，没有明确的具体时间点，只是要做的事情。\n"
            "2) 'reminder'：在某个具体时间点需要提醒的事件（例如“明天早上 9 点提醒我复习心内科”）。\n"
            "3) 'days'：某个一次性的特殊日子/倒计时（例如“6 月 20 号考研初试那天记一下”）。\n"
            "4) 'annis'：纪念日/重复有意义的日子（例如“我的生日是 5 月 6 号，帮我记一下”）。\n"
            "5) 'none'：只是正常聊天或者跟任务无关，不需要创建任何记录。\n\n"
            "如果需要创建任务，请帮我结构化信息。\n"
            "输出一个 JSON，格式为：\n"
            "{\n"
            "  'action': 'todo' | 'reminder' | 'days' | 'annis' | 'none',\n"
            "  'title': '简短标题，10~30 字为宜',\n"
            "  'note': '补充说明，可以为空字符串',\n"
            "  'datetime': 'YYYY-MM-DD HH:MM' 或 null,   # 对于 reminder 使用\n"
            "  'date': 'YYYY-MM-DD' 或 null,             # 对于 days / annis 使用\n"
            "  'tags': ['标签1', '标签2']                 # 简短标签数组，例如 ['study','exam']\n"
            "}\n"
            "注意：\n"
            "- 如果判断是 'none'，其他字段可以给空字符串或 null 即可。\n"
            "- 如果是 'todo'，可以只填 title 和 note，datetime/date 可以为 null。\n"
            "- 如果用户没有给出明确时间，但明显是提醒类，也可以尝试根据语义推断一个合理时间。"
        )

        res = await self._call_gpt(system_prompt, text, model=settings.DEFAULT_MODEL)
        if not res or not isinstance(res, dict) or "error" in res:
            log.error(f"❌ AI owner-intent analysis failed: {res}")
            return {"action": "none"}

        res.setdefault("action", "none")
        res.setdefault("title", "")
        res.setdefault("note", "")
        res.setdefault("datetime", None)
        res.setdefault("date", None)
        res.setdefault("tags", [])

        # tags 兜底成 list
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
        """
        上下文感知的任务管理：
        - 支持四种 target: 'todo' | 'reminder' | 'days' | 'annis'
        - 支持四种 op: 'create' | 'update' | 'delete' | 'list'
        返回结构：
        {
          "ok": bool,
          "operations": [
            {
              "op": "create" | "update" | "delete" | "list",
              "target": "todo" | "reminder" | "days" | "annis",
              "id": int 或 null,
              "data": { ... 需要写入的字段 ... }
            },
            ...
          ],
          "reply_text": "给用户看的自然语言说明"
        }
        """
        if days is None:
            days = []
        if annis is None:
            annis = []

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        context_obj = {
            "todos": [
                {"id": t.get("id"), "title": t.get("title")}
                for t in todos
            ],
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
            f"下面是当前已经存在的任务列表（仅供参考，不要重复创建）：\n"
            f"{context_str}\n\n"
            "用户会用中文跟你说一些“管理任务”的话，你需要把它们转化为一组结构化的操作。\n"
            "支持的 target 类型：'todo' | 'reminder' | 'days' | 'annis'。\n"
            "支持的 op 类型：\n"
            "- create：创建新任务\n"
            "- update：根据 id 更新已有任务\n"
            "- delete：根据 id 删除已有任务\n"
            "- list  ：仅用于查询，不修改任何数据\n\n"
            "每条操作的 JSON 格式为：\n"
            "  {\n"
            "    'op': 'create'|'update'|'delete'|'list',\n"
            "    'target': 'todo'|'reminder'|'days'|'annis',\n"
            "    'id': 整数 或 null,            # create 可以是 null，其他必须有\n"
            "    'data': {\n"
            "       'title': str 或 null,\n"
            "       'note': str 或 null,\n"
            "       'datetime': 'YYYY-MM-DD HH:MM' 或 null,  # reminder 或特殊需要\n"
            "       'date': 'YYYY-MM-DD' 或 null,            # days / annis 使用\n"
            "       'tags': [str] 或 null\n"
            "    }\n"
            "  }\n\n"
            "整体输出一个 JSON：\n"
            "{\n"
            "  'ok': true 或 false,\n"
            "  'operations': [ 上述操作对象数组 ],\n"
            "  'reply_text': '给用户的中文说明，比如“已新增 1 条提醒，已删除 2 条 todo”'\n"
            "}\n"
            "注意：\n"
            "- 如果用户只是闲聊，不涉及任务，请返回 ok=false，operations 为空数组，reply_text 简短说明即可；\n"
            "- id 只能使用 context 里已经存在的 id，不要自己杜撰新的 id；\n"
            "- 如果用户说“把刚才那个 xxx 删掉”，请根据最相近的 title 去匹配已有任务，然后给出 delete 操作。"
        )

        res = await self._call_gpt(system_prompt, text, model=settings.DEFAULT_MODEL)
        if not res or not isinstance(res, dict) or "error" in res:
            log.error(f"❌ AI manage-tasks analysis failed: {res}")
            return {"ok": False, "operations": [], "reply_text": "AI 解析失败，未对任务做任何修改。"}

        res.setdefault("ok", False)
        res.setdefault("operations", [])
        res.setdefault("reply_text", "")

        if not isinstance(res["operations"], list):
            res["operations"] = []

        return res

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

    # ========== Image Analysis (Vision) ==========

    async def analyze_image(self, image_path: str, caption: str | None = None) -> Dict[str, Any]:
        """
        使用 GPT-4o 对图片进行分析：
        返回结构示例：
        {
          'summary': '对图片内容的一两句中文描述',
          'tags': ['tag1', 'tag2'],
          'risk': 'safe' | 'nsfw' | 'sensitive'
        }
        """
        if not self.client:
            return {"error": "No API Key configured"}

        try:
            with open(image_path, "rb") as f:
                base64_image = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            log.error(f"❌ Image read failed: {e}")
            return {"error": f"Image read failed: {e}"}

        system_prompt = (
            "You are a helpful assistant analyzing images sent to a Telegram bot.\n"
            "Respond in Chinese.\n"
            "1. SUMMARIZE: Describe the image in 1-2 concise Chinese sentences.\n"
            "2. TAGS: Provide 2-4 short tags (single words or short phrases) about the content.\n"
            "3. RISK: One of 'safe', 'nsfw', or 'sensitive'.\n"
            "Output JSON exactly like:\n"
            "{"
            "  'summary': str,"
            "  'tags': [str],"
            "  'risk': 'safe'|'nsfw'|'sensitive'"
            "}"
        )

        user_content = [
            {"type": "text", "text": caption or "请帮我分析这张图片。"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            },
        ]

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            data = json.loads(content)
        except Exception as e:
            log.error(f"❌ Vision API Error: {e}")
            return {
                "summary": "图片分析失败。",
                "tags": [],
                "risk": "unknown",
                "error": str(e),
            }

        # 兜底字段
        summary = data.get("summary") or "未能识别图片内容。"
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [str(tags)]
        risk = data.get("risk") or "safe"

        return {
            "summary": summary,
            "tags": tags,
            "risk": risk,
        }

    # ========== Simple Chat Reply (for Chat Mode) ==========

    async def chat_reply(self, user_text: str) -> str:
        """
        Chat 模式下的简单对话接口：
        - 不要求 JSON 输出，直接返回一段自然语言文本。
        - 尽量用用户的语言回复（中/英均可）。
        """
        if not self.client:
            return "⚠️ 当前未配置 OpenAI API Key，无法进行 AI 对话。"

        system_prompt = (
            "You are AtriolyTgbot's private chat assistant.\n"
            "Try to reply in the same language as the user.\n"
            "答案要简洁、有条理，可以使用少量 Markdown（如列表、加粗），"
            "但不要输出 JSON 或代码块，直接给出自然语言回复。"
        )

        try:
            response = self.client.chat.completions.create(
                model=settings.DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            log.error(f"❌ Chat reply failed: {e}")
            return "⚠️ 调用 AI 聊天接口失败，请稍后再试。"


agent = AIAgent()
