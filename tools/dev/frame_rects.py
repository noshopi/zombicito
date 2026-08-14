import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")

def clusters(name, y0, y1):
    img = image.load(os.path.join(base, name)).convert_alpha()
    key = img.get_at((0, 0))
    spr = img.copy()
    px = pygame.PixelArray(spr)
    px.replace((key.r, key.g, key.b, 255), (0, 0, 0, 0))
    del px
    w = spr.get_width()
    col_hits = []
    for c in range(w):
        has = any(spr.get_at((c, yy)).a > 128 for yy in range(y0, y1 + 1))
        col_hits.append(has)
    runs = []
    in_run = False
    for c in range(w):
        if col_hits[c] and not in_run:
            runs.append([c, c]); in_run = True
        elif not col_hits[c] and in_run:
            runs[-1][1] = c - 1; in_run = False
    if in_run:
        runs[-1][1] = w - 1
    out = []
    for x0, x1 in runs:
        if x1 - x0 < 6:
            continue
        ys = [yy for yy in range(y0, y1 + 1) if any(spr.get_at((c, yy)).a > 128 for c in range(x0, x1 + 1))]
        if ys:
            out.append((x0, min(ys), x1 - x0 + 1, max(ys) - min(ys) + 1))
    return out

print("zeke UP row (85..121):", clusters("zeke.png", 85, 121))
print("julie row1 (4..41):", clusters("julie.png", 4, 41))
print("julie row2 (52..90):", clusters("julie.png", 52, 90))
print("julie row3 (101..139):", clusters("julie.png", 101, 139))
print("julie row4 (152..190):", clusters("julie.png", 152, 190))
print("julie row5 (204..242):", clusters("julie.png", 204, 242))
