"""Focused admin permission, billing and model-routing checks; no network calls."""
import unittest
from datetime import timedelta
from sqlalchemy import select, func
from tests import test_core as core
from backend import db as store
from backend.jobs import finish


class Administration(unittest.TestCase):
    setUp=core.ProductionCore.setUp
    tearDown=core.ProductionCore.tearDown

    def role(self,role='owner'):
        with store.Session() as db:
            db.add(store.AdminMember(user_id=self.a,role=role,active=True))
            db.commit()

    def change(self,path,body,method='PUT',key='admin-change-fixture'):
        return self.client.request(method,'/api/admin'+path,json={'reason':'Fixture change',**body},headers={'Idempotency-Key':key})

    def test_user_cannot_enter_admin_or_self_promote(self):
        self.assertEqual(self.client.get('/api/admin/catalog').status_code,403)
        self.assertEqual(self.change('/staff/'+self.a,{'role':'owner','active':True}).status_code,403)
        self.client.put('/api/profile',json={'data':{'display_name':'Owner','role':'owner'}})
        self.assertIsNone(self.client.get('/api/workspace').json()['admin_role'])
        self.assertEqual(self.client.get('/api/config').json()['password_min_length'],8)

    def test_support_reads_but_cannot_mutate(self):
        self.role('support')
        self.assertEqual(self.client.get('/api/admin/catalog').status_code,200)
        self.assertEqual(self.client.get('/api/admin/overview').status_code,200)
        result=self.change('/users/'+self.a+'/credits',{'amount':10},method='POST')
        self.assertEqual(result.status_code,403)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)

    def test_catalog_revision_and_audit_are_idempotent(self):
        self.role()
        body={'name':'Journal chat','credits':1,'enabled':True,'revision':1}
        first=self.change('/tasks/chat',body)
        self.assertEqual(first.status_code,200,first.text)
        repeated=self.change('/tasks/chat',body)
        self.assertEqual(repeated.json()['audit_id'],first.json()['audit_id'])
        stale=self.change('/tasks/chat',{**body,'credits':9},key='different-key-123')
        self.assertEqual(stale.status_code,409)
        self.assertEqual(self.client.get('/api/admin/catalog').json()['tasks'][0]['credits'],1)
        self.assertEqual(len(self.client.get('/api/admin/audit').json()['items']),1)

    def test_credit_adjustment_preserves_refund(self):
        self.role()
        result=self.change('/users/'+self.a+'/credits',{'amount':20},method='POST')
        self.assertEqual(result.status_code,200,result.text)
        self.change('/users/'+self.a+'/credits',{'amount':20},method='POST')
        job=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','expected_credits':2},headers={'Idempotency-Key':'credit-job-fixture'})
        self.assertEqual(job.status_code,202,job.text)
        finish(self.a,job.json()['id'],error='Fixture failure')
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],70)
        result=self.change('/users/'+self.a+'/credits',{'amount':-2000},method='POST',key='bad-credit-fixture')
        self.assertEqual(result.status_code,400)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],70)

    def test_routing_snapshot_survives_admin_change_and_zero_cost(self):
        self.role()
        catalog=self.client.get('/api/admin/catalog').json()
        route=next(r for r in catalog['routes'] if r['task_code']=='chat' and r['tier']=='standard')
        route={k:v for k,v in route.items() if k not in ('task_code','tier')}
        route.update(model_id='deepseek/deepseek-v4.1-flash',max_output_tokens=900,instructions='Use a concise format.',revision=1)
        updated=self.change('/routes/chat/standard',route)
        self.assertEqual(updated.status_code,200,updated.text)
        self.change('/tasks/chat',{'name':'Chat','credits':0,'enabled':True,'revision':2},key='free-task-fixture')
        job=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','expected_credits':0},headers={'Idempotency-Key':'snapshot-job-fixture'})
        self.assertEqual(job.status_code,202,job.text)
        with store.database(self.a) as db:
            record=db.get(store.AIJob,job.json()['id'])
            self.assertEqual(record.routing_config['model_id'],'deepseek/deepseek-v4.1-flash')
            self.assertEqual(record.routing_config['max_output_tokens'],900)
        route.update(model_id='qwen/qwen3.7-flash',revision=3)
        self.assertEqual(self.change('/routes/chat/standard',route,key='changed-route-key').status_code,200)
        with store.database(self.a) as db:
            self.assertEqual(db.get(store.AIJob,job.json()['id']).model,'deepseek/deepseek-v4.1-flash')
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)

    def test_last_owner_protected_and_recurring_prices_removed(self):
        self.role()
        self.assertEqual(self.change('/staff/'+self.a,{'role':'support','active':True}).status_code,409)
        self.assertIn(self.change('/prices/pro_annual',{'revision':1}).status_code,(404,405))
        self.assertEqual(self.change('/users/'+self.a,{'display_name':'Fixture','suspended':True},key='suspend-self-fixture').status_code,400)

    def test_added_credits_refund_without_forgiving_prior_usage(self):
        self.role()
        with store.database(self.a) as db:
            from backend.wallet import spend
            spend(db,'fixture-spend',50,'Fixture existing usage')
        self.assertEqual(self.change('/users/'+self.a+'/credits',{'amount':20},method='POST').status_code,200)
        job=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','expected_credits':2},headers={'Idempotency-Key':'bonus-refund-fixture'})
        self.assertEqual(job.status_code,202,job.text)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],18)
        finish(self.a,job.json()['id'],error='Fixture failure')
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],20)

    def test_langgraph_passes_saved_route_to_both_model_calls(self):
        import asyncio
        from unittest.mock import patch
        from types import SimpleNamespace
        from backend import ai
        from backend.schemas import AIRequest,QueryPlan
        route={'model_id':'qwen/qwen3.7-flash','planner_model_id':'z-ai/glm-5.3-flash','max_output_tokens':700,'timeout_seconds':40,'temperature':0.1,'reasoning_effort':'none','instructions':'Keep it brief.'}
        calls=[]
        def fake_model(model_id,saved=None):
            calls.append((model_id,saved))
            class Fake:
                async def ainvoke(self,messages):
                    return SimpleNamespace(content=QueryPlan().model_dump_json() if model_id==route['planner_model_id'] else 'Fixture answer')
            return Fake()
        with patch.object(ai,'model',side_effect=fake_model):
            result=asyncio.run(ai.ask(AIRequest(message='Summarize',mode='query'),self.a,route['model_id'],route))
        self.assertEqual(result['answer'],'Fixture answer')
        self.assertEqual([c[0] for c in calls],['qwen/qwen3.7-flash','z-ai/glm-5.3-flash','qwen/qwen3.7-flash'])
        self.assertTrue(all(c[1]==route for c in calls))

    def test_settings_disable_ai_and_feature_gates_read_catalog(self):
        self.role()
        catalog=self.client.get('/api/admin/catalog').json()
        values={**catalog['settings'],'ai_enabled':False,'announcement':'Service announcement'}
        self.assertEqual(self.change('/settings',{'revision':1,'value':values}).status_code,200)
        self.assertFalse(self.client.get('/api/workspace').json()['billing']['ai_available'])
        self.assertEqual(self.client.get('/api/workspace').json()['product']['announcement'],'Service announcement')
        result=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','expected_credits':2},headers={'Idempotency-Key':'disabled-task-fixture'})
        self.assertEqual(result.status_code,503)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)
