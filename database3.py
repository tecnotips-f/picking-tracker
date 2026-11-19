import sqlite3

class DatabaseManager:
    def __init__(self, db_name="picking_tracker.db"):
        self.db_name = db_name
        self.crear_tabla()

    def conectar(self):
        return sqlite3.connect(self.db_name)

    def crear_tabla(self):
        with self.conectar() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT,
                    sg TEXT,
                    tipo TEXT,
                    skus INTEGER,
                    articulos INTEGER,
                    ingreso REAL
                )
            """)
            conn.commit()

    def verificar_sg_existente(self, sg):
        """Retorna True si el SG ya se encuentra registrado en la base de datos"""
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE sg = ?", (sg,))
            count = cursor.fetchone()[0]
            return count > 0

    def insertar_pedido(self, fecha, sg, tipo, skus, articulos, ingreso):
        with self.conectar() as conn:
            conn.execute("""
                INSERT INTO pedidos (fecha, sg, tipo, skus, articulos, ingreso)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fecha, sg, tipo, skus, articulos, ingreso))
            conn.commit()

    def obtener_pedidos_por_fecha(self, fecha):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, sg, tipo, skus, articulos, ingreso 
                FROM pedidos WHERE fecha = ? ORDER BY id DESC
            """, (fecha,))
            return cursor.fetchall()

    def obtener_pedidos_por_rango(self, fecha_desde, fecha_hasta):
        """Pedidos entre dos fechas (inclusive, formato AAAA-MM-DD), más recientes primero"""
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, fecha, sg, tipo, skus, articulos, ingreso
                FROM pedidos WHERE fecha BETWEEN ? AND ?
                ORDER BY fecha DESC, id DESC
            """, (fecha_desde, fecha_hasta))
            return cursor.fetchall()

    def eliminar_pedido(self, pedido_id):
        with self.conectar() as conn:
            conn.execute("DELETE FROM pedidos WHERE id = ?", (pedido_id,))
            conn.commit()
