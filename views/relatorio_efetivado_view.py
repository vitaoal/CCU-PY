import asyncio
import flet as ft
from styles.style import TITLE_STYLE, PAGE_PADDING, DIVIDER
from views.components.pdf_viewer import PdfViewer
import pdf_generator as pg
from utils import utils
import os


def relatorio_efetivado_view(page: ft.Page) -> ft.Control:

    def pdf_teste(e):
        return

    pdf_viewer = PdfViewer(
        page=page,
        pdf_saida_path_getter=lambda: pg.PDF_SAIDA,
        on_reload=pdf_teste,
    )

    async def gerar_e_mostrar(e):
        await asyncio.to_thread(
            pg.main_sem_csv,
            pdf_entrada=pg.PDF_ENTRADA,
            mes=11,
            ano=2026,
            on_progress=lambda msg, prog: print(f"{msg} - {prog*100:.0f}%"),
        )

        if not os.path.exists(pg.PDF_SAIDA):
            return

        imagens, _ = await asyncio.to_thread(
            utils.pdf_para_imagens,
            pg.PDF_SAIDA
        )

        pdf_viewer.load_images(imagens)
        page.update()

    botao_gerar = ft.ElevatedButton(
        "Gerar Relatório Efetivado (Teste)",
        on_click=lambda e: page.run_task(gerar_e_mostrar, e),
    )

    return ft.Container(
        padding=PAGE_PADDING,
        expand=True,
        content=ft.Column(
            expand=True,
            controls=[
                ft.Text("Relatório Efetivado View", style=TITLE_STYLE),
                botao_gerar,
                DIVIDER,
                ft.Container(height=16),
                *pdf_viewer.get_controls(),
            ],
        ),
    )
