// New ZAMN map generator: builds a brand-new 2112x1248 map from scratch.
// Layout: road grid (5x4 blocks), team plazas on the 4 corners, houses with
// hedged yards, trees, a central pond, elevated zones, AO shadows.
// Produces level_big.png + walk_big.bin (fully connected, verified).
const fs = require("fs");
const { PNG } = require("pngjs");

const TW = 132, TH = 78, TS = 16;
const W = TW * TS, H = TH * TS;
const img = new PNG({ width: W, height: H });
const walk = new Uint8Array(TW * TH);

const put = (x, y, r, g, b) => {
    const i = (y * W + x) * 4;
    img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; img.data[i + 3] = 255;
};
const getc = (x, y) => {
    const i = (y * W + x) * 4;
    return [img.data[i], img.data[i + 1], img.data[i + 2]];
};
const hash = (x, y, s) => {
    let h = (x * 374761393 + y * 668265263 + s * 69069) | 0;
    h = (h ^ (h >> 13)) * 1274126177 | 0;
    return ((h ^ (h >> 16)) & 0x7FFFFFFF) / 0x7FFFFFFF;
};

// ---------- layout ----------
// vertical roads (tile x runs), horizontal roads (tile y runs)
const VROADS = [[20, 22], [54, 56], [88, 90], [122, 124]];
const HROADS = [[18, 20], [39, 41], [60, 62]];
const vx = t => t * TS, vy = t => t * TS;

// block bounds (exclusive of roads)
const vcuts = [0, 20, 54, 88, 122, 132];
const hcuts = [0, 18, 39, 60, 78];
const blocks = [];
for (let bi = 0; bi < 5; bi++) for (let bj = 0; bj < 4; bj++)
    blocks.push({ x0: vcuts[bi] + (bi ? 3 : 0), x1: vcuts[bi + 1] - (bi < 4 ? 3 : 0),
                  y0: hcuts[bj] + (bj ? 3 : 0), y1: hcuts[bj + 1] - (bj < 3 ? 3 : 0),
                  bi, bj });
const blockAt = (bi, bj) => blocks.find(b => b.bi === bi && b.bj === bj);

// per-block content: house (with hedge ring) unless plaza; pond in center block
const PLAZA = [[0, 0], [4, 0], [0, 3], [4, 3]];

// ---------- fill background (lawn) ----------
for (let ty = 0; ty < TH; ty++) for (let tx = 0; tx < TW; tx++) {
    // base per block hue
    const bx = Math.max(0, Math.min(4, vcuts.findIndex(c => c > tx) - 1));
    const by = Math.max(0, Math.min(3, hcuts.findIndex(c => c > ty) - 1));
    const hue = ((bx * 7 + by * 11) % 5) - 2;  // -2..2
    const band = Math.sin(ty / 2.6) * 0.05 + Math.sin(tx / 3.4) * 0.03;
    const nz = (hash(tx, ty, 7) - 0.5) * 0.10;
    const m = 1 + band + nz;
    let r = (8 + hue) * m, g = (112 + hue * 1.4) * m, b = (80 + hue) * m;
    r = Math.max(0, Math.min(255, r));
    g = Math.max(0, Math.min(255, g));
    b = Math.max(0, Math.min(255, b));
    for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++)
        put(tx * TS + x, ty * TS + y, r | 0, g | 0, b | 0);
    walk[ty * TW + tx] = 1;
}

// ---------- roads ----------
for (const [a, b] of VROADS) for (let ty = 0; ty < TH; ty++) {
    for (let tx = a; tx <= b; tx++) {
        for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
            const px = tx * TS + x, py = ty * TS + y;
            const edge = x < 3 || x > TS - 4;
            const dash = (Math.floor(py / 12) % 2) === 0 && Math.abs(x - TS / 2) <= 1;
            let c = edge ? [120, 120, 124] : (dash ? [176, 176, 180] : [142, 142, 146]);
            put(px, py, c[0], c[1], c[2]);
        }
    }
}
for (const [a, b] of HROADS) for (let tx = 0; tx < TW; tx++) {
    for (let ty = a; ty <= b; ty++) {
        for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
            const px = tx * TS + x, py = ty * TS + y;
            const edge = y < 3 || y > TS - 4;
            const dash = (Math.floor(px / 12) % 2) === 0 && Math.abs(y - TS / 2) <= 1;
            let c = edge ? [120, 120, 124] : (dash ? [176, 176, 180] : [142, 142, 146]);
            put(px, py, c[0], c[1], c[2]);
        }
    }
}

