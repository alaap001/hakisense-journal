"""Subscription access is derived from verified, paid provider invoices."""
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlparse
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool
from .config import config
from .db import database, Price, Plan, Subscription, Checkout, SubscriptionIndex, WebhookEvent, Payment, CreditEntry, serialize, utcnow
from .auth import Identity, require_user, get_db
from .entitlements import lock_user, snapshot, public_catalog, aware, wallet
from .payments import provider
from .security import rate_limit
from .runtime_settings import settings, checkout_ready

router = APIRouter(prefix='/api/billing', tags=['Billing'])
webhooks = APIRouter(tags=['Payment webhooks'])


@router.get('/catalog')
def catalog_route():
    with database(system=True) as db:
        return public_catalog(db)


@router.get('/me')
def me(db=Depends(get_db)):
    return snapshot(db)


@router.get('/history')
def history(db=Depends(get_db)):
    return {'credits': [serialize(c) for c in db.scalars(select(CreditEntry).order_by(CreditEntry.created_at.desc()).limit(100))],
            'payments': [serialize(p) for p in db.scalars(select(Payment).order_by(Payment.created_at.desc()).limit(36))]}


class CheckoutInput(BaseModel):
    price_code: str = Field(max_length=100)
    expected_amount_paise: int | None = Field(default=None, ge=1)


def bind_checkout(db, checkout, remote):
    price = db.get(Price, checkout.price_code)
    if remote.get('plan_id') != price.provider_plan_id or remote.get('notes', {}).get('hakisense_checkout') != checkout.id:
        raise HTTPException(409, 'Checkout details did not match. Contact support.')
    url = remote.get('short_url', '')
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ('rzp.io', 'razorpay.com', 'rzp.io.in'):
        raise HTTPException(502, 'The payment link could not be verified.')
    index = db.get(SubscriptionIndex, remote['id'])
    if not index:
        index = SubscriptionIndex(provider_id=remote['id'], user_id=db.info['user_id'], price_code=price.code,
            amount_paise=price.amount_paise, provider_plan_id=price.provider_plan_id, payment_url=url)
        db.add(index)
    elif index.user_id != db.info['user_id']:
        raise HTTPException(409, 'Checkout ownership did not match.')
    checkout.provider_id, checkout.status = remote['id'], 'ready'
    return {'id': checkout.id, 'url': url, 'status': checkout.status}


