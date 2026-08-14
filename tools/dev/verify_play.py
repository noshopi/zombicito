from PIL import Image

img = Image.open("shot_play_sc2.png").convert("RGB")
w, h = img.size
px = img.load()

# find the player: Zeke's blue shirt is the brightest blue block in lower-middle
best = None
for y in range(150, 240, 2):
    for x in range(0, w, 2):
        r, g, b = px[x, y]
        if b > 140 and b - r > 60 and b - g > 30:
            if best is None:
                best = (x, y)
            # cluster around
            pass
# center-of-mass of blue pixels
xs, ys, n = 0, 0, 0
for y in range(140, 250, 2):
    for x in range(0, w, 2):
        r, g, b = px[x, y]
        if b > 140 and b - r > 60:
            xs += x; ys += y; n += 1
print("blue px:", n)
if n:
    print("player COM:", xs // n, ys // n, " (screen center x=%d)" % (w // 2))
# sky + void + ground colors present
from collections import Counter
c = Counter()
for y in range(0, h, 3):
    for x in range(0, w, 3):
        c[px[x, y]] += 1
topc = c.most_common(3)
print("top colors:", topc)
print("void-ish px (12,16,14):", c.get((12, 16, 14), 0))
