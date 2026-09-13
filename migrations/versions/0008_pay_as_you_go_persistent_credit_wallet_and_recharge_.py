"""Persistent wallet, one-time recharges and linked playbooks. Retains legacy billing history."""
from alembic import op
import json
import sqlalchemy as sa

revision = '0008_pay_as_you_go'
down_revision = '0007_landing_pricing'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("SELECT key FROM journal.platform_config WHERE key='product' FOR UPDATE")
    op.execute("""DO $$ BEGIN
      IF EXISTS(SELECT 1 FROM journal.subscriptions WHERE provider_id IS NOT NULL AND status NOT IN ('cancelled','completed','expired','refunded','revoked'))
         OR EXISTS(SELECT 1 FROM journal.checkouts WHERE status IN ('creating','uncertain','ready'))
         OR EXISTS(SELECT 1 FROM journal.ai_jobs WHERE status IN ('queued','running'))
      THEN RAISE EXCEPTION 'Resolve existing mandates, checkouts and active AI jobs before PAYG cutover'; END IF;
    END $$""")
    op.execute("\nCREATE TABLE journal.credit_packs (\n\tcode VARCHAR(80) NOT NULL, \n\tname VARCHAR(100) NOT NULL, \n\tcredits INTEGER NOT NULL, \n\tamount_paise INTEGER NOT NULL, \n\tcurrency VARCHAR(3) NOT NULL, \n\tfirst_purchase_only BOOLEAN NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tsort_order INTEGER NOT NULL, \n\tPRIMARY KEY (code), \n\tCHECK (amount_paise > 0 AND credits > 0 AND currency = 'INR')\n)\n\n;\n\nCREATE TABLE journal.credit_wallets (\n\tuser_id UUID NOT NULL, \n\tfree_month VARCHAR(7) NOT NULL, \n\tfree_allocation INTEGER NOT NULL, \n\tfree_balance INTEGER NOT NULL, \n\tpurchased_balance INTEGER NOT NULL, \n\tbalance INTEGER NOT NULL, \n\tspent INTEGER NOT NULL, \n\trevision INTEGER NOT NULL, \n\tfirst_purchase_id VARCHAR, \n\tupdated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (user_id), \n\tCHECK (free_balance >= 0 AND free_allocation >= 0 AND spent >= 0 AND revision >= 0), \n\tCHECK (balance = free_balance + purchased_balance)\n)\n\n;\n\nCREATE TABLE journal.wallet_entries (\n\tid VARCHAR NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tevent_key VARCHAR(200) NOT NULL, \n\tamount INTEGER NOT NULL, \n\tfree_delta INTEGER NOT NULL, \n\tpurchased_delta INTEGER NOT NULL, \n\tbalance_after INTEGER NOT NULL, \n\treason VARCHAR(1000) NOT NULL, \n\tdetails JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tuser_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (user_id, event_key), \n\tUNIQUE (user_id, sequence), \n\tCHECK (amount = free_delta + purchased_delta)\n)\n\n;\nCREATE INDEX ix_journal_wallet_entries_user_id ON journal.wallet_entries (user_id);\n\nCREATE TABLE journal.credit_purchases (\n\tid VARCHAR NOT NULL, \n\tidempotency_key VARCHAR(100) NOT NULL, \n\tpack_code VARCHAR(80) NOT NULL, \n\tpack_name VARCHAR(100) NOT NULL, \n\tamount_paise INTEGER NOT NULL, \n\tcredits INTEGER NOT NULL, \n\tfirst_purchase_only BOOLEAN NOT NULL, \n\tprovider_id VARCHAR(100), \n\tpayment_id VARCHAR(100), \n\tpayment_url TEXT, \n\tstatus VARCHAR(30) NOT NULL, \n\tcredited INTEGER NOT NULL, \n\trefunded_paise INTEGER NOT NULL, \n\tdispute_id VARCHAR(100), \n\tdispute_status VARCHAR(30), \n\tsettlement_version INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tchecked_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tuser_id UUID NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (user_id, idempotency_key), \n\tCHECK (amount_paise > 0 AND credits > 0 AND credited >= 0 AND credited <= credits), \n\tUNIQUE (provider_id), \n\tUNIQUE (payment_id)\n)\n\n;\nCREATE INDEX ix_journal_credit_purchases_user_id ON journal.credit_purchases (user_id);\nCREATE INDEX ix_credit_purchases_pending ON journal.credit_purchases (status, checked_at);\n\nCREATE TABLE journal.purchase_index (\n\tid VARCHAR NOT NULL, \n\tuser_id UUID NOT NULL, \n\tprovider_id VARCHAR(100), \n\tpayment_id VARCHAR(100), \n\tchecked_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (provider_id), \n\tUNIQUE (payment_id)\n)\n\n;\nCREATE INDEX ix_journal_purchase_index_checked_at ON journal.purchase_index (checked_at);")
    user = "NULLIF(current_setting('app.user_id', true), '')::uuid"
    actor = "NULLIF(current_setting('app.actor_id', true), '')::uuid"
    staff = f"EXISTS (SELECT 1 FROM journal.admin_members m WHERE m.user_id={actor} AND m.active)"
    writer = f"EXISTS (SELECT 1 FROM journal.admin_members m WHERE m.user_id={actor} AND m.active AND m.role IN ('owner','admin'))"
    for table in ('credit_packs','credit_wallets','wallet_entries','credit_purchases','purchase_index'):
        op.execute(f'ALTER TABLE journal.{table} ENABLE ROW LEVEL SECURITY; ALTER TABLE journal.{table} FORCE ROW LEVEL SECURITY; REVOKE ALL ON journal.{table} FROM PUBLIC,anon,authenticated,service_role')
        if table in ('credit_wallets','wallet_entries','credit_purchases'):
            op.execute(f'ALTER TABLE journal.{table} ADD FOREIGN KEY(user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE')
            op.execute(f'CREATE POLICY tenant_read ON journal.{table} FOR SELECT TO hakisense_api USING(user_id=(SELECT {user}))')
            op.execute(f'CREATE POLICY tenant_insert ON journal.{table} FOR INSERT TO hakisense_api WITH CHECK(user_id=(SELECT {user}))')
            op.execute(f'GRANT SELECT,INSERT ON journal.{table} TO hakisense_api')
            if table!='wallet_entries':
                op.execute(f'CREATE POLICY tenant_update ON journal.{table} FOR UPDATE TO hakisense_api USING(user_id=(SELECT {user})) WITH CHECK(user_id=(SELECT {user})); GRANT UPDATE ON journal.{table} TO hakisense_api')
        elif table=='credit_packs':
            op.execute(f'CREATE POLICY catalog_read ON journal.{table} FOR SELECT TO hakisense_api USING(true); GRANT SELECT ON journal.{table} TO hakisense_api')
        else:
            op.execute(f'CREATE POLICY internal_routing ON journal.{table} FOR ALL TO hakisense_api USING(true) WITH CHECK(true); GRANT SELECT,INSERT,UPDATE ON journal.{table} TO hakisense_api')
        op.execute(f'CREATE POLICY admin_read ON journal.{table} FOR SELECT TO hakisense_admin USING({staff}); GRANT SELECT ON journal.{table} TO hakisense_admin')
        if table in ('credit_packs','credit_wallets','wallet_entries'):
            op.execute(f'CREATE POLICY admin_insert ON journal.{table} FOR INSERT TO hakisense_admin WITH CHECK({writer}); GRANT INSERT ON journal.{table} TO hakisense_admin')
            if table!='wallet_entries':
                op.execute(f'CREATE POLICY admin_update ON journal.{table} FOR UPDATE TO hakisense_admin USING({writer}) WITH CHECK({writer}); GRANT UPDATE ON journal.{table} TO hakisense_admin')
    op.execute("""
      ALTER TABLE journal.credit_purchases ADD UNIQUE(user_id,id);
      ALTER TABLE journal.credit_purchases ADD FOREIGN KEY(pack_code) REFERENCES journal.credit_packs(code);
      ALTER TABLE journal.purchase_index ADD FOREIGN KEY(user_id,id) REFERENCES journal.credit_purchases(user_id,id) ON DELETE CASCADE;
      CREATE UNIQUE INDEX one_pending_recharge ON journal.credit_purchases(user_id) WHERE status IN ('creating','uncertain','ready');
      CREATE INDEX ix_purchase_user_created ON journal.credit_purchases(user_id,created_at DESC);
      ALTER TABLE journal.records ADD UNIQUE(user_id,id);
      ALTER TABLE journal.trades ADD COLUMN playbook_id text;
      ALTER TABLE journal.trades ADD COLUMN playbook_snapshot json NOT NULL DEFAULT '{}';
      ALTER TABLE journal.trades ADD FOREIGN KEY(user_id,playbook_id) REFERENCES journal.records(user_id,id);
      CREATE INDEX ix_trades_playbook ON journal.trades(user_id,playbook_id) WHERE playbook_id IS NOT NULL;
      UPDATE journal.prices SET active=false;
      UPDATE journal.platform_config SET revision=revision+1 WHERE key='product';
    """)
    # Preserve existing AI costs/routes and custom settings. Only seed new product fields.
    bind=op.get_bind()
    defaults={'monthly_free_credits':50,'playbook_creation_credits':1,'advanced_credit_multiplier':3,'reference_credit_paise':100}
    row=bind.execute(sa.text("SELECT value FROM journal.platform_config WHERE key='product'")).scalar_one()
    value={**defaults,**row}
    bind.execute(sa.text("UPDATE journal.platform_config SET value=CAST(:value AS json) WHERE key='product'"),{'value':json.dumps(value)})
    packs=[('first_recharge','First recharge',50,2100,True,0),('starter_50','Starter',50,5000,False,1),('review_600','Review',600,19900,False,2),('deep_dive_4000','Deep dive',4000,50000,False,3)]
    for code,name,credits,amount,first,sort in packs:
        bind.execute(sa.text("INSERT INTO journal.credit_packs(code,name,credits,amount_paise,currency,first_purchase_only,active,sort_order) VALUES (:code,:name,:credits,:amount,'INR',:first,true,:sort)"),{'code':code,'name':name,'credits':credits,'amount':amount,'first':first,'sort':sort})
    # Freeze the opening balance at cutover; historical monthly ledgers remain immutable history.
    op.execute("""
      INSERT INTO journal.credit_wallets(user_id,free_month,free_allocation,free_balance,purchased_balance,balance,spent,revision,updated_at)
      SELECT user_id,month,allocation,0,balance,balance,0,1,now() FROM journal.wallets
      WHERE month=to_char(now() AT TIME ZONE 'Asia/Kolkata','YYYY-MM');
      INSERT INTO journal.wallet_entries(id,user_id,sequence,event_key,amount,free_delta,purchased_delta,balance_after,reason,details,created_at)
      SELECT gen_random_uuid()::text,user_id,1,'legacy-opening',balance,0,balance,balance,
        'Previous wallet balance carried forward',json_build_object('month',free_month),now() FROM journal.credit_wallets;
    """)

    op.execute("""
      UPDATE journal.credit_wallets w SET first_purchase_id=p.id FROM
        (SELECT DISTINCT ON (user_id) user_id,id FROM journal.payments ORDER BY user_id,created_at) p
        WHERE w.user_id=p.user_id;
    """)
    # Historical commercial records remain in the database, outside the active runtime surface.
    for table in ('plans','prices','subscriptions','wallets','credit_entries','checkouts','subscription_index','payments','access_grants'):
        op.execute(f'REVOKE ALL ON journal.{table} FROM hakisense_api,hakisense_admin')


def downgrade():
    raise RuntimeError('Money and purchase history require a forward migration. Automatic downgrade is disabled.')
