"""Opt-in synthetic live provider check. No customer records; no wallet or database writes."""
import argparse,asyncio,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from backend.config import config
from backend.ai_runtime import provider_stream
from backend.ai_contracts import Plan
from backend.ai import BASE,json_instruction
from backend.ai_pricing import charge
parser=argparse.ArgumentParser()
parser.add_argument('--run',action='store_true',help='Make one short coordinator call and one final writer call against the configured Standard model')
args=parser.parse_args()
async def main():
 async with httpx.AsyncClient(timeout=30) as client:
  response=await client.get('https://openrouter.ai/api/v1/models')
  response.raise_for_status()
  models={r['id']:r for r in response.json()['data']}
 model=config.standard_model
 info=models.get(model)
 if not info:
  print(json.dumps({'configured_model':model,'available':False}));return
 print(json.dumps({'configured_model':model,'available':True,'context_length':info.get('context_length'),'architecture':info.get('architecture'),'hugging_face_id':info.get('hugging_face_id')}))
 if not args.run:return
 async def ignore(value):pass
 route={'temperature':.1,'reasoning_effort':'none','timeout_seconds':90}
 prompt=json_instruction('You are the coordinator. Plan a conceptual explanation of R multiple. No journal data is needed. Set coverage to none and leave requests empty.',Plan)
 result,usage,generation,stop=await provider_stream(model,[{'role':'system','content':prompt},{'role':'user','content':'Explain what R multiple means in a trading journal.'}],route,1600,ignore,ignore)
 plan=Plan.model_validate_json(result.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip())
 assert stop=='stop' and plan.coverage=='none' and not plan.requests
 answer,usage2,generation2,stop2=await provider_stream(model,[{'role':'system','content':BASE+' You are the answer writer. Explain this concept in three short sentences.'},{'role':'user','content':plan.task}],route,500,ignore,ignore)
 assert stop2=='stop' and len(answer.strip())>40
 inputs=usage['input_tokens']+usage2['input_tokens'];outputs=usage['output_tokens']+usage2['output_tokens']
 print(json.dumps({'status':'passed','model_calls':2,'input_tokens':inputs,'output_tokens':outputs,'credits':charge(inputs,outputs),'nonempty_output':True,'provider_cost':(usage.get('provider_cost') or 0)+(usage2.get('provider_cost') or 0)}))
asyncio.run(main())