// ---------- pond (center block) ----------
{
    const b = blockAt(2, 1);
    const cx = (b.x0 + b.x1) / 2 | 0, cy = (b.y0 + b.y1) / 2 | 0;
    const rx = 7, ry = 5;
    for (let ty = cy - ry; ty <= cy + ry; ty++) for (let tx = cx - rx; tx <= cx + rx; tx++) {
        const dx = (tx - cx) / rx, dy = (ty - cy) / ry;
        if (dx * dx + dy * dy > 1.05) continue;
        for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
            const px = tx * TS + x, py = ty * TS + y;
            const band = Math.sin((px + py) / 18) * 0.08;
            const sp = hash(px, py, 3) > 0.96 ? 40 : 0;
            let r = 40 * (1 + band), g = 84 * (1 + band), b = 200 * (1 + band) + sp;
            put(px, py, r | 0, g | 0, b | 0);
        }
        walk[ty * TW + tx] = 0;
    }
}

// ---------- houses with hedged yards ----------
function house(block) {
    const bw = 5, bh = 4;
    const hx = ((block.x0 + block.x1 - bw) / 2) | 0;
    const hy = ((block.y0 + block.y1 - bh) / 2) | 0;
    const ring = 1;
    for (let ty = hy - ring; ty < hy + bh + ring; ty++) for (let tx = hx - ring; tx < hx + bw + ring; tx++) {
        const inHouse = tx >= hx && tx < hx + bw && ty >= hy && ty < hy + bh;
        const inRing = !inHouse;
        for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
            const px = tx * TS + x, py = ty * TS + y;
            if (inHouse) {
                const relY = (y + 0.5) / TS;
                const relX = (x + 0.5) / TS;
                let r = 196, g = 92, b = 82;
                if (relY < 0.22) { r = 222; g = 112; b = 96; }
                if (relY > 0.78) { r = 150; g = 62; b = 58; }
                const edge = Math.min(relX, 1 - relX, relY, 1 - relY);
                if (edge < 0.06) { r *= 0.72; g *= 0.72; b *= 0.75; }
                // door
                if (relX > 0.40 && relX < 0.60 && relY > 0.75) { r = 92; g = 54; b = 36; }
                put(px, py, r | 0, g | 0, b | 0);
            } else if (inRing) {
                put(px, py, 16, 232, 150);
            }
        }
        if (inHouse || inRing) walk[ty * TW + tx] = 0;
    }
}
for (const b of blocks) {
    if (PLAZA.some(p => p[0] === b.bi && p[1] === b.bj)) continue;
    if (b.bi === 2 && b.bj === 1) continue;  // pond block
    house(b);
}

// ---------- trees on lawn ----------
for (const b of blocks) {
    if (PLAZA.some(p => p[0] === b.bi && p[1] === b.bj)) continue;
    if (b.bi === 0 || b.bi === 4) continue;  // narrow edge blocks: keep open
    const n = 6 + ((b.bi * 3 + b.bj * 5) % 4);
    let placed = 0, tries = 0;
    while (placed < n && tries < 200) {
        tries++;
        const tx = b.x0 + 1 + ((hash(b.bi, tries, 5) * (b.x1 - b.x0 - 2)) | 0);
        const ty = b.y0 + 1 + ((hash(b.bj, tries, 9) * (b.y1 - b.y0 - 2)) | 0);
        if (!walk[ty * TW + tx]) continue;
        for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
            const px = tx * TS + x, py = ty * TS + y;
            const rr = (hash(px, py, 11) - 0.5) * 18;
            put(px, py, 18 + rr | 0, 70 + rr | 0, 40 + rr | 0);
        }
        walk[ty * TW + tx] = 0;
        placed++;
    }
}

