import subprocess
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)

ROBOT_DIR = BASE_DIR
ROBOT_FILE = os.path.join(ROBOT_DIR, "CCU.robot")
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "results")

PROGRESS_MAP = {
    "STEP: Logando na intranet": ("Logando na intranet", 0.15),
    "STEP: Login concluído": ("Login concluído", 0.20),
    "STEP: Buscando mês": ("Buscando mês especificado", 0.25),
    "STEP: Extraindo dados": ("Extraindo dados", 0.30),
    "STEP: Gerando CSV": ("Gerando CSV", 0.40),
    "STEP: CSV criado com sucesso": ("Processo finalizado", 0.45),
}



def report(cb, msg, value):
    if cb:
        cb(msg, value)


def executar_robot(data_param: str, on_progress=None):
    report(on_progress, "Preparando execução do robô", 0.05)

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        report(on_progress, "Iniciando Robot Framework", 0.10)

        robot_cmd = [
            sys.executable,
            "-m", "robot",
            "--loglevel", "INFO",
            "--console", "verbose",
            "--outputdir", OUTPUT_DIR,
            "--variable", f"DATA_PARAM:{data_param}",
            ROBOT_FILE,
        ]


        process = subprocess.Popen(
            robot_cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            line = line.strip()

            for key, (msg, val) in PROGRESS_MAP.items():
                if key in line:
                    report(on_progress, msg, val)
                    break

        process.wait()

        if process.returncode != 0:
            raise RuntimeError(f"Robot falhou com código {process.returncode}")

        report(on_progress, "Coleta finalizada", 0.5)

    except Exception as e:
        report(on_progress, f"Erro ao executar robô: {e}", 0.0)
        raise


if __name__ == "__main__":
    executar_robot(time.strftime("%m/%Y"))