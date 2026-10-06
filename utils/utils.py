import os
import sys
import tempfile
import random
from datetime import datetime, time, timedelta, date
from pdf2image import convert_from_path
from PIL import Image
from typing import List

feriados: set[date] = set()
_feriados_carregados = False

def load_feriados():
    """Carrega feriados do arquivo CSV e retorna um conjunto de datas"""
    global _feriados_carregados
    _feriados_carregados = True
    base_dir = os.path.dirname(os.path.abspath(__file__))
    feriados_path = os.path.join(base_dir, "..", "configs", "feriados.csv")

    if not os.path.exists(feriados_path):
        return feriados

    with open(feriados_path, "r", encoding="utf-8") as f:
        next(f)
        for line in f:
            parts = line.strip().split(",")
            if parts:
                try:
                    d = datetime.fromisoformat(parts[0]).date()
                    feriados.add(d)
                except ValueError:
                    continue
    return feriados

def juntar_imagens_em_uma(
    imagens: List[str],
    output_path: str,
    direcao: str = "vertical"
) -> str:
    """
    Junta múltiplas imagens em uma única imagem.

    :param imagens: lista de caminhos das imagens
    :param output_path: caminho da imagem final (png/jpg)
    :param direcao: "vertical" ou "horizontal"
    :return: caminho da imagem gerada
    """
    imgs = [Image.open(img).convert("RGB") for img in imagens]

    if direcao == "vertical":
        largura = max(img.width for img in imgs)
        altura = sum(img.height for img in imgs)

        imagem_final = Image.new("RGB", (largura, altura), "white")

        y_offset = 0
        for img in imgs:
            imagem_final.paste(img, (0, y_offset))
            y_offset += img.height

    elif direcao == "horizontal":
        largura = sum(img.width for img in imgs)
        altura = max(img.height for img in imgs)

        imagem_final = Image.new("RGB", (largura, altura), "white")

        x_offset = 0
        for img in imgs:
            imagem_final.paste(img, (x_offset, 0))
            x_offset += img.width
    else:
        raise ValueError("direcao deve ser 'vertical' ou 'horizontal'")

    imagem_final.save(output_path)
    return output_path


def pdf_para_imagens(pdf_path: str) -> tuple[list[str], str]:
    """
    Converte um PDF em imagens PNG temporárias.
    Retorna (lista_de_caminhos, pasta_temporaria)
    """
    temp_dir = tempfile.mkdtemp(prefix="pdf_preview_")

    imagens = convert_from_path(
        pdf_path,
        dpi=150,
        fmt="png",
        output_folder=temp_dir,
        paths_only=True
    )

    return imagens, temp_dir

def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python script.py <caminho_pdf_ou_imagem> [saida.png]")
        sys.exit(1)

    entrada = sys.argv[1]
    saida = sys.argv[2] if len(sys.argv) > 2 else "imagem_final.png"

    # Caso seja PDF
    if entrada.lower().endswith(".pdf"):
        imagens, temp_dir = pdf_para_imagens(entrada)
        print(f"PDF convertido em {len(imagens)} imagens temporárias em {temp_dir}")

        juntar_imagens_em_uma(
            imagens,
            saida,
            direcao="vertical"
        )

    # Caso seja imagem única ou pasta
    else:
        if os.path.isdir(entrada):
            imagens = sorted(
                os.path.join(entrada, f)
                for f in os.listdir(entrada)
                if f.lower().endswith((".png", ".jpg", ".jpeg"))
            )
        else:
            imagens = [entrada]

        if not imagens:
            raise ValueError("Nenhuma imagem encontrada")

        juntar_imagens_em_uma(
            imagens,
            saida,
            direcao="vertical"
        )

    print(f"Imagem final gerada em: {saida}")


if __name__ == "__main__":
    main()

def parse_hora(valor: str) -> time:
    if not valor:
        raise ValueError("Hora vazia")

    valor = valor.strip()

    if "T" in valor or " " in valor:
        return datetime.fromisoformat(valor).time()

    parts = valor.split(":")

    if len(parts) >= 2:
        h = int(parts[0])
        m = int(parts[1])
        return time(h, m)

    raise ValueError(f"Formato de hora inválido: {valor}")

def jitter_time(base: time, minutos_range: int) -> time:
    base_dt = datetime.combine(datetime.today(), base)
    delta = random.randint(-minutos_range, minutos_range)
    return (base_dt + timedelta(minutes=delta)).time()


def _as_dt(hora: time) -> datetime:
    return datetime.combine(date.today(), hora)


def add_minutes(hora: time, minutos: int) -> time:
    return (_as_dt(hora) + timedelta(minutes=minutos)).time()


def jitter_para_cima(base: time, minutos_range: int) -> time:
    if minutos_range <= 0:
        return base
    return add_minutes(base, random.randint(1, minutos_range))


def formatar_hora(hora: time) -> str:
    return hora.strftime("%H:%M")


def normalizar_hora_digitada(valor: str) -> str:
    texto = (valor or "").strip()
    if not texto:
        return ""

    parts = texto.split(":")
    if len(parts) != 2:
        raise ValueError("Use o formato HH:MM")

    hora = int(parts[0])
    minuto = int(parts[1])
    if hora < 0 or hora > 23 or minuto < 0 or minuto > 59:
        raise ValueError("Use o formato HH:MM")
    return f"{hora:02d}:{minuto:02d}"


def desfazer_horario_britanico(
    entrada: time,
    intervalo_inicio: time,
    intervalo_fim: time,
    minutos_range: int,
    variar_entrada: bool = True,
) -> tuple[time, time, time, time]:
    """
    Mantém o intervalo configurado e gera jornada de pelo menos 8h,
    com poucos minutos extras na saída. A entrada só varia se variar_entrada=True.
    """
    if minutos_range <= 0:
        saida = (_as_dt(entrada) + (_as_dt(intervalo_fim) - _as_dt(intervalo_inicio)) + timedelta(hours=8)).time()
        return entrada, intervalo_inicio, intervalo_fim, saida

    entrada_var = jitter_para_cima(entrada, minutos_range) if variar_entrada else entrada
    inicio_var = intervalo_inicio
    fim_var = intervalo_fim

    if _as_dt(fim_var) <= _as_dt(inicio_var):
        fim_var = add_minutes(inicio_var, 120)

    extra = timedelta(minutes=random.randint(1, minutos_range))
    manha = _as_dt(inicio_var) - _as_dt(entrada_var)
    restante = timedelta(hours=8) + extra - manha
    if restante < timedelta(minutes=1):
        restante = timedelta(minutes=random.randint(1, minutos_range))

    saida_var = (_as_dt(fim_var) + restante).time()
    return entrada_var, inicio_var, fim_var, saida_var


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5

def is_feriado(d: date) -> bool:
    global _feriados_carregados
    if not _feriados_carregados:
        load_feriados()
    return d in feriados
