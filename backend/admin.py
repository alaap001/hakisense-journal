"""Audited administration with database-enforced roles and no journal-content access."""
import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import select, func, text
from .auth import require_user, Identity
from .db import (admin_database, AdminMember, AdminAudit, PlatformConfig, Profile, AITask,
    AIModel, AIRoute, AIJob, CreditWallet, WalletEntry, CreditPack, CreditPurchase, utcnow, serialize, uid)
from .entitlements import aware
from .runtime_settings import ProductSettings, settings, checkout_ready
from .config import config
from .catalog import FEATURE_NAMES, UPCOMING_FEATURE_NAMES
from .markets import month_key, IST

router = APIRouter(prefix='/api/admin', tags=['Administration'])


def get_admin_db(identity: Identity = Depends(require_user)):
    with admin_database(identity.id) as db:
        yield db


def staff_role(db, user_id):
    row = db.get(AdminMember, user_id)
    return row.role if row and row.active else None


class Change(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator('reason')
    @classmethod
    def meaningful(cls, value):
        if len(value.strip()) < 3:
            raise ValueError('Describe why this change is needed.')
        return value.strip()


class CatalogChange(Change):
    revision: int = Field(ge=1)


def mutate(db, payload, key, action, target, apply, owner_only=False):
    if not key or not 8 <= len(key) <= 100:
        raise HTTPException(400, 'A valid Idempotency-Key is required.')
    state = db.scalar(select(PlatformConfig).where(PlatformConfig.key == 'product').with_for_update().execution_options(populate_existing=True))
    # Refresh membership after the shared administrative lock, preventing stale-role writes.
    member = db.get(AdminMember, db.info['admin_actor'], populate_existing=True)
    if not member or not member.active or member.role not in (('owner',) if owner_only else ('owner','admin')):
        raise HTTPException(403, 'Owner access is required.' if owner_only else 'Your administration role is read-only.')
    body = {'action':action,'target':target,'payload':payload.model_dump(mode='json')}
    digest = hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest()
    existing = db.scalar(select(AdminAudit).where(AdminAudit.actor_id == member.user_id, AdminAudit.idempotency_key == key))
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(409, 'This request key belongs to a different change.')
        return {'ok':True,'audit_id':existing.id,'revision':state.revision,'duplicate':True}
    revision = getattr(payload,'revision',None)
    if revision is not None and revision != state.revision:
        raise HTTPException(409, {'code':'config_changed','message':'Another administrator changed the catalog. Refresh before saving your changes.'})
    before, after = apply()
    if revision is not None:
        state.revision += 1
        state.updated_at = utcnow()
    audit = AdminAudit(actor_id=member.user_id,actor_role=member.role,action=action,target=target,reason=payload.reason,
        before=before,after=after,idempotency_key=key,request_hash=digest)
    db.add(audit)
    db.flush()
    return {'ok':True,'audit_id':audit.id,'revision':state.revision}


def auth_user(db, user_id):
    try:
        user_id = str(UUID(user_id))
    except ValueError:
        raise HTTPException(400,'Choose a valid user.')
    if db.bind.dialect.name == 'postgresql':
        row = db.execute(text('SELECT id,email,created_at,last_sign_in_at,email_confirmed_at FROM journal.user_directory WHERE id=:id'), {'id':user_id}).mappings().first()
        if not row:
            raise HTTPException(404,'User not found.')
        return {k:(str(v) if k=='id' else v.isoformat() if isinstance(v,datetime) else v) for k,v in row.items()}
    row = db.get(Profile,user_id)
    if not row:
        raise HTTPException(404,'User not found.')
    return {'id':user_id,'email':row.display_name+'@fixture.invalid','created_at':row.created_at.isoformat(),'email_confirmed_at':row.created_at.isoformat(),'last_sign_in_at':None}


def target_profile(db, user_id):
    user = auth_user(db,user_id)
    row = db.scalar(select(Profile).where(Profile.user_id==user_id).with_for_update())
    if not row:
        row = Profile(user_id=user_id, display_name=user['email'].split('@')[0] if user['email'] else 'Trader')
        db.add(row)
        db.flush()
    return row


def describe_user(db, user_id):
    result = auth_user(db,user_id)
    profile = db.get(Profile,user_id)
    db.info['user_id'] = user_id
    balance = db.get(CreditWallet,user_id)
    balance_view=serialize(balance) if balance else None
    result.update({'display_name':profile.display_name if profile else '', 'suspended':profile.suspended if profile else False,
        'role':staff_role(db,user_id), 'monthly_free_credits':settings(db).monthly_free_credits, 'wallet':balance_view})
    return result


@router.get('/me')
def me(db=Depends(get_admin_db)):
    return {'role':db.info['admin_role'],'user_id':db.info['admin_actor']}


@router.get('/overview')
def overview(db=Depends(get_admin_db)):
    jobs = dict(db.execute(select(AIJob.status,func.count(AIJob.id)).group_by(AIJob.status)).all())
    users = db.scalar(text('SELECT count(id) FROM journal.user_directory')) if db.bind.dialect.name=='postgresql' else db.scalar(select(func.count()).select_from(Profile))
    return {'users':users,'suspended':db.scalar(select(func.count()).select_from(Profile).where(Profile.suspended.is_(True))),
        'paid_recharges':db.scalar(select(func.count()).select_from(CreditPurchase).where(CreditPurchase.payment_id.is_not(None))),
        'credits_used_this_month':max(0,db.scalar(select(func.coalesce(func.sum(-WalletEntry.amount),0)).where(
            WalletEntry.event_key.like('reserve:%')|WalletEntry.event_key.like('refund:%')|WalletEntry.event_key.like('playbook:%'),
            WalletEntry.created_at>=datetime.now(IST).replace(day=1,hour=0,minute=0,second=0,microsecond=0)))),
        'jobs':jobs,'environment':config.environment,'period':month_key(),
        'readiness':{'ai_key_configured':bool(config.openrouter_key),'payment_keys_configured':bool(config.razorpay_key and config.razorpay_secret and config.razorpay_webhook_secret),
        'checkout_available':checkout_ready(settings(db)),'password_min_length':8}}


@router.get('/users')
def users(q:str=Query(default='',max_length=100), page:int=Query(default=1,ge=1,le=10000), db=Depends(get_admin_db)):
    limit=30
    if db.bind.dialect.name=='postgresql':
        pattern='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
        params={'q':pattern,'offset':(page-1)*limit,'limit':limit,'month':month_key()}
        where="WHERE (u.email ILIKE :q OR p.display_name ILIKE :q OR CAST(u.id AS text) ILIKE :q)"
        total=db.scalar(text('SELECT count(u.id) FROM journal.user_directory u LEFT JOIN journal.profiles p ON p.user_id=u.id '+where),params)
        rows=db.execute(text("""SELECT u.id,u.email,u.created_at,u.email_confirmed_at,u.last_sign_in_at,
            COALESCE(p.display_name,'') AS display_name,COALESCE(p.suspended,false) AS suspended,
            CASE WHEN m.active THEN m.role ELSE NULL END AS role,
            CASE WHEN w.user_id IS NOT NULL THEN json_build_object('balance',w.balance) ELSE NULL END AS wallet
            FROM journal.user_directory u
            LEFT JOIN journal.profiles p ON p.user_id=u.id
            LEFT JOIN journal.admin_members m ON m.user_id=u.id
            LEFT JOIN journal.credit_wallets w ON w.user_id=u.id
            """+where+' ORDER BY u.created_at DESC,u.id LIMIT :limit OFFSET :offset'),params).mappings().all()
        return {'items':[{**dict(r),'monthly_free_credits':settings(db).monthly_free_credits} for r in rows], 'total':total,'page':page,'page_size':limit}
    else:
        query=select(Profile).where(Profile.display_name.contains(q,autoescape=True))
        total=len(db.scalars(query).all())
        ids=[p.user_id for p in db.scalars(query.offset((page-1)*limit).limit(limit))]
    return {'items':[describe_user(db,str(user_id)) for user_id in ids], 'total':total, 'page':page,'page_size':limit}


@router.get('/users/{user_id}')
def user_detail(user_id:str, db=Depends(get_admin_db)):
    result=describe_user(db,user_id)
    result['credits']=[serialize(r) for r in db.scalars(select(WalletEntry).where(WalletEntry.user_id==user_id).order_by(WalletEntry.sequence.desc()).limit(50))]
    result['purchases']=[serialize(r) for r in db.scalars(select(CreditPurchase).where(CreditPurchase.user_id==user_id).order_by(CreditPurchase.created_at.desc()).limit(50))]
    totals=db.execute(select(func.coalesce(func.sum(WalletEntry.amount),0),func.count(WalletEntry.id)).where(WalletEntry.user_id==user_id)).one()
    result['wallet_check']={'ledger_total':totals[0],'entries':totals[1],'matches':not result['wallet'] or (totals[0]==result['wallet']['balance'] and totals[1]==result['wallet']['revision'])}
    return result


class UserChange(Change):
    display_name:str=Field(min_length=1,max_length=100)
    suspended:bool


@router.put('/users/{user_id}')
def update_user(user_id:str,payload:UserChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    def apply():
        if payload.suspended and user_id==db.info['admin_actor']:
            raise HTTPException(400,'You cannot suspend your own administrator account.')
        if payload.suspended and staff_role(db,user_id):
            if db.info['admin_role']!='owner':
                raise HTTPException(403,'Only an owner can suspend a staff account.')
            raise HTTPException(409,'Remove this user’s staff access before suspending their account.')
        row=target_profile(db,user_id)
        before=serialize(row)
        row.display_name,row.suspended=payload.display_name.strip(),payload.suspended
        return before,serialize(row)
    return mutate(db,payload,key,'user.update',user_id,apply)


class CreditChange(Change):
    amount:int=Field(ge=-1000000,le=1000000)


@router.post('/users/{user_id}/credits')
def adjust_credits(user_id:str,payload:CreditChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    def apply():
        if payload.amount==0:
            raise HTTPException(400,'Enter a nonzero credit adjustment.')
        target_profile(db,user_id)
        db.info['user_id']=user_id
        from .wallet import get_wallet, append
        row=get_wallet(db)
        before=serialize(row)
        if payload.amount<0 and row.balance+payload.amount<0:
            raise HTTPException(400,'The adjustment cannot create credit debt.')
        # Positive adjustments repay any reversal debt. Negative adjustments consume free first.
        free=-min(row.free_balance,-payload.amount) if payload.amount<0 else 0
        append(db,row,'admin:'+db.info['admin_actor']+':'+key,free=free,purchased=payload.amount-free,
            reason='Admin credit adjustment: '+payload.reason)
        return before,serialize(row)
    return mutate(db,payload,key,'credits.adjust',user_id,apply)


@router.get('/catalog')
def catalog(db=Depends(get_admin_db)):
    state=db.get(PlatformConfig,'product')
    return {'revision':state.revision,
        'packs':[serialize(x) for x in db.scalars(select(CreditPack).order_by(CreditPack.sort_order,CreditPack.code))],
        'tasks':[serialize(x) for x in db.scalars(select(AITask).order_by(AITask.code))],
        'models':[serialize(x) for x in db.scalars(select(AIModel).order_by(AIModel.name))],
        'routes':[serialize(x) for x in db.scalars(select(AIRoute).order_by(AIRoute.task_code,AIRoute.tier))],
        'settings':settings(db).model_dump(),'features':FEATURE_NAMES,'upcoming_features':UPCOMING_FEATURE_NAMES}


def safe_code(value):
    if not re.fullmatch('[a-z][a-z0-9_]{1,79}',value):
        raise HTTPException(400,'Use a lowercase code with letters, digits and underscores.')


class TaskChange(CatalogChange):
    name:str=Field(min_length=1,max_length=100)
    credits:int=Field(ge=0,le=100000)
    enabled:bool=True


@router.put('/tasks/{code}')
def save_task(code:str,payload:TaskChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    def apply():
        row=db.get(AITask,code)
        if not row:raise HTTPException(404,'Task not found.')
        before=serialize(row)
        row.name,row.credits,row.enabled=payload.name,payload.credits,payload.enabled
        return before,serialize(row)
    return mutate(db,payload,key,'task.save',code,apply)


class ModelChange(CatalogChange):
    id:str=Field(pattern=r'^[a-zA-Z0-9][a-zA-Z0-9._-]*/[a-zA-Z0-9][a-zA-Z0-9._:/-]*$',max_length=200)
    name:str=Field(min_length=1,max_length=100)
    enabled:bool=True


@router.post('/models')
def save_model(payload:ModelChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    def apply():
        row=db.get(AIModel,payload.id)
        before=serialize(row) if row else {}
        if not payload.enabled and db.scalar(select(AIRoute.task_code).where(AIRoute.enabled.is_(True),(AIRoute.model_id==payload.id)|(AIRoute.planner_model_id==payload.id)).limit(1)):
            raise HTTPException(409,'Reassign or disable routes using this model first.')
        if not row:
            row=AIModel(id=payload.id)
            db.add(row)
        row.name,row.enabled=payload.name,payload.enabled
        return before,serialize(row)
    return mutate(db,payload,key,'model.save',payload.id,apply)


class RouteChange(CatalogChange):
    model_id:str=Field(max_length=200)
    planner_model_id:str|None=Field(default=None,max_length=200)
    max_output_tokens:int=Field(default=2400,ge=128,le=16000)
    timeout_seconds:int=Field(default=90,ge=10,le=90)
    temperature:float=Field(default=0.2,ge=0,le=2,allow_inf_nan=False)
    reasoning_effort:Literal['none','minimal','low','medium','high']='low'
    instructions:str=Field(default='',max_length=4000)
    enabled:bool=True


@router.put('/routes/{task}/{tier}')
def save_route(task:str,tier:Literal['standard','advanced'],payload:RouteChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    def apply():
        if not db.get(AITask,task):raise HTTPException(404,'Task not found.')
        for model_id in (payload.model_id,payload.planner_model_id or payload.model_id):
            row=db.get(AIModel,model_id)
            if not row or (payload.enabled and not row.enabled):raise HTTPException(400,'Choose an enabled model from the model registry.')
        row=db.get(AIRoute,(task,tier))
        before=serialize(row) if row else {}
        if not row:
            row=AIRoute(task_code=task,tier=tier)
            db.add(row)
        for k,v in payload.model_dump(exclude={'reason','revision'}).items():setattr(row,k,v)
        return before,serialize(row)
    return mutate(db,payload,key,'routing.save',task+':'+tier,apply)


class SettingsChange(CatalogChange):
    value:ProductSettings


@router.put('/settings')
def save_settings(payload:SettingsChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    def apply():
        if payload.value.checkout_enabled and not checkout_ready(payload.value):
            raise HTTPException(400,'Configure payment secrets, merchant identity and support/policy links before enabling checkout.')
        row=db.get(PlatformConfig,'product')
        before=row.value.copy()
        row.value=payload.value.model_dump()
        return before,row.value
    return mutate(db,payload,key,'settings.save','product',apply)


@router.get('/staff')
def staff(db=Depends(get_admin_db)):
    return [{**auth_user(db,row.user_id),'role':row.role,'active':row.active} for row in db.scalars(select(AdminMember).order_by(AdminMember.created_at))]


@router.get('/model-catalog')
def provider_models(q:str=Query(min_length=2,max_length=100),db=Depends(get_admin_db)):
    import httpx
    try:
        response=httpx.get('https://openrouter.ai/api/v1/models',timeout=12)
        response.raise_for_status()
        rows=response.json()['data']
    except (httpx.HTTPError,ValueError,KeyError):
        raise HTTPException(502,'The provider catalog is temporarily unavailable.')
    return {'items':[{'id':m['id'],'name':m.get('name',m['id'])[:100]} for m in rows
        if q.casefold() in (m['id']+' '+m.get('name','')).casefold()][:50]}


class StaffChange(Change):
    role:Literal['owner','admin','support']
    active:bool=True


@router.put('/staff/{user_id}')
def save_staff(user_id:str,payload:StaffChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    def apply():
        user=auth_user(db,user_id)
        profile=db.get(Profile,user_id)
        if payload.active and (not user['email_confirmed_at'] or profile and profile.suspended):
            raise HTTPException(400,'Staff must have a verified, unsuspended account.')
        row=db.get(AdminMember,user_id)
        before=serialize(row) if row else {}
        if row and row.active and row.role=='owner' and (not payload.active or payload.role!='owner'):
            count=db.scalar(select(func.count()).select_from(AdminMember).where(AdminMember.active.is_(True),AdminMember.role=='owner'))
            if count<=1:raise HTTPException(409,'Keep at least one active owner.')
        if not row:
            row=AdminMember(user_id=user_id)
            db.add(row)
        row.role,row.active=payload.role,payload.active
        return before,{**serialize(row),'user_id':user_id}
    return mutate(db,payload,key,'staff.save',user_id,apply,owner_only=True)


@router.get('/jobs')
def jobs(status:str=Query(default='',max_length=20),page:int=Query(default=1,ge=1,le=10000),db=Depends(get_admin_db)):
    query=select(AIJob.id,AIJob.user_id,AIJob.status,AIJob.task_code,AIJob.credits,AIJob.model,AIJob.created_at,AIJob.finished_at,AIJob.error)
    if status:query=query.where(AIJob.status==status)
    rows=db.execute(query.order_by(AIJob.created_at.desc()).offset((page-1)*30).limit(31)).mappings().all()
    return {'items':[dict(r) for r in rows[:30]],'has_more':len(rows)>30,'page':page}


@router.get('/audit')
def audit(q:str=Query(default='',max_length=100),page:int=Query(default=1,ge=1,le=10000),db=Depends(get_admin_db)):
    query=select(AdminAudit)
    if q:query=query.where(AdminAudit.target.contains(q,autoescape=True)|AdminAudit.action.contains(q,autoescape=True)|AdminAudit.reason.contains(q,autoescape=True))
    rows=list(db.scalars(query.order_by(AdminAudit.created_at.desc()).offset((page-1)*30).limit(31)))
    return {'items':[serialize(r) for r in rows[:30]],'has_more':len(rows)>30,'page':page}


class PackChange(CatalogChange):
    name: str = Field(min_length=1,max_length=100)
    credits: int = Field(ge=1,le=1000000)
    amount_paise: int = Field(ge=100,le=100000000)
    first_purchase_only: bool = False
    active: bool = True
    sort_order: int = Field(default=0,ge=0,le=1000)


@router.put('/packs/{code}')
def save_pack(code:str,payload:PackChange,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    safe_code(code)
    def apply():
        row=db.scalar(select(CreditPack).where(CreditPack.code==code).with_for_update())
        before=serialize(row) if row else {}
        if not row:
            row=CreditPack(code=code,currency='INR')
            db.add(row)
        for k,v in payload.model_dump(exclude={'reason','revision'}).items():setattr(row,k,v)
        return before,serialize(row)
    return mutate(db,payload,key,'pack.save',code,apply)


@router.get('/purchases')
def purchases(page:int=Query(default=1,ge=1,le=10000),status:str=Query(default='',max_length=30),db=Depends(get_admin_db)):
    query=select(CreditPurchase)
    if status:query=query.where(CreditPurchase.status==status)
    rows=list(db.scalars(query.order_by(CreditPurchase.created_at.desc()).offset((page-1)*30).limit(31)))
    return {'items':[{**serialize(p),'user_id':p.user_id} for p in rows[:30]],'has_more':len(rows)>30}


@router.post('/purchases/{purchase_id}/reconcile')
def reconcile_recharge(purchase_id:str,payload:Change,key:str|None=Header(default=None,alias='Idempotency-Key'),db=Depends(get_admin_db)):
    if db.info['admin_role'] not in ('owner','admin'):raise HTTPException(403,'Support access is read-only.')
    purchase=db.get(CreditPurchase,purchase_id)
    if not purchase:raise HTTPException(404,'Recharge not found.')
    # Provider I/O and tenant settlement use separate transactions, never the admin catalog lock.
    from .recharges import reconcile_purchase
    result=reconcile_purchase(purchase.id,purchase.user_id)
    def apply():return {},result
    return mutate(db,payload,key,'purchase.reconcile',purchase_id,apply)
