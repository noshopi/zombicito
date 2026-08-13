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

def ch(s):
    a = s.get_at((0, 0)).a
    return "#" if a > 128 else ("+" if a > 16 else ".")

# print strip from x=85..195, y=44..81
for yy in range(44, 82):
    row = ""
    for c in range(85, 195):
        a = spr.get_at((c, yy)).a
        row += "#" if a > 128 else ("+" if a > 16 else ".")
    print(f"{yy:3d} {row}")

print()
print("=== also (4,44)-(68,81) strip ===")
for yy in range(44, 82):
    row = ""
    for c in range(4, 70):
        a = spr.get_at((c, yy)).a
        row += "#" if a > 128 else ("+" if a > 16 else ".")
    print(f"{yy:3d} {row}")
