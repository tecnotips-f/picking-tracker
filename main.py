import flet as ft
from datetime import datetime
from calculator import calcular_ingreso
from database import DatabaseManager

def main(page: ft.Page):
    page.title = "Control de Picking"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 16
    page.scroll = ft.ScrollMode.ADAPTIVE

    db = DatabaseManager()
    fecha_actual = datetime.now().strftime("%Y-%m-%d")

    # Controles de Entrada
    txt_fecha = ft.TextField(
        label="Fecha (AAAA-MM-DD)",
        value=fecha_actual,
        icon=ft.Icons.CALENDAR_TODAY,
        on_change=lambda e: actualizar_vista_diaria()
    )
    txt_sg = ft.TextField(
        label="Número de SG",
        hint_text="Ej: 104589",
        keyboard_type=ft.KeyboardType.NUMBER
    )
    rg_tipo = ft.RadioGroup(
        value="Picking",
        on_change=lambda e: actualizar_vista_previa_monto(),
        content=ft.Row([
            ft.Radio(value="Picking", label="Picking ($1300 + $80/SKU)"),
            ft.Radio(value="Driver", label="Driver ($1850 + $38/Art.)"),
        ], wrap=True)
    )
    txt_skus = ft.TextField(
        label="Cant. SKUs",
        keyboard_type=ft.KeyboardType.NUMBER,
        expand=True,
        on_change=lambda e: actualizar_vista_previa_monto()
    )
    txt_articulos = ft.TextField(
        label="Cant. Artículos",
        keyboard_type=ft.KeyboardType.NUMBER,
        expand=True,
        on_change=lambda e: actualizar_vista_previa_monto()
    )

    lbl_estimado = ft.Text("Ingreso estimado del pedido: $ 0", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_700)
    lbl_total_dia = ft.Text("$ 0", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    lbl_conteo_dia = ft.Text("0 pedidos", size=14, color=ft.Colors.WHITE)
    lista_pedidos_container = ft.Column(spacing=10)

    def obtener_valores_numericos():
        try:
            skus = int(txt_skus.value) if txt_skus.value else 0
            arts = int(txt_articulos.value) if txt_articulos.value else 0
            return max(0, skus), max(0, arts)
        except ValueError:
            return 0, 0

    def actualizar_vista_previa_monto():
        skus, arts = obtener_valores_numericos()
        monto = calcular_ingreso(rg_tipo.value, skus, arts)
        lbl_estimado.value = f"Ingreso estimado del pedido: $ {monto:,.0f}".replace(",", ".")
        page.update()

    def eliminar_registro(pedido_id):
        db.eliminar_pedido(pedido_id)
        actualizar_vista_diaria()

    def actualizar_vista_diaria():
        fecha_sel = txt_fecha.value.strip()
        registros = db.obtener_pedidos_por_fecha(fecha_sel)
        lista_pedidos_container.controls.clear()

        total_dinero = 0.0
        for reg in registros:
            p_id, sg, tipo, skus, arts, ingreso = reg
            total_dinero += ingreso

            tarjeta = ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.GREY_100,
                border=ft.border.all(1, ft.Colors.GREY_300),
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(
                            spacing=2,
                            expand=True,
                            controls=[
                                ft.Text(f"SG: {sg}  •  {tipo.upper()}", weight=ft.FontWeight.BOLD, size=15),
                                ft.Text(f"SKUs: {skus} | Artículos: {arts}", size=13, color=ft.Colors.GREY_700),
                            ]
                        ),
                        ft.Row(
                            spacing=4,
                            controls=[
                                ft.Text(f"$ {ingreso:,.0f}".replace(",", "."), weight=ft.FontWeight.BOLD, size=16, color=ft.Colors.GREEN_700),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE_OUTLINE,
                                    icon_color=ft.Colors.RED_400,
                                    tooltip="Eliminar registro",
                                    on_click=lambda e, pid=p_id: eliminar_registro(pid)
                                )
                            ]
                        )
                    ]
                )
            )
            lista_pedidos_container.controls.append(tarjeta)

        lbl_total_dia.value = f"$ {total_dinero:,.0f}".replace(",", ".")
        lbl_conteo_dia.value = f"{len(registros)} pedido(s) registrado(s)"
        page.update()

    def guardar_pedido(e):
        fecha_val = txt_fecha.value.strip()
        sg_val = txt_sg.value.strip()
        skus, arts = obtener_valores_numericos()

        if not fecha_val or not sg_val:
            page.snack_bar = ft.SnackBar(ft.Text("Por favor ingresa la Fecha y el número de SG."), bgcolor=ft.Colors.RED_600)
            page.snack_bar.open = True
            page.update()
            return

        if rg_tipo.value == "Picking" and skus <= 0:
            page.snack_bar = ft.SnackBar(ft.Text("Para Picking debes ingresar al menos 1 SKU."), bgcolor=ft.Colors.ORANGE_700)
            page.snack_bar.open = True
            page.update()
            return

        if rg_tipo.value == "Driver" and arts <= 0:
            page.snack_bar = ft.SnackBar(ft.Text("Para Driver debes ingresar al menos 1 artículo."), bgcolor=ft.Colors.ORANGE_700)
            page.snack_bar.open = True
            page.update()
            return

        ingreso = calcular_ingreso(rg_tipo.value, skus, arts)
        db.insertar_pedido(fecha_val, sg_val, rg_tipo.value, skus, arts, ingreso)

        txt_sg.value = ""
        txt_skus.value = ""
        txt_articulos.value = ""
        actualizar_vista_previa_monto()
        actualizar_vista_diaria()

        page.snack_bar = ft.SnackBar(ft.Text("Pedido registrado correctamente."), bgcolor=ft.Colors.GREEN_600)
        page.snack_bar.open = True
        page.update()

    tarjeta_resumen = ft.Container(
        padding=18,
        border_radius=12,
        gradient=ft.LinearGradient(
            begin=ft.alignment.top_left,
            end=ft.alignment.bottom_right,
            colors=[ft.Colors.INDIGO_700, ft.Colors.BLUE_600]
        ),
        content=ft.Column([
            ft.Text("INGRESO TOTAL DEL DÍA", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            lbl_total_dia,
            lbl_conteo_dia
        ])
    )

    page.add(
        tarjeta_resumen,
        ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
        ft.Text("Registrar Nuevo Pedido", size=18, weight=ft.FontWeight.BOLD),
        txt_fecha,
        txt_sg,
        ft.Text("Modalidad de Preparación:", size=14, weight=ft.FontWeight.W_500),
        rg_tipo,
        ft.Row([txt_skus, txt_articulos], spacing=10),
        lbl_estimado,
        ft.ElevatedButton(
            text="GUARDAR PEDIDO",
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            bgcolor=ft.Colors.INDIGO_600,
            color=ft.Colors.WHITE,
            height=48,
            width=float("inf"),
            on_click=guardar_pedido
        ),
        ft.Divider(height=20),
        ft.Text("Pedidos del Día Seleccionado", size=18, weight=ft.FontWeight.BOLD),
        lista_pedidos_container
    )

    actualizar_vista_diaria()

if __name__ == "__main__":
    ft.run(main)
