"""Private tenant schema, commercial catalog, durable jobs and RLS."""
from pathlib import Path
from alembic import op

revision = '0001_production'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Frozen SQL snapshot: later model edits do not alter an already released migration.
    sql = (Path(__file__).parents[1] / '0001_production.sql').read_text()
    # Send the DDL without client parameter interpolation (%I belongs to PostgreSQL format()).
    with op.get_bind().connection.driver_connection.cursor() as cursor:
        cursor.execute(sql, prepare=False)


def downgrade():
    raise RuntimeError('Refusing to destroy customer and billing data. Restore a verified backup or ship a forward migration.')
