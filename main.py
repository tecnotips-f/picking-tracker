secret_number = 3

print(
"""
+==================================+
| ¡Bienvenido a mi juego, muggle!  |
| Introduce un número entero       |
| y adivina qué número he          |
| elegido para ti.                 |
| Entonces,                        |
| ¿Cuál es el número secreto?      |
+==================================+
""")

# 1. Pedimos el primer número y lo convertimos a entero con int()
n = int(input("Introduce un número entero: "))

# 2. El bucle se ejecutará MIENTRAS el usuario NO adivine
while n != secret_number:
    print("¡Ja, ja! ¡Estás atrapado en mi bucle!")
    
    # Le volvemos a pedir el número adentro para evitar el bucle infinito real
    n = int(input("Intenta de nuevo, introduce un número entero: "))

# 3. Si el bucle termina, significa que n == secret_number (¡Adivinó!)

print(f"El número secreto era el {n}.")
print("¡Bien hecho, muggle! Eres libre ahora.")
