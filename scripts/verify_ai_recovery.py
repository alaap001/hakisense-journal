"""Opt-in synthetic reproduction of the reported complex-query/Hi failure sequence."""
import os,sys,asyncio,json,argparse
from dataclasses import replace
from pathlib import Path
from dotenv import dotenv_values
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
parser=argparse.ArgumentParser()
parser.add_argument('--run',action='store_true');parser.add_argument('--probe',action='store_true')
parser.add_argument('--tier',choices=('standard','advanced'),default='standard')
parser.add_argument('--output-limit',type=int,default=16000)
args=parser.parse_args()
if not args.run:raise SystemExit('Pass --run for live synthetic recovery checks.')
key=os.getenv('OPENROUTER_API_KEY') or dotenv_values(ROOT/'backend/.env').get('OPENROUTER_API_KEY') or dotenv_values(ROOT/'.env').get('OPENROUTER_API_KEY')
from tests.test_ai_workflows import Workflows
from backend import ai_runtime,db as store
from backend.jobs import enqueue
from backend.schemas import AIRequest
from backend.worker import run_one
from sqlalchemy import select
fixture=Workflows();fixture.setUp();ai_runtime.config=replace(ai_runtime.config,openrouter_key=key)
reports=[]
async def probe():
 # Match the saved Advanced route while using a harmless request, never customer context.
 try:
  async def ignore(*args):pass
  answer,receipt,generation,finish=await ai_runtime.provider_stream('z-ai/glm-5.3-flash',
   [{'role':'user','content':'Say hello in one sentence.'}],{'reasoning_effort':'none','temperature':0,'timeout_seconds':90},512,ignore,ignore)
  print(json.dumps({'advanced_probe':'succeeded','answer':answer,'receipt':receipt}),flush=True)
 except ai_runtime.ProviderFailure as exc:print(json.dumps({'advanced_probe':'failed','reason':str(exc)}),flush=True)
try:
 if args.probe:asyncio.run(probe())
 else:
  fixture.seed(500)
  with store.database(fixture.a) as db:
   for i,trade in enumerate(db.scalars(select(store.Trade).order_by(store.Trade.id))):
    trade.exit_price=110 if i%2 else 95
  thread_id=None
  for index,question in enumerate(("tell me about my last 10 profitable trades and last 10 losing trades, I don't care about unrealized ones, those you can ignore, but look at last 10 profitable and last 10 losing ones and tell me any patterns or issues you notice in those",'hi')):
   with store.database(fixture.a) as db:
    route=db.get(store.AIRoute,('chat',args.tier));route.max_output_tokens=args.output_limit;route.temperature=.1 if args.tier=='standard' else 0;route.reasoning_effort='medium'
    job=enqueue(db,AIRequest(message=question,model_tier=args.tier,thread_id=thread_id),'recovery-'+str(index))
   assert job.routing_config['tier']==args.tier
   asyncio.run(run_one())
   with store.database(fixture.a) as db:
    saved=db.get(store.AIJob,job.id)
    calls=[{'agent':c.agent,'model':c.model,'response':c.response,'usage':c.usage} for c in db.scalars(select(store.AICall).where(store.AICall.job_id==job.id).order_by(store.AICall.created_at))]
    report={'tier':args.tier,'output_limit':args.output_limit,'question':question,'status':saved.status,'error':saved.error,'usage':saved.usage,'credits':saved.credits,'result':saved.result,'calls':calls}
    reports.append(report);Path('/tmp/hakisense-recovery-'+args.tier+'.json').write_text(json.dumps(reports,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('calls','result')}),flush=True)
    assert saved.status=='succeeded','Inspect synthetic recovery report'
    assert saved.result['coverage']['records_retrieved']==(20 if index==0 else 0)
    thread_id=saved.result['thread_id']
finally:fixture.tearDown()
