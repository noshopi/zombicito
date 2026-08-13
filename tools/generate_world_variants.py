"""Create independent base layouts for worlds 3-6 from the two source maps."""
from pathlib import Path
from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "ZamnNative" / "assets"
SOURCES = [
    (ASSETS / "level1_deco.png", ASSETS / "walk1_deco.bin"),
    (ASSETS / "level2_big.png", ASSETS / "walk2_big.bin"),
]
TINTS = [(1.12, (190, 105, 45)), (0.86, (35, 125, 145)),
         (1.05, (115, 65, 170)), (0.92, (155, 45, 65))]

def tint(img, factor, color):
    base = ImageEnhance.Color(img).enhance(0.82)
    base = ImageEnhance.Brightness(base).enhance(factor)
    wash = Image.new("RGB", base.size, color)
    return Image.blend(base, wash, 0.12)

def transform_mask(data, size, op):
    mask = Image.frombytes("L", size, bytes(data))
    return op(mask).tobytes()

for index, (src_img, src_walk) in enumerate(SOURCES * 2, start=3):
    img = Image.open(src_img).convert("RGB")
    walk = bytearray(src_walk.read_bytes())
    op = (ImageOps.mirror if index in (3, 5) else ImageOps.flip)
    if index == 5:
        op = lambda im: ImageOps.flip(ImageOps.mirror(im))
    out_img = tint(op(img), *TINTS[index - 3])
    out_walk = transform_mask(walk, (img.width // 16, img.height // 16), op)
    out_img.save(ASSETS / f"level{index}_big.png")
    (ASSETS / f"walk{index}_big.bin").write_bytes(out_walk)
    print(f"saved world {index}: {out_img.size}, walk={len(out_walk)}")
