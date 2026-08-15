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
class DadosContratoFretamento:
    empresa_nome: str
    empresa_cnpj: str
    empresa_contato: str | None
    codigo_rastreio: str
    cliente_nome: str
    cliente_documento: str | None
    cliente_contato: str | None
    origem: str
    destino: str
    data_hora_saida: datetime
    data_hora_retorno_prevista: datetime | None
    onibus_identificacao: str | None
    motorista_nome: str | None
    distancia_km: float | None
    valor_total: float | None
    observacoes: str | None


CLAUSULAS_CONTRATO_FRETAMENTO = [
    "1. O presente contrato tem por objeto a prestacao de servico de fretamento de onibus pela CONTRATADA "
    "a CONTRATANTE, no trajeto, data e horario especificados acima.",
    "2. O valor total informado refere-se exclusivamente ao trajeto e periodo contratados, podendo haver "
    "cobranca adicional em caso de alteracao de roteiro solicitada pela CONTRATANTE apos a confirmacao.",
    "3. A CONTRATANTE se compromete a respeitar o horario de saida combinado. Atrasos podem acarretar em "
    "ajuste do horario de retorno, sujeito a disponibilidade do veiculo e do motorista.",
    "4. A CONTRATADA se responsabiliza pela manutencao e seguranca do veiculo, bem como pela habilitacao "
    "do motorista designado para a viagem.",
    "5. Eventuais danos causados ao veiculo por mau uso durante o periodo de fretamento serao de "
    "responsabilidade da CONTRATANTE, apurados e comunicados apos a vistoria do veiculo.",
]


def gerar_contrato_fretamento_pdf(dados: DadosContratoFretamento) -> bytes:
    """Contrato formal de fretamento em A4 — documento que o cliente/evento
    pede para formalizar a contratacao, gerado a partir dos dados que ja
    existem no fretamento (sem digitar nada de novo)."""
    pdf = FPDF(format="A4", orientation="P")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_margin(15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Contrato de Fretamento", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"{dados.empresa_nome} - CNPJ {dados.empresa_cnpj}", new_x="LMARGIN", new_y="NEXT", align="C")
    if dados.empresa_contato:
        pdf.cell(0, 6, dados.empresa_contato, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Codigo: {dados.codigo_rastreio}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "CONTRATANTE", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Nome/Razao social: {dados.cliente_nome}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"CPF/CNPJ: {dados.cliente_documento or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Contato: {dados.cliente_contato or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "OBJETO DO CONTRATO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Trajeto: {dados.origem} -> {dados.destino}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Saida: {dados.data_hora_saida.strftime('%d/%m/%Y as %H:%M')}", new_x="LMARGIN", new_y="NEXT")
    retorno = dados.data_hora_retorno_prevista.strftime("%d/%m/%Y as %H:%M") if dados.data_hora_retorno_prevista else "-"
    pdf.cell(0, 6, f"Retorno previsto: {retorno}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Veiculo: {dados.onibus_identificacao or '-'}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Motorista: {dados.motorista_nome or '-'}", new_x="LMARGIN", new_y="NEXT")
    if dados.distancia_km is not None:
        pdf.cell(0, 6, f"Distancia prevista: {dados.distancia_km:.1f} km", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 7, f"Valor total: R$ {dados.valor_total:.2f}" if dados.valor_total is not None else "Valor total: a combinar", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    if dados.observacoes:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "OBSERVACOES", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 5, dados.observacoes)
        pdf.ln(2)

    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "CLAUSULAS GERAIS", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for clausula in CLAUSULAS_CONTRATO_FRETAMENTO:
        pdf.multi_cell(0, 5, clausula)
        pdf.ln(1)

    pdf.ln(10)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(90, 6, "_" * 35, new_x="RIGHT", new_y="LAST", align="C")
    pdf.cell(90, 6, "_" * 35, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.cell(90, 5, "CONTRATADA", new_x="RIGHT", new_y="LAST", align="C")
    pdf.cell(90, 5, "CONTRATANTE", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(6)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, f"Gerado em {datetime.now().strftime('%d/%m/%Y as %H:%M')}", new_x="LMARGIN", new_y="NEXT", align="C")

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
    pdf.cell(0, 8, "Kivo", new_x="LMARGIN", new_y="NEXT", align="C")

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


@dataclass
class DadosIngresso:
    empresa_nome: str
    nome_evento: str
    local_nome: str
    data_hora: datetime
    numero_assento: str
    categoria_assento: str
    cliente_nome: str
    cliente_documento: str
    codigo: str
    preco: float


def gerar_ingresso_pdf(dados: DadosIngresso) -> bytes:
    """Ingresso em formato de recibo estreito (80mm) — mesmo layout de
    gerar_bilhete_pdf, só troca os campos (evento/local/assento em vez de
    trecho/partida/poltrona)."""
    pdf = FPDF(format=(80, 150))
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_margin(5)

    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, "Kivo", new_x="LMARGIN", new_y="NEXT", align="C")

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

    linha("EVENTO", dados.nome_evento, negrito=True)
    linha("LOCAL", dados.local_nome)
    linha("SESSAO", dados.data_hora.strftime("%d/%m/%Y as %H:%M"))
    linha("ASSENTO", f"{dados.numero_assento} ({dados.categoria_assento})")
    linha("PASSAGEIRO", dados.cliente_nome)
    linha("CPF", dados.cliente_documento)
    linha("VALOR PAGO", f"R$ {dados.preco:.2f}")

    pdf.ln(2)
    pdf.line(5, pdf.get_y(), 75, pdf.get_y())
    pdf.ln(4)

    qr_png = gerar_qrcode_png(dados.codigo)
    pdf.image(io.BytesIO(qr_png), x=20, w=40)
    pdf.ln(2)

    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 6, dados.codigo, new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 4, "Apresente este codigo na entrada", new_x="LMARGIN", new_y="NEXT", align="C")

    saida = pdf.output()
    return bytes(saida)
