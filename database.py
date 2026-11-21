import os
import sqlite3
import hmac
from datetime import datetime, timedelta

from seguridad import (normalizar_rut, validar_rut, validar_id_boosmap, hash_clave,
                       carpetas_de_datos, carpeta_destino)
from calculator import TARIFAS_POR_DEFECTO
import math

MAX_INTENTOS = 5          # intentos fallidos antes de bloquear
MINUTOS_BLOQUEO = 15      # duración del bloqueo


NOMBRE_BD = "picking_tracker.db"


def _contenido(ruta):
    """Cantidad de filas (usuarios + pedidos) de una base; sirve para elegir la que tiene datos."""
    try:
        conn = sqlite3.connect(str(ruta))
        try:
            total = 0
            for tabla in ("usuarios", "pedidos"):
                try:
                    total += conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
                except sqlite3.Error:
                    pass
            return total
        finally:
            conn.close()
    except sqlite3.Error:
        return -1


def elegir_base(nombre=NOMBRE_BD):
    """Usa la base que ya existe (la de `flet run`, la de la carpeta del código o la de Flet en el móvil).
    Si hay varias, la que tenga más datos; si no hay ninguna, se crea en la carpeta de datos de Flet
    (o junto al código cuando se ejecuta desde la consola)."""
    existentes = [c / nombre for c in carpetas_de_datos() if (c / nombre).is_file()]
    if not existentes:
        destino = carpeta_destino()
        destino.mkdir(parents=True, exist_ok=True)
        return str(destino / nombre)
    return str(max(existentes, key=_contenido))   # en empate gana la de mayor prioridad


