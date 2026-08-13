import os
from PIL import Image

ASSETS = os.path.join("ZamnNative", "assets")
OUT = os.path.join("C:\\Users\\Felipe\\AppData\\Local\\Temp\\opencode", "sprites_improved")
os.makedirs(OUT, exist_ok=True)

def load(path, key_mode):
    img = Image.open(os.path.join(ASSETS, path)).convert("RGBA")
    w, h = img.size
    key = img.getpixel((0, 0))
    key_rgb = key[:3]
    data = list(img.getdata())
    if key_mode:
        for i in range(len(data)):
            r, g, b, a = data[i]
            if (r, g, b, a) == (key_rgb[0], key_rgb[1], key_rgb[2], 255):
                data[i] = (0, 0, 0, 0)
            elif key_mode == 2:
                if abs(r - 8) <= 26 and abs(g - 176) <= 26 and abs(b - 120) <= 26:
                    data[i] = (0, 0, 0, 0)
                elif abs(r - 8) <= 20 and abs(g - 112) <= 20 and abs(b - 80) <= 20:
                    data[i] = (0, 0, 0, 0)
    return data, w, h, key_rgb + (0,)  # transparent fill

def get(data, w, x, y):
    return data[y * w + x]

def frame_info(data, w, rect):
    x, y, rw, rh = rect
    minx, miny, maxx, maxy, n, sx = rw, rh, -1, -1, 0, 0
    for yy in range(rh):
        for xx in range(rw):
            if get(data, w, x + xx, y + yy)[3] > 40:
                if xx < minx: minx = xx
                if xx > maxx: maxx = xx
                if yy < miny: miny = yy
                if yy > maxy: maxy = yy
                n += 1
                sx += xx
    if n == 0:
        return None
    return {"minx": minx, "maxx": maxx, "miny": miny, "maxy": maxy,
            "n": n, "cx": sx / n, "cw": maxx - minx + 1}

def shift_frame(data, w, rect, dx, fill):
    x, y, rw, rh = rect
    if dx == 0:
        return
    content = {}
    for yy in range(rh):
        for xx in range(rw):
            c = get(data, w, x + xx, y + yy)
            if c[3] > 40:
                content[(xx, yy)] = c
    c0 = min(x, x + dx)
    c1 = max(x + rw, x + dx + rw)
    for yy in range(rh):
        for xx in range(c0, c1):
            data[(y + yy) * w + xx] = fill
    for (xx, yy), c in content.items():
        gx = x + xx + dx
        if 0 <= gx < w:
            data[(y + yy) * w + gx] = c

def recenter(data, w, h, master, cycle_idxs, fill, max_shift=2):
    rects = [master[i] for i in cycle_idxs]
    infos = [frame_info(data, w, r) for r in rects]
    us = [inf["cx"] - r[2] / 2.0 for inf, r in zip(infos, rects)]
    if max(us) - min(us) <= 0.75:
        return rects, [0] * len(rects)
    shifts = [max(-max_shift, min(max_shift, round(-u))) for u in us]
    cyc = {id(r): i for i, r in enumerate(rects)}
    order = sorted(range(len(rects)), key=lambda i: rects[i][0])
    for i in order:
        r = rects[i]
        s = shifts[i]
        t = -2 * (us[i] + s)
        base_pl, base_pr = max(-s, 0), max(s, 0)
        if t >= 0:
            pl = max(base_pl, base_pr + t)
            pr = pl - t
        else:
            pr = max(base_pr, base_pl - t)
            pl = pr + t
        y0, y1 = r[1], r[1] + r[3]
        nl = 0
        nr = w
        for j, m in enumerate(master):
            if m is r:
                continue
            if not (m[1] < y1 and y0 < m[1] + m[3]):
                continue
            if m[0] + m[2] <= r[0] and m[0] + m[2] > nl:
                nl = m[0] + m[2]
            if m[0] >= r[0] + r[2] and m[0] < nr:
                nr = m[0]
        room_l = r[0] - nl
        room_r = nr - (r[0] + r[2])
        pl = int(round(pl))
        pr = int(round(pr))
        pl = max(pl, 0, -s)
        pr = max(pr, 0, s)
        pr = min(pr, max(0, room_r))
        pl = min(pl, max(0, room_l))
        if s:
            shift_frame(data, w, r, s, fill)
        master[cycle_idxs[i]] = (r[0] - pl, r[1], r[2] + pl + pr, r[3])
    new_rects = [master[i] for i in cycle_idxs]
    for r, inf in zip(new_rects, infos):
        nf = frame_info(data, w, r)
        if nf is None or nf["n"] < inf["n"]:
            print("    WARN clip %s: n %d -> %d" % (r, inf["n"], nf["n"] if nf else 0))
    return new_rects, shifts

