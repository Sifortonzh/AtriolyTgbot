import logging
import os
import re
import html
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ApplicationHandlerStop

from src.config import settings
from src.services.ai_agent import agent
from src.services.safety import safety_filter
from src.services.blacklist_manager import blacklist
from src.services.private_contacts import private_contacts
from src.services.private_threads import private_threads
from src.services.state_manager import state_manager
from src.services.task_manager import task_manager  # NEW

# Setup Logger
log = logging.getLogger(__name__)


def _safe_original_message_link(msg) -> str | None:
    try:
        link = getattr(msg, "link", None)
        if link:
            return str(link)
    except Exception:
        return None
    return None


def _format_price_line(analysis: dict) -> str:
    price = analysis.get("price")
    currency = str(analysis.get("currency") or "").upper()
    if price in (None, ""):
        return "—"

    if currency == "CNY":
        currency_prefix = "¥"
    elif currency == "USD":
        currency_prefix = "$"
    else:
        currency_prefix = ""

    price_text = f"{price}" if isinstance(price, (int, float)) else str(price)
    suffix = " / month"
    return f"{currency_prefix}{html.escape(price_text)}{suffix}"


def build_membership_report_card(update: Update, analysis: dict) -> tuple[str, InlineKeyboardMarkup]:
    msg = update.effective_message
    user = update.effective_user

    platform = html.escape(str(analysis.get("platform") or "Unknown"))
    intent = html.escape(str(analysis.get("intent") or "Unknown").capitalize())
    risk = html.escape(str(analysis.get("risk_score") if analysis.get("risk_score") is not None else "—"))
    confidence_value = analysis.get("confidence")
    if isinstance(confidence_value, (int, float)):
        confidence = f"{confidence_value:.2f}"
    elif confidence_value is None:
        confidence = "—"
    else:
        confidence = str(confidence_value)
    confidence = html.escape(confidence)

    summary = html.escape(str(analysis.get("summary") or "No details"))
    price_line = _format_price_line(analysis)

    sender_name = "Unknown"
    sender_id = "unknown"
    sender_profile_url = None
    if user:
        sender_name = user.full_name or "Unknown"
        sender_id = str(user.id)
        sender_profile_url = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"

    sender_html = html.escape(sender_name)
    sender_line = f"👤 Sender: {sender_html}"
    if settings.ENABLE_SENDER_PROFILE_LINK and sender_profile_url:
        sender_line = f"👤 Sender: <a href=\"{html.escape(sender_profile_url)}\">{sender_html}</a>"

    original_link = _safe_original_message_link(msg)
    if original_link:
        original_line = f"🔗 Original Message: <a href=\"{html.escape(original_link)}\">Open</a>"
    else:
        original_line = "🔗 Original Message: unavailable"

    card_text = (
        "💠 <b>Verified Opportunity</b>\n\n"
        f"🎬 Platform: {platform}\n"
        f"💰 Price: {price_line}\n"
        f"🧭 Intent: {intent}\n"
        f"⚠️ Risk: {risk} / 100\n"
        f"📊 Confidence: {confidence}\n\n"
        f"📝 Summary: {summary}\n\n"
        f"{sender_line}\n"
        f"🆔 User ID: {html.escape(sender_id)}\n"
        f"{original_line}"
    )

    callback_uid = sender_id if sender_id.isdigit() else "0"
    callback_mid = str(msg.message_id if msg else 0)
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Save", callback_data=f"report:save:{callback_uid}:{callback_mid}"),
                InlineKeyboardButton("🚫 Blacklist", callback_data=f"report:blacklist:{callback_uid}:{callback_mid}"),
            ],
            [
                InlineKeyboardButton("👁 View Sender", url=sender_profile_url or f"tg://user?id={callback_uid}"),
                InlineKeyboardButton("📝 Add Note", callback_data=f"report:add_note:{callback_uid}:{callback_mid}"),
            ],
        ]
    )

    return card_text, keyboard


