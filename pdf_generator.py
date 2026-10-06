import csv
import json
import os
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from reportlab.lib.colors import black, white
from reportlab.pdfgen import canvas
from PyPDF2 import PdfReader, PdfWriter
from utils import utils
from utils.pdf_grid import (
    GradeFolhaPonto,
    caixa_assinatura,
    detectar_grade,
    posicao_texto_centralizado,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PDF_OVERLAY = os.path.join(BASE_DIR, "pdfs", "overlay.pdf")
PDF_ENTRADA = os.path.join(BASE_DIR, "pdfs", "entrada.pdf")
PDF_SAIDA   = os.path.join(BASE_DIR, "pdfs", "saida.pdf")
CSV_HORAS   = os.path.join(BASE_DIR, "results", "horas.csv")
CONFIG_PATH = os.path.join(BASE_DIR, "configs", "config.json")

os.makedirs(os.path.dirname(PDF_OVERLAY), exist_ok=True)

FONT_NAME = "Helvetica"
FONT_SIZE = 9


def report(cb, msg, value):
    if cb:
        cb(msg, value)


def ler_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {}

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def ler_csv_horas(caminho_csv: str):
    with open(caminho_csv, newline="", encoding="utf-8") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)
        for row in reader:
            yield row

def get_configs_values(configs: dict) -> tuple:
    assinatura_cfg = configs.get("assinatura", {})
    tipo_assinatura = assinatura_cfg.get("tipo")
    texto_assinatura = assinatura_cfg.get("texto", "")
    caminho_assinatura = assinatura_cfg.get("arquivo", "")
    if caminho_assinatura and not os.path.isabs(caminho_assinatura):
        caminho_assinatura = os.path.join(BASE_DIR, caminho_assinatura)

    horarios_cfg = configs.get("horarios", {})
    valor_central_entrada = horarios_cfg.get("central_entrada") or "07:50:00"
    valor_central_saida = horarios_cfg.get("central_saida") or "18:00:00"
    valor_intervalo_inicio = horarios_cfg.get("intervalo_inicio") or "12:00"
    valor_intervalo_fim = horarios_cfg.get("intervalo_fim") or "14:00"

    return (
        tipo_assinatura,
        texto_assinatura,
        caminho_assinatura,
        valor_central_entrada,
        valor_central_saida,
        valor_intervalo_inicio,
        valor_intervalo_fim,
    )


def get_variacao_britanico(configs: dict) -> tuple[bool, int]:
    horarios_cfg = configs.get("horarios", {})
    ativo = bool(horarios_cfg.get("desfazer_horario_britanico"))
    if not ativo:
        return False, 0

    bruto = str(horarios_cfg.get("variacao_minutos") or horarios_cfg.get("range_intervalo") or "").strip()
    try:
        minutos = int(bruto) if bruto else 5
    except ValueError:
        minutos = 5
    # Variação pequena: 1 a 10 minutos. Valores altos (ex.: 120) empurravam a entrada para 9h.
    return True, min(max(minutos, 1), 10)


def _novo_canvas(pdf_overlay: str, grade: GradeFolhaPonto) -> canvas.Canvas:
    c = canvas.Canvas(pdf_overlay, pagesize=grade.page_size)
    c.setFont(FONT_NAME, FONT_SIZE)
    return c


def draw_texto_celula(
    c: canvas.Canvas,
    grade: GradeFolhaPonto,
    dia: int,
    coluna: str,
    texto: str,
    forcar: bool = False,
):
    celula = grade.celula(dia, coluna, ignorar_ocupada=forcar)
    if not celula:
        return

    x0, x1, y0, y1 = celula
    valor = str(texto).strip() if texto else ""

    if forcar:
        inset = 0.8
        c.setFillColor(white)
        c.rect(
            x0 + inset,
            y0 + inset,
            max(x1 - x0 - inset * 2, 1),
            max(y1 - y0 - inset * 2, 1),
            fill=1,
            stroke=0,
        )
        c.setFillColor(black)

    if not valor:
        return

    x, y = posicao_texto_centralizado(x0, x1, y0, y1, valor, FONT_NAME, FONT_SIZE)
    c.setFont(FONT_NAME, FONT_SIZE)
    c.drawString(x, y, valor)


