"""Read-only check of the deployed catalog migration. No user or provider calls."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import psycopg
from backend.config import config

with psycopg.connect(config.migration_url.replace('postgresql+psycopg://','postgresql://'),sslmode='require',connect_timeout=10) as conn:
    with conn.cursor() as cur:
        cur.execute('SET TRANSACTION READ ONLY')
        cur.execute('SELECT version_num FROM journal.alembic_version')
        assert cur.fetchone()[0] == '0008_pay_as_you_go'
        cur.execute('SELECT code,credits,amount_paise FROM journal.credit_packs WHERE active ORDER BY sort_order')
        offers=cur.fetchall()
        assert all(credits>0 and amount>0 for _,credits,amount in offers)
        cur.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='journal.credit_packs'::regclass")
        assert cur.fetchone()==(True,True)
        print('Current backend recharge catalog:',offers)
print('Credit catalog verified without changing users or provider state.')
