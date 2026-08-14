# Level 2 generator: recomposed layout + modern night palette.
# Reuses original 16px tiles from level_big.png (so the style matches),
# reorders them into a NEW layout and applies a night palette.
import sys
from PIL import Image
from collections import Counter

SRC = "ZamnNative/assets/level_big.png"
WALK = "ZamnNative/assets/walk_big.bin"
OUT_IMG = "ZamnNative/assets/level2_big.png"
OUT_WALK = "ZamnNative/assets/walk2_big.bin"

img = Image.open(SRC).convert("RGB")
W, H = img.size
TS = 16
TW, TH = W // TS, H // TS
px = img.load()
walk = bytearray(open(WALK, "rb").read())
assert len(walk) == TW * TH, len(walk)

# ---------------- tile classification (same buckets as analyzer) ----------------
CLS = {
    "GRASS_L": [(8, 112, 80), (16, 88, 72), (24, 64, 64)],
    "GRASS_D": [(0, 72, 40), (8, 176, 64), (0, 56, 0)],
    "GRASS_X": [(104, 248, 64), (8, 176, 120)],
    "HOUSE": [(224, 96, 96), (248, 160, 152)],
    "WATER": [(48, 88, 216)],
    "DARK": [(0, 0, 0)],
    "CEM": [(248, 248, 248)],
}
CLS_ORDER = list(CLS)

def tile_cls(tx, ty):
    cnt = Counter()
    for y in range(ty * TS, (ty + 1) * TS):
        for x in range(tx * TS, (tx + 1) * TS):
            r, g, b = px[x, y]
            best, bd = None, 99
            for name, cols in CLS.items():
                for cc in cols:
                    d = abs(r - cc[0]) + abs(g - cc[1]) + abs(b - cc[2])
                    if d < bd:
                        best, bd = name, d
            cnt[best] += 1
    return cnt.most_common(1)[0][0]

# find best source tile per class: highest pure fraction
SRC_CNT = {}
for ty in range(TH):
    for tx in range(TW):
        c = tile_cls(tx, ty)
        if c not in SRC_CNT:
            SRC_CNT[c] = []
        SRC_CNT[c].append((tx, ty))
SRC_TILE = {}
SRC_FRAC = {}
for ty in range(TH):
    for tx in range(TW):
        cnt = Counter()
        for y in range(ty * TS, (ty + 1) * TS):
            for x in range(tx * TS, (tx + 1) * TS):
                r, g, b = px[x, y]
                best, bd = None, 99
                for name, cols in CLS.items():
                    for cc in cols:
                        d = abs(r - cc[0]) + abs(g - cc[1]) + abs(b - cc[2])
                        if d < bd:
                            best, bd = name, d
                cnt[best] += 1
        c = cnt.most_common(1)[0][0]
        f = cnt[c] / 256.0
        if c not in SRC_FRAC or f > SRC_FRAC[c]:
            SRC_FRAC[c] = f
            SRC_TILE[c] = (tx, ty)
print("source tiles:", SRC_TILE, SRC_FRAC)

# ---------------- layout (132x78, new arrangement) ----------------
GRID = [["."] * TW for _ in range(TH)]

def paint(x0, y0, x1, y1, ch):
    for y in range(max(0, y0), min(TH, y1 + 1)):
        for x in range(max(0, x0), min(TW, x1 + 1)):
            GRID[y][x] = ch

