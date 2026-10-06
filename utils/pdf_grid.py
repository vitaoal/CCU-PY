from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTLine, LTRect, LTTextContainer

_MIN_LINE = 100
_CLUSTER_TOL = 1.5
_COLUNAS_ESPERADAS = (
    "dia",
    "entrada",
    "intervalo_saida",
    "intervalo_entrada",
    "saida",
    "visto",
    "autorizacao",
)


@dataclass
class GradeFolhaPonto:
    page_size: tuple[float, float]
    columns: dict[str, tuple[float, float]]
    rows: dict[int, tuple[float, float]]
    occupied: set[tuple[int, str]] = field(default_factory=set)

    COLUNAS_HORARIO = (
        "entrada",
        "intervalo_saida",
        "intervalo_entrada",
        "saida",
    )

    def celula(
        self,
        dia: int,
        coluna: str,
        ignorar_ocupada: bool = False,
    ) -> tuple[float, float, float, float] | None:
        if dia not in self.rows or coluna not in self.columns:
            return None
        if not ignorar_ocupada and (dia, coluna) in self.occupied:
            return None
        x0, x1 = self.columns[coluna]
        y0, y1 = self.rows[dia]
        return x0, x1, y0, y1

    def hit_test_horario(self, x: float, y: float) -> tuple[int, str] | None:
        for dia, (y0, y1) in self.rows.items():
            if y < y0 or y > y1:
                continue
            for coluna in self.COLUNAS_HORARIO:
                x0, x1 = self.columns[coluna]
                if x0 <= x <= x1:
                    if coluna == "entrada" and (dia, "entrada") in self.occupied:
                        return None
                    return dia, coluna
            return None
        return None


def _norm(texto: str) -> str:
    nfd = unicodedata.normalize("NFD", texto)
    return "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn").lower().strip()


def _cluster(valores: list[float], tol: float = _CLUSTER_TOL) -> list[float]:
    if not valores:
        return []
    ordenados = sorted(valores)
    grupos: list[list[float]] = [[ordenados[0]]]
    for valor in ordenados[1:]:
        if valor - grupos[-1][-1] <= tol:
            grupos[-1].append(valor)
        else:
            grupos.append([valor])
    return [sum(grupo) / len(grupo) for grupo in grupos]


def _iter_elements(container):
    yield container
    if hasattr(container, "__iter__"):
        for child in container:
            yield from _iter_elements(child)


def _coletar_geometria(page):
    texts: list[tuple[float, float, float, float, str]] = []
    xs: list[float] = []
    ys: list[float] = []

    for el in _iter_elements(page):
        if isinstance(el, LTTextContainer):
            continue
        if hasattr(el, "get_text") and not hasattr(el, "__iter__"):
            texto = el.get_text().strip()
            if texto:
                texts.append((el.x0, el.y0, el.x1, el.y1, texto))
            continue

        if isinstance(el, LTLine):
            dx = abs(el.x1 - el.x0)
            dy = abs(el.y1 - el.y0)
            if dy >= _MIN_LINE and dx <= _CLUSTER_TOL * 2:
                xs.append((el.x0 + el.x1) / 2)
            elif dx >= _MIN_LINE and dy <= _CLUSTER_TOL * 2:
                ys.append((el.y0 + el.y1) / 2)
        elif isinstance(el, LTRect):
            dx = abs(el.x1 - el.x0)
            dy = abs(el.y1 - el.y0)
            if dy >= _MIN_LINE and dx <= _CLUSTER_TOL * 3:
                xs.append((el.x0 + el.x1) / 2)
            elif dx >= _MIN_LINE and dy <= _CLUSTER_TOL * 3:
                ys.append((el.y0 + el.y1) / 2)

    # LTTextLine fica dentro de LTTextContainer; percorre de novo só o texto.
    for el in page:
        if not isinstance(el, LTTextContainer):
            continue
        for line in el:
            if not hasattr(line, "get_text"):
                continue
            texto = line.get_text().strip()
            if texto:
                texts.append((line.x0, line.y0, line.x1, line.y1, texto))

    return texts, _cluster(xs), _cluster(ys)


def _coluna_de(xs: list[float], x_centro: float) -> int | None:
    for i in range(len(xs) - 1):
        if xs[i] - _CLUSTER_TOL <= x_centro <= xs[i + 1] + _CLUSTER_TOL:
            return i
    return None


def _nome_coluna(textos_cabecalho: list[str]) -> str | None:
    normas = [_norm(t) for t in textos_cabecalho]
    junto = " ".join(normas)
    if any("visto" in t for t in normas):
        return "visto"
    if any("autoriza" in t for t in normas):
        return "autorizacao"
    if any(t == "dia" for t in normas):
        return "dia"
    if "intervalo" in junto:
        if "saida" in junto:
            return "intervalo_saida"
        if "entrada" in junto:
            return "intervalo_entrada"
        return None
    if any(t == "entrada" for t in normas):
        return "entrada"
    if any(t == "saida" for t in normas):
        return "saida"
    return None


