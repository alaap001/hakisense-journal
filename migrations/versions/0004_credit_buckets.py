"""Keep admin credits separate from plan usage through downgrades and refunds."""
from alembic import op
import sqlalchemy as sa
revision='0004_credit_buckets'
down_revision='0003_admin_control'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('wallets',sa.Column('bonus_spent',sa.Integer(),nullable=False,server_default='0'),schema='journal')
    op.add_column('ai_jobs',sa.Column('bonus_credits',sa.Integer(),nullable=False,server_default='0'),schema='journal')
    op.create_check_constraint('wallet_bonus_spent_nonnegative','wallets','bonus_spent >= 0 AND bonus_spent <= spent',schema='journal')
    op.create_check_constraint('job_bonus_credits_valid','ai_jobs','bonus_credits >= 0 AND bonus_credits <= credits',schema='journal')


def downgrade():
    raise RuntimeError('Credit settlement history requires a reviewed forward migration.')
