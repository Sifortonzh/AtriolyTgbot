import logging
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

    # --- 1. Owner Secretary Mode ---
    if user.id in settings.OWNER_IDS:
        intent = await agent.analyze_owner_intent(text)
        action = intent.get("action", "none")

        if action != "none":
            # 写入任务系统
            try:
                task_manager.add_entry(action, intent)
            except Exception as e:
                log.error(f"❌ task_manager.add_entry failed: {e}")
                await msg.reply_text(f"⚠️ 创建 {action} 时出错：{e}")
                return

            tags = " ".join(intent.get("tags", [])) or "—"
            reply = (
                f"✅ **Created {action.upper()}**\n"
                f"📌 {intent.get('title') or 'No title'}\n"
                f"🕒 {intent.get('datetime') or 'N/A'}\n"
                f"🏷 {tags}"
            )
            await msg.reply_text(reply, parse_mode=ParseMode.MARKDOWN)
            return

        # action == 'none'：视为无关闲聊，不再走后面的“转发给自己当管理员”的逻辑
        log.info(f"Owner message classified as 'none', ignoring. Text='{text[:50]}...'")
        return

    # --- 2. 普通用户：AI 分类 + 转发给管理员 ---

    # 2.1 AI 分类（服务台）
    analysis = await agent.analyze_private_message(text)

    # 2.2 Spam Enforcement
    if analysis.get("is_spam"):
        status = blacklist.add_strike(user.id)
        if status == "banned":
            await msg.reply_text("🚫 You have been banned for spam.")
        return

    # 2.3 Mode（目前仍然主要用于将来扩展）
    mode = state_manager.get_mode(user.id)
    log.info(f"Private message mode for user {user.id}: {mode}")

    # 2.4 构造转发头信息
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