def _identificar_colunas(
    xs: list[float],
    ys: list[float],
    texts: list[tuple[float, float, float, float, str]],
) -> dict[str, tuple[float, float]]:
    if len(xs) < 8:
        raise ValueError(
            f"Grade da folha ponto inválida: esperado 8 linhas verticais, encontrado {len(xs)}."
        )

    ys_desc = sorted(ys, reverse=True)
    if len(ys_desc) < 3:
        raise ValueError("Grade da folha ponto inválida: poucas linhas horizontais.")

    y_topo, y_base_cab = ys_desc[0], ys_desc[1]
    cabecalhos: dict[int, list[str]] = {i: [] for i in range(len(xs) - 1)}

    for x0, y0, x1, y1, texto in texts:
        y_centro = (y0 + y1) / 2
        if not (y_base_cab - 2 <= y_centro <= y_topo + 2):
            continue
        idx = _coluna_de(xs, (x0 + x1) / 2)
        if idx is not None:
            cabecalhos[idx].append(texto)

    colunas: dict[str, tuple[float, float]] = {}
    nomes_por_indice: list[str | None] = []
    for i in range(len(xs) - 1):
        nome = _nome_coluna(cabecalhos[i])
        nomes_por_indice.append(nome)
        if nome:
            colunas[nome] = (xs[i], xs[i + 1])

    faltando = [nome for nome in _COLUNAS_ESPERADAS if nome not in colunas]
    if faltando:
        raise ValueError(
            "Não foi possível identificar as colunas da folha ponto. "
            f"Cabeçalhos lidos: {nomes_por_indice}. Faltando: {faltando}."
        )

    if len(colunas) != 7:
        raise ValueError(
            f"Esperado 7 colunas na folha ponto, encontrado {len(colunas)}: {list(colunas)}."
        )

    return colunas


def _mapear_linhas(
    xs: list[float],
    ys: list[float],
    texts: list[tuple[float, float, float, float, str]],
    colunas: dict[str, tuple[float, float]],
) -> tuple[dict[int, tuple[float, float]], set[tuple[int, str]]]:
    ys_desc = sorted(ys, reverse=True)
    faixas = [(ys_desc[i + 1], ys_desc[i]) for i in range(1, len(ys_desc) - 1)]

    x_dia0, x_dia1 = colunas["dia"]
    rows: dict[int, tuple[float, float]] = {}

    for x0, y0, x1, y1, texto in texts:
        if not texto.isdigit():
            continue
        dia = int(texto)
        if dia < 1 or dia > 31:
            continue
        x_centro = (x0 + x1) / 2
        if not (x_dia0 - 1 <= x_centro <= x_dia1 + 1):
            continue
        y_centro = (y0 + y1) / 2
        for y_bottom, y_top in faixas:
            if y_bottom - 1 <= y_centro <= y_top + 1:
                rows[dia] = (y_bottom, y_top)
                break

    if not rows:
        raise ValueError("Não foi possível mapear os dias da folha ponto às linhas da grade.")

    pares = sorted(colunas.items(), key=lambda item: item[1][0])

    def coluna_por_x(x_centro: float) -> str | None:
        for nome, (cx0, cx1) in pares:
            if cx0 - _CLUSTER_TOL <= x_centro <= cx1 + _CLUSTER_TOL:
                return nome
        return None

    occupied: set[tuple[int, str]] = set()
    for x0, y0, x1, y1, texto in texts:
        y_centro = (y0 + y1) / 2
        x_centro = (x0 + x1) / 2
        dia_linha = None
        for dia, (y_bottom, y_top) in rows.items():
            if y_bottom - 1 <= y_centro <= y_top + 1:
                dia_linha = dia
                break
        if dia_linha is None:
            continue
        coluna = coluna_por_x(x_centro)
        if not coluna or coluna == "dia":
            continue
        occupied.add((dia_linha, coluna))

    return rows, occupied


def posicao_texto_centralizado(
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    texto: str,
    font_name: str,
    font_size: float,
) -> tuple[float, float]:
    from reportlab.pdfbase.pdfmetrics import stringWidth

    largura = stringWidth(texto, font_name, font_size)
    x = x0 + max((x1 - x0 - largura) / 2, 1)
    ascent = font_size * 0.718
    descent = font_size * 0.207
    meio = (y0 + y1) / 2
    y = meio - (ascent - descent) / 2
    return x, y


def caixa_assinatura(
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    max_width: float = 80,
) -> tuple[float, float, float, float]:
    padding = 1.2
    altura = max(y1 - y0 - padding * 2, 8)
    largura_celula = max(x1 - x0 - padding * 2, 8)
    largura = min(max_width, largura_celula)
    x = x0 + (x1 - x0 - largura) / 2
    y = y0 + (y1 - y0 - altura) / 2
    return x, y, largura, altura


def detectar_grade(pdf_path: str) -> GradeFolhaPonto:
    pages = list(
        extract_pages(
            pdf_path,
            page_numbers={0},
            laparams=LAParams(line_margin=0.1, char_margin=1.5),
        )
    )
    if not pages:
        raise ValueError(f"PDF sem páginas: {pdf_path}")

    page = pages[0]
    texts, xs, ys = _coletar_geometria(page)
    colunas = _identificar_colunas(xs, ys, texts)
    rows, occupied = _mapear_linhas(xs, ys, texts, colunas)

    return GradeFolhaPonto(
        page_size=(float(page.width), float(page.height)),
        columns=colunas,
        rows=rows,
        occupied=occupied,
    )
