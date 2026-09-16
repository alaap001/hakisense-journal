"""Rollback-only checkout regression under the real PostgreSQL API role.

Uses MIGRATION_DATABASE_URL to insert temporary fixture identities, then runs
checkout as hakisense_api. All provider calls are mocked; no charge is created.
The outer transaction rolls back every fixture, purchase and wallet entry.
"""
import hashlib
import hmac
import sys
from contextlib import contextmanager, ExitStack
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from backend.config import config
from backend import db as store, payments
from backend.auth import require_user, Identity
from backend.main import app
from backend.wallet import get_wallet


def run():
    engine=store.make_engine(config.migration_url)
    actor,other=str(uuid4()),str(uuid4())
    order={}
    try:
        with engine.connect() as connection:
            outer=connection.begin()
            try:
                for user in (actor,other):
                    connection.execute(text("INSERT INTO auth.users(id,email,aud,role,created_at,updated_at,email_confirmed_at) VALUES (:id,:email,'authenticated','authenticated',now(),now(),now())"),
                        {'id':user,'email':user+'@checkout-verification.invalid'})
                    connection.execute(text("INSERT INTO journal.profiles(user_id,display_name,created_at) VALUES (:id,'Checkout verification fixture',now())"),{'id':user})
                connection.execute(text('SET LOCAL ROLE hakisense_api'))
                access=connection.execute(text("SELECT current_user,has_table_privilege(current_user,'journal.credit_packs','SELECT'),has_table_privilege(current_user,'journal.credit_packs','UPDATE')")).one()
                assert tuple(access)==('hakisense_api',True,False), 'Expected restricted catalog permissions'

                @contextmanager
                def database(user_id=None,system=False):
                    with store.Session(bind=connection,info={'user_id':user_id},join_transaction_mode='create_savepoint') as db:
                        try:
                            db.execute(text("SELECT set_config('app.user_id',:id,true)"),{'id':user_id or ''})
                            yield db
                            db.commit()
                        except Exception:
                            db.rollback()
                            raise

                with database(actor) as db:
                    pack=db.scalar(select(store.CreditPack).where(store.CreditPack.active.is_(True),store.CreditPack.first_purchase_only.is_(True)))
                    assert pack, 'An active introductory pack is required for this check'
                    before=get_wallet(db).balance
                payment={'id':'pay_db_fixture','order_id':'order_db_fixture','amount':pack.amount_paise,
                    'currency':'INR','status':'captured','amount_refunded':0}

                def create_order(purchase):
                    order.update(id='order_db_fixture',receipt=purchase.id,notes={'hakisense_purchase':purchase.id},
                        amount=purchase.amount_paise,currency='INR',amount_paid=0,status='created')
                    return dict(order)

                with ExitStack() as stack:
                    stack.enter_context(patch.dict(app.dependency_overrides,{require_user:lambda:Identity(actor,'fixture@example.invalid','Fixture')}))
                    stack.enter_context(patch('backend.recharges.database',database))
                    stack.enter_context(patch('backend.recharges.checkout_ready',return_value=True))
                    stack.enter_context(patch.object(payments,'config',replace(config,razorpay_secret='db-fixture-secret')))
                    creation=stack.enter_context(patch.object(payments.provider,'create_order',side_effect=create_order))
                    stack.enter_context(patch.object(payments.provider,'order',side_effect=lambda _:dict(order)))
                    stack.enter_context(patch.object(payments.provider,'order_payments',side_effect=lambda _:[payment] if order['amount_paid'] else []))
                    stack.enter_context(patch.object(payments.provider,'payment',return_value=payment))
                    client=stack.enter_context(TestClient(app))
                    payload={'pack_code':pack.code,'expected_amount_paise':pack.amount_paise,'expected_credits':pack.credits}
                    for _ in range(2):
                        response=client.post('/api/billing/create-order',json=payload,headers={'Idempotency-Key':'db-fixture-checkout'})
                        assert response.status_code==200, (response.status_code,response.text)
                        assert response.json()['order_id']==order['id']
                    assert creation.call_count==1
                    order.update(amount_paid=pack.amount_paise,status='paid')
                    signature=hmac.new(b'db-fixture-secret',b'order_db_fixture|pay_db_fixture',hashlib.sha256).hexdigest()
                    for _ in range(2):
                        response=client.post('/api/billing/verify-payment',json={'razorpay_order_id':order['id'],
                            'razorpay_payment_id':payment['id'],'razorpay_signature':signature})
                        assert response.status_code==200, (response.status_code,response.text)
                        assert response.json()['success']
                    with database(actor) as db:assert get_wallet(db).balance==before+pack.credits
                    with database(other) as db:
                        assert db.scalar(select(store.CreditPurchase).where(store.CreditPurchase.provider_id==order['id'])) is None
                print('PostgreSQL checkout: create/retry HTTP 200, signed verification HTTP 200, credits granted once, tenant isolation and read-only catalog permissions passed.')
            finally:
                outer.rollback()
                print('All temporary database fixtures rolled back. No Razorpay calls or charges.')
    finally:
        engine.dispose()


if __name__=='__main__':run()
