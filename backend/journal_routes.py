import csv
import io
import json
import math
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, delete
from sqlalchemy.orm import Session as DBSession
from .db import Account, Trade, Record, Message, Setting, Profile, serialize, get_setting, uid, now
from .auth import get_db, require_user, Identity
from .schemas import AccountInput, TradeInput, FilterInput, RecordInput
from .analytics import enrich, apply_filters, statistics, group_rows, coach_checks, DIMENSIONS
from .importer import read_table, preview_rows, fingerprint, ALIASES
from .entitlements import consume_trades, require_feature, provision, snapshot, public_catalog, lock_user
from .markets import catalog, IST
from . import simulator

def enforce_features(request: Request, db=Depends(get_db)):
    path = request.url.path.removeprefix('/api/')
    feature = next((value for prefix,value in [('trades','journal'),('analytics','analytics'),('import/','import_export'),
        ('export/','import_export'),('accounts','accounts'),('simulator','replay'),('records/note','notebook'),('records/daily','notebook')]
        if path.startswith(prefix)), None)
    if feature:
        require_feature(db, feature)


api=APIRouter(prefix='/api', dependencies=[Depends(require_user), Depends(enforce_features)], tags=['Journal'])

from .repository import journal_rows as all_trades


def get_record(db, record_id, kind=None):
    record=db.get(Record,record_id)
    if not record or kind and record.kind!=kind:
        raise HTTPException(404,'Record not found')
    return record


def require_account(db, account_id):
    account=db.get(Account,account_id)
    if not account:
        raise HTTPException(400,'Select an existing account')
    return account


@api.get('/workspace')
def workspace(identity: Identity = Depends(require_user), db=Depends(get_db)):
    from .db import AdminMember
    from .runtime_settings import settings
    product = settings(db)
    member = db.get(AdminMember, identity.id)
    profile = provision(db, identity.name)
    settings = {s.key: s.value for s in db.scalars(select(Setting)) if s.key in ('preferences', 'dashboard')}
    return {'accounts': [serialize(a) for a in db.scalars(select(Account))], 'settings': settings,
            'currency': 'INR', 'timezone': 'Asia/Kolkata', 'user': {'id': identity.id, 'email': identity.email, 'name': profile.display_name},
            'billing': snapshot(db), 'catalog': public_catalog(db), 'markets': catalog(),
            'admin_role': member.role if member and member.active else None,
            'product': {'brand_name': product.brand_name, 'announcement': product.announcement}}


@api.put('/profile')
def update_profile(payload: RecordInput, db=Depends(get_db)):
    profile = lock_user(db)
    name = str(payload.data.get('display_name', '')).strip()
    if not name or len(name) > 100:
        raise HTTPException(400, 'Enter a name between 1 and 100 characters.')
    profile.display_name = name
    return {'ok': True}

@api.get('/trades')
def trades(filters:FilterInput=Depends(),db:DBSession=Depends(get_db)):
    return apply_filters(all_trades(db,filters),filters)


@api.post('/trades')
def create_trade(payload:TradeInput,db:DBSession=Depends(get_db)):
    require_account(db,payload.account_id)
    consume_trades(db,1)
    t=Trade(**payload.model_dump())
    db.add(t)
    db.flush()
    return enrich(serialize(t))


@api.put('/trades/{trade_id}')
def update_trade(trade_id:str,payload:TradeInput,db:DBSession=Depends(get_db)):
    require_account(db,payload.account_id)
    t=db.get(Trade,trade_id)
    if not t:
        raise HTTPException(404,'Trade not found')
    for k,v in payload.model_dump().items():
        setattr(t,k,v)
    t.fingerprint=None
    t.is_demo=False
    db.flush()
    return enrich(serialize(t))


@api.delete('/trades/{trade_id}')
def delete_trade(trade_id:str,db:DBSession=Depends(get_db)):
    t=db.get(Trade,trade_id)
    if not t:
        raise HTTPException(404,'Trade not found')
    db.delete(t)
    return {'ok':True}


