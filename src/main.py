import logging
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    TypeHandler,
    filters,
)
from telegram import Update

from src.config import settings
from src.bot.handlers import (
    gatekeeper_middleware,
    handle_group_message,
    handle_private_message,
    handle_admin_reply,
)
from src.bot.commands import (
    cmd_start,
    cmd_help,
    cmd_membership_sharing,
    cmd_blacklist,
    cmd_whitelist,
    cmd_ai_test,
    cmd_mode,
    cmd_ping,
    cmd_status,
)
from src.services.scheduler import scheduler_service  # 调度服务（建议使用 BackgroundScheduler）

# 全局日志配置
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(settings, "LOG_LEVEL", logging.INFO),
)
log = logging.getLogger(__name__)


def main() -> None:
    """Entry point for AtriolyTgbot."""
    if not settings.TELEGRAM_BOT_TOKEN:
        log.error("❌ Error: TELEGRAM_BOT_TOKEN missing.")
        return

    # 1. 创建 Application（PTB 自己管理事件循环）
    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    # 2. Middleware (Priority -1)
    application.add_handler(TypeHandler(Update, gatekeeper_middleware), group=-1)

    # 3. Commands
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("mode", cmd_mode))
    application.add_handler(CommandHandler("ping", cmd_ping))
    application.add_handler(CommandHandler("status", cmd_status))
    application.add_handler(CommandHandler("membership_sharing", cmd_membership_sharing))
    application.add_handler(CommandHandler("blacklist", cmd_blacklist))
    application.add_handler(CommandHandler("whitelist", cmd_whitelist))
    application.add_handler(CommandHandler("ai_test", cmd_ai_test))

    # 4. Message Logic

    # A. 管理员在私聊里「回复转发消息」→ Bot 再转回原用户
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.REPLY & filters.TEXT,
            handle_admin_reply,
        )
    )

    # B. 普通私聊消息（用户 → Bot），走 AI 分类 + 转发 / Owner Secretary 模式
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT,
            handle_private_message,
        )
    )

    # C. 群消息（合租嗅探 + Spam 过滤）
    application.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT,
            handle_group_message,
        )
    )

    # 5. 启动调度器（注意：scheduler_service 内部请使用 BackgroundScheduler）
    scheduler_service.start(application)

    log.info("🟢 Atrioly · Wanatring Agent v3.0 Online (with scheduler).")

    # 6. 阻塞运行，PTB 自己创建/管理 asyncio 事件循环
    application.run_polling()


if __name__ == "__main__":
    main()
