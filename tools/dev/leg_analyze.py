import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")
zeke = image.load(os.path.join(base, "zeke.png")).convert_alpha()
print("flags:", zeke.get_flags(), "has alpha:", zeke.get_flags() & pygame.SRCALPHA)

def opaque(surf, x, y):
    c = surf.get_at((x, y))
    return c.a > 128 or (c.r + c.g + c.b) > 30

def analyze(name, rect):
    x, y, w, h = rect
    sub = zeke.subsurface((x, y, w, h))
    bottom = []
    for yy in range(int(h * 0.6), h):
        cols = [c for c in range(w) if opaque(sub, c, yy)]
        if cols:
            bottom.append((yy, min(cols), max(cols)))
    if not bottom:
        print(name, "no legs")
        return
    # count runs of opaque columns in each of the last 6 rows
    runs_info = []
    for yy, _, _ in bottom[-6:]:
        runs = 0
        in_run = False
        for c in range(w):
            if opaque(sub, c, yy):
                if not in_run:
                    runs += 1
                    in_run = True
            else:
                in_run = False
        runs_info.append(runs)
    rows = [f"y={y:2d} L={l:2d} R={r:2d}" for (y, l, r) in bottom[-3:]]
    print(f"{name}: runs(last6)={runs_info} | {rows}")
    # center of mass of foot pixels (last 4 rows)
    sx = sy = cnt = 0
    for yy in range(max(0, h - 4), h):
        for c in range(w):
            if opaque(sub, c, yy):
                sx += c; sy += yy; cnt += 1
    if cnt:
        print(f"   foot COM: ({sx/cnt:.1f},{sy/cnt:.1f}) of {w}x{h}")

F = {
    "left_f0": (87, 44, 15, 37), "left_f1": (108, 44, 13, 37),
    "left_f2": (70, 44, 13, 37), "left_f3": (152, 44, 14, 37), "left_f4": (125, 44, 15, 37),
}
for n, r in F.items():
    analyze(n, r)
print("--- down ---")
D = {"down_f0": (86, 5, 16, 36), "down_f1": (108, 4, 15, 37), "down_f2": (128, 4, 16, 37)}
for n, r in D.items():
    analyze(n, r)
