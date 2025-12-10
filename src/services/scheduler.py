from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import ContextTypes
import datetime
from src.config import settings
from src.utils.calendar_utils import get_today_holidays
import logging

log = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self.context_app = None # Injected later in main.py
        self.started = False

    def start(self, app):
        self.context_app = app
        if not self.started:
            # 1. Daily Morning Greeting (07:00 UTC+8)
            self.scheduler.add_job(
                self._daily_greeting_job, 
                'cron', 
                hour=7, 
                minute=0
            )
            self.scheduler.start()
            self.started = True
            log.info("⏰ Scheduler started (Asia/Shanghai).")

    def schedule_one_off(self, entry: dict):
        """Schedule a specific /reminder."""
        try:
            run_date = datetime.datetime.fromisoformat(entry['datetime'])
            self.scheduler.add_job(
                self._send_reminder,
                'date',
                run_date=run_date,
                args=[entry]
            )
            log.info(f"⏰ Scheduled reminder: {entry['title']} at {run_date}")
        except Exception as e:
            log.error(f"Failed to schedule reminder: {e}")

    async def _send_reminder(self, entry):
        if not self.context_app: return
        text = f"🔔 **REMINDER**\n\n📌 **{entry.get('title')}**\n📝 {entry.get('note', '')}\n🏷 {entry.get('tags', '')}"
        for owner_id in settings.OWNER_IDS:
            await self.context_app.bot.send_message(chat_id=owner_id, text=text, parse_mode='Markdown')

    async def _daily_greeting_job(self):
        """Runs every day at 07:00 to check for festivals/days/annis."""
        if not self.context_app: return
        
        from src.services.task_manager import task_manager
        from src.services.ai_agent import agent
        
        # 1. Get Holidays
        holidays = get_today_holidays()
        
        # 2. Get Custom Days/Annis
        # (Simplified logic: Assuming client stores 'MM-DD' for recurring annis)
        # For full implementation, you'd parse the stored dates here.
        
        if not holidays:
            return # No greeting today

        # 3. Generate Greeting via AI
        event_names = ", ".join(holidays)
        greeting = await agent.generate_greeting(event_names)
        
        msg = f"🌅 **Morning Greeting**\n\n{greeting}"
        for owner_id in settings.OWNER_IDS:
            await self.context_app.bot.send_message(chat_id=owner_id, text=msg, parse_mode='Markdown')

scheduler_service = SchedulerService()