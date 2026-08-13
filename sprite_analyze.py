import os
from PIL import Image

ASSETS = os.path.join("ZamnNative", "assets")

def load(path, key_mode):
    img = Image.open(path).convert("RGBA")
    px = img.load()
    w, h = img.size
    if key_mode:
        key = px[0, 0]
        # mimic pygame: replace exact key + zombie green ranges
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

def content_stats(img, rect):
    x, y, w, h = rect
    sub = img.crop((x, y, x + w, y + h))
    px = sub.load()
    minx, miny, maxx, maxy = w, h, -1, -1
    n = 0
    for yy in range(h):
        for xx in range(w):
            if px[xx, yy][3] > 40:
                if xx < minx: minx = xx
                if xx > maxx: maxx = xx
                if yy < miny: miny = yy
                if yy > maxy: maxy = yy
                n += 1
    if n == 0:
        return None
    # baseline: lowest row with content
    baseline = maxy
    # centroid x
    sx = 0
    for yy in range(h):
        for xx in range(w):
            if px[xx, yy][3] > 40:
                sx += xx
    return {"content": n, "bbox": (minx, miny, maxx, maxy), "baseline": baseline,
            "w": maxx - minx + 1, "h": maxy - miny + 1, "centroid": sx / n,
            "margin_b": h - 1 - maxy, "margin_t": miny}

def analyze(name, path, frames, key_mode=1):
    img = load(os.path.join(ASSETS, path), key_mode)
    print("==== %s (%dx%d) ====" % (name, img.size[0], img.size[1]))
    for label, flist in frames:
        print("-- %s" % label)
        for i, f in enumerate(flist):
            s = content_stats(img, f)
            if s is None:
                print("  frame %d %s EMPTY" % (i, f))
            else:
                print("  frame %d %s bbox=%s w=%d h=%d cx=%.1f base=%d mt=%d mb=%d" % (
                    i, f, s["bbox"], s["w"], s["h"], s["centroid"], s["baseline"], s["margin_t"], s["margin_b"]))

analyze("ZEKE", "zeke.png", [
    ("DOWN", ZEKE_DOWN := [(86, 5, 16, 36), (108, 4, 16, 37), (128, 4, 16, 37), (148, 4, 16, 37)]),
    ("LEFT", ZEKE_LEFT := [(86, 44, 17, 37), (108, 44, 13, 37), (125, 44, 23, 37), (151, 44, 15, 37)]),
    ("UP", ZEKE_UP := [(87, 86, 16, 35), (108, 85, 14, 36), (129, 86, 16, 35), (153, 85, 14, 36)]),
])
analyze("JULIE", "julie.png", [
    ("DOWN", JULIE_DOWN := [(7, 4, 20, 38), (8, 52, 18, 38), (10, 102, 16, 38), (7, 154, 16, 38), (7, 205, 16, 38)]),
    ("LEFT", JULIE_LEFT := [(41, 5, 18, 37), (38, 55, 25, 36), (39, 103, 24, 36), (39, 153, 20, 36), (36, 206, 29, 35)]),
    ("UP", JULIE_UP := [(76, 5, 20, 37), (76, 53, 14, 37), (74, 101, 15, 37), (73, 152, 14, 37), (74, 204, 15, 37)]),
    ("RIGHT", JULIE_RIGHT := [(108, 6, 20, 37), (105, 54, 23, 36), (102, 103, 22, 36), (101, 154, 22, 36), (94, 205, 27, 35)]),
])
analyze("ZOMBIE", "zombie.png", [
    ("DOWN", ZOM_DOWN := [(8, 22, 27, 47), (41, 21, 27, 48), (74, 21, 27, 48), (108, 22, 27, 47)]),
    ("RIGHT", ZOM_RIGHT := [(145, 23, 32, 46), (177, 24, 32, 45), (209, 23, 33, 46), (242, 24, 31, 45)]),
    ("UP", ZOM_UP := [(286, 23, 23, 46), (313, 23, 25, 46), (343, 23, 23, 46), (374, 23, 23, 46)]),
    ("RISE", ZOM_RISE := [(11, 135, 12, 6), (30, 128, 24, 13), (63, 125, 32, 15), (148, 100, 32, 41), (189, 94, 28, 47)]),
    ("DIE", ZOM_DIE := [(43, 154, 4, 7), (48, 165, 34, 51), (61, 156, 7, 5)]),
], key_mode=2)
analyze("VICTIMS", "victims.png", [
    ("CHEER", VIC_CHEER := [(40, 109, 44, 41), (184, 95, 44, 41), (280, 97, 44, 41), (376, 103, 44, 41)]),
    ("DOG", VIC_DOG := [(2, 56, 33, 27), (35, 54, 30, 29), (67, 52, 30, 31), (100, 54, 31, 29)]),
    ("SOLDIER", VIC_SOLDIER := [(4, 220, 33, 46), (40, 218, 33, 48), (76, 218, 32, 48)]),
    ("KID", VIC_KID := [(37, 384, 31, 29), (72, 379, 37, 34), (113, 373, 46, 40)]),
    ("TOURIST", VIC_TOURIST := [(7, 167, 41, 39), (59, 174, 41, 32)]),
])
