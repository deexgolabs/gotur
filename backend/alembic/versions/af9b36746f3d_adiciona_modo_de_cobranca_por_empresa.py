"""adiciona modo de cobranca por empresa

Revision ID: af9b36746f3d
Revises: 3540b75a69ea
Create Date: 2026-08-12 16:47:58.072976

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af9b36746f3d'
down_revision: Union[str, Sequence[str], None] = '3540b75a69ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'empresas',
        sa.Column(
            'modo_cobranca',
            sa.Enum('AUTOMATICA', 'MANUAL', 'DESATIVADA', name='modocobranca'),
            nullable=False,
            server_default='AUTOMATICA',
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('empresas', 'modo_cobranca')
