"""Post scheduler service backed by APScheduler.

Maintains an in-process job store and exposes helpers to:
    - Schedule a PostJob for a future time
    - Retry failed jobs
    - Enforce daily posting windows
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Callable, Coroutine, List, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from app.config import get_settings
from app.models.post import PostJob, PostStatus

logger = logging.getLogger(__name__)


class PostScheduler:
    """Wraps APScheduler to schedule and manage Instagram post jobs.

    Usage::

        scheduler = PostScheduler()
        scheduler.start()
        scheduler.schedule_job(job, publish_fn)
        ...
        scheduler.shutdown()
    """

    def __init__(self, timezone: str = "America/Sao_Paulo") -> None:
        self._tz = ZoneInfo(timezone)
        self._scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": AsyncIOExecutor()},
            job_defaults={"coalesce": False, "max_instances": 1},
        )
        self._settings = get_settings()

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the underlying APScheduler instance."""
        if not self._scheduler.running:
            self._scheduler.start()
            logger.info("PostScheduler started")

    def shutdown(self) -> None:
        """Gracefully shut down the scheduler."""
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("PostScheduler stopped")

    # ── Scheduling ────────────────────────────────────────────────────────

    def schedule_job(
        self,
        job: PostJob,
        publish_fn: Callable[[PostJob], Coroutine],
        run_at: Optional[datetime] = None,
    ) -> PostJob:
        """Schedule *job* to be published at *run_at*.

        Args:
            job: The post job to schedule.
            publish_fn: Async callable that accepts a :class:`PostJob`.
            run_at: When to publish.  Defaults to the next available
                posting window.

        Returns:
            The updated *job* with ``scheduled_time`` and
            ``status=SCHEDULED`` set.
        """
        if run_at is None:
            run_at = self.next_posting_window()

        job.scheduled_time = run_at
        job.status = PostStatus.SCHEDULED

        self._scheduler.add_job(
            publish_fn,
            "date",
            run_date=run_at,
            args=[job],
            id=job.job_id,
            replace_existing=True,
        )
        logger.info("Scheduled job %s for %s", job.job_id, run_at.isoformat())
        return job

    def schedule_retry(
        self,
        job: PostJob,
        publish_fn: Callable[[PostJob], Coroutine],
        delay_minutes: int = 30,
    ) -> PostJob:
        """Reschedule a failed *job* after *delay_minutes*.

        Args:
            job: The failed job to retry.
            publish_fn: Publish coroutine.
            delay_minutes: Retry delay (default 30 min).

        Returns:
            The updated *job*.
        """
        retry_at = datetime.now(tz=self._tz) + timedelta(minutes=delay_minutes)
        logger.info("Retrying job %s at %s", job.job_id, retry_at.isoformat())
        return self.schedule_job(job, publish_fn, run_at=retry_at)

    # ── Window logic ──────────────────────────────────────────────────────

    def next_posting_window(self) -> datetime:
        """Return the next available posting time within the configured hours.

        Reads ``POSTING_HOURS`` from settings (comma-separated 24-h values,
        e.g. ``"9,12,18,20"``).

        Returns:
            A timezone-aware :class:`datetime` for the next posting slot.
        """
        hours: List[int] = [
            int(h.strip()) for h in self._settings.posting_hours.split(",") if h.strip().isdigit()
        ]
        if not hours:
            hours = [9, 12, 18, 20]

        now = datetime.now(tz=self._tz)
        # Look for the next slot today or tomorrow
        for delta_days in range(2):
            for hour in sorted(hours):
                candidate = now.replace(
                    hour=hour, minute=0, second=0, microsecond=0
                ) + timedelta(days=delta_days)
                if candidate > now:
                    return candidate

        # Fallback: 1 hour from now
        return now + timedelta(hours=1)

    # ── Status ────────────────────────────────────────────────────────────

    def list_pending(self) -> list:
        """Return all APScheduler jobs currently queued."""
        return self._scheduler.get_jobs()
