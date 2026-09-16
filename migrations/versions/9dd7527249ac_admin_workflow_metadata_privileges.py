"""admin workflow metadata privileges

Revision ID: 9dd7527249ac
Revises: fd0774ab6ca4
Create Date: 2026-09-15 01:57:14.035390

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9dd7527249ac'
down_revision: Union[str, Sequence[str], None] = 'fd0774ab6ca4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The existing staff-membership RLS policy still applies. No journal payloads,
    # checkpoints, clarification text, events or specialist responses are granted.
    op.execute('GRANT SELECT(max_credits, usage, pricing_version, routing_config, cancel_requested, heartbeat_at) ON journal.ai_jobs TO hakisense_admin')


def downgrade() -> None:
    op.execute('REVOKE SELECT(max_credits, usage, pricing_version, routing_config, cancel_requested, heartbeat_at) ON journal.ai_jobs FROM hakisense_admin')
