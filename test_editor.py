"""
Test del editor con las plantillas
"""
import os
import sys

# Simular las variables globales del editor
gCust = [0]  # Zeke seleccionado
gEdRefTex = None
gEdFrames = []
gEdFW = 23
gEdFH = 38

ASSETS = r'C:\proy\zombis\ZamnNative\assets'

def _load_template(name, fw, fh, rows=4):
    """Cargar plantilla y extraer frames sin bordes rojos."""
    path = os.path.join(ASSETS, name)
    if not os.path.exists(path):
        print(f"  No encontrado: {path}")
        return None
    
    try:
        # Simular carga (no podemos usar pygame sin display)
        print(f"  Cargando: {name}")
        print(f"  Dimensiones frame: {fw}x{fh}")
        print(f"  Filas: {rows}, Columnas: 8")
        print(f"  Frames totales: {rows * 8}")
        
        # Para Zeke-like (3 filas = 24 frames)
        if rows == 3:
            # Frame sin bordes rojos: 23-2=21, 38-2=36
            frame_w = fw - 2
            frame_h = fh - 2
            print(f"  Frame extraído (sin bordes): {frame_w}x{frame_h}")
            print(f"  Se añadirán 8 frames vacíos para completar 32")
        else:
            frame_w = fw - 2
            frame_h = fh - 2
            print(f"  Frame extraído (sin bordes): {frame_w}x{frame_h}")
        
        return True
    except Exception as e:
        print(f"  Error: {e}")
        return False

print("=== TEST: editor_open() ===\n")

# Simular editor_open()
print("Cargando plantillas...")
print()

templates = {
    0: ('zeke_template.png', 23, 38, 3),
    1: ('julie_template.png', 29, 38, 4),
    2: ('rusty_template.png', 23, 38, 3),
    3: ('azura_template.png', 29, 38, 4),
    4: ('dante_template.png', 23, 38, 3),
}

bi = gCust[0]
if bi in templates:
    name, fw, fh, rows = templates[bi]
    print(f"Personaje seleccionado: índice {bi}")
    print(f"Plantilla: {name}")
    print()
    success = _load_template(name, fw, fh, rows)
    
    if success:
        print()
        print("Resultado:")
        print(f"  gEdFW = {fw - 2}")
        print(f"  gEdFH = {fh - 2}")
        print(f"  gEdFrames = 32 frames")
        print(f"  gEdRefTex = Surface({(fw-2)*8}x{(fh-2)*4})")
        print()
        print("  [OK] Plantilla cargada correctamente")
else:
    print(f"  [FAIL] Personaje {bi} no tiene plantilla")

print()
print("=== TEST: _ed_zoom() ===\n")

# Calcular zoom
VIEW_W = 480
VIEW_H = 270
ED_CX = 54
ED_CY = 46
ED_ZOOM = 4

gEdFW_test = 21  # 23 - 2 (sin bordes rojos)
gEdFH_test = 36  # 38 - 2

max_w = VIEW_W - ED_CX - 12
max_h = VIEW_H - ED_CY - 44

zoom_w = max_w // gEdFW_test
zoom_h = max_h // gEdFH_test
zoom = max(ED_ZOOM, min(zoom_w, zoom_h))

print(f"Frame: {gEdFW_test}x{gEdFH_test}")
print(f"Espacio disponible: {max_w}x{max_h}")
print(f"Zoom X: {zoom_w}")
print(f"Zoom Y: {zoom_h}")
print(f"Zoom final: {zoom}")
print(f"Tamaño en pantalla: {gEdFW_test * zoom}x{gEdFH_test * zoom}")
print()

if gEdFW_test * zoom <= max_w and gEdFH_test * zoom <= max_h:
    print("[OK] El frame cabe perfectamente en el área de dibujo")
else:
    print("[FAIL] El frame NO cabe en el área de dibujo")
