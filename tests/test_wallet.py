"""Focused PAYG money checks. Isolated SQLite, fake identities, no provider calls."""
import unittest
from unittest.mock import patch
from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select,func
from tests import test_core as core
from backend import db as store
from backend.catalog import PACKS
from backend.wallet import get_wallet,spend,append,refund_spend,intro_eligible
from backend.recharges import RechargeInput,prepare,settle
from backend.schemas import AIRequest
from backend.jobs import enqueue,finish


class CreditWalletTests(unittest.TestCase):
    setUpBase=core.ProductionCore.setUp
    tearDown=core.ProductionCore.tearDown
    trade=core.ProductionCore.trade

    def setUp(self):
        self.setUpBase()

    def balanced(self,db):
        w=get_wallet(db)
        entries=list(db.scalars(select(store.WalletEntry).order_by(store.WalletEntry.sequence)))
        self.assertEqual(sum(e.amount for e in entries),w.balance)
        self.assertEqual(sum(e.free_delta for e in entries),w.free_balance)
        self.assertEqual(sum(e.purchased_delta for e in entries),w.purchased_balance)
        self.assertEqual([e.sequence for e in entries],list(range(1,w.revision+1)))

    def purchase(self,db,code='review_600',key='purchase-001'):
        pack=db.get(store.CreditPack,code)
        payload=RechargeInput(pack_code=code,expected_amount_paise=pack.amount_paise,expected_credits=pack.credits)
        purchase,_=prepare(db,payload,key)
        link={'id':'plink_'+purchase.id,'reference_id':purchase.id,'notes':{'hakisense_purchase':purchase.id},
            'amount':pack.amount_paise,'amount_paid':pack.amount_paise,'currency':'INR','accept_partial':False,
            'status':'paid','short_url':'https://rzp.io/i/test','order_id':'order_'+purchase.id,
            'payments':[{'payment_id':'pay_'+purchase.id,'status':'captured'}]}
        payment={'id':'pay_'+purchase.id,'order_id':'order_'+purchase.id,'amount':pack.amount_paise,'currency':'INR','status':'captured','amount_refunded':0}
        return purchase,link,payment,payload

    def test_rollover_preserves_purchased_and_refunds_once(self):
        with store.database(self.a) as db:
            w=get_wallet(db)
            append(db,w,'test-topup',purchased=100,reason='Fixture')
            spend(db,'spend-1',60,'Review')
            spend(db,'spend-1',60,'Review')
            self.assertEqual((w.free_balance,w.purchased_balance),(0,90))
        with patch('backend.wallet.month_key',return_value='2026-12'):
            with store.database(self.a) as db:
                w=get_wallet(db)
                self.assertEqual((w.free_balance,w.purchased_balance),(50,90))
                refund_spend(db,'spend-1','refund-1','Failed review')
                refund_spend(db,'spend-1','refund-1','Failed review')
                self.assertEqual((w.free_balance,w.purchased_balance),(50,150))
                self.balanced(db)

    def test_intro_single_claim_and_immutable_purchase_terms(self):
        with store.database(self.a) as db:
            p,link,payment,payload=self.purchase(db,'first_recharge')
            again,fresh=prepare(db,payload,'purchase-001')
            self.assertFalse(fresh);self.assertEqual(p.id,again.id)
            self.assertFalse(intro_eligible(db))
            db.get(store.CreditPack,'first_recharge').credits=999
            settle(db,p,link,payment)
            settle(db,p,link,payment)
            self.assertEqual(get_wallet(db).balance,100)
            payment['amount_refunded']=payment['amount'];payment['status']='refunded'
            settle(db,p,link,payment)
            self.assertFalse(intro_eligible(db))
            with self.assertRaises(HTTPException):prepare(db,RechargeInput(pack_code='first_recharge',expected_amount_paise=2100,expected_credits=999),'purchase-002')
            self.balanced(db)

    def test_reversals_debt_and_dispute_recovery(self):
        with store.database(self.a) as db:
            p,link,payment,_=self.purchase(db)
            settle(db,p,link,payment)
            spend(db,'large-review',640,'Fixture usage')
            payment['amount_refunded']=10000
            settle(db,p,link,payment)
            self.assertEqual(p.credited,298) # ceil(600*10000/19900) removed
            self.assertEqual(get_wallet(db).balance,-292)
            with self.assertRaises(HTTPException):spend(db,'no-debt-spend',1,'Blocked')
            payment['amount_refunded']=0
            settle(db,p,link,payment)
            self.assertEqual(p.credited,298) # stale refund state cannot add credits back
            settle(db,p,link,payment,{'id':'disp_one','payment_id':payment['id'],'status':'open'})
            self.assertEqual(p.credited,0)
            settle(db,p,link,payment,{'id':'disp_one','payment_id':payment['id'],'status':'won'})
            self.assertEqual(p.credited,298)
            self.balanced(db)

    def test_payment_mismatch_and_cross_tenant_are_rejected(self):
        with store.database(self.a) as db:
            p,link,payment,_=self.purchase(db)
            for key,bad in [('amount',1),('currency','USD'),('order_id','order_foreign'),('id','pay_other')]:
                with self.assertRaises(HTTPException):settle(db,p,link,{**payment,key:bad})
            self.assertEqual(get_wallet(db).balance,50)
            purchase_id=p.id
        self.actor=self.b
        self.client.get('/api/workspace')
        self.assertEqual(self.client.post('/api/billing/checkout/'+purchase_id+'/cancel').status_code,404)
        self.assertEqual(self.client.get('/api/billing/history').json()['purchases'],[])
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)

    def test_ai_advanced_reservation_and_failure(self):
        with store.database(self.a) as db:
            task=db.get(store.AITask,'chat')
            job=enqueue(db,AIRequest(message='Fixture only',model_tier='advanced',expected_credits=task.credits*3),'advanced-001')
            self.assertEqual(job.credits,task.credits*3)
            self.assertEqual(job.routing_config['tier'],'advanced')
            self.assertEqual(enqueue(db,AIRequest(message='Fixture only',model_tier='advanced',expected_credits=task.credits*3),'advanced-001').id,job.id)
            job_id=job.id
        finish(self.a,job_id,error='Fixture failure')
        finish(self.a,job_id,error='Duplicate failure')
        with store.database(self.a) as db:
            self.assertEqual(get_wallet(db).balance,50);self.balanced(db)

    def test_playbook_charge_link_snapshot_and_ownership(self):
        data={'data':{'title':'Opening range','checklist':['Wait for retest']},'expected_credits':1}
        headers={'Idempotency-Key':'playbook-001'}
        created=self.client.post('/api/records/playbook',json=data,headers=headers)
        self.assertEqual(created.status_code,200,created.text)
        book=created.json()
        self.assertEqual(self.client.post('/api/records/playbook',json=data,headers=headers).json()['id'],book['id'])
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],49)
        trade=self.client.post('/api/trades',json=self.trade(playbook_id=book['id'],setup='Forged label')).json()
        self.assertEqual(trade['setup'],'Opening range')
        self.assertEqual(trade['playbook_snapshot']['checklist'],['Wait for retest'])
        self.client.put('/api/records/playbook/'+book['id'],json={'data':{'title':'Renamed','checklist':['Different rule']}})
        edited=self.client.put('/api/trades/'+trade['id'],json=self.trade(playbook_id=book['id'])).json()
        self.assertEqual(edited['playbook_snapshot'],trade['playbook_snapshot'])
        self.assertEqual(self.client.get('/api/playbooks/performance').json()[book['id']]['count'],1)
        self.actor=self.b;other=self.client.get('/api/workspace').json()['accounts'][0]['id']
        self.assertEqual(self.client.post('/api/trades',json=self.trade(account_id=other,playbook_id=book['id'])).status_code,404)
        self.actor=self.a
        self.client.delete('/api/records/playbook/'+book['id'])
        self.assertEqual(self.client.get('/api/records/playbook').json(),[])
        self.assertEqual(self.client.post('/api/trades',json=self.trade(playbook_id=book['id'])).status_code,400)

    def test_admin_adjustments_and_pack_edits_are_audited(self):
        with store.database(self.a) as db:
            db.add(store.AdminMember(user_id=self.a,role='owner',active=True))
        request={'amount':100,'reason':'Fixture credit adjustment'}
        for _ in range(2):
            result=self.client.post('/api/admin/users/'+self.a+'/credits',json=request,headers={'Idempotency-Key':'admin-adjust-001'})
            self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],150)
        detail=self.client.get('/api/admin/users/'+self.a).json()
        self.assertTrue(detail['wallet_check']['matches'])
        payload={'name':'Review new','credits':700,'amount_paise':19900,'sort_order':2,'active':True,'reason':'Fixture new pack terms','revision':1}
        result=self.client.put('/api/admin/packs/review_600',json=payload,headers={'Idempotency-Key':'admin-pack-001'})
        self.assertEqual(result.status_code,200,result.text)
        packs=self.client.get('/api/catalog').json()['packs']
        self.assertEqual(next(p for p in packs if p['code']=='review_600')['credits'],700)
        with store.database(self.a) as db:db.get(store.AdminMember,self.a).role='support'
        self.assertEqual(self.client.put('/api/admin/packs/review_600',json={**payload,'revision':2},headers={'Idempotency-Key':'admin-pack-002'}).status_code,403)

    def test_catalog_all_features_and_no_new_subscription(self):
        catalog=self.client.get('/api/catalog').json()
        self.assertEqual(catalog['billing_model'],'pay_as_you_go')
        self.assertNotIn('prices',catalog)
        self.assertEqual([p['discount_percent'] for p in catalog['packs']],[58,0,66.8,87.5])
        self.assertEqual(catalog['packs'][-1]['value_multiple'],8)
        self.assertIn('replay',self.work['billing']['features'])
        self.assertIn('playbooks',self.work['billing']['features'])
        self.assertIsNone(self.work['billing']['trades']['limit'])
        self.assertIn(self.client.post('/api/billing/legacy/checkout',json={'price_code':'pro_monthly'},headers={'Idempotency-Key':'legacy-checkout'}).status_code,(404,405))

    def test_checkout_and_signed_webhook_deliver_once(self):
        import json,hmac,hashlib
        from dataclasses import replace
        from backend import billing
        remote={}
        def create_link(purchase):
            remote.update({'id':'plink_http','reference_id':purchase.id,'notes':{'hakisense_purchase':purchase.id},
                'amount':2100,'amount_paid':0,'currency':'INR','accept_partial':False,'status':'created',
                'short_url':'https://rzp.io/i/fixture','order_id':'order_http','payments':[]})
            return remote.copy()
        with patch('backend.recharges.checkout_ready',return_value=True),patch('backend.recharges.provider.credit_link',side_effect=create_link) as creation:
            payload={'pack_code':'first_recharge','expected_amount_paise':2100,'expected_credits':50}
            result=self.client.post('/api/billing/checkout',json=payload,headers={'Idempotency-Key':'http-checkout-001'})
            self.assertEqual(result.status_code,200,result.text)
            self.assertEqual(creation.call_count,1)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],50)
        remote.update(status='paid',amount_paid=2100,payments=[{'payment_id':'pay_http','status':'captured'}])
        payment={'id':'pay_http','order_id':'order_http','amount':2100,'currency':'INR','status':'captured','amount_refunded':0}
        raw=json.dumps({'event':'payment_link.paid','payload':{'payment_link':{'entity':{'id':'plink_http'}}}}).encode()
        secret='fixture-only-webhook'
        signature=hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
        with patch.object(billing,'config',replace(billing.config,razorpay_webhook_secret=secret)),patch('backend.recharges.provider.link',return_value=remote),patch('backend.recharges.provider.payment',return_value=payment):
            for event in ('event-one','event-one','event-two'):
                response=self.client.post('/api/webhooks/razorpay',content=raw,headers={'x-razorpay-signature':signature,'x-razorpay-event-id':event,'Content-Type':'application/json'})
                self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'],100)
        with store.database(self.a) as db:self.balanced(db)
