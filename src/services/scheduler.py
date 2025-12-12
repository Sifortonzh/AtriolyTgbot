import logging
import datetime
import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError

from src.config import settings
from src.utils.calendar_utils import get_today_holidays

log = logging.getLogger(__name__)


class SchedulerService:
    def __init__(self):
        # 独立后台调度器，不占用 PTB 自己的事件循环
        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self.context_app = None
        self.started = False

    def start(self, app):
        """
        由 main.py 调用，传入 PTB Application 以便内部发送消息。
        """
        self.context_app = app
        if self.started:
            log.info("⏰ Scheduler already started, skip.")
            return

        # 每天 7:00 统一做节日 & 特殊日子祝福
        self.scheduler.add_job(
            self._daily_greeting_job,
            CronTrigger(hour=7, minute=0),
            id="daily_greeting",
            replace_existing=True,
        )

        self.scheduler.start()
        self.started = True
        log.info("⏰ Scheduler started (Asia/Shanghai).")

    # ---------- Reminder 管理 ----------

    def schedule_reminder(self, entry: dict):
        """
        为单个 reminder 建立/更新调度任务。

        entry 里约定：
          - id: 唯一标识（int）
          - datetime: 事件发生时间（ISO 字符串，例 '2025-12-11T18:30:00'）
        实际提醒时间 = 事件时间 - 15 分钟
        """
        if not self.context_app:
            # 还没完成 start()，先不挂
            return

        try:
            event_dt = datetime.datetime.fromisoformat(entry["datetime"])
        except Exception as e:
            log.error(f"schedule_reminder: invalid datetime in entry {entry}: {e}")
            return

        # 提前 15 分钟提醒
        run_dt = event_dt - datetime.timedelta(minutes=15)
        now = datetime.datetime.now(tz=self.scheduler.timezone)

        # 如果提前 15 分钟已经过去，就直接跳过（或者你想也可以设为立即提醒）
        if run_dt < now:
            log.warning(
                f"Reminder time already passed (id={entry.get('id')}), "
                f"event={event_dt}, reminder={run_dt}"
            )
            return

        job_id = str(entry["id"])

        try:
            self.scheduler.add_job(
                self._send_reminder,
                "date",
                run_date=run_dt,
                args=[entry],
                id=job_id,
                replace_existing=True,  # 允许更新时间
            )
            log.info(
                f"⏰ Scheduled reminder (id={job_id}) at {run_dt} "
                f"for event {event_dt}"
            )
        except Exception as e:
            log.error(f"Failed to schedule reminder {entry}: {e}")

    def cancel_reminder(self, entry_id: int):
        """
        删除指定 reminder 对应的调度任务。
        """
        job_id = str(entry_id)
        try:
            self.scheduler.remove_job(job_id)
            log.info(f"⏰ Cancelled reminder job: {job_id}")
        except JobLookupError:
            log.warning(f"⚠️ Reminder job {job_id} not found (maybe already executed).")
        except Exception as e:
            log.error(f"Failed to cancel reminder {job_id}: {e}")

    # ---------- 内部工具：在独立事件循环中跑协程 ----------

    def _run_coro(self, coro):
        try:
            asyncio.run(coro)
        except RuntimeError:
            # 如果已有 loop，在新的 loop 中跑
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(coro)
            loop.close()

    # ---------- 具体 Job 回调 ----------

    def _send_reminder(self, entry: dict):
        """
        APScheduler 调用的真正任务：发送提醒消息。
        """
        if not self.context_app:
            return

        async def _inner():
            text = (
                f"🔔 **REMINDER**\n\n"
                f"📌 **{entry.get('title', '(no title)')}**\n"
                f"🕒 Event Time: {entry.get('datetime')}\n"
                f"📝 {entry.get('note', '')}\n"
            )
            tags = entry.get("tags")
            if tags:
                if isinstance(tags, (list, tuple)):
                    tags_str = ", ".join(str(t) for t in tags)
                else:
                    tags_str = str(tags)
                text += f"🏷 {tags_str}"

            for owner_id in settings.OWNER_IDS:
                await self.context_app.bot.send_message(
                    chat_id=owner_id,
                    text=text,
                    parse_mode="Markdown",
                )

        self._run_coro(_inner())

    def _daily_greeting_job(self):
        """
        每天 7:00：
          1. 根据内置节日库发送祝福
          2. 根据 tasks.json 里的 days / annis 发送自定义纪念日祝福
        """
        if not self.context_app:
            return

        from src.services.ai_agent import agent
        from src.services.task_manager import task_manager

        today = datetime.date.today()
        today_str = today.isoformat()

        async def _inner():
            # 1) 固定节日（阳历 + 农历由 calendar_utils 处理）
            holidays = get_today_holidays()
            if holidays:
                event_names = ", ".join(holidays)
                greeting = await agent.generate_greeting(event_names)
                msg = f"🌅 **Morning Greeting**\n\n{greeting}"
                for owner_id in settings.OWNER_IDS:
                    await self.context_app.bot.send_message(
                        chat_id=owner_id, text=msg, parse_mode="Markdown"
                    )

            # 2) 自定义 Days / Anniversaries
            # 约定：entry 里用 date 字段存 'YYYY-MM-DD'
            days = task_manager.get_entries("days")
            annis = task_manager.get_entries("annis")
            custom_events = []

            for d in days:
                if (d.get("date") or d.get("datetime")) == today_str:
                    custom_events.append(("Day", d))

            for a in annis:
                # annis 默认每年重复，可以只比对 MM-DD 也可以比对完整日期
                date_val = a.get("date") or a.get("datetime")
                if not date_val:
                    continue
                try:
                    dt_obj = datetime.date.fromisoformat(date_val)
                except Exception:
                    # 如果不是标准日期字符串，就直接全字符串比较
                    if date_val == today_str:
                        custom_events.append(("Anniversary", a))
                    continue

                if dt_obj.month == today.month and dt_obj.day == today.day:
                    custom_events.append(("Anniversary", a))

            for kind, entry in custom_events:
                title = entry.get("title", "(未命名)")
                name_for_ai = f"{kind}: {title}"
                greeting = await agent.generate_greeting(name_for_ai)
                text = (
                    f"🌅 **{kind} Reminder**\n\n"
                    f"📌 {title}\n"
                    f"📅 {entry.get('date') or entry.get('datetime') or today_str}\n\n"
                    f"{greeting}"
                )
                for owner_id in settings.OWNER_IDS:
                    await self.context_app.bot.send_message(
                        chat_id=owner_id, text=text, parse_mode="Markdown"
                    )

        self._run_coro(_inner())


scheduler_service = SchedulerService()