@router.post('/checkout')
def create_checkout(payload: CheckoutInput, identity: Identity = Depends(require_user), idempotency_key: str | None = Header(default=None)):
    if not idempotency_key or not 8 <= len(idempotency_key) <= 100:
        raise HTTPException(400, 'A valid Idempotency-Key is required.')
    with database(identity.id) as db:
        if not checkout_ready(settings(db)):
            raise HTTPException(503, 'Subscriptions will be available soon. Your free plan remains available.')
        lock_user(db)
        rate_limit(db, 'checkout:' + identity.id, 5, 60)
        price = db.scalar(select(Price).where(Price.code == payload.price_code).with_for_update(read=True))
        if not price or not price.active or not price.provider_plan_id:
            raise HTTPException(400, 'This subscription is not currently available.')
        plan = db.get(Plan, price.plan_code)
        if not plan or not plan.active:
            raise HTTPException(400, 'This plan is not available for new subscriptions.')
        if payload.expected_amount_paise != price.amount_paise:
            raise HTTPException(409, {'code':'price_changed','message':'This price has changed. Refresh and review the price before continuing.'})
        sub = db.get(Subscription, identity.id)
        if sub and sub.paid_until and aware(sub.paid_until) > utcnow():
            raise HTTPException(409, 'You already have a paid subscription. You can cancel renewal and choose a new plan after the current paid period.')
        checkout = db.scalar(select(Checkout).where(Checkout.idempotency_key == idempotency_key))
        if checkout and checkout.price_code != price.code:
            raise HTTPException(409, 'This checkout key belongs to another price.')
        if checkout and checkout.status == 'closed':
            raise HTTPException(409, {'code':'checkout_closed','message':'That checkout has closed. Choose your plan again to start a new checkout.'})
        fresh = False
        if not checkout:
            pending = db.scalar(select(Checkout).where(Checkout.status.in_(['creating', 'uncertain', 'ready'])).order_by(Checkout.created_at.desc()).limit(1))
            if pending:
                checkout = pending
                if pending.price_code != price.code:
                    raise HTTPException(409, 'A checkout is already pending. Complete or cancel it before choosing another plan.')
            else:
                checkout = Checkout(idempotency_key=idempotency_key, price_code=price.code)
                db.add(checkout)
                db.flush()
                fresh = True
        checkout_id, provider_id = checkout.id, checkout.provider_id
        plan_id, interval, amount = price.provider_plan_id, price.interval, price.amount_paise
        is_fresh = fresh
    if provider_id:
        remote = provider.subscription(provider_id)
        if remote['status'] in ('cancelled', 'expired', 'completed'):
            with database(identity.id) as db:
                lock_user(db)
                db.get(Checkout, checkout_id).status = 'closed'
            raise HTTPException(409, {'code':'checkout_closed','message':'That checkout has closed. Choose your plan again to create a new checkout.'})
        with database(identity.id) as db:
            lock_user(db)
            return bind_checkout(db, db.get(Checkout, checkout_id), remote)
    if not is_fresh:
        # Razorpay subscription creation has no assumed idempotency support. Never blindly POST a second time.
        recent = provider.request('GET', 'subscriptions', params={'count': 100}).get('items', [])
        remote = next((s for s in recent if s.get('notes', {}).get('hakisense_checkout') == checkout_id), None)
        if not remote:
            raise HTTPException(409, 'Checkout confirmation is pending. Contact support if it does not appear; no second checkout was created.')
    else:
        try:
            remote_plan = provider.plan(plan_id)
            item = remote_plan.get('item', {})
            if item.get('amount') != amount or item.get('currency') != 'INR' or remote_plan.get('period') != ('monthly' if interval == 'month' else 'yearly') or remote_plan.get('interval') != 1:
                raise HTTPException(503, 'This subscription is temporarily unavailable.')
            remote = provider.create_subscription(plan_id, interval, checkout_id, identity.id)
        except Exception:
            with database(identity.id) as db:
                lock_user(db)
                db.get(Checkout, checkout_id).status = 'uncertain'
            raise
    with database(identity.id) as db:
        lock_user(db)
        return bind_checkout(db, db.get(Checkout, checkout_id), remote)


def verify_invoice(index, invoice, payment):
    if invoice.get('subscription_id') != index.provider_id or invoice.get('status') != 'paid':
        return None
    if payment.get('id') != invoice.get('payment_id') or payment.get('invoice_id') != invoice.get('id'):
        raise HTTPException(502, 'Payment and invoice did not match.')
    if payment.get('status') not in ('captured', 'refunded') or payment.get('currency') != 'INR' or invoice.get('currency') != 'INR':
        return None
    if invoice.get('amount_paid') != index.amount_paise or payment.get('amount') != index.amount_paise or invoice.get('amount_due', 0) != 0:
        raise HTTPException(502, 'Payment amount did not match the subscription price.')
    start, end = invoice.get('billing_start'), invoice.get('billing_end')
    if not isinstance(start, int) or not isinstance(end, int) or end <= start:
        raise HTTPException(502, 'The billing period is awaiting confirmation.')
    return datetime.fromtimestamp(start, timezone.utc), datetime.fromtimestamp(end, timezone.utc)


