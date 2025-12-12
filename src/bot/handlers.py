import logging
import os
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ApplicationHandlerStop

from src.config import settings
from src.services.ai_agent import agent
from src.services.safety import safety_filter
from src.services.blacklist_manager import blacklist
from src.services.state_manager import state_manager
from src.services.task_manager import task_manager  # NEW

# Setup Logger
log = logging.getLogger(__name__)

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
        summary = analysis.get("summary", "No details")

        log.info(f"💎 MEMBERSHIP FOUND | Platform: {platform} | Forwarding to admins...")

        alert_msg = (
            f"💠 **Verified Opportunity**\n"
            f"🎬 **Service**: {platform}\n"
            f"📊 **Details**: {summary}\n"
            f"🔗 [Original Message]({msg.link})"
        )

        targets = settings.get_forward_targets()
        if not targets:
            log.warning("⚠️ No FORWARD_TO targets configured!")

        for admin in targets:
            try:
                await context.bot.send_message(
                    chat_id=admin, text=alert_msg, parse_mode=ParseMode.MARKDOWN
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

    # 2.1 Chat 模式：直接用 AI 回复用户，不再转发给管理员
    if mode == "chat":
        try:
            reply_text = await agent.chat_reply(text)
        except Exception as e:
            log.error(f"❌ chat_reply failed for user {user.id}: {e}")
            reply_text = "⚠️ AI 聊天暂时不可用，请稍后再试。"
        await msg.reply_text(reply_text, parse_mode=ParseMode.MARKDOWN)
        return

    # 2.2 Forward 模式（默认）：先做 AI 分类，再转发给管理员
    analysis = await agent.analyze_private_message(text)

    # Spam Enforcement
    if analysis.get("is_spam"):
        status = blacklist.add_strike(user.id)
        if status == "banned":
            await msg.reply_text("🚫 You have been banned for spam.")
        return

    # 构造转发头信息
    tags = " ".join([f"#{t}" for t in analysis.get("tags", [])])
    category = analysis.get("category", "general").upper()
    summary = analysis.get("summary", "No summary")

    header = (
        f"📨 **Private Message** [{category}]\n"
        f"👤 **From**: {user.full_name} (`{user.id}`)\n"
        f"🏷 **Tags**: {tags or '—'}\n"
        f"📝 **Summary**: {summary}\n"
        f"-----------------------------"
    )

    targets = settings.get_forward_targets()
    for admin_id in targets:
        try:
            # Header
            await context.bot.send_message(
                chat_id=admin_id, text=header, parse_mode=ParseMode.MARKDOWN
            )
            # Forward 原始消息（保留上下文 / 媒体）
            fwd_msg = await context.bot.forward_message(
                chat_id=admin_id,
                from_chat_id=user.id,
                message_id=msg.message_id,
            )
            # 注册回复桥接
            state_manager.register_forward(fwd_msg.message_id, user.id)

        except Exception as e:
            log.error(f"Failed to forward DM to {admin_id}: {e}")

    # 如需给普通用户一个确认，可以在这里打开：
    # await msg.reply_text("Your message has been received by support.")


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
        # 可能回复到了 header 或者非映射消息，忽略
        return

    # 4. 回发给原始用户
    try:
        await context.bot.send_message(chat_id=original_user_id, text=msg.text)
        await msg.reply_text(f"✅ Sent to user `{original_user_id}`")
    except Exception as e:
        await msg.reply_text(f"❌ Failed to send: {e}")
