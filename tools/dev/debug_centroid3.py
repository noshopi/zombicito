import os
from PIL import Image
ASSETS = os.path.join("ZamnNative", "assets")
img = Image.open(os.path.join(ASSETS, "zombie.png")).convert("RGBA")
px = img.load()
w, h = img.size
key = px[0, 0]
print("key before:", key)
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if (r, g, b, a) == (key[0], key[1], key[2], 255):
            px[x, y] = (0, 0, 0, 0)
        elif key == (0, 0, 0, 0):
            if abs(r - 8) <= 26 and abs(g - 176) <= 26 and abs(b - 120) <= 26:
                px[x, y] = (0, 0, 0, 0)
            elif abs(r - 8) <= 20 and abs(g - 112) <= 20 and abs(b - 80) <= 20:
                px[x, y] = (0, 0, 0, 0)
rect = (149, 23, 25, 46)
x, y, rw, rh = rect
n, sx, black = 0, 0, 0
for yy in range(rh):
    for xx in range(rw):
        if px[x + xx, y + yy][3] > 40:
            n += 1
            sx += xx
            if px[x + xx, y + yy][:3] == (0, 0, 0):
                black += 1
print("n:", n, "black:", black, "cx: %.2f vc: %.2f" % (sx / n, sx / n - rw / 2.0))
