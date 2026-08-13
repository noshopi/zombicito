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

def thigh_runs(name, rect):
    x, y, w, h = rect
    sub = zeke.subsurface((x, y, w, h))
    print(f"--- {name} ({w}x{h}) ---")
    for yy in range(int(h * 0.45), min(h, int(h * 0.9))):
        runs = []
        in_run = False
        for c in range(w):
            if opaque(sub, c, yy):
                if not in_run:
                    runs.append([c, c]); in_run = True
                else:
                    runs[-1][1] = c
            else:
                in_run = False
        if len(runs) >= 2:
            print(f"  y={yy:2d}: {runs}")

F = {
    "left_f0": (87, 44, 15, 37), "left_f1": (108, 44, 13, 37),
    "left_f2": (70, 44, 13, 37), "left_f3": (152, 44, 14, 37), "left_f4": (125, 44, 15, 37),
}
for n, r in F.items():
    thigh_runs(n, r)
