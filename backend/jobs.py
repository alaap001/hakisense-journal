"""Durable AI runs, whole-workflow reservations, resumable human input and replayable SSE."""
import asyncio
import hashlib
import json
from datetime import timedelta
from sqlalchemy import select, delete
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from .db import database, AIJob, AIEvent, AITask, JobQueue, Message, Trade, uid, utcnow
from .auth import require_user, get_db
from .entitlements import lock_user, aware
from .wallet import get_wallet, spend, refund_spend, settle_reservations
from .security import rate_limit
from .schemas import AIRequest, AIContinue
from .config import config
from .runtime_settings import settings, routing
from .ai_pricing import VERSION, charge
from . import ai_public

router = APIRouter(prefix='/api/ai', tags=['AI'])
TERMINAL = ('succeeded', 'failed', 'cancelled', 'partial')


def view(job):
    return {'id': job.id, 'status': job.status, 'task': job.task_code, 'credits': job.credits,
            'revision': job.revision, 'pause': ai_public.pause(job.pause), 'event_sequence': job.event_sequence,
            'cancel_requested': job.cancel_requested,
            'thread_id': job.request.get('thread_id'), 'message': job.request.get('message'),
            'created_at': job.created_at.isoformat(), 'result': ai_public.result(job.result), 'error': job.error}


def event(db, job, kind, data):
    job.event_sequence += 1
    db.add(AIEvent(job_id=job.id, sequence=job.event_sequence, kind=kind, data=data))


def emit(user_id, job_id, kind, data, revision=None):
    with database(user_id) as db:
        job = db.scalar(select(AIJob).where(AIJob.id == job_id).with_for_update())
        if not job or job.status != 'running' or (revision is not None and job.revision != revision):
            return
        event(db, job, kind, data)
        job.heartbeat_at = utcnow()


def validate_target(db, payload):
    if payload.trade_id and not db.get(Trade, payload.trade_id):
        raise HTTPException(404, 'Trade not found.')
    if payload.mode == 'trade_note' and not payload.trade_id:
        raise HTTPException(422, 'Select a trade to review.')
    if payload.thread_id and not db.scalar(select(Message.id).where(Message.thread_id == payload.thread_id).limit(1)):
        raise HTTPException(404, 'Conversation not found.')


@router.post('/estimate')
def estimate(payload: AIRequest, db=Depends(get_db)):
    validate_target(db, payload)
    # A free, deterministic quote; no journal scan and no model invocation while typing.
    balance = max(0, get_wallet(db).balance)
    return {'min_credits': 1, 'max_credits': 7,
            'affordable_max': max((c for c in (1, 2, 3, 4, 7) if c <= balance), default=0),
            'scope': payload.filters.model_dump(),
            'message': 'Reviews cost 1–7 credits. You are charged for the work used; unused credits are returned.'}


def enqueue(db, payload, key):
    if not key or not 8 <= len(key) <= 100:
        raise HTTPException(400, 'Provide an Idempotency-Key of 8–100 characters.')
    body = payload.model_dump()
    digest = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    lock_user(db)
    existing = db.scalar(select(AIJob).where(AIJob.idempotency_key == key))
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(409, 'This request key belongs to a different AI request.')
        return existing
    task = db.get(AITask, payload.mode)
    if not task or not task.enabled:
        raise HTTPException(403, 'This AI task is not currently available.')
    product = settings(db)
    if not config.openrouter_key or not product.ai_enabled:
        raise HTTPException(503, 'AI is temporarily unavailable. No credits were used.')
    if payload.pricing_version and payload.pricing_version != VERSION:
        raise HTTPException(409, {'code': 'price_changed', 'message': 'AI pricing has changed. Refresh before starting a review.'})
    validate_target(db, payload)
    if db.scalar(select(AIJob.id).where(AIJob.status.in_(['queued', 'running', 'awaiting_input'])).limit(1)):
        raise HTTPException(409, 'A review is already active. Open AI activity to continue or stop it.')
    rate_limit(db, 'ai:' + db.info['user_id'], product.ai_requests_per_minute, 60)
    row = get_wallet(db)
    # Reserve an affordable ceiling internally. Honor explicit limits from older clients.
    maximum = payload.max_credits or max((c for c in (1, 2, 3, 4, 7) if c <= row.balance), default=1)
    route = routing(db, task.code, payload.model_tier)
    job_id = uid()
    spend(db, 'reserve:' + job_id, maximum, 'AI review credit reservation', {'job_id': job_id})
    job = AIJob(id=job_id, idempotency_key=key, request_hash=digest, request=body, task_code=task.code,
                credits=0, max_credits=maximum, pricing_version=VERSION, month=row.free_month,
                model=route['model_id'], routing_config=route, bonus_credits=0,
                usage={'input_tokens': 0, 'output_tokens': 0, 'calls': 0}, checkpoint={}, event_sequence=0, revision=0)
    db.add(job)
    db.flush()
    event(db, job, 'status', {'stage': 'queued', 'message': 'Your workflow is queued.'})
    db.add(JobQueue(job_id=job_id, user_id=db.info['user_id']))
    db.flush()
    return job


