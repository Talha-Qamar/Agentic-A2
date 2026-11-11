"""Arq worker: `arq worker.main.WorkerSettings` (docker compose `worker` service).
In the single-process Render deployment the same worker runs as a background task of the web process."""
from __future__ import annotations

import os

from arq import cron
from arq.connections import RedisSettings

from worker.tasks import analyse_job, converse, resume_thread, scout, sync_pipeline, tick


async def startup(ctx):
    from agent.tracing import setup_tracing
    from common import db
    db.init_schema()
    setup_tracing("gigbid-worker")


class WorkerSettings:
    functions = [analyse_job, resume_thread, converse, scout, sync_pipeline, tick]
    cron_jobs = [cron(tick, minute=set(range(0, 60, int(os.environ.get("TICK_MINUTES", "5")))), run_at_startup=False)]
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://localhost:6379"))
    on_startup = startup
    max_jobs = int(os.environ.get("WORKER_CONCURRENCY", "4"))
    job_timeout = 900
    keep_result = 3600