def apply_verified(db, index, remote, pairs, dispute_payment=None, dispute_status=None):
    lock_user(db)
    if remote.get('id') != index.provider_id or remote.get('plan_id') != index.provider_plan_id:
        raise HTTPException(409, 'Subscription identity did not match.')
    sub = db.get(Subscription, db.info['user_id'])
    for invoice, payment in pairs:
        period = verify_invoice(index, invoice, payment)
        if period is None:
            continue
        row = db.get(Payment, payment['id'])
        if not row:
            row = Payment(id=payment['id'], provider_subscription_id=index.provider_id, amount_paise=index.amount_paise,
                          status='paid', period_start=period[0], period_end=period[1], price_code=index.price_code)
            db.add(row)
        if payment.get('amount_refunded', 0) >= payment['amount']:
            row.status = 'refunded'
        if dispute_payment == payment['id']:
            row.status = 'paid' if dispute_status == 'won' else 'disputed'
    db.flush()
    paid = db.scalar(select(Payment).where(Payment.status == 'paid', Payment.period_start <= utcnow(), Payment.period_end > utcnow()).order_by(Payment.period_end.desc()).limit(1))
    if paid:
        price = db.get(Price, paid.price_code)
        if sub.provider_id != paid.provider_subscription_id:
            sub.cancel_at_period_end = False
        sub.plan_code, sub.price_code = price.plan_code, paid.price_code
        sub.provider_id, sub.last_payment_id, sub.paid_until = paid.provider_subscription_id, paid.id, paid.period_end
        if paid.provider_subscription_id == index.provider_id:
            sub.status = remote.get('status', 'active')
            sub.cancel_at_period_end = sub.cancel_at_period_end or sub.status in ('cancelled', 'completed')
        else:
            sub.status = 'active'
    elif sub.provider_id == index.provider_id:
        sub.status = 'refunded' if any(p.status == 'refunded' for p in db.scalars(select(Payment).where(Payment.provider_subscription_id == index.provider_id))) else 'expired'
        sub.paid_until = None
        sub.cancel_at_period_end = False
    checkout = db.scalar(select(Checkout).where(Checkout.provider_id == index.provider_id))
    if checkout and remote.get('status') in ('active','cancelled','completed','expired','halted'):
        checkout.status = 'closed'
    sub.updated_at = utcnow()
    wallet(db)


def fetch_pairs(subscription_id):
    invoices = provider.invoices(subscription_id)
    return [(invoice, provider.payment(invoice['payment_id'])) for invoice in invoices if invoice.get('status') == 'paid' and invoice.get('payment_id')]


@router.post('/reconcile')
def reconcile(identity: Identity = Depends(require_user)):
    with database(identity.id) as db:
        rate_limit(db, 'reconcile:' + identity.id, 4, 60)
        indexes = list(db.scalars(select(SubscriptionIndex).where(SubscriptionIndex.user_id == identity.id)))
    for index in indexes[-5:]:
        remote = provider.subscription(index.provider_id)
        pairs = fetch_pairs(index.provider_id)
        with database(identity.id) as db:
            apply_verified(db, index, remote, pairs)
    with database(identity.id) as db:
        return snapshot(db)


@router.post('/cancel')
def cancel(identity: Identity = Depends(require_user)):
    with database(identity.id) as db:
        lock_user(db)
        sub = db.get(Subscription, identity.id)
        if not sub or not sub.provider_id:
            raise HTTPException(400, 'There is no paid subscription to cancel.')
        if sub.cancel_at_period_end:
            return {'ok': True, 'paid_until': aware(sub.paid_until).isoformat() if sub.paid_until else None}
        provider_id = sub.provider_id
    remote = provider.subscription(provider_id)
    if remote.get('status') not in ('cancelled', 'completed', 'expired'):
        provider.cancel(provider_id)
    with database(identity.id) as db:
        lock_user(db)
        sub = db.get(Subscription, identity.id)
        if sub.provider_id == provider_id:
            sub.cancel_at_period_end = True
        return {'ok': True, 'paid_until': aware(sub.paid_until).isoformat() if sub.paid_until else None}


