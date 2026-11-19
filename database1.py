import sqlite3

class DatabaseManager:
    def __init__(self, db_name="picking_ingresos.db"):
        self.db_name = db_name
        self.crear_tabla()

    def _conectar(self):
        return sqlite3.connect(self.db_name, check_same_thread=False)

    def crear_tabla(self):
        with self._conectar() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT NOT NULL,
                    sg TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    skus INTEGER NOT NULL,
                    articulos INTEGER NOT NULL,
                    ingreso REAL NOT NULL
                )
            """)

    def insertar_pedido(self, fecha: str, sg: str, tipo: str, skus: int, articulos: int, ingreso: float):
        with self._conectar() as conn:
            conn.execute(
                "INSERT INTO pedidos (fecha, sg, tipo, skus, articulos, ingreso) VALUES (?, ?, ?, ?, ?, ?)",
                (fecha, sg, tipo, skus, articulos, ingreso)
            )

    def obtener_pedidos_por_fecha(self, fecha: str):
        with self._conectar() as conn:
            cursor = conn.execute(
                "SELECT id, sg, tipo, skus, articulos, ingreso FROM pedidos WHERE fecha = ? ORDER BY id DESC",
                (fecha,)
            )
            return cursor.fetchall()

    def eliminar_pedido(self, pedido_id: int):
        with self._conectar() as conn:
            conn.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))