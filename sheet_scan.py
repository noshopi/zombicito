import os
from PIL import Image

ASSETS = os.path.join("ZamnNative", "assets")

def load(path, key_mode):
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

def clusters(img, gap=2):
    px = img.load()
    w, h = img.size
    visited = [[False] * w for _ in range(h)]
    out = []
    for y in range(h):
        for x in range(w):
            if visited[y][x] or px[x, y][3] <= 40:
                continue
            stack = [(x, y)]
            visited[y][x] = True
            minx, miny, maxx, maxy, n = x, y, x, y, 0
            while stack:
                cx, cy = stack.pop()
                n += 1
                if cx < minx: minx = cx
                if cx > maxx: maxx = cx
                if cy < miny: miny = cy
                if cy > maxy: maxy = cy
                for dx in range(-gap, gap + 1):
                    for dy in range(-gap, gap + 1):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < w and 0 <= ny < h and not visited[ny][nx] and px[nx, ny][3] > 40:
                            visited[ny][nx] = True
                            stack.append((nx, ny))
            out.append((minx, miny, maxx - minx + 1, maxy - miny + 1, n))
    out.sort(key=lambda c: (c[1], c[0]))
    return out

for path, km in [("zeke.png", 1), ("julie.png", 1), ("zombie.png", 2), ("victims.png", 1)]:
    img = load(path, km)
    print("==== %s (%dx%d) ====" % (path, img.size[0], img.size[1]))
    for c in clusters(img):
        if c[4] > 8:
            print("  rect=(%d,%d,%d,%d) px=%d" % c)
