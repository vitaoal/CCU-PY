import asyncio
import flet as ft
import pdf_generator as pg
import robot_utils.robot_runner as rr
import utils.utils as utils
import os
from styles.style import TITLE_STYLE, PAGE_PADDING
from datetime import datetime
from dateutil.relativedelta import relativedelta
from views.components.pdf_viewer import PdfViewer

pdf_entrada = {"path": None}

def relatorio_view(page: ft.Page) -> ft.Control:

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

    def mostrar_dialog(titulo, mensagem, sucesso=True):
        icon, title, text = dialog.content.content.controls[:3]

        icon.name = ft.Icons.CHECK_CIRCLE if sucesso else ft.Icons.ERROR
        icon.color = ft.Colors.GREEN_600 if sucesso else ft.Colors.RED_600

        title.value = titulo
        text.value = mensagem

        page.open(dialog)

    # ---------------- FILE PICKER ----------------

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

    def selecionar_pdf(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        pdf_entrada["path"] = e.files[0].path
        mostrar_dialog("PDF selecionado", os.path.basename(pdf_entrada["path"]))

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

    def atualizar_progresso(msg, value):
        progress_text.value = msg
        progress_bar.value = value
        page.update()

    # ---------------- PDF VIEWER ----------------

    pdf_viewer = PdfViewer(
        page=page,
        pdf_saida_path_getter=lambda: pg.PDF_SAIDA,
        on_reload=lambda e: gerar_e_mostrar(e),
    )

    # ---------------- AÇÕES ----------------

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



    def gerar_e_mostrar(e):

        if not pdf_entrada["path"]:
            mostrar_dialog(
                "PDF não selecionado",
                "Selecione um PDF de entrada antes de gerar o relatório.",
                sucesso=False
            )
            return

        progress_container.visible = True
        progress_text.visible = True
        progress_bar.visible = True
        progress_bar.value = 0
        page.update()

        async def tarefa():

            await asyncio.to_thread(
                rr.executar_robot,
                mes_selecionado["value"],
                on_progress=atualizar_progresso
            )
            
            sessao = await asyncio.to_thread(
                pg.main,
                pdf_entrada=pdf_entrada["path"],
                on_progress=atualizar_progresso
            )

            if not os.path.exists(pg.PDF_SAIDA):
                return

            imagens, _ = utils.pdf_para_imagens(pg.PDF_SAIDA)


            progress_container.visible = False
            page.update()

            pdf_viewer.load_images(imagens, sessao=sessao)

        page.run_task(tarefa)

    # ---------------- BOTÃO ----------------

    row_generate_button = ft.Container(
        padding=PAGE_PADDING,
        content=ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                mes_dropdown,
                ft.ElevatedButton("Gerar Relatório PDF", on_click=gerar_e_mostrar),
                ft.ElevatedButton(
                    "Selecionar PDF de Entrada",
                    on_click=lambda e: pdf_picker.pick_files(
                        allow_multiple=False,
                        allowed_extensions=["pdf"]
                    )
                )
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
                ft.Text("Relatório", style=TITLE_STYLE),
                row_generate_button,
                progress_container,
                *pdf_viewer.get_controls(),
            ],
        ),
    )
