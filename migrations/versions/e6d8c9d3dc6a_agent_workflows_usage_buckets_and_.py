"""Whole-workflow buckets, private agent receipts and durable progress events."""
from alembic import op

revision = 'e6d8c9d3dc6a'
down_revision = '0008_pay_as_you_go'
branch_labels = None
depends_on = None


def upgrade():
    # Freeze legacy jobs at their original price; deploy only after old workers have drained.
    op.execute("""DO $$ BEGIN
      IF EXISTS (SELECT 1 FROM journal.ai_jobs WHERE status IN ('queued','running'))
      THEN RAISE EXCEPTION 'Drain active AI jobs before deploying workflow pricing'; END IF;
    END $$""")
    op.execute("""
      ALTER TABLE journal.ai_jobs
        ADD COLUMN pricing_version varchar(40) NOT NULL DEFAULT 'legacy',
        ADD COLUMN max_credits integer NOT NULL DEFAULT 0,
        ADD COLUMN usage json NOT NULL DEFAULT '{}',
        ADD COLUMN checkpoint json NOT NULL DEFAULT '{}',
        ADD COLUMN pause json,
        ADD COLUMN revision integer NOT NULL DEFAULT 0,
        ADD COLUMN event_sequence integer NOT NULL DEFAULT 0,
        ADD COLUMN cancel_requested boolean NOT NULL DEFAULT false,
        ADD COLUMN heartbeat_at timestamptz;
      CREATE UNIQUE INDEX one_active_ai_workflow ON journal.ai_jobs(user_id)
        WHERE status IN ('queued','running','awaiting_input');
      CREATE INDEX ix_ai_jobs_user_created ON journal.ai_jobs(user_id,created_at DESC);
      CREATE INDEX ix_messages_user_thread_created ON journal.messages(user_id,thread_id,created_at DESC);
    """)
    op.execute('\nCREATE TABLE journal.ai_events (\n\tjob_id VARCHAR NOT NULL, \n\tsequence INTEGER NOT NULL, \n\tkind VARCHAR(40) NOT NULL, \n\tdata JSON NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tuser_id UUID NOT NULL, \n\tPRIMARY KEY (job_id, sequence), \n\tFOREIGN KEY(user_id, job_id) REFERENCES journal.ai_jobs (user_id, id) ON DELETE CASCADE\n)\n\n')
    op.execute('CREATE INDEX ix_journal_ai_events_user_id ON journal.ai_events (user_id)')
    op.execute('\nCREATE TABLE journal.ai_calls (\n\tjob_id VARCHAR NOT NULL, \n\tcall_key VARCHAR(100) NOT NULL, \n\tagent VARCHAR(40) NOT NULL, \n\tmodel VARCHAR(200) NOT NULL, \n\trequest_hash VARCHAR(64) NOT NULL, \n\tstatus VARCHAR(30) NOT NULL, \n\tgeneration_id VARCHAR(200), \n\tusage JSON NOT NULL, \n\tresponse TEXT, \n\tcreated_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tuser_id UUID NOT NULL, \n\tPRIMARY KEY (job_id, call_key), \n\tFOREIGN KEY(user_id, job_id) REFERENCES journal.ai_jobs (user_id, id) ON DELETE CASCADE\n)\n\n')
    op.execute('CREATE INDEX ix_journal_ai_calls_user_id ON journal.ai_calls (user_id)')
    for table in ('ai_events', 'ai_calls'):
        op.execute(f'ALTER TABLE journal.{table} ENABLE ROW LEVEL SECURITY; ALTER TABLE journal.{table} FORCE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON journal.{table} FROM PUBLIC,anon,authenticated,service_role,hakisense_admin')
        owner = "user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)"
        op.execute(f'CREATE POLICY tenant_read ON journal.{table} FOR SELECT TO hakisense_api USING ({owner})')
        op.execute(f'CREATE POLICY tenant_insert ON journal.{table} FOR INSERT TO hakisense_api WITH CHECK ({owner})')
        op.execute(f'GRANT SELECT,INSERT ON journal.{table} TO hakisense_api')
        if table == 'ai_calls':
            op.execute(f'CREATE POLICY tenant_update ON journal.{table} FOR UPDATE TO hakisense_api USING ({owner}) WITH CHECK ({owner}); GRANT UPDATE ON journal.{table} TO hakisense_api')
    op.execute("UPDATE journal.platform_config SET revision=revision+1 WHERE key='product'")


def downgrade():
    raise RuntimeError('Preserve AI and credit receipts. Use a forward migration.')
