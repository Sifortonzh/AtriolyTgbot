import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ApplicationHandlerStop
from src.config import settings
from src.services.ai_agent import agent
from src.services.safety import safety_filter
from src.services.blacklist_manager import blacklist

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
    log.info(f"📩 GROUP MSG RECEIVED | Group: '{chat_title}' | User: {user.full_name} | Text: '{text[:50]}...'")

    # --- 1. Zero-Cost Safety Check ---
    if safety_filter.is_obvious_spam(text):
        log.info(f"🛡️ SPAM DETECTED (Layer 1) | Dropping message from {user.id}")
        return

    # --- 2. Relevance Trigger Check ---
    # Define keywords (ensure these match your requirements)
    triggers = ["车", "合租", "会员", "Netflix", "奈飞", "Disney", "迪士尼", "YouTube", "HBO", "Prime", "sub", "share", "Apple", "Spotify"]
    
    # Check if ANY keyword is present
    is_relevant_keyword = any(t.lower() in text.lower() for t in triggers)
    
    if not is_relevant_keyword:
        # LOGGING: Verify why it stopped here
        log.info(f"⏭️ SKIPPED (No Keyword) | Text did not contain membership keywords.")
        return 
    else:
        log.info(f"✅ KEYWORD MATCHED | Proceeding to AI Analysis.")

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
        reason = analysis.get('spam_reason', 'Spam detected')
        log.warning(f"🤖 AI SPAM DETECTED | Reason: {reason}")
        
        status = blacklist.add_strike(user.id)
        
        if status == "banned":
            await msg.reply_text(
                f"🚫 **System Alert**\nUser {user.mention_html()} has been banned.\nReason: {reason}",
                parse_mode="HTML"
            )
            log.info(f"🚫 User {user.id} BANNED.")
        elif status == "warned":
            count = blacklist.get_strike_count(user.id)
            await msg.reply_text(
                f"⚠️ **Warning ({count}/3)**\n{user.mention_html()}, message flagged: {reason}",
                parse_mode="HTML"
            )
            log.info(f"⚠️ User {user.id} WARNED.")
        return

    # Branch B: Membership Opportunity
    if analysis.get("is_membership"):
        platform = analysis.get('platform', 'Unknown')
        summary = analysis.get('summary', 'No details')
        
        log.info(f"💎 MEMBERSHIP FOUND | Platform: {platform} | Forwarding to admins...")
        
        alert_msg = (
            f"💠 **Verified Opportunity**\n"
            f"🎬 **Service**: {platform}\n"
            f"📊 **Details**: {summary}\n"
            f"🔗 [Original Message]({msg.link})"
        )
        
        # Forward to Admins
        targets = settings.get_forward_targets()
        if not targets:
            log.warning("⚠️ No FORWARD_TO targets configured!")
            
        for admin in targets:
            try:
                await context.bot.send_message(chat_id=admin, text=alert_msg, parse_mode=ParseMode.MARKDOWN)
                log.info(f"🚀 Sent alert to Admin ID: {admin}")
            except Exception as e:
                log.error(f"❌ Failed to forward to {admin}: {e}")
    else:
        log.info("📉 AI determined message was NOT a membership offer.")