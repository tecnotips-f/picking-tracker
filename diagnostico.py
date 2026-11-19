"""Diagnóstico de inicio de sesión (no muestra ni modifica claves).

    python diagnostico.py            -> qué base y qué archivo secreto usa la app, y los usuarios que hay
    python diagnostico.py 285447097  -> además pide la clave y dice si ese RUT + clave coinciden
"""
import getpass
import hmac
import sqlite3
import sys

from database import NOMBRE_BD, _contenido, elegir_base
from seguridad import (NOMBRE_PEPPER, carpetas_de_datos, hash_clave, normalizar_rut,
                       ruta_pepper_existente)


def main():
    print("== Bases de datos encontradas ==")
    for carpeta in carpetas_de_datos():
        ruta = carpeta / NOMBRE_BD
        print(f"  {'SI ' if ruta.is_file() else 'no '} {ruta}" + (f"  (filas: {_contenido(ruta)})" if ruta.is_file() else ""))
    base = elegir_base()
    print(f"\nBase que usará la app: {base}")
    pepper = ruta_pepper_existente()
    print(f"Archivo secreto ({NOMBRE_PEPPER}): {pepper if pepper else 'NO existe todavía (se creará al primer uso)'}")

    conn = sqlite3.connect(base)
    try:
        usuarios = conn.execute("SELECT id, rut, nombre, rol, activo, clave_hash FROM usuarios ORDER BY id").fetchall()
    except sqlite3.Error:
        usuarios = []
    print(f"\n== Usuarios ({len(usuarios)}) ==")
    for u in usuarios:
        print(f"  id={u[0]}  RUT={u[1]}  {u[2]}  rol={u[3]}  {'activo' if u[4] else 'INACTIVO'}")

    if len(sys.argv) > 1:
        rut = normalizar_rut(sys.argv[1])
        fila = next((u for u in usuarios if u[1] == rut), None)
        print(f"\n== Prueba de {rut} ==")
        if not fila:
            print("  El RUT NO existe en esa base.")
            return
        clave = getpass.getpass("  Clave (no se muestra): ").strip()
        coincide = hmac.compare_digest(fila[5], hash_clave(clave))
        print(f"  RUT existe: sí | activo: {'sí' if fila[4] else 'NO'} | clave coincide: {'SÍ' if coincide else 'NO'}")


if __name__ == "__main__":
    main()
