import sqlite3
from seguridad import hash_clave

class DatabaseManager:
    def __init__(self, db_name="picking_tracker.db"):
        self.db_name = db_name
        self.crear_tablas()
        self.forzar_admin_activo()  # <--- Asegura que el admin siempre esté activo

    def conectar(self):
        return sqlite3.connect(self.db_name)

    def crear_tablas(self):
        with self.conectar() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut TEXT NOT NULL UNIQUE,
                    nombre TEXT NOT NULL,
                    correo TEXT,
                    clave_hash TEXT NOT NULL,
                    rol TEXT NOT NULL DEFAULT 'usuario',
                    activo INTEGER NOT NULL DEFAULT 0,
                    creado TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha TEXT,
                    sg TEXT,
                    tipo TEXT,
                    skus INTEGER,
                    articulos INTEGER,
                    ingreso REAL,
                    usuario_id INTEGER
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intentos_login (
                    rut TEXT PRIMARY KEY,
                    fallos INTEGER NOT NULL DEFAULT 0,
                    bloqueado_hasta TEXT
                )
            """)
            conn.commit()

    def forzar_admin_activo(self):
        """Fuerza que el administrador principal (285447097) esté activo y con clave correcta"""
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE rut = '285447097'")
            row = cursor.fetchone()
            clave_admin_hash = hash_clave("385621")
            
            if row:
                conn.execute("""
                    UPDATE usuarios 
                    SET activo = 1, rol = 'admin', clave_hash = ? 
                    WHERE rut = '285447097'
                """, (clave_admin_hash,))
            else:
                conn.execute("""
                    INSERT INTO usuarios (rut, nombre, correo, clave_hash, rol, activo, creado)
                    VALUES ('285447097', 'Franklin Morillo', 'franklinmorillo@gmail.com', ?, 'admin', 1, datetime('now'))
                """, (clave_admin_hash,))
            conn.commit()

    def autenticar(self, rut, clave):
        rut_norm = rut.strip().upper()
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, rut, nombre, correo, rol, activo, clave_hash FROM usuarios WHERE rut = ?", (rut_norm,))
            user = cursor.fetchone()
            
            if not user:
                return "error", None
            
            uid, u_rut, u_nombre, u_correo, u_rol, u_activo, u_hash = user
            
            if u_hash != hash_clave(clave):
                return "error", None
                
            if not u_activo:
                return "inactivo", None
                
            return "ok", {"id": uid, "rut": u_rut, "nombre": u_nombre, "correo": u_correo, "rol": u_rol}

    def verificar_sg_existente(self, sg, usuario_id):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE sg = ? AND usuario_id = ?", (sg, usuario_id))
            return cursor.fetchone()[0] > 0

    def insertar_pedido(self, fecha, sg, tipo, skus, articulos, ingreso, usuario_id):
        with self.conectar() as conn:
            conn.execute("""
                INSERT INTO pedidos (fecha, sg, tipo, skus, articulos, ingreso, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (fecha, sg, tipo, skus, articulos, ingreso, usuario_id))
            conn.commit()

    def actualizar_pedido(self, pedido_id, usuario_id, fecha, sg, tipo, skus, articulos, ingreso):
        """Actualiza un pedido existente asegurando que pertenezca al usuario"""
        with self.conectar() as conn:
            conn.execute("""
                UPDATE pedidos 
                SET fecha = ?, sg = ?, tipo = ?, skus = ?, articulos = ?, ingreso = ?
                WHERE id = ? AND usuario_id = ?
            """, (fecha, sg, tipo, skus, articulos, ingreso, pedido_id, usuario_id))
            conn.commit()

    def obtener_pedidos_por_fecha(self, fecha, usuario_id):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, sg, tipo, skus, articulos, ingreso 
                FROM pedidos WHERE fecha = ? AND usuario_id = ? ORDER BY id DESC
            """, (fecha, usuario_id))
            return cursor.fetchall()

    def obtener_pedidos_por_rango(self, desde, hasta, usuario_id):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, fecha, sg, tipo, skus, articulos, ingreso 
                FROM pedidos WHERE fecha BETWEEN ? AND ? AND usuario_id = ? ORDER BY fecha DESC, id DESC
            """, (desde, hasta, usuario_id))
            return cursor.fetchall()

    def eliminar_pedido(self, pedido_id, usuario_id):
        with self.conectar() as conn:
            conn.execute("DELETE FROM pedidos WHERE id = ? AND usuario_id = ?", (pedido_id, usuario_id))
            conn.commit()

    def listar_usuarios(self, admin_id):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rol FROM usuarios WHERE id = ?", (admin_id,))
            row = cursor.fetchone()
            if not row or row[0] != 'admin':
                return []
            cursor.execute("SELECT id, rut, nombre, correo, rol, activo FROM usuarios ORDER BY id ASC")
            return [{"id": r[0], "rut": r[1], "nombre": r[2], "correo": r[3], "rol": r[4], "activo": r[5]} for r in cursor.fetchall()]

    def cambiar_estado(self, admin_id, target_id, activar):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rol FROM usuarios WHERE id = ?", (admin_id,))
            row = cursor.fetchone()
            if not row or row[0] != 'admin':
                return False
            conn.execute("UPDATE usuarios SET activo = ? WHERE id = ?", (1 if activar else 0, target_id))
            conn.commit()
            return True

    def rechazar_usuario(self, admin_id, target_id):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT rol FROM usuarios WHERE id = ?", (admin_id,))
            row = cursor.fetchone()
            if not row or row[0] != 'admin':
                return False
            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE usuario_id = ?", (target_id,))
            if cursor.fetchone()[0] > 0:
                return False
            conn.execute("DELETE FROM usuarios WHERE id = ? AND activo = 0", (target_id,))
            conn.commit()
            return True

    def obtener_usuario(self, usuario_id):
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, rut, nombre, correo, rol, activo FROM usuarios WHERE id = ?", (usuario_id,))
            r = cursor.fetchone()
            if not r:
                return None
            return {"id": r[0], "rut": r[1], "nombre": r[2], "correo": r[3], "rol": r[4], "activo": r[5]}