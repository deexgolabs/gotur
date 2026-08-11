"""Limite de taxa simples, em memória, pra formulários públicos (sem
autenticação) que são alvo óbvio de spam/abuso: pedir orçamento de
fretamento, criar conta, cadastrar empresa.

Não precisa de Redis nem de outra infra: cada processo guarda os
carimbos de tempo recentes por IP, o suficiente pra um único servidor
como este (PythonAnywhere). Se um dia isso rodar em múltiplos processos
atrás de um load balancer, o limite passa a valer por processo, não
globalmente — nesse caso, trocar por um backend compartilhado (Redis)."""

import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_registros: dict[str, list[float]] = defaultdict(list)
_chamadas_desde_limpeza = 0


def _limpar_registros_antigos(agora: float) -> None:
    """Remove entradas totalmente vencidas pra não crescer pra sempre."""
    global _chamadas_desde_limpeza
    _chamadas_desde_limpeza += 1
    if _chamadas_desde_limpeza < 200:
        return
    _chamadas_desde_limpeza = 0
    chaves_vazias = [chave for chave, tempos in _registros.items() if not tempos or agora - tempos[-1] > 3600]
    for chave in chaves_vazias:
        _registros.pop(chave, None)


def limitar_taxa(namespace: str, max_chamadas: int, janela_segundos: int):
    """Fábrica de dependência do FastAPI. Uso:
    `Depends(limitar_taxa("solicitar-fretamento", max_chamadas=5, janela_segundos=600))`
    """

    def dependencia(request: Request) -> None:
        ip = request.client.host if request.client else "desconhecido"
        chave = f"{namespace}:{ip}"
        agora = time.time()

        tempos = _registros[chave]
        limite_inferior = agora - janela_segundos
        while tempos and tempos[0] < limite_inferior:
            tempos.pop(0)

        if len(tempos) >= max_chamadas:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas tentativas em pouco tempo. Aguarde alguns minutos e tente de novo.",
            )

        tempos.append(agora)
        _limpar_registros_antigos(agora)

    return dependencia
