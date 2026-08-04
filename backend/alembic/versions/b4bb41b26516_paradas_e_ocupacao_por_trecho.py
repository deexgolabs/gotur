"""paradas e ocupacao por trecho

Introduz venda por trecho: paradas intermediárias numa rota e um
"livro-razão" de ocupação de poltrona por trecho (ocupacoes_poltrona),
substituindo o status único (livre/hold/bloqueada/vendida) que a poltrona
tinha para a viagem inteira.

Faz backfill de dados existentes:
- cada rota ganha 2 paradas (origem/destino) se ainda não tiver nenhuma;
- toda passagem existente passa a referenciar essas 2 paradas (trecho =
  viagem inteira, comportamento equivalente ao anterior);
- toda poltrona bloqueada vira um registro de bloqueio no livro-razão
  cobrindo a rota inteira;
- toda passagem confirmada vira um registro de venda no livro-razão.
Holds antigos (temporários, expiram em minutos) não são migrados.

Revision ID: b4bb41b26516
Revises: 8eed861ef93f
Create Date: 2026-08-03 20:38:42.730875

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4bb41b26516"
down_revision: Union[str, Sequence[str], None] = "8eed861ef93f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "paradas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("rota_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("peso_proximo", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.ForeignKeyConstraint(["rota_id"], ["rotas.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ocupacoes_poltrona",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("poltrona_viagem_id", sa.Integer(), nullable=False),
        sa.Column("tipo", sa.Enum("HOLD", "BLOQUEIO", "VENDA", name="tipoocupacao"), nullable=False),
        sa.Column("parada_origem_ordem", sa.Integer(), nullable=False),
        sa.Column("parada_destino_ordem", sa.Integer(), nullable=False),
        sa.Column("expira_em", sa.DateTime(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("passagem_id", sa.Integer(), nullable=True),
        sa.Column("motivo", sa.String(length=200), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["passagem_id"], ["passagens.id"]),
        sa.ForeignKeyConstraint(["poltrona_viagem_id"], ["poltronas_viagem.id"]),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.add_column("passagens", sa.Column("parada_origem_id", sa.Integer(), nullable=True))
    op.add_column("passagens", sa.Column("parada_destino_id", sa.Integer(), nullable=True))

    # --- backfill: cada rota existente ganha paradas origem(ordem 0) e destino(ordem 1) ---
    rotas = bind.execute(sa.text("SELECT id, origem, destino FROM rotas")).fetchall()
    parada_origem_id_por_rota: dict[int, int] = {}
    parada_destino_id_por_rota: dict[int, int] = {}
    for rota_id, origem, destino in rotas:
        ja_tem = bind.execute(sa.text("SELECT COUNT(*) FROM paradas WHERE rota_id = :r"), {"r": rota_id}).scalar()
        if ja_tem:
            linhas = bind.execute(
                sa.text("SELECT id, ordem FROM paradas WHERE rota_id = :r ORDER BY ordem"), {"r": rota_id}
            ).fetchall()
            parada_origem_id_por_rota[rota_id] = linhas[0][0]
            parada_destino_id_por_rota[rota_id] = linhas[-1][0]
            continue

        resultado_origem = bind.execute(
            sa.text(
                "INSERT INTO paradas (rota_id, nome, ordem, peso_proximo) VALUES (:rota_id, :nome, 0, 1.0)"
            ),
            {"rota_id": rota_id, "nome": origem},
        )
        id_origem = resultado_origem.lastrowid
        resultado_destino = bind.execute(
            sa.text(
                "INSERT INTO paradas (rota_id, nome, ordem, peso_proximo) VALUES (:rota_id, :nome, 1, NULL)"
            ),
            {"rota_id": rota_id, "nome": destino},
        )
        id_destino = resultado_destino.lastrowid
        parada_origem_id_por_rota[rota_id] = id_origem
        parada_destino_id_por_rota[rota_id] = id_destino

    # --- backfill: cada passagem existente referencia origem/destino da rota da sua viagem ---
    passagens = bind.execute(
        sa.text(
            """
            SELECT p.id, v.rota_id
            FROM passagens p
            JOIN viagens v ON v.id = p.viagem_id
            """
        )
    ).fetchall()
    for passagem_id, rota_id in passagens:
        bind.execute(
            sa.text("UPDATE passagens SET parada_origem_id = :o, parada_destino_id = :d WHERE id = :p"),
            {
                "o": parada_origem_id_por_rota[rota_id],
                "d": parada_destino_id_por_rota[rota_id],
                "p": passagem_id,
            },
        )

    with op.batch_alter_table("passagens") as batch_op:
        batch_op.alter_column("parada_origem_id", nullable=False)
        batch_op.alter_column("parada_destino_id", nullable=False)
        batch_op.create_foreign_key("fk_passagens_parada_origem", "paradas", ["parada_origem_id"], ["id"])
        batch_op.create_foreign_key("fk_passagens_parada_destino", "paradas", ["parada_destino_id"], ["id"])

    # --- backfill: poltronas bloqueadas viram registro de bloqueio no livro-razão (rota inteira) ---
    bloqueadas = bind.execute(
        sa.text(
            """
            SELECT pv.id, v.rota_id, pv.bloqueio_motivo
            FROM poltronas_viagem pv
            JOIN viagens v ON v.id = pv.viagem_id
            WHERE pv.status = 'BLOQUEADA'
            """
        )
    ).fetchall()
    for poltrona_viagem_id, rota_id, motivo in bloqueadas:
        destino_ordem = bind.execute(
            sa.text("SELECT MAX(ordem) FROM paradas WHERE rota_id = :r"), {"r": rota_id}
        ).scalar()
        bind.execute(
            sa.text(
                """
                INSERT INTO ocupacoes_poltrona
                    (poltrona_viagem_id, tipo, parada_origem_ordem, parada_destino_ordem, motivo, criado_em)
                VALUES (:pv, 'BLOQUEIO', 0, :destino_ordem, :motivo, CURRENT_TIMESTAMP)
                """
            ),
            {"pv": poltrona_viagem_id, "destino_ordem": destino_ordem, "motivo": motivo},
        )

    # --- backfill: passagens confirmadas viram registro de venda no livro-razão ---
    vendidas = bind.execute(
        sa.text(
            """
            SELECT p.id, p.poltrona_viagem_id, po.ordem, pd.ordem, p.criado_em
            FROM passagens p
            JOIN paradas po ON po.id = p.parada_origem_id
            JOIN paradas pd ON pd.id = p.parada_destino_id
            WHERE p.status = 'CONFIRMADA'
            """
        )
    ).fetchall()
    for passagem_id, poltrona_viagem_id, origem_ordem, destino_ordem, criado_em in vendidas:
        bind.execute(
            sa.text(
                """
                INSERT INTO ocupacoes_poltrona
                    (poltrona_viagem_id, tipo, parada_origem_ordem, parada_destino_ordem, passagem_id, criado_em)
                VALUES (:pv, 'VENDA', :o, :d, :passagem_id, :criado_em)
                """
            ),
            {
                "pv": poltrona_viagem_id,
                "o": origem_ordem,
                "d": destino_ordem,
                "passagem_id": passagem_id,
                "criado_em": criado_em,
            },
        )

    with op.batch_alter_table("poltronas_viagem") as batch_op:
        batch_op.drop_column("status")
        batch_op.drop_column("hold_usuario_id")
        batch_op.drop_column("bloqueio_motivo")
        batch_op.drop_column("hold_expira_em")


def downgrade() -> None:
    with op.batch_alter_table("poltronas_viagem") as batch_op:
        batch_op.add_column(sa.Column("hold_expira_em", sa.DATETIME(), nullable=True))
        batch_op.add_column(sa.Column("bloqueio_motivo", sa.VARCHAR(length=200), nullable=True))
        batch_op.add_column(sa.Column("hold_usuario_id", sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.VARCHAR(length=9), nullable=False, server_default="livre"))
        batch_op.create_foreign_key("fk_poltronas_viagem_hold_usuario", "usuarios", ["hold_usuario_id"], ["id"])

    with op.batch_alter_table("passagens") as batch_op:
        batch_op.drop_constraint("fk_passagens_parada_destino", type_="foreignkey")
        batch_op.drop_constraint("fk_passagens_parada_origem", type_="foreignkey")
        batch_op.drop_column("parada_destino_id")
        batch_op.drop_column("parada_origem_id")

    op.drop_table("ocupacoes_poltrona")
    op.drop_table("paradas")
