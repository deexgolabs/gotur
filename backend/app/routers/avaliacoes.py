from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from app.core.deps import require_staff
from app.database import get_db
from app.models.avaliacao import Avaliacao
from app.models.usuario import Usuario
from app.schemas.avaliacao import AvaliacaoOut, ResumoAvaliacoesOut

router = APIRouter(prefix="/avaliacoes", tags=["avaliacoes"])


@router.get("", response_model=ResumoAvaliacoesOut)
def listar_avaliacoes(
    db: Session = Depends(get_db),
    usuario_atual: Usuario = Depends(require_staff),
):
    avaliacoes = (
        db.query(Avaliacao)
        .options(joinedload(Avaliacao.passagem), joinedload(Avaliacao.fretamento))
        .filter(Avaliacao.tenant_id == usuario_atual.tenant_id)
        .order_by(Avaliacao.criado_em.desc())
        .all()
    )

    resultado = []
    for a in avaliacoes:
        if a.passagem:
            cliente_nome = a.passagem.cliente_nome
            origem, destino = a.passagem.origem_trecho, a.passagem.destino_trecho
        elif a.fretamento:
            cliente_nome = a.fretamento.cliente_nome
            origem, destino = a.fretamento.origem, a.fretamento.destino
        else:
            cliente_nome = origem = destino = None

        resultado.append(
            AvaliacaoOut(
                id=a.id,
                passagem_id=a.passagem_id,
                fretamento_id=a.fretamento_id,
                nota=a.nota,
                comentario=a.comentario,
                criado_em=a.criado_em,
                cliente_nome=cliente_nome,
                origem=origem,
                destino=destino,
            )
        )

    media = round(sum(a.nota for a in avaliacoes) / len(avaliacoes), 2) if avaliacoes else None
    return ResumoAvaliacoesOut(total=len(avaliacoes), media=media, avaliacoes=resultado)
