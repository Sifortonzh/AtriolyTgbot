
from __future__ import annotations

import datetime
import json
import logging
from typing import Any, Iterable

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config import settings
from src.services.ai_agent import agent
from src.services.blacklist_manager import blacklist
from src.services.membership import manager
from src.services.state_manager import state_manager
from src.services.task_manager import task_manager

log = logging.getLogger(__name__)


async def safe_reply(
    update: Update,
    text: str,
    parse_mode: str | None = ParseMode.MARKDOWN,
    **kwargs: Any,
) -> None:
    """Reply to a command safely without allowing Telegram formatting errors to crash handlers."""
    message = update.effective_message
    if not message:
        return

    try:
        await message.reply_text(text, parse_mode=parse_mode, **kwargs)
    except Exception as error:  # noqa: BLE001 - command replies should degrade gracefully
        log.warning("Markdown/HTML reply failed, retrying as plain text: %s", error)
        try:
            await message.reply_text(text, parse_mode=None, **kwargs)
        except Exception as fallback_error:  # noqa: BLE001
            log.error("Failed to send command reply: %s", fallback_error, exc_info=fallback_error)


def current_user_id(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def is_owner(update: Update) -> bool:
    return settings.is_owner(current_user_id(update))


async def require_owner(update: Update, command_name: str) -> bool:
    """Return True for owners; otherwise send a clear permission-denied message."""
    if is_owner(update):
        return True

    uid = current_user_id(update)
    log.warning("Permission denied for command /%s from user_id=%s", command_name, uid)
    await safe_reply(
        update,
        "⛔ **Permission denied**\nThis command is reserved for Atrioly owners.",
    )
    return False


def format_bool(value: bool) -> str:
    return "ON" if value else "OFF"


def format_json(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        return str(data)


def get_task_count(entry_type: str) -> int:
    try:
        return len(task_manager.get_entries(entry_type))
    except Exception as error:  # noqa: BLE001
        log.warning("Failed to read task count for %s: %s", entry_type, error)
        return 0


def split_long_message(lines: Iterable[str], limit: int = 3500) -> list[str]:
    """Split long Telegram messages by line while staying below the Telegram hard limit."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1
        if current and current_len + line_len > limit:
            chunks.append("\n".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len

    if current:
        chunks.append("\n".join(current))

    return chunks


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = current_user_id(update)
    mode = state_manager.get_mode(user_id) if user_id is not None else "chat"

    await safe_reply(
        update,
        (
            "💠 **Atrioly · Wanatring Online**\n"
            f"Current Mode: `{mode.upper()}`\n"
            "Use /help to see available tools."
        ),
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    owner_hint = "\n\n🔐 **Owner Console**\n" if is_owner(update) else ""
    owner_commands = (
        "`/probe <text>` - Analyze text with the AI filter\n"
        "`/ai_test <text>` - Legacy alias for /probe\n"
        "`/blacklist <uid>` - Ban a user\n"
        "`/whitelist <uid>` - Unban a user\n"
        "`/listall` - List all stored tasks\n"
    )

    text = (
        "📚 **Atrioly Command List**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/start` - Wake the agent\n"
        "`/help` - Show this manual\n"
        "`/status` - System health & task stats\n"
        "`/ping` - Check bot responsiveness\n"
        "`/mode [chat|forward]` - Switch AI/Human routing\n"
        "`/membership_sharing` - View tracked memberships\n"
        f"{owner_hint}{owner_commands if is_owner(update) else ''}"
    )
    await safe_reply(update, text)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current user mode, model, feature flags, and task statistics."""
    user_id = current_user_id(update)
    mode = state_manager.get_mode(user_id) if user_id is not None else "chat"

    todos = get_task_count("todo")
    reminders = get_task_count("reminder")
    days = get_task_count("days")
    annis = get_task_count("annis")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    summary = settings.public_runtime_summary()

    text = (
        "🟢 **Atrioly System Status**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🤖 **Model**: `{settings.DEFAULT_MODEL}`\n"
        f"📡 **Mode**: `{mode.upper()}`\n"
        f"🧭 **Timezone**: `{settings.DEFAULT_TIMEZONE}`\n"
        f"📅 **Date**: `{now_str}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "**Feature Flags**\n"
        f"• AI Filter: `{format_bool(settings.ENABLE_AI_FILTER)}`\n"
        f"• Heuristic Filter: `{format_bool(settings.ENABLE_HEURISTIC_FILTER)}`\n"
        f"• Auto Ban: `{format_bool(settings.ENABLE_AUTO_BAN)}`\n"
        f"• Daily Report: `{format_bool(settings.ENABLE_DAILY_REPORT)}`\n"
        f"• Sender Profile Link: `{format_bool(settings.ENABLE_SENDER_PROFILE_LINK)}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "**Database Stats**\n"
        f"• Todos: `{todos}`\n"
        f"• Pending Reminders: `{reminders}`\n"
        f"• Special Days: `{days}`\n"
        f"• Anniversaries: `{annis}`\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "**Runtime**\n"
        f"• Owners: `{summary['owners']}`\n"
        f"• Forward Targets: `{summary['forward_targets']}`\n"
        f"• Data Dir: `{summary['data_dir']}`\n"
        f"• Max Message Length: `{summary['max_message_length']}`"
    )
    await safe_reply(update, text)


async def cmd_membership_sharing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        subs = manager.get_active()
    except Exception as error:  # noqa: BLE001
        log.error("Failed to load memberships: %s", error, exc_info=error)
        await safe_reply(update, "⚠️ Failed to load membership records.")
        return

    if not subs:
        await safe_reply(update, "📡 **Membership Radar**\n\nNo active subscriptions.")
        return

    lines = ["📡 **Membership Radar**", ""]
    for item in subs:
        platform = item.get("platform", "Unknown")
        expiry = item.get("expiry", "N/A")
        status = item.get("status", "active")
        lines.append(f"- **{platform}** | Exp: `{expiry}` | Status: `{status}`")

    await safe_reply(update, "\n".join(lines))


async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update, "blacklist"):
        return

    if not context.args:
        await safe_reply(update, "Usage: `/blacklist <uid>`")
        return

    try:
        uid = int(context.args[0])
    except ValueError:
        await safe_reply(update, "Invalid UID. Usage: `/blacklist <uid>`")
        return

    try:
        blacklist.ban_user(uid)
        log.info("Owner %s added user %s to blacklist.", current_user_id(update), uid)
        await safe_reply(update, f"🚫 User `{uid}` added to blacklist.")
    except Exception as error:  # noqa: BLE001
        log.error("Failed to blacklist user %s: %s", uid, error, exc_info=error)
        await safe_reply(update, "⚠️ Failed to update blacklist.")


async def cmd_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_owner(update, "whitelist"):
        return

    if not context.args:
        await safe_reply(update, "Usage: `/whitelist <uid>`")
        return

    try:
        uid = int(context.args[0])
    except ValueError:
        await safe_reply(update, "Invalid UID. Usage: `/whitelist <uid>`")
        return

    try:
        if blacklist.unban_user(uid):
            log.info("Owner %s removed user %s from blacklist.", current_user_id(update), uid)
            await safe_reply(update, f"✅ User `{uid}` unbanned.")
        else:
            await safe_reply(update, f"ℹ️ User `{uid}` was not banned.")
    except Exception as error:  # noqa: BLE001
        log.error("Failed to whitelist user %s: %s", uid, error, exc_info=error)
        await safe_reply(update, "⚠️ Failed to update blacklist.")


async def cmd_ai_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Legacy diagnostic command. Kept for compatibility with older README/docs."""
    await cmd_probe(update, context)


async def cmd_probe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if settings.ADMIN_ONLY_AI_TEST and not await require_owner(update, "probe"):
        return

    if not context.args:
        await safe_reply(update, "Usage: `/probe <text>`")
        return

    text = " ".join(context.args).strip()
    if not text:
        await safe_reply(update, "Usage: `/probe <text>`")
        return

    if len(text) > settings.MAX_MESSAGE_LENGTH:
        text = text[: settings.MAX_MESSAGE_LENGTH]

    try:
        result = await agent.analyze_message(text)
        log.info("AI probe result requested by user_id=%s: %s", current_user_id(update), result)
    except Exception as error:  # noqa: BLE001
        log.error("AI probe failed: %s", error, exc_info=error)
        await safe_reply(update, "⚠️ AI probe failed. Check logs for details.")
        return

    await safe_reply(
        update,
        f"```json\n{format_json(result)}\n```",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Switch between `chat` (AI) and `forward` (Human) mode."""
    if not context.args:
        await safe_reply(update, "Usage: `/mode [chat|forward]`")
        return

    new_mode = context.args[0].lower().strip()
    if new_mode not in {"chat", "forward"}:
        await safe_reply(update, "Invalid mode. Use `chat` or `forward`.")
        return

    user_id = current_user_id(update)
    if user_id is None:
        await safe_reply(update, "⚠️ Cannot identify current user.")
        return

    state_manager.set_mode(user_id, new_mode)
    log.info("User %s switched mode to %s.", user_id, new_mode)
    await safe_reply(update, f"✅ Mode switched to: **{new_mode.upper()}**")


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await safe_reply(update, "🏓 Pong! System operational.")


def _fmt_tags_hash(raw: Any) -> str:
    """Render tags as: #reminder #exam #CET_6."""
    if not raw:
        return ""

    tags = raw if isinstance(raw, list) else [str(raw)]
    normalized: list[str] = []
    seen: set[str] = set()

    for tag in tags:
        text = str(tag).strip()
        if not text:
            continue
        text = text.replace(" ", "_")
        if not text.startswith("#"):
            text = "#" + text
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)

    if not normalized:
        return ""
    return " | Tags: " + " ".join(normalized)


