import os
from PIL import Image

ASSETS = os.path.join("ZamnNative", "assets")

def load_a(path, key_mode):
    img = Image.open(os.path.join(ASSETS, path)).convert("RGBA")
    px = img.load()
    w, h = img.size
    if key_mode:
        key = px[0, 0]
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if (r, g, b, a) == (key[0], key[1], key[2], 255):
                    px[x, y] = (0, 0, 0, 0)
                elif key_mode == 2:
                    if abs(r - 8) <= 26 and abs(g - 176) <= 26 and abs(b - 120) <= 26:
                        px[x, y] = (0, 0, 0, 0)
                    elif abs(r - 8) <= 20 and abs(g - 112) <= 20 and abs(b - 80) <= 20:
                        px[x, y] = (0, 0, 0, 0)
    return img

img = load_a("zombie.png", 2)
px = img.load()
print("key(0,0):", px[0, 0])
rect = (149, 23, 25, 46)
x, y, w, h = rect
n, sx = 0, 0
mins = 999
for yy in range(h):
    for xx in range(w):
        if px[x + xx, y + yy][3] > 40:
            n += 1
            sx += xx
print("n:", n, "cx:", sx / n, "vc:", sx / n - w / 2.0)
# count transparent inside rect
t = sum(1 for yy in range(h) for xx in range(w) if px[x + xx, y + yy][3] <= 40)
print("transparent in rect:", t)