def draw_assinatura(
    c: canvas.Canvas,
    grade: GradeFolhaPonto,
    dia: int,
    tipo: str,
    texto: str,
    caminho: str,
):
    celula = grade.celula(dia, "visto")
    if not celula:
        return

    x0, x1, y0, y1 = celula

    if tipo == "digitada" and texto:
        x, y = posicao_texto_centralizado(x0, x1, y0, y1, texto, FONT_NAME, FONT_SIZE)
        c.setFont(FONT_NAME, FONT_SIZE)
        c.drawString(x, y, texto)
    elif tipo == "canvas" and caminho and os.path.exists(caminho):
        img_x, img_y, img_w, img_h = caixa_assinatura(x0, x1, y0, y1)
        c.drawImage(
            caminho,
            img_x,
            img_y,
            width=img_w,
            height=img_h,
            preserveAspectRatio=True,
            mask="auto",
        )


def draw_linha_dia(
    c: canvas.Canvas,
    grade: GradeFolhaPonto,
    dia: int,
    entrada: str,
    inicio_intercalo: str,
    fim_intercalo: str,
    saida: str,
    tipo_assinatura: str,
    texto_assinatura: str,
    caminho_assinatura: str,
    forcar_intervalo: bool = False,
):
    draw_texto_celula(c, grade, dia, "entrada", entrada)
    draw_texto_celula(
        c, grade, dia, "intervalo_saida", inicio_intercalo, forcar=forcar_intervalo
    )
    draw_texto_celula(
        c, grade, dia, "intervalo_entrada", fim_intercalo, forcar=forcar_intervalo
    )
    draw_texto_celula(c, grade, dia, "saida", saida)

    if entrada.strip() and saida.strip():
        draw_assinatura(c, grade, dia, tipo_assinatura, texto_assinatura, caminho_assinatura)


def _hora_vazia() -> dict[str, str]:
    return {
        "entrada": "",
        "intervalo_saida": "",
        "intervalo_entrada": "",
        "saida": "",
    }


def _fmt_hora_overlay(valor: str) -> str:
    if not valor or not str(valor).strip():
        return ""
    try:
        return utils.parse_hora(valor).strftime("%H:%M")
    except ValueError:
        return str(valor).strip()


def _registrar_horario(
    horarios: dict[int, dict[str, str]],
    dia: int,
    entrada: str,
    intervalo_saida: str,
    intervalo_entrada: str,
    saida: str,
):
    horarios[dia] = {
        "entrada": _fmt_hora_overlay(entrada),
        "intervalo_saida": _fmt_hora_overlay(intervalo_saida),
        "intervalo_entrada": _fmt_hora_overlay(intervalo_entrada),
        "saida": _fmt_hora_overlay(saida),
    }


def _horarios_iniciais(grade: GradeFolhaPonto) -> dict[int, dict[str, str]]:
    return {dia: _hora_vazia() for dia in grade.rows}


def redesenhar_overlay(sessao: "SessaoEdicao"):
    c = _novo_canvas(sessao.pdf_overlay, sessao.grade)
    for dia, horas in sessao.horarios.items():
        draw_linha_dia(
            c,
            sessao.grade,
            dia,
            horas.get("entrada", ""),
            horas.get("intervalo_saida", ""),
            horas.get("intervalo_entrada", ""),
            horas.get("saida", ""),
            sessao.tipo_assinatura,
            sessao.texto_assinatura,
            sessao.caminho_assinatura,
            forcar_intervalo=True,
        )
    c.save()


