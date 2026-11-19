import flet as ft
from datetime import datetime, timedelta
import threading
import platform
import cv2
import zxingcpp
from calculator import calcular_ingreso
from database import DatabaseManager
from seguridad import normalizar_rut, validar_rut, validar_id_boosmap

if platform.system() == "Windows":
    import winsound

def main(page: ft.Page):
    page.title = "Control de Picking"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 16
    page.scroll = ft.ScrollMode.ADAPTIVE

    db = DatabaseManager()

<<<<<<< HEAD
    # Controles de Entrada
    txt_fecha = ft.TextField(
        label="Fecha (AAAA-MM-DD)",
        value=fecha_actual,
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
=======
    def mostrar_alerta(mensaje, es_error=False, ms=2000):
        """Muestra notificaciones visuales (se ocultan solas; 2 segundos por defecto)"""
        snack = ft.SnackBar(
            content=ft.Text(mensaje, color="white", weight=ft.FontWeight.BOLD),
            bgcolor="red" if es_error else "green",
            duration=ms,
        )
>>>>>>> fd06846 (Actualiza interfaz, edicion de pedidos y rutas)
        try:
            page.show_dialog(snack)
        except AttributeError:
            page.snack_bar = snack
            page.snack_bar.open = True
            page.update()

    def ajustar_ancho(e=None):
        ancho = page.width or 0
        if not ancho:
            return
        movil = page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS) or ancho < 600
        margen = 12 if movil else ancho * 0.10
        try:
            page.padding = ft.Padding.symmetric(horizontal=margen, vertical=16)
        except AttributeError:
            page.padding = ft.padding.symmetric(horizontal=margen, vertical=16)
        page.update()

    page.on_resize = ajustar_ancho

    # =====================================================================
    #  PANTALLA DE ACCESO (REDISEÑADA CON COLOR Y CENTRADA)
    # =====================================================================
    def mostrar_login(aviso=None):
        page.clean()
        ancho_campo = 320

        txt_rut = ft.TextField(
            label="RUT (sin puntos ni guion)", 
            label_style=ft.TextStyle(color="#0d47a1", weight=ft.FontWeight.BOLD),
            hint_text="Ej: 123456785 o 12345678K",
            color="#000000",
            width=ancho_campo, 
            autofocus=True,
            border_color="#3f51b5",
            focused_border_color="#1a237e"
        )
        txt_clave = ft.TextField(
            label="Clave (ID Boosmap)", 
            label_style=ft.TextStyle(color="#0d47a1", weight=ft.FontWeight.BOLD),
            password=True, 
            can_reveal_password=True,
            color="#000000",
            width=ancho_campo,
            border_color="#3f51b5",
            focused_border_color="#1a237e"
        )

<<<<<<< HEAD
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
                                    icon=ft.icons.DELETE_OUTLINE,
                                    icon_color=ft.Colors.RED_400,
                                    tooltip="Eliminar registro",
                                    on_click=lambda e, pid=p_id: eliminar_registro(pid)
                                )
                            ]
                        )
                    ]
