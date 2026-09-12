"""Expose only approved Auth directory columns through an invoker-rights view."""
from alembic import op
revision='0005_admin_directory'
down_revision='0004_credit_buckets'
branch_labels=None
depends_on=None


def upgrade():
    # Supabase owns auth's schema ACL and does not delegate its GRANT option.
    # An invoker-rights view resolves the relation at creation while still enforcing
    # the caller's limited column privileges. It never elevates to the view owner.
    op.execute("""
    CREATE VIEW journal.auth_directory WITH (security_invoker=true, security_barrier=true) AS
      SELECT id,email,created_at,last_sign_in_at,email_confirmed_at FROM auth.users
      WHERE EXISTS (SELECT 1 FROM journal.admin_members m
        WHERE m.user_id=NULLIF(current_setting('app.actor_id',true),'')::uuid AND m.active);
    REVOKE ALL ON journal.auth_directory FROM PUBLIC,anon,authenticated,service_role;
    GRANT SELECT ON journal.auth_directory TO hakisense_admin;
    """)


def downgrade():
    op.execute('DROP VIEW journal.auth_directory')
