from __future__ import annotations

import datetime
import logging
from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.config import settings
from src.services import ai_runtime
from src.services.blacklist_manager import blacklist
from src.services.membership import manager
from src.services.private_threads import private_threads
from src.services.state_manager import state_manager
from src.services.task_manager import task_manager

log = logging.getLogger(__name__)

PRIVATE_QUICK_REPLIES = {
    "ask_details": "你好，请问你想咨询哪个平台？我可以先帮你确认一下具体情况。🌿",
    "send_price": "目前价格需要根据平台和周期确认。你可以先告诉我想咨询 Netflix、Disney+、Spotify 还是其他平台。💰",
    "check_availability": "我先帮你确认一下是否还有可用位置，稍后回复你。📦",
    "polite_reject": "抱歉，目前这边暂时没有合适的位置或方案。感谢你的理解～ 🙏",
}


def current_user_id(update: Update) -> int | None:
    return update.effective_user.id if update.effective_user else None


def is_owner(update: Update) -> bool:
    return settings.is_owner(current_user_id(update))


def format_bool(value: bool) -> str:
    return "ON" if value else "OFF"


def get_task_count(entry_type: str) -> int:
    try:
        return len(task_manager.get_entries(entry_type))
    except Exception as error:  # noqa: BLE001
        log.warning("Failed to read task count for %s: %s", entry_type, error)
        return 0


def build_home_keyboard(is_owner_user: bool) -> InlineKeyboardMarkup:
    keyboard: list[list[InlineKeyboardButton]] = [
        [
            InlineKeyboardButton("📊 Status", callback_data="menu:status"),
            InlineKeyboardButton("🧠 AI Radar", callback_data="menu:probe"),
        ],
        [
            InlineKeyboardButton("🎬 Membership", callback_data="menu:membership"),
            InlineKeyboardButton("🗂 Tasks", callback_data="menu:listall"),
        ],
        [
            InlineKeyboardButton("🔁 Mode", callback_data="menu:mode"),
            InlineKeyboardButton("📖 Help", callback_data="menu:help"),
        ],
    ]
    if is_owner_user:
        keyboard.append([InlineKeyboardButton("🛡 Owner Tools", callback_data="menu:owner")])
        keyboard.append([InlineKeyboardButton("⚙️ AI Provider", callback_data="menu:ai_provider")])
    return InlineKeyboardMarkup(keyboard)


def build_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu:home")]])


def build_mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🤖 Chat Mode", callback_data="menu:mode:chat"),
                InlineKeyboardButton("📨 Forward Mode", callback_data="menu:mode:forward"),
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu:home")],
        ]
    )


def render_home_text(update: Update) -> str:
    user_id = current_user_id(update)
    mode = state_manager.get_mode(user_id) if user_id is not None else "chat"
    summary = settings.public_runtime_summary()
    ai = summary.get("ai", {})
    provider = ai.get("provider") or summary.get("provider") or "N/A"
    model = ai.get("model") or summary.get("model") or "N/A"
    ready = ai.get("provider_ready")
    if ready is None:
        ready = summary.get("active_ai_provider_ready")
    ready_icon = "✅" if ready else "⚠️"

    return (
        "🪐 *Atrioly · Wanatring Console*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Current Mode: `{mode.upper()}`\n"
        f"AI Provider: `{provider} · {model} {ready_icon}`\n"
        "\n"
        "Intelligent routing, AI radar, membership tracking, and task console."
    )


def render_status_text(update: Update) -> str:
    user_id = current_user_id(update)
    mode = state_manager.get_mode(user_id) if user_id is not None else "chat"

    todos = get_task_count("todo")
    reminders = get_task_count("reminder")
    days = get_task_count("days")
    annis = get_task_count("annis")

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    summary = settings.public_runtime_summary()

    return (
        "🟢 *Atrioly System Status*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🤖 Model: `{settings.DEFAULT_MODEL}`\n"
        f"📡 Mode: `{mode.upper()}`\n"
        f"🧭 Timezone: `{settings.DEFAULT_TIMEZONE}`\n"
        f"📅 Date: `{now_str}`\n"
        "\n"
        "*Feature Flags*\n"
        f"• AI Filter: `{format_bool(settings.ENABLE_AI_FILTER)}`\n"
        f"• Heuristic Filter: `{format_bool(settings.ENABLE_HEURISTIC_FILTER)}`\n"
        f"• Auto Ban: `{format_bool(settings.ENABLE_AUTO_BAN)}`\n"
        "\n"
        "*Task Stats*\n"
        f"• Todos: `{todos}`\n"
        f"• Pending Reminders: `{reminders}`\n"
        f"• Special Days: `{days}`\n"
        f"• Anniversaries: `{annis}`\n"
        "\n"
        "*Runtime*\n"
        f"• Owners: `{summary['owners']}`\n"
        f"• Forward Targets: `{summary['forward_targets']}`"
    )


