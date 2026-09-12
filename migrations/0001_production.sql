-- Frozen production schema, generated from the reviewed models. Apply through Alembic.
CREATE SCHEMA IF NOT EXISTS journal;

DO $$ BEGIN CREATE ROLE hakisense_api NOLOGIN NOSUPERUSER NOBYPASSRLS; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE ROLE hakisense_app LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END $$;

GRANT hakisense_api TO hakisense_app;

GRANT hakisense_api TO CURRENT_USER;

REVOKE ALL ON SCHEMA journal FROM PUBLIC;

GRANT USAGE ON SCHEMA journal TO hakisense_api;


CREATE TABLE journal.accounts (
	id VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	broker VARCHAR NOT NULL, 
	currency VARCHAR NOT NULL, 
	initial_balance NUMERIC(28, 8) NOT NULL, 
	color VARCHAR NOT NULL, 
	is_demo BOOLEAN NOT NULL, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, id)
)

;

CREATE INDEX ix_journal_accounts_user_id ON journal.accounts (user_id);

ALTER TABLE journal.accounts ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.accounts FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.accounts FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.accounts FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON journal.accounts TO hakisense_api;


CREATE TABLE journal.ai_jobs (
	id VARCHAR NOT NULL, 
	idempotency_key VARCHAR(100) NOT NULL, 
	request_hash VARCHAR(64) NOT NULL, 
	request JSON NOT NULL, 
	status VARCHAR NOT NULL, 
	task_code VARCHAR NOT NULL, 
	credits INTEGER NOT NULL, 
	month VARCHAR(7) NOT NULL, 
	model VARCHAR NOT NULL, 
	result JSON, 
	error VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, idempotency_key)
)

;

CREATE INDEX ix_journal_ai_jobs_user_id ON journal.ai_jobs (user_id);

ALTER TABLE journal.ai_jobs ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.ai_jobs FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.ai_jobs FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.ai_jobs FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE ON journal.ai_jobs TO hakisense_api;


CREATE TABLE journal.ai_tasks (
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	credits INTEGER NOT NULL, 
	enabled BOOLEAN NOT NULL, 
	PRIMARY KEY (code)
)

;

ALTER TABLE journal.ai_tasks ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.ai_tasks FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.ai_tasks FROM PUBLIC;

CREATE POLICY backend_only ON journal.ai_tasks FOR ALL TO hakisense_api USING (true) WITH CHECK (true);

GRANT SELECT ON journal.ai_tasks TO hakisense_api;


CREATE TABLE journal.checkouts (
	id VARCHAR NOT NULL, 
	idempotency_key VARCHAR NOT NULL, 
	price_code VARCHAR NOT NULL, 
	provider_id VARCHAR, 
	status VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, idempotency_key), 
	UNIQUE (provider_id)
)

;

CREATE INDEX ix_journal_checkouts_user_id ON journal.checkouts (user_id);

ALTER TABLE journal.checkouts ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.checkouts FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.checkouts FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.checkouts FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE ON journal.checkouts TO hakisense_api;


CREATE TABLE journal.credit_entries (
	id VARCHAR NOT NULL, 
	event_key VARCHAR NOT NULL, 
	month VARCHAR(7) NOT NULL, 
	amount INTEGER NOT NULL, 
	balance_after INTEGER NOT NULL, 
	reason VARCHAR NOT NULL, 
	job_id VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (user_id, event_key)
)

;

CREATE INDEX ix_journal_credit_entries_user_id ON journal.credit_entries (user_id);

ALTER TABLE journal.credit_entries ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.credit_entries FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.credit_entries FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.credit_entries FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT ON journal.credit_entries TO hakisense_api;


CREATE TABLE journal.job_queue (
	job_id VARCHAR NOT NULL, 
	user_id UUID NOT NULL, 
	claimed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (job_id)
)

;

ALTER TABLE journal.job_queue ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.job_queue FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.job_queue FROM PUBLIC;

CREATE POLICY backend_only ON journal.job_queue FOR ALL TO hakisense_api USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON journal.job_queue TO hakisense_api;