def _normalize_private_category(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    if value in {"membership_sharing", "membership"}:
        return "membership"
    if value in {"support", "billing", "general", "general_chat", "spam"}:
        return "general" if value == "general_chat" else value
    return "general"


def _derive_private_priority(category: str, analysis: dict) -> str:
    explicit = str(analysis.get("priority") or "").strip().lower()
    if explicit in {"normal", "high", "urgent"}:
        return explicit

    risk = analysis.get("risk_score")
    try:
        risk_num = int(risk) if risk is not None else None
    except (TypeError, ValueError):
        risk_num = None

    if risk_num is not None:
        if risk_num >= 85:
            return "urgent"
        if risk_num >= 60:
            return "high"

    if bool(analysis.get("is_spam")):
        return "urgent"
    if category in {"membership", "billing"}:
        return "high"
    return "normal"


def _private_thread_values(update: Update, analysis: dict) -> dict:
    msg = update.effective_message
    user = update.effective_user
    message_text = (msg.text or "") if msg else ""

    category = _normalize_private_category(analysis.get("category"))
    priority = _derive_private_priority(category, analysis)

    summary_raw = str(analysis.get("summary") or "").strip()
    if not summary_raw:
        summary_raw = message_text[:120] if message_text else "No summary"

    return {
        "category": category,
        "priority": priority,
        "summary_raw": summary_raw,
        "message_text": message_text,
    }


def build_private_service_card(
    update: Update,
    analysis: dict,
    owner_message_id: int = 0,
) -> tuple[str, InlineKeyboardMarkup]:
    msg = update.effective_message
    user = update.effective_user
    values = _private_thread_values(update, analysis)
    message_text = values["message_text"]
    preview = html.escape(message_text[:800]) if message_text else "(empty)"

    category = values["category"]
    priority = values["priority"]
    summary_raw = values["summary_raw"]
    summary = html.escape(summary_raw)

    sender_name = user.full_name if user and user.full_name else "Unknown"
    sender_name_html = html.escape(sender_name)
    sender_id = str(user.id) if user else "0"
    sender_url = (
        f"https://t.me/{user.username}" if user and user.username else f"tg://user?id={sender_id}"
    )

    sender_line = f"👤 Sender: {sender_name_html}"
    if settings.ENABLE_SENDER_PROFILE_LINK and user:
        sender_line = f"👤 Sender: <a href=\"{html.escape(sender_url)}\">{sender_name_html}</a>"

    card_text = (
        "📨 <b>Private Message</b>\n\n"
        f"{sender_line}\n"
        f"🆔 User ID: {html.escape(sender_id)}\n"
        f"🏷 Category: {html.escape(category)}\n"
        f"🧠 Priority: {html.escape(priority)}\n"
        f"📝 Summary: {summary}\n\n"
        "💬 Message:\n"
        f"{preview}"
    )

    callback_uid = sender_id if sender_id.isdigit() else "0"
    callback_mid = str(owner_message_id or (msg.message_id if msg else 0))
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("↩️ Reply Guide", callback_data=f"private:reply_guide:{callback_uid}:{callback_mid}"),
                InlineKeyboardButton("👁 View Sender", url=sender_url),
            ],
            [
                InlineKeyboardButton("💬 Ask Details", callback_data=f"private:ask_details:{callback_uid}:{callback_mid}"),
                InlineKeyboardButton("💰 Send Price", callback_data=f"private:send_price:{callback_uid}:{callback_mid}"),
            ],
            [
                InlineKeyboardButton("📦 Check Availability", callback_data=f"private:check_availability:{callback_uid}:{callback_mid}"),
                InlineKeyboardButton("🙏 Polite Reject", callback_data=f"private:polite_reject:{callback_uid}:{callback_mid}"),
            ],
            [
                InlineKeyboardButton("🚫 Blacklist", callback_data=f"private:blacklist:{callback_uid}:{callback_mid}"),
                InlineKeyboardButton("✅ Mark Resolved", callback_data=f"private:resolved:{callback_uid}:{callback_mid}"),
            ],
        ]
    )

    return card_text, keyboard


def _escape_markdown_text(text: str) -> str:
    """Escape Telegram Markdown (v1) special chars for link labels."""
    value = str(text or "")
    return re.sub(r"([_\*\[\]\(\)`])", r"\\\1", value)


