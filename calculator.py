def calcular_ingreso(tipo_pedido: str, skus: int, articulos: int) -> float:
    """
    Calcula el ingreso monetario según la actividad:
    - Picking: Base $1300 + ($80 * cantidad de SKUs)
    - Driver:  Base $1850 + ($38 * cantidad de artículos/unidades)
    """
    tipo = tipo_pedido.strip().lower()
    if tipo == "picking":
        return 1300.0 + (80.0 * skus)
    elif tipo == "driver":
        return 1850.0 + (38.0 * articulos)
    return 0.0