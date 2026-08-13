import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ["SDL_VIDEODRIVER"] = "dummy"
import pygame
pygame.init()
pygame.display.set_mode((64, 64))
from pygame import image
base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")
zeke = image.load(os.path.join(base, "zeke.png")).convert_alpha()
frames = {
    "left_f0": (87, 44, 15, 37), "left_f1": (108, 44, 13, 37),
    "left_f2": (70, 44, 13, 37), "left_f3": (152, 44, 14, 37), "left_f4": (125, 44, 15, 37),
    "down_f0": (86, 5, 16, 36), "down_f1": (108, 4, 15, 37), "down_f2": (128, 4, 16, 37),
}
names = list(frames)
w, h = 130, 40
sheet = pygame.Surface((w * len(names), h + 18), pygame.SRCALPHA)
for i, n in enumerate(names):
    x, y, fw, fh = frames[n]
    sub = zeke.subsurface((x, y, fw, fh))
    sheet.blit(sub, (i * w + (w - fw) // 2, 16 + (h - fh)))
    font = pygame.font.Font(None, 16)
    sheet.blit(font.render(n, True, (255, 255, 255)), (i * w, 0))
image.save(sheet, "frames_montage.png")
print("saved frames_montage.png", sheet.get_size())
