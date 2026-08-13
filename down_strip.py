import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")
zeke = image.load(os.path.join(base, "zeke.png")).convert_alpha()
key = zeke.get_at((0, 0))
spr = zeke.copy()
px = pygame.PixelArray(spr)
px.replace((key.r, key.g, key.b, 255), (0, 0, 0, 0))
del px

print("=== DOWN row (y=4..41) x=0..190 ===")
for yy in range(4, 42):
    row = ""
    for c in range(0, 190):
        a = spr.get_at((c, yy)).a
        row += "#" if a > 128 else ("+" if a > 16 else ".")
    print(f"{yy:3d} {row}")