def cleanup_strays(data, w, h, rects, fill, max_rem_frac=0.06):
    total = 0
    for rect in rects:
        x, y, rw, rh = rect
        before = frame_info(data, w, rect)["n"]
        remove = []
        for yy in range(rh):
            for xx in range(rw):
                if get(data, w, x + xx, y + yy)[3] <= 40:
                    continue
                cnt = 0
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + xx + dx, y + yy + dy
                        if 0 <= nx < w and 0 <= ny < h and get(data, w, nx, ny)[3] > 40:
                            cnt += 1
                if cnt <= 1:
                    remove.append((xx, yy))
        if before > 0 and len(remove) > before * max_rem_frac:
            print("    WARN %s: %d of %d px would be removed - skipped" % (rect, len(remove), before))
            continue
        for xx, yy in remove:
            data[(y + yy) * w + (x + xx)] = fill
        total += len(remove)
    return total

def report_cycle(name, data, w, rects, label):
    print("  [%s] %s" % (name, label))
    us = []
    for i, r in enumerate(rects):
        inf = frame_info(data, w, r)
        u = inf["cx"] - r[2] / 2.0
        us.append(u)
        print("    f%d %s u=%+.1f n=%d" % (i, r, u, inf["n"]))
    print("    jitter spread: %.2f px" % (max(us) - min(us)))

def save(path, data, w, h):
    img = Image.new("RGBA", (w, h))
    img.putdata(data)
    img.save(os.path.join(OUT, path))

def check_collisions(rects_by_sheet):
    ok = True
    for sheet, rects in rects_by_sheet.items():
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                if not (a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]):
                    print("  COLLISION in %s: %s vs %s" % (sheet, a, b))
                    ok = False
    if ok:
        print("  no rect collisions")

all_new = {}
all_rects = {"zeke.png": [], "julie.png": [], "zombie.png": [], "victims.png": []}

# ---------------- ZEKE ----------------
data, w, h, kfill = load("zeke.png", 1)
zd = [(86, 5, 16, 36), (108, 4, 15, 37), (128, 4, 16, 37), (149, 4, 15, 37), (170, 4, 15, 37)]
zl = [(87, 44, 15, 37), (108, 44, 13, 37), (127, 44, 20, 37), (152, 44, 14, 37), (170, 45, 21, 36)]
zu = [(87, 86, 16, 35), (108, 85, 14, 36), (129, 86, 16, 35), (153, 85, 14, 36), (174, 86, 16, 35)]
print("=== ZEKE before ===")
for nm, c in [("DOWN", zd), ("LEFT", zl), ("UP", zu)]:
    report_cycle("zeke", data, w, c, nm)
st = cleanup_strays(data, w, h, zd + zl + zu, kfill)
print("ZEKE strays:", st)
master = zd + zl + zu
all_new["ZEKE_DOWN"], _ = recenter(data, w, h, master, range(0, 5), kfill)
all_new["ZEKE_LEFT"], _ = recenter(data, w, h, master, range(5, 10), kfill)
all_new["ZEKE_UP"], _ = recenter(data, w, h, master, range(10, 15), kfill)
print("=== ZEKE after ===")
for nm, c in [("DOWN", all_new["ZEKE_DOWN"]), ("LEFT", all_new["ZEKE_LEFT"]), ("UP", all_new["ZEKE_UP"])]:
    report_cycle("zeke", data, w, c, nm)
save("zeke.png", data, w, h)
all_rects["zeke.png"] += all_new["ZEKE_DOWN"] + all_new["ZEKE_LEFT"] + all_new["ZEKE_UP"]

# ---------------- JULIE ----------------
data, w, h, kfill = load("julie.png", 1)
jd = [(7, 4, 20, 38), (9, 52, 16, 38), (10, 102, 15, 38), (7, 154, 16, 38), (7, 205, 16, 38)]
jl = [(41, 5, 18, 37), (40, 55, 22, 36), (40, 103, 22, 36), (39, 153, 20, 36), (39, 206, 24, 35)]
ju = [(76, 5, 20, 37), (76, 53, 14, 37), (74, 101, 15, 37), (73, 152, 14, 37), (74, 204, 15, 37)]
jr = [(109, 6, 18, 37), (105, 54, 22, 36), (102, 103, 22, 36), (102, 154, 20, 36), (96, 205, 24, 35)]
print("=== JULIE before ===")
for nm, c in [("DOWN", jd), ("LEFT", jl), ("UP", ju), ("RIGHT", jr)]:
    report_cycle("julie", data, w, c, nm)
