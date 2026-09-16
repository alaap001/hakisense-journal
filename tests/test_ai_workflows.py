"""Workflow contracts and money/isolation outcomes; deterministic provider fixtures only."""
import asyncio
import json
import unittest
from unittest.mock import patch
from uuid import uuid4
from sqlalchemy import select, event, func
from tests import test_core as core
from backend import db as store
from backend import ai
from backend.ai_pricing import charge, allowance, VERSION
from backend.ai_contracts import Plan, EvidenceRequest, TradeSelection
from backend.ai_evidence import execute, answer_evidence, packed
from backend.ai_runtime import Runtime, HumanInput, normalize_usage, ProviderFailure, CapacityExceeded
from backend.jobs import enqueue, finish, pause_job, emit
from backend.schemas import AIRequest
from backend.worker import run_one
from backend.wallet import settle_reservations, spend, append, get_wallet


class TokenBuckets(unittest.TestCase):
    def test_boundaries_and_mixed_dimensions(self):
        for i,o,c in [(0,0,0),(8000,2000,1),(5000,3000,2),(8001,1,2),(16000,4000,2),(16001,1,3),(32000,6000,3),(1,6001,4),(64000,8000,4),(64001,1,7),(100000,16000,7)]:
            self.assertEqual(charge(i,o),c)
        for i,o in [(100001,0),(0,16001),(-1,0)]:
            with self.assertRaises(ValueError):charge(i,o)
        self.assertEqual(allowance(7),(100000,16000))

    def test_cache_and_reasoning_are_not_double_counted(self):
        value=normalize_usage({'prompt_tokens':5000,'completion_tokens':3000,'prompt_tokens_details':{'cached_tokens':4000},'completion_tokens_details':{'reasoning_tokens':2000}})
        self.assertEqual(charge(value['input_tokens'],value['output_tokens']),2)
        with self.assertRaises(ProviderFailure):normalize_usage({})


