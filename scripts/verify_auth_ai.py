"""One disposable Supabase account verifies real Auth and optionally one paid AI job.
No email is sent. The fixture account and its journal data are deleted in finally.
"""
import sys
import argparse
import asyncio
import secrets
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from backend.config import config
from backend.main import app
from backend.db import database, AIJob
from backend import ai
from backend.jobs import finish
from backend.ai_runtime import Runtime
from backend.schemas import AIRequest

parser=argparse.ArgumentParser()
parser.add_argument('--ai',action='store_true',help='Make one short, paid standard-model request')
args=parser.parse_args()
secret=dotenv_values(Path(__file__).resolve().parents[1]/'backend'/'.env').get('SUPABASE_SECRET_KEY')
if not secret:
    raise SystemExit('SUPABASE_SECRET_KEY is required for temporary Auth fixture management.')
headers={'apikey':secret,'Authorization':'Bearer '+secret}
email='hakisense-verification-'+str(uuid4())+'@example.invalid'
password=secrets.token_urlsafe(32)
user_id=None
job_id=None
with httpx.Client(timeout=20) as http:
    try:
        created=http.post(config.supabase_url+'/auth/v1/admin/users',headers=headers,json={'email':email,'password':password,'email_confirm':True,'user_metadata':{'display_name':'Temporary verification'}})
        if not created.is_success:
            raise RuntimeError('Temporary Auth user creation failed: HTTP '+str(created.status_code))
        user_id=created.json()['id']
        login=http.post(config.supabase_url+'/auth/v1/token?grant_type=password',headers={'apikey':config.supabase_key},json={'email':email,'password':password})
        if not login.is_success:
            raise RuntimeError('Temporary sign-in failed: HTTP '+str(login.status_code))
        token=login.json()['access_token']
        with TestClient(app) as client:
            client.headers.update({'Authorization':'Bearer '+token})
            response=client.get('/api/workspace')
            assert response.status_code==200, 'Authenticated workspace failed with HTTP '+str(response.status_code)
            workspace=response.json()
            assert workspace['billing']['credits']['remaining']==50
            assert workspace['currency']=='INR'
            account_id=workspace['accounts'][0]['id']
            response=client.post('/api/trades',json={'account_id':account_id,'symbol':'HAKI-VERIFY','entry_price':100,'exit_price':110,'quantity':10,'commission':2,'fees':1,'entry_time':'2026-09-10T09:15:00','exit_time':'2026-09-10T10:00:00','notes':'Disposable verification fixture, not a real market trade.'})
            assert response.status_code==200, 'Trade creation failed'
            assert response.json()['net_pnl']==97
            assert client.get('/api/simulator').status_code==200
            assert client.get('/api/backup').status_code==200
            print('Real Supabase sign-in, verified JWT, onboarding, INR trade, free allowance, unlocked tools and authenticated export: passed')
            if args.ai:
                request={'message':'In one sentence, report only my recorded trade count and net P&L in INR.','mode':'summary','pricing_version':'workflow-buckets-v1','max_credits':7}
                response=client.post('/api/ai/query',json=request,headers={'Idempotency-Key':'live-check-'+str(uuid4())})
                assert response.status_code==202, 'AI enqueue failed with HTTP '+str(response.status_code)
                job_id=response.json()['id']
                with database(user_id) as db:
                    job=db.get(AIJob,job_id)
                    job.status='running'
                    model=job.model
                    route=job.routing_config
                result=asyncio.run(ai.ask(AIRequest.model_validate(request),user_id,model,route,runtime=Runtime(user_id,job_id,0,route,7)))
                assert result['answer'].strip(), 'AI response was empty'
                finish(user_id,job_id,result)
                state=client.get('/api/ai/jobs/'+job_id).json()
                assert state['status']=='succeeded'
                assert client.get('/api/billing/me').json()['credits']['remaining']==50-state['credits']
                print('One real LangGraph/OpenRouter standard-model review, saved result and usage-bucket settlement: passed ('+model+')')
    finally:
        if user_id:
            if job_id:
                try:
                    finish(user_id,job_id,error='Verification cleanup')
                except Exception:
                    pass
            deleted=http.delete(config.supabase_url+'/auth/v1/admin/users/'+user_id,headers=headers)
            if not deleted.is_success:
                raise RuntimeError('Temporary account cleanup failed; remove Auth user '+user_id)
            print('Temporary Auth account and journal data deleted. No email was sent.')