// ---------- team plazas (corners): open lawn with spawn markers ----------
for (const [bi, bj] of PLAZA) {
    const b = blockAt(bi, bj);
    for (let ty = b.y0; ty < b.y1; ty++) for (let tx = b.x0; tx < b.x1; tx++) {
        for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
            const px = tx * TS + x, py = ty * TS + y;
            const band = Math.sin(py / 22) * 0.05 + Math.sin(px / 26) * 0.03;
            const nz = (hash(px, py, 17) - 0.5) * 0.08;
            const m = 1 + band + nz;
            put(px, py, 10 * m | 0, 126 * m | 0, 90 * m | 0);
        }
    }
}

// ---------- elevated zones ----------
const ELEV = [
    [blockAt(1, 0), 0.30, 0.25, 0.45, 0.55],
    [blockAt(3, 0), 0.30, 0.25, 0.45, 0.55],
    [blockAt(1, 2), 0.30, 0.25, 0.45, 0.55],
    [blockAt(3, 2), 0.30, 0.25, 0.45, 0.55],
];
for (const [b, fx0, fy0, fx1, fy1] of ELEV) {
    const zx0 = b.x0 + ((b.x1 - b.x0) * fx0) | 0, zx1 = b.x0 + ((b.x1 - b.x0) * fx1) | 0;
    const zy0 = b.y0 + ((b.y1 - b.y0) * fy0) | 0, zy1 = b.y0 + ((b.y1 - b.y0) * fy1) | 0;
    for (let ty = zy0; ty < zy1; ty++) for (let tx = zx0; tx < zx1; tx++) {
        for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
            const px = tx * TS + x, py = ty * TS + y;
            const c = getc(px, py);
            const edge = Math.min(px - zx0 * TS, zx1 * TS - 1 - px, py - zy0 * TS, zy1 * TS - 1 - py);
            let r = c[0], g = c[1], b2 = c[2];
            if (edge <= 5) { r *= 0.7; g *= 0.62; b2 *= 0.66; }
            else { r = Math.min(255, r * 1.22); g = Math.min(255, g * 1.24); b2 = Math.min(255, b2 * 1.1); }
            put(px, py, r | 0, g | 0, b2 | 0);
        }
    }
}

// ---------- AO shadows ----------
for (let ty = 0; ty < TH; ty++) for (let tx = 0; tx < TW; tx++) {
    if (!walk[ty * TW + tx]) continue;
    const n = !walk[(ty - 1) * TW + tx], s = !walk[(ty + 1) * TW + tx];
    const w = !walk[ty * TW + tx - 1], e = !walk[ty * TW + tx + 1];
    if (!n && !s && !w && !e) continue;
    for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
        const px = tx * TS + x, py = ty * TS + y;
        const c = getc(px, py);
        let d = 99;
        if (n) d = Math.min(d, y);
        if (s) d = Math.min(d, TS - 1 - y);
        if (w) d = Math.min(d, x);
        if (e) d = Math.min(d, TS - 1 - x);
        if (d >= 4) continue;
        const k = 1 - (4 - d) / 4 * 0.35;
        put(px, py, c[0] * k | 0, c[1] * k | 0, c[2] * k | 0);
    }
}

// ---------- connectivity check ----------
{
    const seen = new Uint8Array(TW * TH);
    let start = -1;
    for (let i = 0; i < TW * TH; i++) if (walk[i]) { start = i; break; }
    const q = [start];
    seen[start] = 1;
    let walkable = 0;
    for (let i = 0; i < TW * TH; i++) if (walk[i]) walkable++;
    while (q.length) {
        const c = q.pop();
        const cx = c % TW, cy = (c / TW) | 0;
        for (const [dx, dy] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
            const nx = cx + dx, ny = cy + dy;
            if (nx < 0 || ny < 0 || nx >= TW || ny >= TH) continue;
            const ni = ny * TW + nx;
            if (seen[ni] || !walk[ni]) continue;
            seen[ni] = 1;
            q.push(ni);
        }
    }
    let reach = 0;
    for (let i = 0; i < TW * TH; i++) reach += seen[i] && walk[i];
    console.log("walkable", walkable, "reach", reach, (100 * reach / walkable).toFixed(1) + "%");
    for (let i = 0; i < TW * TH; i++) if (walk[i] && !seen[i])
        console.log("  aislado tile", i % TW, (i / TW) | 0);
}

fs.writeFileSync("level_big.png", PNG.sync.write(img));
fs.writeFileSync("walk_big.bin", Buffer.from(walk));
console.log("new map written:", W, "x", H);