class Workflows(unittest.TestCase):
    setUp=core.ProductionCore.setUp
    tearDown=core.ProductionCore.tearDown
    trade=core.ProductionCore.trade

    def job(self,**changes):
        message=changes.pop('message','Review')
        with store.database(self.a) as db:
            job=enqueue(db,AIRequest(message=message,max_credits=7,pricing_version=VERSION,**changes),'workflow-'+str(uuid4()))
            return job

    def provider(self,plan,*,clarify=False,additional=False):
        self.calls=[]
        async def fake(model,messages,route,maximum,on_text,on_id):
            context=json.loads(messages[-1]['content']);system=messages[0]['content']
            self.calls.append({'system':system,'context':context,'maximum':maximum})
            await on_id('fixture-'+str(len(self.calls)))
            if 'You are the coordinator.' in system:
                content=plan.model_dump_json()
            else:
                content='Verified fixture answer. ₹4,850 net P&L.'
                await on_text(content)
            return content,{'input_tokens':1000,'output_tokens':200},'fixture-'+str(len(self.calls)),'stop'
        return fake

    def run_job(self,plan,**changes):
        job=self.job(**changes)
        with patch('backend.ai_runtime.provider_stream',side_effect=self.provider(plan)):
            asyncio.run(run_one())
        with store.database(self.a) as db:return db.get(store.AIJob,job.id)

    def test_concept_uses_two_small_agents_and_zero_trade_queries(self):
        queries=[]
        def record(conn,cursor,statement,parameters,context,many):queries.append(statement)
        event.listen(store.engine,'before_cursor_execute',record)
        try:
            job=self.run_job(Plan(task='Explain R multiple',coverage='none'))
        finally:event.remove(store.engine,'before_cursor_execute',record)
        self.assertEqual(job.status,'succeeded',job.error)
        self.assertEqual(len(self.calls),2)
        self.assertFalse(any('FROM main.trades' in q or 'FROM trades' in q for q in queries))
        self.assertEqual(job.credits,1)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],49)

    def seed(self,n=50,notes='A complete note with its exception at the END.',day='2026-09-10'):
        with store.database(self.a) as db:
            from backend.schemas import TradeInput
            for i in range(n):
                db.add(store.Trade(**TradeInput(**self.trade(symbol='TEST'+str(i),notes=notes,entry_time=day+'T09:15:00',exit_time=day+'T10:15:00')).model_dump()))

    def test_weekly_arithmetic_ignores_unrelated_history_and_notes(self):
        self.seed()
        filters={'start':'2026-09-10','end':'2026-09-10'}
        request=EvidenceRequest(kind='metrics',purpose='Exact P&L')
        first=execute(self.a,filters,request)
        self.seed(100,notes='DO NOT LEAK UNRELATED NOTES',day='2025-09-10')
        second=execute(self.a,filters,request)
        self.assertEqual(first['data'],second['data'])
        self.assertEqual(second['metadata']['matched'],50)
        self.assertEqual(second['data']['metrics']['net_pnl'],4850)
        self.assertNotIn('notes',json.dumps(second['data']))
        job=self.run_job(Plan(task='Weekly P&L',analysis='calculation',scope=filters,requests=[request]),mode='query')
        self.assertEqual(job.status,'succeeded',job.error)
        self.assertEqual(len(self.calls),2)
        self.assertNotIn('DO NOT LEAK',json.dumps(self.calls))
        self.assertNotIn('note_ref',json.dumps(self.calls[-1]['context']))

    def test_general_reviews_include_every_requested_trade_with_notes_and_risk(self):
        self.seed(300,notes='UNRELATED_OLD_NOTE',day='2025-09-10')
        self.seed(200)
        with store.database(self.a) as db:
            recent=list(db.scalars(select(store.Trade).where(store.Trade.entry_time >= '2026-09-01').order_by(store.Trade.id)))
            for i,t in enumerate(recent):
                t.notes=f'Trade {i}: waited for confirmation; followed the recorded stop.'
                t.stop_loss=95
                t.exit_price=110 if i%2 else 96
            ordered=sorted(recent,key=lambda t:(t.entry_time,t.id),reverse=True)
            expected=[{'id':t.id,'notes':t.notes,'net_pnl':97 if t.exit_price==110 else -43} for t in ordered]
        for count in (20,90,200):
            with self.subTest(count=count):
                # Reproduce the reported plan: metrics + groups, no record tools.
                plan=Plan(task='Summarize performance',analysis='calculation',coverage='aggregate',requests=[
                    EvidenceRequest(kind='metrics',purpose='Performance'),
                    EvidenceRequest(kind='groups',purpose='Setup breakdown',metric='win_rate')])
                job=self.run_job(plan,message=f'tell me about my last {count} trades')
                self.assertEqual(job.status,'succeeded',job.error)
                payload=self.calls[-1]['context']['evidence']
                records=[a for a in payload.values() if 'columns' in a['data']]
                self.assertEqual(len(records),1,'Do not duplicate records for each aggregate tool')
                data=records[0]['data']
                rows=[dict(zip(data['columns'],r)) for r in data['rows']]
                self.assertEqual([r['id'] for r in rows],[r['id'] for r in expected[:count]])
                self.assertEqual(data['metrics']['net_pnl'],sum(r['net_pnl'] for r in expected[:count]))
                for row,want in zip(rows,expected):
                    self.assertEqual(data['notes'][row['note_ref']],want['notes'])
                    self.assertEqual(row['net_pnl'],want['net_pnl'])
                    self.assertEqual(row['risk'],50)
                    self.assertAlmostEqual(row['r_multiple'],want['net_pnl']/50)
                    self.assertIn('rule_ref',row)
                self.assertNotIn('UNRELATED_OLD_NOTE',packed(payload))
                self.assertEqual(job.result['coverage']['records_inspected'],count)
                self.assertEqual(job.result['coverage']['records_included'],count)

    def test_specific_numeric_question_stays_metrics_only(self):
        self.seed(90,notes='A note that is not needed for arithmetic.')
        plan=Plan(task='Total P&L',analysis='calculation',requests=[EvidenceRequest(kind='metrics',purpose='Total P&L')])
        job=self.run_job(plan,message='What was the total P&L of my last 20 trades?')
        self.assertEqual(job.status,'succeeded',job.error)
        evidence=self.calls[-1]['context']['evidence']['e1']
        self.assertEqual(evidence['data']['metrics']['total_positions'],20)
        self.assertEqual(evidence['data']['metrics']['net_pnl'],1940)
        self.assertNotIn('notes',packed(evidence))
        self.assertEqual(job.result['coverage']['records_included'],0)

    def test_large_review_retains_eighty_varied_details_and_full_cohort_totals(self):
        self.seed(200)
        with store.database(self.a) as db:
            for i,t in enumerate(db.scalars(select(store.Trade).order_by(store.Trade.id))):
                t.notes=f'Trade {i}. '+('Recorded observation. '*100)
                t.exit_price=110 if i%2 else 96
                t.setup=['Breakout','Reversal','Trend'][i%3]
                t.emotion=['Calm','FOMO'][i%2]
        artifact=execute(self.a,{},EvidenceRequest(kind='records',purpose='Review',include_notes=True,include_rules=True))
        # A constrained fixture budget triggers sampling without changing the production cap.
        evidence,representations=answer_evidence({'e1':artifact},lambda e: len(packed(e))<230000)
        record=evidence['e1'];data=record['data']
        self.assertEqual(representations['e1'],'sample')
        self.assertEqual(record['record_coverage']['total'],200)
        self.assertEqual(len(data['rows']),80)
        self.assertEqual(data['metrics'],artifact['data']['metrics'])
        rows=[dict(zip(data['columns'],r)) for r in data['rows']]
        self.assertEqual({r['setup'] for r in rows},{'Breakout','Reversal','Trend'})
        self.assertTrue(any(r['net_pnl']<0 for r in rows))
        self.assertTrue(any(r['net_pnl']>0 for r in rows))
        self.assertEqual(rows[0]['id'],artifact['source_ids'][0])
        self.assertEqual(rows[-1]['id'],artifact['source_ids'][-1])
        original={r[0]:r[artifact['data']['columns'].index('notes')] for r in artifact['data']['rows']}
        self.assertTrue(all(data['notes'][r['note_ref']]==original[r['id']] for r in rows))
        self.assertEqual(len(artifact['data']['rows']),200,'Fitting must not mutate saved evidence')

    def test_fifty_notes_use_two_agents_and_lossless_deduplication(self):
        note='Recorded details. '*100+'Important exception at the END.'
        self.seed(50,note)
        plan=Plan(task='Read every trade note',coverage='exhaustive',requests=[EvidenceRequest(kind='records',purpose='Read all notes',include_notes=True,include_rules=True)])
        job=self.run_job(plan,mode='coach')
        self.assertEqual(job.status,'succeeded',job.error)
        self.assertEqual(len(self.calls),2)
        answer_data=self.calls[1]['context']['evidence']['e1']['data']
        self.assertEqual(len(answer_data['rows']),50)
        self.assertEqual(answer_data['notes'][answer_data['rows'][-1][answer_data['columns'].index('note_ref')]],note)
        self.assertEqual(job.result['coverage']['records_inspected'],50)
        self.assertEqual(answer_data['metrics']['net_pnl'],4850)
        self.assertIsNone(answer_data['metrics']['avg_r'])

    def test_selected_trade_does_not_pull_other_records(self):
        self.seed(3)
        with store.database(self.a) as db:trade_id=db.scalar(select(store.Trade.id))
        job=self.run_job(Plan(task='Review selected trade',coverage='none',requests=[EvidenceRequest(kind='records',purpose='Selected trade',trade_ids=[trade_id])]),mode='trade_note',trade_id=trade_id)
        self.assertEqual(job.status,'succeeded',job.error)
        self.assertEqual(job.result['coverage']['records_retrieved'],1)
        self.assertEqual(job.result['coverage']['records_inspected'],1)
        columns=self.calls[1]['context']['evidence']['e1']['data']['columns']
        for field in ('note_ref','rule_ref','entry_price'):
            self.assertIn(field,columns)

    def test_clarification_resume_and_duplicate_continue(self):
        job=self.run_job(Plan(task='Resolve scope',clarification='Which week?'))
        self.assertEqual(job.status,'awaiting_input')
        self.assertEqual(len(self.calls),1)
        response=self.client.post('/api/ai/jobs/'+job.id+'/continue',json={'revision':0,'answer':'Last week'})
        self.assertEqual(response.status_code,202,response.text)
        again=self.client.post('/api/ai/jobs/'+job.id+'/continue',json={'revision':0,'answer':'Last week'})
        self.assertEqual(again.json()['revision'],1)
        with patch('backend.ai_runtime.provider_stream',side_effect=self.provider(Plan(task='Answer clarified question',coverage='none'))):asyncio.run(run_one())
        with store.database(self.a) as db:
            saved=db.get(store.AIJob,job.id)
            self.assertEqual(saved.status,'succeeded',saved.error)
            self.assertEqual(saved.usage['calls'],3)
            self.assertEqual(saved.credits,1)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],49)

    def test_internal_capacity_failure_happens_before_paid_dispatch(self):
        job=self.job()
        with store.database(self.a) as db:
            row=db.get(store.AIJob,job.id);row.status='running';row.usage={'input_tokens':99000,'output_tokens':1000,'calls':1}
        runtime=Runtime(self.a,job.id,0,job.routing_config,7)
        with patch('backend.ai_runtime.provider_stream') as provider:
            with self.assertRaises(CapacityExceeded):asyncio.run(runtime.call('writer','large','Review',{'notes':'Large note '*3000}))
            provider.assert_not_called()
        with store.database(self.a) as db:self.assertEqual(db.scalar(select(func.count()).select_from(store.AICall)),0)

    def test_cross_tenant_jobs_events_continue_cancel_and_evidence(self):
        self.seed(1)
        job=self.run_job(Plan(task='Ask',clarification='Which account?'))
        self.actor=self.b;self.client.get('/api/workspace')
        for method,path,body in [('GET','',None),('GET','/events',None),('POST','/cancel',None),('POST','/continue',{'revision':0,'answer':'Other'})]:
            result=self.client.request(method,'/api/ai/jobs/'+job.id+path,json=body)
            self.assertEqual(result.status_code,404,result.text)
        self.assertEqual(execute(self.b,{},EvidenceRequest(kind='records',purpose='Read',include_notes=True))['metadata']['matched'],0)

    def test_reservation_partial_release_and_output_wins(self):
        job=self.job()
        with store.database(self.a) as db:
            row=db.get(store.AIJob,job.id);row.usage={'input_tokens':5000,'output_tokens':3000,'calls':4}
        result={'answer':'Fixture','thread_id':str(uuid4()),'coverage':{},'chart':None}
        finish(self.a,job.id,result);finish(self.a,job.id,result)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],48)
        with store.database(self.a) as db:
            entries=list(db.scalars(select(store.WalletEntry)))
            self.assertEqual(sum(e.amount for e in entries),48)
            self.assertEqual(db.get(store.AIJob,job.id).credits,2)

    def test_cancelled_run_cannot_publish_or_capture(self):
        job=self.job()
        cancel=self.client.post('/api/ai/jobs/'+job.id+'/cancel')
        self.assertEqual(cancel.json()['status'],'cancelled')
        finish(self.a,job.id,{'answer':'Late answer','thread_id':str(uuid4())})
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)
        with store.database(self.a) as db:self.assertEqual(db.scalar(select(func.count()).select_from(store.Message)),0)

    def test_note_append_conflict_does_not_overwrite_other_edits(self):
        self.seed(1)
        with store.database(self.a) as db:trade_id=db.scalar(select(store.Trade.id))
        job=self.run_job(Plan(task='Draft',coverage='targeted'),mode='trade_note',trade_id=trade_id)
        with store.database(self.a) as db:db.get(store.Trade,trade_id).notes='A concurrent note edit'
        result=self.client.post('/api/trades/'+trade_id+'/ai-note',json={'job_id':job.id,'expected_notes':'old','draft':'New AI draft'})
        self.assertEqual(result.status_code,409)
        success=self.client.post('/api/trades/'+trade_id+'/ai-note',json={'job_id':job.id,'expected_notes':'A concurrent note edit','draft':'New AI draft'})
        self.assertEqual(success.status_code,200,success.text)
        self.assertEqual(success.json()['notes'],'A concurrent note edit\n\nNew AI draft')

    def test_completed_call_reuse_is_free_and_unknown_dispatch_is_not_replayed(self):
        job=self.job()
        with store.database(self.a) as db:db.get(store.AIJob,job.id).status='running'
        runtime=Runtime(self.a,job.id,0,job.routing_config,7)
        async def fake(*args):return 'Saved answer',{'input_tokens':100,'output_tokens':10},'one','stop'
        with patch('backend.ai_runtime.provider_stream',side_effect=fake) as provider:
            for _ in range(2):self.assertEqual(asyncio.run(runtime.call('writer','one','Fixture',{},final=True)),'Saved answer')
            self.assertEqual(provider.call_count,1)
        with store.database(self.a) as db:db.get(store.AICall,(job.id,'one')).status='dispatched'
        with patch('backend.ai_runtime.provider_stream') as provider:
            with self.assertRaises(ProviderFailure):asyncio.run(runtime.call('writer','one','Fixture',{},final=True))
            provider.assert_not_called()

    def test_sse_replays_only_after_cursor_and_has_terminal_snapshot(self):
        job=self.run_job(Plan(task='Explain',coverage='none'))
        response=self.client.get('/api/ai/jobs/'+job.id+'/events?after=1')
        self.assertEqual(response.status_code,200)
        self.assertNotIn('id: 1\n',response.text)
        self.assertIn('event: text',response.text)
        self.assertIn('event: snapshot',response.text)
        self.assertIn('"status": "succeeded"',response.text)

    def test_large_notes_fit_automatically_without_a_customer_pause(self):
        # Distinct notes force excerpting; repeated notes are losslessly deduplicated.
        self.seed(3)
        with store.database(self.a) as db:
            for i,t in enumerate(db.scalars(select(store.Trade))):
                t.notes=('detail '+str(i)+' ')*20000
        plan=Plan(task='Read notes',coverage='exhaustive',requests=[EvidenceRequest(kind='records',purpose='Review notes',include_notes=True)])
        job=self.run_job(plan)
        self.assertEqual(job.status,'succeeded',job.error)
        self.assertIsNone(job.pause)
        evidence=self.calls[-1]['context']['evidence']['e1']
        self.assertEqual(len(evidence['data']['rows']),3)
        self.assertIn('excerpts',evidence['detail'])
        self.assertEqual(evidence['data']['metrics']['net_pnl'],291)
        self.assertEqual(job.result['coverage']['records_inspected'],0)

    def test_stopping_during_call_records_usage_before_settling(self):
        job=self.job()
        real_provider=self.provider(Plan(task='Concept',coverage='none'))
        async def stop_after_receipt(*args):
            result=await real_provider(*args)
            response=self.client.post('/api/ai/jobs/'+job.id+'/cancel')
            self.assertTrue(response.json()['cancel_requested'])
            return result
        with patch('backend.ai_runtime.provider_stream',side_effect=stop_after_receipt):asyncio.run(run_one())
        with store.database(self.a) as db:
            saved=db.get(store.AIJob,job.id)
            self.assertEqual(saved.status,'cancelled')
            self.assertEqual(saved.usage['calls'],1)
            self.assertEqual(saved.credits,1)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],49)

    def test_stop_racing_with_pause_settles_instead_of_leaving_a_locked_pause(self):
        job=self.job()
        with store.database(self.a) as db:
            saved=db.get(store.AIJob,job.id)
            saved.status='running'
            saved.usage={'input_tokens':1000,'output_tokens':200,'calls':1}
        self.client.post('/api/ai/jobs/'+job.id+'/cancel')
        pause_job(self.a,job.id,{}, {'kind':'clarification','question':'Which week?'},0)
        with store.database(self.a) as db:
            saved=db.get(store.AIJob,job.id)
            self.assertEqual(saved.status,'cancelled')
            self.assertIsNone(saved.pause)
            self.assertEqual(saved.credits,1)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],49)

    def test_unused_old_free_reservation_is_not_converted_to_purchased(self):
        job=self.job()
        with patch('backend.wallet.month_key',return_value='2099-01'):
            with store.database(self.a) as db:
                settle_reservations(db,job.id,2)
                wallet=get_wallet(db)
                self.assertEqual(wallet.free_balance,50)
                self.assertEqual(wallet.purchased_balance,0)
                settlement=db.scalar(select(store.WalletEntry).where(store.WalletEntry.event_key=='settle:'+job.id))
                self.assertEqual(settlement.details['expired_free_released'],5)

    def test_partial_exit_fees_risk_and_balance_match_existing_analytics(self):
        response=self.client.post('/api/trades',json=self.trade(status='Partial',closed_quantity=4,risk_amount=50))
        self.assertEqual(response.status_code,200,response.text)
        old=self.client.get('/api/analytics').json()['metrics']
        result=execute(self.a,{},EvidenceRequest(kind='metrics',purpose='Compare accounting'))['data']['metrics']
        self.assertEqual(result,old)
        self.assertEqual(result['net_pnl'],38.8)
        self.assertEqual(result['fees'],1.2)
        self.assertEqual(result['avg_r'],1.94)

    def test_latest_three_of_five_hundred_are_selected_before_notes_are_read(self):
        self.seed(497,notes='UNRELATED_OLD_NOTE',day='2025-09-10')
        self.seed(3,notes='The selected recent note.',day='2026-09-10')
        # Regression: even an omitted planner count must never broaden the explicit question.
        plan=Plan(task='Latest three trades',coverage='targeted',requests=[EvidenceRequest(kind='sequence',purpose='Recent trades',include_notes=True)])
        queries=[]
        def record(conn,cursor,statement,parameters,context,many):queries.append((statement,parameters))
        event.listen(store.engine,'before_cursor_execute',record)
        try:
            job=self.run_job(plan,message='hi, tell me about my last 3 trades')
        finally:event.remove(store.engine,'before_cursor_execute',record)
        self.assertEqual(job.status,'succeeded',job.error)
        self.assertEqual(len(self.calls),2)
        evidence=self.calls[-1]['context']['evidence']['e1']
        self.assertEqual(len(evidence['data']['rows']),3)
        self.assertEqual(evidence['data']['metrics']['net_pnl'],291)
        self.assertNotIn('UNRELATED_OLD_NOTE',json.dumps(self.calls))
        self.assertTrue(any('LIMIT' in sql and 'trades.entry_time DESC' in sql for sql,_ in queries))
        detail_queries=[sql for sql,_ in queries if 'trades.notes' in sql and 'FROM' in sql]
        self.assertTrue(detail_queries)
        self.assertTrue(all('trades.id IN' in sql for sql in detail_queries))
        self.assertEqual(job.result['coverage']['records_inspected'],3)

    def test_latest_earliest_and_previous_cohort_order_and_derived_filters(self):
        self.seed(6)
        with store.database(self.a) as db:
            trades=list(db.scalars(select(store.Trade).order_by(store.Trade.id)))
            for i,t in enumerate(trades):
                t.entry_time=f'2026-09-10T0{i}:00:00+00:00'
                t.exit_time=f'2026-09-10T0{i}:30:00+00:00'
                t.exit_price=90 if i%2 else 110
                t.tags=['chosen'] if i%2 else []
            ids=[t.id for t in trades]
        for selection,expected in [(TradeSelection(count=3),ids[-3:][::-1]),
                                   (TradeSelection(count=2,order='oldest'),ids[:2]),
                                   (TradeSelection(count=3,offset=3),ids[:3][::-1])]:
            evidence=execute(self.a,{},EvidenceRequest(kind='records',purpose='Select',selection=selection))
            self.assertEqual(evidence['source_ids'],expected)
        evidence=execute(self.a,{},EvidenceRequest(kind='records',purpose='Last two losses',filters={'outcome':'loss','tag':'chosen'},selection=TradeSelection(count=2),include_notes=True))
        self.assertEqual(evidence['source_ids'],[ids[5],ids[3]])

    def test_public_job_stream_history_and_catalog_exclude_internal_diagnostics(self):
        job=self.run_job(Plan(task='Explain',coverage='none'))
        paths=['/api/ai/jobs','/api/ai/jobs/'+job.id,'/api/ai/jobs/'+job.id+'/events',
               '/api/ai/threads/'+job.result['thread_id'],'/api/workspace','/api/backup']
        for path in paths:
            response=self.client.get(path)
            self.assertEqual(response.status_code,200,response.text)
            for internal in ('input_tokens','output_tokens','pricing_version','records_inspected','source_hash','100k'):
                self.assertNotIn(internal,response.text,path)
        with store.database(self.a) as db:
            self.assertEqual(db.get(store.AIJob,job.id).usage['calls'],2)

    def test_submission_chooses_affordable_reservation_without_customer_configuration(self):
        with store.database(self.a) as db:spend(db,'fixture-balance',48,'Fixture')
        response=self.client.post('/api/ai/query',json={'message':'Explain R multiple'},headers={'Idempotency-Key':'simple-submission'})
        self.assertEqual(response.status_code,202,response.text)
        with store.database(self.a) as db:self.assertEqual(db.get(store.AIJob,response.json()['id']).max_credits,2)

    def test_legacy_scope_pause_can_resume_the_original_clear_question(self):
        job=self.job(message='Tell me about my last 3 trades')
        with store.database(self.a) as db:
            saved=db.get(store.AIJob,job.id)
            db.delete(db.get(store.JobQueue,job.id))
            saved.status='awaiting_input'
            saved.pause={'kind':'scope','question':'The remaining evidence exceeds 100k input tokens'}
            saved.checkpoint={'node':'investigate','thread_id':str(uuid4()),'call_counter':1,'clarifications':[]}
        public=self.client.get('/api/ai/jobs/'+job.id).json()
        self.assertEqual(public['pause']['kind'],'retry')
        self.assertNotIn('100k',json.dumps(public))
        response=self.client.post('/api/ai/jobs/'+job.id+'/continue',json={'revision':0})
        self.assertEqual(response.status_code,202,response.text)
        self.seed(3)
        with patch('backend.ai_runtime.provider_stream',side_effect=self.provider(Plan(task='Recent',requests=[EvidenceRequest(kind='records',purpose='Recent')]))):asyncio.run(run_one())
        with store.database(self.a) as db:self.assertEqual(db.get(store.AIJob,job.id).status,'succeeded')

    def test_closed_cohort_excludes_newer_partial_positions_and_normalizes_case(self):
        self.seed(4)
        with store.database(self.a) as db:
            partial=db.scalar(select(store.Trade))
            partial.status='Partial';partial.closed_quantity=2
            partial.exit_time='2026-09-12T05:00:00+00:00'
            partial_id=partial.id
        plan=Plan(task='Recent closed positions',selection=TradeSelection(count=3,time_field='exit_time'),
                  requests=[EvidenceRequest(kind='records',purpose='Closed',filters={'status':'closed'})])
        job=self.run_job(plan,message='Walk through my three most recent closed positions')
        self.assertEqual(job.status,'succeeded',job.error)
        self.assertEqual(job.result['coverage']['records_inspected'],3)
        self.assertNotIn(partial_id,json.dumps(self.calls[-1]['context']['evidence']))

    def test_summary_and_daily_use_their_feature_instructions_and_exact_facts(self):
        self.seed(3)
        for mode in ('summary','daily'):
            with self.subTest(mode=mode):
                job=self.run_job(Plan(task='Review',requests=[EvidenceRequest(kind='metrics',purpose='Performance')]),mode=mode)
                self.assertEqual(job.status,'succeeded',job.error)
                self.assertEqual(len(self.calls),2)
                self.assertIn(ai.FEATURES[mode],self.calls[-1]['system'])
                self.assertEqual(self.calls[-1]['context']['evidence']['e1']['data']['metrics']['net_pnl'],291)

    def test_null_optional_planner_fields_do_not_break_the_next_chat(self):
        responses=[{'task':'Compare two cohorts','selection':None,'scope':None,'requests':[
            {'kind':'records','purpose':'Winners','filters':{'outcome':'win','status':'closed','tag':None},'selection':{'count':10}},
            {'kind':'records','purpose':'Losers','filters':{'outcome':'loss','status':'closed'},'selection':{'count':10}}]},
            {'task':'Greet','coverage':'none','selection':None,'scope':None,'requests':None,'clarification':None}]
        self.seed(50)
        with store.database(self.a) as db:
            for i,trade in enumerate(db.scalars(select(store.Trade))):trade.exit_price=95 if i%2 else 110
        for index,response in enumerate(responses):
            job=self.job(message='Compare my last 10 winners and last 10 losers' if index==0 else 'hi')
            async def provider(model,messages,route,maximum,on_text,on_id):
                content=json.dumps(response) if 'You are the coordinator.' in messages[0]['content'] else 'A valid answer.'
                if 'You are the answer writer.' in messages[0]['content']:await on_text(content)
                return content,{'input_tokens':1000,'output_tokens':100},'nullable-fixture','stop'
            with patch('backend.ai_runtime.provider_stream',side_effect=provider):asyncio.run(run_one())
            with store.database(self.a) as db:
                saved=db.get(store.AIJob,job.id)
                self.assertEqual(saved.status,'succeeded',saved.error)
                self.assertEqual(saved.result['coverage']['records_retrieved'],20 if index==0 else 0)

    def test_invalid_plan_failure_does_not_poison_the_following_run(self):
        bad=self.job()
        async def provider(*args):return '{"task":"Broken","selection":{"count":-1}}',{'input_tokens':100,'output_tokens':10},'bad-plan','stop'
        with patch('backend.ai_runtime.provider_stream',side_effect=provider):asyncio.run(run_one())
        with store.database(self.a) as db:self.assertEqual(db.get(store.AIJob,bad.id).status,'failed')
        good=self.run_job(Plan(task='Greet',coverage='none'),message='hi')
        self.assertEqual(good.status,'succeeded',good.error)
        self.assertEqual(good.credits,1)

    def test_provider_rate_limit_refunds_and_explains_availability_without_internal_details(self):
        job=self.job(message='hi')
        with patch('backend.ai_runtime.provider_stream',side_effect=ProviderFailure('Private provider diagnostics',status_code=429)):
            asyncio.run(run_one())
        public=self.client.get('/api/ai/jobs/'+job.id).json()
        self.assertEqual(public['status'],'failed')
        self.assertIn('temporarily busy',public['error'])
        self.assertNotIn('Private',public['error'])
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)