@dataclass
class SessaoEdicao:
    grade: GradeFolhaPonto
    pdf_base: str
    pdf_overlay: str
    pdf_saida: str
    horarios: dict[int, dict[str, str]]
    tipo_assinatura: str
    texto_assinatura: str
    caminho_assinatura: str
    forcar_intervalo: bool = True

    def hit_test(self, pdf_x: float, pdf_y: float) -> tuple[int, str] | None:
        return self.grade.hit_test_horario(pdf_x, pdf_y)

    def aplicar(self, dia: int, coluna: str, valor: str):
        if dia not in self.horarios:
            self.horarios[dia] = _hora_vazia()
        self.horarios[dia][coluna] = valor
        redesenhar_overlay(self)
        merge_pdfs(self.pdf_base, self.pdf_overlay, self.pdf_saida)


def _montar_sessao(
    grade: GradeFolhaPonto,
    pdf_base: str,
    horarios: dict[int, dict[str, str]],
    configs: dict,
) -> SessaoEdicao:
    tipo, texto, caminho, *_ = get_configs_values(configs)
    return SessaoEdicao(
        grade=grade,
        pdf_base=pdf_base,
        pdf_overlay=PDF_OVERLAY,
        pdf_saida=PDF_SAIDA,
        horarios=horarios,
        tipo_assinatura=tipo,
        texto_assinatura=texto,
        caminho_assinatura=caminho,
    )


def calcular_saida_8h(
    entrada_str: str,
    intervalo_inicio_str: str = "12:00",
    intervalo_fim_str: str = "14:00",
) -> tuple[str, str, str]:
    """
    Calcula a saída para jornada de 8h a partir da entrada, usando a duração
    real do intervalo configurado.
    Retorna (inicio_intervalo, fim_intervalo, saida_ajustada)
    """
    if not entrada_str or not entrada_str.strip():
        return "", "", ""

    entrada_time = utils.parse_hora(entrada_str)
    inicio_time = utils.parse_hora(intervalo_inicio_str)
    fim_time = utils.parse_hora(intervalo_fim_str)

    entrada_dt = datetime.combine(date.today(), entrada_time)
    inicio_dt = datetime.combine(date.today(), inicio_time)
    fim_dt = datetime.combine(date.today(), fim_time)
    duracao_intervalo = fim_dt - inicio_dt
    if duracao_intervalo <= timedelta(0):
        duracao_intervalo = timedelta(hours=2)

    saida_dt = entrada_dt + timedelta(hours=8) + duracao_intervalo

    return (
        inicio_time.strftime("%H:%M"),
        fim_time.strftime("%H:%M"),
        saida_dt.strftime("%H:%M"),
    )


def horarios_do_dia(
    entrada_str: str,
    variar: bool,
    minutos_range: int,
    intervalo_inicio_str: str = "12:00",
    intervalo_fim_str: str = "14:00",
    variar_entrada: bool = True,
) -> tuple[str, str, str, str]:
    if not entrada_str or not entrada_str.strip():
        return "", "", "", ""

    entrada = utils.parse_hora(entrada_str)
    intervalo_inicio = utils.parse_hora(intervalo_inicio_str)
    intervalo_fim = utils.parse_hora(intervalo_fim_str)

    if variar:
        entrada, intervalo_inicio, intervalo_fim, saida = utils.desfazer_horario_britanico(
            entrada,
            intervalo_inicio,
            intervalo_fim,
            minutos_range,
            variar_entrada=variar_entrada,
        )
        return (
            utils.formatar_hora(entrada),
            utils.formatar_hora(intervalo_inicio),
            utils.formatar_hora(intervalo_fim),
            utils.formatar_hora(saida),
        )

    inicio_str, fim_str, saida_str = calcular_saida_8h(
        entrada_str,
        intervalo_inicio_str,
        intervalo_fim_str,
    )
    return (
        entrada.strftime("%H:%M"),
        inicio_str,
        fim_str,
        saida_str,
    )

