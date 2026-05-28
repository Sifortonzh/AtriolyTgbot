from __future__ import annotations

import logging
import sys
import traceback
from typing import Any

from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    TypeHandler,
    filters,
)

from src.bot.callbacks import handle_menu_callback

from src.bot.commands import (
    cmd_ai_provider,
    cmd_ai_test,
    cmd_blacklist,
    cmd_help,
    cmd_listall,
    cmd_membership_sharing,
    cmd_mode,
    cmd_ping,
    cmd_probe,
    cmd_start,
    cmd_status,
    cmd_whitelist,
)
from src.bot.handlers import (
    gatekeeper_middleware,
    handle_admin_reply,
    handle_group_message,
    handle_private_message,
)
from src.config import settings
from src.services.scheduler import scheduler_service


LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
log = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure process-wide logging from settings.LOG_LEVEL."""
    logging.basicConfig(
        format=LOG_FORMAT,
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        stream=sys.stdout,
        force=True,
    )

    # Reduce noisy third-party logs while keeping warnings/errors visible.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.INFO)


def mask_secret(value: str | None, visible: int = 4) -> str:
    """Return a safe preview for secret values used in diagnostics."""
    if not value:
        return "missing"
    if len(value) <= visible * 2:
        return "configured"
    return f"{value[:visible]}…{value[-visible:]}"


def log_startup_summary() -> None:
    """Log a safe startup summary without leaking credentials."""
    summary = settings.public_runtime_summary()
    summary["telegram_bot_token"] = mask_secret(settings.TELEGRAM_BOT_TOKEN)
    summary["active_ai_key"] = "configured" if settings.active_ai_key_configured() else "missing"
    summary["active_ai_provider_ready"] = settings.active_ai_provider_ready()
    log.info("Atrioly · Wanatring runtime summary: %s", summary)


def ensure_runtime_environment() -> bool:
    """Validate required runtime configuration and prepare local directories."""
    settings.ensure_data_dir()

    if not settings.TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is missing. Set it in `.env` before starting the bot.")
        return False

    if not settings.OWNER_IDS:
        log.warning("OWNER_IDS is empty. Admin-only commands will be inaccessible.")

    if not settings.FORWARD_TO:
        log.warning("FORWARD_TO is empty. Radar alerts will not be forwarded to any chat.")

    if settings.ENABLE_AI_FILTER and not settings.active_ai_provider_ready():
        log.warning(
            "ENABLE_AI_FILTER is true but AI_PROVIDER=%s is not ready. AI analysis will use safe fallback behavior.",
            settings.AI_PROVIDER,
        )

    return True


async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch unhandled handler errors so one bad message cannot crash the bot."""
    error = context.error

    if isinstance(error, TelegramError):
        log.warning("Telegram API error: %s", error, exc_info=error)
    else:
        log.error("Unhandled bot error: %s", error, exc_info=error)

    # Try to notify owners, but never let notification failure cascade.
    if not settings.OWNER_IDS:
        return

    update_info = "unknown update"
    if isinstance(update, Update):
        update_info = f"update_id={update.update_id}"

    tb = "".join(traceback.format_exception(type(error), error, error.__traceback__)) if error else "No traceback"
    if len(tb) > 3000:
        tb = tb[:3000] + "\n… traceback truncated"

    message = (
        "🚨 <b>Atrioly Bot Error</b>\n"
        f"<b>Update:</b> <code>{update_info}</code>\n"
        f"<b>Error:</b> <code>{type(error).__name__ if error else 'UnknownError'}</code>\n"
        f"<pre>{tb}</pre>"
    )

    for owner_id in settings.OWNER_IDS:
        try:
            await context.bot.send_message(chat_id=owner_id, text=message, parse_mode="HTML")
        except Exception as notify_error:  # noqa: BLE001 - logging must never raise here
            log.warning("Failed to notify owner %s about bot error: %s", owner_id, notify_error)


def register_middlewares(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """Register middleware-like handlers with high priority."""
    application.add_handler(TypeHandler(Update, gatekeeper_middleware), group=-1)


def register_commands(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """Register command handlers in one predictable place."""
    command_handlers = {
        "start": cmd_start,
        "help": cmd_help,
        "mode": cmd_mode,
        "ping": cmd_ping,
        "status": cmd_status,
        "membership_sharing": cmd_membership_sharing,
        "blacklist": cmd_blacklist,
        "whitelist": cmd_whitelist,
        "ai_test": cmd_ai_test,
        "ai_provider": cmd_ai_provider,
        "probe": cmd_probe,
        "listall": cmd_listall,
    }

    for command, handler in command_handlers.items():
        application.add_handler(CommandHandler(command, handler))

    application.add_handler(CallbackQueryHandler(handle_menu_callback, pattern=r"^menu:"))


def register_message_handlers(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """Register private, admin-reply, and group message handlers."""
    # Admin replies in private chat: owner replies to a forwarded user message,
    # then the bot sends the reply back to the original user.
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.REPLY & filters.TEXT,
            handle_admin_reply,
        )
    )

    # Normal private messages: user → bot. This can trigger AI classification,
    # forwarding, or owner secretary mode depending on handlers.py.
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.TEXT | filters.PHOTO),
            handle_private_message,
        )
    )

    # Group messages: radar sniffing + spam filtering.
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT,
            handle_group_message,
        )
    )


def build_application() -> Application[Any, Any, Any, Any, Any, Any]:
    """Build and configure the Telegram application."""
    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    application.add_error_handler(global_error_handler)
    register_middlewares(application)
    register_commands(application)
    register_message_handlers(application)

    return application


def start_scheduler(application: Application[Any, Any, Any, Any, Any, Any]) -> None:
    """Start scheduler safely so scheduling failures do not stop the bot."""
    try:
        scheduler_service.start(application)
        log.info("Scheduler service started.")
    except Exception as error:  # noqa: BLE001 - bot should still run if scheduler fails
        log.error("Failed to start scheduler service: %s", error, exc_info=error)


def main() -> None:
    """Entry point for Atrioly · Wanatring."""
    configure_logging()

    if not ensure_runtime_environment():
        return

    log_startup_summary()

    application = build_application()
    start_scheduler(application)

    log.info("🟢 Atrioly · Wanatring Agent Online.")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=False,
    )


if __name__ == "__main__":
    main()
