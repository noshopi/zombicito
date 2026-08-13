import os
from PIL import Image
from collections import Counter

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

def pal(img, rect):
    x, y, w, h = rect
    c = Counter()
    for yy in range(h):
        for xx in range(w):
            a = img.getpixel((x + xx, y + yy))[3]
            if a > 40:
                c[img.getpixel((x + xx, y + yy))[:3]] += 1
    return c

def report(name, img, rects):
    print("== %s ==" % name)
    for r in rects:
        p = pal(img, r)
        top = [c for c, n in p.most_common(4)]
        print("  %s px=%d palette=%s" % (r, sum(p.values()), top))

zeke = load("zeke.png", 1)
# reference: used DOWN frames
report("ZEKE DOWN used (108,4)", zeke, [(86, 5, 16, 36), (108, 4, 15, 37), (128, 4, 16, 37)])
report("ZEKE DOWN candidates", zeke, [(149, 4, 15, 37), (170, 4, 15, 37), (214, 4, 16, 37), (239, 4, 23, 37), (292, 4, 23, 37)])
report("ZEKE LEFT used", zeke, [(87, 44, 15, 37), (108, 44, 13, 37), (126, 44, 21, 37), (152, 44, 14, 37)])
report("ZEKE LEFT candidates", zeke, [(170, 45, 21, 36)])
report("ZEKE UP used", zeke, [(87, 86, 16, 35), (108, 85, 14, 36), (129, 86, 16, 35), (153, 85, 14, 36)])
report("ZEKE UP candidates", zeke, [(174, 86, 16, 35), (215, 84, 16, 37), (237, 84, 29, 37), (290, 84, 29, 37)])

julie = load("julie.png", 1)
report("JULIE DOWN used", julie, [(7, 4, 20, 38), (9, 52, 16, 38), (10, 102, 15, 38), (7, 154, 16, 38), (7, 205, 16, 38)])
report("JULIE DOWN candidates", julie, [(229, 6, 16, 37), (251, 5, 30, 38), (298, 7, 17, 38), (333, 8, 30, 38)])
report("JULIE LEFT used", julie, [(41, 5, 18, 37), (40, 55, 22, 36), (40, 103, 22, 36), (39, 153, 20, 36), (39, 206, 24, 35)])
report("JULIE LEFT candidates", julie, [(179, 7, 15, 16), (203, 6, 13, 16), (545, 14, 16, 13), (521, 15, 16, 12)])

zomb = load("zombie.png", 2)
report("ZOMBIE DOWN used", zomb, [(8, 22, 27, 47), (41, 21, 27, 48), (74, 21, 27, 48), (108, 22, 27, 47)])
report("ZOMBIE DOWN candidates (y8-16)", zomb, [(9, 8, 31, 9), (48, 8, 18, 9), (69, 8, 19, 7), (91, 8, 40, 7)])
report("ZOMBIE RIGHT candidates", zomb, [(272, 79, 36, 7), (9, 81, 41, 9), (227, 84, 11, 7)])
