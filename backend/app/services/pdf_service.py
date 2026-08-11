import io
from dataclasses import dataclass
from datetime import datetime

from fpdf import FPDF

from app.services.qrcode_service import gerar_qrcode_png


@dataclass
class PassageiroManifesto:
    poltrona: str
    nome: str
    documento: str
    tipo_documento: str
    categoria: str
    embarcado: bool


@dataclass
class DadosManifesto:
    empresa_nome: str
    origem: str
    destino: str
    data_hora_partida: datetime
    onibus_identificacao: str
    motorista_nome: str | None
    passageiros: list[PassageiroManifesto]


def gerar_manifesto_pdf(dados: DadosManifesto) -> bytes:
    """Lista de passageiros embarcados numa viagem, em A4 — documento que o
    motorista mostra em fiscalização (blitz) numa linha intermunicipal."""
    pdf = FPDF(format="A4", orientation="P")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margin(12)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Manifesto de Passageiros", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, dados.empresa_nome, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"{dados.origem} -> {dados.destino}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Partida: {dados.data_hora_partida.strftime('%d/%m/%Y as %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Onibus: {dados.onibus_identificacao}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Motorista: {dados.motorista_nome or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    with pdf.table(col_widths=(14, 52, 40, 22, 30, 22), text_align=("C", "L", "L", "L", "L", "C")) as table:
        cabecalho = table.row()
        for texto in ("Poltr.", "Passageiro", "Documento", "Tipo", "Categoria", "Embarque"):
            cabecalho.cell(texto)
        for p in dados.passageiros:
            linha = table.row()
            linha.cell(p.poltrona)
            linha.cell(p.nome)
            linha.cell(p.documento)
            linha.cell(p.tipo_documento)
            linha.cell(p.categoria)
            linha.cell("Sim" if p.embarcado else "Nao")

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(0, 5, f"Total de passageiros: {len(dados.passageiros)}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Gerado em {datetime.now().strftime('%d/%m/%Y as %H:%M')}", new_x="LMARGIN", new_y="NEXT")

    saida = pdf.output()
    return bytes(saida)


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
