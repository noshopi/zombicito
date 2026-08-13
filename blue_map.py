from PIL import Image

img = Image.open("shot_play_sc2.png").convert("RGB")
w, h = img.size
px = img.load()
# ASCII map: '#' = blue, '.' = other
for y in range(100, 240, 3):
    row = ""
    for x in range(0, w, 3):
        r, g, b = px[x, y]
        if b > 140 and b - r > 60:
            row += "#"
        else:
            row += "."
    if "#" in row:
        print("%03d %s" % (y, row))