@router.post('/query', status_code=202)
def submit(payload: AIRequest, idempotency_key: str | None = Header(default=None), db=Depends(get_db)):
    return view(enqueue(db, payload, idempotency_key))


@router.get('/jobs')
def list_jobs(db=Depends(get_db)):
    return [view(j) for j in db.scalars(select(AIJob).order_by(AIJob.created_at.desc()).limit(30))]


@router.get('/jobs/{job_id}')
def get_job(job_id: str, db=Depends(get_db)):
    job = db.get(AIJob, job_id)
    if not job:
        raise HTTPException(404, 'AI task not found.')
    return view(job)


@router.post('/jobs/{job_id}/continue', status_code=202)
def continue_job(job_id: str, payload: AIContinue, db=Depends(get_db)):
    lock_user(db)
    job = db.scalar(select(AIJob).where(AIJob.id == job_id).with_for_update())
    if not job:
        raise HTTPException(404, 'AI task not found.')
    # A duplicate continuation cannot reserve or enqueue again.
    if payload.revision < job.revision:
        return view(job)
    if job.status != 'awaiting_input' or payload.revision != job.revision:
        raise HTTPException(409, 'This review has changed. Refresh its progress.')
    if job.pause['kind'] == 'clarification' and not payload.answer.strip():
        raise HTTPException(422, 'Please answer the clarification before continuing.')
    maximum = payload.max_credits or job.max_credits
    if maximum < job.max_credits:
        raise HTTPException(422, 'An active reservation cannot be reduced. Stop the review to release it.')
    # Recover legacy capacity pauses without asking customers to interpret internal limits.
    if job.pause['kind'] != 'clarification':
        available = get_wallet(db).balance + job.max_credits
        maximum = max((c for c in (1, 2, 3, 4, 7) if c <= available), default=job.max_credits)
    if maximum > job.max_credits:
        spend(db, f'reserve:{job.id}:{job.revision + 1}', maximum-job.max_credits, 'AI workflow reservation extended', {'job_id': job.id})
    state = dict(job.checkpoint)
    if job.pause['kind'] != 'clarification':
        state['node'] = 'coordinate'
    if payload.answer.strip():
        state['clarifications'] = [*state.get('clarifications', []), {'question': job.pause['question'], 'answer': payload.answer.strip()}]
        state['node'] = 'coordinate'
    job.checkpoint, job.max_credits = state, maximum
    job.pause, job.status = None, 'queued'
    job.revision += 1
    job.cancel_requested = False
    event(db, job, 'status', {'stage': 'queued', 'message': 'Continuing your workflow.'})
    db.add(JobQueue(job_id=job.id, user_id=db.info['user_id']))
    return view(job)


@router.post('/jobs/{job_id}/cancel')
def cancel_job(job_id: str, db=Depends(get_db)):
    lock_user(db)
    job = db.scalar(select(AIJob).where(AIJob.id == job_id).with_for_update())
    if not job:
        raise HTTPException(404, 'AI task not found.')
    if job.status in TERMINAL:
        return view(job)
    job.cancel_requested = True
    if job.status == 'running':
        # Finish the already dispatched call for its receipt; never dispatch another agent.
        event(db, job, 'status', {'stage': 'stopping', 'message': 'Stopping after the current step; recording its actual usage.'})
    else:
        cancel_settlement(db, job)
    return view(job)


def cancel_settlement(db, job):
    actual = charge(job.usage.get('input_tokens', 0), job.usage.get('output_tokens', 0))
    settle_reservations(db, job.id, actual)
    job.status, job.credits, job.finished_at = 'cancelled', actual, utcnow()
    job.checkpoint = {}
    job.pause = None
    event(db, job, 'done', {'status': 'cancelled', 'credits': actual})
    db.execute(delete(JobQueue).where(JobQueue.job_id == job.id))


def finish_cancel(user_id, job_id):
    with database(user_id) as db:
        lock_user(db)
        job = db.scalar(select(AIJob).where(AIJob.id == job_id).with_for_update())
        if job and job.status not in TERMINAL:
            cancel_settlement(db, job)