@api.get('/analytics')
def analytics(filters:FilterInput=Depends(),db:DBSession=Depends(get_db)):
    rows=apply_filters(all_trades(db,filters),filters)
    balance=sum(a.initial_balance for a in db.scalars(select(Account)) if not filters.account_id or filters.account_id==a.id)
    return {**statistics(rows,balance),'groups':{d:group_rows(rows,d) for d in DIMENSIONS},'checks':coach_checks(rows)}


@api.get('/export/trades')
def export_trades(filters:FilterInput=Depends(),db:DBSession=Depends(get_db)):
    rows=apply_filters(all_trades(db,filters),filters)
    out=io.StringIO()
    columns=list(TradeInput.model_fields)
    writer=csv.DictWriter(out,fieldnames=columns)
    writer.writeheader()
    for row in rows:
        safe={k:json.dumps(row[k]) if isinstance(row.get(k),(dict,list)) else row.get(k) for k in columns}
        # Prevent spreadsheet formula execution while keeping normal negative numerics.
        safe={k:"'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for k,v in safe.items()}
        writer.writerow(safe)
    return StreamingResponse(iter([out.getvalue()]),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=hakisense-trades.csv'})


@api.post('/accounts')
def create_account(payload:AccountInput,db:DBSession=Depends(get_db)):
    current=list(db.scalars(select(Account)))
    if current and any(a.currency!=payload.currency for a in current):
        raise HTTPException(400,'Use the same reporting currency for all accounts. Convert imported amounts before importing; FX conversion is not automatic.')
    a=Account(**payload.model_dump())
    db.add(a)
    db.flush()
    if not current:
        pref=get_setting(db,'preferences')
        if pref:
            pref.value={**pref.value,'currency':a.currency}
        else:
            db.add(Setting(key='preferences',value={'currency':a.currency}))
    return serialize(a)


@api.put('/accounts/{account_id}')
def update_account(account_id:str,payload:AccountInput,db:DBSession=Depends(get_db)):
    account=require_account(db,account_id)
    if payload.currency!=account.currency:
        raise HTTPException(400,'Changing account currency would relabel existing amounts. Create a new workspace or convert data first.')
    for k,v in payload.model_dump().items():
        setattr(account,k,v)
    return serialize(account)


@api.delete('/accounts/{account_id}')
def delete_account(account_id:str,db:DBSession=Depends(get_db)):
    account=require_account(db,account_id)
    if db.scalar(select(Trade.id).where(Trade.account_id==account_id).limit(1)):
        raise HTTPException(400,'This account still has trades. Move or delete its trades first.')
    db.delete(account)
    return {'ok':True}


KINDS={'note','playbook','goal','dividend','pin','template','saved_filter'}


def validate_record(kind,data):
    if kind not in KINDS:
        raise HTTPException(400,'Unsupported record type')
    if kind in ('note','playbook','goal') and not str(data.get('title','')).strip():
        raise HTTPException(400,'Title is required')
    if kind=='goal':
        if data.get('metric') not in ('net_pnl','reviewed','process','count','win_rate') or not isinstance(data.get('target'),(int,float)) or not math.isfinite(data['target']) or data['target']<=0:
            raise HTTPException(400,'Select a goal metric and a positive target')
    if kind=='dividend':
        if not data.get('symbol') or not data.get('date') or not isinstance(data.get('amount'),(int,float)) or not math.isfinite(data['amount']):
            raise HTTPException(400,'Dividend requires symbol, date, and amount')
    return data


@api.get('/records/{kind}')
def records(kind:str,db:DBSession=Depends(get_db)):
    if kind in ('playbook','saved_filter'):
        require_feature(db,'playbooks' if kind=='playbook' else 'saved_views')
    if kind not in KINDS:
        raise HTTPException(400,'Unsupported record type')
    return [serialize(r) for r in db.scalars(select(Record).where(Record.kind==kind).order_by(Record.created_at.desc()))]


@api.post('/records/{kind}')
def create_record(kind:str,payload:RecordInput,db:DBSession=Depends(get_db)):
    if kind in ('playbook','saved_filter'):
        require_feature(db,'playbooks' if kind=='playbook' else 'saved_views')
    data=validate_record(kind,payload.data)
    if kind=='dividend':
        require_account(db,data.get('account_id'))
    r=Record(kind=kind,data=data)
    db.add(r)
    db.flush()
    return serialize(r)


@api.put('/records/{kind}/{record_id}')
def update_record(kind:str,record_id:str,payload:RecordInput,db:DBSession=Depends(get_db)):
    if kind in ('playbook','saved_filter'):
        require_feature(db,'playbooks' if kind=='playbook' else 'saved_views')
    r=get_record(db,record_id,kind)
    data=dict(validate_record(kind,payload.data))
    data.pop('is_demo',None)
    if kind=='dividend':
        require_account(db,data.get('account_id'))
    r.data=data
    return serialize(r)


@api.delete('/records/{kind}/{record_id}')
def delete_record(kind:str,record_id:str,db:DBSession=Depends(get_db)):
    if kind in ('playbook','saved_filter'):
        require_feature(db,'playbooks' if kind=='playbook' else 'saved_views')
    db.delete(get_record(db,record_id,kind))
    return {'ok':True}


@api.put('/settings/{key}')
def save_setting(key:str,payload:RecordInput,db:DBSession=Depends(get_db)):
    if key not in ('dashboard','preferences'):
        raise HTTPException(400,'Unknown setting')
    if key == 'preferences':
        payload.data = {'currency': 'INR', 'timezone': 'Asia/Kolkata', 'language': payload.data.get('language', 'en')}
    setting=get_setting(db,key)
    if setting:
        setting.value=payload.data
    else:
        db.add(Setting(key=key,value=payload.data))
    return {'ok':True}


@api.post('/import/inspect')
async def inspect_import(file:UploadFile=File(...)):
    try:
        columns,rows,mapping=read_table(await file.read(15*1024*1024+1),file.filename or 'trades.csv')
        return {'columns':columns,'rows':rows,'mapping':mapping,'fields':list(ALIASES)}
    except Exception as e:
        raise HTTPException(400,f'Unable to read file: {e}')


class ImportInput(BaseModel):
    account_id:str
    rows:list[dict] = Field(max_length=20000)
    mapping:dict[str,str]
    defaults:dict=Field(default_factory=dict)


@api.post('/import/preview')
def preview_import(payload:ImportInput,db:DBSession=Depends(get_db)):
    require_account(db,payload.account_id)
    rows=preview_rows(db,payload.rows,payload.mapping,payload.account_id,payload.defaults)
    return {'rows':rows,'valid':sum(r['status']=='valid' for r in rows),'duplicates':sum(r['status']=='duplicate' for r in rows),'errors':sum(r['status']=='error' for r in rows)}


@api.post('/import/commit')
def commit_import(payload:ImportInput,db:DBSession=Depends(get_db)):
    lock_user(db)
    preview=preview_import(payload,db)
    consume_trades(db,preview['valid'])
    for row in preview['rows']:
        if row['status']=='valid':
            db.add(Trade(**row['data'],fingerprint=row['fingerprint']))
    db.flush()
    return {'imported':preview['valid'],'duplicates':preview['duplicates'],'errors':preview['errors']}


@api.get('/ai/threads')
def ai_threads(db:DBSession=Depends(get_db)):
    result={}
    for m in db.scalars(select(Message).order_by(Message.created_at)):
        if m.thread_id not in result:
            result[m.thread_id]={'id':m.thread_id,'title':m.content[:80],'created_at':m.created_at}
    return list(result.values())[::-1]


@api.get('/ai/threads/{thread_id}')
def ai_messages(thread_id:str,db:DBSession=Depends(get_db)):
    return [serialize(m) for m in db.scalars(select(Message).where(Message.thread_id==thread_id).order_by(Message.created_at))]


@api.get('/backup')
def backup(db:DBSession=Depends(get_db)):
    data={'version':2,'exported_at':now(),'accounts':[serialize(a) for a in db.scalars(select(Account))],
          'trades':[serialize(t) for t in db.scalars(select(Trade))],'records':[serialize(r) for r in db.scalars(select(Record))],
          'messages':[serialize(m) for m in db.scalars(select(Message))],'settings':[serialize(s) for s in db.scalars(select(Setting))]}
    return Response(json.dumps(data),media_type='application/json',headers={'Content-Disposition':'attachment; filename=hakisense-backup.json'})


@api.get('/simulator')
def simulations(db:DBSession=Depends(get_db)):
    require_feature(db,'replay')
    return [{'id':r.id,'symbol':r.data['symbol'],'source':r.data['source'],'created_at':r.created_at,'pnl':r.data['balance']-r.data['initial_balance'],'count':len(r.data['trades'])} for r in db.scalars(select(Record).where(Record.kind=='simulation').order_by(Record.created_at.desc()))]


@api.post('/simulator')
async def create_simulation(request:Request,db:DBSession=Depends(get_db)):
    require_feature(db,'replay')
    payload=await request.json()
    candles=payload.get('candles') or simulator.sample_candles()
    if len(candles)<5 or len(candles)>50000:
        raise HTTPException(400,'Provide 5 to 50,000 candles')
    previous=''
    try:
        for c in candles:
            dt=datetime.fromisoformat(c['time'].replace('Z','+00:00'))
            c['time']=dt.replace(tzinfo=dt.tzinfo or IST).astimezone(timezone.utc).isoformat()
            for k in ('open','high','low','close'):
                c[k]=float(c[k])
                if not math.isfinite(c[k]) or c[k]<=0:
                    raise ValueError('Prices must be finite and positive')
            if c['time']<=previous or c['high']<max(c['open'],c['close'],c['low']) or c['low']>min(c['open'],c['close']):
                raise ValueError('Candles need increasing timestamps and valid OHLC prices')
            previous=c['time']
    except (ValueError,TypeError,KeyError) as e:
        raise HTTPException(400,str(e))
    data=simulator.session_state(candles,str(payload.get('symbol','NIFTY PRACTICE')),str(payload.get('source','Synthetic practice candles')))
    data['asset_type']=payload.get('asset_type','Indices' if not payload.get('candles') else 'Stocks')
    for key in ('exchange','segment','lot_size','expiry','strike','option_type'):
        data[key]=payload.get(key)
    data['exchange']=data['exchange'] or ('Crypto' if data['asset_type']=='Crypto' else 'NSE')
    data['segment']=data['segment'] or ('Crypto spot' if data['asset_type']=='Crypto' else 'Index reference' if data['asset_type']=='Indices' else 'Equity')
    if data['asset_type'] not in ['Stocks','Options','Futures','Crypto','Indices']:
        raise HTTPException(400,'Unknown asset class')
    try:
        contract=TradeInput(account_id='practice',symbol=data['symbol'],asset_type=data['asset_type'],exchange=data['exchange'],segment=data['segment'],
            expiry=data.get('expiry'),lot_size=data.get('lot_size'),strike=data.get('strike'),option_type=data.get('option_type'),
            status='Open',entry_price=candles[0]['close'],quantity=data.get('lot_size') or 1,entry_time=candles[0]['time'])
    except ValidationError as exc:
        raise HTTPException(400, '; '.join(error['msg'] for error in exc.errors()))
    data.update({key:getattr(contract,key) for key in ('exchange','segment','expiry','lot_size','strike','option_type')})
    r=Record(kind='simulation',data=data)
    db.add(r)
    db.flush()
    return {'id':r.id,**simulator.visible(data)}


@api.get('/simulator/{session_id}')
def get_simulation(session_id:str,db:DBSession=Depends(get_db)):
    require_feature(db,'replay')
    lock_user(db)
    r=get_record(db,session_id,'simulation')
    return {'id':r.id,**simulator.visible(r.data)}


class SimAction(BaseModel):
    action:str
    side:str='Long'
    quantity:float=Field(default=10,gt=0,allow_inf_nan=False)
    multiplier:float=Field(default=1,gt=0,allow_inf_nan=False)
    fees:float=Field(default=0,ge=0,allow_inf_nan=False)
    stop_loss:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    target_price:float|None=Field(default=None,gt=0,allow_inf_nan=False)
    count:int=Field(default=1,ge=1,le=100)


@api.post('/simulator/{session_id}/action')
def simulation_action(session_id:str,payload:SimAction,db:DBSession=Depends(get_db)):
    require_feature(db,'replay')
    lock_user(db)
    r=get_record(db,session_id,'simulation')
    data=json.loads(json.dumps(r.data))
    candle=data['candles'][data['cursor']]
    if payload.action=='step':
        data=simulator.step(data,payload.count)
    elif payload.action=='open':
        if data.get('asset_type') in ('Options','Futures') and data.get('exchange') in ('NSE','BSE') and (payload.multiplier != 1 or payload.quantity % data['lot_size'] != 0):
            raise HTTPException(400, 'Use a whole number of contract lots in units, with multiplier 1.')
        if data['position']:
            raise HTTPException(400,'Close the current position first')
        if data['cursor']==len(data['candles'])-1:
            raise HTTPException(400,'Replay is finished. Start a new session.')
        if payload.side not in ('Long','Short'):
            raise HTTPException(400,'Choose Long or Short')
        if payload.stop_loss is not None and (payload.stop_loss>=candle['close'] if payload.side=='Long' else payload.stop_loss<=candle['close']):
            raise HTTPException(400,'Place the stop on the loss side of the entry')
        if payload.target_price is not None and (payload.target_price<=candle['close'] if payload.side=='Long' else payload.target_price>=candle['close']):
            raise HTTPException(400,'Place the target on the profit side of the entry')
        data['position']={**payload.model_dump(exclude={'action','count'}),'entry_price':candle['close'],'entry_time':candle['time']}
    elif payload.action=='close':
        if not data['position']:
            raise HTTPException(400,'There is no open position')
        simulator.close_position(data,candle['close'],'Manual close')
    elif payload.action=='bracket':
        if not data['position']:
            raise HTTPException(400,'There is no open position')
        p=data['position']
        if payload.stop_loss is not None and (payload.stop_loss>=candle['close'] if p['side']=='Long' else payload.stop_loss<=candle['close']):
            raise HTTPException(400,'Stop must be on the loss side of the current price')
        if payload.target_price is not None and (payload.target_price<=candle['close'] if p['side']=='Long' else payload.target_price>=candle['close']):
            raise HTTPException(400,'Target must be on the profit side of the current price')
        p.update(stop_loss=payload.stop_loss,target_price=payload.target_price)
    else:
        raise HTTPException(400,'Unknown simulation action')
    r.data=data
    return {'id':r.id,**simulator.visible(data)}


@api.post('/simulator/{session_id}/export')
def export_simulation(session_id:str,db:DBSession=Depends(get_db)):
    require_feature(db,'replay')
    lock_user(db)
    r=get_record(db,session_id,'simulation')
    data=json.loads(json.dumps(r.data))
    start=data.get('exported_count',0)
    rows=data['trades'][start:]
    if not rows:
        raise HTTPException(400,'No new closed practice trades to export')
    consume_trades(db,len(rows))
    a=db.scalar(select(Account).where(Account.broker=='HakiSense Replay'))
    if not a:
        first=db.scalar(select(Account))
        a=Account(name='Replay practice',broker='HakiSense Replay',currency=first.currency if first else 'INR',initial_balance=100000,color='#c2a2d4')
        db.add(a)
        db.flush()
    for t in rows:
        payload=TradeInput(account_id=a.id,symbol=data['symbol'],asset_type=data.get('asset_type','Stocks'),side=t['side'],status='Closed',
            entry_price=t['entry_price'],exit_price=t['exit_price'],quantity=t['quantity'],multiplier=t['multiplier'],fees=t['fees'],
            entry_time=t['entry_time'],exit_time=t['exit_time'],stop_loss=t.get('stop_loss'),target_price=t.get('target_price'),
            setup='Replay practice',notes=f"Practice session: {data['source']}. Exit: {t['reason']}. Initial balance is simulated.",
            exchange=data.get('exchange','NSE'),segment=data.get('segment','Equity'),lot_size=data.get('lot_size'),expiry=data.get('expiry'),strike=data.get('strike'),option_type=data.get('option_type'),
            tags=['Simulation'],attributes={'simulated':True,'session_id':session_id})
        db.add(Trade(**payload.model_dump()))
    data['exported_count']=len(data['trades'])
    r.data=data
    return {'imported':len(rows),'account_id':a.id}
