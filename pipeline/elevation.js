// Elevation pass on the big map: tints walkable lawn into raised plateaus
// (brighter grass + shadow contour on the lower/right edges) and lowlands
// (darker, teal-tinted grass). Purely cosmetic - the walk grid is unchanged.
const fs = require("fs");
const { PNG } = require("pngjs");
const img = PNG.sync.read(fs.readFileSync("level_big.png"));
const W = img.width, H = img.height;
const px = (x, y) => { const i = (y * W + x) * 4; return [img.data[i], img.data[i + 1], img.data[i + 2]]; };
const put = (x, y, r, g, b) => { const i = (y * W + x) * 4; img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; };

// greenish lawn test (houses/hedges/paths stay untouched)
const isLawn = (c) => c[1] > c[0] * 1.25 && c[1] > c[2] * 1.05 && c[1] > 45 && c[1] < 190;

const ELEVATED = [
    [650, 600, 250, 190],   // center-left plateau
    [1430, 250, 230, 160],  // upper-right hill
    [920, 70, 220, 150],    // top-mid hill
    [1640, 880, 250, 190],  // lower-right plateau
    [230, 830, 210, 150],   // lower-left hill
];
const LOWLANDS = [
    [480, 300, 210, 160],   // upper-left swamp
    [1280, 680, 230, 160],  // center-right low zone
    [180, 230, 190, 150],   // top-left hollow
    [1850, 480, 190, 150],  // right-mid hollow
];

function passZone(zone, mode) {
    const [zx, zy, zw, zh] = zone;
    for (let y = zy; y < zy + zh && y < H; y++) {
        for (let x = zx; x < zx + zw && x < W; x++) {
            const c = px(x, y);
            if (!isLawn(c)) continue;
            if (mode === "up") {
                let r = c[0], g = c[1], b = c[2];
                const edge = Math.min(y - zy, (zy + zh - 1) - y, x - zx, (zx + zw - 1) - x);
                if (edge <= 4) {          // contour shadow ring
                    r = r * 0.72; g = g * 0.66; b = b * 0.7;
                } else {
                    r = Math.min(255, r * 1.18); g = Math.min(255, g * 1.2); b = Math.min(255, b * 1.1);
                }
                put(x, y, r | 0, g | 0, b | 0);
            } else {
                let r = c[0] * 0.82, g = c[1] * 0.8, b = Math.min(255, c[2] * 0.95 + 14);
                put(x, y, r | 0, g | 0, b | 0);
            }
        }
    }
}

for (const z of ELEVATED) passZone(z, "up");
for (const z of LOWLANDS) passZone(z, "low");

fs.writeFileSync("level_big.png", PNG.sync.write(img));
console.log("elevation pass done:", ELEVATED.length, "raised zones,", LOWLANDS.length, "lowlands");
