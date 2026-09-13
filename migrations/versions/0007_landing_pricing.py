"""New public pricing offers and separately advertised upcoming plan features."""
from alembic import op

revision = '0007_landing_pricing'
down_revision = '0006_user_directory'
branch_labels = None
depends_on = None


def upgrade():
    # Serialize catalog changes with the administrator; retain historical price records.
    op.execute("SELECT key FROM journal.platform_config WHERE key = 'product' FOR UPDATE")
    op.execute("""
      ALTER TABLE journal.plans ADD COLUMN upcoming_features jsonb NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(upcoming_features) = 'array');
      UPDATE journal.plans SET upcoming_features = '["deep_stock_research"]'::jsonb WHERE code = 'advanced';
      UPDATE journal.prices SET active = false
        WHERE (plan_code IN ('pro','advanced') AND interval = 'year')
           OR (plan_code = 'advanced' AND interval = 'month');
      INSERT INTO journal.prices (code,plan_code,interval,amount_paise,currency,tax_inclusive,active)
      VALUES ('pro_annual_202609','pro','year',189900,'INR',true,true),
             ('advanced_monthly','advanced','month',150000,'INR',true,true),
             ('advanced_annual_202609','advanced','year',760000,'INR',true,true);
      UPDATE journal.platform_config SET revision = revision + 1 WHERE key = 'product';
    """)


def downgrade():
    raise RuntimeError('Keep historical subscription terms intact. Use a forward migration to change offers.')
