"""white label slug cor e logo da empresa

Revision ID: 5baaf7bb8401
Revises: 43b9a2077bee
Create Date: 2026-08-10 17:30:47.857729

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5baaf7bb8401'
down_revision: Union[str, Sequence[str], None] = '43b9a2077bee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('empresas') as batch_op:
        batch_op.add_column(sa.Column('slug', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('cor_primaria', sa.String(length=7), nullable=True))
        batch_op.add_column(sa.Column('logo_filename', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_empresas_slug', ['slug'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('empresas') as batch_op:
        batch_op.drop_constraint('uq_empresas_slug', type_='unique')
        batch_op.drop_column('logo_filename')
        batch_op.drop_column('cor_primaria')
        batch_op.drop_column('slug')
