import io
from dataclasses import dataclass
from datetime import datetime

from fpdf import FPDF

from app.services.qrcode_service import gerar_qrcode_png


@dataclass
class DadosBilhete:
    empresa_nome: str
    origem: str
    destino: str
    data_hora_partida: datetime
    numero_poltrona: str
    categoria_poltrona: str
    cliente_nome: str
    cliente_documento: str
    localizador: str
    preco: float


def gerar_bilhete_pdf(dados: DadosBilhete) -> bytes:
    """Bilhete em formato de recibo estreito (80mm), pronto para impressão
    de balcão em impressoras térmicas comuns ou impressão normal em papel A4."""
    pdf = FPDF(format=(80, 150))
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_margin(5)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "GoTur", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, dados.empresa_nome, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)

    pdf.set_draw_color(200, 200, 200)
    pdf.line(5, pdf.get_y(), 75, pdf.get_y())
    pdf.ln(3)

    def linha(rotulo: str, valor: str, negrito: bool = False) -> None:
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 4.5, rotulo, new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "B" if negrito else "", 10)
        pdf.cell(0, 5.5, valor, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    linha("TRECHO", f"{dados.origem} -> {dados.destino}", negrito=True)
    linha("PARTIDA", dados.data_hora_partida.strftime("%d/%m/%Y as %H:%M"))
    linha("POLTRONA", f"{dados.numero_poltrona} ({dados.categoria_poltrona})")
    linha("PASSAGEIRO", dados.cliente_nome)
    linha("CPF", dados.cliente_documento)
    linha("VALOR PAGO", f"R$ {dados.preco:.2f}")

    pdf.ln(2)
    pdf.line(5, pdf.get_y(), 75, pdf.get_y())
    pdf.ln(4)

    qr_png = gerar_qrcode_png(dados.localizador)
    pdf.image(io.BytesIO(qr_png), x=20, w=40)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, dados.localizador, new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 4, "Apresente este codigo no embarque", new_x="LMARGIN", new_y="NEXT", align="C")

    saida = pdf.output()
    return bytes(saida)
