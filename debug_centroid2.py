import os
from PIL import Image
ASSETS = os.path.join("ZamnNative", "assets")
img = Image.open(os.path.join(ASSETS, "zombie.png")).convert("RGBA")
px = img.load()
w, h = img.size
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if (r, g, b, a) == (px[0, 0][0], px[0, 0][1], px[0, 0][2], 255):
            px[x, y] = (0, 0, 0, 0)
        else:
            if abs(r - 8) <= 26 and abs(g - 176) <= 26 and abs(b - 120) <= 26:
                px[x, y] = (0, 0, 0, 0)
            elif abs(r - 8) <= 20 and abs(g - 112) <= 20 and abs(b - 80) <= 20:
                px[x, y] = (0, 0, 0, 0)
rect = (149, 23, 25, 46)
x, y, rw, rh = rect
n, sx = 0, 0
for yy in range(rh):
    for xx in range(rw):
        if px[x + xx, y + yy][3] > 40:
            n += 1
            sx += xx
print("cx=%.2f rectw=%d vc(cx-rectw/2)=%.2f" % (sx / n, rw, sx / n - rw / 2.0))