def _build_sender_profile_lines(user) -> str:
    if not settings.ENABLE_SENDER_PROFILE_LINK or not user:
        return ""

    profile_url = f"https://t.me/{user.username}" if user.username else f"tg://user?id={user.id}"
    display_name = _escape_markdown_text(user.full_name or "Unknown")
    return f"👤 Sender: [{display_name}]({profile_url})\n🆔 User ID: {user.id}\n"

def _fmt_tags_hash(tags) -> str:
    """将标签列表/字符串统一转为 '#tag' 形式。"""
    if not tags:
        return "—"
    # 允许字符串或列表两种输入
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return " ".join(
        f"#{t.strip().replace(' ', '_')}"  # 空格换成下划线，避免分裂标签
        for t in tags
        if isinstance(t, str) and t.strip()
    )


async def gatekeeper_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    PRIORITY -1: Checks if user is banned.
    """
    user = update.effective_user
    if user and blacklist.is_banned(user.id):
        log.warning(f"🛑 Blocked interaction from banned user: {user.id} ({user.full_name})")
        raise ApplicationHandlerStop


async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message

    # Check if message exists (sometimes updates are just status changes)
    if not msg or not msg.text:
        return

    text = msg.text
    user = update.effective_user
    chat_title = update.effective_chat.title

    # --- DEBUG LOG: Message Receipt ---
    log.info(
        f"📩 GROUP MSG RECEIVED | Group: '{chat_title}' | "
        f"User: {user.full_name} | Text: '{text[:50]}...'"
    )

    # --- 1. Zero-Cost Safety Check ---
    if safety_filter.is_obvious_spam(text):
        log.info(f"🛡️ SPAM DETECTED (Layer 1) | Dropping message from {user.id}")
        return

    # --- 2. Relevance Trigger Check ---
    triggers = [
        "车", "合租", "会员", "Netflix", "奈飞", "Disney", "迪士尼",
        "YouTube", "HBO", "Prime", "sub", "share", "Apple", "Spotify",
    ]
    is_relevant_keyword = any(t.lower() in text.lower() for t in triggers)

    if not is_relevant_keyword:
        log.info("⏭️ SKIPPED (No Keyword) | Text did not contain membership keywords.")
        return
    else:
        log.info("✅ KEYWORD MATCHED | Proceeding to AI Analysis.")

    # --- 3. AI Analysis ---
    try:
        log.info("🧠 Sending to AI Agent for context analysis...")
        analysis = await agent.analyze_message(text)
        log.info(f"🧠 AI RESULT: {analysis}")
    except Exception as e:
        log.error(f"❌ AI ERROR: {e}")
        return

    # --- 4. Logic Branching ---

    # Branch A: Spam Enforcement
    if analysis.get("is_spam"):
        reason = analysis.get("spam_reason", "Spam detected")
        log.warning(f"🤖 AI SPAM DETECTED | Reason: {reason}")

        status = blacklist.add_strike(user.id)

        if status == "banned":
            await msg.reply_text(
                f"🚫 **System Alert**\nUser {user.mention_html()} has been banned.\nReason: {reason}",
                parse_mode="HTML",
            )
            log.info(f"🚫 User {user.id} BANNED.")
        elif status == "warned":
            count = blacklist.get_strike_count(user.id)
            await msg.reply_text(
                f"⚠️ **Warning ({count}/3)**\n{user.mention_html()}, message flagged: {reason}",
                parse_mode="HTML",
            )
            log.info(f"⚠️ User {user.id} WARNED.")
        return

    # Branch B: Membership Opportunity
    if analysis.get("is_membership"):
        platform = analysis.get("platform", "Unknown")

        log.info(f"💎 MEMBERSHIP FOUND | Platform: {platform} | Forwarding to admins...")
        alert_msg, alert_kb = build_membership_report_card(update, analysis)

        targets = settings.get_forward_targets()
        if not targets:
            log.warning("⚠️ No FORWARD_TO targets configured!")

        for admin in targets:
            try:
                await context.bot.send_message(
                    chat_id=admin,
                    text=alert_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=alert_kb,
                    disable_web_page_preview=True,
                )
                log.info(f"🚀 Sent alert to Admin ID: {admin}")
            except Exception as e:
                log.error(f"❌ Failed to forward to {admin}: {e}")
    else:
        log.info("📉 AI determined message was NOT a membership offer.")


# --- Private Logic (Owner Secretary + User Support) ---
async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    私聊逻辑分两部分：
    1. Owner：进入“私人秘书模式”，由 AI 自动解析为 todo/reminder/days/annis，并写入 task_manager。
    2. 普通用户：走原有的 AI 分类 + 转发给管理员 + 回复桥接逻辑。
    """
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return

    text = msg.text or ""

    # 0. Safety Check
    if safety_filter.is_obvious_spam(text):
        if user.id not in settings.OWNER_IDS:
            private_contacts.upsert_from_user(
                user,
                category="spam",
                priority="urgent",
                summary=text[:120],
            )
        return

    mode = state_manager.get_mode(user.id)

    # --- 1. Owner Secretary Mode ---
    if user.id in settings.OWNER_IDS:
        log.info(f"Owner private message in mode: {mode}")

        # CHAT mode for owner: pure AI chat, no task parsing
        if mode == "chat":
            try:
                reply_text = await agent.chat_reply(text)
            except Exception as e:
                log.error(f"❌ chat_reply failed for owner {user.id}: {e}")
                reply_text = "⚠️ AI 聊天暂时不可用，请稍后再试。"
            await msg.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
            return
        else:
            intent = await agent.analyze_owner_intent(text)
            action = intent.get("action", "none")

            if action != "none":
                # 写入任务系统（创建 todo/reminder/days/annis）
                try:
                    task_manager.add_entry(action, intent)
                except Exception as e:
                    log.error(f"❌ task_manager.add_entry failed: {e}")
                    await msg.reply_text(f"⚠️ 创建 {action} 时出错：{e}")
                    return

                raw_tags = intent.get("tags", [])
                tags_str = _fmt_tags_hash(raw_tags)

                reply = (
                    f"✅ **Created {action.upper()}**\n"
                    f"📌 {intent.get('title') or 'No title'}\n"
                    f"🕒 {intent.get('datetime') or 'N/A'}\n"
                    f"🏷 {tags_str}"
                )
                await msg.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
                return

            # action == 'none'：进入“任务管理模式”（更新 / 删除 / 列出）
            try:
                todos = task_manager.get_entries("todo")
                reminders = task_manager.get_entries("reminder")
                days = task_manager.get_entries("days")
                annis = task_manager.get_entries("annis")
            except Exception as e:
                log.error(f"❌ Failed to load task lists for manage_tasks_from_chat: {e}")
                await msg.reply_text("⚠️ 读取任务列表失败，暂时无法进行管理操作。")
                return

            manage_res = await agent.manage_tasks_from_chat(
                text,
                todos=todos,
                reminders=reminders,
                days=days,
                annis=annis,
            )

            if not manage_res.get("ok"):
                # AI 未能可靠解析当前指令
                log.warning(f"manage_tasks_from_chat returned not ok: {manage_res}")
                await msg.reply_text("🤖 没有完全理解这条任务管理指令，未对现有任务做修改。")
                return

            ops = manage_res.get("operations", [])
            for op in ops:
                op_type = op.get("op")
                target = op.get("target")
                if target not in ("todo", "reminder", "days", "annis"):
                    continue

                if op_type == "create":
                    data = op.get("data") or {}
                    try:
                        task_manager.add_entry(target, data)
                    except Exception as e:
                        log.error(f"❌ add_entry failed in manage_tasks_from_chat: {e}")
                elif op_type == "update":
                    entry_id = op.get("id")
                    data = op.get("data") or {}
                    if entry_id is not None:
                        try:
                            task_manager.update_entry(target, entry_id, data)
                        except Exception as e:
                            log.error(f"❌ update_entry failed in manage_tasks_from_chat: {e}")
                elif op_type == "delete":
                    entry_id = op.get("id")
                    if entry_id is not None:
                        try:
                            task_manager.delete_entry(target, entry_id)
                        except Exception as e:
                            log.error(f"❌ delete_entry failed in manage_tasks_from_chat: {e}")
                else:
                    # 'list' 或其他无状态操作，不需要直接改数据库
                    continue

            reply_text = manage_res.get("reply_text") or "已根据你的指令更新任务。"
            await msg.reply_text(f"🤖 {reply_text}")
            return

    # --- 2. 普通用户：根据 mode 切换 Chat / Forward ---

    log.info(f"Private message mode for user {user.id}: {mode}")

    # 2.1 Chat 模式：仅 owner 使用；普通私聊用户保持转人工转发。
    if mode == "chat":
        log.info("Forcing non-owner private user %s to forward mode.", user.id)

    # 2.2 Forward 模式（默认）：先做 AI 分类，再转发给管理员
    analysis = await agent.analyze_private_message(text)

    values = _private_thread_values(update, analysis)
    private_contacts.upsert_from_user(
        user,
        category=values["category"],
        priority=values["priority"],
        summary=values["summary_raw"],
    )

    # Spam Enforcement
    if analysis.get("is_spam"):
        status = blacklist.add_strike(user.id)
        if status == "banned":
            await msg.reply_text("🚫 You have been banned for spam.")
        return

    header, _ = build_private_service_card(update, analysis)

    targets = settings.get_forward_targets()
    delivered = False
    for admin_id in targets:
        try:
            # Header
            header_msg = await context.bot.send_message(
                chat_id=admin_id,
                text=header,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True,
            )
            _, updated_kb = build_private_service_card(update, analysis, owner_message_id=header_msg.message_id)
            try:
                await header_msg.edit_reply_markup(reply_markup=updated_kb)
            except Exception as edit_error:  # noqa: BLE001
                log.warning("Failed to update private card callback IDs: %s", edit_error)

            # Forward 原始消息（保留上下文 / 媒体）
            fwd_msg = await context.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=user.id,
                message_id=msg.message_id,
            )
            # 注册回复桥接
            state_manager.register_forward(header_msg.message_id, user.id)
            state_manager.register_forward(fwd_msg.message_id, user.id)
            private_threads.add_or_update(
                user_id=user.id,
                user_name=user.full_name or "Unknown",
                username=user.username,
                category=values["category"],
                priority=values["priority"],
                summary=values["summary_raw"],
                message_preview=values["message_text"],
                owner_message_id=header_msg.message_id,
                user_message_id=msg.message_id,
            )
            delivered = True

        except Exception as e:
            log.error(f"Failed to forward DM to {admin_id}: {e}")

    if delivered:
        await msg.reply_text(
            "✅ 已收到你的消息，Wanatring 已悄悄递给主人啦 📨\n"
            "先喝口水等一等，他看到后会尽快回你～ 🌿"
        )
    else:
        await msg.reply_text(
            "⚠️ 消息刚才没能送给主人。\n"
            "可以稍后再试一次，或者换个方式联系他～ 🍃"
        )


# --- Admin Reply Logic (The Bridge) ---
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    管理员在私聊里回复转发消息时，Bot 会把这条回复再转发回原始用户。
    """
    msg = update.effective_message
    user = update.effective_user
    if not msg or not user:
        return

    # 1. 安全：只有 OWNER 允许使用这一桥接功能
    if user.id not in settings.OWNER_IDS:
        return

    # 2. 必须是针对某条消息的回复
    if not msg.reply_to_message:
        return

    # 3. 查找原始发送者
    original_user_id = state_manager.get_original_sender(msg.reply_to_message.message_id)
    if not original_user_id:
        await msg.reply_text("⚠️ 这条消息没有关联到有效的私聊用户，无法转发。")
        return

    # 4. 回发给原始用户
    try:
        await context.bot.send_message(chat_id=original_user_id, text=msg.text)
        await msg.reply_text("✅ 回复已送达给用户。")
    except Exception as e:
        log.error("Failed to relay owner reply to user_id=%s: %s", original_user_id, e, exc_info=e)
        await msg.reply_text(
            "⚠️ 回复未能送达。\n"
            "可能原因：用户阻止了 Bot、映射已过期，或这条消息不是有效的私聊转发记录。"
        )
