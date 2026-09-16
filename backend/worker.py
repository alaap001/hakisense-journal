"""Run separately: python -m backend.worker. Each process handles one AI job at a time."""
import asyncio
import logging
import signal
import json
import traceback
from pydantic import ValidationError
from sqlalchemy import select, delete
from .config import config
from .db import database, AIJob, RateBucket, utcnow
from .jobs import claim, finish, expire_stale, pause_job, finish_cancel
from .ai_runtime import Runtime, HumanInput, WorkflowCancelled, ProviderFailure
from .schemas import AIRequest
from . import ai

log = logging.getLogger('hakisense.worker')


def log_failure(exc, job_id=None):
    log.warning('ai_job_failed job_id=%s error_type=%s', job_id, type(exc).__name__)
    if isinstance(exc, ProviderFailure):
        # Controlled diagnostics and sanitized provider error explanations only.
        log.warning('ai_provider_failure job_id=%s reason=%s', job_id, str(exc))
    elif isinstance(exc, ValidationError):
        log.warning('ai_contract_failure job_id=%s fields=%s', job_id,
                    json.dumps(exc.errors(include_input=False, include_url=False), default=str))
    else:
        frames = [{'file': frame.filename, 'line': frame.lineno, 'function': frame.name} for frame in traceback.extract_tb(exc.__traceback__)]
        log.warning('ai_failure_location job_id=%s frames=%s', job_id, json.dumps(frames))
        original = getattr(exc, 'orig', None)
        if original is not None:
            log.warning('ai_database_failure job_id=%s driver_error=%s sqlstate=%s connection_invalidated=%s',
                        job_id, type(original).__name__, getattr(original, 'sqlstate', None), getattr(exc, 'connection_invalidated', None))


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
        job.heartbeat_at = utcnow()
        payload, model, route = AIRequest.model_validate(job.request), job.model, job.routing_config
        revision, maximum, checkpoint = job.revision, job.max_credits, job.checkpoint
    runtime = Runtime(user_id, job_id, revision, route, maximum)
    log.info('ai_job_started job_id=%s task=%s tier=%s', job_id, payload.mode, route.get('tier', 'standard'))
    async def heartbeat():
        while True:
            await asyncio.sleep(15)
            try:
                await asyncio.to_thread(runtime.active, True)
            except WorkflowCancelled:
                task.cancel()
                return
            with database(user_id) as db:
                active_job = db.get(AIJob, job_id)
                if active_job and active_job.status == 'running':
                    active_job.heartbeat_at = utcnow()
    task = asyncio.create_task(ai.ask(payload, user_id, model, route, runtime=runtime, checkpoint=checkpoint))
    heartbeat_task = asyncio.create_task(heartbeat())
    try:
        # A claimed job is never automatically replayed against a paid provider.
        result = await asyncio.wait_for(task, timeout=1800)
        await asyncio.to_thread(finish, user_id, job_id, result)
        log.info('ai_job_succeeded job_id=%s', job_id)
    except HumanInput as pause:
        with database(user_id) as db:
            saved = db.get(AIJob, job_id).checkpoint
        await asyncio.to_thread(pause_job, user_id, job_id, saved, {'kind': pause.kind, 'question': pause.question}, revision)
    except WorkflowCancelled:
        await asyncio.to_thread(finish_cancel, user_id, job_id)
    except asyncio.CancelledError:
        # Process shutdown is an interruption, not a customer-approved cancellation.
        await asyncio.to_thread(finish, user_id, job_id, None, 'This review was interrupted. Your credits were refunded.')
    except Exception as exc:
        log_failure(exc, job_id)
        message = 'The review could not be completed. Your credits have been refunded.'
        if isinstance(exc, ProviderFailure) and exc.status_code in (429, 502, 503, 504):
            message = 'The AI service is temporarily busy. Please try again shortly. Your credits have been refunded.'
        await asyncio.to_thread(finish, user_id, job_id, None, message)
    finally:
        heartbeat_task.cancel()
        await asyncio.gather(heartbeat_task, return_exceptions=True)
    return True


async def main():
    config.validate()
    log.info('ai_worker_started polling_seconds=2')
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
            log_failure(exc)
            try:
                await asyncio.wait_for(stop.wait(), timeout=5)
            except asyncio.TimeoutError:
                pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    asyncio.run(main())
