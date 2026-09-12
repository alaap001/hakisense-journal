"""Durable, idempotent AI work with transactional credit reservations."""
import hashlib
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from fastapi import APIRouter, Depends, Header, HTTPException
from .db import database, AIJob, AITask, JobQueue, Wallet, CreditEntry, Message, Trade, uid, utcnow, serialize
from .auth import require_user, Identity, get_db
from .entitlements import wallet, lock_user, aware, available_credits
from .security import rate_limit
from .schemas import AIRequest
from .config import config
from .runtime_settings import settings, routing

router = APIRouter(prefix='/api/ai', tags=['AI'])


def view(job):
    return {'id': job.id, 'status': job.status, 'task': job.task_code, 'credits': job.credits,
            'created_at': job.created_at.isoformat(), 'result': job.result, 'error': job.error}


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
    if payload.expected_credits != task.credits:
        raise HTTPException(409, {'code':'price_changed','message':'The credit price has changed. Refresh and review the current price before trying again.'})
    row, plan = wallet(db)
    product = settings(db)
    route = routing(db, task.code, plan.model_tier)
    model = route['model_id']
    if not config.openrouter_key or not product.ai_enabled:
        raise HTTPException(503, 'AI is temporarily unavailable. No credits were used.')
    if payload.trade_id and not db.get(Trade, payload.trade_id):
        raise HTTPException(404, 'Trade not found.')
    if payload.thread_id and not db.scalar(select(Message.id).where(Message.thread_id == payload.thread_id).limit(1)):
        raise HTTPException(404, 'Conversation not found.')
    if row.balance < task.credits:
        raise HTTPException(402, {'code': 'insufficient_credits', 'message': f'This task needs {task.credits} credits. You have {row.balance} remaining.', 'upgrade': True})
    if db.scalar(select(AIJob.id).where(AIJob.status.in_(['queued', 'running'])).limit(1)):
        raise HTTPException(409, 'A review is already in progress. Open AI activity to view it.')
    rate_limit(db, 'ai:' + db.info['user_id'], product.ai_requests_per_minute, 60)
    job_id = uid()
    base_available = max(0, row.allocation - (row.spent - row.bonus_spent) + min(0, row.adjustment - row.bonus_spent))
    bonus_credits = max(0, task.credits - base_available)
    row.balance -= task.credits
    row.spent += task.credits
    row.bonus_spent += bonus_credits
    job = AIJob(id=job_id, idempotency_key=key, request_hash=digest, request=body, task_code=task.code,
                credits=task.credits, month=row.month, model=model, routing_config=route, bonus_credits=bonus_credits)
    db.add(job)
    db.add(CreditEntry(event_key='reserve:' + job_id, month=row.month, amount=-task.credits,
                       balance_after=row.balance, reason=task.name, job_id=job_id))
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
    queue = db.get(JobQueue, job_id)
    if queue and ((job.status == 'queued' and aware(queue.created_at) < utcnow() - timedelta(minutes=15)) or (job.status == 'running' and queue.claimed_at and aware(queue.claimed_at) < utcnow() - timedelta(minutes=5))):
        finish(db.info['user_id'], job_id, error='This review timed out. Your credits have been refunded.')
        db.refresh(job)
    return view(job)


def claim():
    with database(system=True) as db:
        row = db.scalar(select(JobQueue).where(JobQueue.claimed_at.is_(None)).order_by(JobQueue.created_at).limit(1).with_for_update(skip_locked=True))
        if not row:
            return None
        row.claimed_at = utcnow()
        return row.job_id, row.user_id


def finish(user_id, job_id, result=None, error=None):
    with database(user_id) as db:
        lock_user(db)
        job = db.scalar(select(AIJob).where(AIJob.id == job_id).with_for_update())
        if not job or job.status in ('succeeded', 'failed'):
            db.execute(delete(JobQueue).where(JobQueue.job_id == job_id))
            return
        if error:
            row = db.get(Wallet, (user_id, job.month))
            row.spent = max(0, row.spent - job.credits)
            row.bonus_spent = max(0, row.bonus_spent - job.bonus_credits)
            new_balance = available_credits(row)
            refund = new_balance - row.balance
            row.balance = new_balance
            db.add(CreditEntry(event_key='refund:' + job_id, month=job.month, amount=refund,
                               balance_after=row.balance, reason='AI task refunded', job_id=job_id))
            job.status, job.error = 'failed', error
        else:
            # Message persistence and credit settlement share one commit.
            thread_id = result['thread_id']
            db.add(Message(thread_id=thread_id, role='user', content=job.request['message']))
            db.add(Message(thread_id=thread_id, role='assistant', content=result['answer'],
                           metadata_json={'chart': result.get('chart'), 'mode': job.task_code, 'job_id': job.id}))
            job.status, job.result = 'succeeded', result
        job.finished_at = utcnow()
        db.execute(delete(JobQueue).where(JobQueue.job_id == job_id))


def expire_stale():
    cutoff = utcnow() - timedelta(minutes=5)
    waiting_cutoff = utcnow() - timedelta(minutes=15)
    with database(system=True) as db:
        rows = [(r.job_id, r.user_id) for r in db.scalars(select(JobQueue).where(
            (JobQueue.claimed_at < cutoff) | ((JobQueue.claimed_at.is_(None)) & (JobQueue.created_at < waiting_cutoff))).limit(100))]
    for job_id, user_id in rows:
        finish(user_id, job_id, error='This review could not finish. Your credits have been refunded; you can submit a new review.')