st = cleanup_strays(data, w, h, jd + jl + ju + jr, kfill)
print("JULIE strays:", st)
master = jd + jl + ju + jr
all_new["JULIE_DOWN"], _ = recenter(data, w, h, master, range(0, 5), kfill)
all_new["JULIE_LEFT"], _ = recenter(data, w, h, master, range(5, 10), kfill)
all_new["JULIE_UP"], _ = recenter(data, w, h, master, range(10, 15), kfill)
all_new["JULIE_RIGHT"], _ = recenter(data, w, h, master, range(15, 20), kfill)
print("=== JULIE after ===")
for nm, c in [("DOWN", all_new["JULIE_DOWN"]), ("LEFT", all_new["JULIE_LEFT"]),
              ("UP", all_new["JULIE_UP"]), ("RIGHT", all_new["JULIE_RIGHT"])]:
    report_cycle("julie", data, w, c, nm)
save("julie.png", data, w, h)
all_rects["julie.png"] += all_new["JULIE_DOWN"] + all_new["JULIE_LEFT"] + all_new["JULIE_UP"] + all_new["JULIE_RIGHT"]

# ---------------- ZOMBIE ----------------
data, w, h, kfill = load("zombie.png", 2)
mzd = [(8, 22, 27, 47), (41, 21, 27, 48), (74, 21, 27, 48), (108, 22, 27, 47)]
mzr = [(149, 23, 25, 46), (178, 24, 29, 45), (212, 23, 27, 46), (242, 24, 30, 45)]
mzu = [(286, 23, 22, 46), (315, 23, 22, 46), (344, 23, 22, 46), (375, 23, 22, 46)]
mzrise = [(11, 135, 12, 6), (30, 128, 24, 13), (63, 125, 32, 15), (148, 100, 32, 41), (189, 94, 28, 47)]
mzdie = [(43, 154, 4, 7), (48, 165, 34, 51), (61, 156, 7, 5)]
print("=== ZOMBIE before ===")
for nm, c in [("DOWN", mzd), ("RIGHT", mzr), ("UP", mzu)]:
    report_cycle("zomb", data, w, c, nm)
st = cleanup_strays(data, w, h, mzd + mzr + mzu + mzrise + mzdie, kfill)
print("ZOMBIE strays:", st)
master = mzd + mzr + mzu + mzrise + mzdie
all_new["ZOM_DOWN"], _ = recenter(data, w, h, master, range(0, 4), kfill, 3)
all_new["ZOM_RIGHT"], _ = recenter(data, w, h, master, range(4, 8), kfill, 3)
all_new["ZOM_UP"], _ = recenter(data, w, h, master, range(8, 12), kfill, 3)
print("=== ZOMBIE after ===")
for nm, c in [("DOWN", all_new["ZOM_DOWN"]), ("RIGHT", all_new["ZOM_RIGHT"]), ("UP", all_new["ZOM_UP"])]:
    report_cycle("zomb", data, w, c, nm)
save("zombie.png", data, w, h)
all_rects["zombie.png"] += all_new["ZOM_DOWN"] + all_new["ZOM_RIGHT"] + all_new["ZOM_UP"] + mzrise + mzdie

# ---------------- VICTIMS ----------------
data, w, h, kfill = load("victims.png", 1)
vdog = [(4, 56, 29, 27), (37, 54, 27, 29), (68, 52, 28, 31), (100, 54, 30, 29)]
vsol = [(4, 220, 32, 46), (40, 218, 33, 48), (77, 218, 31, 48)]
vcheer = [(40, 109, 44, 41), (184, 95, 44, 41), (280, 97, 44, 41), (376, 103, 44, 41)]
vkid = [(37, 384, 31, 29), (72, 379, 37, 34), (113, 373, 46, 40)]
vtour = [(7, 167, 41, 39), (59, 174, 41, 32)]
print("=== VICTIM before ===")
report_cycle("vic", data, w, vdog, "DOG")
report_cycle("vic", data, w, vsol, "SOLDIER")
st = cleanup_strays(data, w, h, vdog + vsol + vcheer + vkid + vtour, kfill)
print("VICTIMS strays:", st)
master = vdog + vsol + vcheer + vkid + vtour
all_new["VIC_DOG"], _ = recenter(data, w, h, master, range(0, 4), kfill, 3)
all_new["VIC_SOLDIER"], _ = recenter(data, w, h, master, range(4, 7), kfill, 3)
print("=== VICTIM after ===")
report_cycle("vic", data, w, all_new["VIC_DOG"], "DOG")
report_cycle("vic", data, w, all_new["VIC_SOLDIER"], "SOLDIER")
save("victims.png", data, w, h)
all_rects["victims.png"] += all_new["VIC_DOG"] + all_new["VIC_SOLDIER"] + vcheer + vkid + vtour

print()
print("=== COLLISIONS ===")
check_collisions(all_rects)
print("=== NEW RECTS ===")
for k in sorted(all_new):
    print("%s = %s" % (k, all_new[k]))
