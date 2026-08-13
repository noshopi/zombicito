"""
Procesar plantillas de personajes:
1. Añadir líneas rojas de frame (bordes) alrededor de cada bloque de frame
2. Eliminar fotos de selección de personaje (Julie_original, Zeke_original)
3. Mantener solo los frames de walk (down, left, up) - 8 frames por fila, 3 filas para Zeke-like
4. Para Julie-like: mantener 4 filas (down, left, up, right)
"""
from PIL import Image, ImageDraw
import os

FOLDER = r"C:\proy\zombis\plantillas_personajes"

# Dimensiones conocidas por personaje base
CHAR_DIMS = {
    "1_ZEKE": {"fw": 23, "fh": 38, "cols": 8, "rows": 3},  # 3 filas: down, left, up
    "3_RUSTY": {"fw": 23, "fh": 38, "cols": 8, "rows": 3},
    "5_DANTE": {"fw": 23, "fh": 38, "cols": 8, "rows": 3},
    "2_JULIE": {"fw": 29, "fh": 38, "cols": 8, "rows": 4},  # 4 filas: down, left, up, right
    "4_AZURA": {"fw": 29, "fh": 38, "cols": 8, "rows": 4},
}

def get_base_name(name):
    """Obtener el nombre base de la plantilla."""
    name = name.replace(".png", "")
    if name.endswith("_rojo"):
        name = name[:-5]
    if name.endswith("rojo"):
        name = name[:-4]
    return name

def process_template(input_path, output_path):
    """Procesar una plantilla individual: añadir líneas rojas entre frames."""
    img = Image.open(input_path).convert("RGBA")
    w, h = img.size
    
    base_name = get_base_name(os.path.basename(input_path).replace(".png", ""))
    
    # Buscar dimensiones en CHAR_DIMS
    dims = None
    for key, val in CHAR_DIMS.items():
        if key == base_name.upper() or key.replace("_", "") == base_name.upper().replace("_", ""):
            dims = val
            break
    
    if dims is None:
        print(f"  No se encontraron dimensiones para {base_name}, saltando")
        return False
    
    fw, fh = dims["fw"], dims["fh"]
    cols, rows = dims["cols"], dims["rows"]
    
    print(f"  Dimensiones: frame={fw}x{fh}, grid={cols}x{rows}")
    print(f"  Tamaño esperado: {cols*fw}x{rows*fh}, actual: {w}x{h}")
    
    # Añadir líneas rojas entre frames
    draw = ImageDraw.Draw(img)
    line_color = (255, 0, 0, 255)  # Rojo
    
    # Líneas verticales entre columnas
    for col in range(1, cols):
        x = col * fw
        draw.line([(x, 0), (x, h)], fill=line_color, width=1)
    
    # Líneas horizontales entre filas
    for row in range(1, rows):
        y = row * fh
        draw.line([(0, y), (w, y)], fill=line_color, width=1)
    
    # Borde exterior
    draw.rectangle([(0, 0), (w-1, h-1)], outline=line_color, width=1)
    
    img.save(output_path)
    return True

def delete_unused_images():
    """Eliminar imágenes que no se usan (selección de personaje)."""
    unused = ["Julie_original.png", "Zeke_original.png"]
    for filename in unused:
        path = os.path.join(FOLDER, filename)
        if os.path.exists(path):
            os.remove(path)
            print(f"Eliminado: {filename}")

def main():
    print("Procesando plantillas de personajes...")
    print()
    
    # Eliminar imágenes no usadas
    delete_unused_images()
    print()
    
    # Procesar cada plantilla
    files = sorted([f for f in os.listdir(FOLDER) if f.endswith(".png")])
    
    for filename in files:
        input_path = os.path.join(FOLDER, filename)
        output_path = os.path.join(FOLDER, filename)
        
        print(f"Procesando {filename}...")
        
        success = process_template(input_path, output_path)
        
        if success:
            print(f"  -> Guardado con líneas rojas")
        print()
    
    print("¡Procesamiento completado!")

if __name__ == "__main__":
    main()
