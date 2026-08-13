"""adiciona role motorista e usuario.motorista_id

Revision ID: 7b06526b9442
Revises: b8e6085594ef
Create Date: 2026-08-13 09:36:17.596833

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7b06526b9442'
down_revision: Union[str, Sequence[str], None] = 'b8e6085594ef'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('usuarios') as batch:
        batch.add_column(sa.Column('motorista_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_usuarios_motorista_id', 'motoristas', ['motorista_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuarios') as batch:
        batch.drop_constraint('fk_usuarios_motorista_id', type_='foreignkey')
        batch.drop_column('motorista_id')
