import logging
import signal

from apscheduler.schedulers.blocking import BlockingScheduler

from app.ingest.runner import due_sources, run_source

log = logging.getLogger("worker")
TICK_SECONDS = 60


def tick() -> None:
    for key in due_sources():
        result = run_source(key)
        log.info("ingestion %s: %s", key, result)


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(tick, "interval", seconds=TICK_SECONDS, max_instances=1, coalesce=True, id="ingestion-tick")
    signal.signal(signal.SIGTERM, lambda *_: scheduler.shutdown(wait=False))
    log.info("worker started, checking sources every %s seconds", TICK_SECONDS)
    tick()
    scheduler.start()
