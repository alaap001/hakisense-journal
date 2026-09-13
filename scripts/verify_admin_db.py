"""Rollback-only checks of real admin RLS. Never assigns a persistent administrator."""
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from backend.config import config

connection=psycopg.connect(config.migration_url,sslmode='require',connect_timeout=10)
try:
    with connection.cursor() as c:
        c.execute('SELECT version_num FROM journal.alembic_version')
        assert c.fetchone()[0]=='0008_pay_as_you_go'
        c.execute('SELECT code,credits FROM journal.ai_tasks ORDER BY code')
        assert dict(c.fetchall())=={'chat':2,'coach':5,'daily':3,'query':4,'summary':2,'trade_note':1}
        c.execute('SELECT count(*) FROM journal.ai_routes')
        assert c.fetchone()[0]==12
        c.execute("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='journal' AND c.relkind='r' AND c.relname<>'alembic_version' AND NOT(c.relrowsecurity AND c.relforcerowsecurity)")
        assert c.fetchone()[0]==0
        owner,support,ordinary=[str(uuid4()) for _ in range(3)]
        for user in (owner,support,ordinary):
            c.execute("INSERT INTO auth.users(id,email,aud,role,created_at,updated_at,email_confirmed_at) VALUES (%s,%s,'authenticated','authenticated',now(),now(),now())",(user,user+'@admin-verification.invalid'))
            c.execute("INSERT INTO journal.profiles(user_id,display_name,created_at) VALUES (%s,'Admin verification fixture',now())",(user,))
        c.execute("INSERT INTO journal.admin_members(user_id,role) VALUES (%s,'owner'),(%s,'support')",(owner,support))
        c.execute('SET LOCAL ROLE hakisense_admin')
        c.execute("SELECT set_config('app.actor_id',%s,true)",(ordinary,))
        c.execute('SELECT count(*) FROM journal.credit_packs')
        assert c.fetchone()[0]==0
        c.execute("UPDATE journal.ai_tasks SET credits=999 WHERE code='chat'")
        assert c.rowcount==0
        c.execute("SELECT set_config('app.actor_id',%s,true)",(support,))
        c.execute('SELECT count(*) FROM journal.credit_packs')
        assert c.fetchone()[0]>=4
        c.execute("UPDATE journal.ai_tasks SET credits=999 WHERE code='chat'")
        assert c.rowcount==0
        c.execute("SELECT set_config('app.actor_id',%s,true)",(owner,))
        c.execute("UPDATE journal.ai_tasks SET credits=2 WHERE code='chat'")
        assert c.rowcount==1
        c.execute('SELECT id,email FROM journal.user_directory WHERE id=%s',(ordinary,))
        assert str(c.fetchone()[0])==ordinary
        c.execute('SELECT id,status,model FROM journal.ai_jobs LIMIT 1')
        def denied(sql,args=None):
            c.execute('SAVEPOINT access_check')
            blocked=False
            try:c.execute(sql,args)
            except psycopg.Error:blocked=True
            c.execute('ROLLBACK TO SAVEPOINT access_check')
            assert blocked,'Expected privilege denial'
        denied('SELECT encrypted_password FROM auth.users LIMIT 1')
        denied('SELECT content FROM journal.messages LIMIT 1')
        denied('SELECT request FROM journal.ai_jobs LIMIT 1')
        denied("UPDATE journal.wallet_entries SET reason='cannot rewrite history'")
        denied("UPDATE journal.admin_audit SET reason='cannot rewrite history'")
        # Removing membership takes effect in the following statement, without a JWT refresh.
        c.execute('RESET ROLE')
        c.execute('UPDATE journal.admin_members SET active=false WHERE user_id=%s',(owner,))
        c.execute('SET LOCAL ROLE hakisense_admin')
        c.execute("UPDATE journal.ai_tasks SET credits=999 WHERE code='chat'")
        assert c.rowcount==0
        c.execute('SET LOCAL ROLE hakisense_api')
        c.execute("SELECT set_config('app.user_id',%s,true)",(ordinary,))
        denied("INSERT INTO journal.admin_members(user_id,role) VALUES (%s,'owner')",(ordinary,))
        denied("UPDATE journal.platform_config SET revision=999")
        print('Admin schema, reduced costs and 12 model routes verified.')
        print('Ordinary/support writes denied; owner edits permitted; revocation effective; passwords, prompts and history rewrites denied.')
finally:
    connection.rollback()
    connection.close()
print('All admin fixtures rolled back. No administrator was assigned.')
