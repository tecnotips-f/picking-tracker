import flet as ft
from datetime import datetime, timedelta
import threading
import platform
import cv2
import zxingcpp
from calculator import calcular_ingreso
from database import DatabaseManager

if platform.system() == "Windows":
    import winsound

def main(page: ft.Page):
    page.title = "Control de Picking"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 16
    page.scroll = ft.ScrollMode.ADAPTIVE

    db = DatabaseManager()
    fecha_actual = datetime.now().strftime("%Y-%m-%d")
    primer_dia_mes = datetime.now().replace(day=1).strftime("%Y-%m-%d")

    # Estado de la vista:
    #   "rango":  None = un solo día, o (desde, hasta) = rango histórico
    #   "mostrar": el historial (tabla) NO se muestra al iniciar; solo cuando el usuario lo consulta
    #              o guarda un pedido, y se mantiene visible hasta cerrar la sesión/aplicación
    estado = {"rango": None, "mostrar": False}

    # Tarifa Shopper: $3600 por SG + $38 por unidad (campo "Cant. Artículos")
    TARIFA_SHOPPER_SG = 3600
    TARIFA_SHOPPER_UNIDAD = 38

    def calcular_monto(tipo, skus, arts):
        if tipo == "Shopper":
            return TARIFA_SHOPPER_SG + TARIFA_SHOPPER_UNIDAD * arts
        return calcular_ingreso(tipo, skus, arts)

    # Controles de Entrada
    txt_fecha = ft.TextField(
        label="Fecha (AAAA-MM-DD)",
        value=fecha_actual,
        on_change=lambda e: volver_a_dia()
    )

    txt_sg = ft.TextField(
        label="Número de SG",
        hint_text="Escanee o ingrese el SG...",
        keyboard_type=ft.KeyboardType.NUMBER
    )

    rg_tipo = ft.RadioGroup(
        value="Picking",
        on_change=lambda e: actualizar_vista_previa_monto(),
        content=ft.Row([
            ft.Radio(value="Picking", label="Picking ($1300 + $80/SKU)"),
            ft.Radio(value="Driver", label="Driver ($1850 + $38/Art.)"),
            ft.Radio(value="Shopper", label="Shopper ($3600 + $38/Unidad)"),
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

    # Controles de consulta por rango de fechas
    txt_desde = ft.TextField(label="Desde (AAAA-MM-DD)", value=primer_dia_mes, width=200)
    txt_hasta = ft.TextField(label="Hasta (AAAA-MM-DD)", value=fecha_actual, width=200)

    lbl_estimado = ft.Text("Ingreso estimado del pedido: $ 0", size=16, weight=ft.FontWeight.BOLD, color="blue")
    lbl_titulo_total = ft.Text("INGRESO TOTAL DEL DÍA", size=12, weight=ft.FontWeight.BOLD, color="white")
    lbl_total_dia = ft.Text("$ 0", size=26, weight=ft.FontWeight.BOLD, color="white")
    lbl_conteo_dia = ft.Text("0 pedidos", size=14, color="white")
    lbl_titulo_lista = ft.Text("Pedidos del Día Seleccionado", size=18, weight=ft.FontWeight.BOLD, visible=False)
    lista_pedidos_container = ft.Column(spacing=10)

    def mostrar_alerta(mensaje, es_error=False):
        """Muestra notificaciones visuales garantizadas en la interfaz"""
        snack = ft.SnackBar(
            content=ft.Text(mensaje, color="white", weight=ft.FontWeight.BOLD),
            bgcolor="red" if es_error else "green",
            duration=2000,  # se oculta solo a los 2 segundos
        )
        try:
            page.show_dialog(snack)      # Flet 0.70+ (ft.run)
        except AttributeError:
            page.snack_bar = snack       # Flet antiguo
            page.snack_bar.open = True
            page.update()

    def procesar_texto_escaneado(texto_crudo):
        """Procesa el texto detectado, valida duplicados y actualiza campos"""
        datos = texto_crudo.strip()

        sg_encontrado = datos
        skus_detectados = None
        arts_detectados = None

        if "|" in datos:
            partes = datos.split("|")
            sg_encontrado = partes[0].strip()
            if len(partes) > 1 and partes[1].strip().isdigit():
                skus_detectados = int(partes[1].strip())
            if len(partes) > 2 and partes[2].strip().isdigit():
                arts_detectados = int(partes[2].strip())

        # VALIDACIÓN DE DUPLICADOS
        if db.verificar_sg_existente(sg_encontrado):
            mostrar_alerta(f"⚠️ El SG '{sg_encontrado}' ya existe en la base de datos.", es_error=True)
            if platform.system() == "Windows":
                try:
                    winsound.Beep(1000, 600)  # Sonido grave de advertencia
                except Exception:
                    pass
            return

        # Si no existe, asignamos y emitimos éxito
        if platform.system() == "Windows":
            try:
                winsound.Beep(2500, 300)  # Sonido agudo de éxito
            except Exception:
                pass

        txt_sg.value = sg_encontrado
        if skus_detectados is not None:
            txt_skus.value = str(skus_detectados)
        if arts_detectados is not None:
            txt_articulos.value = str(arts_detectados)

        actualizar_vista_previa_monto()
        mostrar_alerta(f"¡Código leído con éxito: {txt_sg.value}!")

    # --- CONTROL DE CÁMARA CON ACTIVAR / DESACTIVAR ---
    camara_activa = threading.Event()   # True = cámara encendida
    hilo_cam = {"t": None}              # referencia al hilo de escaneo

    def _estado_boton(activo):
        """Cambia el aspecto del botón según el estado de la cámara"""
        btn_escanear.content = "⏹ DETENER CÁMARA" if activo else "📷 ACTIVAR CÁMARA Y ESCANEAR CÓDIGO"
        btn_escanear.bgcolor = "#c62828" if activo else "#00897b"
        page.update()

    def escanear_con_webcam_pc():
        cap = None
        codigo_encontrado = None
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if platform.system() == "Windows" else cv2.VideoCapture(0)
            if not cap.isOpened():
                mostrar_alerta("No se pudo abrir la cámara.", es_error=True)
                return

            ventana_nombre = "Escaner - Enfoque el codigo (ESC para salir)"

            while camara_activa.is_set():
                ret, frame = cap.read()
                if not ret or frame is None:
                    break

                resultados = zxingcpp.read_barcodes(frame)
                if resultados:
                    codigo_encontrado = resultados[0].text
                    break

                cv2.imshow(ventana_nombre, frame)

                if cv2.waitKey(1) & 0xFF == 27:
                    break
                if cv2.getWindowProperty(ventana_nombre, cv2.WND_PROP_VISIBLE) < 1:
                    break
        except Exception as ex:
            print(f"Error en cámara: {ex}")
        finally:
            # Liberación segura: siempre se apaga la cámara
            try:
                if cap is not None:
                    cap.release()
            except Exception:
                pass

            try:
                cv2.destroyAllWindows()
                cv2.waitKey(1)
            except Exception:
                pass

            camara_activa.clear()
            _estado_boton(False)

        if codigo_encontrado:
            procesar_texto_escaneado(codigo_encontrado)

    def iniciar_escaneo(e):
        # La captura con OpenCV solo funciona en la app de escritorio (PC/laptop)
        if page.web or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
            mostrar_alerta("En móvil/navegador el escaneo requiere la cámara del navegador. Ingresa el SG manualmente.", es_error=True)
            return

        # Segundo clic: apagar la cámara
        if camara_activa.is_set():
            camara_activa.clear()
            return

        # Si el hilo anterior aún se está cerrando, ignorar el clic
        t = hilo_cam["t"]
        if t is not None and t.is_alive():
            return

        # Primer clic: encender la cámara
        camara_activa.set()
        _estado_boton(True)
        hilo_cam["t"] = threading.Thread(target=escanear_con_webcam_pc, daemon=True)
        hilo_cam["t"].start()

    btn_escanear = ft.Button(
        content="📷 ACTIVAR CÁMARA Y ESCANEAR CÓDIGO",
        bgcolor="#00897b",
        color="white",
        height=48,
        width=float("inf"),
        on_click=iniciar_escaneo
    )
    # -------------------------------------------------------------

    def obtener_valores_numericos():
        try:
            skus = int(txt_skus.value) if txt_skus.value else 0
            arts = int(txt_articulos.value) if txt_articulos.value else 0
            return max(0, skus), max(0, arts)
        except ValueError:
            return 0, 0

    def actualizar_vista_previa_monto():
        skus, arts = obtener_valores_numericos()
        monto = calcular_monto(rg_tipo.value, skus, arts)
        lbl_estimado.value = f"Ingreso estimado del pedido: $ {monto:,.0f}".replace(",", ".")
        page.update()

    def eliminar_registro(pedido_id):
        db.eliminar_pedido(pedido_id)
        actualizar_vista_diaria()

    def fmt_moneda(valor):
        return f"$ {valor:,.0f}".replace(",", ".")

    def renderizar_tabla(registros):
        """Dibuja la tabla. registros: (id, fecha, sg, tipo, skus, arts, ingreso)"""
        lista_pedidos_container.controls.clear()

        total_dinero = 0.0
        filas = []
        for p_id, fecha, sg, tipo, skus, arts, ingreso in registros:
            total_dinero += ingreso
            filas.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(fecha), size=13)),
                    ft.DataCell(ft.Text(str(sg), weight=ft.FontWeight.BOLD, size=13)),
                    ft.DataCell(ft.Text(tipo.upper(), size=13)),
                    ft.DataCell(ft.Text(str(skus), size=13)),
                    ft.DataCell(ft.Text(str(arts), size=13)),
                    ft.DataCell(ft.Text(fmt_moneda(ingreso), weight=ft.FontWeight.BOLD, size=13, color="green")),
                    ft.DataCell(
                        ft.Container(
                            content=ft.Text("🗑️", size=18),
                            tooltip="Eliminar registro",
                            padding=6,
                            border_radius=6,
                            ink=True,
                            on_click=lambda e, pid=p_id: eliminar_registro(pid)
                        )
                    ),
                ])
            )

        if not estado["mostrar"]:
            lista_pedidos_container.controls.append(
                ft.Text("El historial se muestra al consultarlo: usa «VER PEDIDOS DEL DÍA» o «CONSULTAR RANGO».",
                        size=13, color="#666666")
            )
        elif filas:
            tabla = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("SG", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Tipo", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("SKUs", weight=ft.FontWeight.BOLD), numeric=True),
                    ft.DataColumn(ft.Text("Artículos", weight=ft.FontWeight.BOLD), numeric=True),
                    ft.DataColumn(ft.Text("Ingreso", weight=ft.FontWeight.BOLD), numeric=True),
                    ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
                ],
                rows=filas,
                column_spacing=28,
                divider_thickness=1,
            )
            # Row con scroll horizontal: en celulares la tabla se desplaza de lado
            lista_pedidos_container.controls.append(ft.Row([tabla], scroll=ft.ScrollMode.AUTO))
        else:
            lista_pedidos_container.controls.append(
                ft.Text("No hay pedidos registrados en este período.", color="#666666")
            )

        lbl_total_dia.value = fmt_moneda(total_dinero)
        lbl_conteo_dia.value = f"{len(registros)} pedido(s) registrado(s)"
        page.update()

    def actualizar_vista_diaria():
        """Refresca la vista actual: un día o el rango consultado"""
        if estado["rango"]:
            desde, hasta = estado["rango"]
            registros = db.obtener_pedidos_por_rango(desde, hasta)
            lbl_titulo_total.value = "INGRESO TOTAL DEL RANGO"
            lbl_titulo_lista.value = f"Pedidos del {desde} al {hasta}"
        else:
            fecha_sel = txt_fecha.value.strip()
            registros = [
                (p_id, fecha_sel, sg, tipo, skus, arts, ingreso)
                for (p_id, sg, tipo, skus, arts, ingreso) in db.obtener_pedidos_por_fecha(fecha_sel)
            ]
            lbl_titulo_total.value = "INGRESO TOTAL DEL DÍA"
            lbl_titulo_lista.value = "Pedidos del Día Seleccionado"
        lbl_titulo_lista.visible = estado["mostrar"]
        renderizar_tabla(registros)

    def volver_a_dia(e=None):
        """Cambió la fecha: vuelve a la vista de un día (sin mostrar el historial si aún está oculto)"""
        estado["rango"] = None
        actualizar_vista_diaria()

    def ver_pedidos_del_dia(e=None):
        """El usuario pide ver el historial del día indicado en el campo Fecha"""
        estado["rango"] = None
        estado["mostrar"] = True
        actualizar_vista_diaria()

    # --- CONSULTA POR RANGO DE FECHAS ---
    def consultar_rango(e=None):
        try:
            d = datetime.strptime(txt_desde.value.strip(), "%Y-%m-%d")
            h = datetime.strptime(txt_hasta.value.strip(), "%Y-%m-%d")
        except ValueError:
            mostrar_alerta("Fechas inválidas. Usa el formato AAAA-MM-DD.", es_error=True)
            return

        if d > h:
            mostrar_alerta("La fecha 'Desde' no puede ser mayor que 'Hasta'.", es_error=True)
            return

        estado["rango"] = (d.strftime("%Y-%m-%d"), h.strftime("%Y-%m-%d"))
        estado["mostrar"] = True
        actualizar_vista_diaria()

    def rango_rapido(tipo):
        hoy = datetime.now()
        if tipo == "semana":
            desde, hasta = hoy - timedelta(days=hoy.weekday()), hoy
        elif tipo == "mes":
            desde, hasta = hoy.replace(day=1), hoy
        else:  # mes anterior
            hasta = hoy.replace(day=1) - timedelta(days=1)
            desde = hasta.replace(day=1)
        txt_desde.value = desde.strftime("%Y-%m-%d")
        txt_hasta.value = hasta.strftime("%Y-%m-%d")
        consultar_rango()

    def abrir_calendario(campo):
        def al_elegir(e):
            if e.control.value:
                campo.value = e.control.value.strftime("%Y-%m-%d")
                page.update()
        dp = ft.DatePicker(on_change=al_elegir)
        try:
            page.show_dialog(dp)         # Flet 0.70+
        except AttributeError:
            page.overlay.append(dp)      # Flet antiguo
            dp.open = True
            page.update()

    def boton_calendario(campo):
        return ft.Container(
            content=ft.Text("📅", size=24),
            tooltip="Elegir fecha",
            padding=8,
            border_radius=8,
            ink=True,
            on_click=lambda e: abrir_calendario(campo)
        )

    def boton_rango(texto, color, accion):
        return ft.Button(content=texto, bgcolor=color, color="white", height=42, on_click=accion)
    # -------------------------------------

    def ajustar_ancho(e=None):
        """PC/laptop: contenido al 80% del ancho (centrado). Móvil: ancho completo."""
        ancho = page.width or 0
        if not ancho:
            return
        movil = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS) or ancho < 600
        margen = 12 if movil else ancho * 0.10
        try:
            page.padding = ft.Padding.symmetric(horizontal=margen, vertical=16)   # Flet 1.x
        except AttributeError:
            page.padding = ft.padding.symmetric(horizontal=margen, vertical=16)   # Flet antiguo
        page.update()

    page.on_resize = ajustar_ancho

    def guardar_pedido(e):
        fecha_val = txt_fecha.value.strip()
        sg_val = txt_sg.value.strip()
        skus, arts = obtener_valores_numericos()

        if not fecha_val or not sg_val:
            mostrar_alerta("Por favor ingresa la Fecha y el número de SG.", es_error=True)
            return

        # VALIDACIÓN MANUAL DE DUPLICADOS
        if db.verificar_sg_existente(sg_val):
            mostrar_alerta(f"⚠️ El SG '{sg_val}' ya existe en la base de datos.", es_error=True)
            if platform.system() == "Windows":
                try:
                    winsound.Beep(1000, 600)
                except Exception:
                    pass
            return

        if rg_tipo.value == "Picking" and skus <= 0:
            mostrar_alerta("Para Picking debes ingresar al menos 1 SKU.", es_error=True)
            return

        if rg_tipo.value == "Driver" and arts <= 0:
            mostrar_alerta("Para Driver debes ingresar al menos 1 artículo.", es_error=True)
            return

        if rg_tipo.value == "Shopper" and arts <= 0:
            mostrar_alerta("Para Shopper debes ingresar al menos 1 unidad (Cant. Artículos).", es_error=True)
            return

        ingreso = calcular_monto(rg_tipo.value, skus, arts)
        db.insertar_pedido(fecha_val, sg_val, rg_tipo.value, skus, arts, ingreso)

        txt_sg.value = ""
        txt_skus.value = ""
        txt_articulos.value = ""
        actualizar_vista_previa_monto()
        estado["mostrar"] = True   # al cargar datos, se muestra el historial y se mantiene en la sesión
        actualizar_vista_diaria()

        mostrar_alerta("Pedido registrado correctamente.")

    tarjeta_resumen = ft.Container(
        padding=18,
        border_radius=12,
        bgcolor="#1a237e",
        content=ft.Column([
            lbl_titulo_total,
            lbl_total_dia,
            lbl_conteo_dia
        ])
    )

    page.add(
        tarjeta_resumen,
        ft.Divider(height=10, color="transparent"),
        ft.Text("Registrar Nuevo Pedido", size=18, weight=ft.FontWeight.BOLD),
        txt_fecha,
        btn_escanear,
        txt_sg,
        ft.Text("Modalidad de Preparación:", size=14, weight=ft.FontWeight.W_500),
        rg_tipo,
        ft.Row([txt_skus, txt_articulos], spacing=10),
        lbl_estimado,
        ft.Button(
            content="GUARDAR PEDIDO",
            bgcolor="#303f9f",
            color="white",
            height=48,
            width=float("inf"),
            on_click=guardar_pedido
        ),
        ft.Divider(height=20),
        ft.Text("Consultar histórico", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("«Ver pedidos del día» usa la fecha del campo Fecha de arriba; para otro período elige un rango.",
                size=13, color="#666666"),
        ft.Row(
            [txt_desde, boton_calendario(txt_desde), txt_hasta, boton_calendario(txt_hasta)],
            wrap=True,
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        ),
        ft.Row(
            [
                boton_rango("🔍 CONSULTAR RANGO", "#303f9f", consultar_rango),
                boton_rango("Esta semana", "#5c6bc0", lambda e: rango_rapido("semana")),
                boton_rango("Este mes", "#5c6bc0", lambda e: rango_rapido("mes")),
                boton_rango("Mes anterior", "#5c6bc0", lambda e: rango_rapido("anterior")),
                boton_rango("📋 VER PEDIDOS DEL DÍA", "#00897b", ver_pedidos_del_dia),
            ],
            wrap=True,
            spacing=10
        ),
        ft.Divider(height=20),
        lbl_titulo_lista,
        lista_pedidos_container
    )

    actualizar_vista_diaria()
    ajustar_ancho()

if __name__ == "__main__":
    ft.run(main)