def render_help_text(owner: bool) -> str:
    owner_hint = "\n\n🔐 *Owner Console*\n" if owner else ""
    owner_commands = (
        "`/probe <text>` - Analyze text with the AI filter\n"
        "`/ai_test <text>` - Legacy alias for /probe\n"
        "`/blacklist <uid>` - Ban a user\n"
        "`/whitelist <uid>` - Unban a user\n"
        "`/inbox` - Show open private threads\n"
        "`/listall` - List all stored tasks\n"
    )

    return (
        "📚 *Atrioly Command List*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "`/start` - Open console menu\n"
        "`/help` - Show this manual\n"
        "`/status` - System health & task stats\n"
        "`/ping` - Check bot responsiveness\n"
        "`/mode [chat|forward]` - Switch AI/Human routing\n"
        "`/membership_sharing` - View tracked memberships\n"
        f"{owner_hint}{owner_commands if owner else ''}"
    )


def render_probe_text() -> str:
    return (
        "🧠 *AI Probe*\n"
        "Send `/probe <text>` to test the AI radar.\n\n"
        "Examples:\n"
        "`/probe Netflix 车位还有一个，25元一个月`\n"
        "`/probe USDT 投资稳赚，点击链接进群`"
    )


def render_membership_text() -> str:
    try:
        subs = manager.get_active()
    except Exception as error:  # noqa: BLE001
        log.error("Failed to load memberships: %s", error, exc_info=error)
        return "⚠️ Failed to load membership records."

    if not subs:
        return "📡 *Membership Radar*\n\nNo active membership records."

    lines = ["📡 *Membership Radar*", ""]
    for item in subs:
        platform = item.get("platform", "Unknown")
        expiry = item.get("expiry", "N/A")
        status = item.get("status", "active")
        lines.append(f"- *{platform}* | Exp: `{expiry}` | Status: `{status}`")

    return "\n".join(lines)


def render_tasks_summary_text() -> str:
    todos = get_task_count("todo")
    reminders = get_task_count("reminder")
    days = get_task_count("days")
    annis = get_task_count("annis")
    return (
        "🗂 *Task Console Summary*\n"
        f"• Todos: `{todos}`\n"
        f"• Reminders: `{reminders}`\n"
        f"• Days: `{days}`\n"
        f"• Anniversaries: `{annis}`\n\n"
        "Use `/listall` to view full details."
    )


def render_owner_tools_text() -> str:
    return (
        "🛡 *Owner Tools*\n"
        "`/probe <text>`\n"
        "`/blacklist <uid>`\n"
        "`/whitelist <uid>`\n"
        "`/inbox`\n"
        "`/listall`"
    )


def build_ai_provider_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(f"OpenAI · {settings.DEFAULT_MODEL}", callback_data="menu:ai_provider:openai")],
            [InlineKeyboardButton(f"DeepSeek · {settings.DEEPSEEK_MODEL}", callback_data="menu:ai_provider:deepseek")],
            [InlineKeyboardButton(f"Claude · {settings.ANTHROPIC_MODEL}", callback_data="menu:ai_provider:anthropic")],
            [InlineKeyboardButton("OpenAI Compatible", callback_data="menu:ai_provider:openai_compatible")],
            [InlineKeyboardButton("Clear Runtime Override", callback_data="menu:ai_provider:clear")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu:home")],
        ]
    )


def _provider_model_default(provider: str) -> str:
    if provider == "deepseek":
        return settings.DEEPSEEK_MODEL
    if provider == "anthropic":
        return settings.ANTHROPIC_MODEL
    if provider == "openai_compatible":
        return settings.OPENAI_COMPATIBLE_MODEL or settings.DEFAULT_MODEL
    return settings.DEFAULT_MODEL


