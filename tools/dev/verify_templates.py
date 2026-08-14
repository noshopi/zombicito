"""
Verificar que las plantillas con lineas rojas se cargan correctamente
"""
import os

FOLDER = r"C:\proy\zombis\plantillas_personajes"

templates = [
    ("1_ZEKErojo.png", 23, 38, 3),
    ("1_ZEKE_rojo.png", 23, 38, 3),
    ("2_JULIE_rojo.png", 29, 38, 4),
    ("3_RUSTY_rojo.png", 23, 38, 3),
    ("4_AZURA_rojo.png", 29, 38, 4),
    ("5_DANTE_rojo.png", 23, 38, 3),
]

print("=== Verificando plantillas con lineas rojas ===\n")

for filename, fw, fh, rows in templates:
    path = os.path.join(FOLDER, filename)
    if os.path.exists(path):
        size = os.path.getsize(path)
        expected_w = fw * 8
        expected_h = fh * rows
        print(f"[OK] {filename}")
        print(f"     Tamano: {size} bytes")
        print(f"     Frame: {fw}x{fh}")
        print(f"     Grid: 8x{rows}")
        print(f"     Tamano esperado: {expected_w}x{expected_h}")
    else:
        print(f"[FAIL] {filename} - NO ENCONTRADO")
    print()

print("=== Verificacion completada ===")
