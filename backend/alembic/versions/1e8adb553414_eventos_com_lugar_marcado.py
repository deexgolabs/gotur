"""eventos com lugar marcado

Revision ID: 1e8adb553414
Revises: e200cfe8adcf
Create Date: 2026-08-14 15:37:07.847933

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e8adb553414'
down_revision: Union[str, Sequence[str], None] = 'e200cfe8adcf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('locais',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('nome', sa.String(length=150), nullable=False),
    sa.Column('endereco', sa.String(length=255), nullable=True),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['tenant_id'], ['empresas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('assentos_local',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('local_id', sa.Integer(), nullable=False),
    sa.Column('numero', sa.String(length=10), nullable=False),
    sa.Column('fileira', sa.Integer(), nullable=False),
    sa.Column('coluna', sa.Integer(), nullable=False),
    sa.Column('setor', sa.String(length=50), nullable=True),
    sa.Column('categoria', sa.String(length=30), nullable=False),
    sa.Column('multiplicador_preco', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.ForeignKeyConstraint(['local_id'], ['locais.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('sessoes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('local_id', sa.Integer(), nullable=False),
    sa.Column('nome_evento', sa.String(length=150), nullable=False),
    sa.Column('data_hora', sa.DateTime(), nullable=False),
    sa.Column('preco', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('ativo', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['local_id'], ['locais.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['empresas.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('assentos_sessao',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sessao_id', sa.Integer(), nullable=False),
    sa.Column('assento_local_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.Enum('LIVRE', 'HOLD', 'BLOQUEADA', 'VENDIDA', name='statuspoltrona'), nullable=False),
    sa.Column('hold_usuario_id', sa.Integer(), nullable=True),
    sa.Column('hold_expira_em', sa.DateTime(), nullable=True),
    sa.Column('ingresso_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['assento_local_id'], ['assentos_local.id'], ),
    sa.ForeignKeyConstraint(['hold_usuario_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['sessao_id'], ['sessoes.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('ingressos',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('sessao_id', sa.Integer(), nullable=False),
    sa.Column('assento_sessao_id', sa.Integer(), nullable=False),
    sa.Column('cliente_usuario_id', sa.Integer(), nullable=True),
    sa.Column('cliente_nome', sa.String(length=150), nullable=False),
    sa.Column('cliente_documento', sa.String(length=30), nullable=False),
    sa.Column('vendido_por_usuario_id', sa.Integer(), nullable=True),
    sa.Column('preco', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('forma_pagamento', sa.Enum('DINHEIRO', 'CARTAO', 'PIX', 'BOLETO', 'OUTRO', name='formapagamento'), nullable=False),
    sa.Column('gateway_ref', sa.String(length=100), nullable=True),
    sa.Column('status', sa.Enum('CONFIRMADA', 'CANCELADA', name='statuspassagem'), nullable=False),
    sa.Column('codigo', sa.String(length=10), nullable=False),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.Column('checkin_em', sa.DateTime(), nullable=True),
    sa.Column('valor_reembolsado', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('motivo_reembolso', sa.String(length=255), nullable=True),
    sa.Column('reembolsado_em', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['assento_sessao_id'], ['assentos_sessao.id'], ),
    sa.ForeignKeyConstraint(['cliente_usuario_id'], ['usuarios.id'], ),
    sa.ForeignKeyConstraint(['sessao_id'], ['sessoes.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['empresas.id'], ),
    sa.ForeignKeyConstraint(['vendido_por_usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('codigo')
    )
    with op.batch_alter_table('assentos_sessao', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_assentos_sessao_ingresso_id', 'ingressos', ['ingresso_id'], ['id'])
    op.create_table('pedidos_ingresso_pendente',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('tenant_id', sa.Integer(), nullable=False),
    sa.Column('sessao_id', sa.Integer(), nullable=False),
    sa.Column('assento_sessao_id', sa.Integer(), nullable=False),
    sa.Column('usuario_id', sa.Integer(), nullable=False),
    sa.Column('cliente_nome', sa.String(length=150), nullable=False),
    sa.Column('cliente_documento', sa.String(length=30), nullable=False),
    sa.Column('forma_pagamento', sa.Enum('DINHEIRO', 'CARTAO', 'PIX', 'BOLETO', 'OUTRO', name='formapagamento'), nullable=False),
    sa.Column('valor', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('pix_copia_cola', sa.String(length=300), nullable=True),
    sa.Column('status', sa.Enum('PENDENTE', 'CONFIRMADO', 'EXPIRADO', 'CANCELADO', name='statuspedidopagamento'), nullable=False),
    sa.Column('ingresso_id', sa.Integer(), nullable=True),
    sa.Column('gateway_ref', sa.String(length=100), nullable=True),
    sa.Column('expira_em', sa.DateTime(), nullable=False),
    sa.Column('criado_em', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['assento_sessao_id'], ['assentos_sessao.id'], ),
    sa.ForeignKeyConstraint(['ingresso_id'], ['ingressos.id'], ),
    sa.ForeignKeyConstraint(['sessao_id'], ['sessoes.id'], ),
    sa.ForeignKeyConstraint(['tenant_id'], ['empresas.id'], ),
    sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('empresas', sa.Column('eventos_ativo', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('planos', sa.Column('modulo_eventos', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('planos', 'modulo_eventos')
    op.drop_column('empresas', 'eventos_ativo')
    op.drop_table('pedidos_ingresso_pendente')
    with op.batch_alter_table('assentos_sessao', schema=None) as batch_op:
        batch_op.drop_constraint('fk_assentos_sessao_ingresso_id', type_='foreignkey')
    op.drop_table('ingressos')
    op.drop_table('assentos_sessao')
    op.drop_table('sessoes')
    op.drop_table('assentos_local')
    op.drop_table('locais')