def gerar_overlay(csv_path: str, pdf_overlay: str, configs: dict, pdf_entrada: str, on_progress=None):
    report(on_progress, "Detectando grade da folha ponto", 0.35)
    grade = detectar_grade(pdf_entrada)
    horarios = _horarios_iniciais(grade)

    report(on_progress, "Gerando overlay do PDF", 0.4)

    c = _novo_canvas(pdf_overlay, grade)

    tipo_assinatura, texto_assinatura, caminho_assinatura, *_ = get_configs_values(configs)

    linhas = list(ler_csv_horas(csv_path))
    total = len(linhas)

    for i, (dia, entrada, inicio_intercalo, fim_intercalo, saida) in enumerate(linhas):
        if not dia.strip().isdigit():
            continue

        dia_n = int(dia)
        _registrar_horario(horarios, dia_n, entrada, inicio_intercalo, fim_intercalo, saida)
        horas = horarios[dia_n]
        draw_linha_dia(
            c,
            grade,
            dia_n,
            horas["entrada"],
            horas["intervalo_saida"],
            horas["intervalo_entrada"],
            horas["saida"],
            tipo_assinatura,
            texto_assinatura,
            caminho_assinatura,
        )

        progress = 0.4 + (i / max(total, 1)) * 0.4
        report(on_progress, f"Processando registros ({i+1}/{total})", progress)

    c.save()
    report(on_progress, "Overlay gerado", 0.85)
    return grade, horarios

def gerar_overlay_efetivado(csv_path: str, pdf_overlay: str, configs: dict, pdf_entrada: str, on_progress=None):
    report(on_progress, "Detectando grade da folha ponto", 0.35)
    grade = detectar_grade(pdf_entrada)
    horarios = _horarios_iniciais(grade)

    report(on_progress, "Gerando overlay do PDF para Efetivado", 0.4)

    c = _novo_canvas(pdf_overlay, grade)

    tipo_assinatura, texto_assinatura, caminho_assinatura, _, _, intervalo_inicio, intervalo_fim = get_configs_values(configs)
    variar, minutos_range = get_variacao_britanico(configs)

    linhas = list(ler_csv_horas(csv_path))
    total = len(linhas)

    for i, (dia, entrada, _, _, _) in enumerate(linhas):
        if not dia.strip().isdigit():
            continue

        if entrada.strip():
            entrada_str, inicio_intervalo, fim_intervalo, saida_str = horarios_do_dia(
                entrada,
                variar,
                minutos_range,
                intervalo_inicio,
                intervalo_fim,
                variar_entrada=False,
            )
            dia_n = int(dia)
            _registrar_horario(horarios, dia_n, entrada_str, inicio_intervalo, fim_intervalo, saida_str)
            horas = horarios[dia_n]
            draw_linha_dia(
                c,
                grade,
                dia_n,
                horas["entrada"],
                horas["intervalo_saida"],
                horas["intervalo_entrada"],
                horas["saida"],
                tipo_assinatura,
                texto_assinatura,
                caminho_assinatura,
                forcar_intervalo=True,
            )

        progress = 0.4 + (i / max(total, 1)) * 0.4
        report(on_progress, f"Processando registros ({i+1}/{total})", progress)

    c.save()
    report(on_progress, "Overlay gerado", 0.85)
    return grade, horarios

