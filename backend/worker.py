"""Run separately: python -m backend.worker. Each process handles one AI job at a time."""
import asyncio
import logging
import signal
from sqlalchemy import select, delete
from .config import config
from .db import database, AIJob, RateBucket, utcnow
from .jobs import claim, finish, expire_stale
from .schemas import AIRequest
from . import ai

log = logging.getLogger('hakisense.worker')


async def run_one():
    item = await asyncio.to_thread(claim)
    if not item:
        return False
    job_id, user_id = item
    with database(user_id) as db:
        job = db.get(AIJob, job_id)
        if not job or job.status != 'queued':
            return True
        job.status = 'running'
        payload, model, route = AIRequest.model_validate(job.request), job.model, job.routing_config
    try:
        # A claimed job is never automatically replayed against a paid provider.
        result = await asyncio.wait_for(ai.ask(payload, user_id, model, route), timeout=200)
        await asyncio.to_thread(finish, user_id, job_id, result)
        log.info('ai_job_succeeded job_id=%s', job_id)
    except Exception as exc:
        log.warning('ai_job_failed job_id=%s error_type=%s', job_id, type(exc).__name__)
        await asyncio.to_thread(finish, user_id, job_id, None, 'The review could not be completed. Your credits have been refunded.')
    return True


async def main():
    config.validate()
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    tick = 0
    while not stop.is_set():
        try:
            if tick % 30 == 0:
                await asyncio.to_thread(expire_stale)
                with database(system=True) as db:
                    db.execute(delete(RateBucket).where(RateBucket.expires_at < utcnow()))
            worked = await run_one()
            tick += 1
            if not worked:
                try:
                    await asyncio.wait_for(stop.wait(), timeout=2)
                except asyncio.TimeoutError:
                    pass
        except Exception as exc:
            log.error('worker_iteration_failed error_type=%s', type(exc).__name__)
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(main())
