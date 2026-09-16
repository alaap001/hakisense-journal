"""Opt-in paid synthetic 50-trade workflow; isolated SQLite, no customer journal access."""
import os,sys,asyncio,json
from dataclasses import replace
from pathlib import Path
from dotenv import dotenv_values
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
key=os.getenv('OPENROUTER_API_KEY') or dotenv_values(root/'backend/.env').get('OPENROUTER_API_KEY') or dotenv_values(root/'.env').get('OPENROUTER_API_KEY')
if '--run' not in sys.argv:raise SystemExit('Pass --run to authorize one live workflow of up to 100k input and 16k output tokens using synthetic records only.')
if not key:raise SystemExit('Provider key is not configured')
from tests.test_ai_workflows import Workflows
from backend import ai_runtime
from backend import db as store
from backend.jobs import enqueue
from backend.schemas import AIRequest
from backend.ai_pricing import VERSION
from backend.worker import run_one
fixture=Workflows();fixture.setUp();fixture.seed(50,notes='I followed my planned entry, but moved my stop once after entry. This is a synthetic verification note, not a real trade.')
ai_runtime.config=replace(ai_runtime.config,openrouter_key=key)
try:
 with store.database(fixture.a) as db:
  job=enqueue(db,AIRequest(message='Read every note in my 50 trades. Summarize my recorded results, identify the recurring process issue, and give three concise review actions. Use all recorded trades; no clarification is needed about the period.',mode='coach',max_credits=7,pricing_version=VERSION),'live-synthetic-workflow')
 asyncio.run(run_one())
 with store.database(fixture.a) as db:
  job=db.get(store.AIJob,job.id)
  from sqlalchemy import select
  calls=[{'agent':c.agent,'status':c.status,'usage':c.usage,'response':c.response} for c in db.scalars(select(store.AICall).where(store.AICall.job_id==job.id).order_by(store.AICall.created_at))]
  report={'status':job.status,'credits':job.credits,'usage':job.usage,'error':job.error,'pause':job.pause,'result':job.result,'agent_calls':calls,'checkpoint':job.checkpoint}
  Path('/tmp/hakisense-live-workflow.json').write_text(json.dumps(report,indent=2))
  print(json.dumps({k:v for k,v in report.items() if k not in ('result','agent_calls')}))
  assert job.status=='succeeded','Live workflow did not finish; inspect its synthetic report.'
  assert job.result['coverage']['records_inspected']==50
  assert 'stop' in job.result['answer'].lower()
  print('All 50 notes inspected; recurring stop-movement issue present in the final answer. Isolated fixture removed on exit.')
finally:fixture.tearDown()
