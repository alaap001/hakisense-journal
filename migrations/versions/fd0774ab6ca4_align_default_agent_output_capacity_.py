"""Replace the legacy 2,400-token default; the shared 16k workflow budget remains authoritative."""
from alembic import op

revision = 'fd0774ab6ca4'
down_revision = 'e6d8c9d3dc6a'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
      UPDATE journal.ai_routes SET max_output_tokens=16000 WHERE max_output_tokens=2400;
      UPDATE journal.platform_config SET revision=revision+1 WHERE key='product';
    """)


def downgrade():
    raise RuntimeError('Do not silently reduce active model capacity; change routes explicitly.')