CREATE TABLE journal.messages (
	id VARCHAR NOT NULL, 
	thread_id VARCHAR NOT NULL, 
	role VARCHAR NOT NULL, 
	content TEXT NOT NULL, 
	metadata_json JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_journal_messages_thread_id ON journal.messages (thread_id);

CREATE INDEX ix_journal_messages_user_id ON journal.messages (user_id);

ALTER TABLE journal.messages ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.messages FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.messages FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.messages FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON journal.messages TO hakisense_api;


CREATE TABLE journal.payments (
	id VARCHAR NOT NULL, 
	provider_subscription_id VARCHAR NOT NULL, 
	amount_paise INTEGER NOT NULL, 
	status VARCHAR NOT NULL, 
	period_start TIMESTAMP WITH TIME ZONE NOT NULL, 
	period_end TIMESTAMP WITH TIME ZONE NOT NULL, 
	price_code VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_journal_payments_user_id ON journal.payments (user_id);

ALTER TABLE journal.payments ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.payments FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.payments FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.payments FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE ON journal.payments TO hakisense_api;


CREATE TABLE journal.plans (
	code VARCHAR NOT NULL, 
	name VARCHAR NOT NULL, 
	monthly_credits INTEGER NOT NULL, 
	trade_limit INTEGER, 
	model_tier VARCHAR NOT NULL, 
	features JSON NOT NULL, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (code)
)

;

ALTER TABLE journal.plans ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.plans FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.plans FROM PUBLIC;

CREATE POLICY backend_only ON journal.plans FOR ALL TO hakisense_api USING (true) WITH CHECK (true);

GRANT SELECT ON journal.plans TO hakisense_api;


CREATE TABLE journal.prices (
	code VARCHAR NOT NULL, 
	plan_code VARCHAR NOT NULL, 
	interval VARCHAR NOT NULL, 
	amount_paise INTEGER NOT NULL, 
	currency VARCHAR NOT NULL, 
	tax_inclusive BOOLEAN NOT NULL, 
	provider_plan_id VARCHAR, 
	active BOOLEAN NOT NULL, 
	PRIMARY KEY (code)
)

;

ALTER TABLE journal.prices ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.prices FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.prices FROM PUBLIC;

CREATE POLICY backend_only ON journal.prices FOR ALL TO hakisense_api USING (true) WITH CHECK (true);

GRANT SELECT ON journal.prices TO hakisense_api;


CREATE TABLE journal.profiles (
	user_id UUID NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id)
)

;

ALTER TABLE journal.profiles ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.profiles FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.profiles FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.profiles FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE ON journal.profiles TO hakisense_api;


CREATE TABLE journal.rate_buckets (
	key VARCHAR NOT NULL, 
	hits INTEGER NOT NULL, 
	expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
)

;

CREATE INDEX ix_journal_rate_buckets_expires_at ON journal.rate_buckets (expires_at);

ALTER TABLE journal.rate_buckets ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.rate_buckets FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.rate_buckets FROM PUBLIC;

CREATE POLICY backend_only ON journal.rate_buckets FOR ALL TO hakisense_api USING (true) WITH CHECK (true);

GRANT SELECT, INSERT, UPDATE, DELETE ON journal.rate_buckets TO hakisense_api;


CREATE TABLE journal.records (
	id VARCHAR NOT NULL, 
	kind VARCHAR NOT NULL, 
	data JSON NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id)
)

;

CREATE INDEX ix_journal_records_kind ON journal.records (kind);

CREATE INDEX ix_journal_records_user_id ON journal.records (user_id);

ALTER TABLE journal.records ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.records FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.records FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.records FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON journal.records TO hakisense_api;


CREATE TABLE journal.settings (
	user_id UUID NOT NULL, 
	key VARCHAR NOT NULL, 
	value JSON NOT NULL, 
	PRIMARY KEY (user_id, key)
)

;

ALTER TABLE journal.settings ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.settings FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.settings FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.settings FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON journal.settings TO hakisense_api;


CREATE TABLE journal.subscription_index (
	provider_id VARCHAR NOT NULL, 
	user_id UUID NOT NULL, 
	price_code VARCHAR NOT NULL, 
	amount_paise INTEGER NOT NULL, 
	provider_plan_id VARCHAR NOT NULL, 
	payment_url VARCHAR NOT NULL, 
	PRIMARY KEY (provider_id)
)

;

ALTER TABLE journal.subscription_index ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.subscription_index FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.subscription_index FROM PUBLIC;

CREATE POLICY backend_only ON journal.subscription_index FOR ALL TO hakisense_api USING (true) WITH CHECK (true);

GRANT SELECT, INSERT ON journal.subscription_index TO hakisense_api;


CREATE TABLE journal.subscriptions (
	user_id UUID NOT NULL, 
	plan_code VARCHAR NOT NULL, 
	price_code VARCHAR, 
	provider_id VARCHAR, 
	status VARCHAR NOT NULL, 
	paid_until TIMESTAMP WITH TIME ZONE, 
	last_payment_id VARCHAR, 
	cancel_at_period_end BOOLEAN NOT NULL, 
	updated_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (user_id), 
	UNIQUE (provider_id)
)

;

ALTER TABLE journal.subscriptions ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.subscriptions FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.subscriptions FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.subscriptions FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE ON journal.subscriptions TO hakisense_api;


