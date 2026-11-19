"""Utilidades de seguridad: RUT, ID Boosmap y hash de claves."""
import hashlib
import os
import re
import secrets
from pathlib import Path

_pepper_cache = None
NOMBRE_PEPPER = ".picking_pepper"


def carpeta_codigo():
    return Path(__file__).resolve().parent


def carpetas_de_datos():
    """Carpetas donde pueden estar la base de datos y el archivo secreto, por prioridad:
    la que define Flet (FLET_APP_STORAGE_DATA), la de `flet run` (.flet/storage/data) y la del código."""
    codigo = carpeta_codigo()
    candidatas = []
    env = os.environ.get("FLET_APP_STORAGE_DATA")
    if env:
        candidatas.append(Path(env))
    candidatas += [codigo / ".flet" / "storage" / "data", codigo]
    unicas, vistas = [], set()
    for c in candidatas:
        clave = os.path.normcase(str(c.resolve()))
        if clave not in vistas:
            vistas.add(clave)
            unicas.append(c)
    return unicas


def carpeta_destino():
    """Donde se CREAN archivos nuevos: la carpeta de datos de Flet (móvil / flet run) o la del código."""
    env = os.environ.get("FLET_APP_STORAGE_DATA")
    return Path(env) if env else carpeta_codigo()


def ruta_pepper_existente():
    """Si ya existe un archivo secreto se REUTILIZA (cambiarlo invalida todas las claves guardadas).
    Prioridad: carpeta del código (donde lo creaban las versiones anteriores) y luego las carpetas de datos."""
    for carpeta in [carpeta_codigo()] + carpetas_de_datos():
        ruta = carpeta / NOMBRE_PEPPER
        if ruta.is_file():
            return ruta
    return None


def _pepper():
    """Secreto del servidor (fuera de la base de datos).
    Se toma de la variable de entorno PICKING_PEPPER o de un archivo local que se crea solo.
    ¡Respáldalo! Si se pierde, nadie podrá iniciar sesión (los hash no se pueden recuperar)."""
    global _pepper_cache
    if _pepper_cache is None:
        env = os.environ.get("PICKING_PEPPER")
        if env:
            _pepper_cache = env.encode("utf-8")
        elif ruta_pepper_existente() is not None:
            _pepper_cache = bytes.fromhex(ruta_pepper_existente().read_text().strip())
        else:
            valor = secrets.token_hex(32)
            ruta = carpeta_destino() / NOMBRE_PEPPER
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(valor)
            try:
                os.chmod(ruta, 0o600)
            except OSError:
                pass
            _pepper_cache = bytes.fromhex(valor)
    return _pepper_cache


def normalizar_rut(texto):
    """Quita puntos, guion y espacios; la K en mayúscula."""
    return re.sub(r"[.\-\s]", "", texto or "").upper()


def _digito_verificador(cuerpo):
    suma, mult = 0, 2
    for d in reversed(cuerpo):
        suma += int(d) * mult
        mult = 2 if mult == 7 else mult + 1
    r = 11 - (suma % 11)
    return "0" if r == 11 else "K" if r == 10 else str(r)


def validar_rut(rut):
    """RUT normalizado: 7-8 dígitos + dígito verificador (0-9 o K), validado con módulo 11."""
    if not re.fullmatch(r"\d{7,8}[0-9K]", rut or ""):
        return False
    return rut[-1] == _digito_verificador(rut[:-1])


def validar_id_boosmap(valor):
    """ID Boosmap: exactamente 6 dígitos."""
    return bool(re.fullmatch(r"\d{6}", valor or ""))


def hash_clave(clave):
    """Hash determinista (PBKDF2 + pepper del servidor): permite la restricción UNIQUE
    y evita recuperar los ids por fuerza bruta si solo se filtra el archivo .db."""
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), _pepper(), 200_000).hex()
