import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
img = pygame.image.load("shot_3d.png")
w, h = img.get_size()
print("size:", w, h)
for (x, y, label) in [
    (240, 20, "sky-top"), (240, 60, "sky-mid"), (240, 95, "horizon"),
    (240, 130, "ground-mid"), (240, 220, "ground-near"), (240, 260, "ground-bottom"),
    (240, 205, "player-area"),
]:
    print(f"{label:14s} ({x},{y}): {img.get_at((x, y))}")
# count distinct colors to ensure not blank
cols = set()
for yy in range(0, h, 9):
    for xx in range(0, w, 9):
        cols.add(img.get_at((xx, yy)))
print("distinct colors sampled:", len(cols))
