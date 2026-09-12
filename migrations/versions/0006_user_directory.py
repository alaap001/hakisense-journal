"""Synchronize a safe account directory without granting application access to Auth tables."""
from alembic import op
revision='0006_user_directory'
down_revision='0005_admin_directory'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""
    DROP VIEW journal.auth_directory;
    REVOKE SELECT(id,email,created_at,last_sign_in_at,email_confirmed_at) ON auth.users FROM hakisense_admin;
    CREATE TABLE journal.user_directory (
      id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
      email text, created_at timestamptz, last_sign_in_at timestamptz, email_confirmed_at timestamptz);
    CREATE INDEX ix_directory_created ON journal.user_directory(created_at DESC,id);
    ALTER TABLE journal.user_directory ENABLE ROW LEVEL SECURITY;
    ALTER TABLE journal.user_directory FORCE ROW LEVEL SECURITY;
    REVOKE ALL ON journal.user_directory FROM PUBLIC,anon,authenticated,service_role;
    GRANT SELECT ON journal.user_directory TO hakisense_admin;
    CREATE POLICY directory_staff ON journal.user_directory FOR SELECT TO hakisense_admin USING (
      EXISTS(SELECT 1 FROM journal.admin_members m
        WHERE m.user_id=NULLIF(current_setting('app.actor_id',true),'')::uuid AND m.active));
    GRANT USAGE ON SCHEMA journal TO supabase_auth_admin;
    GRANT SELECT,INSERT,UPDATE ON journal.user_directory TO supabase_auth_admin;
    CREATE POLICY auth_directory_sync ON journal.user_directory FOR ALL TO supabase_auth_admin USING(true) WITH CHECK(true);
    CREATE FUNCTION journal.sync_user_directory() RETURNS trigger
    LANGUAGE plpgsql SECURITY INVOKER SET search_path='' AS $$
    BEGIN
      INSERT INTO journal.user_directory(id,email,created_at,last_sign_in_at,email_confirmed_at)
      VALUES(NEW.id,NEW.email,NEW.created_at,NEW.last_sign_in_at,NEW.email_confirmed_at)
      ON CONFLICT(id) DO UPDATE SET email=EXCLUDED.email,created_at=EXCLUDED.created_at,
        last_sign_in_at=EXCLUDED.last_sign_in_at,email_confirmed_at=EXCLUDED.email_confirmed_at;
      RETURN NEW;
    END;
    $$;
    REVOKE ALL ON FUNCTION journal.sync_user_directory() FROM PUBLIC,anon,authenticated,service_role,hakisense_admin,hakisense_api;
    GRANT EXECUTE ON FUNCTION journal.sync_user_directory() TO supabase_auth_admin;
    CREATE TRIGGER hakisense_user_directory_sync AFTER INSERT OR UPDATE OF email,email_confirmed_at,last_sign_in_at
      ON auth.users FOR EACH ROW EXECUTE FUNCTION journal.sync_user_directory();
    INSERT INTO journal.user_directory(id,email,created_at,last_sign_in_at,email_confirmed_at)
      SELECT id,email,created_at,last_sign_in_at,email_confirmed_at FROM auth.users;
    """)


def downgrade():
    raise RuntimeError('Auth directory synchronization requires a reviewed forward migration.')
