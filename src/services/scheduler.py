import logging
import datetime
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.utils.calendar_utils import get_today_holidays

log = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        # 使用线程版调度器，不依赖 asyncio 事件循环
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.context_app = None  # 在 main.py 中注入
        self.started = False

    def start(self, app):
        """
        在 main() 里调用：scheduler_service.start(application)
        """
        self.context_app = app
        if self.started:
            log.info("⏰ Scheduler already started, skip.")
            return

        # 1. 每天早上 07:00 的节日/纪念日问候
        self.scheduler.add_job(
            self._daily_greeting_job,
            CronTrigger(hour=7, minute=0),
            id="daily_greeting",
            replace_existing=True,
        )

        self.scheduler.start()
        self.started = True
        log.info("⏰ Scheduler started (Asia/Shanghai).")

    # ------- 公共方法：用于一锤子提醒（/reminder） -------

    def schedule_one_off(self, entry: dict):
        """Schedule a specific /reminder."""
        try:
            run_date = datetime.datetime.fromisoformat(entry["datetime"])
            self.scheduler.add_job(
                self._send_reminder,
                "date",
                run_date=run_date,
                args=[entry],
            )
            log.info(f"⏰ Scheduled reminder: {entry['title']} at {run_date}")
        except Exception as e:
            log.error(f"Failed to schedule reminder: {e}")

    # ------- 内部工具：在调度线程里跑协程 -------

    def _run_coro(self, coro):
        """
        在调度器所在的线程里执行异步函数。
        优先用 asyncio.run，如遇到已有 loop 再手动建一个。
        """
        try:
            asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
            loop.close()

    # ------- 具体 Job 实现 -------

    def _send_reminder(self, entry: dict):
        """
        真正执行提醒的 Job（同步函数，由 BackgroundScheduler 调用）。
        """
        if not self.context_app:
            return

        async def _inner():
            text = (
                f"🔔 **REMINDER**\n\n"
                f"📌 **{entry.get('title')}**\n"
                f"📝 {entry.get('note', '')}\n"
                f"🏷 {entry.get('tags', '')}"
            )
            for owner_id in settings.OWNER_IDS:
                await self.context_app.bot.send_message(
                    chat_id=owner_id, text=text, parse_mode="Markdown"
                )

        self._run_coro(_inner())

    def _daily_greeting_job(self):
        """
        每天 07:00 触发：检查今日节日/纪念日并发送问候。
        """
        if not self.context_app:
            return

        from src.services.task_manager import task_manager  # 预留，将来可用
        from src.services.ai_agent import agent

        # 1. 获取今天的节日（西方 + 农历等，由 get_today_holidays 封装）
        holidays = get_today_holidays()
        # 将来这里可以再加：从 task_manager 获取自定义 /days /annis

        if not holidays:
            return  # 今天没有节日，不发

        event_names = ", ".join(holidays)

        async def _inner():
            # 2. 让 AI 生成一条文艺问候
            greeting = await agent.generate_greeting(event_names)
            msg = f"🌅 **Morning Greeting**\n\n{greeting}"

            # 3. 发送给所有 OWNER
            for owner_id in settings.OWNER_IDS:
                await self.context_app.bot.send_message(
                    chat_id=owner_id, text=msg, parse_mode="Markdown"
                )

        self._run_coro(_inner())


scheduler_service = SchedulerService()
