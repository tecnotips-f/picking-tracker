import os
import platform
from datetime import datetime
from pathlib import Path
from fpdf import FPDF


def _fmt_moneda(valor):
    return f"$ {float(valor):,.0f}".replace(",", ".")


def _obtener_carpeta_salida():
    """Determina una carpeta accesible para guardar el PDF tanto en Windows como en Android."""
    if platform.system() == "Windows":
        descargas = Path.home() / "Downloads"
        if descargas.is_dir():
            return descargas
        return Path.cwd()

    # Android / Linux / macOS
    rutas_candidatas = [
        Path("/storage/emulated/0/Download"),
        Path.home() / "Downloads",
    ]
    for ruta in rutas_candidatas:
        try:
            if ruta.is_dir() and os.access(ruta, os.W_OK):
                return ruta
        except Exception:
            pass

    flet_dir = os.environ.get("FLET_APP_STORAGE_DATA") or os.environ.get("FLET_APP_STORAGE_TEMP")
    if flet_dir:
        p = Path(flet_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    return Path.cwd()


def _deducir_tarifas_fila(tipo, skus, arts, ingreso, tarifas_vigentes):
    """Calcula la tarifa por pedido y la tarifa unitaria aplicada (SKU o Cantidad) para cada fila."""
    tipo_cap = str(tipo).strip().capitalize()
    if tipo_cap not in tarifas_vigentes:
        tipo_cap = "Picking"

    t_cfg = tarifas_vigentes[tipo_cap]
    base_vigente = float(t_cfg.get("base", 0.0))
    unidad_vigente = float(t_cfg.get("unidad", 0.0))

    skus_int = int(skus or 0)
    arts_int = int(arts or 0)
    ingreso_val = float(ingreso or 0.0)

    if tipo_cap == "Picking":
        cant_aplicable = skus_int
        etiqueta_cant = f"{skus_int} SKU x {_fmt_moneda(unidad_vigente)}"
    else:
        cant_aplicable = arts_int
        etiqueta_cant = f"{arts_int} Cant. x {_fmt_moneda(unidad_vigente)}"

    # Verificar si el ingreso guardado coincide exactamente con la tarifa vigente;
    # si fue guardado con una tarifa histórica distinta, ajustar la base proporcionalmente
    # para que Base + (Cantidad * Tarifa Unitaria) == Total registrado.
    calculado_vigente = base_vigente + (cant_aplicable * unidad_vigente)
    if abs(calculado_vigente - ingreso_val) <= 1.0:
        base_aplicada = base_vigente
    else:
        base_aplicada = max(0.0, ingreso_val - (cant_aplicable * unidad_vigente))

    return base_aplicada, etiqueta_cant, ingreso_val


class _ReportePDF(FPDF):
    def __init__(self, titulo_periodo, usuario):
        super().__init__(orientation="L", unit="mm", format="A4")
        self.titulo_periodo = titulo_periodo
        self.usuario = usuario

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(26, 35, 126)  # #1a237e
        self.cell(0, 9, "Gestión de Pedidos", new_x="LMARGIN", new_y="NEXT", align="L")

        self.set_font("Helvetica", "", 10)
        self.set_text_color(60, 60, 60)
        nombre_u = str(self.usuario.get("nombre", ""))
        rut_u = str(self.usuario.get("rut", ""))
        emitido = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.cell(
            0,
            6,
            f"Operador: {nombre_u} ({rut_u})   |   Período: {self.titulo_periodo}   |   Emitido: {emitido}",
            new_x="LMARGIN",
            new_y="NEXT",
            align="L",
        )
        self.ln(3)

        # Encabezados de tabla (ancho útil A4 horizontal con márgenes 12mm = 273mm)
        self.set_fill_color(26, 35, 126)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 9)

        # Columnas: N, Fecha, SG, Tipo, SKUs, Cant., Tarifa Pedido, Tarifa SKU / Cant., Total
        anchos = [14, 24, 38, 25, 18, 20, 34, 62, 38]
        titulos = [
            "N",
            "Fecha",
            "SG",
            "Tipo",
            "SKUs",
            "Cant.",
            "Tarifa Pedido",
            "Tarifa SKU / Cant.",
            "Total",
        ]
        alineaciones = ["C", "C", "L", "C", "R", "R", "R", "R", "R"]

        for w, titulo, al in zip(anchos, titulos, alineaciones):
            self.cell(w, 8, titulo, border=1, align=al, fill=True)
        self.ln()

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Control de Picking - Página {self.page_no()}/{{nb}}", align="C")


