"""Rollback-only admin API/privilege checks. No persistent staff or customer changes."""
import sys
import importlib.util
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import DBAPIError
from alembic.migration import MigrationContext
from alembic.operations import Operations
from backend.config import config
from backend.db import make_engine, AIJob, utcnow
from backend.admin import catalog, overview, jobs
from backend.ai_pricing import VERSION

engine=make_engine(config.migration_url)
owner,support,ordinary=[str(uuid4()) for _ in range(3)]
try:
 with engine.connect() as connection:
  outer=connection.begin()
  try:
   if '--test-migration' in sys.argv:
    spec=importlib.util.spec_from_file_location('admin_metadata_migration',Path(__file__).resolve().parents[1]/'migrations/versions/9dd7527249ac_admin_workflow_metadata_privileges.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with Operations.context(MigrationContext.configure(connection)):migration.upgrade()
   for user in (owner,support,ordinary):
    connection.execute(text("INSERT INTO auth.users(id,email,aud,role,created_at,updated_at,email_confirmed_at) VALUES (:id,:email,'authenticated','authenticated',now(),now(),now())"),{'id':user,'email':user+'@admin-verification.invalid'})
    connection.execute(text("INSERT INTO journal.profiles(user_id,display_name,created_at) VALUES (:id,'Admin verification fixture',now())"),{'id':user})
   connection.execute(text("INSERT INTO journal.admin_members(user_id,role) VALUES (:owner,'owner'),(:support,'support')"),{'owner':owner,'support':support})
   job_id=str(uuid4())
   connection.execute(AIJob.__table__.insert().values(id=job_id,user_id=ordinary,idempotency_key=job_id,request_hash='0'*64,
    request={'message':'PRIVATE_QUESTION'},result={'answer':'PRIVATE_ANSWER'},pause={'question':'PRIVATE_CLARIFICATION'},checkpoint={'notes':'PRIVATE_EVIDENCE'},
    status='succeeded',task_code='chat',credits=2,max_credits=7,pricing_version=VERSION,month='2026-09',model='fixture/model',
    routing_config={'model_id':'fixture/model','planner_model_id':'fixture/planner','tier':'standard','instructions':'PRIVATE_STYLE'},
    usage={'input_tokens':5000,'output_tokens':3000,'calls':4},finished_at=utcnow()))
   connection.execute(text('SET LOCAL ROLE hakisense_admin'))
   connection.execute(text("SELECT set_config('app.actor_id',:id,true)"),{'id':ordinary})
   assert connection.scalar(text('SELECT count(*) FROM journal.credit_packs'))==0
   assert connection.execute(text("UPDATE journal.ai_tasks SET name='Forbidden' WHERE code='chat'")).rowcount==0
   for actor in (support,owner):
    connection.execute(text("SELECT set_config('app.actor_id',:id,true)"),{'id':actor})
    with Session(bind=connection,join_transaction_mode='create_savepoint',info={'admin_actor':actor}) as db:
     assert catalog(db)['ai_pricing']['input_limit']==100000
     assert overview(db)['ai_credits_charged_this_month']>=2
     result=jobs(status='succeeded',task='chat',q=job_id,page=1,db=db)
     assert len(result['items'])==1
     item=result['items'][0]
     assert item['billing']=={'legacy':False,'maximum':7,'charged':2,'reserved':0,'released':5}
     assert 'PRIVATE_' not in str(item)
     assert item['routing']['planner_model_id']=='fixture/planner'
    changed=connection.execute(text("UPDATE journal.ai_tasks SET name='Temporary admin validation' WHERE code='chat'")).rowcount
    assert changed==(1 if actor==owner else 0)
   def denied(sql,values=None):
    try:
     with connection.begin_nested():connection.execute(text(sql),values or {})
    except DBAPIError:return
    raise AssertionError('Expected privilege denial: '+sql)
   for field in ('request','result','checkpoint','pause'):
    denied(f'SELECT {field} FROM journal.ai_jobs LIMIT 1')
   denied('SELECT content FROM journal.messages LIMIT 1')
   denied('SELECT data FROM journal.ai_events LIMIT 1')
   denied('SELECT response FROM journal.ai_calls LIMIT 1')
   denied('SELECT encrypted_password FROM auth.users LIMIT 1')
   denied("UPDATE journal.wallet_entries SET reason='Forbidden'")
   denied("UPDATE journal.admin_audit SET reason='Forbidden'")
   connection.execute(text('RESET ROLE'))
   connection.execute(text('UPDATE journal.admin_members SET active=false WHERE user_id=:id'),{'id':owner})
   connection.execute(text('SET LOCAL ROLE hakisense_admin'))
   assert connection.execute(text("UPDATE journal.ai_tasks SET name='Forbidden' WHERE code='chat'")).rowcount==0
   connection.execute(text('SET LOCAL ROLE hakisense_api'))
   connection.execute(text("SELECT set_config('app.user_id',:id,true)"),{'id':ordinary})
   denied("INSERT INTO journal.admin_members(user_id,role) VALUES (:id,'owner')",{'id':ordinary})
   denied("UPDATE journal.platform_config SET revision=999")
   print('Admin catalog, overview and workflow operations passed against PostgreSQL under real staff roles.')
   print('Support read-only, owner edits, revocation and private question/evidence/agent-response exclusions passed.')
  finally:outer.rollback()
finally:engine.dispose()
print('All fixtures and test privileges rolled back. No persistent administrator or customer data changed.')
