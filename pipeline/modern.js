// Modern texture pass on the big map. Enhances the existing art (which
// already has the elevation zones) with modern-looking shading:
//   - mowed-lawn bands + fine noise on grass
//   - gradient roofs with a top-left light edge
//   - contact shadows (AO) along every wall
//   - textured paths, sparkling water, richer hedges
// Walk grid is untouched (purely visual).
const fs = require("fs");
const { PNG } = require("pngjs");
const img = PNG.sync.read(fs.readFileSync("level_big.png"));
const grid = Uint8Array.from(fs.readFileSync("walk_big.bin"));
const W = img.width, H = img.height, TW = 132, TH = 78, TS = 16;
const at = (x, y) => { const i = (y * W + x) * 4; return [img.data[i], img.data[i + 1], img.data[i + 2]]; };
const set = (x, y, r, g, b) => { const i = (y * W + x) * 4; img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; };
const wl = (tx, ty) => tx >= 0 && ty >= 0 && tx < TW && ty < TH && grid[ty * TW + tx];

const near = (c, r, g, b, t) => Math.abs(c[0] - r) <= t && Math.abs(c[1] - g) <= t && Math.abs(c[2] - b) <= t;
function famOf(c) {
    if (near(c, 8, 112, 80, 24) || near(c, 16, 88, 72, 24) || near(c, 8, 176, 64, 24)) return "lawn";
    if (near(c, 0, 0, 0, 30)) return "dark";
    if (near(c, 24, 64, 64, 24) || near(c, 0, 72, 40, 24) || near(c, 0, 56, 0, 24)) return "dgreen";
    if (near(c, 48, 88, 216, 40) || near(c, 16, 48, 88, 28)) return "water";
    if (near(c, 248, 160, 152, 30) || near(c, 224, 96, 96, 30) || near(c, 144, 24, 16, 30)) return "brick";
    if (near(c, 16, 248, 160, 40) || near(c, 128, 248, 200, 40) || near(c, 104, 248, 64, 40) || near(c, 8, 176, 120, 20)) return "hedge";
    if (near(c, 120, 64, 32, 30) || near(c, 80, 32, 16, 25) || near(c, 144, 96, 48, 30)) return "brown";
    if (near(c, 104, 104, 104, 30) || near(c, 64, 64, 64, 20) || near(c, 160, 160, 160, 30) || near(c, 248, 248, 248, 20)) return "gray";
    return "other";
}

// per-tile dominant family
const tfam = new Array(TW * TH);
for (let ty = 0; ty < TH; ty++) for (let tx = 0; tx < TW; tx++) {
    const cnt = {};
    for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
        const c = at(tx * TS + x, ty * TS + y);
        const f = famOf(c);
        cnt[f] = (cnt[f] || 0) + 1;
    }
    let best = "other", bn = 0;
    for (const k in cnt) if (cnt[k] > bn) { bn = cnt[k]; best = k; }
    tfam[ty * TW + tx] = best;
}

// hash noise
function hash(x, y, seed) {
    let h = (x * 374761393 + y * 668265263 + seed * 69069) | 0;
    h = (h ^ (h >> 13)) * 1274126177 | 0;
    return ((h ^ (h >> 16)) & 0x7FFFFFFF) / 0x7FFFFFFF;
}

for (let ty = 0; ty < TH; ty++) {
    for (let tx = 0; tx < TW; tx++) {
        const f = tfam[ty * TW + tx];
        const x0 = tx * TS, y0 = ty * TS;
        for (let y = 0; y < TS; y++) {
            for (let x = 0; x < TS; x++) {
                const px = x0 + x, py = y0 + y;
                const c = at(px, py);
                const fpx = famOf(c);
                if (f === "lawn") {
                    if (fpx !== "lawn") continue;
                    const band = Math.sin((py + 3) / 26.0) * 0.045 + Math.sin((px + 1) / 34.0) * 0.03;
                    const nz = (hash(px, py, 7) - 0.5) * 0.09;
                    let r = c[0] * (1 + band + nz);
                    let g = c[1] * (1 + band + nz);
                    let b = c[2] * (1 + band * 0.7 + nz * 0.7);
                    set(px, py, r | 0, g | 0, b | 0);
                } else if (f === "brick") {
                    if (fpx !== "brick" && fpx !== "brown") continue;
                    const relY = (y + 0.5) / TS;
                    let m = 1 + 0.10 * (1 - relY) - 0.16 * relY;
                    let r = c[0] * m, g = c[1] * m, b = c[2] * m;
                    const relX = (x + 0.5) / TS;
                    const edge = Math.min(relX, 1 - relX, relY, 1 - relY);
                    if (edge > 0.88) { r *= 0.86; g *= 0.86; b *= 0.9; }          // darker rim
                    if (edge > 0.75 && edge <= 0.88 && relY < 0.5 && relX < 0.5) { r += 14; g += 12; b += 8; } // top-left light
                    set(px, py, r | 0, g | 0, b | 0);
                } else if (f === "gray") {
                    if (fpx !== "gray") continue;
                    const nz = (hash(px, py, 11) - 0.5) * 0.10;
                    let r = c[0] * (1 + nz), g = c[1] * (1 + nz), b = c[2] * (1 + nz);
                    const relY = (y + 0.5) / TS;
                    if (relY < 0.18) { r += 8; g += 8; b += 8; }
                    set(px, py, r | 0, g | 0, b | 0);
                } else if (f === "water") {
                    if (fpx !== "water") continue;
                    const band = Math.sin((px + py) / 18.0) * 0.07;
                    let r = c[0] * (1 + band), g = c[1] * (1 + band), b = c[2] * (1 + band * 1.4);
                    if (hash(px, py, 3) > 0.965) { r += 46; g += 46; b += 40; }   // sparkle
                    set(px, py, r | 0, g | 0, b | 0);
                } else if (f === "hedge" && fpx === "hedge") {
                    set(px, py, Math.min(255, c[0] * 0.94) | 0, Math.min(255, c[1] * 1.06) | 0, Math.min(255, c[2] * 0.94) | 0);
                }
            }
        }
    }
}

// ambient occlusion: darken the walkable strip hugging non-walkable tiles
const AO = 4;
for (let ty = 0; ty < TH; ty++) for (let tx = 0; tx < TW; tx++) {
    if (!wl(tx, ty)) continue;
    const x0 = tx * TS, y0 = ty * TS;
    const wallN = !wl(tx, ty - 1), wallS = !wl(tx, ty + 1);
    const wallW = !wl(tx - 1, ty), wallE = !wl(tx + 1, ty);
    if (!wallN && !wallS && !wallW && !wallE) continue;
    for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
        const px = x0 + x, py = y0 + y;
        const c = at(px, py);
        if (near(c, 0, 0, 0, 30)) continue;
        let d = 99;
        if (wallN) d = Math.min(d, y);
        if (wallS) d = Math.min(d, TS - 1 - y);
        if (wallW) d = Math.min(d, x);
        if (wallE) d = Math.min(d, TS - 1 - x);
        if (d >= AO) continue;
        const k = 1 - (AO - d) / AO * 0.32;
        set(px, py, c[0] * k | 0, c[1] * k | 0, c[2] * k | 0);
    }
}

fs.writeFileSync("level_big.png", PNG.sync.write(img));
console.log("modern texture pass done (AO, grass bands, roofs, paths, water)");
