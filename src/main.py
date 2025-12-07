import logging
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, TypeHandler, filters
from telegram import Update
from src.config import settings
from src.bot.handlers import gatekeeper_middleware, handle_group_message
from src.bot.commands import cmd_start, cmd_help, cmd_membership_sharing, cmd_blacklist, cmd_whitelist, cmd_ai_test

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

def main():
	if not settings.TELEGRAM_BOT_TOKEN:
		print("❌ Error: TELEGRAM_BOT_TOKEN missing.")
		return

	app = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

	# 1. Gatekeeper (Priority -1)
	app.add_handler(TypeHandler(Update, gatekeeper_middleware), group=-1)

	# 2. Commands
	app.add_handler(CommandHandler("start", cmd_start))
	app.add_handler(CommandHandler("help", cmd_help))
	app.add_handler(CommandHandler("membership_sharing", cmd_membership_sharing))
	app.add_handler(CommandHandler("blacklist", cmd_blacklist))
	app.add_handler(CommandHandler("whitelist", cmd_whitelist))
	app.add_handler(CommandHandler("ai_test", cmd_ai_test))

	# 3. Message Logic
	app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT, handle_group_message))

	print("🟢 Atrioly · Wanatring Agent Online.")
	app.run_polling()

if __name__ == "__main__":
	main()
