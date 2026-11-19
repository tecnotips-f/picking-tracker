"""Cálculo de ingresos por pedido.

Las tarifas vigentes se guardan en la base de datos y solo el administrador puede
verlas y cambiarlas desde la app. Los valores de abajo son los iniciales / de respaldo.
"""

TARIFAS_POR_DEFECTO = {
    # base = monto fijo por pedido; unidad = valor por SKU (Picking) o por artículo/unidad (Driver, Shopper)
    "Picking": {"base": 1300.0, "unidad": 80.0},
    "Driver": {"base": 1850.0, "unidad": 38.0},
    "Shopper": {"base": 3600.0, "unidad": 38.0},
}


def calcular_ingreso(tipo_pedido: str, skus: int, articulos: int, tarifas: dict | None = None) -> float:
    """
    Ingreso según la modalidad:
    - Picking: base + (valor por SKU * cantidad de SKUs)
    - Driver:  base + (valor por artículo * cantidad de artículos)
    - Shopper: base + (valor por unidad * cantidad de artículos/unidades)
    `tarifas` es el diccionario vigente (ver DatabaseManager.obtener_tarifas); si no se pasa,
    se usan las tarifas por defecto.
    """
    tarifas = tarifas or TARIFAS_POR_DEFECTO
    tipo = (tipo_pedido or "").strip().capitalize()
    t = tarifas.get(tipo)
    if not t:
        return 0.0
    cantidad = skus if tipo == "Picking" else articulos
    return float(t["base"]) + float(t["unidad"]) * cantidad
