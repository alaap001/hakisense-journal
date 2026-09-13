"""One-time credit purchases. The provider verifies money; wallet entries grant usage."""
import hashlib
from urllib.parse import urlparse
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from .auth import require_user, Identity, get_db
from .db import (database, CreditPack, CreditPurchase, PurchaseIndex, WalletEntry,
                 WebhookEvent, serialize, utcnow)
from .wallet import get_wallet, intro_eligible, append
from .entitlements import lock_user, snapshot
from .payments import provider
from .runtime_settings import settings, checkout_ready
from .security import rate_limit

router = APIRouter(prefix='/api/billing', tags=['Credit wallet'])
PENDING = ('creating','uncertain','ready')


class RechargeInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    pack_code: str = Field(min_length=1, max_length=80)
    expected_amount_paise: int = Field(ge=1)
    expected_credits: int = Field(ge=1)


def public_purchase(row):
    return {k:serialize(row)[k] for k in ('id','pack_code','pack_name','amount_paise','credits',
        'status','payment_id','created_at','credited','refunded_paise','first_purchase_only')}


def prepare(db, payload, key):
    if not key or not 8 <= len(key) <= 100:
        raise HTTPException(400, 'A valid Idempotency-Key is required.')
    row = get_wallet(db)
    old = db.scalar(select(CreditPurchase).where(CreditPurchase.idempotency_key == key))
    if old:
        if (old.pack_code,old.amount_paise,old.credits) != (payload.pack_code,payload.expected_amount_paise,payload.expected_credits):
            raise HTTPException(409, 'This checkout key belongs to different purchase terms.')
        return old, False
    pending = db.scalar(select(CreditPurchase).where(CreditPurchase.status.in_(PENDING)).limit(1))
    if pending:
        if pending.pack_code == payload.pack_code:
            if (pending.amount_paise,pending.credits)!=(payload.expected_amount_paise,payload.expected_credits):
                raise HTTPException(409, {'code':'price_changed','message':'Your pending recharge has different terms. Review it in the wallet or cancel it before starting another.'})
            return pending, False
        raise HTTPException(409, 'Finish or cancel your pending recharge before choosing another pack.')
    pack = db.scalar(select(CreditPack).where(CreditPack.code == payload.pack_code).with_for_update(read=True))
    if not pack or not pack.active:
        raise HTTPException(400, 'This recharge pack is unavailable.')
    if (pack.amount_paise,pack.credits) != (payload.expected_amount_paise,payload.expected_credits):
        raise HTTPException(409, {'code':'price_changed','message':'This pack changed. Refresh and review its current price and credits.'})
    if pack.first_purchase_only and not intro_eligible(db,row):
        raise HTTPException(409, {'code':'offer_unavailable','message':'The first-recharge offer is no longer available for this account. Choose a standard pack.'})
    purchase = CreditPurchase(idempotency_key=key, pack_code=pack.code, pack_name=pack.name,
        amount_paise=pack.amount_paise, credits=pack.credits, first_purchase_only=pack.first_purchase_only)
    db.add(purchase)
    db.flush()
    if pack.first_purchase_only:
        row.first_purchase_id = purchase.id
    db.add(PurchaseIndex(id=purchase.id,user_id=row.user_id))
    db.flush()
    return purchase, True


def verify_link(purchase, remote):
    if (remote.get('reference_id') != purchase.id or remote.get('notes',{}).get('hakisense_purchase') != purchase.id
        or remote.get('amount') != purchase.amount_paise or remote.get('currency') != 'INR'
        or remote.get('accept_partial') is not False or not str(remote.get('id','')).startswith('plink_')
        or purchase.provider_id and purchase.provider_id != remote['id']):
        raise HTTPException(409, 'Recharge identity or price did not match. No credits were added.')


def bind(db, purchase, remote):
    verify_link(purchase, remote)
    url = remote.get('short_url','')
    if urlparse(url).scheme != 'https' or urlparse(url).hostname not in ('rzp.io','rzp.io.in','razorpay.com'):
        raise HTTPException(502, 'The payment link could not be verified.')
    purchase.provider_id, purchase.payment_url = remote['id'], url
    index = db.get(PurchaseIndex,purchase.id)
    index.provider_id = remote['id']
    if purchase.status in PENDING:
        purchase.status = 'ready'
    db.flush()


