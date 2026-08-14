import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")
zeke = image.load(os.path.join(base, "zeke.png")).convert_alpha()

def keyed():
    s = zeke.copy()
    key = s.get_at((0, 0))
    px = pygame.PixelArray(s)
    px.replace((key.r, key.g, key.b, 255), (0, 0, 0, 0))
    del px
    return s

spr = keyed()

def opaque(surf, x, y):
    return surf.get_at((x, y)).a > 128

def ascii_frame(rect):
    x, y, w, h = rect
    sub = spr.subsurface((x, y, w, h))
    for yy in range(h):
        row = "".join("#" if opaque(sub, c, yy) else ("+" if sub.get_at((c, yy)).a > 16 else ".") for c in range(w))
        print(row)

F = {
    "left_f0": (87, 44, 15, 37), "left_f1": (108, 44, 13, 37),
    "left_f2": (70, 44, 13, 37), "left_f3": (152, 44, 14, 37), "left_f4": (125, 44, 15, 37),
}
for n, r in F.items():
    print(f"=== {n} ===")
    ascii_frame(r)
    print()
