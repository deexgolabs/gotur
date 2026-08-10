import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.empresa import Empresa


def slugificar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    minusculo = sem_acento.lower()
    com_hifens = re.sub(r"[^a-z0-9]+", "-", minusculo).strip("-")
    return com_hifens[:70] or "empresa"


def gerar_slug_unico(db: Session, texto_base: str, empresa_id_ignorar: int | None = None) -> str:
    base = slugificar(texto_base)
    candidato = base
    contador = 2
    while True:
        query = db.query(Empresa).filter(Empresa.slug == candidato)
        if empresa_id_ignorar is not None:
            query = query.filter(Empresa.id != empresa_id_ignorar)
        if not query.first():
            return candidato
        candidato = f"{base}-{contador}"
        contador += 1
