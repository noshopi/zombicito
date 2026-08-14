"""
Integrar plantillas de personajes en el editor de diseño.
Extrae los frames de las plantillas y los prepara para usarlos en el editor.
"""
from PIL import Image
import os
import pygame

FOLDER = r"C:\proy\zombis\plantillas_personajes"
ASSETS_FOLDER = r"C:\proy\zombis\ZamnNative\assets"

# Configuración de frames por personaje
CHAR_CONFIG = {
    "1_ZEKE": {
        "fw": 23, "fh": 38,
        "cols": 8, "rows": 3,
        "actions": ["down", "left", "up"],  # 3 acciones
        "output": "zeke_template.png"
    },
    "2_JULIE": {
        "fw": 29, "fh": 38,
        "cols": 8, "rows": 4,
        "actions": ["down", "left", "up", "right"],  # 4 acciones
        "output": "julie_template.png"
    },
    "3_RUSTY": {
        "fw": 23, "fh": 38,
        "cols": 8, "rows": 3,
        "actions": ["down", "left", "up"],
        "output": "rusty_template.png"
    },
    "4_AZURA": {
        "fw": 29, "fh": 38,
        "cols": 8, "rows": 4,
        "actions": ["down", "left", "up", "right"],
        "output": "azura_template.png"
    },
    "5_DANTE": {
        "fw": 23, "fh": 38,
        "cols": 8, "rows": 3,
        "actions": ["down", "left", "up"],
        "output": "dante_template.png"
    },
}

def extract_frames_from_template(template_path, config):
    """Extraer frames individuales de una plantilla con líneas rojas."""
    img = Image.open(template_path).convert("RGBA")
    w, h = img.size
    
    fw, fh = config["fw"], config["fh"]
    cols, rows = config["cols"], config["rows"]
    
    print(f"Extrayendo frames de {os.path.basename(template_path)}...")
    print(f"  Tamaño: {w}x{h}, Frame: {fw}x{fh}, Grid: {cols}x{rows}")
    
    frames = []
    for row in range(rows):
        for col in range(cols):
            x = col * fw
            y = row * fh
            # Extraer el frame (las líneas rojas están en los bordes, así que recortamos 1px)
            frame = img.crop((x + 1, y + 1, x + fw - 1, y + fh - 1))
            frames.append(frame)
    
    print(f"  Extraídos {len(frames)} frames")
    return frames

def create_editor_sheet(frames, fw, fh, cols=8, rows=4):
    """Crear una sheet para el editor con los frames extraídos."""
    # Crear una superficie vacía
    sheet_w = fw * cols
    sheet_h = fh * rows
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    
    # Pegar cada frame en su posición
    for idx, frame in enumerate(frames):
        row = idx // cols
        col = idx % cols
        x = col * fw
        y = row * fh
        sheet.paste(frame, (x, y))
    
    return sheet

def main():
    print("Integrando plantillas en el editor...")
    print()
    
    # Procesar cada plantilla
    for char_name, config in CHAR_CONFIG.items():
        # Buscar la plantilla con líneas rojas
        template_file = None
        for f in os.listdir(FOLDER):
            if f.startswith(char_name) and ("_rojo" in f or "rojo" in f) and f.endswith(".png"):
                template_file = f
                break
        
        if not template_file:
            print(f"No se encontró plantilla roja para {char_name}")
            continue
        
        template_path = os.path.join(FOLDER, template_file)
        print(f"Procesando {template_file}...")
        
        # Extraer frames
        frames = extract_frames_from_template(template_path, config)
        
        # Crear sheet para el editor
        # Para personajes con 3 filas, añadir una fila vacía para completar 4
        if config["rows"] == 3:
            # Crear sheet con 4 filas (última fila vacía para RIGHT)
            sheet = create_editor_sheet(frames, config["fw"], config["fh"], cols=8, rows=4)
        else:
            sheet = create_editor_sheet(frames, config["fw"], config["fh"], cols=8, rows=4)
        
        # Guardar en assets
        output_path = os.path.join(ASSETS_FOLDER, config["output"])
        sheet.save(output_path)
        print(f"  Guardado en {output_path}")
        print()
    
    print("¡Integración completada!")
    print()
    print("Ahora puedes cargar estas plantillas en el editor:")
    for char_name, config in CHAR_CONFIG.items():
        print(f"  - {config['output']}")

if __name__ == "__main__":
    main()