def render_ai_provider_text() -> str:
    info = ai_runtime.summary()
    runtime = info.get("runtime") or {}
    runtime_provider = runtime.get("provider") or info.get("provider") or "N/A"
    runtime_model = runtime.get("model") or info.get("model") or "N/A"
    override_active = bool(info.get("runtime_override_active"))
    default_provider = info.get("default_provider") or settings.AI_PROVIDER
    provider_ready = bool(info.get("provider_ready"))
    key_ready = bool(info.get("api_key_configured"))
    ready_icon = "✅" if provider_ready else "⚠️"

    warning = ""
    if not key_ready:
        warning = "\n\n⚠️ Selected provider API key is not configured."
    elif runtime_provider == "openai_compatible" and not settings.OPENAI_COMPATIBLE_BASE_URL:
        warning = "\n\n⚠️ OPENAI_COMPATIBLE_BASE_URL is missing."

    return (
        "⚙️ *AI Provider Runtime Switcher*\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"Runtime Provider: `{runtime_provider}`\n"
        f"Runtime Model: `{runtime_model}`\n"
        f"Runtime Override: `{'ACTIVE' if override_active else 'INACTIVE'}`\n"
        f"Default (.env) Provider: `{default_provider}`\n"
        f"Provider Readiness: `{ready_icon}`"
        f"{warning}"
    )


async def _safe_edit(
    query: Any,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    parse_mode: str | None = ParseMode.MARKDOWN,
) -> None:
    try:
        await query.edit_message_text(text=text, parse_mode=parse_mode, reply_markup=reply_markup)
    except Exception as error:  # noqa: BLE001
        log.warning("Menu edit failed with parse_mode=%s, retrying plain text: %s", parse_mode, error)
        await query.edit_message_text(text=text, parse_mode=None, reply_markup=reply_markup)


