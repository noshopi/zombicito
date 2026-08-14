# Level 1 decoration pass: adds flat detail to the original day map
# (flowers, grass blades, pool grates + sun glints, floating leaves,
#  hedges, pavement cracks). Everything stays walkable: walk1_deco.bin
# is a copy of the original walk grid.
import random
from collections import Counter
from PIL import Image

SRC = "ZamnNative/assets/level_big.png"
WALK = "ZamnNative/assets/walk_big.bin"
OUT_IMG = "ZamnNative/assets/level1_deco.png"
OUT_WALK = "ZamnNative/assets/walk1_deco.bin"

img = Image.open(SRC).convert("RGB")
W, H = img.size
TS = 16
TW, TH = W // TS, H // TS
px = img.load()
walk = bytearray(open(WALK, "rb").read())

CLS = {
    "GRASS_L": [(8, 112, 80), (16, 88, 72), (24, 64, 64)],
    "GRASS_D": [(0, 72, 40), (8, 176, 64), (0, 56, 0)],
    "GRASS_X": [(104, 248, 64), (8, 176, 120)],
    "HOUSE": [(224, 96, 96), (248, 160, 152)],
    "WATER": [(48, 88, 216)],
    "DARK": [(0, 0, 0)],
    "CEM": [(248, 248, 248)],
    "PAVE": [(160, 160, 160), (104, 104, 104), (208, 192, 128)],
    "BRICK": [(120, 64, 32), (80, 32, 16), (64, 64, 64), (16, 24, 16)],
}

GROUND = ("CEM", "PAVE", "BRICK")

def tile_cls(tx, ty):
    cnt = Counter()
    for y in range(ty * TS, (ty + 1) * TS):
        for x in range(tx * TS, (tx + 1) * TS):
            r, g, b = px[x, y]
            best, bd = "GRASS_L", 99
            for name, cols in CLS.items():
                for cc in cols:
                    d = abs(r - cc[0]) + abs(g - cc[1]) + abs(b - cc[2])
                    if d < bd:
                        best, bd = name, d
            cnt[best] += 1
    return cnt.most_common(1)[0][0]

def nh(tx, ty, seed):
    return (tx * 31 + ty * 57 + seed * 131) & 0xFFFF

def in_grid(tx, ty):
    return 0 <= tx < TW and 0 <= ty < TH

def blend(x, y, c, a):
    r0, g0, b0 = op[x, y]
    op[x, y] = (int(r0 * (1 - a) + c[0] * a),
                int(g0 * (1 - a) + c[1] * a),
                int(b0 * (1 - a) + c[2] * a))

# object tiles (pixel coords -> tile), keep decoration off them
VSPOTS_DAY = [(520, 800), (1100, 790), (1520, 900), (1980, 560), (1670, 450),
              (930, 1050), (610, 1110), (1350, 330), (240, 520), (1800, 320),
              (2100, 340), (1830, 1070), (480, 310), (2030, 780), (320, 1070), (360, 60)]
TSPAWN_DAY = [(340, 600), (364, 600), (340, 624),
              (820, 240), (844, 240), (820, 264),
              (1990, 230), (2014, 230), (1990, 254),
              (2080, 850), (2104, 850), (2080, 874)]
MEDKITS_DAY = [(170, 420), (1300, 480), (900, 640), (1600, 900),
               (700, 1210), (1500, 1210), (1450, 210), (2100, 1150)]
