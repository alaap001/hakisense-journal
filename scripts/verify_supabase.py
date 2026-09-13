"""One bounded Postgres check. Fixture rows and auth users are rolled back, never committed."""
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from backend.config import config
from backend.db import database
from sqlalchemy import text

with database(system=True) as db:
    role = db.execute(text('SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user')).one()
    assert role == ('hakisense_api', False, False), role
    assert db.scalar(text('SELECT count(*) FROM journal.credit_packs')) >= 4
    print('Restricted runtime connection and backend catalog: passed')

connection = psycopg.connect(config.migration_url, connect_timeout=10, sslmode='require')
try:
    with connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='journal' AND c.relkind='r' AND c.relname<>'alembic_version' AND NOT (c.relrowsecurity AND c.relforcerowsecurity)")
        assert cursor.fetchone()[0] == 0
        a, b = str(uuid4()), str(uuid4())
        # Direct SQL fixtures do not invoke signup or send email; the outer transaction always rolls back.
        for user in (a, b):
            cursor.execute("INSERT INTO auth.users(id, email, aud, role, created_at, updated_at) VALUES (%s, %s, 'authenticated', 'authenticated', now(), now())", (user, user+'@verification.invalid'))
            cursor.execute("INSERT INTO journal.profiles(user_id,display_name,created_at) VALUES (%s,'Temporary verification',now())", (user,))
        cursor.execute('SET LOCAL ROLE hakisense_api')
        cursor.execute("SELECT set_config('app.user_id',%s,true)", (a,))
        cursor.execute("INSERT INTO journal.accounts(id,user_id,name,broker,currency,initial_balance,color,is_demo) VALUES ('verification-account',%s,'Verification','Manual','INR',0,'#a6d96a',false)", (a,))
        cursor.execute('SELECT count(*) FROM journal.accounts')
        assert cursor.fetchone()[0] == 1
        cursor.execute("SELECT set_config('app.user_id',%s,true)", (b,))
        cursor.execute("SELECT count(*) FROM journal.accounts WHERE id='verification-account'")
        assert cursor.fetchone()[0] == 0
        cursor.execute("UPDATE journal.accounts SET name='must not change' WHERE id='verification-account'")
        assert cursor.rowcount == 0
        checks = [
            ("INSERT INTO journal.accounts(id,user_id,name,broker,currency,initial_balance,color,is_demo) VALUES ('wrong-owner',%s,'No','Manual','INR',0,'#a6d96a',false)", (a,)),
            ("UPDATE journal.credit_packs SET credits=999999", None),
            ("UPDATE journal.wallet_entries SET amount=999999", None),
        ]
        for statement, parameters in checks:
            cursor.execute('SAVEPOINT rejection_check')
            rejected = False
            try:
                cursor.execute(statement, parameters)
            except psycopg.Error:
                rejected = True
            cursor.execute('ROLLBACK TO SAVEPOINT rejection_check')
            assert rejected, 'Expected ownership/privilege rejection'
        cursor.execute("SELECT set_config('app.user_id','',true)")
        cursor.execute('SELECT count(*) FROM journal.accounts')
        assert cursor.fetchone()[0] == 0
        cursor.execute('RESET ROLE')
        cursor.execute("SELECT has_schema_privilege('anon','journal','USAGE'),has_schema_privilege('authenticated','journal','USAGE')")
        assert cursor.fetchone() == (False, False)
        print('Live RLS: cross-user reads/updates/inserts denied; prices and ledger immutable to runtime; browser roles denied')
finally:
    connection.rollback()
    connection.close()
print('All live database checks passed; fixture data rolled back.')
