"""adiciona programa de fidelidade e cupom pessoal por cliente

Revision ID: 55fd409e910e
Revises: bca9dd9cbe8c
Create Date: 2026-08-11 20:17:50.887964

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55fd409e910e'
down_revision: Union[str, Sequence[str], None] = 'bca9dd9cbe8c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('cupons') as batch:
        batch.add_column(sa.Column('cliente_usuario_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_cupons_cliente_usuario_id', 'usuarios', ['cliente_usuario_id'], ['id'])

    op.add_column('empresas', sa.Column('fidelidade_ativa', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('empresas', sa.Column('fidelidade_passagens_necessarias', sa.Integer(), nullable=True))
    op.add_column('empresas', sa.Column('fidelidade_desconto_percentual', sa.Numeric(precision=5, scale=2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('empresas', 'fidelidade_desconto_percentual')
    op.drop_column('empresas', 'fidelidade_passagens_necessarias')
    op.drop_column('empresas', 'fidelidade_ativa')

    with op.batch_alter_table('cupons') as batch:
        batch.drop_constraint('fk_cupons_cliente_usuario_id', type_='foreignkey')
        batch.drop_column('cliente_usuario_id')