class DatabaseManager:
    def __init__(self, db_name=None):
        if db_name is None:
            db_name = elegir_base()
        self.db_name = db_name
        self.crear_tabla()
        self._admin_desde_entorno()

    def conectar(self):
        return sqlite3.connect(self.db_name, timeout=10)

    # ------------------------------------------------------------------ esquema
    def crear_tabla(self):
        with self.conectar() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rut TEXT NOT NULL UNIQUE,
                    nombre TEXT NOT NULL,
                    correo TEXT,
                    clave_hash TEXT NOT NULL UNIQUE,
                    rol TEXT NOT NULL DEFAULT 'usuario',
                    activo INTEGER NOT NULL DEFAULT 0,
                    creado TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS intentos_login (
                    rut TEXT PRIMARY KEY,
                    fallos INTEGER NOT NULL DEFAULT 0,
                    bloqueado_hasta TEXT
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
                    usuario_id INTEGER,
                    sincronizado INTEGER NOT NULL DEFAULT 0
                )
            """)
            # Migración: bases anteriores no tienen usuario_id ni sincronizado
            columnas = [fila[1] for fila in conn.execute("PRAGMA table_info(pedidos)")]
            if "usuario_id" not in columnas:
                conn.execute("ALTER TABLE pedidos ADD COLUMN usuario_id INTEGER")
            if "sincronizado" not in columnas:
                conn.execute("ALTER TABLE pedidos ADD COLUMN sincronizado INTEGER NOT NULL DEFAULT 0")
            try:   # el ID Boosmap (clave) no puede repetirse; las bases antiguas no lo exigían
                conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_clave ON usuarios(clave_hash)")
            except sqlite3.IntegrityError:
                pass
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_usuario_fecha ON pedidos(usuario_id, fecha)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_usuario_sg ON pedidos(usuario_id, sg)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sesion_local (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    rut TEXT NOT NULL,
                    clave TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tarifas (
                    tipo TEXT PRIMARY KEY,
                    base REAL NOT NULL,
                    unidad REAL NOT NULL
                )
            """)
            for tipo, t in TARIFAS_POR_DEFECTO.items():   # solo siembra las que faltan; no pisa lo editado
                conn.execute("INSERT OR IGNORE INTO tarifas (tipo, base, unidad) VALUES (?, ?, ?)",
                             (tipo, t["base"], t["unidad"]))
            conn.commit()

    def _admin_desde_entorno(self):
        """Opcional: si existen PICKING_ADMIN_RUT y PICKING_ADMIN_CLAVE (variables de entorno del servidor),
        asegura que ese administrador exista y esté activo. Sustituye a las claves escritas en el código."""
        rut = os.environ.get("PICKING_ADMIN_RUT")
        clave = os.environ.get("PICKING_ADMIN_CLAVE")
        if rut and clave:
            self.crear_admin(rut, os.environ.get("PICKING_ADMIN_NOMBRE", "Administrador"),
                             os.environ.get("PICKING_ADMIN_CORREO", ""), clave)

    # ------------------------------------------------------------------ usuarios
    @staticmethod
    def _usuario(fila):
        if not fila:
            return None
        return {"id": fila[0], "rut": fila[1], "nombre": fila[2], "correo": fila[3],
                "rol": fila[4], "activo": bool(fila[5])}

    def obtener_usuario(self, usuario_id):
        with self.conectar() as conn:
            fila = conn.execute(
                "SELECT id, rut, nombre, correo, rol, activo FROM usuarios WHERE id = ?", (usuario_id,)
            ).fetchone()
            return self._usuario(fila)

    def obtener_usuario_por_rut(self, rut):
        rut = normalizar_rut(rut)
        with self.conectar() as conn:
            fila = conn.execute(
                "SELECT id, rut, nombre, correo, rol, activo FROM usuarios WHERE rut = ?", (rut,)
            ).fetchone()
            return self._usuario(fila)

    def registrar_usuario(self, rut, nombre, correo, id_boosmap):
        """Crea una cuenta INACTIVA (pendiente). El administrador debe activarla."""
        rut = normalizar_rut(rut)
        nombre = (nombre or "").strip()
        correo = (correo or "").strip() or None
        if not validar_rut(rut):
            return False, "RUT inválido."
        if not validar_id_boosmap(id_boosmap):
            return False, "El ID Boosmap debe tener exactamente 6 dígitos."
        if len(nombre) < 3:
            return False, "Ingresa tu nombre."
        try:
            with self.conectar() as conn:
                conn.execute(
                    "INSERT INTO usuarios (rut, nombre, correo, clave_hash, rol, activo, creado) "
                    "VALUES (?, ?, ?, ?, 'usuario', 0, ?)",
                    (rut, nombre, correo, hash_clave(id_boosmap), datetime.now().isoformat(timespec="seconds"))
                )
                conn.commit()
        except sqlite3.IntegrityError:
            return False, "No fue posible registrar: el RUT o el ID ya están en uso. Contacta al administrador."
        return True, "Solicitud enviada. Tu cuenta quedará disponible cuando el administrador la active."

    def crear_admin(self, rut, nombre, correo, clave):
        """Crea (o promueve) al administrador y le asigna los pedidos antiguos sin usuario."""
        rut = normalizar_rut(rut)
        if not validar_rut(rut):
            return False, "RUT inválido."
        correo = (correo or "").strip() or None
        ahora = datetime.now().isoformat(timespec="seconds")
        try:
            with self.conectar() as conn:
                try:
                    cur = conn.execute(
                        "INSERT INTO usuarios (rut, nombre, correo, clave_hash, rol, activo, creado) "
                        "VALUES (?, ?, ?, ?, 'admin', 1, ?)",
                        (rut, nombre, correo, hash_clave(clave), ahora)
                    )
                    admin_id = cur.lastrowid
                except sqlite3.IntegrityError:
                    conn.execute(
                        "UPDATE usuarios SET nombre=?, correo=?, clave_hash=?, rol='admin', activo=1 WHERE rut=?",
                        (nombre, correo, hash_clave(clave), rut)
                    )
                    admin_id = conn.execute("SELECT id FROM usuarios WHERE rut=?", (rut,)).fetchone()[0]
                huerfanos = conn.execute(
                    "UPDATE pedidos SET usuario_id = ? WHERE usuario_id IS NULL", (admin_id,)
                ).rowcount
                conn.commit()
        except sqlite3.IntegrityError:
            return False, "Esa clave ya la usa otro usuario. Elige una distinta."
        return True, f"Administrador listo. Pedidos antiguos asignados: {huerfanos}."

    def sincronizar_usuario_nube(self, rut, nombre, correo, clave_plana=None, rol="usuario", activo=False):
        """Crea o actualiza en SQLite local un usuario recibido desde Firebase."""
        rut = normalizar_rut(rut)
        if not validar_rut(rut):
            return None
        correo = (correo or "").strip() or None
        activo_int = 1 if activo else 0
        with self.conectar() as conn:
            fila = conn.execute("SELECT id FROM usuarios WHERE rut = ?", (rut,)).fetchone()
            if fila:
                if clave_plana:
                    conn.execute(
                        "UPDATE usuarios SET nombre=?, correo=?, clave_hash=?, rol=?, activo=? WHERE rut=?",
                        (nombre, correo, hash_clave(clave_plana), rol, activo_int, rut)
                    )
                else:
                    conn.execute(
                        "UPDATE usuarios SET nombre=?, correo=?, rol=?, activo=? WHERE rut=?",
                        (nombre, correo, rol, activo_int, rut)
                    )
                conn.commit()
            else:
                clave_para_hash = clave_plana if clave_plana else f"pendiente_{rut}_{datetime.now().timestamp()}"
                conn.execute(
                    "INSERT INTO usuarios (rut, nombre, correo, clave_hash, rol, activo, creado) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (rut, nombre, correo, hash_clave(clave_para_hash), rol, activo_int,
                     datetime.now().isoformat(timespec="seconds"))
                )
                conn.commit()
        return self.obtener_usuario_por_rut(rut)

    def autenticar(self, rut, clave):
        """Devuelve (estado, dato): 'ok' + usuario | 'credenciales' | 'inactivo' | 'bloqueado' + minutos."""
        rut = normalizar_rut(rut)
        if not validar_rut(rut) or not clave:
            return "credenciales", None
        ahora = datetime.now()
        with self.conectar() as conn:
            intento = conn.execute(
                "SELECT fallos, bloqueado_hasta FROM intentos_login WHERE rut = ?", (rut,)
            ).fetchone()
            if intento and intento[1]:
                hasta = datetime.fromisoformat(intento[1])
                if hasta > ahora:
                    return "bloqueado", int((hasta - ahora).total_seconds() // 60) + 1

            fila = conn.execute(
                "SELECT id, rut, nombre, correo, rol, activo, clave_hash FROM usuarios WHERE rut = ?", (rut,)
            ).fetchone()
            hash_ingresado = hash_clave(clave)   # siempre se calcula (tiempo parejo exista o no el RUT)
            correcto = fila is not None and hmac.compare_digest(fila[6], hash_ingresado)

            if not correcto:
                fallos = (intento[0] if intento else 0) + 1
                bloqueado = None
                if fallos >= MAX_INTENTOS:
                    bloqueado = (ahora + timedelta(minutes=MINUTOS_BLOQUEO)).isoformat()
                    fallos = 0
                conn.execute(
                    "INSERT INTO intentos_login (rut, fallos, bloqueado_hasta) VALUES (?, ?, ?) "
                    "ON CONFLICT(rut) DO UPDATE SET fallos = excluded.fallos, bloqueado_hasta = excluded.bloqueado_hasta",
                    (rut, fallos, bloqueado)
                )
                conn.commit()
                return "credenciales", None

            conn.execute("DELETE FROM intentos_login WHERE rut = ?", (rut,))
            conn.commit()
            if not fila[5]:
                return "inactivo", None
            return "ok", self._usuario(fila[:6])

    # ---------------------------------------------------- administración de usuarios
    def _es_admin_activo(self, conn, usuario_id):
        return conn.execute(
            "SELECT 1 FROM usuarios WHERE id = ? AND rol = 'admin' AND activo = 1", (usuario_id,)
        ).fetchone() is not None

    def listar_usuarios(self, solicitante_id):
        with self.conectar() as conn:
            if not self._es_admin_activo(conn, solicitante_id):
                return []
            filas = conn.execute(
                "SELECT id, rut, nombre, correo, rol, activo FROM usuarios ORDER BY activo ASC, creado DESC"
            ).fetchall()
            return [self._usuario(f) for f in filas]

    def cambiar_estado(self, solicitante_id, usuario_id, activo):
        """Activa/desactiva a un usuario (los administradores no se pueden desactivar desde la app)."""
        with self.conectar() as conn:
            if not self._es_admin_activo(conn, solicitante_id):
                return False
            cur = conn.execute(
                "UPDATE usuarios SET activo = ? WHERE id = ? AND rol != 'admin'",
                (1 if activo else 0, usuario_id)
            )
            conn.commit()
            return cur.rowcount > 0

    def rechazar_usuario(self, solicitante_id, usuario_id):
        """Elimina una solicitud pendiente (inactiva y sin pedidos). Libera el RUT y el ID."""
        with self.conectar() as conn:
            if not self._es_admin_activo(conn, solicitante_id):
                return False
            cur = conn.execute(
                "DELETE FROM usuarios WHERE id = ? AND activo = 0 AND rol != 'admin' "
                "AND NOT EXISTS (SELECT 1 FROM pedidos p WHERE p.usuario_id = usuarios.id)",
                (usuario_id,)
            )
            conn.commit()
            return cur.rowcount > 0

    # ------------------------------------------------------------------ tarifas
    def obtener_tarifas(self):
        """Tarifas vigentes: {'Picking': {'base': x, 'unidad': y}, ...}"""
        tarifas = {t: dict(v) for t, v in TARIFAS_POR_DEFECTO.items()}
        with self.conectar() as conn:
            for tipo, base, unidad in conn.execute("SELECT tipo, base, unidad FROM tarifas"):
                if tipo in tarifas:
                    tarifas[tipo] = {"base": float(base), "unidad": float(unidad)}
        return tarifas

    def guardar_tarifas(self, solicitante_id, nuevas):
        """Solo un administrador activo puede cambiarlas. `nuevas` = {tipo: {'base': x, 'unidad': y}}.
        Los pedidos ya guardados conservan su ingreso; el cambio rige para los nuevos y los editados."""
        limpias = {}
        for tipo, t in (nuevas or {}).items():
            if tipo not in TARIFAS_POR_DEFECTO:
                return False, f"Modalidad desconocida: {tipo}."
            try:
                base, unidad = float(t["base"]), float(t["unidad"])
            except (KeyError, TypeError, ValueError):
                return False, f"Montos inválidos en {tipo}."
            if (not (math.isfinite(base) and math.isfinite(unidad))
                    or not (0 <= base <= 1_000_000) or not (0 <= unidad <= 1_000_000)):
                return False, f"Los montos de {tipo} deben estar entre 0 y 1.000.000."
            limpias[tipo] = (base, unidad)
        if not limpias:
            return False, "No hay tarifas para guardar."
        with self.conectar() as conn:
            if not self._es_admin_activo(conn, solicitante_id):
                return False, "Solo el administrador puede cambiar las tarifas."
            for tipo, (base, unidad) in limpias.items():
                conn.execute(
                    "INSERT INTO tarifas (tipo, base, unidad) VALUES (?, ?, ?) "
                    "ON CONFLICT(tipo) DO UPDATE SET base = excluded.base, unidad = excluded.unidad",
                    (tipo, base, unidad)
                )
            conn.commit()
        return True, "Tarifas actualizadas."

    # ------------------------------------------------------------------ pedidos
    def verificar_sg_existente(self, sg, usuario_id):
        """True si ESE usuario ya registró el SG"""
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pedidos WHERE sg = ? AND usuario_id = ?", (sg, usuario_id))
            return cursor.fetchone()[0] > 0

    def insertar_pedido(self, fecha, sg, tipo, skus, articulos, ingreso, usuario_id, sincronizado=0):
        with self.conectar() as conn:
            cur = conn.execute("""
                INSERT INTO pedidos (fecha, sg, tipo, skus, articulos, ingreso, usuario_id, sincronizado)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (fecha, sg, tipo, skus, articulos, ingreso, usuario_id, sincronizado))
            conn.commit()
            return cur.lastrowid

    def actualizar_pedido(self, pedido_id, usuario_id, fecha, sg, tipo, skus, articulos, ingreso):
        """Actualiza un pedido existente asegurando que pertenezca al usuario y lo marca pendiente de sync"""
        with self.conectar() as conn:
            conn.execute("""
                UPDATE pedidos
                SET fecha = ?, sg = ?, tipo = ?, skus = ?, articulos = ?, ingreso = ?, sincronizado = 0
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

    def obtener_pedidos_por_rango(self, fecha_desde, fecha_hasta, usuario_id):
        """Pedidos del usuario entre dos fechas (inclusive, AAAA-MM-DD), más recientes primero"""
        with self.conectar() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, fecha, sg, tipo, skus, articulos, ingreso
                FROM pedidos WHERE fecha BETWEEN ? AND ? AND usuario_id = ?
                ORDER BY fecha DESC, id DESC
            """, (fecha_desde, fecha_hasta, usuario_id))
            return cursor.fetchall()

    def eliminar_pedido(self, pedido_id, usuario_id):
        """Solo elimina si el pedido pertenece al usuario"""
        with self.conectar() as conn:
            conn.execute("DELETE FROM pedidos WHERE id = ? AND usuario_id = ?", (pedido_id, usuario_id))
            conn.commit()

    # ---------------------------------------------------- sincronización con Firebase
    def obtener_pendientes_sync(self, usuario_id):
        """Devuelve los pedidos del usuario que aún no se han subido a Cloud Firestore."""
        with self.conectar() as conn:
            filas = conn.execute("""
                SELECT id, fecha, sg, tipo, skus, articulos, ingreso
                FROM pedidos WHERE usuario_id = ? AND sincronizado = 0
                ORDER BY id ASC
            """, (usuario_id,)).fetchall()
            return [
                {"id": f[0], "fecha": f[1], "sg": f[2], "tipo": f[3],
                 "skus": f[4], "articulos": f[5], "ingreso": f[6]}
                for f in filas
            ]

    def marcar_sincronizado(self, pedido_id):
        """Marca un pedido como respaldado en la nube."""
        with self.conectar() as conn:
            conn.execute("UPDATE pedidos SET sincronizado = 1 WHERE id = ?", (pedido_id,))
            conn.commit()

    def importar_desde_nube(self, usuario_id, lista_pedidos):
        """Inserta en SQLite local los pedidos descargados de Firebase que no existan localmente."""
        importados = 0
        with self.conectar() as conn:
            for p in lista_pedidos:
                sg = str(p.get("sg") or "").strip()
                if not sg:
                    continue
                existe = conn.execute(
                    "SELECT 1 FROM pedidos WHERE sg = ? AND usuario_id = ?", (sg, usuario_id)
                ).fetchone()
                if not existe:
                    conn.execute("""
                        INSERT INTO pedidos (fecha, sg, tipo, skus, articulos, ingreso, usuario_id, sincronizado)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                    """, (p["fecha"], sg, p["tipo"], p["skus"], p["articulos"], p["ingreso"], usuario_id))
                    importados += 1
            conn.commit()
        return importados

    # ---------------------------------------------------- sesión persistente local
    def guardar_sesion_local(self, rut, clave):
        """Guarda las credenciales activas en SQLite local para mantener la sesión abierta en Android."""
        rut = normalizar_rut(rut)
        if not rut or not clave:
            return
        with self.conectar() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sesion_local (id, rut, clave) VALUES (1, ?, ?)",
                (rut, str(clave).strip())
            )
            conn.commit()

    def obtener_sesion_local(self):
        """Recupera la sesión persistente guardada en SQLite local (o None si se cerró sesión)."""
        with self.conectar() as conn:
            fila = conn.execute("SELECT rut, clave FROM sesion_local WHERE id = 1").fetchone()
            if fila:
                return {"rut": fila[0], "clave": fila[1]}
            return None

    def borrar_sesion_local(self):
        """Elimina la sesión persistente al cerrar sesión manualmente o al desactivar la cuenta."""
        with self.conectar() as conn:
            conn.execute("DELETE FROM sesion_local WHERE id = 1")
            conn.commit()
