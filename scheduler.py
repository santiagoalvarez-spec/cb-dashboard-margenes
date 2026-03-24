"""
Scheduler en background usando APScheduler.
Se inicializa una sola vez a nivel de módulo para sobrevivir re-runs de Streamlit.
"""
from __future__ import annotations

import threading
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler

_lock = threading.Lock()
_scheduler: BackgroundScheduler | None = None


def _get_scheduler() -> BackgroundScheduler:
    global _scheduler
    with _lock:
        if _scheduler is None or not _scheduler.running:
            _scheduler = BackgroundScheduler(timezone="America/Santiago")
            _scheduler.start()
    return _scheduler


def schedule_job(
    func: Callable,
    interval_hours: float,
    job_id: str = "auto_email",
) -> None:
    """Programa (o reprograma) un job periódico."""
    sched = _get_scheduler()
    sched.add_job(
        func,
        trigger="interval",
        hours=interval_hours,
        id=job_id,
        replace_existing=True,
    )


def remove_job(job_id: str = "auto_email") -> None:
    sched = _get_scheduler()
    if sched.get_job(job_id):
        sched.remove_job(job_id)


def is_job_active(job_id: str = "auto_email") -> bool:
    sched = _get_scheduler()
    return sched.get_job(job_id) is not None


def next_run_time(job_id: str = "auto_email") -> str:
    sched = _get_scheduler()
    job = sched.get_job(job_id)
    if job and job.next_run_time:
        return job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
    return "—"