def house(x0, y0, w, h):
    paint(x0, y0, x0 + w - 1, y0 + h - 1, "R")
    paint(x0 + 1, y0 + 1, x0 + w - 2, y0 + h - 2, "#")
    paint(x0 + w // 2 - 1, y0 + h - 1, x0 + w // 2, y0 + h - 1, "o")

def pool(x0, y0, w, h):
    paint(x0, y0, x0 + w - 1, y0 + h - 1, "o")
    paint(x0 + 1, y0 + 1, x0 + w - 2, y0 + h - 2, "~")

def trees(x0, y0, x1, y1):
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            GRID[y][x] = "#" if (x + y) % 5 != 0 else ";"

# plaza norte (puerta de salida en tile 30,4..5, siempre caminable delante)
paint(28, 4, 36, 14, "o")
paint(37, 14, 62, 14, "o")
# avenida vertical central
paint(63, 0, 66, 77, "o")
# avenida horizontal central
paint(0, 39, 131, 41, "o")
# cuadra NO
house(6, 17, 20, 14)
paint(6, 31, 25, 31, "o")
pool(30, 18, 16, 11)
trees(50, 17, 61, 22)
paint(6, 33, 25, 38, ",")
paint(30, 33, 61, 38, ",")
# cuadra NE
house(70, 17, 20, 14)
paint(70, 31, 89, 31, "o")
pool(94, 18, 16, 11)
trees(114, 17, 127, 22)
paint(70, 33, 89, 38, ",")
paint(94, 33, 127, 38, ",")
# cuadra SO
house(6, 46, 20, 14)
paint(6, 60, 25, 60, "o")
trees(30, 46, 61, 70)
pool(48, 56, 7, 7)
paint(6, 62, 25, 66, ",")
# cuadra SE
house(70, 46, 20, 14)
paint(70, 60, 89, 60, "o")
pool(100, 50, 22, 18)
trees(94, 70, 127, 76)
paint(70, 62, 96, 66, ",")
# parque central
paint(68, 43, 125, 71, ";")
trees(70, 45, 80, 52)
pool(86, 54, 7, 7)
trees(94, 58, 108, 64)
paint(112, 66, 122, 71, ";")

# ---------------- build image: source tile + night palette ----------------
# palette mapping (original color -> night target)
PALETTE = {
    (8, 112, 80): (10, 84, 70), (16, 88, 72): (8, 70, 58), (24, 64, 64): (7, 52, 46),
    (0, 72, 40): (5, 56, 40), (8, 176, 64): (32, 128, 66), (0, 56, 0): (4, 38, 28),
    (104, 248, 64): (88, 198, 78), (8, 176, 120): (30, 122, 88),
    (224, 96, 96): (208, 86, 126), (248, 160, 152): (222, 128, 140), (168, 88, 96): (182, 74, 106),
    (48, 88, 216): (38, 140, 188),
    (0, 0, 0): (8, 18, 20),
    (248, 248, 248): (140, 152, 168),
    (248, 176, 0): (255, 214, 80),
    (208, 192, 128): (132, 124, 106), (216, 192, 192): (170, 142, 152),
    (16, 248, 160): (54, 196, 106), (16, 48, 88): (22, 56, 104),
    (152, 104, 152): (136, 84, 158), (120, 64, 32): (88, 56, 40),
    (144, 96, 48): (108, 74, 44), (104, 104, 104): (64, 70, 82),
    (160, 160, 160): (110, 118, 132), (64, 64, 64): (46, 50, 56),
    (80, 32, 16): (66, 38, 28), (144, 24, 16): (140, 34, 38),
    (128, 248, 200): (78, 190, 152), (104, 80, 80): (102, 62, 68),
    (16, 24, 16): (8, 24, 18),
}

# color -> target lookup table built from unique colors in source
uniq = set()
for y in range(H):
    for x in range(W):
        uniq.add(px[x, y])
print("unique colors:", len(uniq))

def closest(p, table):
    best, bd = None, 1 << 30
    for o in table:
        d = abs(p[0] - o[0]) + abs(p[1] - o[1]) + abs(p[2] - o[2])
        if d < bd:
            best, bd = o, d
    return best

LUT = {}
for c in uniq:
    o = closest(c, list(PALETTE))
    if o is None:
        LUT[c] = c
    elif o == (248, 176, 0):
        LUT[c] = PALETTE[o]
    elif o in ((0, 0, 0), (248, 248, 248)):
        LUT[c] = PALETTE[o]
    else:
        t = PALETTE[o]
        LUT[c] = (int(c[0] * 0.28 + t[0] * 0.72),
                  int(c[1] * 0.28 + t[1] * 0.72),
                  int(c[2] * 0.28 + t[2] * 0.72))
print("lut size:", len(LUT))

out = Image.new("RGB", (W, H))
op = out.load()
wout = bytearray(TW * TH)
CEM_BASE = (138, 150, 166)
for ty in range(TH):
    for tx in range(TW):
        ch = GRID[ty][tx]
        cls = {".": "GRASS_L", ",": "GRASS_D", ";": "GRASS_X",
               "R": "HOUSE", "o": "CEM", "~": "WATER", "#": "DARK"}[ch]
        sx, sy = SRC_TILE[cls]
        wout[ty * TW + tx] = 1 if ch in ".,;o" else 0
        if cls == "CEM":
            # procedural night pavement (original cement is never a pure tile)
            for yy in range(TS):
                for xx in range(TS):
                    v = ((xx * 7 + yy * 13 + tx * 3 + ty * 5) % 9) - 4
                    speck = 18 if (xx * 3 + yy * 11 + tx + ty) % 37 == 0 else 0
                    op[tx * TS + xx, ty * TS + yy] = (
                        max(0, CEM_BASE[0] + v - speck),
                        max(0, CEM_BASE[1] + v - speck),
                        max(0, CEM_BASE[2] + v - speck))
            continue
        for yy in range(TS):
            for xx in range(TS):
                op[tx * TS + xx, ty * TS + yy] = LUT[px[sx * TS + xx, sy * TS + yy]]

# ---------------- decoration pass (flat detail, all walkable) ----------------
def nh(tx, ty, seed):
    return (tx * 31 + ty * 57 + seed * 131) & 0xFFFF

def in_grid(tx, ty):
    return 0 <= tx < TW and 0 <= ty < TH

def blend(x, y, c, a):
    r0, g0, b0 = op[x, y]
    op[x, y] = (int(r0 * (1 - a) + c[0] * a),
                int(g0 * (1 - a) + c[1] * a),
                int(b0 * (1 - a) + c[2] * a))

NEON = [(255, 70, 200), (80, 220, 255), (255, 230, 120)]
MOON = (215, 245, 255)
POST = (215, 225, 240)

for ty in range(TH):
    for tx in range(TW):
        ch = GRID[ty][tx]
        bx, by = tx * TS, ty * TS
        if ch == "~":
            # pool lane lines + a glint of moonlight in every pool
            for yy in (3, 7, 11):
                for xx in range(TS):
                    blend(bx + xx, by + yy, (110, 205, 240), 0.55)
            gx = 5 + nh(tx, ty, 1) % 6
            gy = 5 + nh(tx, ty, 2) % 6
            for dy in range(3):
                for dx in range(2):
                    op[bx + gx + dx - 1, by + gy + dy - 1] = MOON
        elif ch in ",;":
            # neon flowers scattered over lawns
            if nh(tx, ty, 3) % 23 == 0:
                c = NEON[nh(tx, ty, 8) % 3]
                for k in range(2):
                    fx = 2 + nh(tx, ty, 4 + k) % 12
                    fy = 2 + nh(tx, ty, 6 + k) % 12
                    op[bx + fx, by + fy] = c
                    op[bx + fx + 1, by + fy] = c
                    op[bx + fx, by + fy + 1] = c
        elif ch == "o":
            # wet pavement glints
            if nh(tx, ty, 10) % 97 == 0:
                cx, cy = bx + 8, by + 8
                c = (200, 215, 235)
                op[cx, cy] = c
                op[cx - 1, cy] = c
                op[cx + 1, cy] = c
                op[cx, cy - 1] = c
                op[cx, cy + 1] = c
            # white posts on the inner edge of pool borders
            for ddx, ddy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if in_grid(tx + ddx, ty + ddy) and GRID[ty + ddy][tx + ddx] == "~":
                    if ddy == 1:
                        for xx in (1, 5, 9, 13):
                            op[bx + xx, by + 14] = POST
                            op[bx + xx, by + 15] = POST
                    elif ddy == -1:
                        for xx in (1, 5, 9, 13):
                            op[bx + xx, by] = POST
                            op[bx + xx, by + 1] = POST
                    elif ddx == 1:
                        for yy in (1, 5, 9, 13):
                            op[bx + 14, by + yy] = POST
                            op[bx + 15, by + yy] = POST
                    else:
                        for yy in (1, 5, 9, 13):
                            op[bx, by + yy] = POST
                            op[bx + 1, by + yy] = POST

# street lamps along the avenues (light halos over pavement)
LAMP = (255, 224, 120)
LAMP_DIM = (255, 190, 100)
LAMP_POST = (70, 78, 92)
LAMP_TILES = [(64, 8), (64, 16), (64, 24), (64, 32), (64, 48), (64, 56), (64, 64), (64, 72),
              (10, 40), (18, 40), (26, 40), (34, 40), (42, 40), (50, 40), (58, 40),
              (72, 40), (80, 40), (88, 40), (96, 40), (104, 40), (112, 40), (120, 40), (128, 40),
              (30, 8), (33, 8)]
for (lx, ly) in LAMP_TILES:
    if not (in_grid(lx, ly) and GRID[ly][lx] == "o"):
        continue
    lpx = lx * TS + 7
    lpy = ly * TS + 3
    # glow, layered
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            d2 = dx * dx + dy * dy
            a = 0.42 if d2 <= 4 else (0.22 if d2 <= 10 else (0.10 if d2 <= 18 else 0))
            if a:
                blend(lpx + dx, lpy + dy, LAMP_DIM, a)
    # lantern
    for yy in range(3):
        for xx in range(2):
            op[lpx + xx, lpy + yy] = LAMP
    # post
    for yy in range(5, 16):
        op[lpx + 1, lpy + yy] = LAMP_POST

# benches on the north plaza + swings on the central lawn
BENCH = (150, 110, 60)
BENCH_D = (80, 58, 34)
for (btx, bty) in ((30, 12), (33, 12)):
    if GRID[bty][btx] != "o":
        continue
    bx, by = btx * TS, bty * TS
    for yy in range(5):
        for xx in range(14):
            op[bx + 1 + xx, by + 6 + yy] = BENCH
    for xx in (0, 13):
        op[bx + 1 + xx, by + 6] = BENCH_D
        op[bx + 1 + xx, by + 10] = BENCH_D
SWING = (190, 90, 80)
SWING_S = (140, 60, 60)
for (stx, sty) in ((74, 55), (108, 50)):
    if GRID[sty][stx] != ";":
        continue
    bx, by = stx * TS, sty * TS
    for xx in range(10):
        op[bx + 3 + xx, by + 2] = SWING
        op[bx + 3 + xx, by + 3] = SWING
    for yy in range(4, 11):
        op[bx + 3, by + yy] = SWING
        op[bx + 12, by + yy] = SWING
    for xx in range(3):
        op[bx + 6 + xx, by + 11] = SWING_S
        op[bx + 6 + xx, by + 12] = SWING_S

out.save(OUT_IMG)
open(OUT_WALK, "wb").write(wout)
print("saved", OUT_IMG, out.size, "walk ones:", sum(wout), "/", len(wout))

for (tx, ty) in [(12, 22), (13, 22), (12, 23), (30, 5), (10, 33)]:
    ch = GRID[ty][tx]
    print("DBG tile(%d,%d) layout=%s walk=%d px=%s" % (tx, ty, ch, wout[ty * TW + tx], op[tx * TS + 8, ty * TS + 8]))

# sanity: check object tiles are walkable, print layout compact
OBJ = {
    "door": [(30, 5)],
    "vspots": [(10, 33), (52, 33), (94, 33), (118, 33), (30, 33), (58, 30), (94, 30), (126, 30),
               (12, 66), (46, 72), (84, 66), (120, 44), (26, 52), (84, 52), (82, 52), (58, 40)],
    "tspawn": [(18, 36), (28, 38), (16, 38), (104, 36), (112, 38), (96, 38),
               (18, 64), (28, 62), (16, 62), (88, 62), (92, 64), (86, 66)],
    "medkits": [(40, 14), (92, 14), (20, 40), (112, 40), (30, 30), (92, 26), (26, 56), (112, 56)],
}
for name, pts in OBJ.items():
    for i, (tx, ty) in enumerate(pts):
        if not wout[ty * TW + tx]:
            print("NON-WALKABLE %s[%d] (%d,%d) layout=%s" % (name, i, tx, ty, GRID[ty][tx]))
print("done")
