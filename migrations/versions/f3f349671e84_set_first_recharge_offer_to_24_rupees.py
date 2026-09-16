"""set first recharge offer to 24 rupees

Revision ID: f3f349671e84
Revises: 9dd7527249ac
Create Date: 2026-09-15 22:15:03.434098

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f3f349671e84'
down_revision: Union[str, Sequence[str], None] = '9dd7527249ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Only replace the original catalog default. Existing purchase/payment terms
    # and deliberate custom prices remain unchanged.
    op.execute("""
        UPDATE journal.credit_packs SET amount_paise=2400
        WHERE code='first_recharge' AND credits=50
          AND first_purchase_only=true AND amount_paise=2100
    """)
    op.execute("UPDATE journal.platform_config SET revision=revision+1 WHERE key='product'")


def downgrade() -> None:
    op.execute("""
        UPDATE journal.credit_packs SET amount_paise=2100
        WHERE code='first_recharge' AND credits=50
          AND first_purchase_only=true AND amount_paise=2400
    """)
    op.execute("UPDATE journal.platform_config SET revision=revision+1 WHERE key='product'")
