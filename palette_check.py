import os
from PIL import Image

ASSETS = os.path.join("ZamnNative", "assets")

def load(path, key_mode=1):
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

def frame_palette(img, rect):
    x, y, w, h = rect
    sub = img.crop((x, y, x + w, y + h))
    px = sub.load()
    from collections import Counter
    c = Counter()
    for yy in range(h):
        for xx in range(w):
            a = px[xx, yy][3]
            if a > 40:
                c[px[xx, yy][:3]] += 1
    return c

def edge_info(img, rect):
    x, y, w, h = rect
    px = img.load()
    edges = []
    for yy in range(h):
        for xx in range(w):
            if px[x + xx, y + yy][3] > 40:
                # check 4-neighbors outside content
                n_out = 0
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + xx + dx, y + yy + dy
                    if 0 <= nx < img.size[0] and 0 <= ny < img.size[1]:
                        if px[nx, ny][3] <= 40:
                            n_out += 1
                if n_out:
                    edges.append((xx, yy, px[x + xx, y + yy]))
    return edges

img = load("zeke.png", 1)
print("== ZEKE palette (DOWN f0) ==")
for col, n in frame_palette(img, (86, 5, 16, 36)).most_common(12):
    print(col, n)
edges = edge_info(img, (86, 5, 16, 36))
print("edge px count:", len(edges))
print("edge samples:", edges[:8])
lums = []
for xx, yy, c in edges:
    lums.append(c[0] * 0.3 + c[1] * 0.6 + c[2] * 0.1)
print("edge luminance min/max: %.1f %.1f" % (min(lums), max(lums)))

img = load("zombie.png", 2)
print("== ZOMBIE palette (DOWN f0) ==")
for col, n in frame_palette(img, (8, 22, 27, 47)).most_common(10):
    print(col, n)
edges = edge_info(img, (8, 22, 27, 47))
lums = [c[0] * 0.3 + c[1] * 0.6 + c[2] * 0.1 for xx, yy, c in edges]
print("edge px:", len(edges), "lum %.1f..%.1f" % (min(lums), max(lums)))

img = load("victims.png", 1)
for nm, r in [("CHEER", (40, 109, 44, 41)), ("SOLDIER", (4, 220, 32, 46))]:
    print("== VICTIM %s palette ==" % nm)
    for col, n in frame_palette(img, r).most_common(8):
        print(col, n)
    edges = edge_info(img, r)
    lums = [c[0] * 0.3 + c[1] * 0.6 + c[2] * 0.1 for xx, yy, c in edges]
    print("edge px:", len(edges), "lum %.1f..%.1f" % (min(lums), max(lums)))

img = load("julie.png", 1)
print("== JULIE palette (DOWN f0) ==")
for col, n in frame_palette(img, (7, 4, 20, 38)).most_common(10):
    print(col, n)
edges = edge_info(img, (7, 4, 20, 38))
lums = [c[0] * 0.3 + c[1] * 0.6 + c[2] * 0.1 for xx, yy, c in edges]
print("edge px:", len(edges), "lum %.1f..%.1f" % (min(lums), max(lums)))
