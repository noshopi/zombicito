import os
from PIL import Image

ASSETS = os.path.join("ZamnNative", "assets")

img = Image.open(os.path.join(ASSETS, "zeke.png")).convert("RGBA")
px = img.load()
w, h = img.size
key = px[0, 0]
for y in range(h):
    for x in range(w):
        r, g, b, a = px[x, y]
        if (r, g, b, a) == (key[0], key[1], key[2], 255):
            px[x, y] = (0, 0, 0, 0)

def sig(rect):
    x, y, rw, rh = rect
    out = []
    for yy in range(rh):
        for xx in range(rw):
            out.append(px[x + xx, y + yy])
    return tuple(out)

def compare(a, b):
    sa, sb = sig(a), sig(b)
    same = sum(1 for i in range(min(len(sa), len(sb))) if sa[i] == sb[i])
    return same, min(len(sa), len(sb))

pairs = [
    ("DOWN D(149,4) vs B(108,4)", (149, 4, 15, 37), (108, 4, 15, 37)),
    ("DOWN E(170,4) vs C(128,4)", (170, 4, 15, 37), (128, 4, 16, 37)),
    ("DOWN D vs E", (149, 4, 15, 37), (170, 4, 15, 37)),
    ("DOWN D vs A(86,5)", (149, 4, 15, 37), (86, 5, 16, 36)),
    ("LEFT F(170,45) vs A(87,44)", (170, 45, 21, 36), (87, 44, 15, 37)),
    ("LEFT F vs B(108,44)", (170, 45, 21, 36), (108, 44, 13, 37)),
    ("LEFT F vs C(126,44)", (170, 45, 21, 36), (126, 44, 21, 37)),
    ("LEFT F vs D(152,44)", (170, 45, 21, 36), (152, 44, 14, 37)),
    ("UP G(174,86) vs A(87,86)", (174, 86, 16, 35), (87, 86, 16, 35)),
    ("UP G vs B(108,85)", (174, 86, 16, 35), (108, 85, 14, 36)),
    ("UP G vs C(129,86)", (174, 86, 16, 35), (129, 86, 16, 35)),
    ("UP G vs D(153,85)", (174, 86, 16, 35), (153, 85, 14, 36)),
]
for name, a, b in pairs:
    same, total = compare(a, b)
    print("%s: %d/%d equal (%.0f%%)" % (name, same, total, 100.0 * same / total))
