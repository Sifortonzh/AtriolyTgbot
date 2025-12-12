from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config import settings
from src.services.blacklist_manager import blacklist
from src.services.membership import manager
from src.services.ai_agent import agent
from src.services.state_manager import state_manager
from src.services.task_manager import task_manager
import datetime


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = state_manager.get_mode(user_id)
    await update.message.reply_text(
        f"💠 **Atrioly Agent Online**\n"
        f"Current Mode: `{mode.upper()}`\n"
        f"Use /help to see tools.",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "📚 **Atrioly Command List**\n"
        "`/membership_sharing` - View tracked memberships\n"
        "`/status` - System health & task stats\n"
        "`/ai_test <text>` - Test AI logic (group filter)\n"
        "`/mode [chat|forward]` - Switch AI/Human routing\n"
        "`/ping` - Check bot responsiveness\n"
        "`/listall` - List all stored tasks (owner only)\n"
        "**Admin Only:**\n"
        "`/blacklist <uid>` - Ban user\n"
        "`/whitelist <uid>` - Unban user"
    )
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Restored V3 Status Command.
    显示当前用户模式、模型以及任务统计。
    """
    user_id = update.effective_user.id
    mode = state_manager.get_mode(user_id)

    # Gather stats from task_manager
    try:
        todos = len(task_manager.get_entries("todo"))
    except Exception:
        todos = 0

    try:
        reminders = len(task_manager.get_entries("reminder"))
    except Exception:
        reminders = 0

    try:
        days = len(task_manager.get_entries("days"))
    except Exception:
        days = 0

    try:
        annis = len(task_manager.get_entries("annis"))
    except Exception:
        annis = 0

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    txt = (
        f"🟢 **Atrioly System v3.0.2**\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **Model**: `{settings.DEFAULT_MODEL}`\n"
        f"📡 **Mode**: `{mode.upper()}`\n"
        f"⏰ **Scheduler**: Active (Asia/Shanghai)\n"
        f"📅 **Date**: {now_str}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"**Database Stats:**\n"
        f"• Todos: `{todos}`\n"
        f"• Pending Reminders: `{reminders}`\n"
        f"• Special Days: `{days}`\n"
        f"• Anniversaries: `{annis}`"
    )
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)


async def cmd_membership_sharing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = manager.get_active()
    msg = "📡 **Membership Radar**\n\n" + (
        "\n".join([f"- {s['platform']} (Exp: {s['expiry']})" for s in subs])
        if subs
        else "No active subscriptions."
    )
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in settings.OWNER_IDS:
        return
    try:
        uid = int(context.args[0])
        blacklist.ban_user(uid)
        await update.message.reply_text(f"🚫 User {uid} added to blacklist.")
    except Exception:
        await update.message.reply_text("Usage: /blacklist <uid>")


async def cmd_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in settings.OWNER_IDS:
        return
    try:
        uid = int(context.args[0])
        if blacklist.unban_user(uid):
            await update.message.reply_text(f"✅ User {uid} unbanned.")
        else:
            await update.message.reply_text("User was not banned.")
    except Exception:
        await update.message.reply_text("Usage: /whitelist <uid>")


async def cmd_ai_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return
    res = await agent.analyze_message(" ".join(context.args))
    await update.message.reply_text(
        f"```json\n{res}\n```", parse_mode=ParseMode.MARKDOWN
    )


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch between 'chat' (AI) and 'forward' (Human) mode."""
    if not context.args:
        await update.message.reply_text(
            "Usage: `/mode [chat|forward]`", parse_mode=ParseMode.MARKDOWN
        )
        return

    new_mode = context.args[0].lower()
    if new_mode not in ["chat", "forward"]:
        await update.message.reply_text("Invalid mode. Use `chat` or `forward`.")
        return

    state_manager.set_mode(update.effective_user.id, new_mode)
    await update.message.reply_text(
        f"✅ Mode switched to: **{new_mode.upper()}**",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! System operational.")


# -------- NEW: /listall --------

def _fmt_tags_hash(raw) -> str:
    """
    统一把 tags 渲染为系统风格: #reminder #exam #CET_6
    - 自动去重
    - 自动补 '#'
    - 把空格替换为下划线，避免 Markdown 断开
    """
    if not raw:
        return ""

    tags = raw if isinstance(raw, list) else [str(raw)]
    normalized = []
    seen = set()

    for t in tags:
        s = str(t).strip()
        if not s:
            continue
        # 空格 -> 下划线，避免拆成两个词
        s = s.replace(" ", "_")
        # 自动补 '#'
        if not s.startswith("#"):
            s = "#" + s
        # 去重（不区分大小写）
        key = s.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(s)

    if not normalized:
        return ""
    return " | Tags: " + " ".join(normalized)


async def cmd_listall(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    列出所有 Todo / Reminder / Days / Anniversary。
    仅 owner 可用。
    """
    user_id = update.effective_user.id
    if user_id not in settings.OWNER_IDS:
        return

    todos = task_manager.get_entries("todo")
    reminders = task_manager.get_entries("reminder")
    days = task_manager.get_entries("days")
    annis = task_manager.get_entries("annis")

    lines = ["📋 **All Stored Tasks**"]

    # Todos
    if todos:
        lines.append("\n✅ *Todos*")
        for t in todos:
            tid = t.get("id", "?")
            title = t.get("title", "(no title)")
            note = t.get("note", "")
            line = f"- [`{tid}`] **{title}**"
            if note:
                line += f" — {note}"
            line += _fmt_tags_hash(t.get("tags"))
            lines.append(line)
    else:
        lines.append("\n✅ *Todos*: _none_")

    # Reminders
    if reminders:
        lines.append("\n⏰ *Reminders*")
        for r in reminders:
            rid = r.get("id", "?")
            title = r.get("title", "(no title)")
            dt = r.get("datetime", "N/A")
            note = r.get("note", "")
            line = f"- [`{rid}`] **{title}** — {dt}"
            if note:
                line += f" | {note}"
            line += _fmt_tags_hash(r.get("tags"))
            lines.append(line)
    else:
        lines.append("\n⏰ *Reminders*: _none_")

    # Special Days
    if days:
        lines.append("\n📅 *Days*")
        for d in days:
            did = d.get("id", "?")
            title = d.get("title", "(no title)")
            date = d.get("date") or d.get("datetime") or "N/A"
            note = d.get("note", "")
            line = f"- [`{did}`] **{title}** — {date}"
            if note:
                line += f" | {note}"
            line += _fmt_tags_hash(d.get("tags"))
            lines.append(line)
    else:
        lines.append("\n📅 *Days*: _none_")

    # Anniversaries
    if annis:
        lines.append("\n🎉 *Anniversaries*")
        for a in annis:
            aid = a.get("id", "?")
            title = a.get("title", "(no title)")
            date = a.get("date") or a.get("datetime") or "N/A"
            note = a.get("note", "")
            line = f"- [`{aid}`] **{title}** — {date}"
            if note:
                line += f" | {note}"
            line += _fmt_tags_hash(a.get("tags"))
            lines.append(line)
    else:
        lines.append("\n🎉 *Anniversaries*: _none_")

    msg = "\n".join(lines)
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)
