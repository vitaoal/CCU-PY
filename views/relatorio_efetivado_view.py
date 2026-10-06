import asyncio
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
import flet as ft

import pdf_generator as pg
import robot_utils.robot_runner as rr
from styles.style import TITLE_STYLE, PAGE_PADDING
from utils import utils
from views.components.pdf_viewer import PdfViewer

pdf_entrada = {"path": None}


def relatorio_efetivado_view(page: ft.Page) -> ft.Control:

    # ---------------- DIALOG ----------------

    def criar_dialog():
        return ft.AlertDialog(
            modal=True,
            content=ft.Container(
                width=380,
                padding=20,
                content=ft.Column(
                    tight=True,
                    spacing=16,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Icon(size=48),
                        ft.Text(size=20, weight=ft.FontWeight.BOLD),
                        ft.Text(size=14, color=ft.Colors.GREY_700),
                        ft.Divider(height=1),
                        ft.ElevatedButton("OK", on_click=lambda e: page.close(dialog)),
                    ],
                ),
            ),
        )

    dialog = criar_dialog()

    def mostrar_dialog(titulo: str, mensagem: str, sucesso: bool = True):
        icon, title, text = dialog.content.content.controls[:3]

        icon.name = ft.Icons.CHECK_CIRCLE if sucesso else ft.Icons.ERROR
        icon.color = ft.Colors.GREEN_600 if sucesso else ft.Colors.RED_600

        title.value = titulo
        text.value = mensagem

        page.open(dialog)

    # ---------------- FILE PICKER ----------------

    pdf_nome_text = ft.Text(
        os.path.basename(pdf_entrada["path"]) if pdf_entrada["path"] else "Nenhum PDF selecionado",
        size=13,
        color=ft.Colors.GREY_400,
    )

    def selecionar_pdf(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        pdf_entrada["path"] = e.files[0].path
        pdf_nome_text.value = os.path.basename(pdf_entrada["path"])
        mostrar_dialog("PDF Selecionado", os.path.basename(pdf_entrada["path"]))
        page.update()

    def selecionar_diretorio(e: ft.FilePickerResultEvent):
        if not e.path:
            return
        try:
            destino = os.path.join(e.path, os.path.basename(pg.PDF_SAIDA))
            with open(pg.PDF_SAIDA, "rb") as o, open(destino, "wb") as s:
                s.write(o.read())
            mostrar_dialog("Sucesso", "PDF salvo com sucesso.")
        except Exception as ex:
            mostrar_dialog("Erro", str(ex), False)

    pdf_picker = ft.FilePicker(on_result=selecionar_pdf)
    file_picker = ft.FilePicker(on_result=selecionar_diretorio)
    page.overlay.append(file_picker)
    page.overlay.append(pdf_picker)

    # ---------------- PROGRESSO ----------------

    progress_text = ft.Text("", visible=False)
    progress_bar = ft.ProgressBar(width=420, visible=False)

    progress_container = ft.Container(
        alignment=ft.Alignment(0, 0),
        visible=False,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[progress_text, progress_bar],
        ),
    )

    def atualizar_progresso(msg: str, value: float):
        progress_text.value = msg
        progress_bar.value = value
        page.update()

    # ---------------- AÇÕES & MESES ----------------

    def gerar_meses():
        hoje = datetime.today()
        meses = []
        for i in range(0, 7):
            d = hoje - relativedelta(months=i)
            meses.append(d.strftime("%m/%Y"))
        return meses

    mes_selecionado = {"value": None}

    mes_dropdown = ft.Dropdown(
        width=200,
        label="Mês/Ano",
        options=[ft.dropdown.Option(m) for m in gerar_meses()],
        value=gerar_meses()[0],
        on_change=lambda e: mes_selecionado.update(value=e.control.value),
    )

    mes_selecionado["value"] = mes_dropdown.value

    # ---------------- GERAR E MOSTRAR ----------------

    def gerar_e_mostrar(e=None):
        if not pdf_entrada["path"]:
            mostrar_dialog(
                "PDF não selecionado",
                "Selecione um PDF de entrada antes de gerar o relatório.",
                sucesso=False,
            )
            return

        try:
            mes_str, ano_str = mes_selecionado["value"].split("/")
            mes = int(mes_str)
            ano = int(ano_str)
        except Exception:
            mes = datetime.today().month
            ano = datetime.today().year

        progress_container.visible = True
        progress_text.visible = True
        progress_bar.visible = True
        progress_bar.value = 0
        page.update()

        async def tarefa():
            try:
                # 1. Executa o robô CCU para extrair os horários reais do mês selecionado
                await asyncio.to_thread(
                    rr.executar_robot,
                    mes_selecionado["value"],
                    on_progress=atualizar_progresso,
                )

                # 2. Gera o PDF para Efetivado pegando o horário de entrada do CCU
                sessao = await asyncio.to_thread(
                    pg.main_efetivado,
                    pdf_entrada=pdf_entrada["path"],
                    on_progress=atualizar_progresso,
                )

                if not os.path.exists(pg.PDF_SAIDA):
                    mostrar_dialog("Erro", "Falha ao gerar o PDF de saída.", sucesso=False)
                    return

                # 3. Renderiza imagens para pré-visualização
                imagens, _ = await asyncio.to_thread(
                    utils.pdf_para_imagens,
                    pg.PDF_SAIDA,
                )

                progress_container.visible = False
                page.update()

                pdf_viewer.load_images(imagens, sessao=sessao)
            except Exception as ex:
                progress_container.visible = False
                page.update()
                mostrar_dialog("Erro ao gerar relatório", str(ex), sucesso=False)

        page.run_task(tarefa)

    # ---------------- PDF VIEWER ----------------

    pdf_viewer = PdfViewer(
        page=page,
        pdf_saida_path_getter=lambda: pg.PDF_SAIDA,
        on_reload=lambda e: gerar_e_mostrar(e),
    )

    # ---------------- BOTÕES ----------------

    row_generate_button = ft.Container(
        padding=PAGE_PADDING,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=[
                        mes_dropdown,
                        ft.ElevatedButton(
                            "Gerar Relatório Efetivado",
                            on_click=lambda e: gerar_e_mostrar(e),
                        ),
                        ft.ElevatedButton(
                            "Selecionar PDF de Entrada",
                            on_click=lambda e: pdf_picker.pick_files(
                                allow_multiple=False,
                                allowed_extensions=["pdf"],
                            ),
                        ),
                    ],
                ),
                pdf_nome_text,
            ],
        ),
    )

    # ---------------- VIEW FINAL ----------------

    return ft.Container(
        expand=True,
        padding=PAGE_PADDING,
        content=ft.Column(
            expand=True,
            spacing=0,
            controls=[
                ft.Text("Relatório Efetivado", style=TITLE_STYLE),
                row_generate_button,
                progress_container,
                *pdf_viewer.get_controls(),
            ],
        ),
    )