async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    owner = is_owner(update)
    user_id = current_user_id(update)

    if data.startswith("report:"):
        if not owner:
            await query.answer("Owner only.", show_alert=True)
            return

        parts = data.split(":")
        if len(parts) < 4:
            await query.answer("Invalid report action.", show_alert=True)
            return

        action = parts[1]
        target_user_id = parts[2]

        if action == "save":
            await query.answer("Saved placeholder. Persistence will be added later.", show_alert=True)
            return

        if action == "blacklist":
            try:
                uid = int(target_user_id)
                blacklist.ban_user(uid)
                await query.answer(f"User {uid} blacklisted.", show_alert=True)
            except Exception:
                await query.answer("Blacklist placeholder. Persistence will be wired later.", show_alert=True)
            return

        if action == "view_sender":
            link = f"tg://user?id={target_user_id}"
            await query.answer(f"Sender: {link}", show_alert=True)
            return

        if action == "add_note":
            await query.answer("Note placeholder. Note storage will be added later.", show_alert=True)
            return

        await query.answer("Unknown report action.", show_alert=True)
        return

    if data.startswith("spam:"):
        if not owner:
            await query.answer("Owner only.", show_alert=True)
            return

        parts = data.split(":")
        if len(parts) < 3:
            await query.answer("Invalid spam action.", show_alert=True)
            return

        action = parts[1]
        try:
            target_user_id = int(parts[2])
        except (TypeError, ValueError):
            await query.answer("Invalid spam user.", show_alert=True)
            return

        if action == "keep":
            await query.answer("✅ 已保持黑名单状态。", show_alert=True)
            return

        if action == "unblacklist":
            try:
                if blacklist.unban_user(target_user_id):
                    await query.answer("♻️ 已移出黑名单。", show_alert=True)
                else:
                    await query.answer("ℹ️ 该用户当前不在黑名单。", show_alert=True)
            except Exception as error:  # noqa: BLE001
                log.error("Failed to unblacklist spam user %s: %s", target_user_id, error, exc_info=error)
                await query.answer("⚠️ 移出黑名单失败。", show_alert=True)
            return

        await query.answer("Unknown spam action.", show_alert=True)
        return

    if data.startswith("private:"):
        if not owner:
            await query.answer("Owner only.", show_alert=True)
            return

        parts = data.split(":")
        if len(parts) < 4:
            await query.answer("Invalid private action.", show_alert=True)
            return

        action = parts[1]
        target_user_id = parts[2]
        owner_message_id = None
        try:
            owner_message_id = int(parts[3])
        except (TypeError, ValueError):
            owner_message_id = None

        if action == "reply_guide":
            await query.answer(
                "Reply to this forwarded message, and Wanatring will relay your reply to the original user.",
                show_alert=True,
            )
            return

        if action in PRIVATE_QUICK_REPLIES:
            if owner_message_id is None:
                await query.answer("⚠️ 快捷回复未能送达，可能是用户阻止了 Bot 或记录已过期。", show_alert=True)
                return

            thread = private_threads.get_by_owner_message_id(owner_message_id)
            if not thread:
                await query.answer("⚠️ 快捷回复未能送达，可能是用户阻止了 Bot 或记录已过期。", show_alert=True)
                return

            try:
                await context.bot.send_message(
                    chat_id=int(thread["user_id"]),
                    text=PRIVATE_QUICK_REPLIES[action],
                )
                await query.answer("✅ 快捷回复已发送。", show_alert=True)
            except Exception as error:  # noqa: BLE001
                log.error(
                    "Failed to send private quick reply action=%s owner_message_id=%s user_id=%s: %s",
                    action,
                    owner_message_id,
                    thread.get("user_id"),
                    error,
                    exc_info=error,
                )
                await query.answer("⚠️ 快捷回复未能送达，可能是用户阻止了 Bot 或记录已过期。", show_alert=True)
            return

        if action == "blacklist":
            try:
                uid = int(target_user_id)
                blacklist.ban_user(uid)
                await query.answer("User blacklisted.", show_alert=True)
            except Exception:
                await query.answer("Blacklist placeholder. Persistence will be wired later.", show_alert=True)
            return

        if action == "resolved":
            if owner_message_id is None:
                await query.answer("⚠️ 没找到对应的私聊记录，可能已经过期。", show_alert=True)
                return

            thread = private_threads.get_by_owner_message_id(owner_message_id)
            if not thread:
                await query.answer("⚠️ 没找到对应的私聊记录，可能已经过期。", show_alert=True)
                return

            private_threads.mark_resolved(str(thread["thread_id"]))
            await query.answer("✅ 已标记为已处理。", show_alert=True)
            return

        await query.answer("Unknown private action.", show_alert=True)
        return

    await query.answer()

    if data == "menu:home":
        await _safe_edit(query, render_home_text(update), build_home_keyboard(owner))
        return

    if data == "menu:status":
        await _safe_edit(query, render_status_text(update), build_back_keyboard())
        return

    if data == "menu:help":
        await _safe_edit(query, render_help_text(owner), build_back_keyboard())
        return

    if data == "menu:probe":
        await _safe_edit(query, render_probe_text(), build_back_keyboard())
        return

    if data == "menu:membership":
        await _safe_edit(query, render_membership_text(), build_back_keyboard())
        return

    if data == "menu:listall":
        if not owner:
            await _safe_edit(query, "⛔ Permission denied. Owner tools only.", build_back_keyboard(), parse_mode=None)
            return
        await _safe_edit(query, render_tasks_summary_text(), build_back_keyboard())
        return

    if data == "menu:mode":
        await _safe_edit(query, render_mode_text(update), build_mode_keyboard())
        return

    if data == "menu:mode:chat":
        if user_id is not None:
            state_manager.set_mode(user_id, "chat")
        await _safe_edit(query, render_mode_text(update), build_mode_keyboard())
        return

    if data == "menu:mode:forward":
        if user_id is not None:
            state_manager.set_mode(user_id, "forward")
        await _safe_edit(query, render_mode_text(update), build_mode_keyboard())
        return

    if data == "menu:owner":
        if not owner:
            await _safe_edit(query, "⛔ Permission denied. Owner tools only.", build_back_keyboard(), parse_mode=None)
            return
        await _safe_edit(query, render_owner_tools_text(), build_back_keyboard())
        return

    if data == "menu:ai_provider":
        if not owner:
            await _safe_edit(query, "⛔ Permission denied. Owner tools only.", build_back_keyboard(), parse_mode=None)
            return
        await _safe_edit(query, render_ai_provider_text(), build_ai_provider_keyboard())
        return

    if data in {
        "menu:ai_provider:openai",
        "menu:ai_provider:deepseek",
        "menu:ai_provider:anthropic",
        "menu:ai_provider:openai_compatible",
        "menu:ai_provider:clear",
    }:
        if not owner:
            await _safe_edit(query, "⛔ Permission denied. Owner tools only.", build_back_keyboard(), parse_mode=None)
            return

        if data == "menu:ai_provider:clear":
            ai_runtime.clear()
        else:
            provider = data.split(":")[-1]
            ai_runtime.set_provider(provider, _provider_model_default(provider))

        await _safe_edit(query, render_ai_provider_text(), build_ai_provider_keyboard())
        return


def render_mode_text(update: Update) -> str:
    user_id = current_user_id(update)
    mode = state_manager.get_mode(user_id) if user_id is not None else "chat"
    return (
        "🔁 *Mode Switch*\n"
        f"Current mode: `{mode.upper()}`\n\n"
        "Choose your routing mode:"
    )
