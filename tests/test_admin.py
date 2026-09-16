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
        body={'name':'Journal chat','enabled':True,'revision':1}
        first=self.change('/tasks/chat',body)
        self.assertEqual(first.status_code,200,first.text)
        repeated=self.change('/tasks/chat',body)
        self.assertEqual(repeated.json()['audit_id'],first.json()['audit_id'])
        stale=self.change('/tasks/chat',{**body,'name':'Stale name'},key='different-key-123')
        self.assertEqual(stale.status_code,409)
        catalog=self.client.get('/api/admin/catalog').json()
        self.assertNotIn('credits',catalog['tasks'][0])
        self.assertEqual(catalog['ai_pricing']['input_limit'],100000)
        self.assertNotIn('advanced_credit_multiplier',catalog['settings'])
        retired=self.change('/tasks/chat',{**body,'credits':9},key='retired-price-field')
        self.assertEqual(retired.status_code,422)
        self.assertEqual(len(self.client.get('/api/admin/audit').json()['items']),1)

    def test_credit_adjustment_preserves_refund(self):
        self.role()
        result=self.change('/users/'+self.a+'/credits',{'amount':20},method='POST')
        self.assertEqual(result.status_code,200,result.text)
        self.change('/users/'+self.a+'/credits',{'amount':20},method='POST')
        job=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','max_credits':2,'pricing_version':'workflow-buckets-v1'},headers={'Idempotency-Key':'credit-job-fixture'})
        self.assertEqual(job.status_code,202,job.text)
        finish(self.a,job.json()['id'],error='Fixture failure')
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],70)
        result=self.change('/users/'+self.a+'/credits',{'amount':-2000},method='POST',key='bad-credit-fixture')
        self.assertEqual(result.status_code,400)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],70)

    def test_routing_snapshot_survives_admin_change_and_legacy_zero_price(self):
        self.role()
        catalog=self.client.get('/api/admin/catalog').json()
        route=next(r for r in catalog['routes'] if r['task_code']=='chat' and r['tier']=='standard')
        route={k:v for k,v in route.items() if k not in ('task_code','tier')}
        route.update(model_id='deepseek/deepseek-v4.1-flash',max_output_tokens=900,instructions='Use a concise format.',revision=1)
        updated=self.change('/routes/chat/standard',route)
        self.assertEqual(updated.status_code,200,updated.text)
        self.change('/tasks/chat',{'name':'Chat','enabled':True,'revision':2},key='rename-task-fixture')
        job=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','max_credits':1,'pricing_version':'workflow-buckets-v1'},headers={'Idempotency-Key':'snapshot-job-fixture'})
        self.assertEqual(job.status_code,202,job.text)
        with store.database(self.a) as db:
            record=db.get(store.AIJob,job.json()['id'])
            self.assertEqual(record.routing_config['model_id'],'deepseek/deepseek-v4.1-flash')
            self.assertEqual(record.routing_config['max_output_tokens'],900)
        route.update(model_id='qwen/qwen3.7-flash',revision=3)
        self.assertEqual(self.change('/routes/chat/standard',route,key='changed-route-key').status_code,200)
        with store.database(self.a) as db:
            self.assertEqual(db.get(store.AIJob,job.json()['id']).model,'deepseek/deepseek-v4.1-flash')
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],49)

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
        job=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','max_credits':2,'pricing_version':'workflow-buckets-v1'},headers={'Idempotency-Key':'bonus-refund-fixture'})
        self.assertEqual(job.status_code,202,job.text)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],18)
        finish(self.a,job.json()['id'],error='Fixture failure')
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],20)

    def test_specialist_runtime_preserves_saved_route(self):
        import asyncio,json
        from unittest.mock import patch
        from backend.ai_runtime import Runtime
        from backend.jobs import enqueue
        from backend.schemas import AIRequest
        with store.database(self.a) as db:
            job=enqueue(db,AIRequest(message='A concept',max_credits=7,pricing_version='workflow-buckets-v1'),'model-route-fixture')
            job.status='running'
            job.routing_config={**job.routing_config,'model_id':'writer-model','planner_model_id':'planner-model'}
            route=job.routing_config
        calls=[]
        async def provider(model,messages,saved,maximum,on_text,on_id):
            calls.append((model,saved,maximum))
            return 'Fixture answer',{'input_tokens':100,'output_tokens':20},'fixture-id','stop'
        runtime=Runtime(self.a,job.id,0,route,7)
        with patch('backend.ai_runtime.provider_stream',side_effect=provider):
            for agent in ('coordinator','writer'):
                asyncio.run(runtime.call(agent,agent,'Fixture',{},final=agent=='writer'))
        self.assertEqual([c[0] for c in calls],['planner-model','writer-model'])
        self.assertEqual(calls[0][1],{**route,'reasoning_effort':'none'})
        self.assertEqual(calls[1][1],route)

    def test_settings_disable_ai_and_feature_gates_read_catalog(self):
        self.role()
        catalog=self.client.get('/api/admin/catalog').json()
        values={**catalog['settings'],'ai_enabled':False,'announcement':'Service announcement'}
        self.assertEqual(self.change('/settings',{'revision':1,'value':values}).status_code,200)
        self.assertFalse(self.client.get('/api/workspace').json()['billing']['ai_available'])
        self.assertEqual(self.client.get('/api/workspace').json()['product']['announcement'],'Service announcement')
        result=self.client.post('/api/ai/query',json={'message':'Review','mode':'chat','max_credits':2,'pricing_version':'workflow-buckets-v1'},headers={'Idempotency-Key':'disabled-task-fixture'})
        self.assertEqual(result.status_code,503)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)

    def test_overview_separates_settled_charges_from_current_reservations(self):
        from backend.jobs import enqueue
        from backend.schemas import AIRequest
        from backend.ai_pricing import VERSION
        self.role()
        with store.database(self.a) as db:
            done=enqueue(db,AIRequest(message='Private question',max_credits=7,pricing_version=VERSION),'overview-settlement')
            done.usage={'input_tokens':5000,'output_tokens':3000,'calls':4,'reasoning_tokens':1000}
            done.created_at=store.utcnow()-timedelta(days=40)
        finish(self.a,done.id,{'answer':'Private answer','thread_id':store.uid()})
        with store.database(self.a) as db:
            held=enqueue(db,AIRequest(message='Another question',max_credits=4,pricing_version=VERSION),'overview-reservation')
            held.status='awaiting_input'
            db.add(store.AIJob(idempotency_key='legacy-failed',request_hash='0'*64,request={},task_code='chat',
                model='legacy',credits=5,month='2026-01',status='failed',finished_at=store.utcnow()))
        result=self.client.get('/api/admin/overview')
        self.assertEqual(result.status_code,200,result.text)
        values=result.json()
        self.assertEqual(values['credits_used_this_month'],2)
        self.assertEqual(values['ai_credits_charged_this_month'],2)
        self.assertEqual(values['ai_credits_reserved'],4)
        self.assertEqual(values['ai_usage_this_month']['input_tokens'],5000)
        self.assertEqual(values['ai_usage_this_month']['output_tokens'],3000)

    def test_operations_filtering_receipts_and_private_payload_exclusion(self):
        from backend.jobs import enqueue
        from backend.schemas import AIRequest
        from backend.ai_pricing import VERSION
        self.role('support')
        with store.database(self.a) as db:
            job=enqueue(db,AIRequest(message='DO_NOT_EXPOSE_QUESTION',max_credits=7,pricing_version=VERSION),'operations-metadata')
            job.usage={'input_tokens':5000,'output_tokens':3000,'calls':3}
            job.routing_config={**job.routing_config,'instructions':'DO_NOT_EXPOSE_INSTRUCTIONS'}
        finish(self.a,job.id,{'answer':'DO_NOT_EXPOSE_ANSWER','thread_id':store.uid()})
        result=self.client.get('/api/admin/jobs',params={'q':job.id,'task':'chat','status':'succeeded'})
        self.assertEqual(result.status_code,200,result.text)
        item=result.json()['items'][0]
        self.assertEqual(item['billing'],{'legacy':False,'maximum':7,'charged':2,'reserved':0,'released':5})
        self.assertEqual(item['routing']['tier'],'standard')
        self.assertNotIn('DO_NOT_EXPOSE',result.text)
        self.assertFalse({'request','result','checkpoint','pause','routing_config'} & item.keys())
        self.assertEqual(self.client.get('/api/admin/jobs',params={'task':'daily'}).json()['items'],[])
        self.assertEqual(self.client.get('/api/admin/jobs?status=unrecognized').status_code,422)
        self.assertEqual(self.change('/tasks/chat',{'name':'No write','enabled':False,'revision':1}).status_code,403)

    def test_partial_settings_edit_preserves_unedited_values_and_zero_grants(self):
        self.role()
        with store.Session() as db:
            state=db.get(store.PlatformConfig,'product')
            state.value={**state.value,'advanced_credit_multiplier':9,'support_email':'support@example.invalid'}
            db.commit()
        saved=self.change('/settings',{'revision':1,'value':{'monthly_free_credits':0}})
        self.assertEqual(saved.status_code,200,saved.text)
        with store.Session() as db:
            value=db.get(store.PlatformConfig,'product').value
            self.assertEqual(value['monthly_free_credits'],0)
            self.assertEqual(value['advanced_credit_multiplier'],9)
            self.assertEqual(value['support_email'],'support@example.invalid')
