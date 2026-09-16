"""Credit wallet read API and signed one-time-payment webhook entry point."""
import hashlib
import hmac
import json
from fastapi import APIRouter,Depends,HTTPException,Request
from starlette.concurrency import run_in_threadpool
from .config import config
from .db import database,WebhookEvent
from .auth import get_db
from .entitlements import snapshot,public_catalog
from .recharges import process_topup_event

router=APIRouter(prefix='/api/billing',tags=['Credit wallet'])
webhooks=APIRouter(tags=['Payment webhooks'])

@router.get('/catalog')
def catalog_route():
    with database(system=True) as db:return public_catalog(db)

@router.get('/me')
def me(db=Depends(get_db)):
    return snapshot(db)


def process_event(raw,signature,event_id):
    if not config.razorpay_webhook_secret:raise HTTPException(503,'Webhook is not configured.')
    expected=hmac.new(config.razorpay_webhook_secret.encode(),raw,hashlib.sha256).hexdigest()
    if not signature or len(signature)!=64 or not signature.isascii() or not hmac.compare_digest(signature,expected):
        raise HTTPException(400,'Invalid webhook signature.')
    if not event_id or len(event_id)>200:raise HTTPException(400,'A webhook event ID is required.')
    digest=hashlib.sha256(raw).hexdigest()
    with database(system=True) as db:
        previous=db.get(WebhookEvent,event_id)
        if previous:
            if previous.body_hash!=digest:raise HTTPException(400,'Webhook event mismatch.')
            return {'ok':True,'duplicate':True}
    try:
        event=json.loads(raw)
        event_type,payload=event['event'],event.get('payload',{})
        if not isinstance(event_type,str) or not isinstance(payload,dict):raise ValueError()
    except (ValueError,KeyError,TypeError):raise HTTPException(400,'Invalid webhook payload.')
    if not (event_type.startswith('payment_link.') or event_type.startswith('payment.') or event_type.startswith('refund.') or event_type=='order.paid'):
        return {'ok':True,'ignored':True}
    return process_topup_event(payload,event_type,event_id,digest) or {'ok':True,'ignored':True}


@webhooks.post('/api/webhooks/razorpay')
async def razorpay_webhook(request:Request):
    body=await request.body()
    if len(body)>1024*1024:raise HTTPException(413,'Webhook too large.')
    return await run_in_threadpool(process_event,body,request.headers.get('x-razorpay-signature'),request.headers.get('x-razorpay-event-id'))
