import logging
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, TypeHandler, filters
from telegram import Update
from src.config import settings
from src.bot.handlers import (
    gatekeeper_middleware,
    handle_group_message,
    handle_private_message,
    handle_admin_reply,
)
from src.bot.commands import (
    cmd_start, cmd_help, cmd_membership_sharing,
    cmd_blacklist, cmd_whitelist, cmd_ai_test,
    cmd_mode, cmd_ping, cmd_status
)
from src.services.scheduler import scheduler_service  # NEW: Import scheduler_service

# 设置日志级别，默认INFO
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(settings, "LOG_LEVEL", logging.INFO),
)
log = logging.getLogger(__name__)

def main():
    if not settings.TELEGRAM_BOT_TOKEN:
        log.error("❌ Error: TELEGRAM_BOT_TOKEN missing.")
        return

    app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # 1. Middleware (Priority -1)
    app.add_handler(TypeHandler(Update, gatekeeper_middleware), group=-1)

    # 2. Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("mode", cmd_mode))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("status", cmd_status))  # NEW: Add /status command
    app.add_handler(CommandHandler("membership_sharing", cmd_membership_sharing))
    app.add_handler(CommandHandler("blacklist", cmd_blacklist))
    app.add_handler(CommandHandler("whitelist", cmd_whitelist))
    app.add_handler(CommandHandler("ai_test", cmd_ai_test))

    # 3. Message Logic

    # A. Admin Reply Bridge（管理员在私聊里回复转发消息）
    # 条件：私聊 + 文本 + 是回复消息
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.REPLY & filters.TEXT,
            handle_admin_reply,
        )
    )

    # B. 普通私聊消息（用户 -> Bot）
    # 条件：私聊 + 文本（且不是上面的 reply 情况时由该 handler 处理）
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT,
            handle_private_message,
        )
    )

    # C. 群消息
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT,
            handle_group_message,
        )
    )

    # START SCHEDULER (Pass 'app' so it can send messages)
    scheduler_service.start(app)  # Start the scheduler service

    log.info("🟢 Atrioly · Wanatring Agent Online (v3.0 with Scheduler).")
    app.run_polling()

if __name__ == "__main__":
    main()
