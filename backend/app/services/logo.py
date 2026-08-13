"""Processamento do logo enviado pela empresa (white-label).

Gera, a partir da imagem enviada:
- `logo.png`: versão exibida no cabeçalho da loja (mantém proporção/transparência).
- `icon-192.png` / `icon-512.png`: versão quadrada com fundo na cor da marca,
  usada nos ícones do PWA instalável (`/loja/{slug}/manifest.json`).
"""

import io
import time
from pathlib import Path

from PIL import Image

from app.config import settings

COR_PADRAO = (110, 0, 167, 255)  # roxo-escuro do GoTur, usado se a empresa não definir cor própria


def _hex_para_rgba(cor_hex: str | None) -> tuple[int, int, int, int]:
    if not cor_hex:
        return COR_PADRAO
    cor_hex = cor_hex.lstrip("#")
    if len(cor_hex) != 6:
        return COR_PADRAO
    try:
        r, g, b = (int(cor_hex[i : i + 2], 16) for i in (0, 2, 4))
        return (r, g, b, 255)
    except ValueError:
        return COR_PADRAO


def _diretorio_empresa(empresa_id: int) -> Path:
    caminho = Path(settings.media_dir) / "empresas" / str(empresa_id)
    caminho.mkdir(parents=True, exist_ok=True)
    return caminho


def _icone_quadrado(imagem: Image.Image, tamanho: int, cor_fundo: tuple[int, int, int, int]) -> Image.Image:
    fundo = Image.new("RGBA", (tamanho, tamanho), cor_fundo)
    miniatura = imagem.copy()
    margem = int(tamanho * 0.16)
    area_util = tamanho - 2 * margem
    miniatura.thumbnail((area_util, area_util), Image.LANCZOS)
    posicao = ((tamanho - miniatura.width) // 2, (tamanho - miniatura.height) // 2)
    fundo.paste(miniatura, posicao, miniatura if miniatura.mode == "RGBA" else None)
    return fundo


def salvar_logo(empresa_id: int, conteudo: bytes, cor_primaria: str | None) -> str:
    """Salva o logo e gera os ícones. Retorna um valor de versão (timestamp)
    para cache-busting da URL pública."""
    imagem = Image.open(io.BytesIO(conteudo)).convert("RGBA")

    destino = _diretorio_empresa(empresa_id)

    exibicao = imagem.copy()
    exibicao.thumbnail((800, 800), Image.LANCZOS)
    exibicao.save(destino / "logo.png")

    cor_fundo = _hex_para_rgba(cor_primaria)
    _icone_quadrado(imagem, 192, cor_fundo).save(destino / "icon-192.png")
    _icone_quadrado(imagem, 512, cor_fundo).save(destino / "icon-512.png")

    return str(int(time.time()))


def regenerar_icones_com_nova_cor(empresa_id: int, cor_primaria: str | None) -> bool:
    """Chamado quando a empresa muda a cor depois de já ter enviado um logo,
    pra manter os ícones do PWA consistentes com a nova cor."""
    destino = _diretorio_empresa(empresa_id)
    logo_path = destino / "logo.png"
    if not logo_path.exists():
        return False
    imagem = Image.open(logo_path).convert("RGBA")
    cor_fundo = _hex_para_rgba(cor_primaria)
    _icone_quadrado(imagem, 192, cor_fundo).save(destino / "icon-192.png")
    _icone_quadrado(imagem, 512, cor_fundo).save(destino / "icon-512.png")
    return True
