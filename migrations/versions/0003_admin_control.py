"""Protected administration, live model routing and lower task prices."""
from alembic import op
import json
import sqlalchemy as sa

revision = '0003_admin_control'
down_revision = '0002_queue_integrity'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('profiles', sa.Column('suspended', sa.Boolean(), nullable=False, server_default=sa.false()), schema='journal')
    op.add_column('wallets', sa.Column('adjustment', sa.Integer(), nullable=False, server_default='0'), schema='journal')
    op.add_column('ai_jobs', sa.Column('routing_config', sa.JSON(), nullable=False, server_default='{}'), schema='journal')
    op.execute("""
    CREATE TABLE journal.admin_members (
      user_id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
      role varchar(20) NOT NULL CHECK(role IN ('owner','admin','support')),
      active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE journal.admin_audit (
      id text PRIMARY KEY, actor_id uuid NOT NULL, actor_role text NOT NULL,
      action varchar(100) NOT NULL, target varchar(200) NOT NULL, reason varchar(1000) NOT NULL,
      before json NOT NULL DEFAULT '{}', after json NOT NULL DEFAULT '{}',
      idempotency_key varchar(100) NOT NULL, request_hash varchar(64) NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(actor_id,idempotency_key));
    CREATE INDEX ix_admin_audit_created ON journal.admin_audit(created_at DESC);
    CREATE TABLE journal.platform_config (
      key text PRIMARY KEY, value json NOT NULL DEFAULT '{}', revision integer NOT NULL DEFAULT 1,
      updated_at timestamptz NOT NULL DEFAULT now());
    CREATE TABLE journal.ai_models (
      id varchar(200) PRIMARY KEY, name varchar(100) NOT NULL, enabled boolean NOT NULL DEFAULT true);
    CREATE TABLE journal.ai_routes (
      task_code text NOT NULL REFERENCES journal.ai_tasks(code), tier text NOT NULL CHECK(tier IN ('standard','advanced')),
      model_id varchar(200) NOT NULL REFERENCES journal.ai_models(id), planner_model_id varchar(200) REFERENCES journal.ai_models(id),
      max_output_tokens integer NOT NULL DEFAULT 2400 CHECK(max_output_tokens BETWEEN 128 AND 16000),
      timeout_seconds integer NOT NULL DEFAULT 90 CHECK(timeout_seconds BETWEEN 10 AND 90),
      temperature numeric(4,2) NOT NULL DEFAULT 0.2 CHECK(temperature BETWEEN 0 AND 2),
      reasoning_effort varchar(20) NOT NULL DEFAULT 'low', instructions text NOT NULL DEFAULT '',
      enabled boolean NOT NULL DEFAULT true, PRIMARY KEY(task_code,tier));
    CREATE TABLE journal.access_grants (
      user_id uuid PRIMARY KEY REFERENCES journal.profiles(user_id) ON DELETE CASCADE,
      plan_code text NOT NULL REFERENCES journal.plans(code), expires_at timestamptz NOT NULL,
      reason varchar(1000) NOT NULL, updated_at timestamptz NOT NULL DEFAULT now());
    UPDATE journal.ai_tasks SET credits = ceil(credits::numeric / 3)::integer;
    DO $$ BEGIN CREATE ROLE hakisense_admin NOLOGIN NOSUPERUSER NOBYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    GRANT hakisense_admin TO hakisense_app;
    GRANT hakisense_admin TO CURRENT_USER;
    GRANT USAGE ON SCHEMA journal TO hakisense_admin;
    GRANT USAGE ON SCHEMA auth TO hakisense_admin;
    GRANT SELECT(id,email,created_at,last_sign_in_at,email_confirmed_at) ON auth.users TO hakisense_admin;
    """)
    actor = "NULLIF(current_setting('app.actor_id', true), '')::uuid"
    user = "NULLIF(current_setting('app.user_id', true), '')::uuid"
    staff = f"EXISTS (SELECT 1 FROM journal.admin_members m WHERE m.user_id = {actor} AND m.active)"
    writer = f"EXISTS (SELECT 1 FROM journal.admin_members m WHERE m.user_id = {actor} AND m.active AND m.role IN ('owner','admin'))"
    owner = f"EXISTS (SELECT 1 FROM journal.admin_members m WHERE m.user_id = {actor} AND m.active AND m.role = 'owner')"
    for table in ('admin_members','admin_audit','platform_config','ai_models','ai_routes','access_grants'):
        op.execute(f'ALTER TABLE journal.{table} ENABLE ROW LEVEL SECURITY; ALTER TABLE journal.{table} FORCE ROW LEVEL SECURITY; REVOKE ALL ON journal.{table} FROM PUBLIC,anon,authenticated,service_role')
    # Directory contains roles and IDs only. Its SELECT policy has no recursive membership lookup.
    op.execute(f"CREATE POLICY member_self ON journal.admin_members FOR SELECT TO hakisense_api USING(user_id = (SELECT {user})); GRANT SELECT ON journal.admin_members TO hakisense_api")
    op.execute('CREATE POLICY member_directory ON journal.admin_members FOR SELECT TO hakisense_admin USING(true); GRANT SELECT,INSERT,UPDATE ON journal.admin_members TO hakisense_admin')
    op.execute(f'CREATE POLICY member_create ON journal.admin_members FOR INSERT TO hakisense_admin WITH CHECK({owner})')
    op.execute(f'CREATE POLICY member_change ON journal.admin_members FOR UPDATE TO hakisense_admin USING({owner}) WITH CHECK({owner})')
    for table in ('platform_config','ai_models','ai_routes'):
        op.execute(f'GRANT SELECT ON journal.{table} TO hakisense_api; CREATE POLICY runtime_read ON journal.{table} FOR SELECT TO hakisense_api USING(true)')
    op.execute(f'GRANT SELECT ON journal.access_grants TO hakisense_api; CREATE POLICY grant_self ON journal.access_grants FOR SELECT TO hakisense_api USING(user_id=(SELECT {user}))')
    for table in ('plans','prices','ai_tasks','platform_config','ai_models','ai_routes','profiles','wallets','access_grants'):
        op.execute(f'GRANT SELECT,INSERT,UPDATE ON journal.{table} TO hakisense_admin')
        op.execute(f'CREATE POLICY admin_read ON journal.{table} FOR SELECT TO hakisense_admin USING({staff})')
        op.execute(f'CREATE POLICY admin_insert ON journal.{table} FOR INSERT TO hakisense_admin WITH CHECK({writer})')
        op.execute(f'CREATE POLICY admin_update ON journal.{table} FOR UPDATE TO hakisense_admin USING({writer}) WITH CHECK({writer})')
    for table in ('subscriptions','payments','checkouts','subscription_index'):
        op.execute(f'GRANT SELECT ON journal.{table} TO hakisense_admin; CREATE POLICY admin_read ON journal.{table} FOR SELECT TO hakisense_admin USING({staff})')
    # Job inputs/results and message text are deliberately not granted to administration.
    op.execute('GRANT SELECT(id,user_id,status,task_code,credits,model,created_at,finished_at,error) ON journal.ai_jobs TO hakisense_admin')
    op.execute(f'CREATE POLICY admin_job_metadata ON journal.ai_jobs FOR SELECT TO hakisense_admin USING({staff})')
    for table in ('credit_entries','admin_audit'):
        op.execute(f'GRANT SELECT,INSERT ON journal.{table} TO hakisense_admin; CREATE POLICY admin_read ON journal.{table} FOR SELECT TO hakisense_admin USING({staff})')
        extra = f' AND actor_id = {actor}' if table == 'admin_audit' else ''
        op.execute(f'CREATE POLICY admin_append ON journal.{table} FOR INSERT TO hakisense_admin WITH CHECK(({writer}){extra})')
    # All settings begin as bootstrap values. Subsequent runtime reads use these rows.
    from backend.config import AI_MODELS, config
    from backend.runtime_settings import defaults
    bind = op.get_bind()
    bind.execute(sa.text('INSERT INTO journal.platform_config(key,value) VALUES (:key,CAST(:value AS json))'), {'key':'product','value':json.dumps(defaults())})
    for model_id in AI_MODELS['available']:
        bind.execute(sa.text('INSERT INTO journal.ai_models(id,name) VALUES (:id,:name)'), {'id':model_id,'name':model_id})
    for task in bind.execute(sa.text('SELECT code FROM journal.ai_tasks')).scalars().all():
        for tier, model_id in [('standard',config.standard_model),('advanced',config.advanced_model)]:
            bind.execute(sa.text('INSERT INTO journal.ai_routes(task_code,tier,model_id) VALUES (:task,:tier,:model)'), {'task':task,'tier':tier,'model':model_id})


def downgrade():
    raise RuntimeError('Administrative history and routing snapshots require a reviewed forward migration; automatic downgrade is disabled.')
