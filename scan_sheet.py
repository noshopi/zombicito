import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")
zeke = image.load(os.path.join(base, "zeke.png")).convert_alpha()
key = zeke.get_at((0, 0))
print("key:", key)
spr = zeke.copy()
px = pygame.PixelArray(spr)
px.replace((key.r, key.g, key.b, 255), (0, 0, 0, 0))
del px

def opaque(x, y):
    return spr.get_at((x, y)).a > 128

# scan rows 0, 44, 85 for frame runs
for row in (0, 44, 85, 130):
    runs = []
    in_run = False
    for c in range(spr.get_width()):
        has = any(opaque(c, row + dy) for dy in range(0, 40, 4))
        if has and not in_run:
            runs.append(c); in_run = True
        if not has and in_run:
            runs[-1] = (runs[-1], c - 1); in_run = False
    if in_run:
        runs[-1] = (runs[-1], spr.get_width() - 1)
    print(f"row {row}: runs: {runs}")
