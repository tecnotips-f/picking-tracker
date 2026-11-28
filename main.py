import flet as ft
from datetime import datetime, timedelta
import threading
import platform
import os
import re
import io
import asyncio

try:
    import cv2          # Solo en PC/laptop (webcam). El APK no lo incluye.
except ImportError:
    cv2 = None
try:
    import numpy as np
except ImportError:
    np = None
try:
    from PIL import Image     # Decodifica fotogramas JPEG de la cámara en el móvil
except ImportError:
    Image = None
try:
    import zxingcpp     # Opcional en PC/laptop
except ImportError:
    zxingcpp = None
try:
    from code128 import decodificar_code128     # Decodificador propio (sirve en el APK)
except ImportError:
    decodificar_code128 = None

from calculator import calcular_ingreso
from database import DatabaseManager
from firebase_sync import FirebaseCloudSync
from pdf_report import generar_pdf_consulta
from seguridad import normalizar_rut, validar_rut, validar_id_boosmap

try:
    import flet_camera as fc                      # Cámara del móvil
    import flet_permission_handler as fph         # Permiso de cámara en Android
except ImportError:
    fc = None
    fph = None

if platform.system() == "Windows":
    import winsound


def _decodificar_frame(frame):
    """Lee un código de barras de un fotograma en PC/laptop. Devuelve el texto exacto o None."""
    if zxingcpp is not None:
        res = zxingcpp.read_barcodes(frame)
        if res and res[0].text.strip():
            return res[0].text.strip()
        return None
    if decodificar_code128 is not None:
        return decodificar_code128(frame)
    return None