def generar_pdf_consulta(registros, usuario, titulo_periodo, tarifas_vigentes):
    """
    Genera el PDF de la consulta actual.
    `registros` viene ordenado desde el más reciente al más antiguo:
    [(id, fecha, sg, tipo, skus, articulos, ingreso), ...]
    El consecutivo N va desde el último transcrito (len(registros)) hasta el primero (1).
    """
    if not registros:
        return None

    pdf = _ReportePDF(titulo_periodo=titulo_periodo, usuario=usuario)
    pdf.set_margins(12, 12, 12)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    pdf.add_page()

    anchos = [14, 24, 38, 25, 18, 20, 34, 62, 38]
    total_pedidos = len(registros)
    suma_skus = 0
    suma_cantidades = 0
    suma_total = 0.0

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(20, 20, 20)

    for idx, fila in enumerate(registros):
        _, fecha, sg, tipo, skus, arts, ingreso = fila
        consecutivo = total_pedidos - idx  # Desde el último transcrito hacia el primero

        skus_int = int(skus or 0)
        arts_int = int(arts or 0)
        base_ap, detalle_var, total_fila = _deducir_tarifas_fila(
            tipo, skus_int, arts_int, ingreso, tarifas_vigentes
        )

        suma_skus += skus_int
        suma_cantidades += arts_int
        suma_total += total_fila

        fill = idx % 2 == 1
        if fill:
            pdf.set_fill_color(240, 242, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        valores = [
            str(consecutivo),
            str(fecha),
            str(sg),
            str(tipo).capitalize(),
            str(skus_int),
            str(arts_int),
            _fmt_moneda(base_ap),
            detalle_var,
            _fmt_moneda(total_fila),
        ]
        alineaciones = ["C", "C", "L", "C", "R", "R", "R", "R", "R"]

        for w, val, al in zip(anchos, valores, alineaciones):
            pdf.cell(w, 7, val, border=1, align=al, fill=fill)
        pdf.ln()

    # Última fila: Cantidad de pedidos, sumatoria de SKUs, sumatoria de cantidades y sumatoria de totales finales
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(224, 231, 255)
    pdf.set_text_color(26, 35, 126)

    # Celdas combinadas para etiquetar la cantidad de pedidos y alinear cada sumatoria bajo su columna
    ancho_etiqueta_pedidos = anchos[0] + anchos[1] + anchos[2] + anchos[3]  # 14 + 24 + 38 + 25 = 101 mm
    pdf.cell(ancho_etiqueta_pedidos, 8, f"TOTAL PEDIDOS: {total_pedidos}", border=1, align="L", fill=True)
    pdf.cell(anchos[4], 8, str(suma_skus), border=1, align="R", fill=True)
    pdf.cell(anchos[5], 8, str(suma_cantidades), border=1, align="R", fill=True)
    pdf.cell(anchos[6] + anchos[7], 8, "TOTAL GENERAL:", border=1, align="R", fill=True)
    pdf.cell(anchos[8], 8, _fmt_moneda(suma_total), border=1, align="R", fill=True)
    pdf.ln()

    carpeta = _obtener_carpeta_salida()
    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    nombre_archivo = f"Gestion_Pedidos_{usuario.get('rut', 'usuario')}_{marca_tiempo}.pdf"
    ruta_salida = carpeta / nombre_archivo
    pdf.output(str(ruta_salida))
    return str(ruta_salida)
