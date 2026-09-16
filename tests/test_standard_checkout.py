"""Payment boundary checks with isolated storage and no external requests."""
import hashlib
import hmac
import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from tests import test_core as core
from backend import payments, billing, runtime_settings
from backend import db as store
from backend.wallet import get_wallet


class StandardCheckoutTests(unittest.TestCase):
    setUpBase=core.ProductionCore.setUp
    tearDown=core.ProductionCore.tearDown

    def setUp(self):
        self.setUpBase()
        self.remote={}
        self.payment={'id':'pay_fixture','order_id':'order_fixture','amount':2400,
            'currency':'INR','status':'captured','amount_refunded':0}
        self.config=replace(payments.config,razorpay_key='rzp_test_fixture',razorpay_secret='fixture-secret')
        for target,kwargs in [
            ('backend.payments.config',{'new':self.config}),
            ('backend.recharges.checkout_ready',{'return_value':True}),
            ('backend.recharges.provider.create_order',{'side_effect':self.create_remote}),
            ('backend.recharges.provider.order',{'side_effect':lambda _:dict(self.remote)}),
            ('backend.recharges.provider.order_payments',{'side_effect':lambda _:[dict(self.payment)] if self.remote.get('amount_paid') else []}),
            ('backend.recharges.provider.payment',{'side_effect':lambda _:dict(self.payment)}),
        ]:
            patcher=patch(target,**kwargs);patcher.start();self.addCleanup(patcher.stop)

    def create_remote(self,purchase):
        self.remote.update(id='order_fixture',receipt=purchase.id,notes={'hakisense_purchase':purchase.id},
            amount=purchase.amount_paise,currency='INR',amount_paid=0,status='created')
        return dict(self.remote)

    def create(self,key='order-fixture-001',**changes):
        return self.client.post('/api/billing/create-order',json={
            'pack_code':'first_recharge','expected_amount_paise':2400,'expected_credits':50,**changes},
            headers={'Idempotency-Key':key})

    def signature(self):
        return {'razorpay_order_id':'order_fixture','razorpay_payment_id':'pay_fixture',
            'razorpay_signature':hmac.new(b'fixture-secret',b'order_fixture|pay_fixture',hashlib.sha256).hexdigest()}

    def verify(self,**changes):
        return self.client.post('/api/billing/verify-payment',json={**self.signature(),**changes})

    def balance(self):
        with store.database(self.a) as db:return get_wallet(db).balance

    def test_order_retry_and_signed_callback_credit_once(self):
        created=self.create()
        self.assertEqual(created.status_code,200,created.text)
        self.assertEqual((created.json()['amount'],created.json()['currency']),(2400,'INR'))
        self.assertEqual(self.create().json()['order_id'],'order_fixture')
        self.assertEqual(payments.provider.create_order.call_count,1)
        self.assertEqual(self.balance(),50)
        self.remote.update(amount_paid=2400,status='paid')
        for _ in range(2):
            response=self.verify();self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(response.json()['success'])
        self.assertEqual(self.balance(),100)

    def test_missing_bad_signatures_and_foreign_order_never_credit(self):
        self.create()
        for body in ({},{'razorpay_order_id':'order_fixture'}):
            self.assertEqual(self.client.post('/api/billing/verify-payment',json=body).status_code,400)
        self.assertEqual(self.client.post('/api/billing/verify-payment').status_code,400)
        for signature in ('0'*64,'é'*64):self.assertEqual(self.verify(razorpay_signature=signature).status_code,400)
        payments.provider.payment.assert_not_called()
        self.actor=self.b
        self.assertEqual(self.verify().status_code,404)
        self.assertEqual(self.balance(),50)

    def test_authorized_payment_waits_then_capture_grants(self):
        self.create();self.payment['status']='authorized'
        result=self.verify()
        self.assertEqual(result.status_code,202,result.text)
        self.assertFalse(result.json()['success']);self.assertEqual(self.balance(),50)
        self.payment['status']='captured';self.remote.update(amount_paid=2400,status='paid')
        self.assertEqual(self.verify().status_code,200)
        self.assertEqual(self.balance(),100)

    def test_amount_currency_and_order_mismatch_rejected(self):
        self.create();self.remote.update(amount_paid=2400,status='paid')
        for field,value in (('amount',100),('currency','USD'),('order_id','order_other')):
            with patch.dict(self.payment,{field:value}):self.assertEqual(self.verify().status_code,409)
            self.assertEqual(self.balance(),50)

    def test_uncertain_order_recovers_without_second_create(self):
        def timeout(purchase):
            self.create_remote(purchase)
            raise HTTPException(500,'Confirmation pending')
        payments.provider.create_order.side_effect=timeout
        self.assertEqual(self.create().status_code,500)
        with patch.object(payments.provider,'find_order',return_value=dict(self.remote)):
            self.assertEqual(self.create().status_code,200)
        self.assertEqual(payments.provider.create_order.call_count,1)

    def test_cancelled_order_keeps_intro_claim_and_late_capture_is_credited(self):
        purchase=self.create().json()
        self.payment['status']='failed'
        result=self.client.post('/api/billing/checkout/'+purchase['id']+'/cancel')
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.create(key='another-order-key').status_code,409)
        self.payment['status']='captured';self.remote.update(amount_paid=2400,status='paid')
        self.assertEqual(self.verify().status_code,200)
        self.assertEqual(self.balance(),100)

    def test_payment_webhook_and_refund_recover_without_browser_callback(self):
        self.create();self.remote.update(amount_paid=2400,status='paid')
        cfg=replace(billing.config,razorpay_webhook_secret='webhook-fixture')
        with patch.object(billing,'config',cfg):
            for event_id,event,payload in (
                ('capture','payment.captured',{'payment':{'entity':{'id':'pay_fixture','order_id':'order_fixture'}}}),
                ('refund','refund.processed',{'refund':{'entity':{'payment_id':'pay_fixture'}}}),
            ):
                if event_id=='refund':self.payment.update(amount_refunded=2400,status='refunded')
                raw=json.dumps({'event':event,'payload':payload}).encode()
                headers={'x-razorpay-event-id':event_id,'x-razorpay-signature':hmac.new(b'webhook-fixture',raw,hashlib.sha256).hexdigest()}
                for _ in range(2):
                    response=self.client.post('/api/webhooks/razorpay',content=raw,headers=headers)
                    self.assertEqual(response.status_code,200,response.text)
                self.assertEqual(self.balance(),100 if event_id=='capture' else 50)

    def test_minimum_pack_price_and_untrusted_amount(self):
        self.assertEqual(self.create(expected_amount_paise=100).status_code,409)
        with store.Session() as db:
            db.get(store.CreditPack,'first_recharge').amount_paise=99;db.commit()
        self.assertEqual(self.create(expected_amount_paise=99).status_code,400)
        payments.provider.create_order.assert_not_called()

    def test_hosted_test_checkout_requires_active_owner_or_admin(self):
        from backend import recharges
        cfg=replace(recharges.config,environment='production',razorpay_key='rzp_test_fixture',razorpay_allow_test_checkout=True)
        with patch.object(recharges,'config',cfg):
            self.assertEqual(self.create().status_code,403)
            payments.provider.create_order.assert_not_called()
            with store.Session() as db:
                db.add(store.AdminMember(user_id=self.a,role='support',active=True));db.commit()
            self.assertEqual(self.create().status_code,403)
            with store.Session() as db:
                db.get(store.AdminMember,self.a).role='owner';db.commit()
            result=self.create()
            self.assertEqual(result.status_code,200,result.text)
            with store.Session() as db:
                db.get(store.AdminMember,self.a).active=False;db.commit()
            self.assertEqual(self.verify().status_code,403)


