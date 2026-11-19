"""Crea (o promueve) al administrador de la aplicación. Ejecutar UNA vez en el servidor:

    python crear_admin.py

Las credenciales se escriben en la consola (la clave no se muestra) y no quedan en el código.
Los pedidos antiguos sin usuario pasan a ser del administrador."""
import getpass

from database import DatabaseManager
from seguridad import normalizar_rut, validar_rut

MIN_CLAVE_ADMIN = 8   # el administrador puede activar/desactivar usuarios: clave más robusta


def main():
    db = DatabaseManager()
    print(f"Base de datos: {db.db_name}")
    rut = normalizar_rut(input("RUT del administrador (sin puntos ni guion): "))
    if not validar_rut(rut):
        print("RUT inválido.")
        return
    nombre = input("Nombre: ").strip()
    if len(nombre) < 3:
        print("Ingresa un nombre.")
        return
    correo = input("Correo (opcional): ").strip()
    clave = getpass.getpass(f"Clave de administrador (mínimo {MIN_CLAVE_ADMIN} caracteres): ")
    if len(clave) < MIN_CLAVE_ADMIN:
        print(f"La clave debe tener al menos {MIN_CLAVE_ADMIN} caracteres.")
        return
    if clave != getpass.getpass("Repite la clave: "):
        print("Las claves no coinciden.")
        return
    ok, mensaje = db.crear_admin(rut, nombre, correo, clave)
    print(mensaje)


if __name__ == "__main__":
    main()
