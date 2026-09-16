"""Verify the AI migration, reservations and tenant isolation in a rolled-back PostgreSQL transaction."""
import sys
import importlib.util
from pathlib import Path
from uuid import uuid4
from contextlib import contextmanager
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text, select
from sqlalchemy.exc import DBAPIError
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.config import config
from backend.db import make_engine, TenantSession, AIJob, AIEvent, AICall, Trade
from backend.entitlements import provision
from backend.jobs import enqueue, event
from backend.wallet import get_wallet, settle_reservations
from backend.schemas import AIRequest, TradeInput
from backend.ai_pricing import VERSION
from backend.ai_contracts import EvidenceRequest, TradeSelection
from backend.ai_evidence import execute, select_cohort

engine=make_engine(config.migration_url or config.database_url)
a,b=str(uuid4()),str(uuid4())
try:
 with engine.connect() as connection:
  outer=connection.begin()
  try:
   current=connection.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema='journal' AND table_name='ai_jobs' AND column_name='pricing_version'"))
   if not current:
    spec=importlib.util.spec_from_file_location('ai_migration',Path(__file__).resolve().parents[1]/'migrations/versions/e6d8c9d3dc6a_agent_workflows_usage_buckets_and_.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
   for user in (a,b):
    connection.execute(text("INSERT INTO auth.users(id,email,aud,role,created_at,updated_at) VALUES (:id,:email,'authenticated','authenticated',now(),now())"),{'id':user,'email':user+'@ai-verification.invalid'})
   connection.execute(text('SET LOCAL ROLE hakisense_api'))
   assert connection.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()==(False,False)
   @contextmanager
   def session(user):
    connection.execute(text("SELECT set_config('app.user_id',:user,true)"),{'user':user})
    with TenantSession(bind=connection,info={'user_id':user},join_transaction_mode='create_savepoint',expire_on_commit=False) as db:
     yield db
     db.commit()
   with session(a) as db:
    provision(db,'Temporary AI fixture')
    from backend.db import Account
    account=db.scalar(select(Account.id))
    trade=Trade(**TradeInput(account_id=account,symbol='FIXTURE',entry_price=100,exit_price=110,quantity=10,entry_time='2026-09-10T09:15:00',exit_time='2026-09-10T10:15:00',commission=2,fees=1,notes='Full source note').model_dump())
    db.add(trade)
    for i in range(496):
     db.add(Trade(**TradeInput(account_id=account,symbol='OLD'+str(i),entry_price=100,exit_price=110,quantity=10,
         entry_time='2025-09-10T09:15:00',exit_time='2025-09-10T10:15:00',commission=2,fees=1,notes='OLD_NOTE').model_dump()))
    for i in range(3):
     db.add(Trade(**TradeInput(account_id=account,symbol='RECENT'+str(i),entry_price=100,exit_price=110,quantity=10,
         entry_time='2026-09-11T09:15:00',exit_time='2026-09-11T10:15:00',commission=2,fees=1,notes='RECENT_NOTE').model_dump()))
    job=enqueue(db,AIRequest(message='Temporary AI verification',max_credits=7,pricing_version=VERSION),'verify-ai-'+a)
    assert get_wallet(db).balance==43
    event(db,job,'status',{'message':'Private fixture progress'})
    db.add(AICall(job_id=job.id,call_key='fixture',agent='writer',model=job.model,request_hash='0'*64,status='completed',usage={'input_tokens':5000,'output_tokens':3000},response='Private fixture output'))
    settle_reservations(db,job.id,2)
    settle_reservations(db,job.id,2)
    assert get_wallet(db).balance==48
    job.status='succeeded';job.credits=2
    job_id=job.id
   with patch('backend.ai_evidence.database',session):
    assert execute(a,{},EvidenceRequest(kind='metrics',purpose='Fixture'))['data']['metrics']['net_pnl']==48500
    cohort=select_cohort(a,{},TradeSelection(count=3))
    recent=execute(a,{},EvidenceRequest(kind='records',purpose='Latest three',include_notes=True),cohort)
    assert recent['metadata']['matched']==3
    assert recent['data']['metrics']['net_pnl']==291
    assert all(row[recent['data']['columns'].index('symbol')].startswith('RECENT') for row in recent['data']['rows'])
    assert 'OLD_NOTE' not in str(recent['data'])
   with session(b) as db:
    provision(db,'Other temporary AI fixture')
    assert db.get(AIJob,job_id) is None
    assert list(db.scalars(select(AIEvent).where(AIEvent.job_id==job_id)))==[]
    assert list(db.scalars(select(AICall).where(AICall.job_id==job_id)))==[]
   for table in ('ai_jobs','ai_events','ai_calls'):
    assert connection.scalar(text(f'SELECT count(*) FROM journal.{table} WHERE user_id=:user'),{'user':a})==0
   savepoint=connection.begin_nested()
   rejected=False
   try:
    connection.execute(text("INSERT INTO journal.ai_events(user_id,job_id,sequence,kind,data,created_at) VALUES (:user,:job,99,'status','{}',now())"),{'user':a,'job':job_id})
   except DBAPIError:rejected=True
   finally:savepoint.rollback()
   assert rejected
   print('PostgreSQL migration, latest 3 of 500 selection, projected analytics, partial credit release, idempotency and private event/call RLS passed.')
  finally:outer.rollback()
 print('All temporary users, records and schema changes rolled back. No customer data changed.')
finally:engine.dispose()