EXCL = []
for pts in (VSPOTS_DAY, TSPAWN_DAY, MEDKITS_DAY):
    for (ax, ay) in pts:
        EXCL.append((ax // TS, ay // TS))
EXCL.append((480 // TS, 78 // TS))  # exit door

def near_excl(tx, ty):
    for (ex, ey) in EXCL:
        if abs(tx - ex) <= 2 and abs(ty - ey) <= 2:
            return True
    return False

out = img.copy()
op = out.load()
wout = bytearray(walk)

POST = (215, 225, 240)
SUN = (255, 248, 220)

for ty in range(TH):
    for tx in range(TW):
        ch = tile_cls(tx, ty)
        bx, by = tx * TS, ty * TS
        if ch == "WATER":
            # pool grate + warm sun glints
            for yy in (3, 7, 11):
                for xx in range(TS):
                    blend(bx + xx, by + yy, (110, 205, 240), 0.55)
            gx = 5 + nh(tx, ty, 1) % 6
            gy = 5 + nh(tx, ty, 2) % 6
            for dy in range(3):
                for dx in range(2):
                    op[bx + gx + dx - 1, by + gy + dy - 1] = SUN
            # floating leaves
            if nh(tx, ty, 5) % 17 == 0:
                lx = 3 + nh(tx, ty, 6) % 10
                ly = 3 + nh(tx, ty, 7) % 10
                op[bx + lx, by + ly] = (210, 90, 40)
                op[bx + lx + 1, by + ly] = (170, 60, 30)
        elif ch in ("GRASS_L", "GRASS_X") and walk[ty * TW + tx] and not near_excl(tx, ty):
            # grass blades
            if nh(tx, ty, 8) % 11 == 0:
                gx = 2 + nh(tx, ty, 9) % 12
                gy = 2 + nh(tx, ty, 10) % 12
                op[bx + gx, by + gy] = (110, 200, 110)
                op[bx + gx, by + gy + 1] = (130, 215, 120)
            # wildflowers
            if nh(tx, ty, 11) % 29 == 0:
                c = ((255, 250, 220), (255, 240, 150), (200, 220, 255))[nh(tx, ty, 12) % 3]
                fx = 2 + nh(tx, ty, 13) % 12
                fy = 2 + nh(tx, ty, 14) % 12
                op[bx + fx, by + fy] = c
                op[bx + fx + 1, by + fy] = c
                op[bx + fx, by + fy + 1] = c
            # hedge next to pavement
            if nh(tx, ty, 15) % 53 == 0:
                has_cem = any(in_grid(tx + dx, ty + dy) and tile_cls(tx + dx, ty + dy) in GROUND
                              for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)))
                if has_cem:
                    hx = 4 + nh(tx, ty, 16) % 6
                    hy = 4 + nh(tx, ty, 17) % 6
                    for yy in range(4):
                        for xx in range(6):
                            op[bx + hx + xx, by + hy + yy] = (48, 132, 60)
                    op[bx + hx + 2, by + hy] = (70, 170, 84)
                    op[bx + hx + 4, by + hy + 2] = (66, 158, 78)
        elif ch in GROUND:
            if not walk[ty * TW + tx]:
                # plazas and pool borders (not traversed): layout detail
                if ch == "BRICK":
                    # cracks over paved plazas
                    if nh(tx, ty, 18) % 29 == 0:
                        cx = 4 + nh(tx, ty, 19) % 8
                        cy = 4 + nh(tx, ty, 20) % 8
                        for k in range(3):
                            op[bx + cx + k, by + cy + (k % 2)] = (95, 95, 100)
            else:
                # pavement cracks + sun sparkles
                if nh(tx, ty, 18) % 41 == 0:
                    cx = 4 + nh(tx, ty, 19) % 8
                    cy = 4 + nh(tx, ty, 20) % 8
                    for k in range(3):
                        op[bx + cx + k, by + cy + (k % 2)] = (95, 95, 100)
                if nh(tx, ty, 21) % 103 == 0:
                    cx, cy = bx + 8, by + 8
                    for dx, dy in ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)):
                        op[cx + dx, cy + dy] = SUN
            # white posts on inner pool border
            for ddx, ddy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if in_grid(tx + ddx, ty + ddy) and tile_cls(tx + ddx, ty + ddy) == "WATER":
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

out.save(OUT_IMG)
open(OUT_WALK, "wb").write(wout)
print("saved", OUT_IMG, out.size, "walk ones:", sum(wout), "/", len(wout))

# sanity: nothing added inside exclusion zones, nothing became non-walkable
bad = 0
for ty in range(TH):
    for tx in range(TW):
        if near_excl(tx, ty) and walk[ty * TW + tx]:
            pass
        if not walk[ty * TW + tx]:
            bad += 1
print("non-walkable tiles:", bad, "(must equal original)")
print("done")
