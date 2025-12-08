from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from src.config import settings
from src.services.blacklist_manager import blacklist
from src.services.membership import manager
from src.services.ai_agent import agent
from src.services.state_manager import state_manager

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    mode = state_manager.get_mode(user_id)
    await update.message.reply_text(
        f"💠 **Atrioly Agent Online**\n"
        f"Current Mode: `{mode.upper()}`\n"
        f"Use /help to see tools.",
        parse_mode=ParseMode.MARKDOWN
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = (
        "📚 **Atrioly Command List**\n"
        "`/membership_sharing` - View tracked memberships\n"
        "`/status` - System health\n"
        "`/ai_test <text>` - Test AI logic\n"
        "`/mode [chat|forward]` - Switch AI/Human routing\n"
        "`/ping` - Check bot responsiveness\n"
        "**Admin Only:**\n"
        "`/blacklist <uid>` - Ban user\n"
        "`/whitelist <uid>` - Unban user"
    )
    await update.message.reply_text(txt, parse_mode=ParseMode.MARKDOWN)

async def cmd_membership_sharing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    subs = manager.get_active()
    msg = "📡 **Membership Radar**\n\n" + ("\n".join([f"- {s['platform']} (Exp: {s['expiry']})" for s in subs]) if subs else "No active subscriptions.")
    await update.message.reply_text(msg, parse_mode=ParseMode.MARKDOWN)

async def cmd_blacklist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in settings.OWNER_IDS: return
    try:
        uid = int(context.args[0])
        blacklist.ban_user(uid)
        await update.message.reply_text(f"🚫 User {uid} added to blacklist.")
    except: await update.message.reply_text("Usage: /blacklist <uid>")

async def cmd_whitelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in settings.OWNER_IDS: return
    try:
        uid = int(context.args[0])
        if blacklist.unban_user(uid): await update.message.reply_text(f"✅ User {uid} unbanned.")
        else: await update.message.reply_text("User was not banned.")
    except: await update.message.reply_text("Usage: /whitelist <uid>")

async def cmd_ai_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return
    res = await agent.analyze_message(" ".join(context.args))
    await update.message.reply_text(f"```json\n{res}\n```", parse_mode=ParseMode.MARKDOWN)

async def cmd_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Switch between 'chat' (AI) and 'forward' (Human) mode."""
    if not context.args:
        await update.message.reply_text("Usage: `/mode [chat|forward]`", parse_mode=ParseMode.MARKDOWN)
        return
    
    new_mode = context.args[0].lower()
    if new_mode not in ["chat", "forward"]:
        await update.message.reply_text("Invalid mode. Use `chat` or `forward`.")
        return

    state_manager.set_mode(update.effective_user.id, new_mode)
    await update.message.reply_text(f"✅ Mode switched to: **{new_mode.upper()}**", parse_mode=ParseMode.MARKDOWN)

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! System operational.")
