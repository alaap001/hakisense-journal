"""Read-only diagnostic for explicitly named AI jobs; never prints prompts or secrets."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from backend.config import config
from backend.db import make_engine,AIJob,AICall
from backend.ai_contracts import Plan
from backend.ai_runtime import Runtime
from pydantic import ValidationError
parser=argparse.ArgumentParser();parser.add_argument('job_ids',nargs='+');args=parser.parse_args()
engine=make_engine(config.migration_url or config.database_url)
try:
 with engine.connect() as conn:
  for job in conn.execute(select(AIJob.id,AIJob.status,AIJob.model,AIJob.routing_config,AIJob.usage,AIJob.error).where(AIJob.id.in_(args.job_ids))).mappings():
   route={k:v for k,v in job['routing_config'].items() if k!='instructions'}
   print(json.dumps({'id':job['id'],'status':job['status'],'route':route,'usage':job['usage'],'error':job['error']},default=str))
   for call in conn.execute(select(AICall.agent,AICall.status,AICall.generation_id,AICall.response,AICall.usage).where(AICall.job_id==job['id']).order_by(AICall.created_at)).mappings():
    report={k:v for k,v in call.items() if k!='response'}
    report['response_characters']=len(call['response'] or '')
    if call['agent']=='coordinator' and call['response']:
     try:Runtime.parse(call['response'],Plan);report['validation']='valid'
     except ValidationError as exc:report['validation']=exc.errors(include_input=False,include_url=False)
    print(json.dumps(report,default=str))
finally:engine.dispose()
