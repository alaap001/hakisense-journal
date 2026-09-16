"""Exercise the tour with the real restricted PostgreSQL role; roll every fixture back."""
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from backend.config import config
from backend.db import make_engine, TenantSession, get_setting
from backend.entitlements import provision
from backend.onboarding import state, transition, TourAction

assert config.migration_url.startswith(('postgresql://', 'postgresql+psycopg://')), 'A PostgreSQL migration connection is required.'
engine = make_engine(config.migration_url)
a, b = str(uuid4()), str(uuid4())
try:
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            for user in (a, b):
                connection.execute(text("INSERT INTO auth.users(id,email,aud,role,created_at,updated_at) VALUES (:id,:email,'authenticated','authenticated',now(),now())"), {'id':user,'email':user+'@tour-verification.invalid'})
            connection.execute(text('SET LOCAL ROLE hakisense_api'))
            assert connection.execute(text('SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user')).one() == (False, False)
            for user in (a, b):
                connection.execute(text("SELECT set_config('app.user_id',:user,true)"), {'user':user})
                with TenantSession(bind=connection, info={'user_id':user}, join_transaction_mode='create_savepoint') as db:
                    provision(db, 'Temporary tour verification')
                    assert state(db)['status'] == 'pending'
                    saved = transition(db, TourAction(version=1, revision=0, action='skip'))
                    assert saved['status'] == 'skipped'
                    db.commit()
                # Reload through a separate ORM session, not an identity-map cache.
                with TenantSession(bind=connection, info={'user_id':user}, join_transaction_mode='create_savepoint') as db:
                    assert state(db) == saved
                    assert get_setting(db, 'onboarding').user_id == user
            connection.execute(text("SELECT set_config('app.user_id',:user,true)"), {'user':b})
            assert connection.scalar(text("SELECT count(*) FROM journal.settings WHERE user_id=:user AND key='onboarding'"), {'user':a}) == 0
            assert connection.execute(text("UPDATE journal.settings SET value='{}' WHERE user_id=:user AND key='onboarding'"), {'user':a}).rowcount == 0
            savepoint = connection.begin_nested()
            rejected = False
            try:
                connection.execute(text("INSERT INTO journal.settings(user_id,key,value) VALUES (:user,'forbidden-tour-fixture','{}')"), {'user':a})
            except DBAPIError:
                rejected = True
            finally:
                savepoint.rollback()
            assert rejected, 'Cross-user insert must fail under RLS.'
            print('PostgreSQL: provision, save/reload, tenant reads/writes and RLS passed.')
        finally:
            transaction.rollback()
    print('All temporary users and tour records rolled back. No customer records changed.')
finally:
    engine.dispose()