def gerar_overlay_sem_csv(pdf_overlay: str, configs: dict, mes: int, ano: int, pdf_entrada: str, on_progress=None):
    report(on_progress, "Detectando grade da folha ponto", 0.35)
    grade = detectar_grade(pdf_entrada)
    horarios = _horarios_iniciais(grade)

    report(on_progress, "Gerando overlay do PDF (sem CSV)", 0.4)

    c = _novo_canvas(pdf_overlay, grade)

    tipo_assinatura, texto_assinatura, caminho_assinatura, valor_central_entrada, _, intervalo_inicio, intervalo_fim = get_configs_values(configs)
    variar, minutos_range = get_variacao_britanico(configs)

    dias_no_mes = monthrange(ano, mes)[1]

    for dia in range(1, dias_no_mes + 1):
        data = date(ano, mes, dia)

        if utils.is_weekend(data) or utils.is_feriado(data):
            continue

        entrada, inicio_intervalo, fim_intervalo, saida = horarios_do_dia(
            valor_central_entrada,
            variar,
            minutos_range,
            intervalo_inicio,
            intervalo_fim,
        )
        _registrar_horario(horarios, dia, entrada, inicio_intervalo, fim_intervalo, saida)
        horas = horarios[dia]
        draw_linha_dia(
            c,
            grade,
            dia,
            horas["entrada"],
            horas["intervalo_saida"],
            horas["intervalo_entrada"],
            horas["saida"],
            tipo_assinatura,
            texto_assinatura,
            caminho_assinatura,
            forcar_intervalo=True,
        )

        progress = 0.4 + (dia / max(dias_no_mes, 1)) * 0.4
        report(on_progress, f"Processando dias ({dia}/{dias_no_mes})", progress)

    c.save()
    report(on_progress, "Overlay gerado", 0.85)
    return grade, horarios

def merge_pdfs(pdf_base: str, pdf_overlay: str, pdf_saida: str, on_progress=None):
    report(on_progress, "Mesclando PDFs", 0.9)

    original = PdfReader(pdf_base)
    overlay = PdfReader(pdf_overlay)

    writer = PdfWriter()

    for i, page in enumerate(original.pages):
        if i == 0 and overlay.pages:
            page.merge_page(overlay.pages[0])
        writer.add_page(page)

    with open(pdf_saida, "wb") as f:
        writer.write(f)

    report(on_progress, "PDF finalizado", 1.0)


def main(pdf_entrada: str, on_progress=None) -> SessaoEdicao:
    report(on_progress, "Lendo configurações", 0.05)

    config = ler_config()
    csv_path = config.get("arquivos", {}).get("csv_horas", CSV_HORAS)
    if csv_path and not os.path.isabs(csv_path):
        csv_path = os.path.join(BASE_DIR, csv_path)

    report(on_progress, "Lendo CSV de horas", 0.2)

    grade, horarios = gerar_overlay(csv_path, PDF_OVERLAY, config, pdf_entrada, on_progress)
    merge_pdfs(pdf_entrada, PDF_OVERLAY, PDF_SAIDA, on_progress)
    return _montar_sessao(grade, pdf_entrada, horarios, config)

def main_efetivado(pdf_entrada: str, on_progress=None) -> SessaoEdicao:
    report(on_progress, "Lendo configurações", 0.05)

    config = ler_config()
    csv_path = config.get("arquivos", {}).get("csv_horas", CSV_HORAS)
    if csv_path and not os.path.isabs(csv_path):
        csv_path = os.path.join(BASE_DIR, csv_path)

    report(on_progress, "Lendo CSV de horas do CCU", 0.2)

    grade, horarios = gerar_overlay_efetivado(csv_path, PDF_OVERLAY, config, pdf_entrada, on_progress)
    merge_pdfs(pdf_entrada, PDF_OVERLAY, PDF_SAIDA, on_progress)
    return _montar_sessao(grade, pdf_entrada, horarios, config)

def main_sem_csv(pdf_entrada: str, mes: int, ano: int, on_progress=None) -> SessaoEdicao:
    report(on_progress, "Lendo configurações", 0.05)

    config = ler_config()

    report(on_progress, "Gerando overlay sem CSV", 0.2)

    grade, horarios = gerar_overlay_sem_csv(PDF_OVERLAY, config, mes, ano, pdf_entrada, on_progress)
    merge_pdfs(pdf_entrada, PDF_OVERLAY, PDF_SAIDA, on_progress)
    return _montar_sessao(grade, pdf_entrada, horarios, config)
