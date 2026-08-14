import sys
import os
sys.path.insert(0, r'C:\proy\zombis')

ASSETS = r'C:\proy\zombis\ZamnNative\assets'

templates = {
    'zeke': 'zeke_template.png',
    'julie': 'julie_template.png',
    'rusty': 'rusty_template.png',
    'azura': 'azura_template.png',
    'dante': 'dante_template.png',
}

print('Verificando plantillas:')
for name, file in templates.items():
    path = os.path.join(ASSETS, file)
    if os.path.exists(path):
        print(f'[OK] {name}: {file}')
    else:
        print(f'[FAIL] {name}: {file} NO existe')

print()
print('Configuracion del editor:')
print('  VIEW_W: 480, VIEW_H: 270')
print('  ED_CX: 54, ED_CY: 46')
print('  ED_ZOOM: 4')
print(f'  Espacio disponible: {480-54-12}x{270-46-44}')
