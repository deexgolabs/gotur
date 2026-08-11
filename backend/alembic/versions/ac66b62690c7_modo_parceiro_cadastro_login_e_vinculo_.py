"""modo parceiro: cadastro, login e vinculo em passagem, frete e fretamento

Revision ID: ac66b62690c7
Revises: eb2e1f9cf3e2
Create Date: 2026-08-11 14:21:55.174250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac66b62690c7'
down_revision: Union[str, Sequence[str], None] = 'eb2e1f9cf3e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'parceiros',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=150), nullable=False),
        sa.Column('documento', sa.String(length=30), nullable=True),
        sa.Column('contato', sa.String(length=100), nullable=True),
        sa.Column('vende_passagem', sa.Boolean(), nullable=False),
        sa.Column('despacha_frete', sa.Boolean(), nullable=False),
        sa.Column('comissao_percentual', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('ativo', sa.Boolean(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['empresas.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )

    # SQLite não suporta ALTER TABLE ... ADD CONSTRAINT direto — batch mode
    # faz o "copy-and-move" necessário (e continua usando ALTER nativo em
    # Postgres/MySQL, então funciona nos três bancos).
    with op.batch_alter_table('fretamentos') as batch:
        batch.add_column(sa.Column('parceiro_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_fretamentos_parceiro_id', 'parceiros', ['parceiro_id'], ['id'])

    with op.batch_alter_table('fretes') as batch:
        batch.add_column(sa.Column('peso_kg', sa.Numeric(precision=8, scale=2), nullable=True))
        batch.add_column(sa.Column('quantidade_volumes', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('valor_declarado', sa.Numeric(precision=10, scale=2), nullable=True))
        batch.add_column(sa.Column('parceiro_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_fretes_parceiro_id', 'parceiros', ['parceiro_id'], ['id'])

    with op.batch_alter_table('passagens') as batch:
        batch.add_column(sa.Column('parceiro_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('cliente_telefone', sa.String(length=30), nullable=True))
        batch.add_column(sa.Column(
            'tipo_documento',
            sa.Enum('CPF', 'RG', 'CNH', 'PASSAPORTE', 'OUTRO', name='tipodocumento'),
            nullable=False,
            server_default='CPF',
        ))
        batch.add_column(sa.Column(
            'categoria_passageiro',
            sa.Enum('COMUM', 'IDOSO', 'PCD', 'CRIANCA_COLO', name='categoriapassageiro'),
            nullable=False,
            server_default='COMUM',
        ))
        batch.create_foreign_key('fk_passagens_parceiro_id', 'parceiros', ['parceiro_id'], ['id'])

    with op.batch_alter_table('pedidos_pagamento') as batch:
        batch.add_column(sa.Column('parceiro_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('cliente_telefone', sa.String(length=30), nullable=True))
        batch.add_column(sa.Column(
            'tipo_documento',
            sa.Enum('CPF', 'RG', 'CNH', 'PASSAPORTE', 'OUTRO', name='tipodocumento'),
            nullable=False,
            server_default='CPF',
        ))
        batch.add_column(sa.Column(
            'categoria_passageiro',
            sa.Enum('COMUM', 'IDOSO', 'PCD', 'CRIANCA_COLO', name='categoriapassageiro'),
            nullable=False,
            server_default='COMUM',
        ))
        batch.create_foreign_key('fk_pedidos_pagamento_parceiro_id', 'parceiros', ['parceiro_id'], ['id'])

    with op.batch_alter_table('usuarios') as batch:
        batch.add_column(sa.Column('parceiro_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_usuarios_parceiro_id', 'parceiros', ['parceiro_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('usuarios') as batch:
        batch.drop_constraint('fk_usuarios_parceiro_id', type_='foreignkey')
        batch.drop_column('parceiro_id')

    with op.batch_alter_table('pedidos_pagamento') as batch:
        batch.drop_constraint('fk_pedidos_pagamento_parceiro_id', type_='foreignkey')
        batch.drop_column('categoria_passageiro')
        batch.drop_column('tipo_documento')
        batch.drop_column('cliente_telefone')
        batch.drop_column('parceiro_id')

    with op.batch_alter_table('passagens') as batch:
        batch.drop_constraint('fk_passagens_parceiro_id', type_='foreignkey')
        batch.drop_column('categoria_passageiro')
        batch.drop_column('tipo_documento')
        batch.drop_column('cliente_telefone')
        batch.drop_column('parceiro_id')

    with op.batch_alter_table('fretes') as batch:
        batch.drop_constraint('fk_fretes_parceiro_id', type_='foreignkey')
        batch.drop_column('parceiro_id')
        batch.drop_column('valor_declarado')
        batch.drop_column('quantidade_volumes')
        batch.drop_column('peso_kg')

    with op.batch_alter_table('fretamentos') as batch:
        batch.drop_constraint('fk_fretamentos_parceiro_id', type_='foreignkey')
        batch.drop_column('parceiro_id')

    op.drop_table('parceiros')
