"""
Test para verificar que las plantillas se cargan correctamente.
"""
import os

ASSETS = r"C:\proy\zombis\ZamnNative\assets"

# Test each template
templates = {
    "zeke_template.png": (23, 38, 3),
    "julie_template.png": (29, 38, 4),
    "rusty_template.png": (23, 38, 3),
    "azura_template.png": (29, 38, 4),
    "dante_template.png": (23, 38, 3),
}

for name, (fw, fh, rows) in templates.items():
    path = os.path.join(ASSETS, name)
    if os.path.exists(path):
        size = os.path.getsize(path)
        print(f"[OK] {name}: {size} bytes")
    else:
        print(f"[FAIL] {name}: no encontrado")

print("\nTest completado!")
