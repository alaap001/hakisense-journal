"""Ensure queue routes cannot outlive or mismatch their tenant job."""
from alembic import op
revision='0002_queue_integrity'
down_revision='0001_production'
branch_labels=None
depends_on=None


def upgrade():
    op.create_unique_constraint('uq_jobs_owner_id', 'ai_jobs', ['user_id','id'], schema='journal')
    op.create_foreign_key('fk_queue_job_owner', 'job_queue', 'ai_jobs', ['user_id','job_id'], ['user_id','id'], source_schema='journal', referent_schema='journal', ondelete='CASCADE')
    op.create_foreign_key('fk_price_plan', 'prices', 'plans', ['plan_code'], ['code'], source_schema='journal', referent_schema='journal')
    op.create_foreign_key('fk_subscription_plan', 'subscriptions', 'plans', ['plan_code'], ['code'], source_schema='journal', referent_schema='journal')


def downgrade():
    op.drop_constraint('fk_subscription_plan','subscriptions',schema='journal',type_='foreignkey')
    op.drop_constraint('fk_price_plan','prices',schema='journal',type_='foreignkey')
    op.drop_constraint('fk_queue_job_owner','job_queue',schema='journal',type_='foreignkey')
    op.drop_constraint('uq_jobs_owner_id','ai_jobs',schema='journal',type_='unique')
