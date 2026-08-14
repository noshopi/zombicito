import sys
from PIL import Image

def stats(img, name):
    w, h = img.size
    px = img.load()
    print("=== %s %dx%d ===" % (name, w, h))
    # top gradient
    print("top(0,0):", px[0, 0], " mid(320,150):", px[320, 150], " bottom(320,230):", px[320, 230])
    # star count in sky area
    stars = 0
    for y in range(10, 80, 2):
        for x in range(0, w, 2):
            r, g, b = px[x, y][:3]
            if r > 120:
                stars += 1
    print("bright stars (sky):", stars)
    # title green check
    green = 0
    for y in range(10, min(50, h)):
        for x in range(140, min(500, w), 3):
            r, g, b = px[x, y][:3]
            if g > 150 and r < 150:
                green += 1
    print("title green px:", green)
    # gold border detection in a scanline
    gold = 0
    for y in range(90, 200):
        for x in range(0, w, 2):
            r, g, b = px[x, y][:3]
            if r > 150 and 100 < g < 200 and b < 100:
                gold += 1
    print("gold px (mid):", gold)
    # bottom bar
    print("bottom bar (320,238):", px[320, 238], " (10,234):", px[10, 234])
    # zombie pixels near bottom
    zb = 0
    for y in range(h - 30, h):
        for x in range(0, w, 2):
            r, g, b = px[x, y][:3]
            if r > 90 and g > 90 and b > 90:
                zb += 1
    print("zombie-ish px (bottom):", zb)
    # unique colors
    colors = set()
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            colors.add(px[x, y][:3])
    print("distinct colors (sampled):", len(colors))

for f in sys.argv[1:]:
    stats(Image.open(f).convert("RGB"), f)