@router.post('/checkout')
def checkout(payload:RechargeInput, identity:Identity=Depends(require_user), key:str|None=Header(default=None,alias='Idempotency-Key')):
    with database(identity.id) as db:
        if not checkout_ready(settings(db)):
            raise HTTPException(503, 'Recharges will be available soon. All journal tools and your free credits remain available.')
        rate_limit(db,'recharge:'+identity.id,8,60)
        purchase,fresh = prepare(db,payload,key)
    if purchase.status not in PENDING:
        raise HTTPException(409, {'code':'checkout_closed','message':'This recharge is complete or closed. Refresh your wallet before starting another.'})
    if purchase.provider_id:
        reconcile_purchase(purchase.id, identity.id)
    else:
        try:
            # A reference is unique at Razorpay too. Never POST again after an uncertain response.
            remote = provider.credit_link(purchase) if fresh else provider.find_link(reference_id=purchase.id)
            if not remote:
                raise HTTPException(409, 'Payment-link confirmation is pending. Refresh the wallet; no duplicate link was created.')
            with database(identity.id) as db:
                lock_user(db)
                bind(db,db.get(CreditPurchase,purchase.id),remote)
        except Exception:
            with database(identity.id) as db:
                lock_user(db)
                row=db.get(CreditPurchase,purchase.id)
                if row.status=='creating':row.status='uncertain'
            raise
    with database(identity.id) as db:
        row=db.get(CreditPurchase,purchase.id)
        if row.status not in PENDING:
            raise HTTPException(409, {'code':'checkout_closed','message':'This recharge is closed. Your wallet shows the latest status.'})
        return {'id':row.id,'url':row.payment_url,'status':row.status,'amount_paise':row.amount_paise,'credits':row.credits}


def settle(db, purchase, remote, payment=None, dispute=None):
    """Call only with fresh server-fetched provider entities, under the user's lock."""
    row = get_wallet(db)
    bind(db,purchase,remote)
    if remote.get('status') in ('cancelled','expired') and not purchase.payment_id:
        purchase.status=remote['status']
        if row.first_purchase_id==purchase.id:row.first_purchase_id=None
    if payment is not None:
        listed = {p.get('payment_id') for p in remote.get('payments') or []}
        if (payment.get('id') not in listed or payment.get('amount') != purchase.amount_paise
            or payment.get('currency') != 'INR' or payment.get('order_id') != remote.get('order_id')
            or not remote.get('order_id') or remote.get('amount_paid') != purchase.amount_paise
            or payment.get('status') not in ('captured','refunded')):
            raise HTTPException(409, 'Captured payment did not match the recharge. No credits were added.')
        if purchase.payment_id and purchase.payment_id != payment['id']:
            raise HTTPException(409, 'This recharge already belongs to another payment.')
        refunded=payment.get('amount_refunded',0)
        if type(refunded) is not int or not 0<=refunded<=purchase.amount_paise:
            raise HTTPException(502, 'Invalid provider refund amount.')
        purchase.payment_id = payment['id']
        db.get(PurchaseIndex,purchase.id).payment_id = payment['id']
        row.first_purchase_id = row.first_purchase_id or purchase.id
        # Refund totals cannot go backwards if notifications arrive out of order.
        purchase.refunded_paise = max(purchase.refunded_paise,refunded)
        if dispute is not None:
            if dispute.get('payment_id') != payment['id']:
                raise HTTPException(409,'Dispute payment identity did not match.')
            purchase.dispute_id, purchase.dispute_status = dispute['id'],dispute['status']
        reversal=(purchase.credits*purchase.refunded_paise+purchase.amount_paise-1)//purchase.amount_paise
        desired=0 if purchase.dispute_status and purchase.dispute_status!='won' else purchase.credits-reversal
        delta=desired-purchase.credited
        if delta:
            purchase.settlement_version+=1
            append(db,row,f'purchase:{purchase.id}:{purchase.settlement_version}',purchased=delta,
                reason=('Credit recharge · ' if delta>0 else 'Payment reversal · ')+purchase.pack_name,
                details={'purchase_id':purchase.id,'payment_id':payment['id']})
            purchase.credited=desired
        purchase.status='disputed' if purchase.dispute_status and purchase.dispute_status!='won' else 'refunded' if purchase.refunded_paise==purchase.amount_paise else 'partially_refunded' if purchase.refunded_paise else 'paid'
    purchase.checked_at=utcnow()
    db.get(PurchaseIndex,purchase.id).checked_at=purchase.checked_at
    db.flush()


