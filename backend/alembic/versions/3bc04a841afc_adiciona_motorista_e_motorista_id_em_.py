"""adiciona motorista e motorista_id em viagem fretamento frete

Revision ID: 3bc04a841afc
Revises: 55fd409e910e
Create Date: 2026-08-12 13:43:39.141323

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3bc04a841afc'
down_revision: Union[str, Sequence[str], None] = '55fd409e910e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('motoristas',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=150), nullable=False),
    sa.Column('cnh', sa.String(length=20), nullable=True),
    sa.Column('categoria_cnh', sa.Enum('A', 'B', 'C', 'D', 'E', name='categoriacnh'), nullable=True),
    sa.Column('telefone', sa.String(length=30), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['empresas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('fretamentos') as batch:
        batch.add_column(sa.Column('motorista_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_fretamentos_motorista_id', 'motoristas', ['motorista_id'], ['id'])

    with op.batch_alter_table('fretes') as batch:
        batch.add_column(sa.Column('motorista_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_fretes_motorista_id', 'motoristas', ['motorista_id'], ['id'])

    with op.batch_alter_table('viagens') as batch:
        batch.add_column(sa.Column('motorista_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_viagens_motorista_id', 'motoristas', ['motorista_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('viagens') as batch:
        batch.drop_constraint('fk_viagens_motorista_id', type_='foreignkey')
        batch.drop_column('motorista_id')

    with op.batch_alter_table('fretes') as batch:
        batch.drop_constraint('fk_fretes_motorista_id', type_='foreignkey')
        batch.drop_column('motorista_id')

    with op.batch_alter_table('fretamentos') as batch:
        batch.drop_constraint('fk_fretamentos_motorista_id', type_='foreignkey')
        batch.drop_column('motorista_id')

    op.drop_table('motoristas')
