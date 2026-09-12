"""Bounded checks for the production money and isolation boundaries. No provider calls."""
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import patch

_tmp = tempfile.TemporaryDirectory(prefix='hakisense-check-')
os.environ['APP_ENV'] = 'test'
os.environ['DATABASE_URL'] = 'sqlite:///' + _tmp.name + '/isolated.db'
os.environ['OPENROUTER_API_KEY'] = 'test-key-never-sent'
os.environ['CHECKOUT_ENABLED'] = 'false'

from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import select, func
from backend import db as store
from backend.main import app
from backend.auth import require_user, Identity
from backend.catalog import PLANS, PRICES, TASKS
from backend.config import AI_MODELS
from backend.runtime_settings import defaults
from backend.entitlements import provision, snapshot, consume_trades, wallet
from backend.jobs import enqueue, finish
from backend.schemas import AIRequest, TradeInput
from backend.analytics import enrich, apply_filters, group_rows
from backend.markets import IST, month_key
from backend.billing import apply_verified, verify_invoice, process_event


class ProductionCore(unittest.TestCase):
    def setUp(self):
        store.Base.metadata.drop_all(store.engine)
        store.init_db()
        with store.Session() as db:
            db.add_all(store.Plan(**p) for p in PLANS)
            db.add_all(store.Price(**p) for p in PRICES)
            db.add_all(store.AITask(**p) for p in TASKS)
            db.add(store.PlatformConfig(key='product',value=defaults(),revision=1))
            db.add_all(store.AIModel(id=m,name=m) for m in AI_MODELS['available'])
            db.flush()
            db.add_all(store.AIRoute(task_code=t['code'],tier=tier,model_id=AI_MODELS[tier]) for t in TASKS for tier in ('standard','advanced'))
            db.commit()
        self.a, self.b = str(uuid4()), str(uuid4())
        self.actor = self.a
        app.dependency_overrides[require_user] = lambda: Identity(self.actor, 'fixture@example.invalid', 'Fixture')
        self.client = TestClient(app)
        self.work = self.client.get('/api/workspace').json()
        self.account = self.work['accounts'][0]['id']

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()

    def trade(self, **changes):
        return {'account_id': self.account, 'symbol': 'RELIANCE', 'asset_type': 'Stocks', 'exchange': 'NSE', 'segment': 'Equity',
                'entry_price': 100, 'exit_price': 110, 'quantity': 10, 'entry_time': '2026-09-10T09:15:00', 'exit_time': '2026-09-10T10:15:00',
                'commission': 2, 'fees': 1, **changes}

    def test_auth_and_removed_local_endpoints(self):
        app.dependency_overrides.clear()
        self.assertEqual(self.client.get('/api/workspace').status_code, 401)
        self.assertEqual(self.client.get('/api/trades', headers={'Authorization': 'Bearer forged'}).status_code, 401)
        self.assertIn(self.client.post('/api/settings/openrouter', json={'api_key': 'x'}).status_code, (404, 405))
        self.assertIn(self.client.post('/api/backup/restore', json={}).status_code, (404, 405))

    def test_user_isolation_for_read_write_and_export(self):
        created = self.client.post('/api/trades', json=self.trade())
        self.assertEqual(created.status_code, 200, created.text)
        self.assertEqual(created.json()['net_pnl'], 97)
        trade_id = created.json()['id']
        self.actor = self.b
        self.assertEqual(self.client.get('/api/workspace').status_code, 200)
        self.assertEqual(self.client.get('/api/trades').json(), [])
        self.assertEqual(self.client.put('/api/trades/' + trade_id, json=self.trade()).status_code, 400)
        self.assertEqual(self.client.delete('/api/trades/' + trade_id).status_code, 404)
        self.assertNotIn(trade_id, self.client.get('/api/backup').text)

    def test_free_trade_limit_is_atomic_and_deletion_does_not_refund(self):
        payload = {'account_id': self.account, 'mapping': {}, 'rows': [{} for _ in range(101)], 'defaults': self.trade()}
        # Unique symbols avoid import deduplication, and one oversized batch must commit zero.
        payload['mapping'] = {'symbol': 'symbol'}
        payload['rows'] = [{'symbol': 'TEST' + str(i)} for i in range(101)]
        response = self.client.post('/api/import/commit', json=payload)
        self.assertEqual(response.status_code, 402, response.text)
        self.assertEqual(self.client.get('/api/trades').json(), [])
        payload['rows'] = payload['rows'][:100]
        result = self.client.post('/api/import/commit', json=payload)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['imported'], 100)
        rows = self.client.get('/api/trades').json()
        self.client.delete('/api/trades/' + rows[0]['id'])
        self.assertEqual(self.client.post('/api/trades', json=self.trade()).status_code, 402)
        self.assertEqual(self.client.get('/api/billing/me').json()['trades']['used'], 100)

    def test_credit_reservation_idempotency_and_refund_once(self):
        payload = {'message': 'Review my journal', 'mode': 'chat', 'expected_credits': 2}
        headers = {'Idempotency-Key': 'same-request-123'}
        stale = self.client.post('/api/ai/query', json={**payload, 'expected_credits': 1}, headers=headers)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'], 50)
        first = self.client.post('/api/ai/query', json=payload, headers=headers)
        self.assertEqual(first.status_code, 202, first.text)
        repeated = self.client.post('/api/ai/query', json=payload, headers=headers)
        self.assertEqual(first.json()['id'], repeated.json()['id'])
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'], 48)
        changed = self.client.post('/api/ai/query', json={**payload, 'message': 'Different'}, headers=headers)
        self.assertEqual(changed.status_code, 409)
        finish(self.a, first.json()['id'], error='Fixture failure')
        finish(self.a, first.json()['id'], error='Fixture failure')
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'], 50)
        with store.database(self.a) as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(store.CreditEntry).where(store.CreditEntry.event_key.like('refund:%'))), 1)

    def test_ai_result_saved_once_and_job_is_private(self):
        response = self.client.post('/api/ai/query', json={'message': 'Review', 'mode': 'trade_note', 'expected_credits': 1}, headers={'Idempotency-Key': 'success-request'})
        job_id = response.json()['id']
        result = {'thread_id': str(uuid4()), 'answer': 'Fixture result, no model called.', 'chart': None}
        finish(self.a, job_id, result)
        finish(self.a, job_id, result)
        self.assertEqual(len(self.client.get('/api/ai/threads/' + result['thread_id']).json()), 2)
        self.assertEqual(self.client.get('/api/billing/me').json()['credits']['remaining'], 49)
        self.actor = self.b
        self.client.get('/api/workspace')
        self.assertEqual(self.client.get('/api/ai/jobs/' + job_id).status_code, 404)
        self.assertEqual(self.client.get('/api/ai/threads/' + result['thread_id']).json(), [])

    def test_monthly_grants_and_india_day_boundary(self):
        before = datetime(2026, 9, 30, 18, 29, tzinfo=timezone.utc)
        after = datetime(2026, 9, 30, 18, 30, tzinfo=timezone.utc)
        self.assertEqual(month_key(before), '2026-09')
        self.assertEqual(month_key(after), '2026-10')
        with store.database(self.a) as db:
            first, _ = wallet(db, before)
            first.spent, first.balance = 45, 5
            second, _ = wallet(db, after)
            self.assertEqual(second.balance, 50)
        record = enrich(TradeInput(**self.trade(entry_time='2026-09-10T19:00:00Z', exit_time='2026-09-10T20:00:00Z')).model_dump())
        self.assertEqual(record['pnl_date'], '2026-09-11')
        self.assertEqual(group_rows([record], 'hour')[0]['name'], '00:00')
        self.assertEqual(len(apply_filters([record], {'start': '2026-09-11', 'end': '2026-09-11'})), 1)

    def test_paid_features_cannot_be_unlocked_from_browser(self):
        for url in ('/api/simulator', '/api/records/playbook', '/api/records/saved_filter'):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.client.put('/api/settings/preferences', json={'data': {'plan': 'advanced', 'credits': 999999}})
        self.assertEqual(self.client.get('/api/billing/me').json()['plan']['code'], 'free')
        self.assertEqual(self.client.post('/api/billing/checkout', json={'price_code': 'pro_annual'}, headers={'Idempotency-Key': 'test-checkout'}).status_code, 503)

    def test_paid_invoice_and_refund_are_idempotent(self):
        now = int(datetime.now(timezone.utc).timestamp())
        index = store.SubscriptionIndex(provider_id='sub_test', user_id=self.a, price_code='pro_annual', amount_paise=249900, provider_plan_id='plan_test', payment_url='https://rzp.io/test')
        invoice = {'id': 'inv_test', 'payment_id': 'pay_test', 'subscription_id': 'sub_test', 'status': 'paid', 'currency': 'INR', 'amount_paid': 249900, 'amount_due': 0, 'billing_start': now-100, 'billing_end': now+86400}
        payment = {'id': 'pay_test', 'invoice_id': 'inv_test', 'amount': 249900, 'currency': 'INR', 'status': 'captured', 'amount_refunded': 0}
        remote = {'id': 'sub_test', 'plan_id': 'plan_test', 'status': 'active'}
        with store.database(self.a) as db:
            apply_verified(db, index, remote, [(invoice, payment)])
            apply_verified(db, index, remote, [(invoice, payment)])
            self.assertEqual(snapshot(db)['credits']['remaining'], 1000)
            self.assertEqual(db.scalar(select(func.count()).select_from(store.Payment)), 1)
        with store.database(self.a) as db:
            apply_verified(db, index, {**remote, 'status': 'cancelled'}, [(invoice, payment)])
            self.assertEqual(snapshot(db)['plan']['code'], 'pro')
        with store.database(self.a) as db:
            apply_verified(db, index, remote, [(invoice, {**payment, 'amount_refunded': 249900})])
            self.assertEqual(snapshot(db)['plan']['code'], 'free')
            self.assertEqual(snapshot(db)['credits']['remaining'], 50)
        with self.assertRaises(HTTPException):
            verify_invoice(index, invoice, {**payment, 'amount': 1})

    def test_indian_contract_and_import_dates(self):
        from backend.importer import normalize_date
        parsed = TradeInput(**self.trade(entry_time=normalize_date('10/09/2026 09:15:00')))
        self.assertEqual(parsed.entry_time, '2026-09-10T03:45:00+00:00')
        with self.assertRaises(ValueError):
            TradeInput(**self.trade(asset_type='Options', segment='Index options', symbol='NIFTY', quantity=10, multiplier=100))
        valid = TradeInput(**self.trade(asset_type='Options', segment='Index options', symbol='NIFTY', quantity=20, lot_size=10, multiplier=1, expiry='2026-09-29', strike=25000, option_type='CE'))
        self.assertEqual(valid.lot_size, 10)  # Deliberately synthetic fixture, not an exchange contract master.

    def test_forged_webhook_is_rejected_before_provider_calls(self):
        from backend import billing
        with patch.object(billing, 'config', replace(billing.config, razorpay_webhook_secret='fixture-secret')):
            with patch.object(billing.provider, 'subscription') as network:
                with self.assertRaises(HTTPException) as failure:
                    process_event(b'{"event":"subscription.charged"}', 'forged', 'event-fixture')
                self.assertEqual(failure.exception.status_code, 400)
                network.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
