from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ApplicationHandlerStop
from src.config import settings
from src.services.ai_agent import agent
from src.services.safety import safety_filter
from src.services.blacklist_manager import blacklist

async def gatekeeper_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
	user = update.effective_user
	if user and blacklist.is_banned(user.id):
		raise ApplicationHandlerStop

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
	msg = update.effective_message
	text = msg.text or ""
	user = update.effective_user

	# Layer 1: Heuristic
	if safety_filter.is_obvious_spam(text):
		return

	# Trigger Check
	triggers = ["车", "合租", "会员", "Netflix", "Disney", "YouTube", "HBO", "Prime", "sub", "share"]
	if not any(t.lower() in text.lower() for t in triggers):
		return 

	# Layer 2: AI
	analysis = await agent.analyze_message(text)

	# A. Spam Enforcement
	if analysis.get("is_spam"):
		status = blacklist.add_strike(user.id)
		reason = analysis.get('spam_reason', 'Spam detected')
		if status == "banned":
			await msg.reply_text(f"🚫 **System Alert**\nUser {user.mention_html()} banned.\nReason: {reason}", parse_mode="HTML")
		elif status == "warned":
			count = blacklist.get_strike_count(user.id)
			await msg.reply_text(f"⚠️ **Warning ({count}/3)**\n{user.mention_html()}, spam detected: {reason}", parse_mode="HTML")
		return

	# B. Membership Forwarding
	if analysis.get("is_membership"):
		alert = (
			f"💠 **Verified Opportunity**\n"
			f"🎬 Service: {analysis.get('platform')}\n"
			f"📊 Details: {analysis.get('summary')}\n"
			f"🔗 [Original Message]({msg.link})"
		)
		for admin in settings.FORWARD_TO:
			await context.bot.send_message(chat_id=admin, text=alert, parse_mode=ParseMode.MARKDOWN)
