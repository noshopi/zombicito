import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")
zeke = image.load(os.path.join(base, "zeke.png")).convert_alpha()

def opaque(surf, x, y):
    c = surf.get_at((x, y))
    return c.a > 128

def profile(name, rect):
    x, y, w, h = rect
    sub = zeke.subsurface((x, y, w, h))
    # torso zone: rows 18%-55%
    xs, cnt = 0, 0
    min_x, max_x = 99, -1
    for yy in range(int(h * 0.18), int(h * 0.55)):
        for c in range(w):
            if opaque(sub, c, yy):
                xs += c; cnt += 1
                min_x = min(min_x, c); max_x = max(max_x, c)
    cx = xs / cnt if cnt else 0
    # arm/leg zone rows 55%-85% COM too
    xs2, cnt2 = 0, 0
    for yy in range(int(h * 0.55), int(h * 0.85)):
        for c in range(w):
            if opaque(sub, c, yy):
                xs2 += c; cnt2 += 1
    cx2 = xs2 / cnt2 if cnt2 else 0
    # head zone top 18%
    xs3, cnt3 = 0, 0
    for yy in range(0, int(h * 0.18)):
        for c in range(w):
            if opaque(sub, c, yy):
                xs3 += c; cnt3 += 1
    cx3 = xs3 / cnt3 if cnt3 else 0
    print(f"{name}: w={w} headCOM={cx3:5.2f} torsoCOM={cx:5.2f} (min{min_x} max{max_x}) limbCOM={cx2:5.2f}  "
          f"center={(w-1)/2:5.2f}  lean={(cx - (w-1)/2):+.2f}")

F = {
    "left_f0": (87, 44, 15, 37), "left_f1": (108, 44, 13, 37),
    "left_f2": (70, 44, 13, 37), "left_f3": (152, 44, 14, 37), "left_f4": (125, 44, 15, 37),
}
print("=== LEFT-facing frames (forward = smaller x) ===")
for n, r in F.items():
    profile(n, r)