def process_event(raw, signature, event_id):
    if not config.razorpay_webhook_secret:
        raise HTTPException(503, 'Webhook is not configured.')
    expected = hmac.new(config.razorpay_webhook_secret.encode(), raw, hashlib.sha256).hexdigest()
    if not signature or len(signature) != 64 or not signature.isascii() or not hmac.compare_digest(signature, expected):
        raise HTTPException(400, 'Invalid webhook signature.')
    digest = hashlib.sha256(raw).hexdigest()
    if not event_id or len(event_id) > 200:
        raise HTTPException(400, 'A webhook event ID is required.')
    with database(system=True) as db:
        old = db.get(WebhookEvent, event_id)
        if old:
            if old.body_hash != digest:
                raise HTTPException(400, 'Webhook event mismatch.')
            return {'ok': True, 'duplicate': True}
    try:
        event = json.loads(raw)
        event_type, payload = event['event'], event.get('payload', {})
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, 'Invalid webhook payload.')
    remote = payload.get('subscription', {}).get('entity', {})
    payment = payload.get('payment', {}).get('entity', {})
    invoice = payload.get('invoice', {}).get('entity', {})
    refund = payload.get('refund', {}).get('entity', {})
    dispute = payload.get('dispute', {}).get('entity', {})
    sub_id = remote.get('id') or invoice.get('subscription_id')
    payment_id = payment.get('id') or refund.get('payment_id') or dispute.get('payment_id')
    if not sub_id and payment_id:
        p = provider.payment(payment_id)
        if p.get('invoice_id'):
            inv = provider.request('GET', 'invoices/' + p['invoice_id'])
            sub_id = inv.get('subscription_id')
    if not sub_id:
        return {'ok': True, 'ignored': True}
    remote = provider.subscription(sub_id)
    with database(system=True) as db:
        index = db.get(SubscriptionIndex, sub_id)
    if not index:
        notes = remote.get('notes', {})
        try:
            owner = str(UUID(notes['hakisense_user']))
        except (ValueError, KeyError, TypeError):
            return {'ok': True, 'ignored': True}
        with database(owner) as db:
            lock_user(db)
            checkout = db.get(Checkout, notes.get('hakisense_checkout'))
            if not checkout:
                return {'ok': True, 'ignored': True}
            bind_checkout(db, checkout, remote)
            db.flush()
            index = db.get(SubscriptionIndex, sub_id)
    pairs = fetch_pairs(sub_id)
    # Verify old refunded/disputed invoices too, even if they fall outside the latest invoice page.
    if payment_id and all(p['id'] != payment_id for _, p in pairs):
        p = provider.payment(payment_id)
        if p.get('invoice_id'):
            pairs.append((provider.request('GET', 'invoices/' + p['invoice_id']), p))
    dispute_status = None
    if event_type.startswith('payment.dispute.') and dispute.get('id'):
        verified_dispute = provider.request('GET', 'disputes/' + dispute['id'])
        if verified_dispute.get('payment_id') == payment_id:
            dispute_status = verified_dispute.get('status', 'open')
    with database(index.user_id) as db:
        lock_user(db)
        if db.get(WebhookEvent, event_id):
            return {'ok': True, 'duplicate': True}
        apply_verified(db, index, remote, pairs, payment_id if dispute_status else None, dispute_status)
        db.add(WebhookEvent(id=event_id, event_type=event_type, body_hash=digest))
    return {'ok': True}


@webhooks.post('/api/webhooks/razorpay')
async def razorpay_webhook(request: Request):
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise HTTPException(413, 'Webhook too large.')
    return await run_in_threadpool(process_event, body, request.headers.get('x-razorpay-signature'), request.headers.get('x-razorpay-event-id'))


@router.get('/pending')
def pending_checkouts(db=Depends(get_db)):
    return [{'id': c.id, 'price_code': c.price_code, 'status': c.status, 'created_at': c.created_at.isoformat()} for c in db.scalars(select(Checkout).where(Checkout.status.in_(['creating','uncertain','ready'])).order_by(Checkout.created_at.desc()).limit(5))]


@router.post('/checkout/{checkout_id}/cancel')
def cancel_checkout(checkout_id: str, identity: Identity = Depends(require_user)):
    with database(identity.id) as db:
        lock_user(db)
        row = db.get(Checkout, checkout_id)
        if not row:
            raise HTTPException(404, 'Checkout not found.')
        if row.status == 'closed':
            return {'ok': True}
        provider_id = row.provider_id
    if not provider_id:
        recent = provider.request('GET', 'subscriptions', params={'count':100}).get('items', [])
        remote = next((s for s in recent if s.get('notes', {}).get('hakisense_checkout') == checkout_id), None)
        if not remote:
            raise HTTPException(409, 'Checkout confirmation is still uncertain. Contact billing support before starting another checkout.')
        provider_id = remote['id']
    remote = provider.subscription(provider_id)
    if remote.get('status') not in ('created','expired','cancelled'):
        raise HTTPException(409, 'This checkout has been authorised. Refresh billing and use Cancel renewal for the subscription.')
    if remote.get('status') == 'created':
        provider.request('POST', 'subscriptions/' + provider_id + '/cancel', json={'cancel_at_cycle_end': 0})
    with database(identity.id) as db:
        lock_user(db)
        db.get(Checkout, checkout_id).status = 'closed'
    return {'ok': True}