CREATE TABLE journal.wallets (
	user_id UUID NOT NULL, 
	month VARCHAR(7) NOT NULL, 
	plan_code VARCHAR NOT NULL, 
	allocation INTEGER NOT NULL, 
	balance INTEGER NOT NULL, 
	spent INTEGER NOT NULL, 
	trade_count INTEGER NOT NULL, 
	PRIMARY KEY (user_id, month), 
	CHECK (balance >= 0), 
	CHECK (trade_count >= 0)
)

;

ALTER TABLE journal.wallets ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.wallets FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.wallets FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.wallets FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE ON journal.wallets TO hakisense_api;


CREATE TABLE journal.webhook_events (
	id VARCHAR NOT NULL, 
	event_type VARCHAR NOT NULL, 
	body_hash VARCHAR NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id)
)

;

ALTER TABLE journal.webhook_events ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.webhook_events FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.webhook_events FROM PUBLIC;

CREATE POLICY backend_only ON journal.webhook_events FOR ALL TO hakisense_api USING (true) WITH CHECK (true);

GRANT SELECT, INSERT ON journal.webhook_events TO hakisense_api;


CREATE TABLE journal.trades (
	exchange VARCHAR NOT NULL, 
	segment VARCHAR NOT NULL, 
	expiry VARCHAR, 
	strike NUMERIC(28, 8), 
	option_type VARCHAR, 
	lot_size INTEGER, 
	id VARCHAR NOT NULL, 
	account_id VARCHAR NOT NULL, 
	symbol VARCHAR NOT NULL, 
	asset_type VARCHAR NOT NULL, 
	side VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	entry_price NUMERIC(28, 8) NOT NULL, 
	exit_price NUMERIC(28, 8), 
	mark_price NUMERIC(28, 8), 
	quantity NUMERIC(28, 8) NOT NULL, 
	closed_quantity NUMERIC(28, 8) NOT NULL, 
	multiplier NUMERIC(28, 8) NOT NULL, 
	entry_time TIMESTAMP WITH TIME ZONE NOT NULL, 
	exit_time TIMESTAMP WITH TIME ZONE, 
	commission NUMERIC(28, 8) NOT NULL, 
	fees NUMERIC(28, 8) NOT NULL, 
	stop_loss NUMERIC(28, 8), 
	target_price NUMERIC(28, 8), 
	risk_amount NUMERIC(28, 8), 
	planned_entry NUMERIC(28, 8), 
	setup VARCHAR NOT NULL, 
	emotion VARCHAR NOT NULL, 
	rating INTEGER NOT NULL, 
	notes TEXT NOT NULL, 
	tags JSON NOT NULL, 
	attributes JSON NOT NULL, 
	mfe NUMERIC(28, 8), 
	mae NUMERIC(28, 8), 
	is_demo BOOLEAN NOT NULL, 
	fingerprint VARCHAR, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	user_id UUID NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id, account_id) REFERENCES journal.accounts (user_id, id), 
	UNIQUE (user_id, fingerprint)
)

;

CREATE INDEX ix_journal_trades_account_id ON journal.trades (account_id);

CREATE INDEX ix_journal_trades_entry_time ON journal.trades (entry_time);

CREATE INDEX ix_journal_trades_status ON journal.trades (status);

CREATE INDEX ix_journal_trades_symbol ON journal.trades (symbol);

CREATE INDEX ix_journal_trades_user_id ON journal.trades (user_id);

CREATE INDEX ix_trade_user_entry ON journal.trades (user_id, entry_time);

ALTER TABLE journal.trades ENABLE ROW LEVEL SECURITY;

ALTER TABLE journal.trades FORCE ROW LEVEL SECURITY;

REVOKE ALL ON journal.trades FROM PUBLIC;

CREATE POLICY tenant_isolation ON journal.trades FOR ALL TO hakisense_api USING (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid)) WITH CHECK (user_id = (SELECT NULLIF(current_setting('app.user_id', true), '')::uuid));

GRANT SELECT, INSERT, UPDATE, DELETE ON journal.trades TO hakisense_api;

ALTER TABLE journal.accounts ADD CONSTRAINT accounts_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.ai_jobs ADD CONSTRAINT ai_jobs_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.checkouts ADD CONSTRAINT checkouts_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.credit_entries ADD CONSTRAINT credit_entries_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.messages ADD CONSTRAINT messages_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.payments ADD CONSTRAINT payments_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.records ADD CONSTRAINT records_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.settings ADD CONSTRAINT settings_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.subscriptions ADD CONSTRAINT subscriptions_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.wallets ADD CONSTRAINT wallets_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