class ProviderTests(unittest.TestCase):
    def test_minimum_amount_auth_and_provider_failures(self):
        provider=payments.PaymentProvider()
        with patch.object(payments,'config',replace(payments.config,razorpay_key='rzp_test_fixture',razorpay_secret='fixture')):
            with self.assertRaises(HTTPException) as error:provider.create_order(SimpleNamespace(amount_paise=99))
            self.assertEqual(error.exception.status_code,400)
            for remote_status,expected in ((401,401),(400,500),(500,500)):
                with patch.object(provider.client,'request',return_value=httpx.Response(remote_status)):
                    with self.assertRaises(HTTPException) as error:provider.request('POST','orders')
                    self.assertEqual(error.exception.status_code,expected)
        provider.client.close()

    def test_local_test_readiness_does_not_bypass_production_requirements(self):
        settings=runtime_settings.ProductSettings(checkout_enabled=True)
        cfg=replace(runtime_settings.config,environment='development',razorpay_key='rzp_test_fixture',razorpay_secret='fixture',razorpay_webhook_secret='',razorpay_allow_test_checkout=False)
        with patch.object(runtime_settings,'config',cfg):self.assertTrue(runtime_settings.checkout_ready(settings))
        with patch.object(runtime_settings,'config',replace(cfg,environment='production')):self.assertFalse(runtime_settings.checkout_ready(settings))
        with patch.object(runtime_settings,'config',replace(cfg,razorpay_key='rzp_live_fixture')):self.assertFalse(runtime_settings.checkout_ready(settings))

    def test_hosted_test_flag_never_bypasses_live_setup(self):
        settings=runtime_settings.ProductSettings(checkout_enabled=True)
        cfg=replace(runtime_settings.config,environment='production',razorpay_key='rzp_test_fixture',
            razorpay_secret='fixture',razorpay_webhook_secret='',razorpay_allow_test_checkout=True)
        with patch.object(runtime_settings,'config',cfg):self.assertTrue(runtime_settings.checkout_ready(settings))
        with patch.object(runtime_settings,'config',replace(cfg,razorpay_key='rzp_live_fixture')):
            self.assertFalse(runtime_settings.checkout_ready(settings))
            blockers=runtime_settings.checkout_blockers(settings)
            self.assertTrue(any('RAZORPAY_WEBHOOK_SECRET' in item for item in blockers))
            self.assertTrue(any('legal business name' in item for item in blockers))
            self.assertNotIn('fixture',' '.join(blockers))


if __name__=='__main__':unittest.main()