def main(page: ft.Page):
    page.title = "Control de Picking"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 16
    page.scroll = ft.ScrollMode.ADAPTIVE

    db = DatabaseManager()
    cloud = FirebaseCloudSync()

    es_movil = (not page.web) and page.platform in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS)
    haptic = None
    permiso_camara = None
    if es_movil:
        haptic = ft.HapticFeedback()
        page.services.append(haptic)
        if fph is not None:
            permiso_camara = fph.PermissionHandler()
            page.services.append(permiso_camara)

    def senal(ok=True):
        """Aviso al usuario: pitido en Windows y pulso háptico doble en el móvil."""
        if platform.system() == "Windows":
            try:
                winsound.Beep(2500, 300) if ok else winsound.Beep(1000, 600)
            except Exception:
                pass
            return
        if haptic is not None:
            async def _pulso_movil():
                try:
                    if ok:
                        await haptic.heavy_impact()
                        await asyncio.sleep(0.09)
                        await haptic.medium_impact()
                    else:
                        await haptic.vibrate()
                        await asyncio.sleep(0.14)
                        await haptic.vibrate()
                except Exception:
                    try:
                        await haptic.vibrate()
                    except Exception:
                        pass
            try:
                page.run_task(_pulso_movil)
            except Exception:
                pass

    def mostrar_alerta(mensaje, es_error=False, ms=2500):
        """Muestra notificaciones visuales temporizadas."""
        snack = ft.SnackBar(
            content=ft.Text(mensaje, color="white", weight=ft.FontWeight.BOLD),
            bgcolor="red" if es_error else "green",
            duration=ms,
        )
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
    #  PANTALLA DE ACCESO
    # =====================================================================
    def mostrar_login(aviso=None):
        page.clean()
        page.overlay.clear()
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
            rut_ingresado = normalizar_rut(txt_rut.value or "")
            clave_ingresada = (txt_clave.value or "").strip()
            resultado, dato = db.autenticar(rut_ingresado, clave_ingresada)

            if resultado in ("credenciales", "inactivo") and cloud.configurado:
                estado_nube = cloud.autenticar_solo_login(rut_ingresado, clave_ingresada)
                if estado_nube == "ok":
                    perfil = cloud.obtener_perfil_usuario(rut_ingresado)
                    if perfil:
                        usuario_local = db.sincronizar_usuario_nube(
                            rut_ingresado,
                            perfil["nombre"],
                            perfil["correo"],
                            clave_plana=clave_ingresada,
                            rol=perfil["rol"],
                            activo=perfil["activo"],
                        )
                        if perfil["activo"] and usuario_local:
                            db.guardar_sesion_local(rut_ingresado, clave_ingresada)
                            iniciar_app(usuario_local, clave_ingresada)
                            return
                        else:
                            mostrar_alerta("Tu cuenta está pendiente de activación por el administrador.", True, 4500)
                            return

            if resultado == "ok":
                db.guardar_sesion_local(rut_ingresado, clave_ingresada)
                iniciar_app(dato, clave_ingresada)
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
            subido_nube = False
            if cloud.configurado:
                if cloud.autenticar_o_registrar(rut, id_b):
                    subido_nube = cloud.guardar_perfil_usuario(rut, nombre, correo, rol="usuario", activo=False)
                    cloud.id_token = None

            if subido_nube:
                mostrar_alerta("Solicitud enviada a la nube. El administrador ya puede verla y activarla.", False, 5000)
                for campo in (reg_rut, reg_nombre, reg_correo, reg_id, reg_id2):
                    campo.value = ""
                txt_rut.value = rut
                ir_a(registro=False)
            elif ok:
                mostrar_alerta("Guardado solo en este teléfono (sin conexión a la nube). Revisa tu internet e inténtalo de nuevo.", True, 5000)
            else:
                mostrar_alerta(mensaje, True, 5000)

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
    def iniciar_app(usuario, clave_sesion=""):
        page.clean()
        page.overlay.clear()
        page.bgcolor = None
        uid = usuario["id"]
        rut_usuario = usuario["rut"]
        es_admin = usuario["rol"] == "admin"

        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        primer_dia_mes = datetime.now().replace(day=1).strftime("%Y-%m-%d")

        estado = {
            "rango": None,
            "mostrar": True,
            "sincronizando": False,
            "vista": "inicio",
            "registros": [],
            "periodo_texto": ""
        }
        tarifas = {"vigentes": db.obtener_tarifas()}

        # ---- Botón / Indicador de estado de Firebase ----
        btn_sync = ft.Button(
            content="☁️ Nube",
            bgcolor="#546e7a",
            color="white",
            height=40,
            tooltip="Sincronizar registros con Firebase (cpicking)",
            on_click=lambda e: lanzar_sincronizacion(descargar=True, avisar=True),
        )

        def actualizar_badge_nube(conectado=None):
            pendientes = len(db.obtener_pendientes_sync(uid))
            if not cloud.configurado:
                btn_sync.content = "⚠️ Sin API Key"
                btn_sync.bgcolor = "#e65100"
            elif pendientes > 0:
                btn_sync.content = f"⏳ {pendientes} pendiente(s)"
                btn_sync.bgcolor = "#ef6c00"
            elif conectado is False:
                btn_sync.content = "📴 Offline"
                btn_sync.bgcolor = "#616161"
            else:
                btn_sync.content = "☁️ Sincronizado"
                btn_sync.bgcolor = "#2e7d32"
            try:
                page.update()
            except Exception:
                pass

        def _tarea_sincronizar(descargar=False, avisar=False, eliminar_sg=None):
            if estado["sincronizando"]:
                return
            estado["sincronizando"] = True
            try:
                if not cloud.configurado:
                    actualizar_badge_nube(False)
                    if avisar:
                        mostrar_alerta("Falta configurar FIREBASE_API_KEY en firebase_sync.py.", True, 3500)
                    return

                if not cloud.id_token and clave_sesion:
                    cloud.autenticar_o_registrar(rut_usuario, clave_sesion)

                if not cloud.id_token:
                    actualizar_badge_nube(False)
                    if avisar:
                        mostrar_alerta("Sin conexión a Firebase. Los datos siguen a salvo en el teléfono.", True, 3000)
                    return

                cloud.guardar_perfil_usuario(
                    rut_usuario, usuario["nombre"], usuario.get("correo"), usuario["rol"], usuario["activo"]
                )

                tarifas_nube = cloud.descargar_tarifas()
                if tarifas_nube:
                    tarifas["vigentes"] = tarifas_nube
                    actualizar_vista_previa_monto()

                if es_admin:
                    remotos_u = cloud.listar_todos_usuarios()
                    for u_rem in remotos_u:
                        if u_rem["rut"] != rut_usuario:
                            db.sincronizar_usuario_nube(
                                u_rem["rut"], u_rem["nombre"], u_rem["correo"],
                                rol=u_rem["rol"], activo=u_rem["activo"]
                            )
                    renderizar_usuarios()

                if eliminar_sg:
                    cloud.eliminar_pedido_nube(rut_usuario, eliminar_sg)

                pendientes = db.obtener_pendientes_sync(uid)
                subidos = 0
                for p in pendientes:
                    if cloud.subir_pedido(rut_usuario, p):
                        db.marcar_sincronizado(p["id"])
                        subidos += 1

                importados = 0
                if descargar:
                    remotos = cloud.descargar_pedidos(rut_usuario)
                    if remotos:
                        importados = db.importar_desde_nube(uid, remotos)
                        if importados > 0:
                            actualizar_vista_diaria()

                actualizar_badge_nube(True)
                if avisar:
                    mostrar_alerta(f"Nube al día: {subidos} subido(s), {importados} recuperado(s).")
            finally:
                estado["sincronizando"] = False

        def lanzar_sincronizacion(descargar=False, avisar=False, eliminar_sg=None):
            threading.Thread(
                target=_tarea_sincronizar,
                args=(descargar, avisar, eliminar_sg),
                daemon=True,
            ).start()

        def calcular_monto(tipo, skus, arts):
            return calcular_ingreso(tipo, skus, arts, tarifas["vigentes"])

        def cerrar_sesion(aviso=None):
            camara_activa.clear()
            cam_estado["activa"] = False
            cam_estado["cam"] = None
            cam_estado["token"] += 1
            overlay_camara.visible = False
            cloud.id_token = None
            cloud.refresh_token = None
            db.borrar_sesion_local()
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
            keyboard_type=ft.KeyboardType.NUMBER,
            on_submit=lambda e: procesar_texto_escaneado(txt_sg.value)
        )

        rg_tipo = ft.RadioGroup(
            value="Picking",
            on_change=lambda e: actualizar_vista_previa_monto(),
            content=ft.Row([
                ft.Radio(value="Picking", label="Picking"),
                ft.Radio(value="Driver", label="Driver"),
                ft.Radio(value="Shopper", label="Shopper"),
            ], wrap=False, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
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

        def _limpiar_campos_pedido():
            txt_sg.value = ""
            txt_skus.value = ""
            txt_articulos.value = ""
            actualizar_vista_previa_monto()

        def procesar_texto_escaneado(texto_crudo):
            """Procesa 'SG|SKUs|Cantidad' o SG individual y rellena los campos."""
            datos = (texto_crudo or "").strip()
            partes = [p.strip() for p in re.split(r"[|;	]", datos)]
            sg_encontrado = partes[0]

            skus_detectados = 0
            arts_detectados = 0
            if len(partes) == 3 and partes[1].isdigit() and partes[2].isdigit():
                skus_detectados = int(partes[1])
                arts_detectados = int(partes[2])

            if not sg_encontrado:
                senal(False)
                _limpiar_campos_pedido()
                mostrar_alerta("No se pudo leer un código válido.", es_error=True, ms=3000)
                return

            if db.verificar_sg_existente(sg_encontrado, uid):
                mostrar_alerta(f"⚠️ El SG '{sg_encontrado}' ya existe en la base de datos.", es_error=True, ms=3500)
                senal(False)
                _limpiar_campos_pedido()
                return

            senal(True)

            txt_sg.value = sg_encontrado
            txt_skus.value = str(skus_detectados)
            txt_articulos.value = str(arts_detectados)

            actualizar_vista_previa_monto()
            mostrar_alerta(f"¡Leído! SG {sg_encontrado} | SKUs {txt_skus.value} | Cant. {txt_articulos.value}")
            try:
                txt_sg.focus()
            except Exception:
                pass

        # =================================================================
        #  MOTOR DE ESCÁNER ÓPTICO ADAPTATIVO (PAPEL, PLÁSTICO BRILLANTE/MATE)
        # =================================================================
        TIEMPO_MAX_ESCANEO = 15

        camara_activa = threading.Event()
        hilo_cam = {"t": None}

        def _estado_boton(activo):
            btn_escanear.content = "⏹ DETENER CÁMARA" if activo else "📷 ACTIVAR CÁMARA Y ESCANEAR CÓDIGO"
            btn_escanear.bgcolor = "#c62828" if activo else "#00897b"
            page.update()

        def escanear_con_webcam_pc():
            cap = None
            codigo_encontrado = None
            error_camara = None
            try:
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW) if platform.system() == "Windows" else cv2.VideoCapture(0)
                if not cap.isOpened():
                    error_camara = "No se pudo abrir la cámara."
                    return

                ventana_nombre = "Escaner - Enfoque el codigo (ESC para salir)"
                inicio = datetime.now()

                while camara_activa.is_set():
                    if (datetime.now() - inicio).total_seconds() >= TIEMPO_MAX_ESCANEO:
                        error_camara = "No se detectó ningún código de barras o QR."
                        break

                    ret, frame = cap.read()
                    if not ret or frame is None:
                        error_camara = "Error al capturar imagen de la cámara."
                        break

                    codigo_encontrado = _decodificar_frame(frame)
                    if codigo_encontrado:
                        break

                    cv2.imshow(ventana_nombre, frame)
                    if cv2.waitKey(1) & 0xFF == 27:
                        break
                    if cv2.getWindowProperty(ventana_nombre, cv2.WND_PROP_VISIBLE) < 1:
                        break
            except Exception as ex:
                error_camara = f"Error en el escáner: {ex}"
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

            if codigo_encontrado:
                procesar_texto_escaneado(codigo_encontrado)
            elif error_camara:
                senal(False)
                mostrar_alerta(error_camara, es_error=True, ms=3000)

        cam_estado = {
            "cam": None,
            "activa": False,
            "procesando": False,
            "token": 0,
            "ultimo_codigo": None,
            "ultimo_ts": None,
            "linterna": False,
        }
        visor_camara_stack = ft.Stack(expand=True)
        overlay_camara = ft.Container(
            visible=False,
            expand=True,
            bgcolor="black",
            left=0,
            top=0,
            right=0,
            bottom=0,
            content=visor_camara_stack,
        )
        page.overlay.append(overlay_camara)

        _detector_qr = cv2.QRCodeDetector() if cv2 is not None else None

        def _normalizar_superficie_fila(fila):
            """Corrige reflejos especulares de plástico brillante y sombras de papel mate en 1D.

            1. Recorta brillos especulares (percentil 92) para que un destello sobre bolsa plástica
               no dispare el umbral blanco artificialmente.
            2. Aplica fondo local deslizante (top-hat / baseline adaptativo) para compensar
               iluminación desigual o curvas en envases.
            """
            n = len(fila)
            p5 = float(np.percentile(fila, 5))
            p92 = float(np.percentile(fila, 92))
            if p92 - p5 < 34.0:
                return None

            # Recorte anti-reflejo (glare suppression)
            f_clip = np.clip(fila, p5, p92)

            # Línea base local (ventana ~1/7 del ancho) para compensar sombras y reflejos laterales
            win = max(29, (n // 7) | 1)
            pad = win // 2
            f_pad = np.pad(f_clip, pad, mode="edge")
            windows = np.lib.stride_tricks.as_strided(
                f_pad, shape=(n, win), strides=(f_pad.strides[0], f_pad.strides[0])
            )
            lo = np.min(windows, axis=1)
            hi = np.max(windows, axis=1)
            rango = hi - lo
            if float(np.percentile(rango, 75)) < 28.0:
                return None

            # Normalización [0..1] por ventana local (invariante a brillo/mate)
            norm = np.where(rango > 22.0, (f_clip - lo) / np.maximum(rango, 1.0), 1.0)
            return norm.astype(np.float32)

        def _decodificar_qr_puro(gris):
            """Decodificador omnidireccional de códigos QR (Versiones 1-6) en NumPy puro."""
            if np is None or gris is None or gris.ndim != 2:
                return None

            def _intentar_qr(img_g):
                h, w = img_g.shape
                if min(h, w) < 60:
                    return None

                bajo, alto = np.percentile(img_g, 8), np.percentile(img_g, 90)
                if alto - bajo < 40:
                    return None
                # Recorte de brillos de plástico antes de umbralizar
                img_clip = np.clip(img_g, bajo, alto)
                umbral = (bajo + alto) * 0.5
                bin_img = img_clip < umbral

                def _buscar_patrones_fila(fila_bool):
                    cambios = np.flatnonzero(fila_bool[1:] != fila_bool[:-1]) + 1
                    bordes = np.concatenate(([0], cambios, [len(fila_bool)]))
                    longs = np.diff(bordes)
                    inicios = bordes[:-1]
                    es_negro = fila_bool[inicios]
                    centros = []
                    for idx in range(len(longs) - 4):
                        if not es_negro[idx]:
                            continue
                        r0, r1, r2, r3, r4 = longs[idx:idx + 5]
                        mod = (r0 + r1 + r2 + r3 + r4) / 7.0
                        if mod < 1.6:
                            continue
                        tol = mod * 0.50
                        if (abs(r0 - mod) < tol and abs(r1 - mod) < tol and
                                abs(r2 - 3 * mod) < tol * 1.5 and
                                abs(r3 - mod) < tol and abs(r4 - mod) < tol):
                            cx = inicios[idx] + (r0 + r1 + r2 + r3 + r4) / 2.0
                            centros.append((cx, mod))
                    return centros

                candidatos = []
                for y in range(2, h - 2, 2):
                    for cx, mod in _buscar_patrones_fila(bin_img[y]):
                        ix = int(round(cx))
                        if 0 <= ix < w:
                            col_ok = False
                            for cy_col, mod_col in _buscar_patrones_fila(bin_img[:, ix]):
                                if abs(cy_col - y) < mod * 1.4 and abs(mod_col - mod) < mod * 0.45:
                                    candidatos.append((cx, float(cy_col), (mod + mod_col) / 2.0))
                                    col_ok = True
                                    break
                            if col_ok and len(candidatos) > 100:
                                break
                    if len(candidatos) > 100:
                        break

                if len(candidatos) < 3:
                    return None

                clusters = []
                for cx, cy, mod in candidatos:
                    agregado = False
                    for cl in clusters:
                        if abs(cl[0] - cx) < mod * 2.5 and abs(cl[1] - cy) < mod * 2.5:
                            n_c = cl[3]
                            cl[0] = (cl[0] * n_c + cx) / (n_c + 1)
                            cl[1] = (cl[1] * n_c + cy) / (n_c + 1)
                            cl[2] = (cl[2] * n_c + mod) / (n_c + 1)
                            cl[3] = n_c + 1
                            agregado = True
                            break
                    if not agregado:
                        clusters.append([cx, cy, mod, 1])

                clusters = [c for c in clusters if c[3] >= 2]
                if len(clusters) < 3:
                    return None

                clusters.sort(key=lambda c: -c[3])
                pts = clusters[:6]

                mejor_trio = None
                mejor_err = 999.0
                for i in range(len(pts)):
                    for j in range(len(pts)):
                        if j == i:
                            continue
                        for k in range(len(pts)):
                            if k == i or k == j:
                                continue
                            tl, tr, bl = pts[i], pts[j], pts[k]
                            vx1, vy1 = tr[0] - tl[0], tr[1] - tl[1]
                            vx2, vy2 = bl[0] - tl[0], bl[1] - tl[1]
                            d1 = (vx1 ** 2 + vy1 ** 2) ** 0.5
                            d2 = (vx2 ** 2 + vy2 ** 2) ** 0.5
                            if d1 < 22 or d2 < 22:
                                continue
                            cross = vx1 * vy2 - vy1 * vx2
                            if abs(cross) < d1 * d2 * 0.82:
                                continue
                            if cross < 0:
                                tr, bl = bl, tr
                                vx1, vy1, vx2, vy2 = vx2, vy2, vx1, vy1
                                d1, d2 = d2, d1
                            cos_ang = abs(vx1 * vx2 + vy1 * vy2) / (d1 * d2)
                            ratio = abs(d1 - d2) / max(d1, d2)
                            err = cos_ang + ratio
                            if cos_ang < 0.20 and ratio < 0.20 and err < mejor_err:
                                mejor_err = err
                                mejor_trio = (tl, tr, bl, d1, d2)

                if mejor_trio is None:
                    return None

                tl, tr, bl, d1, d2 = mejor_trio
                mod_est = (tl[2] + tr[2] + bl[2]) / 3.0
                n_mod_est = int(round(((d1 + d2) / 2.0) / mod_est)) + 7
                version = int(round((n_mod_est - 17) / 4.0))
                if version < 1 or version > 6:
                    return None
                dim = 17 + 4 * version

                span = float(dim - 7)
                ux, uy = (tr[0] - tl[0]) / span, (tr[1] - tl[1]) / span
                vx, vy = (bl[0] - tl[0]) / span, (bl[1] - tl[1]) / span
                ox = tl[0] - 3.5 * ux - 3.5 * vx
                oy = tl[1] - 3.5 * uy - 3.5 * vy

                matriz = np.zeros((dim, dim), dtype=int)
                for r in range(dim):
                    for c in range(dim):
                        px = int(round(ox + (c + 0.5) * ux + (r + 0.5) * vx))
                        py = int(round(oy + (c + 0.5) * uy + (r + 0.5) * vy))
                        if 0 <= px < w and 0 <= py < h:
                            matriz[r, c] = 1 if bin_img[py, px] else 0

                fmt_coords = [
                    (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
                    (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)
                ]
                raw_fmt = 0
                for fr, fc_idx in fmt_coords:
                    raw_fmt = (raw_fmt << 1) | int(matriz[fr, fc_idx])
                raw_fmt ^= 0x5412

                def _bch_format(data5):
                    d = data5 << 10
                    for bit in range(4, -1, -1):
                        if d & (1 << (bit + 10)):
                            d ^= 0x537 << bit
                    return (data5 << 10) | d

                mejor_fmt = None
                min_dist = 3
                for cand5 in range(32):
                    val15 = _bch_format(cand5)
                    dist = bin(val15 ^ raw_fmt).count("1")
                    if dist < min_dist:
                        min_dist = dist
                        mejor_fmt = cand5
                if mejor_fmt is None:
                    return None

                ecc_level = (mejor_fmt >> 3) & 0x3
                mask_id = mejor_fmt & 0x7

                func = np.zeros((dim, dim), dtype=bool)
                func[:9, :9] = True
                func[:9, dim - 8:] = True
                func[dim - 8:, :9] = True
                func[6, :] = True
                func[:, 6] = True
                if version >= 2:
                    ap = dim - 7
                    func[ap - 2:ap + 3, ap - 2:ap + 3] = True

                def _aplicar_mascara(m_id, r, c):
                    if m_id == 0:
                        return (r + c) % 2 == 0
                    if m_id == 1:
                        return r % 2 == 0
                    if m_id == 2:
                        return c % 3 == 0
                    if m_id == 3:
                        return (r + c) % 3 == 0
                    if m_id == 4:
                        return ((r // 2) + (c // 3)) % 2 == 0
                    if m_id == 5:
                        return ((r * c) % 2) + ((r * c) % 3) == 0
                    if m_id == 6:
                        return (((r * c) % 2) + ((r * c) % 3)) % 2 == 0
                    return (((r + c) % 2) + ((r * c) % 3)) % 2 == 0

                bits = []
                col = dim - 1
                subiendo = True
                while col > 0:
                    if col == 6:
                        col -= 1
                    filas_iter = range(dim - 1, -1, -1) if subiendo else range(dim)
                    for r in filas_iter:
                        for dc in (0, -1):
                            c = col + dc
                            if not func[r, c]:
                                val = matriz[r, c] ^ (1 if _aplicar_mascara(mask_id, r, c) else 0)
                                bits.append(val)
                    subiendo = not subiendo
                    col -= 2

                codewords = []
                for i in range(0, len(bits) - 7, 8):
                    cw = 0
                    for b in bits[i:i + 8]:
                        cw = (cw << 1) | b
                    codewords.append(cw)

                _CAP_QR = {
                    (1, 1): (26, 19), (1, 0): (26, 16), (1, 3): (26, 13), (1, 2): (26, 9),
                    (2, 1): (44, 34), (2, 0): (44, 28), (2, 3): (44, 22), (2, 2): (44, 16),
                    (3, 1): (70, 55), (3, 0): (70, 44), (3, 3): (70, 34), (3, 2): (70, 26),
                    (4, 1): (100, 80), (4, 0): (100, 64), (4, 3): (100, 48), (4, 2): (100, 36),
                    (5, 1): (134, 108), (5, 0): (134, 86), (5, 3): (134, 62), (5, 2): (134, 46),
                    (6, 1): (172, 136), (6, 0): (172, 108), (6, 3): (172, 76), (6, 2): (172, 60),
                }
                cap = _CAP_QR.get((version, ecc_level))
                if not cap or len(codewords) < cap[0]:
                    return None

                data_cw = codewords[:cap[1]]
                dbits = []
                for cw in data_cw:
                    for s in range(7, -1, -1):
                        dbits.append((cw >> s) & 1)

                def _leer_bits(pos, n_b):
                    if pos + n_b > len(dbits):
                        return None, pos
                    v = 0
                    for b in dbits[pos:pos + n_b]:
                        v = (v << 1) | b
                    return v, pos + n_b

                pos = 0
                salida = []
                _ALNUM = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:"
                while pos + 4 <= len(dbits):
                    modo, pos = _leer_bits(pos, 4)
                    if modo == 0 or modo is None:
                        break
                    if modo == 1:
                        cnt, pos = _leer_bits(pos, 10)
                        if cnt is None:
                            return None
                        while cnt >= 3:
                            val, pos = _leer_bits(pos, 10)
                            if val is None or val >= 1000:
                                return None
                            salida.append(f"{val:03d}")
                            cnt -= 3
                        if cnt == 2:
                            val, pos = _leer_bits(pos, 7)
                            if val is None or val >= 100:
                                return None
                            salida.append(f"{val:02d}")
                        elif cnt == 1:
                            val, pos = _leer_bits(pos, 4)
                            if val is None or val >= 10:
                                return None
                            salida.append(f"{val:01d}")
                    elif modo == 2:
                        cnt, pos = _leer_bits(pos, 9)
                        if cnt is None:
                            return None
                        while cnt >= 2:
                            val, pos = _leer_bits(pos, 11)
                            if val is None or val >= 45 * 45:
                                return None
                            salida.append(_ALNUM[val // 45] + _ALNUM[val % 45])
                            cnt -= 2
                        if cnt == 1:
                            val, pos = _leer_bits(pos, 6)
                            if val is None or val >= 45:
                                return None
                            salida.append(_ALNUM[val])
                    elif modo == 4:
                        cnt, pos = _leer_bits(pos, 8)
                        if cnt is None:
                            return None
                        raw_b = bytearray()
                        for _ in range(cnt):
                            val, pos = _leer_bits(pos, 8)
                            if val is None:
                                return None
                            raw_b.append(val)
                        try:
                            salida.append(raw_b.decode("utf-8"))
                        except UnicodeDecodeError:
                            salida.append(raw_b.decode("latin-1", errors="ignore"))
                    else:
                        return None

                texto_final = "".join(salida).strip()
                return texto_final if texto_final else None

            res = _intentar_qr(gris)
            if res:
                return res
            return _intentar_qr(np.rot90(gris))

        def _decodificar_ean13_puro(gris):
            """Decodificador EAN-13 / UPC-A / EAN-8 adaptativo a papel mate y plástico brillante."""
            if np is None or gris is None or gris.ndim != 2:
                return None

            _PAT_L = {
                0: (3, 2, 1, 1), 1: (2, 2, 2, 1), 2: (2, 1, 2, 2), 3: (1, 4, 1, 1), 4: (1, 1, 3, 2),
                5: (1, 2, 3, 1), 6: (1, 1, 1, 4), 7: (1, 3, 1, 2), 8: (1, 2, 1, 3), 9: (3, 1, 1, 2),
            }
            _PAT_G = {d: pat[::-1] for d, pat in _PAT_L.items()}
            _PARIDAD_PRIMER_DIGITO = {
                "LLLLLL": 0, "LLGLGG": 1, "LLGGLG": 2, "LLGGGL": 3, "LGLLGG": 4,
                "LGGLLG": 5, "LGGGLL": 6, "LGLGLG": 7, "LGLGGL": 8, "LGGLGL": 9,
            }

            def _ajustar_digito(runs4, es_izq=True):
                total = float(runs4.sum())
                if total <= 0:
                    return None, None
                norm = (runs4 / total) * 7.0
                t1 = norm[0] + norm[1]
                t2 = norm[1] + norm[2]
                mejor_d, mejor_p, mejor_err = None, None, 999.0
                cands = [("L", d, p) for d, p in _PAT_L.items()]
                if es_izq:
                    cands += [("G", d, p) for d, p in _PAT_G.items()]
                for par, d, pat in cands:
                    err = abs(t1 - (pat[0] + pat[1])) + abs(t2 - (pat[1] + pat[2])) + 0.35 * float(np.max(np.abs(norm - pat)))
                    if err < mejor_err:
                        mejor_err, mejor_d, mejor_p = err, d, par
                if mejor_err > 1.15:
                    return None, None
                return mejor_d, mejor_p

            def _leer_fila_ean(fila):
                n = len(fila)
                if n < 110:
                    return None
                norm = _normalizar_superficie_fila(fila)
                if norm is None:
                    return None

                k = np.array([0.2, 0.6, 0.2], dtype=np.float32)
                f = np.convolve(norm, k, mode="same")
                bin_f = (f < 0.48).astype(np.uint8)

                cambios = np.flatnonzero(bin_f[1:] != bin_f[:-1]) + 1
                bordes = np.concatenate(([0], cambios, [n]))
                longs = np.diff(bordes).astype(np.float32)
                colores = bin_f[bordes[:-1]]

                # 1. EAN-13 / UPC-A (59 segmentos + quiet zone limpia)
                for idx in range(1, len(longs) - 59):
                    if colores[idx] != 1:
                        continue
                    runs = longs[idx:idx + 59]
                    u_ini = runs[0:3].mean()
                    u_cen = runs[27:32].mean()
                    u_fin = runs[56:59].mean()
                    if u_ini < 1.2 or abs(u_ini - u_fin) > u_ini * 0.45 or abs(u_ini - u_cen) > u_ini * 0.45:
                        continue
                    if longs[idx - 1] < u_ini * 4.5 or longs[idx + 59] < u_fin * 4.5:
                        continue
                    if (np.max(runs[0:3]) > u_ini * 1.75 or np.min(runs[0:3]) < u_ini * 0.40 or
                            np.max(runs[56:59]) > u_fin * 1.75 or np.min(runs[56:59]) < u_fin * 0.40):
                        continue

                    digitos, paridad, ok = [], [], True
                    for d in range(6):
                        dig, par = _ajustar_digito(runs[3 + d * 4: 3 + (d + 1) * 4], es_izq=True)
                        if dig is None:
                            ok = False
                            break
                        digitos.append(dig)
                        paridad.append(par)
                    if not ok:
                        continue

                    primer = _PARIDAD_PRIMER_DIGITO.get("".join(paridad))
                    if primer is None:
                        continue

                    for d in range(6):
                        dig, _ = _ajustar_digito(runs[32 + d * 4: 32 + (d + 1) * 4], es_izq=False)
                        if dig is None:
                            ok = False
                            break
                        digitos.append(dig)
                    if not ok:
                        continue

                    completo = [primer] + digitos
                    suma = sum(completo[i] * (1 if i % 2 == 0 else 3) for i in range(12))
                    if (10 - (suma % 10)) % 10 == completo[12]:
                        cod = "".join(str(x) for x in completo)
                        return cod[1:] if cod.startswith("0") else cod

                # 2. EAN-8 (43 segmentos + quiet zone limpia)
                for idx in range(1, len(longs) - 43):
                    if colores[idx] != 1:
                        continue
                    runs = longs[idx:idx + 43]
                    u_ini = runs[0:3].mean()
                    u_cen = runs[19:24].mean()
                    u_fin = runs[40:43].mean()
                    if u_ini < 1.2 or abs(u_ini - u_fin) > u_ini * 0.45 or abs(u_ini - u_cen) > u_ini * 0.45:
                        continue
                    if longs[idx - 1] < u_ini * 4.5 or longs[idx + 43] < u_fin * 4.5:
                        continue
                    digitos, ok = [], True
                    for d in range(4):
                        dig, par = _ajustar_digito(runs[3 + d * 4: 3 + (d + 1) * 4], es_izq=True)
                        if dig is None or par != "L":
                            ok = False
                            break
                        digitos.append(dig)
                    if not ok:
                        continue
                    for d in range(4):
                        dig, _ = _ajustar_digito(runs[24 + d * 4: 24 + (d + 1) * 4], es_izq=False)
                        if dig is None:
                            ok = False
                            break
                        digitos.append(dig)
                    if not ok:
                        continue
                    suma = sum(digitos[i] * (3 if i % 2 == 0 else 1) for i in range(7))
                    if (10 - (suma % 10)) % 10 == digitos[7]:
                        return "".join(str(x) for x in digitos)
                return None

            for img_o in (gris, np.rot90(gris)):
                h = img_o.shape[0]
                votos_ean = {}
                for y in np.linspace(int(h * 0.08), int(h * 0.92), 25, dtype=int):
                    y0, y1 = max(0, y - 1), min(h, y + 2)
                    res = _leer_fila_ean(img_o[y0:y1].mean(axis=0))
                    if res:
                        votos_ean[res] = votos_ean.get(res, 0) + 1
                        if votos_ean[res] >= 2:
                            return res
            return None

        def _decodificar_stream_o_bytes(evento):
            """Convierte eventos de flet_camera (YUV420/BGRA/JPEG) a array NumPy."""
            if np is None or evento is None:
                return None

            raw = None
            if isinstance(evento, (bytes, bytearray, memoryview)):
                raw = bytes(evento)
            else:
                for attr in ("bytes", "data", "image", "frame"):
                    val = getattr(evento, attr, None)
                    if isinstance(val, (bytes, bytearray, memoryview)) and len(val) > 0:
                        raw = bytes(val)
                        break

            if raw:
                if cv2 is not None:
                    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is not None:
                        return frame
                if Image is not None:
                    try:
                        pil_img = Image.open(io.BytesIO(raw)).convert("RGB")
                        return np.asarray(pil_img)
                    except Exception:
                        pass

            planes = getattr(evento, "planes", None)
            width = getattr(evento, "width", None)
            height = getattr(evento, "height", None)
            if planes and width and height:
                try:
                    p0 = planes[0]
                    p0_bytes = getattr(p0, "bytes", None)
                    row_stride = getattr(p0, "bytes_per_row", width) or width
                    px_stride = getattr(p0, "bytes_per_pixel", 1) or 1
                    if p0_bytes:
                        buf = np.frombuffer(p0_bytes, dtype=np.uint8)
                        if px_stride >= 3 and len(buf) >= height * row_stride:
                            mat = buf[:height * row_stride].reshape((height, row_stride))
                            return mat[:, :width * px_stride].reshape((height, width, px_stride))[:, :, :3]
                        if len(buf) >= height * row_stride:
                            y_plane = buf[:height * row_stride].reshape((height, row_stride))[:, :width]
                            return y_plane.copy()
                except Exception as ex:
                    print(f"Error plano YUV: {ex}")

            if raw and width and height:
                try:
                    buf = np.frombuffer(raw, dtype=np.uint8)
                    if len(buf) >= width * height:
                        return buf[:width * height].reshape((height, width)).copy()
                except Exception:
                    pass

            return None

        def _decodificar_code128_adaptativo(gris):
            """Barrido Code 128 rápido con normalización local anti-reflejo y validación en 3 filas paralelas."""
            if decodificar_code128 is None:
                return None
            try:
                from code128 import _decodificar_runs, _runs_de_fila, _suavizar, _girar

                def _leer_fila(img_g, y):
                    h = img_g.shape[0]
                    y0, y1 = max(0, y - 1), min(h, y + 2)
                    fila = img_g[y0:y1].mean(axis=0)
                    norm = _normalizar_superficie_fila(fila)
                    if norm is None:
                        return None

                    for k in (1, 3):
                        f = _suavizar(norm, k)
                        for umbral in (0.48, 0.42):
                            for sentido in (f, f[::-1]):
                                res = _runs_de_fila(sentido, umbral)
                                if res is None:
                                    continue
                                txt = _decodificar_runs(res[0], res[1])
                                if txt and len(txt) >= 6:
                                    return txt
                    return None

                def _barrido_confirmado(img_g, n_lineas=29):
                    h, w = img_g.shape
                    if w < 80:
                        return None
                    ys = np.linspace(int(h * 0.06), int(h * 0.94), n_lineas, dtype=int)
                    for y in ys:
                        txt = _leer_fila(img_g, y)
                        if txt:
                            coincidencias = 1
                            for dy in (-4, 4, -8, 8):
                                y2 = y + dy
                                if 0 <= y2 < h and _leer_fila(img_g, y2) == txt:
                                    coincidencias += 1
                                    if coincidencias >= 3:
                                        return txt
                    return None

                for orient in (gris, np.rot90(gris)):
                    t = _barrido_confirmado(orient, n_lineas=29)
                    if t:
                        return t

                for orient in (gris, np.rot90(gris)):
                    for ang in (-6, 6):
                        g_rot = _girar(orient, ang)
                        if g_rot is not None:
                            t = _barrido_confirmado(g_rot, n_lineas=17)
                            if t:
                                return t
            except Exception:
                return decodificar_code128(gris)
            return None

        def _leer_codigo_desde_frame(frame):
            if frame is None or np is None:
                return None
            try:
                h, w = frame.shape[:2]
                y1, y2 = int(h * 0.06), int(h * 0.94)
                x1, x2 = int(w * 0.04), int(w * 0.96)
                recorte = frame[y1:y2, x1:x2]

                # 1. PC / Laptop
                if zxingcpp is not None or _detector_qr is not None:
                    for base in (recorte, frame):
                        for rot in (0, -1):
                            img_c = np.ascontiguousarray(base if rot == 0 else np.rot90(base, rot))
                            texto = _decodificar_frame(img_c)
                            if texto:
                                return texto
                            if _detector_qr is not None:
                                t_qr, _, _ = _detector_qr.detectAndDecode(img_c)
                                if t_qr and t_qr.strip():
                                    return t_qr.strip()
                    return None

                # 2. Móvil Android
                if recorte.ndim == 3:
                    gris = recorte[:, :, :3].mean(axis=2).astype(np.float32)
                else:
                    gris = recorte.astype(np.float32)

                if max(gris.shape) > 1080:
                    gris = gris[::2, ::2]

                # 2a. Códigos Code 128 (SG / SG|SKUs|Cant)
                texto_bar = _decodificar_code128_adaptativo(gris)
                if texto_bar:
                    return texto_bar

                # 2b. Códigos QR de bultos
                texto_qr_puro = _decodificar_qr_puro(gris)
                if texto_qr_puro:
                    return texto_qr_puro

                # 2c. Códigos comerciales EAN-13 / UPC-A / EAN-8
                texto_ean = _decodificar_ean13_puro(gris)
                if texto_ean:
                    return texto_ean
            except Exception as ex:
                print(f"Error leyendo frame: {ex}")
            return None

        async def cerrar_camara_movil(mensaje_error=None):
            cam_estado["activa"] = False
            cam_estado["token"] += 1
            cam_estado["ultimo_codigo"] = None
            cam_estado["ultimo_ts"] = None
            cam = cam_estado["cam"]
            cam_estado["cam"] = None
            if cam is not None:
                try:
                    if cam_estado["linterna"]:
                        await cam.set_flash_mode(fc.FlashMode.OFF)
                except Exception:
                    pass
                try:
                    await cam.stop_image_stream()
                except Exception:
                    pass
            cam_estado["linterna"] = False
            visor_camara_stack.controls.clear()
            overlay_camara.visible = False
            _estado_boton(False)
            if mensaje_error:
                senal(False)
                mostrar_alerta(mensaje_error, es_error=True, ms=3500)

        async def _temporizador_escaneo(token_actual, segundos=TIEMPO_MAX_ESCANEO):
            await asyncio.sleep(segundos)
            if cam_estado["activa"] and cam_estado["token"] == token_actual:
                await cerrar_camara_movil("No se detectó ningún código de barras o QR.")

        async def _al_recibir_cuadro(e):
            if not cam_estado["activa"] or cam_estado["procesando"]:
                return
            frame = _decodificar_stream_o_bytes(e)
            if frame is None:
                return
            cam_estado["procesando"] = True
            try:
                texto = await asyncio.to_thread(_leer_codigo_desde_frame, frame)
            finally:
                cam_estado["procesando"] = False

            if not texto or not cam_estado["activa"]:
                return

            # Consenso obligatorio de 2 fotogramas consecutivos (< 0.9s) para cero falsos positivos
            ahora = datetime.now()
            previo = cam_estado.get("ultimo_codigo")
            previo_ts = cam_estado.get("ultimo_ts")
            cam_estado["ultimo_codigo"] = texto
            cam_estado["ultimo_ts"] = ahora

            if previo == texto and previo_ts is not None and (ahora - previo_ts).total_seconds() <= 0.9:
                await cerrar_camara_movil()
                procesar_texto_escaneado(texto)

        async def abrir_camara_movil():
            if fc is None or permiso_camara is None:
                senal(False)
                mostrar_alerta("El escaneo con cámara no está disponible en este dispositivo. Ingresa el SG manualmente.",
                               es_error=True, ms=3000)
                return
            try:
                permiso = await permiso_camara.request(fph.Permission.CAMERA)
            except Exception:
                permiso = None
            if permiso != fph.PermissionStatus.GRANTED:
                senal(False)
                mostrar_alerta("Sin permiso de cámara. Actívalo en Ajustes o ingresa el SG manualmente.",
                               es_error=True, ms=3500)
                return

            cam = fc.Camera(
                expand=True,
                preview_enabled=True,
                on_stream_image=_al_recibir_cuadro,
            )

            async def _alternar_linterna(ev):
                if cam_estado["cam"] is None:
                    return
                try:
                    nuevo = not cam_estado["linterna"]
                    await cam_estado["cam"].set_flash_mode(
                        fc.FlashMode.TORCH if nuevo else fc.FlashMode.OFF
                    )
                    cam_estado["linterna"] = nuevo
                    btn_linterna.content = "🔦 LINTERNA: ON" if nuevo else "🔦 LINTERNA: OFF"
                    btn_linterna.bgcolor = "#f57c00" if nuevo else "#37474f"
                    page.update()
                except Exception:
                    mostrar_alerta("Linterna no disponible en este equipo.", es_error=True, ms=2000)

            async def _reenfocar(ev):
                if cam_estado["cam"] is None:
                    return
                try:
                    await cam_estado["cam"].set_focus_mode(fc.FocusMode.AUTO)
                    await cam_estado["cam"].set_focus_point(ft.Offset(0.5, 0.5))
                except Exception:
                    pass

            btn_linterna = ft.Button(
                content="🔦 LINTERNA: OFF",
                bgcolor="#37474f",
                color="white",
                height=44,
                on_click=_alternar_linterna,
            )

            guia_enfoque = ft.Container(
                expand=True,
                alignment=ft.Alignment(0, 0),
                on_click=_reenfocar,
                content=ft.Column(
                    [
                        ft.Container(
                            padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                            border_radius=8,
                            bgcolor=ft.Colors.with_opacity(0.70, "black"),
                            content=ft.Text(
                                "Enfoca el código (toca el recuadro para reenfocar)",
                                color="white",
                                size=14,
                                weight=ft.FontWeight.BOLD,
                            ),
                        ),
                        ft.Container(
                            width=340,
                            height=240,
                            margin=ft.Margin.symmetric(horizontal=16),
                            border=ft.Border.all(3, "#00e676"),
                            border_radius=14,
                        ),
                        btn_linterna,
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            )

            btn_cerrar_fullscreen = ft.Container(
                bottom=32,
                left=24,
                right=24,
                content=ft.Button(
                    content="✖ CANCELAR ESCANEO",
                    bgcolor="#c62828",
                    color="white",
                    height=50,
                    width=float("inf"),
                    on_click=lambda e: page.run_task(cerrar_camara_movil),
                ),
            )

            visor_camara_stack.controls = [
                ft.Container(content=cam, expand=True),
                guia_enfoque,
                btn_cerrar_fullscreen,
            ]
            overlay_camara.visible = True
            _estado_boton(True)

            try:
                camaras = await cam.get_available_cameras()
                if not camaras:
                    raise RuntimeError("Sin cámaras disponibles")
                trasera = next((c for c in camaras if c.lens_direction == fc.CameraLensDirection.BACK), camaras[0])
                await cam.initialize(
                    description=trasera,
                    resolution_preset=fc.ResolutionPreset.HIGH,
                    enable_audio=False,
                    image_format_group=fc.ImageFormatGroup.YUV420,
                )
                try:
                    await cam.set_focus_mode(fc.FocusMode.AUTO)
                    await cam.set_exposure_mode(fc.ExposureMode.AUTO)
                except Exception:
                    pass

                if not await cam.supports_image_streaming():
                    raise RuntimeError("Este equipo no permite leer fotogramas de la cámara")

                cam_estado["token"] += 1
                cam_estado["cam"] = cam
                cam_estado["activa"] = True
                await cam.start_image_stream()
                page.run_task(_temporizador_escaneo, cam_estado["token"], TIEMPO_MAX_ESCANEO)
            except Exception as ex:
                print(f"Error al abrir la cámara: {ex}")
                await cerrar_camara_movil("No se pudo iniciar la cámara. Ingresa el SG manualmente.")

        async def iniciar_escaneo(e):
            if es_movil:
                if overlay_camara.visible:
                    await cerrar_camara_movil()
                else:
                    await abrir_camara_movil()
                return
            if page.web:
                mostrar_alerta("En el navegador el escaneo con cámara no está disponible. Ingresa el SG manualmente.", es_error=True)
                return
            if cv2 is None or (zxingcpp is None and decodificar_code128 is None):
                mostrar_alerta("El escaneo con cámara no está disponible en este dispositivo. Ingresa el SG manualmente.", es_error=True, ms=3000)
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

        # =================================================================
        #  GESTIÓN DE PEDIDOS Y CONSULTAS
        # =================================================================
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
            try:
                page.update()
            except Exception:
                pass

        def eliminar_registro(pedido_id, sg_valor):
            if not sesion_activa():
                return
            db.eliminar_pedido(pedido_id, uid)
            actualizar_vista_diaria()
            lanzar_sincronizacion(eliminar_sg=sg_valor)

        def abrir_dialogo_editar(p_id, fecha_actual_reg, sg_actual, tipo_actual, skus_actual, arts_actual):
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

                    sg_anterior = str(sg_actual).strip()
                    if nuevo_sg != sg_anterior and db.verificar_sg_existente(nuevo_sg, uid):
                        mostrar_alerta(f"⚠️ El SG '{nuevo_sg}' ya existe en tus registros.", True)
                        return

                    nuevo_ingreso = calcular_monto(nuevo_tipo, nuevos_skus, nuevos_arts)
                    db.actualizar_pedido(
                        p_id, uid, nueva_fecha, nuevo_sg, nuevo_tipo, nuevos_skus, nuevos_arts, nuevo_ingreso
                    )

                    cerrar_dialogo()
                    actualizar_vista_diaria()
                    actualizar_badge_nube()
                    lanzar_sincronizacion(eliminar_sg=sg_anterior if nuevo_sg != sg_anterior else None)
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
                                    on_click=lambda e, pid=p_id, s=sg: eliminar_registro(pid, s)
                                ),
                            ], spacing=4)
                        ),
                    ])
                )

            if estado["vista"] == "consultas" and not estado["mostrar"]:
                lista_pedidos_container.controls.append(
                    ft.Text("Selecciona un filtro o rango y pulsa «CONSULTAR RANGO» o «VER PEDIDOS DEL DÍA».",
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
                msg_vacio = (
                    "No hay pedidos registrados para esta fecha."
                    if estado["vista"] == "inicio"
                    else "No hay pedidos registrados en este período."
                )
                lista_pedidos_container.controls.append(
                    ft.Text(msg_vacio, color="#666666")
                )

            if estado["vista"] == "inicio" or estado["mostrar"]:
                lbl_total_dia.value = fmt_moneda(total_dinero)
                lbl_conteo_dia.value = f"{len(registros)} pedido(s) registrado(s)"
            else:
                lbl_total_dia.value = fmt_moneda(0)
                lbl_conteo_dia.value = "0 pedido(s) registrado(s)"
            page.update()

        def actualizar_vista_diaria():
            if not sesion_activa():
                return
            if estado["vista"] == "consultas" and estado["rango"]:
                desde, hasta = estado["rango"]
                registros = db.obtener_pedidos_por_rango(desde, hasta, uid)
                lbl_titulo_total.value = "INGRESO TOTAL DEL RANGO"
                lbl_titulo_lista.value = f"Pedidos del {desde} al {hasta}"
                lbl_titulo_lista.visible = estado["mostrar"]
                estado["periodo_texto"] = f"Del {desde} al {hasta}"
            elif estado["vista"] == "consultas":
                fecha_sel = txt_fecha.value.strip()
                registros = db.obtener_pedidos_por_rango(fecha_sel, fecha_sel, uid)
                lbl_titulo_total.value = "INGRESO TOTAL DEL DÍA"
                lbl_titulo_lista.value = f"Pedidos del Día ({fecha_sel})"
                lbl_titulo_lista.visible = estado["mostrar"]
                estado["periodo_texto"] = f"Día {fecha_sel}"
            else:
                fecha_sel = txt_fecha.value.strip()
                registros = db.obtener_pedidos_por_rango(fecha_sel, fecha_sel, uid)
                lbl_titulo_total.value = "INGRESO TOTAL DEL DÍA"
                lbl_titulo_lista.value = f"Pedidos Tratados el Día ({fecha_sel})"
                lbl_titulo_lista.visible = True
                estado["periodo_texto"] = f"Día {fecha_sel}"
            estado["registros"] = registros if estado["mostrar"] else []
            renderizar_tabla(registros)

        def volver_a_dia(e=None):
            estado["rango"] = None
            estado["mostrar"] = True
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
        panel_tarifas = ft.Column(visible=False, spacing=10)
        btn_usuarios = ft.Button(content="👥 Usuarios", bgcolor="#5c6bc0", color="white", height=40,
                                 visible=es_admin, on_click=lambda e: alternar_panel_admin())
        btn_tarifas = ft.Button(content="⚙️ Gestión", bgcolor="#8e24aa", color="white", height=40,
                                visible=es_admin, on_click=lambda e: alternar_panel_tarifas())
        btn_consultas = ft.Button(content="🔍 Consultas", bgcolor="#00897b", color="white", height=40,
                                  on_click=lambda e: ir_a_consultas())

        def cambiar_estado_usuario(usuario_id, activar):
            u_obj = db.obtener_usuario(usuario_id)
            if db.cambiar_estado(uid, usuario_id, activar):
                if u_obj and cloud.id_token:
                    cloud.guardar_perfil_usuario(u_obj["rut"], u_obj["nombre"], u_obj["correo"], u_obj["rol"], activar)
                mostrar_alerta("Usuario activado." if activar else "Usuario desactivado.")
            else:
                mostrar_alerta("No se pudo cambiar el estado.", True)
            renderizar_usuarios()

        def rechazar_usuario(usuario_id):
            u_obj = db.obtener_usuario(usuario_id)
            if db.rechazar_usuario(uid, usuario_id):
                if u_obj and cloud.id_token:
                    cloud.eliminar_usuario_nube(u_obj["rut"])
                mostrar_alerta("Solicitud rechazada.")
            else:
                mostrar_alerta("Solo se pueden rechazar solicitudes sin pedidos.", True)
            renderizar_usuarios()

        def renderizar_usuarios():
            usuarios = db.listar_usuarios(uid)
            pendientes = sum(1 for u in usuarios if not u["activo"])
            btn_usuarios.content = f"👥 Usuarios ({pendientes})" if pendientes else "👥 Usuarios"

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
            try:
                page.update()
            except Exception:
                pass

        def alternar_panel_admin():
            if not es_admin or not sesion_activa():
                return
            panel_admin.visible = not panel_admin.visible
            if panel_admin.visible:
                panel_tarifas.visible = False
                renderizar_usuarios()
            page.update()

        def renderizar_tarifas():
            actuales = db.obtener_tarifas()
            detalle = {"Picking": "por SKU", "Driver": "por artículo", "Shopper": "por unidad"}
            campos, filas = {}, []
            for tipo in ("Picking", "Driver", "Shopper"):
                t = actuales[tipo]
                tf_base = ft.TextField(label=f"{tipo}: base por pedido ($)", value=f"{t['base']:g}",
                                       keyboard_type=ft.KeyboardType.NUMBER, expand=True)
                tf_unidad = ft.TextField(label=f"{tipo}: valor {detalle[tipo]} ($)", value=f"{t['unidad']:g}",
                                         keyboard_type=ft.KeyboardType.NUMBER, expand=True)
                campos[tipo] = (tf_base, tf_unidad)
                filas.append(ft.Row([tf_base, tf_unidad], spacing=10))

            def guardar_tarifas(e):
                if not es_admin or not sesion_activa():
                    return
                try:
                    nuevas = {
                        tipo: {"base": float((b.value or "").strip().replace(",", ".")),
                               "unidad": float((u.value or "").strip().replace(",", "."))}
                        for tipo, (b, u) in campos.items()
                    }
                except ValueError:
                    mostrar_alerta("Revisa que todos los montos sean números.", es_error=True)
                    return
                ok, mensaje = db.guardar_tarifas(uid, nuevas)
                if ok:
                    tarifas["vigentes"] = db.obtener_tarifas()
                    if cloud.id_token:
                        cloud.subir_tarifas(tarifas["vigentes"])
                    actualizar_vista_previa_monto()
                mostrar_alerta(mensaje, es_error=not ok)

            panel_tarifas.controls = [
                ft.Text("Tarifas de cálculo", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("Solo el administrador ve y cambia estos montos. Los pedidos ya guardados conservan el "
                        "ingreso con que se registraron; los pedidos nuevos y los que se editen usan las tarifas vigentes.",
                        size=13, color="#666666"),
                *filas,
                ft.Button(content="GUARDAR TARIFAS", bgcolor="#8e24aa", color="white", height=44,
                          on_click=guardar_tarifas),
                ft.Divider(height=10),
            ]
            page.update()

        def alternar_panel_tarifas():
            if not es_admin or not sesion_activa():
                return
            panel_tarifas.visible = not panel_tarifas.visible
            if panel_tarifas.visible:
                panel_admin.visible = False
                renderizar_tarifas()
            page.update()

        def guardar_pedido(e):
            if not sesion_activa():
                return
            fecha_val = txt_fecha.value.strip()
            if re.search(r"[|;	]", txt_sg.value or ""):
                procesar_texto_escaneado(txt_sg.value)
            sg_val = txt_sg.value.strip()
            skus, arts = obtener_valores_numericos()

            if not fecha_val or not sg_val:
                mostrar_alerta("Por favor ingresa la Fecha y el número de SG.", es_error=True)
                return

            if db.verificar_sg_existente(sg_val, uid):
                mostrar_alerta(f"⚠️ El SG '{sg_val}' ya existe en la base de datos.", es_error=True)
                senal(False)
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
            db.insertar_pedido(fecha_val, sg_val, rg_tipo.value, skus, arts, ingreso, uid, sincronizado=0)

            txt_sg.value = ""
            txt_skus.value = ""
            txt_articulos.value = ""
            actualizar_vista_previa_monto()
            estado["mostrar"] = True
            actualizar_vista_diaria()
            actualizar_badge_nube()
            lanzar_sincronizacion()

            mostrar_alerta("Pedido registrado correctamente.")

        def ir_a_consultas():
            if not sesion_activa():
                return
            panel_admin.visible = False
            panel_tarifas.visible = False
            estado["vista"] = "consultas"
            estado["rango"] = None
            estado["mostrar"] = False
            seccion_registro.visible = False
            seccion_consultas.visible = True
            actualizar_vista_diaria()

        def ir_a_menu():
            if not sesion_activa():
                return
            estado["vista"] = "inicio"
            estado["rango"] = None
            estado["mostrar"] = True
            seccion_consultas.visible = False
            seccion_registro.visible = True
            actualizar_vista_diaria()

        def exportar_pdf_consulta(e=None):
            if not sesion_activa():
                return
            if not estado["mostrar"] or not estado["registros"]:
                mostrar_alerta("Primero realiza una consulta con pedidos para generar el PDF.", es_error=True, ms=3000)
                return
            try:
                ruta_pdf = generar_pdf_consulta(
                    estado["registros"],
                    usuario,
                    estado["periodo_texto"],
                    tarifas["vigentes"],
                )
                if ruta_pdf:
                    mostrar_alerta(f"PDF guardado en: {ruta_pdf}", es_error=False, ms=4500)
                    if platform.system() == "Windows":
                        try:
                            os.startfile(ruta_pdf)
                        except Exception:
                            pass
                    else:
                        try:
                            page.launch_url(f"file://{ruta_pdf}")
                        except Exception:
                            pass
            except Exception as ex:
                mostrar_alerta(f"No se pudo generar el PDF: {ex}", es_error=True, ms=4000)

        encabezado = ft.Row(
            [
                ft.Text(f"👤 {usuario['nombre']}" + ("  (Administrador)" if es_admin else ""),
                        size=16, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        btn_sync,
                        btn_usuarios,
                        btn_tarifas,
                        btn_consultas,
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

        seccion_registro = ft.Column(
            [
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
            ],
            visible=True,
            spacing=10
        )

        seccion_consultas = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Consultar histórico", size=18, weight=ft.FontWeight.BOLD),
                        ft.Button(
                            content="⬅️ Ir a Menú",
                            bgcolor="#1a237e",
                            color="white",
                            height=40,
                            on_click=lambda e: ir_a_menu()
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True
                ),
                ft.Text("«Ver pedidos del día» usa la fecha del campo Fecha principal; para otro período elige un rango.",
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
                        boton_rango("📄 GENERAR PDF", "#e65100", exportar_pdf_consulta),
                        boton_rango("🧹 BORRAR CONSULTA", "#c62828", borrar_consulta),
                    ],
                    wrap=True,
                    spacing=10
                ),
            ],
            visible=False,
            spacing=10
        )

        page.add(
            encabezado,
            panel_admin,
            panel_tarifas,
            tarjeta_resumen,
            ft.Divider(height=10, color="transparent"),
            seccion_registro,
            seccion_consultas,
            ft.Divider(height=16),
            lbl_titulo_lista,
            lista_pedidos_container
        )

        actualizar_vista_diaria()
        actualizar_badge_nube()
        lanzar_sincronizacion(descargar=True)
        if es_admin:
            renderizar_usuarios()
        ajustar_ancho()

    sesion_guardada = db.obtener_sesion_local()
    if sesion_guardada and sesion_guardada.get("rut") and sesion_guardada.get("clave"):
        rut_s = normalizar_rut(sesion_guardada["rut"])
        clave_s = str(sesion_guardada["clave"]).strip()
        res_s, dato_s = db.autenticar(rut_s, clave_s)
        if res_s == "ok":
            iniciar_app(dato_s, clave_s)
        else:
            db.borrar_sesion_local()
            mostrar_login()
    else:
        mostrar_login()


if __name__ == "__main__":
    ft.run(main)