=======
        reg_rut = ft.TextField(
            label="RUT (sin puntos ni guion)", 
            label_style=ft.TextStyle(color="#0d47a1", weight=ft.FontWeight.BOLD),
            hint_text="Ej: 123456785 o 12345678K",
            color="#000000",
            width=ancho_campo,
            border_color="#3f51b5"
        )
        reg_nombre = ft.TextField(
            label="Nombre completo", 
            label_style=ft.TextStyle(color="#0d47a1", weight=ft.FontWeight.BOLD),
            color="#000000", 
            width=ancho_campo,
            border_color="#3f51b5"
        )
        reg_correo = ft.TextField(
            label="Correo (opcional)", 
            label_style=ft.TextStyle(color="#0d47a1", weight=ft.FontWeight.BOLD),
            color="#000000",
            keyboard_type=ft.KeyboardType.EMAIL,
            width=ancho_campo,
            border_color="#3f51b5"
        )
        reg_id = ft.TextField(
            label="ID Boosmap (6 dígitos)", 
            label_style=ft.TextStyle(color="#0d47a1", weight=ft.FontWeight.BOLD),
            color="#000000",
            password=True, 
            can_reveal_password=True,
            keyboard_type=ft.KeyboardType.NUMBER, 
            width=ancho_campo,
            border_color="#3f51b5"
        )
        reg_id2 = ft.TextField(
            label="Repite tu ID Boosmap", 
            label_style=ft.TextStyle(color="#0d47a1", weight=ft.FontWeight.BOLD),
            color="#000000",
            password=True, 
            can_reveal_password=True,
            keyboard_type=ft.KeyboardType.NUMBER, 
            width=ancho_campo,
            border_color="#3f51b5"
        )

        def entrar(e=None):
            resultado, dato = db.autenticar(txt_rut.value or "", (txt_clave.value or "").strip())
            if resultado == "ok":
                iniciar_app(dato)
            elif resultado == "bloqueado":
                mostrar_alerta(f"Demasiados intentos. Intenta de nuevo en {dato} min.", True, 4000)
            elif resultado == "inactivo":
                mostrar_alerta("Tu cuenta está pendiente de activación o fue desactivada. Contacta al administrador.", True, 4500)
            else:
                mostrar_alerta("RUT o clave incorrectos.", True, 3000)

        txt_clave.on_submit = entrar

        def registrar(e=None):
            rut = normalizar_rut(reg_rut.value or "")
            nombre = (reg_nombre.value or "").strip()
            correo = (reg_correo.value or "").strip()
            id_b = (reg_id.value or "").strip()

            if not validar_rut(rut):
                mostrar_alerta("RUT inválido. Escríbelo sin puntos ni guion (ej: 123456785 o 12345678K).", True, 4000)
                return
            if len(nombre) < 3:
                mostrar_alerta("Ingresa tu nombre completo.", True)
                return
            if correo and ("@" not in correo or "." not in correo.split("@")[-1]):
                mostrar_alerta("El correo no parece válido (puedes dejarlo vacío).", True, 3000)
                return
            if not validar_id_boosmap(id_b):
                mostrar_alerta("El ID Boosmap debe tener exactamente 6 dígitos.", True, 3000)
                return
            if id_b != (reg_id2.value or "").strip():
                mostrar_alerta("Los ID Boosmap no coinciden.", True, 3000)
                return

            ok, mensaje = db.registrar_usuario(rut, nombre, correo, id_b)
            mostrar_alerta(mensaje, es_error=not ok, ms=5000)
            if ok:
                for campo in (reg_rut, reg_nombre, reg_correo, reg_id, reg_id2):
                    campo.value = ""
                txt_rut.value = rut
                ir_a(registro=False)

        def ir_a(registro):
            form_login.visible = not registro
            form_registro.visible = registro
            page.update()

        form_login = ft.Column(
            [
                txt_rut,
                txt_clave,
                ft.Container(height=5),
                ft.Button(content="INICIAR SESIÓN", bgcolor="#1a237e", color="white", height=48,
                          width=ancho_campo, on_click=entrar),
                ft.Button(content="Solicitar cuenta nueva", bgcolor="#3f51b5", color="white", height=40,
                          width=ancho_campo, on_click=lambda e: ir_a(registro=True)),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=14
        )

        form_registro = ft.Column(
            [
                ft.Text("Solicitar cuenta", size=18, weight=ft.FontWeight.BOLD, color="#1a237e"),
                reg_rut, reg_nombre, reg_correo, reg_id, reg_id2,
                ft.Text("El administrador debe activar tu cuenta antes de que puedas ingresar.",
                        size=12, color="#000000", width=ancho_campo, weight=ft.FontWeight.W_500),
                ft.Container(height=5),
                ft.Button(content="ENVIAR SOLICITUD", bgcolor="#00897b", color="white", height=48,
                          width=ancho_campo, on_click=registrar),
                ft.Button(content="Ya tengo cuenta", bgcolor="#3f51b5", color="white", height=40,
                          width=ancho_campo, on_click=lambda e: ir_a(registro=False)),
            ],
            visible=False,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12
        )

        tarjeta_login = ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.LOCK_OUTLINE, size=40, color="#1a237e"),
                    ft.Text("Control de Picking", size=26, weight=ft.FontWeight.BOLD, color="#1a237e"),
                    ft.Text("Ingresa con tu RUT y tu ID Boosmap.", size=13, color="#000000", weight=ft.FontWeight.W_500),
                    ft.Divider(height=15, color="transparent"),
                    form_login,
                    form_registro,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                tight=True
            ),
            padding=30,
            border_radius=16,
            bgcolor="#ffffff",
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=15,
                color=ft.Colors.with_opacity(0.15, "#1a237e"),
                offset=ft.Offset(0, 4)
            ),
            width=400,
        )

        layout_centrado = ft.Row(
            [
                ft.Column(
                    [tarjeta_login],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
>>>>>>> fd06846 (Actualiza interfaz, edicion de pedidos y rutas)
                )
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True
        )

        page.bgcolor = "#e8eaf6"
        page.add(layout_centrado)
        ajustar_ancho()
        if aviso:
            mostrar_alerta(aviso, True, 4500)

    # =====================================================================
    #  APLICACIÓN PRINCIPAL
    # =====================================================================
    def iniciar_app(usuario):
        page.clean()
        page.bgcolor = None
        uid = usuario["id"]
        es_admin = usuario["rol"] == "admin"

        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        primer_dia_mes = datetime.now().replace(day=1).strftime("%Y-%m-%d")

        estado = {"rango": None, "mostrar": False}

        TARIFA_SHOPPER_SG = 3600
        TARIFA_SHOPPER_UNIDAD = 38

        def calcular_monto(tipo, skus, arts):
            if tipo == "Shopper":
                return TARIFA_SHOPPER_SG + TARIFA_SHOPPER_UNIDAD * arts
            return calcular_ingreso(tipo, skus, arts)

        def cerrar_sesion(aviso=None):
            camara_activa.clear()
            mostrar_login(aviso)

        def sesion_activa():
            u = db.obtener_usuario(uid)
            if not u or not u["activo"]:
                cerrar_sesion("Tu cuenta fue desactivada. Contacta al administrador.")
                return False
            return True

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

        txt_desde = ft.TextField(label="Desde (AAAA-MM-DD)", value=primer_dia_mes, width=200)
        txt_hasta = ft.TextField(label="Hasta (AAAA-MM-DD)", value=fecha_actual, width=200)

        lbl_estimado = ft.Text("Ingreso estimado del pedido: $ 0", size=16, weight=ft.FontWeight.BOLD, color="blue")
        lbl_titulo_total = ft.Text("INGRESO TOTAL DEL DÍA", size=12, weight=ft.FontWeight.BOLD, color="white")
        lbl_total_dia = ft.Text("$ 0", size=26, weight=ft.FontWeight.BOLD, color="white")
        lbl_conteo_dia = ft.Text("0 pedidos", size=14, color="white")
        lbl_titulo_lista = ft.Text("Pedidos del Día Seleccionado", size=18, weight=ft.FontWeight.BOLD, visible=False)
        lista_pedidos_container = ft.Column(spacing=10)

        def procesar_texto_escaneado(texto_crudo):
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

            if db.verificar_sg_existente(sg_encontrado, uid):
                mostrar_alerta(f"⚠️ El SG '{sg_encontrado}' ya existe en la base de datos.", es_error=True)
                if platform.system() == "Windows":
                    try:
                        winsound.Beep(1000, 600)
                    except Exception:
                        pass
                return

            if platform.system() == "Windows":
                try:
                    winsound.Beep(2500, 300)
                except Exception:
                    pass

            txt_sg.value = sg_encontrado
            if skus_detectados is not None:
                txt_skus.value = str(skus_detectados)
            if arts_detectados is not None:
                txt_articulos.value = str(arts_detectados)

            actualizar_vista_previa_monto()
            mostrar_alerta(f"¡Código leído con éxito: {txt_sg.value}!")

        camara_activa = threading.Event()
        hilo_cam = {"t": None}

        def _estado_boton(activo):
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

<<<<<<< HEAD
    tarjeta_resumen = ft.Container(
        padding=18,
        border_radius=12,
        gradient=ft.LinearGradient(
            begin="top_left",
            end="bottom_right",
            colors=[ft.Colors.INDIGO_700, ft.Colors.BLUE_600]
        ),
        content=ft.Column([
            ft.Text("INGRESO TOTAL DEL DÍA", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
            lbl_total_dia,
            lbl_conteo_dia
        ])
    )
=======
                    if cv2.waitKey(1) & 0xFF == 27:
                        break
                    if cv2.getWindowProperty(ventana_nombre, cv2.WND_PROP_VISIBLE) < 1:
                        break
            except Exception as ex:
                print(f"Error en cámara: {ex}")
            finally:
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
>>>>>>> fd06846 (Actualiza interfaz, edicion de pedidos y rutas)

            if codigo_encontrado:
                procesar_texto_escaneado(codigo_encontrado)

        def iniciar_escaneo(e):
            if page.web or page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
                mostrar_alerta("En móvil/navegador el escaneo requiere la cámara del navegador. Ingresa el SG manualmente.", es_error=True)
                return
            if camara_activa.is_set():
                camara_activa.clear()
                return
            t = hilo_cam["t"]
            if t is not None and t.is_alive():
                return
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
            if not sesion_activa():
                return
            db.eliminar_pedido(pedido_id, uid)
            actualizar_vista_diaria()

        def abrir_dialogo_editar(p_id, fecha_actual_reg, sg_actual, tipo_actual, skus_actual, arts_actual):
            """Muestra un diálogo modal para editar los datos del pedido"""
            if not sesion_activa():
                return

            txt_edit_fecha = ft.TextField(label="Fecha (AAAA-MM-DD)", value=str(fecha_actual_reg), width=300)
            txt_edit_sg = ft.TextField(label="Número de SG", value=str(sg_actual), width=300)

            tipo_normalizado = str(tipo_actual).strip().capitalize()
            if tipo_normalizado not in ("Picking", "Driver", "Shopper"):
                tipo_normalizado = "Picking"

            dd_edit_tipo = ft.Dropdown(
                label="Modalidad",
                value=tipo_normalizado,
                options=[
                    ft.dropdown.Option("Picking"),
                    ft.dropdown.Option("Driver"),
                    ft.dropdown.Option("Shopper"),
                ],
                width=300
            )

            txt_edit_skus = ft.TextField(
                label="Cant. SKUs",
                value=str(skus_actual),
                keyboard_type=ft.KeyboardType.NUMBER,
                width=300
            )
            txt_edit_arts = ft.TextField(
                label="Cant. Artículos",
                value=str(arts_actual),
                keyboard_type=ft.KeyboardType.NUMBER,
                width=300
            )

            def cerrar_dialogo(e=None):
                try:
                    page.pop_dialog()
                except AttributeError:
                    dlg.open = False
                    page.update()

            def guardar_cambios_dialogo(e):
                try:
                    nueva_fecha = (txt_edit_fecha.value or "").strip()
                    nuevo_sg = (txt_edit_sg.value or "").strip()
                    nuevo_tipo = dd_edit_tipo.value or tipo_normalizado
                    nuevos_skus = int((txt_edit_skus.value or "0").strip())
                    nuevos_arts = int((txt_edit_arts.value or "0").strip())

                    if not nueva_fecha or not nuevo_sg:
                        mostrar_alerta("La fecha y el SG no pueden estar vacíos.", True)
                        return

                    try:
                        datetime.strptime(nueva_fecha, "%Y-%m-%d")
                    except ValueError:
                        mostrar_alerta("Fecha inválida. Usa el formato AAAA-MM-DD.", True)
                        return

                    if nuevos_skus < 0 or nuevos_arts < 0:
                        mostrar_alerta("SKUs y Artículos no pueden ser negativos.", True)
                        return

                    if nuevo_tipo == "Picking" and nuevos_skus <= 0:
                        mostrar_alerta("Para Picking debes ingresar al menos 1 SKU.", True)
                        return

                    if nuevo_tipo == "Driver" and nuevos_arts <= 0:
                        mostrar_alerta("Para Driver debes ingresar al menos 1 artículo.", True)
                        return

                    if nuevo_tipo == "Shopper" and nuevos_arts <= 0:
                        mostrar_alerta("Para Shopper debes ingresar al menos 1 unidad.", True)
                        return

                    if nuevo_sg != str(sg_actual).strip() and db.verificar_sg_existente(nuevo_sg, uid):
                        mostrar_alerta(f"⚠️ El SG '{nuevo_sg}' ya existe en tus registros.", True)
                        return

                    nuevo_ingreso = calcular_monto(nuevo_tipo, nuevos_skus, nuevos_arts)
                    db.actualizar_pedido(
                        p_id, uid, nueva_fecha, nuevo_sg, nuevo_tipo, nuevos_skus, nuevos_arts, nuevo_ingreso
                    )

                    cerrar_dialogo()
                    actualizar_vista_diaria()
                    mostrar_alerta("Pedido actualizado correctamente.")
                except ValueError:
                    mostrar_alerta("Verifica que SKUs y Artículos sean números válidos.", True)

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Editar Registro de Pedido", weight=ft.FontWeight.BOLD, color="#1a237e"),
                content=ft.Column([
                    txt_edit_fecha,
                    txt_edit_sg,
                    dd_edit_tipo,
                    txt_edit_skus,
                    txt_edit_arts,
                ], tight=True, spacing=10),
                actions=[
                    ft.TextButton("Cancelar", on_click=cerrar_dialogo),
                    ft.Button(
                        content="Guardar Cambios",
                        bgcolor="#1a237e",
                        color="white",
                        on_click=guardar_cambios_dialogo
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            try:
                page.show_dialog(dlg)
            except AttributeError:
                if dlg not in page.overlay:
                    page.overlay.append(dlg)
                dlg.open = True
                page.update()

        def fmt_moneda(valor):
            return f"$ {valor:,.0f}".replace(",", ".")

        def renderizar_tabla(registros):
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
                            ft.Row([
                                ft.Container(
                                    content=ft.Text("✏️", size=18),
                                    tooltip="Editar registro",
                                    padding=4,
                                    border_radius=6,
                                    ink=True,
                                    on_click=lambda e, pid=p_id, f=fecha, s=sg, t=tipo, sk=skus, ar=arts: abrir_dialogo_editar(pid, f, s, t, sk, ar)
                                ),
                                ft.Container(
                                    content=ft.Text("🗑️", size=18),
                                    tooltip="Eliminar registro",
                                    padding=4,
                                    border_radius=6,
                                    ink=True,
                                    on_click=lambda e, pid=p_id: eliminar_registro(pid)
                                ),
                            ], spacing=4)
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
                        ft.DataColumn(ft.Text("Acciones", weight=ft.FontWeight.BOLD)),
                    ],
                    rows=filas,
                    column_spacing=20,
                    divider_thickness=1,
                )
                lista_pedidos_container.controls.append(ft.Row([tabla], scroll=ft.ScrollMode.AUTO))
            else:
                lista_pedidos_container.controls.append(
                    ft.Text("No hay pedidos registrados en este período.", color="#666666")
                )

            if estado["mostrar"]:
                lbl_total_dia.value = fmt_moneda(total_dinero)
                lbl_conteo_dia.value = f"{len(registros)} pedido(s) registrado(s)"
            else:
                lbl_total_dia.value = fmt_moneda(0)
                lbl_conteo_dia.value = "0 pedido(s) registrado(s)"
            page.update()

        def actualizar_vista_diaria():
            if not sesion_activa():
                return
            if estado["rango"]:
                desde, hasta = estado["rango"]
                registros = db.obtener_pedidos_por_rango(desde, hasta, uid)
                lbl_titulo_total.value = "INGRESO TOTAL DEL RANGO"
                lbl_titulo_lista.value = f"Pedidos del {desde} al {hasta}"
            else:
                fecha_sel = txt_fecha.value.strip()
                registros = db.obtener_pedidos_por_rango(fecha_sel, fecha_sel, uid)
                lbl_titulo_total.value = "INGRESO TOTAL DEL DÍA"
                lbl_titulo_lista.value = "Pedidos del Día Seleccionado"
            lbl_titulo_lista.visible = estado["mostrar"]
            renderizar_tabla(registros)

        def volver_a_dia(e=None):
            estado["rango"] = None
            actualizar_vista_diaria()

        def ver_pedidos_del_dia(e=None):
            estado["rango"] = None
            estado["mostrar"] = True
            actualizar_vista_diaria()

        def borrar_consulta(e=None):
            estado["rango"] = None
            estado["mostrar"] = False
            txt_desde.value = primer_dia_mes
            txt_hasta.value = fecha_actual
            actualizar_vista_diaria()

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
            else:
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
                page.show_dialog(dp)
            except AttributeError:
                page.overlay.append(dp)
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

        panel_admin = ft.Column(visible=False, spacing=10)
        btn_usuarios = ft.Button(content="👥 USUARIOS", bgcolor="#5c6bc0", color="white", height=40,
                                 visible=es_admin, on_click=lambda e: alternar_panel_admin())

        def cambiar_estado_usuario(usuario_id, activar):
            if db.cambiar_estado(uid, usuario_id, activar):
                mostrar_alerta("Usuario activado." if activar else "Usuario desactivado.")
            else:
                mostrar_alerta("No se pudo cambiar el estado.", True)
            renderizar_usuarios()

        def rechazar_usuario(usuario_id):
            if db.rechazar_usuario(uid, usuario_id):
                mostrar_alerta("Solicitud rechazada.")
            else:
                mostrar_alerta("Solo se pueden rechazar solicitudes sin pedidos.", True)
            renderizar_usuarios()

        def renderizar_usuarios():
            usuarios = db.listar_usuarios(uid)
            pendientes = sum(1 for u in usuarios if not u["activo"])
            btn_usuarios.content = f"👥 USUARIOS ({pendientes} pendiente(s))" if pendientes else "👥 USUARIOS"

            filas = []
            for u in usuarios:
                if u["rol"] == "admin":
                    estado_txt = "👑 Administrador"
                    acciones = []
                else:
                    estado_txt = "✅ Activo" if u["activo"] else "⏳ Pendiente / desactivado"
                    acciones = [
                        ft.Button(
                            content="Desactivar" if u["activo"] else "Activar",
                            bgcolor="#c62828" if u["activo"] else "#00897b",
                            color="white", height=32,
                            on_click=lambda e, i=u["id"], a=u["activo"]: cambiar_estado_usuario(i, not a)
                        )
                    ]
                    if not u["activo"]:
                        acciones.append(
                            ft.Button(content="Rechazar", bgcolor="#757575", color="white", height=32,
                                      on_click=lambda e, i=u["id"]: rechazar_usuario(i))
                        )
                filas.append(
                    ft.DataRow(cells=[
                        ft.DataCell(ft.Text(u["rut"], size=13)),
                        ft.DataCell(ft.Text(u["nombre"], size=13)),
                        ft.DataCell(ft.Text(u["correo"] or "-", size=13)),
                        ft.DataCell(ft.Text(estado_txt, size=13)),
                        ft.DataCell(ft.Row(acciones, spacing=6)),
                    ])
                )

            tabla = ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("RUT", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Nombre", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Correo", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD)),
                    ft.DataColumn(ft.Text("Acción", weight=ft.FontWeight.BOLD)),
                ],
                rows=filas,
                column_spacing=24,
                divider_thickness=1,
            )
            panel_admin.controls = [
                ft.Text("Administración de usuarios", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("Un usuario desactivado no puede ingresar y su sesión abierta se cierra. "
                        "Sus datos se conservan y siguen siendo privados.", size=13, color="#666666"),
                ft.Row([tabla], scroll=ft.ScrollMode.AUTO),
                ft.Divider(height=10),
            ]
            page.update()

        def alternar_panel_admin():
            if not es_admin or not sesion_activa():
                return
            panel_admin.visible = not panel_admin.visible
            if panel_admin.visible:
                renderizar_usuarios()
            page.update()

        def guardar_pedido(e):
            if not sesion_activa():
                return
            fecha_val = txt_fecha.value.strip()
            sg_val = txt_sg.value.strip()
            skus, arts = obtener_valores_numericos()

            if not fecha_val or not sg_val:
                mostrar_alerta("Por favor ingresa la Fecha y el número de SG.", es_error=True)
                return

            if db.verificar_sg_existente(sg_val, uid):
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
            db.insertar_pedido(fecha_val, sg_val, rg_tipo.value, skus, arts, ingreso, uid)

            txt_sg.value = ""
            txt_skus.value = ""
            txt_articulos.value = ""
            actualizar_vista_previa_monto()
            estado["mostrar"] = True
            actualizar_vista_diaria()

            mostrar_alerta("Pedido registrado correctamente.")

        encabezado = ft.Row(
            [
                ft.Text(f"👤 {usuario['nombre']}" + ("  (Administrador)" if es_admin else ""),
                        size=16, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        btn_usuarios,
                        ft.Button(content="Cerrar sesión", bgcolor="#757575", color="white", height=40,
                                  on_click=lambda e: cerrar_sesion()),
                    ],
                    spacing=8, wrap=True
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True
        )

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
            encabezado,
            panel_admin,
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
                    boton_rango("🧹 BORRAR CONSULTA", "#c62828", borrar_consulta),
                ],
                wrap=True,
                spacing=10
            ),
            ft.Divider(height=20),
            lbl_titulo_lista,
            lista_pedidos_container
        )

        actualizar_vista_diaria()
        if es_admin:
            renderizar_usuarios()
        ajustar_ancho()

    mostrar_login()

if __name__ == "__main__":
<<<<<<< HEAD
    ft.run(main)
=======
    ft.run(main)
>>>>>>> fd06846 (Actualiza interfaz, edicion de pedidos y rutas)
