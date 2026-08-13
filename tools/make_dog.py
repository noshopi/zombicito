# REX generator: turns Zeke's walk sheets into a dog-headed hero (REX).
# Draws a pixel-art dog head (ears, muzzle, nose, eyes) over every frame,
# adds a tail to profile frames, then applies a detail pass (AO + rim light).
# Produces: rex_walk.png (23x38, DOWN y0 / LEFT y38 / UP y76) and rex.png
# (4-frame layout matching zeke.png rects).
import os
import shutil
from PIL import Image

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ZamnNative", "assets")
BAK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "asset_backup")

FUR = (198, 140, 92)
FURL = (238, 188, 128)
FURD = (142, 94, 54)
CREAM = (246, 226, 196)
DARK = (30, 24, 30)
WHITE = (255, 255, 255)
EAR_IN = (172, 122, 80)

HAIR = {(248, 176, 8), (160, 120, 0)}

ZEKE_DOWN = [(86, 5, 16, 36), (108, 4, 16, 37), (128, 4, 16, 37), (148, 4, 16, 37)]
ZEKE_LEFT = [(86, 44, 17, 37), (108, 44, 13, 37), (125, 44, 23, 37), (151, 44, 15, 37)]
ZEKE_UP = [(87, 86, 16, 35), (108, 85, 14, 36), (129, 86, 16, 35), (153, 85, 14, 36)]


def load(name):
    return Image.open(os.path.join(ASSETS, name)).convert("RGBA")


def save(img, name):
    img.save(os.path.join(ASSETS, name))
    print("wrote %s  %dx%d" % (name, img.size[0], img.size[1]))


def backup(name):
    src = os.path.join(ASSETS, name)
    if not os.path.exists(src):
        return
    os.makedirs(BAK, exist_ok=True)
    dst = os.path.join(BAK, name)
    if not os.path.exists(dst):
        shutil.copy2(src, dst)
        print("backed up %s" % name)


def hair_bbox(px, x0, y0, fw, fh):
    x1, y1 = x0 + fw, y0 + fh
    hx0, hy0, hx1, hy1 = x1, y1, x0, y0
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            r, g, b, a = px[xx, yy]
            if a > 40 and (r, g, b) in HAIR:
                hx0, hy0 = min(hx0, xx), min(hy0, yy)
                hx1, hy1 = max(hx1, xx), max(hy1, yy)
    if hx1 < hx0:
        return None
    return hx0, hy0, hx1, hy1


def clear(px, x0, y0, x1, y1):
    for yy in range(y0, y1 + 1):
        for xx in range(x0, x1 + 1):
            px[xx, yy] = (0, 0, 0, 0)


def put(px, x, y, c):
    px[x, y] = c


def draw_down(px, cx, y0):
    # ears (pointy triangles on top corners)
    for x, s in ((cx - 3, -1), (cx + 3, 1)):
        put(px, x, y0 - 2, FURD)
        put(px, x + s, y0 - 2, FURD)
        put(px, x, y0 - 1, FURD)
        put(px, x + s, y0 - 1, EAR_IN)
        put(px, x + s + s, y0 - 1, FURD)
        put(px, x, y0, EAR_IN)
    # head
    for yy in range(y0, y0 + 8):
        for xx in range(cx - 4, cx + 5):
            put(px, xx, yy, FURL if yy == y0 else FUR)
    for xx in range(cx - 4, cx + 5):
        put(px, xx, y0 + 8, FURD)
    # eyes
    put(px, cx - 2, y0 + 4, DARK)
    put(px, cx + 2, y0 + 4, DARK)
    put(px, cx - 3, y0 + 3, FURL)
    put(px, cx + 3, y0 + 3, FURL)
    # muzzle
    for yy in range(y0 + 5, y0 + 10):
        for xx in range(cx - 3, cx + 4):
            put(px, xx, yy, CREAM if yy < y0 + 9 else FUR)
    put(px, cx, y0 + 5, DARK)          # nose
    put(px, cx - 1, y0 + 6, DARK)      # nostril-ish
    put(px, cx + 1, y0 + 6, DARK)
    for xx in range(cx - 3, cx + 4):   # mouth
        put(px, xx, y0 + 8, DARK)
    put(px, cx - 1, y0 + 7, DARK)      # mouth middle


def draw_left(px, cx, y0, face_left):
    s = -1 if face_left else 1
    # ear on the back-top corner
    for yy in range(3):
        for xx in range(2):
            put(px, cx + 3 * s + (xx * s), y0 - 2 + yy, FURD if xx == 1 else EAR_IN)
    # head
    for yy in range(y0, y0 + 8):
        for xx in range(cx - 4, cx + 5):
            put(px, xx, yy, FURL if yy == y0 else FUR)
    for xx in range(cx - 4, cx + 5):
        put(px, xx, y0 + 8, FURD)
    # eye near the face side
    put(px, cx + 3 * s, y0 + 3, DARK)
    put(px, cx + 4 * s, y0 + 2, FURL)
    # snout protruding on the face side
    for yy in range(y0 + 4, y0 + 9):
        for xx in range(cx + 4 * s, cx + 4):
            put(px, xx, yy, CREAM if yy < y0 + 8 else FUR)
    put(px, cx + 4 * s, y0 + 4, DARK)     # nose at the tip
    for xx in range(cx + 3 * s, cx + 4):  # mouth
        put(px, xx, y0 + 7, DARK)


