"""Extract the first six original SNES levels into Python-ready PNG assets.

The format follows ZAMN-Edit's public ROM reader: LoROM pointers, the game's
12-bit dictionary compressor, 4bpp SNES tiles, and 64x64 map16 blocks.
"""
from pathlib import Path
import struct
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / "ZombiesApp" / "rom" / "zamn.sfc"
OUT = ROOT / "ZamnNative" / "assets"
LEVELS = [
    (1, 0xF9060, "Zombie Panic"),
    (2, 0xF8072, "Weird Kids on the Block"),
    (3, 0xF826D, "Mushroom Men"),
    (4, 0xF83DA, "Day of the Tentacle"),
    (5, 0xF85C9, "Super Fund Cleanup Site"),
    (6, 0xF87C9, "Toxic Terrors"),
]

rom = ROM.read_bytes()

def ptr(pos):
    value = rom[pos] | (rom[pos + 1] << 8)
    bank = rom[pos + 2]
    if bank < 0x80 or value < 0x8000:
        raise ValueError(f"invalid LoROM pointer at {pos:#x}")
    return (bank - 0x80) * 0x8000 + value - 0x8000

def decompress(pos):
    out = bytearray()
    dictionary = bytearray(0x1000)
    write_pos = 0xFEE
    while True:
        size = rom[pos] | (rom[pos + 1] << 8)
        pos += 2
        chained = bool(size & 0x8000)
        size &= 0x7FFF
        end = pos + size
        while pos < end:
            flags = rom[pos]
            pos += 1
            for _ in range(8):
                if pos >= end:
                    break
                if flags & 1:
                    value = rom[pos]
                    pos += 1
                    out.append(value)
                    dictionary[write_pos] = value
                    write_pos = (write_pos + 1) & 0xFFF
                else:
                    read_pos = rom[pos]
                    high = rom[pos + 1]
                    pos += 2
                    read_pos |= (high & 0xF0) << 4
                    length = (high & 0x0F) + 3
                    for _ in range(length):
                        value = dictionary[read_pos]
                        out.append(value)
                        dictionary[write_pos] = value
                        write_pos = (write_pos + 1) & 0xFFF
                        read_pos = (read_pos + 1) & 0xFFF
                flags >>= 1
        if not chained:
            return bytes(out)
        pos = ptr(pos)

def palette(pos):
    result = []
    for i in range(128):
        value = rom[pos + i * 2] | (rom[pos + i * 2 + 1] << 8)
        result.append(((value & 31) * 8,
                       ((value >> 5) & 31) * 8,
                       ((value >> 10) & 31) * 8))
    return result

def draw_tile(image, x0, y0, gfx, tile_index, colors, pal_index, xflip, yflip, transparent=False):
    base = tile_index * 32
    for y in range(8):
        row = 7 - y if yflip else y
        p0 = gfx[base + row * 2]
        p1 = gfx[base + row * 2 + 1]
        p2 = gfx[base + 16 + row * 2]
        p3 = gfx[base + 16 + row * 2 + 1]
        for x in range(8):
            bit = 7 - x if not xflip else x
            index = ((p0 >> bit) & 1) | (((p1 >> bit) & 1) << 1)
            index |= (((p2 >> bit) & 1) << 2) | (((p3 >> bit) & 1) << 3)
            if not transparent or index != 0:
                color = colors[pal_index + index]
                image.putpixel((x0 + x, y0 + y), (*color, 255) if image.mode == "RGBA" else color)

def extract(level_no, level_pos, title):
    width = rom[level_pos + 0x22] | (rom[level_pos + 0x23] << 8)
    height = rom[level_pos + 0x24] | (rom[level_pos + 0x25] << 8)
    tileset = ptr(level_pos)
    background = ptr(level_pos + 4)
    collision = ptr(level_pos + 8)
    gfx_addr = ptr(level_pos + 12)
    palette_addr = ptr(level_pos + 16)
    map16 = decompress(tileset)
    gfx = rom[gfx_addr:gfx_addr + 0x4000]
    colors = palette(palette_addr)
    collision_data = rom[collision:collision + 0x400]
    tile_map = [struct.unpack_from("<H", rom, background + i * 2)[0] & 0xFF
                for i in range(width * height)]
    image = Image.new("RGB", (width * 64, height * 64))
    upper = Image.new("RGBA", (width * 64, height * 64), (0, 0, 0, 0))
    block_masks = []
    for my, meta in enumerate(tile_map):
        block = meta * 0x80
        block_walk = bytearray([1] * 16)
        for n in range(64):
            tile = map16[block + n * 2]
            attr = map16[block + n * 2 + 1]
            tile += 0x100 if attr & 1 else 0
            pal_index = 0x10 * ((attr >> 2) & 7)
            draw_tile(image, (my % width) * 64 + (n % 8) * 8,
                      (my // width) * 64 + (n // 8) * 8,
                      gfx, tile, colors, pal_index, bool(attr & 0x40), bool(attr & 0x80))
            # The collision table marks the solid/priority tile pairs used by
            # the SNES map16 data. Build four real 16x16 collision cells per
            # 64x64 block instead of treating the whole block as one cell.
            cell = ((n // 8) // 2) * 4 + ((n % 8) // 2)
            if collision_data[tile * 2] != 0 or collision_data[tile * 2 + 1] != 0:
                block_walk[cell] = 0
            if collision_data[tile * 2] & 1 and not (collision_data[tile * 2 + 1] & 1):
                draw_tile(upper, (my % width) * 64 + (n % 8) * 8,
                          (my // width) * 64 + (n // 8) * 8,
                          gfx, tile, colors, pal_index, bool(attr & 0x40), bool(attr & 0x80), True)
        for row in range(4):
            for col in range(4):
                cell = row * 4 + col
                walkable = not bool(block_walk[cell])
                px0 = (my % width) * 64 + col * 16
                py0 = (my // width) * 64 + row * 16
                blue = 0
                for yy in range(py0, py0 + 16):
                    for xx in range(px0, px0 + 16):
                        r, g, b = image.getpixel((xx, yy))
                        if b > 120 and b > g * 1.35 and r < 100:
                            blue += 1
                if blue > 32:
                    walkable = False
                block_walk[cell] = 1 if walkable else 0
        block_masks.append(block_walk)
    walk = bytearray()
    for by in range(height):
        for row in range(4):
            for bx in range(width):
                walk.extend(block_masks[by * width + bx][row * 4:(row + 1) * 4])
    image.save(OUT / f"level{level_no}_snes.png")
    upper.save(OUT / f"level{level_no}_snes_upper.png")
    (OUT / f"walk{level_no}_snes.bin").write_bytes(walk)
    print(f"level {level_no}: {title}; {width}x{height} blocks; {image.size}; map16={len(map16)}")

for item in LEVELS:
    extract(*item)