def _append_entries(lines: list[str], title: str, empty_label: str, entries: list[dict[str, Any]], date_keys: tuple[str, ...] = ()) -> None:
    if not entries:
        lines.append(f"\n{title}: _none_")
        return

    lines.append(f"\n{title}")
    for item in entries:
        item_id = item.get("id", "?")
        item_title = item.get("title", "(no title)")
        note = item.get("note", "")
        date_value = ""
        for key in date_keys:
            if item.get(key):
                date_value = str(item.get(key))
                break

        line = f"- [`{item_id}`] **{item_title}**"
        if date_value:
            line += f" — {date_value}"
        if note:
            line += f" | {note}"
        line += _fmt_tags_hash(item.get("tags"))
        lines.append(line)


async def cmd_listall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all Todo / Reminder / Days / Anniversary records. Owner only."""
    if not await require_owner(update, "listall"):
        return

    try:
        todos = task_manager.get_entries("todo")
        reminders = task_manager.get_entries("reminder")
        days = task_manager.get_entries("days")
        annis = task_manager.get_entries("annis")
    except Exception as error:  # noqa: BLE001
        log.error("Failed to list all tasks: %s", error, exc_info=error)
        await safe_reply(update, "⚠️ Failed to load stored tasks.")
        return

    lines = ["📋 **All Stored Tasks**"]
    _append_entries(lines, "✅ *Todos*", "Todos", todos)
    _append_entries(lines, "⏰ *Reminders*", "Reminders", reminders, ("datetime", "date"))
    _append_entries(lines, "📅 *Days*", "Days", days, ("date", "datetime"))
    _append_entries(lines, "🎉 *Anniversaries*", "Anniversaries", annis, ("date", "datetime"))

    for chunk in split_long_message(lines):
        await safe_reply(update, chunk)