ALTER TABLE journal.trades ADD CONSTRAINT trades_owner_fk FOREIGN KEY (user_id) REFERENCES journal.profiles(user_id) ON DELETE CASCADE;

DO $$ BEGIN IF to_regclass('auth.users') IS NOT NULL THEN ALTER TABLE journal.profiles ADD CONSTRAINT profiles_auth_user_fk FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE; END IF; END $$;

DO $$ DECLARE r text; BEGIN FOREACH r IN ARRAY ARRAY['anon','authenticated','service_role'] LOOP IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname=r) THEN EXECUTE format('REVOKE ALL ON SCHEMA journal FROM %I',r); EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA journal FROM %I',r); END IF; END LOOP; END $$;

CREATE INDEX ix_queue_waiting ON journal.job_queue (created_at) WHERE claimed_at IS NULL;

CREATE INDEX ix_queue_claimed ON journal.job_queue (claimed_at) WHERE claimed_at IS NOT NULL;

CREATE INDEX ix_messages_user_thread_time ON journal.messages (user_id, thread_id, created_at);

CREATE INDEX ix_records_user_kind ON journal.records (user_id, kind);

CREATE INDEX ix_jobs_user_created ON journal.ai_jobs (user_id, created_at);

CREATE INDEX ix_payments_user_period ON journal.payments (user_id, period_end);

CREATE INDEX ix_subscription_index_user ON journal.subscription_index (user_id);

ALTER TABLE journal.plans ADD CONSTRAINT positive_plan_allowances CHECK (monthly_credits >= 0 AND (trade_limit IS NULL OR trade_limit >= 0));

ALTER TABLE journal.prices ADD CONSTRAINT positive_price CHECK (amount_paise > 0 AND currency = 'INR' AND interval IN ('month','year'));

ALTER TABLE journal.ai_tasks ADD CONSTRAINT positive_task_cost CHECK (credits > 0);

ALTER TABLE journal.wallets ADD CONSTRAINT nonnegative_spent CHECK (spent >= 0 AND allocation >= 0);

ALTER TABLE journal.trades ADD CONSTRAINT valid_trade_values CHECK (quantity > 0 AND entry_price > 0 AND multiplier > 0 AND closed_quantity >= 0 AND closed_quantity <= quantity AND commission >= 0 AND fees >= 0);

ALTER TABLE journal.trades ADD CONSTRAINT trade_time_order CHECK (exit_time IS NULL OR exit_time >= entry_time);

INSERT INTO journal.plans (code, name, monthly_credits, trade_limit, model_tier, features, active) VALUES ('free', 'Free', 50, 100, 'standard', '["journal", "analytics", "calendar", "notebook", "import_export", "accounts"]'::json, true);

INSERT INTO journal.plans (code, name, monthly_credits, trade_limit, model_tier, features, active) VALUES ('pro', 'Pro', 1000, NULL, 'standard', '["journal", "analytics", "calendar", "notebook", "import_export", "accounts", "replay", "playbooks", "saved_views"]'::json, true);

INSERT INTO journal.plans (code, name, monthly_credits, trade_limit, model_tier, features, active) VALUES ('advanced', 'Advanced', 8000, NULL, 'advanced', '["journal", "analytics", "calendar", "notebook", "import_export", "accounts", "replay", "playbooks", "saved_views"]'::json, true);

INSERT INTO journal.prices (code, plan_code, interval, amount_paise, currency, tax_inclusive, active) VALUES ('pro_monthly', 'pro', 'month', 40000, 'INR', true, true);

INSERT INTO journal.prices (code, plan_code, interval, amount_paise, currency, tax_inclusive, active) VALUES ('pro_annual', 'pro', 'year', 249900, 'INR', true, true);

INSERT INTO journal.prices (code, plan_code, interval, amount_paise, currency, tax_inclusive, active) VALUES ('advanced_annual', 'advanced', 'year', 899900, 'INR', true, true);

INSERT INTO journal.ai_tasks (code, name, credits, enabled) VALUES ('chat', 'Ask your journal', 5, true);

INSERT INTO journal.ai_tasks (code, name, credits, enabled) VALUES ('trade_note', 'Draft a trade review', 3, true);

INSERT INTO journal.ai_tasks (code, name, credits, enabled) VALUES ('summary', 'Performance summary', 5, true);

INSERT INTO journal.ai_tasks (code, name, credits, enabled) VALUES ('query', 'Query and chart', 10, true);

INSERT INTO journal.ai_tasks (code, name, credits, enabled) VALUES ('daily', 'Next-session preparation', 8, true);

INSERT INTO journal.ai_tasks (code, name, credits, enabled) VALUES ('coach', 'Detailed coaching review', 15, true);