def reconcile_purchase(purchase_id, user_id, dispute_id=None):
    with database(user_id) as db:
        purchase=db.get(CreditPurchase,purchase_id)
        if not purchase:raise HTTPException(404,'Recharge not found.')
        version=purchase.settlement_version
        previous_checked=purchase.checked_at
    remote=provider.link(purchase.provider_id) if purchase.provider_id else provider.find_link(reference_id=purchase.id)
    if not remote:raise HTTPException(409,'The payment provider has not confirmed this link yet. Try Refresh later.')
    verify_link(purchase,remote)
    captured=remote.get('payments') or []
    payment_id=purchase.payment_id or next((p.get('payment_id') for p in captured if p.get('status')=='captured'),None)
    payment=provider.payment(payment_id) if payment_id else None
    dispute_id=dispute_id or purchase.dispute_id
    dispute=provider.request('GET','disputes/'+dispute_id) if dispute_id else None
    with database(user_id) as db:
        lock_user(db)
        row=db.get(CreditPurchase,purchase_id)
        # Reject concurrent stale fetches, including those preceding a dispute update.
        if row.settlement_version!=version or row.checked_at!=previous_checked:
            raise HTTPException(409,'Another confirmation updated this recharge. Refresh to see the latest status.')
        settle(db,row,remote,payment,dispute)
        return public_purchase(row)


@router.get('/history')
def history(before:int|None=None,db=Depends(get_db)):
    get_wallet(db)
    query=select(WalletEntry).order_by(WalletEntry.sequence.desc())
    if before is not None:query=query.where(WalletEntry.sequence<before)
    entries=list(db.scalars(query.limit(51)))
    return {'credits':[serialize(c) for c in entries[:50]], 'next_cursor':entries[49].sequence if len(entries)>50 else None,
        'purchases':[public_purchase(p) for p in db.scalars(select(CreditPurchase).order_by(CreditPurchase.created_at.desc()).limit(50))]}


@router.get('/pending')
def pending(db=Depends(get_db)):
    return [public_purchase(p) for p in db.scalars(select(CreditPurchase).where(CreditPurchase.status.in_(PENDING)))]


@router.post('/reconcile')
def reconcile(identity:Identity=Depends(require_user)):
    with database(identity.id) as db:
        rate_limit(db,'recharge-sync:'+identity.id,4,60)
        ids=list(db.scalars(select(CreditPurchase.id).order_by(CreditPurchase.created_at.desc()).limit(10)))
    errors=[]
    for purchase_id in ids:
        try:reconcile_purchase(purchase_id,identity.id)
        except HTTPException as exc:errors.append({'id':purchase_id,'message':str(exc.detail)})
    with database(identity.id) as db:return {**snapshot(db),'pending_checks':errors}


@router.post('/checkout/{purchase_id}/cancel')
def cancel(purchase_id:str,identity:Identity=Depends(require_user)):
    with database(identity.id) as db:
        row=db.get(CreditPurchase,purchase_id)
        if not row:raise HTTPException(404,'Recharge not found.')
        if row.status in ('cancelled','expired'):return {'ok':True}
        if row.status not in PENDING:raise HTTPException(409,'This recharge already has a payment. Contact billing support for refunds.')
    remote=provider.link(row.provider_id) if row.provider_id else provider.find_link(reference_id=row.id)
    if not remote:raise HTTPException(409,'Link creation is uncertain. Refresh later before cancelling.')
    verify_link(row,remote)
    if remote.get('status')=='created':provider.request('POST','payment_links/'+remote['id']+'/cancel')
    result=reconcile_purchase(row.id,identity.id)
    if result['status'] not in ('cancelled','expired'):
        raise HTTPException(409,'Payment completed before cancellation. Your wallet has been updated.')
    return {'ok':True}


def process_topup_event(payload,event_type,event_id,digest):
    link=payload.get('payment_link',{}).get('entity',{})
    payment=payload.get('payment',{}).get('entity',{})
    refund=payload.get('refund',{}).get('entity',{})
    dispute=payload.get('dispute',{}).get('entity',{})
    payment_id=payment.get('id') or refund.get('payment_id') or dispute.get('payment_id')
    with database(system=True) as db:
        index=db.scalar(select(PurchaseIndex).where(PurchaseIndex.provider_id==link.get('id'))) if link.get('id') else None
        if not index and payment_id:index=db.scalar(select(PurchaseIndex).where(PurchaseIndex.payment_id==payment_id))
    if not index:
        remote=provider.link(link['id']) if link.get('id') else provider.find_link(payment_id=payment_id) if payment_id else None
        if not remote:return None
        with database(system=True) as db:index=db.get(PurchaseIndex,remote.get('reference_id',''))
    if not index:return None
    reconcile_purchase(index.id,index.user_id,dispute.get('id') if event_type.startswith('payment.dispute.') else None)
    with database(system=True) as db:
        from .entitlements import upsert_ignore
        upsert_ignore(db,WebhookEvent,{'id':event_id,'event_type':event_type,'body_hash':digest},['id'])
    return {'ok':True}
