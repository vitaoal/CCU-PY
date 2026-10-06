import asyncio
import os

import flet as ft

from styles.style import BASE_WIDTH, PAGE_HEIGHT_ESTIMADA
from utils import utils

_LABELS_COLUNA = {
    "entrada": "Entrada",
    "intervalo_saida": "Intervalo saída",
    "intervalo_entrada": "Intervalo entrada",
    "saida": "Saída",
}

_PADDING_PAGINA = 12


class PdfViewer:
    def __init__(
        self,
        page: ft.Page,
        pdf_saida_path_getter,
        on_reload,
    ):
        self.page = page
        self.get_pdf_path = pdf_saida_path_getter
        self.on_reload = on_reload
        self.zoom = 1.0
        self.sessao = None
        self.image_paths: list[str] = []
        self._editando = False
        self._dialog_edicao = None

        self._build()

    def _build(self):
        self.contador_paginas = ft.Text("0 / 0")
        self.hint_edicao = ft.Text(
            "Clique em um horário para editar",
            size=12,
            color=ft.Colors.GREY_400,
            visible=False,
        )

        self.viewer_column = ft.Column(
            spacing=30,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            on_scroll=self._update_page_counter,
        )

        self.viewer_container = ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            bgcolor=ft.Colors.GREY_300,
            padding=30,
            content=self.viewer_column,
            visible=False,
        )

        self.toolbar = ft.Container(
            bgcolor=ft.Colors.GREY_900,
            padding=10,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Row(
                        controls=[
                            ft.IconButton(ft.Icons.ZOOM_OUT, on_click=self.zoom_out),
                            ft.IconButton(ft.Icons.ZOOM_IN, on_click=self.zoom_in),
                            self.hint_edicao,
                        ]
                    ),
                    self.contador_paginas,
                    ft.Row(
                        controls=[
                            ft.IconButton(ft.Icons.REFRESH, on_click=self.reload),
                            ft.IconButton(ft.Icons.DOWNLOAD, on_click=self.download),
                        ]
                    ),
                ],
            ),
        )

    def get_controls(self):
        return [
            self.toolbar,
            self.viewer_container,
        ]

    def show(self):
        self.viewer_container.visible = True
        self.page.update()

    def hide(self):
        self.viewer_container.visible = False
        self.page.update()

    def clear(self):
        self.viewer_column.controls.clear()
        self.contador_paginas.value = "0 / 0"
        self.page.update()

    def load_images(self, image_paths: list[str], sessao=None):
        if sessao is not None or not image_paths:
            self.sessao = sessao

        self.image_paths = list(image_paths or [])
        self.hint_edicao.visible = self.sessao is not None
        self._render_pages()

    def _display_size(self) -> tuple[int, int]:
        width = max(int(BASE_WIDTH * self.zoom) - _PADDING_PAGINA * 2, 50)
        if self.sessao:
            page_w, page_h = self.sessao.grade.page_size
            height = int(width * (page_h / page_w))
        else:
            height = int(width * 1.414)
        return width, height

    def _render_pages(self):
        self.viewer_column.controls.clear()

        if not self.image_paths:
            self.contador_paginas.value = "0 / 0"
            self.hint_edicao.visible = False
            self.page.update()
            return

        width, height = self._display_size()

        for i, img_path in enumerate(self.image_paths):
            image = ft.Image(
                src=img_path,
                width=width,
                height=height,
                fit=ft.ImageFit.FILL,
            )
            content = image
            if i == 0 and self.sessao is not None:
                content = ft.GestureDetector(
                    content=image,
                    on_tap_down=self._on_tap_pagina1,
                )

            self.viewer_column.controls.append(
                ft.Container(
                    width=width + _PADDING_PAGINA * 2,
                    bgcolor=ft.Colors.WHITE,
                    padding=_PADDING_PAGINA,
                    border_radius=4,
                    shadow=ft.BoxShadow(
                        blur_radius=15,
                        spread_radius=1,
                        color=ft.Colors.BLACK26,
                        offset=ft.Offset(0, 5),
                    ),
                    content=content,
                )
            )

        self.contador_paginas.value = f"1 / {len(self.image_paths)}"
        self.show()

    def zoom_in(self, e=None):
        self.zoom += 0.1
        self._apply_zoom()

    def zoom_out(self, e=None):
        self.zoom = max(0.1, self.zoom - 0.1)
        self._apply_zoom()

    def reload(self, e=None):
        self.sessao = None
        if callable(self.on_reload):
            self.on_reload(e)

    def download(self, e=None):
        pdf_path = self.get_pdf_path()
        if not pdf_path or not os.path.exists(pdf_path):
            return

        if not hasattr(self, "_file_picker"):
            self._file_picker = ft.FilePicker(
                on_result=lambda ev: self._save_pdf(ev, pdf_path)
            )
            self.page.overlay.append(self._file_picker)
            self.page.update()

        self._file_picker.get_directory_path()

    def _apply_zoom(self):
        if self.image_paths:
            self._render_pages()
            return
        for container in self.viewer_column.controls:
            container.width = int(BASE_WIDTH * self.zoom)
        self.page.update()

    def _update_page_counter(self, e: ft.ScrollEvent):
        if not self.viewer_container.visible:
            return

        page_size = PAGE_HEIGHT_ESTIMADA + self.viewer_column.spacing
        current_page = int(e.pixels // page_size) + 1
        total = len(self.viewer_column.controls)

        current_page = max(1, min(current_page, total))
        self.contador_paginas.value = f"{current_page} / {total}"
        self.page.update()

    def _save_pdf(self, e: ft.FilePickerResultEvent, pdf_path: str):
        if not e.path:
            return

        destino = os.path.join(e.path, os.path.basename(pdf_path))
        with open(pdf_path, "rb") as o, open(destino, "wb") as s:
            s.write(o.read())

    def _tap_xy(self, e) -> tuple[float, float] | None:
        if hasattr(e, "local_x") and e.local_x is not None:
            return float(e.local_x), float(e.local_y)
        pos = getattr(e, "local_position", None)
        if pos is not None:
            return float(pos.x), float(pos.y)
        return None

    def _on_tap_pagina1(self, e):
        if not self.sessao or self._editando:
            return

        xy = self._tap_xy(e)
        if xy is None:
            return

        local_x, local_y = xy
        disp_w, disp_h = self._display_size()
        if disp_w <= 0 or disp_h <= 0:
            return

        page_w, page_h = self.sessao.grade.page_size
        pdf_x = (local_x / disp_w) * page_w
        pdf_y = page_h - (local_y / disp_h) * page_h

        alvo = self.sessao.hit_test(pdf_x, pdf_y)
        if not alvo:
            return

        dia, coluna = alvo
        self._abrir_editor(dia, coluna)

    def _abrir_editor(self, dia: int, coluna: str):
        atual = self.sessao.horarios.get(dia, {}).get(coluna, "")
        campo = ft.TextField(
            label=_LABELS_COLUNA.get(coluna, coluna),
            value=atual,
            hint_text="HH:MM  (vazio apaga)",
            autofocus=True,
        )
        erro = ft.Text("", color=ft.Colors.RED_400, size=12)

        def fechar(_e=None):
            if self._dialog_edicao:
                self.page.close(self._dialog_edicao)

        def confirmar(_e=None):
            try:
                valor = utils.normalizar_hora_digitada(campo.value or "")
            except ValueError:
                erro.value = "Use o formato HH:MM"
                self.page.update()
                return

            campo.disabled = True
            self.page.update()
            self.page.run_task(self._aplicar_edicao, dia, coluna, valor)

        campo.on_submit = confirmar

        self._dialog_edicao = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"Dia {dia}"),
            content=ft.Column([campo, erro], tight=True, width=260, spacing=8),
            actions=[
                ft.TextButton("Cancelar", on_click=fechar),
                ft.ElevatedButton("Salvar", on_click=confirmar),
            ],
        )
        self.page.open(self._dialog_edicao)

    async def _aplicar_edicao(self, dia: int, coluna: str, valor: str):
        if not self.sessao:
            return

        self._editando = True
        try:
            await asyncio.to_thread(self.sessao.aplicar, dia, coluna, valor)
            imagens, _ = await asyncio.to_thread(
                utils.pdf_para_imagens,
                self.sessao.pdf_saida,
            )
            if self._dialog_edicao:
                self.page.close(self._dialog_edicao)
            self.load_images(imagens, sessao=self.sessao)
        except Exception as ex:
            if self._dialog_edicao:
                self.page.close(self._dialog_edicao)
            dlg_erro = ft.AlertDialog(
                title=ft.Text("Erro ao editar"),
                content=ft.Text(str(ex)),
            )
            dlg_erro.actions = [
                ft.TextButton("OK", on_click=lambda e: self.page.close(dlg_erro)),
            ]
            self.page.open(dlg_erro)
        finally:
            self._editando = False
            self.page.update()
