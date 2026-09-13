"""Catalog preflight or bounded rollback-only wallet RLS checks. Never changes a real account."""
import sys
from pathlib import Path
from uuid import uuid4
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from backend.config import config


def run():
    conn=psycopg.connect(config.migration_url.replace('postgresql+psycopg://','postgresql://'),sslmode='require',connect_timeout=10)
    try:
        with conn.cursor() as c:
            c.execute('SELECT version_num FROM journal.alembic_version')
            version=c.fetchone()[0]
            if '--preflight' in sys.argv:
                c.execute("SELECT count(*) FROM journal.subscriptions WHERE provider_id IS NOT NULL AND status NOT IN ('cancelled','completed','expired','refunded','revoked')")
                subscriptions=c.fetchone()[0]
                c.execute("SELECT count(*) FROM journal.checkouts WHERE status IN ('creating','uncertain','ready')")
                pending=c.fetchone()[0]
                c.execute("SELECT count(*) FROM journal.ai_jobs WHERE status IN ('queued','running')")
                jobs=c.fetchone()[0]
                print({'revision':version,'legacy_mandates_to_review':subscriptions,'legacy_pending_checkouts':pending,'active_ai_jobs':jobs})
                if subscriptions or pending:raise RuntimeError('Review legacy mandates/checkouts before activating PAYG')
                return
            assert version=='0008_pay_as_you_go'
            c.execute('SELECT count(*) FROM journal.prices WHERE active')
            assert c.fetchone()[0]==0
            c.execute('SELECT code,credits,amount_paise FROM journal.credit_packs WHERE active ORDER BY sort_order')
            print('Active packs:',c.fetchall())
            c.execute("SELECT count(*) FROM journal.credit_wallets w LEFT JOIN (SELECT user_id,sum(amount) AS total,count(*) AS entries,sum(free_delta) AS free,sum(purchased_delta) AS purchased FROM journal.wallet_entries GROUP BY user_id) e ON e.user_id=w.user_id WHERE w.balance<>COALESCE(e.total,0) OR w.revision<>COALESCE(e.entries,0) OR w.free_balance<>COALESCE(e.free,0) OR w.purchased_balance<>COALESCE(e.purchased,0)")
            assert c.fetchone()[0]==0,'Wallet ledger mismatch'
            for table in ('credit_packs','credit_wallets','wallet_entries','credit_purchases','purchase_index'):
                c.execute('SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid=%s::regclass',('journal.'+table,))
                assert c.fetchone()==(True,True)
                c.execute("SELECT has_table_privilege('anon',%s,'SELECT'),has_table_privilege('authenticated',%s,'SELECT')",('journal.'+table,'journal.'+table))
                assert c.fetchone()==(False,False)
            a,b,staff=[str(uuid4()) for _ in range(3)]
            for user in (a,b,staff):
                c.execute("INSERT INTO auth.users(id,email,aud,role,created_at,updated_at,email_confirmed_at) VALUES (%s,%s,'authenticated','authenticated',now(),now(),now())",(user,user+'@wallet-verification.invalid'))
                c.execute("INSERT INTO journal.profiles(user_id,display_name,created_at) VALUES (%s,'Wallet verification fixture',now())",(user,))
            c.execute("INSERT INTO journal.admin_members(user_id,role) VALUES (%s,'support')",(staff,))
            c.execute('SET LOCAL ROLE hakisense_api')
            c.execute("SELECT set_config('app.user_id',%s,true)",(a,))
            c.execute("INSERT INTO journal.credit_wallets(user_id,free_month,free_allocation,free_balance,purchased_balance,balance,spent,revision,updated_at) VALUES (%s,'2026-09',50,50,0,50,0,1,now())",(a,))
            c.execute("INSERT INTO journal.wallet_entries(id,user_id,sequence,event_key,amount,free_delta,purchased_delta,balance_after,reason,details,created_at) VALUES (%s,%s,1,'fixture',50,50,0,50,'Fixture','{}',now())",(str(uuid4()),a))
            c.execute('SELECT balance FROM journal.credit_wallets')
            assert c.fetchall()==[(50,)]
            def denied(sql,args=None):
                c.execute('SAVEPOINT access_check')
                blocked=False
                try:c.execute(sql,args)
                except psycopg.Error:blocked=True
                c.execute('ROLLBACK TO SAVEPOINT access_check')
                assert blocked,'Expected privilege denial'
            denied("UPDATE journal.wallet_entries SET amount=999")
            denied('DELETE FROM journal.wallet_entries')
            denied("UPDATE journal.credit_packs SET credits=999")
            c.execute("SELECT set_config('app.user_id',%s,true)",(b,))
            c.execute('SELECT count(*) FROM journal.credit_wallets')
            assert c.fetchone()[0]==0
            c.execute('SELECT count(*) FROM journal.wallet_entries')
            assert c.fetchone()[0]==0
            c.execute('UPDATE journal.credit_wallets SET balance=0,purchased_balance=-50 WHERE user_id=%s',(a,))
            assert c.rowcount==0
            c.execute('SET LOCAL ROLE hakisense_admin')
            c.execute("SELECT set_config('app.actor_id',%s,true)",(staff,))
            c.execute('SELECT count(*) FROM journal.credit_packs')
            assert c.fetchone()[0]>=4
            c.execute('UPDATE journal.credit_packs SET credits=999')
            assert c.rowcount==0
            denied("UPDATE journal.wallet_entries SET reason='rewrite'")
            print('Wallet sums, RLS isolation, append-only permissions and read-only support verified. All fixtures rolled back.')
    finally:
        conn.rollback();conn.close()

if __name__=='__main__':
    try:run()
    except Exception as exc:
        print('Verification failed:',type(exc).__name__)
        raise SystemExit(1)
