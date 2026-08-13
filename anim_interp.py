# Animation interpolator: expands 4-frame walk cycles to 8 frames.
# New frames are blends of neighboring keyframes (feet aligned, body
# recentered), giving smooth motion while keeping the pixel style.
# Produces zeke_walk.png / julie_walk.png / zombie_walk.png side-by-side
# with zamn.py's sprite tables; the game uses them when present.
# Layout (rows = directions, fixed sizes):
#   zeke_walk.png   23x38  DOWN y0 / LEFT y38 / UP y76
#   julie_walk.png  29x38  DOWN y0 / LEFT y38 / UP y76 / RIGHT y114
#   zombie_walk.png 33x48  DOWN y0 / RIGHT y48 / UP y96
import os
from PIL import Image

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")

ZEKE_DOWN = [(86, 5, 16, 36), (108, 4, 16, 37), (128, 4, 16, 37), (148, 4, 16, 37)]
ZEKE_LEFT = [(86, 44, 17, 37), (108, 44, 13, 37), (125, 44, 23, 37), (151, 44, 15, 37)]
ZEKE_UP = [(87, 86, 16, 35), (108, 85, 14, 36), (129, 86, 16, 35), (153, 85, 14, 36)]
JULIE_DOWN = [(7, 4, 20, 38), (8, 52, 18, 38), (10, 102, 16, 38), (7, 154, 16, 38), (7, 205, 16, 38)]
JULIE_LEFT = [(41, 5, 18, 37), (38, 55, 25, 36), (39, 103, 24, 36), (39, 153, 20, 36), (36, 206, 29, 35)]
JULIE_UP = [(76, 5, 20, 37), (76, 53, 14, 37), (74, 101, 15, 37), (73, 152, 14, 37), (74, 204, 15, 37)]
JULIE_RIGHT = [(108, 6, 20, 37), (105, 54, 23, 36), (102, 103, 22, 36), (101, 154, 22, 36), (94, 205, 27, 35)]
ZOM_DOWN = [(8, 22, 27, 47), (41, 21, 27, 48), (74, 21, 27, 48), (108, 22, 27, 47)]
ZOM_RIGHT = [(145, 23, 32, 46), (177, 24, 32, 45), (209, 23, 33, 46), (242, 24, 31, 45)]
ZOM_UP = [(286, 23, 23, 46), (313, 23, 25, 46), (343, 23, 23, 46), (374, 23, 23, 46)]


def load_sheet(name):
    return Image.open(os.path.join(ASSETS, name)).convert("RGBA")


def norm_frames(sheet, rects, fs):
    """Crop each rect to a common box: feet aligned (bottom), body centered."""
    fw, fh = fs
    out = []
    for (x, y, w, h) in rects:
        f = sheet.crop((x, y, x + w, y + h))
        frame = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
        frame.paste(f, ((fw - w) // 2, fh - h))
        out.append(frame)
    return out


def morph(a, b):
    """Blend two keyframes: shared pixels average, lone pixels half-alpha."""
    out = Image.new("RGBA", a.size, (0, 0, 0, 0))
    pa, pb, po = a.load(), b.load(), out.load()
    for y in range(a.height):
        for x in range(a.width):
            r1, g1, b1, al = pa[x, y]
            r2, g2, b2, bl = pb[x, y]
            if al and bl:
                po[x, y] = ((r1 + r2) // 2, (g1 + g2) // 2, (b1 + b2) // 2, 255)
            elif al:
                po[x, y] = (r1, g1, b1, max(96, al // 2))
            elif bl:
                po[x, y] = (r2, g2, b2, max(96, bl // 2))
    return out


def expand(cyc):
    """4 keyframes -> 8 frames: k0 m01 k1 m12 k2 m23 k3 m30."""
    return [cyc[0], morph(cyc[0], cyc[1]), cyc[1], morph(cyc[1], cyc[2]),
            cyc[2], morph(cyc[2], cyc[3]), cyc[3], morph(cyc[3], cyc[0])]


def build(src_fn, rects_by_row, fs):
    sheet = load_sheet(src_fn)
    rows = []
    for rects in rects_by_row:
        cyc = norm_frames(sheet, rects, fs)
        rows.append(expand(cyc))
    fw, fh = fs
    out = Image.new("RGBA", (fw * 8, fh * len(rows)), (0, 0, 0, 0))
    for ri, row in enumerate(rows):
        for fi, frame in enumerate(row):
            out.paste(frame, (fi * fw, ri * fh))
    return out


def check(sheet_path):
    im = Image.open(sheet_path).convert("RGBA")
    px = im.load()
    w, h = im.size
    empty = 0
    for y in range(h):
        for x in range(w):
            if px[x, y][3] == 0:
                empty += 1
    return im.size, empty, (w * h - empty)  # size, empty px, inked px


for src, rows, fs, out in (
    ("zeke.png", [ZEKE_DOWN, ZEKE_LEFT, ZEKE_UP], (23, 38), "zeke_walk.png"),
    ("julie.png", [JULIE_DOWN, JULIE_LEFT, JULIE_UP, JULIE_RIGHT], (29, 38), "julie_walk.png"),
    ("zombie.png", [ZOM_DOWN, ZOM_RIGHT, ZOM_UP], (33, 48), "zombie_walk.png"),
):
    img = build(src, rows, fs)
    img.save(os.path.join(ASSETS, out))
    print(out, check(os.path.join(ASSETS, out)))
print("done")