def stream_snapshot(user_id, job_id, after):
    with database(user_id) as db:
        job = db.get(AIJob, job_id)
        if not job:
            raise HTTPException(404, 'AI task not found.')
        rows = list(db.scalars(select(AIEvent).where(AIEvent.job_id == job_id, AIEvent.sequence > after).order_by(AIEvent.sequence).limit(200)))
        return view(job), [{'id': e.sequence, 'kind': e.kind if e.kind != 'usage' else 'progress',
                            'data': ai_public.event(e.kind, e.data)} for e in rows]


@router.get('/jobs/{job_id}/events')
async def stream_events(job_id: str, request: Request, after: int = 0, user=Depends(require_user)):
    if after < 0:
        raise HTTPException(422, 'Invalid event cursor')
    await asyncio.to_thread(stream_snapshot, user.id, job_id, after)
    async def frames():
        cursor = after
        while not await request.is_disconnected():
            job, events = await asyncio.to_thread(stream_snapshot, user.id, job_id, cursor)
            for item in events:
                cursor = item['id']
                yield f"id: {cursor}\nevent: {item['kind']}\ndata: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
            if cursor >= job['event_sequence'] and (job['status'] in TERMINAL or job['status'] == 'awaiting_input'):
                yield 'event: snapshot\ndata: ' + json.dumps(job, ensure_ascii=False) + '\n\n'
                return
            yield ': keepalive\n\n'
            await asyncio.sleep(0.75)
    return StreamingResponse(frames(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})


def claim():
    with database(system=True) as db:
        row = db.scalar(select(JobQueue).where(JobQueue.claimed_at.is_(None)).order_by(JobQueue.created_at).limit(1).with_for_update(skip_locked=True))
        if not row:
            return None
        row.claimed_at = utcnow()
        return row.job_id, row.user_id


def pause_job(user_id, job_id, state, pause, revision):
    with database(user_id) as db:
        lock_user(db)
        job = db.scalar(select(AIJob).where(AIJob.id == job_id).with_for_update())
        if not job or job.status != 'running' or job.revision != revision:
            return
        if job.cancel_requested:
            cancel_settlement(db, job)
            return
        job.checkpoint, job.pause, job.status = state, pause, 'awaiting_input'
        job.heartbeat_at = utcnow()
        event(db, job, 'pause', pause)
        db.execute(delete(JobQueue).where(JobQueue.job_id == job_id))


def finish(user_id, job_id, result=None, error=None):
    with database(user_id) as db:
        lock_user(db)
        job = db.scalar(select(AIJob).where(AIJob.id == job_id).with_for_update())
        if not job or job.status in TERMINAL:
            return
        if job.cancel_requested and not error:
            cancel_settlement(db, job)
            return
        if error:
            if job.pricing_version == 'legacy':
                refund_spend(db, 'reserve:'+job_id, 'refund:'+job_id, 'AI task refunded')
            else:
                settle_reservations(db, job_id, 0, failed=True)
            job.status, job.error, job.credits = 'failed', error, 0
        else:
            actual = charge(job.usage.get('input_tokens', 0), job.usage.get('output_tokens', 0)) if job.pricing_version == VERSION else job.credits
            if job.pricing_version == VERSION:
                settle_reservations(db, job_id, actual)
            result = {**result, 'credits': actual, 'usage': job.usage, 'job_id': job.id}
            thread_id = result['thread_id']
            question = job.request['message']
            clarifications = job.checkpoint.get('clarifications', [])
            if clarifications:
                question += '\n\n' + '\n'.join('Clarification: ' + c['answer'] for c in clarifications)
            db.add(Message(thread_id=thread_id, role='user', content=question))
            db.add(Message(thread_id=thread_id, role='assistant', content=result['answer'], metadata_json={
                'chart': result.get('chart'), 'mode': job.task_code, 'job_id': job.id,
                'credits': actual}))
            job.status, job.result, job.credits = 'succeeded', result, actual
        job.pause, job.finished_at = None, utcnow()
        # Only completed output and compact provenance survive in the job after settlement.
        job.checkpoint = {}
        event(db, job, 'done', {'status': job.status, 'credits': job.credits})
        db.execute(delete(JobQueue).where(JobQueue.job_id == job_id))


def expire_stale():
    with database(system=True) as db:
        rows = [(r.job_id, r.user_id) for r in db.scalars(select(JobQueue).where(
            (JobQueue.claimed_at < utcnow()-timedelta(minutes=3)) |
            ((JobQueue.claimed_at.is_(None)) & (JobQueue.created_at < utcnow()-timedelta(minutes=15)))).limit(100))]
    for job_id, user_id in rows:
        with database(user_id) as db:
            job = db.get(AIJob, job_id)
            alive = job and job.heartbeat_at and aware(job.heartbeat_at) > utcnow()-timedelta(minutes=3)
        if not alive:
            finish(user_id, job_id, error='This review was interrupted. Your credits were refunded. No paid call was replayed.')