def draw_up(px, cx, y0):
    # two ears on top corners
    for x, s in ((cx - 3, -1), (cx + 3, 1)):
        put(px, x, y0 - 2, FURD)
        put(px, x + s, y0 - 2, FURD)
        put(px, x, y0 - 1, FURD)
        put(px, x + s, y0 - 1, EAR_IN)
        put(px, x + s + s, y0 - 1, FURD)
        put(px, x, y0, EAR_IN)
    # head (no face visible)
    for yy in range(y0, y0 + 10):
        for xx in range(cx - 4, cx + 5):
            put(px, xx, yy, FURL if yy == y0 else FUR)
    for xx in range(cx - 4, cx + 5):
        put(px, xx, y0 + 10, FURD)


def dog_head(img, fw, fh, x0, y0, direction):
    px = img.load()
    bb = hair_bbox(px, x0, y0, fw, fh)
    if bb is None:
        return
    hx0, hy0, hx1, hy1 = bb
    cx = (hx0 + hx1) // 2
    # clear head box (generous: covers hair + face)
    top = max(0, hy0 - 2)
    bot = min(y0 + fh - 1, hy1 + 10)
    lft = max(x0, hx0 - 2 if direction != "left" else hx0 - 5)
    rgt = min(x0 + fw - 1, hx1 + 2)
    clear(px, lft, top, rgt, bot)
    if direction == "down":
        draw_down(px, cx, hy0)
    elif direction == "left":
        draw_left(px, cx, hy0, True)
    elif direction == "up":
        draw_up(px, cx, hy0)
    return cx, hy0


def add_tail_left(img, x0, y0, fw, fh):
    px = img.load()
    # find the back edge of the torso, then curl a tail up from the hip
    bx = x0
    for yy in range(y0 + 16, y0 + 26):
        for xx in range(x0 + fw - 1, x0 - 1, -1):
            if px[xx, yy][3] > 128:
                bx = max(bx, xx)
                break
    base = y0 + 19
    put(px, bx + 1, base + 1, FURD)
    put(px, bx, base + 2, FURD)
    put(px, bx + 1, base, FUR)
    put(px, bx, base + 1, FUR)
    put(px, bx + 1, base - 1, FURL)
    put(px, bx, base, FURL)


def detail_pass(img):
    px = img.load()
    out = img.copy()
    po = out.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < 128:
                continue
            dark = 0
            for dx, dy in ((0, 1), (1, 0), (1, 1), (0, 2)):
                nx, ny = x + dx, y + dy
                if nx < w and ny < h and px[nx, ny][3] < 40:
                    dark += 1
            lit = 0
            for dx, dy in ((-1, 0), (0, -1), (-1, -1)):
                nx, ny = x + dx, y + dy
                if nx >= 0 and ny >= 0 and px[nx, ny][3] < 40:
                    lit += 1
            if dark >= 2:
                f = 0.72 + 0.06 * dark
                po[x, y] = (int(r * f), int(g * f), int(b * f), a)
            elif lit >= 2:
                f = 1.12 + 0.05 * lit
                po[x, y] = (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)), a)
    return out


def build_walk():
    z = load("zeke_walk.png")
    w, h = z.size
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fw, fh = 23, 38
    for row in range(3):
        dirs = ("down", "left", "up")
        for f in range(8):
            x0, y0 = f * fw, row * fh
            fr = z.crop((x0, y0, x0 + fw, y0 + fh)).copy()
            dog_head(fr, fw, fh, 0, 0, dirs[row])
            if dirs[row] == "left":
                add_tail_left(fr, 0, 0, fw, fh)
            out.paste(fr, (x0, y0))
    return detail_pass(out)


def build_4f():
    z = load("zeke.png")
    out = z.copy()
    rects = {"down": ZEKE_DOWN, "left": ZEKE_LEFT, "up": ZEKE_UP}
    for d, rl in rects.items():
        for (x, y, fw, fh) in rl:
            img = z.crop((x, y, x + fw, y + fh)).copy()
            dog_head(img, fw, fh, 0, 0, d)
            if d == "left":
                add_tail_left(img, 0, 0, fw, fh)
            out.paste(img, (x, y))
    return detail_pass(out)


def enhance_existing():
    for name in ("zeke_walk.png", "julie_walk.png", "zombie_walk.png"):
        backup(name)
        img = load(name)
        save(detail_pass(img), name)


if __name__ == "__main__":
    backup("zeke_walk.png")
    backup("julie_walk.png")
    backup("zombie_walk.png")
    save(build_walk(), "rex_walk.png")
    save(build_4f(), "rex.png")
    enhance_existing()
    print("done")
