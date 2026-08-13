from pathlib import Path

from PIL import Image, ImageDraw


OUT = Path(__file__).resolve().parents[1] / "ZamnNative" / "assets"
NAMES = ["rifle", "shotgun", "smg", "pistol", "magnum", "minigun", "flamethrower", "rocket", "ray"]


def icon(index):
    image = Image.new("RGBA", (48, 32), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    outline = (18, 14, 28, 255)
    metal = (154, 165, 184, 255)
    dark_metal = (63, 70, 92, 255)
    glow = (110, 225, 255, 255)
    accent = [(220, 70, 74), (245, 180, 70), (90, 190, 230), (210, 80, 110),
              (255, 230, 130), (100, 220, 150), (245, 105, 55), (220, 105, 235), glow][index]

    if index == 0:  # rifle
        d.rectangle((4, 12, 38, 17), fill=outline)
        d.rectangle((9, 11, 34, 15), fill=metal)
        d.rectangle((34, 13, 46, 15), fill=dark_metal)
        d.rectangle((17, 17, 22, 24), fill=outline)
        d.rectangle((14, 20, 20, 25), fill=(105, 64, 42, 255))
        d.rectangle((8, 9, 14, 11), fill=accent)
    elif index == 1:  # shotgun
        d.rectangle((3, 10, 39, 17), fill=outline)
        d.rectangle((8, 11, 45, 13), fill=metal)
        d.rectangle((8, 15, 45, 17), fill=dark_metal)
        d.rectangle((15, 17, 21, 24), fill=outline)
        d.rectangle((12, 21, 20, 25), fill=(105, 64, 42, 255))
        d.rectangle((7, 8, 11, 10), fill=accent)
        d.point((43, 12), fill=(255, 255, 255, 255))
    elif index == 2:  # smg
        d.rectangle((6, 11, 39, 18), fill=outline)
        d.rectangle((10, 12, 34, 15), fill=metal)
        d.rectangle((35, 13, 45, 16), fill=dark_metal)
        d.rectangle((18, 17, 23, 26), fill=outline)
        d.rectangle((17, 20, 22, 27), fill=dark_metal)
        d.rectangle((11, 8, 25, 10), fill=accent)
        d.rectangle((12, 9, 14, 11), fill=(255, 235, 140, 255))
    elif index == 3:  # pistol
        d.rectangle((9, 10, 34, 17), fill=outline)
        d.rectangle((12, 11, 36, 14), fill=metal)
        d.rectangle((30, 14, 41, 16), fill=dark_metal)
        d.rectangle((19, 16, 26, 24), fill=outline)
        d.rectangle((20, 18, 24, 26), fill=(105, 64, 42, 255))
        d.rectangle((14, 8, 22, 10), fill=accent)
    elif index == 4:  # magnum
        d.rectangle((7, 11, 36, 18), fill=outline)
        d.rectangle((11, 12, 35, 15), fill=(212, 218, 228, 255))
        d.rectangle((34, 13, 45, 16), fill=accent)
        d.rectangle((18, 17, 24, 26), fill=outline)
        d.rectangle((19, 20, 23, 27), fill=(105, 64, 42, 255))
        d.rectangle((8, 9, 13, 11), fill=accent)
    elif index == 5:  # minigun
        d.rectangle((8, 8, 28, 21), fill=outline)
        d.rectangle((12, 10, 28, 18), fill=metal)
        for x in (30, 34, 38, 42):
            d.rectangle((x, 12, 46, 14), fill=outline)
            d.rectangle((x, 13, 46, 13), fill=accent)
        d.rectangle((17, 20, 23, 27), fill=dark_metal)
        d.rectangle((8, 6, 14, 8), fill=accent)
    elif index == 6:  # flamethrower
        d.rectangle((5, 10, 31, 21), fill=outline)
        d.rectangle((9, 12, 28, 18), fill=metal)
        d.rectangle((28, 13, 45, 17), fill=dark_metal)
        d.rectangle((14, 20, 22, 27), fill=outline)
        d.rectangle((16, 22, 21, 28), fill=(105, 64, 42, 255))
        d.polygon([(44, 10), (47, 14), (44, 18), (41, 14)], fill=accent)
        d.rectangle((11, 8, 17, 10), fill=(255, 220, 90, 255))
    elif index == 7:  # rocket launcher
        d.rectangle((5, 9, 39, 21), fill=outline)
        d.rectangle((9, 11, 36, 18), fill=metal)
        d.rectangle((34, 12, 46, 18), fill=accent)
        d.rectangle((16, 19, 23, 27), fill=outline)
        d.rectangle((18, 22, 22, 29), fill=dark_metal)
        d.rectangle((8, 7, 20, 9), fill=accent)
        d.rectangle((40, 13, 45, 17), fill=(255, 255, 255, 255))
    else:  # ray gun
        d.rectangle((7, 10, 35, 19), fill=outline)
        d.rectangle((11, 12, 31, 16), fill=glow)
        d.rectangle((31, 12, 45, 17), fill=accent)
        d.rectangle((17, 18, 24, 27), fill=outline)
        d.rectangle((19, 21, 23, 28), fill=dark_metal)
        d.rectangle((13, 7, 24, 10), fill=accent)
        d.point((43, 14), fill=(255, 255, 255, 255))

    # one-pixel highlight makes each silhouette read cleanly at native scale
    d.line((5, 5, 5, 26), fill=(255, 255, 255, 70))
    return image


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(NAMES):
        icon(index).save(OUT / ("weapon_" + name + ".png"))


if __name__ == "__main__":
    main()
