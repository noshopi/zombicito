import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")

def strip(name, y0, y1, x0, x1):
    img = image.load(os.path.join(base, name)).convert_alpha()
    key = img.get_at((0, 0))
    spr = img.copy()
    px = pygame.PixelArray(spr)
    px.replace((key.r, key.g, key.b, 255), (0, 0, 0, 0))
    del px
    print(f"=== {name} y={y0}..{y1} x={x0}..{x1} ===")
    for yy in range(y0, y1 + 1):
        row = ""
        for c in range(x0, x1):
            a = spr.get_at((c, yy)).a
            row += "#" if a > 128 else ("+" if a > 16 else ".")
        print(f"{yy:3d} {row}")

strip("zeke.png", 85, 121, 80, 165)
