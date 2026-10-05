import logging
import signal

from apscheduler.schedulers.blocking import BlockingScheduler

from app.db import scalar, transaction
from app.ingest.runner import due_sources, run_source

log = logging.getLogger("worker")
TICK_SECONDS = 60


def needs_backfill(key: str) -> bool:
    if key != "usgs":
        return False
    with transaction() as conn:
        return not scalar(conn, "select 1 from historical_event where source_key = 'usgs' limit 1")


def tick() -> None:
    for key in due_sources():
        result = run_source(key, backfill=True) if needs_backfill(key) else run_source(key)
        log.info("ingestion %s: %s", key, result)


def main() -> None:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(tick, "interval", seconds=TICK_SECONDS, max_instances=1, coalesce=True, id="ingestion-tick")
    signal.signal(signal.SIGTERM, lambda *_: scheduler.shutdown(wait=False))
    log.info("worker started, checking sources every %s seconds", TICK_SECONDS)
    tick()
    scheduler.start()
