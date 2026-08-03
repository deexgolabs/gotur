import io

import qrcode


def gerar_qrcode_png(conteudo: str) -> bytes:
    imagem = qrcode.make(conteudo)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    return buffer.getvalue()
