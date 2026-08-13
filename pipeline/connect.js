// Auto-connect all walkable regions of the big map by carving lawn gates
// through the thinnest separating walls. Updates level_big.png + walk_big.bin.
const fs = require("fs");
const { PNG } = require("pngjs");
const TW = 132, TH = 78, TS = 16;
const img = PNG.sync.read(fs.readFileSync("level_big.png"));
const grid = Uint8Array.from(fs.readFileSync("walk_big.bin"));
const src = PNG.sync.read(fs.readFileSync("C:/proy/zombis/assets_raw/level01.png"));
const idx = (x, y) => y * TW + x;

// lawn stamp source (clean grass) from original map
const LX = 176, LY = 396, LS = 40;
function stampTile(tx, ty) {
  grid[idx(tx, ty)] = 1;
  for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
    const si = ((LY + ((ty * TS + y) % LS)) * src.width + (LX + ((tx * TS + x) % LS))) * 4;
    const di = ((ty * TS + y) * img.width + (tx * TS + x)) * 4;
    img.data[di] = src.data[si]; img.data[di+1] = src.data[si+1];
    img.data[di+2] = src.data[si+2]; img.data[di+3] = 255;
  }
}

function flood(sx, sy) {
  const seen = new Uint8Array(TW * TH);
  const q = [idx(sx, sy)];
  if (!grid[q[0]]) return seen;
  seen[q[0]] = 1;
  while (q.length) {
    const c = q.pop();
    const cx = c % TW, cy = (c / TW) | 0;
    for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
      const nx = cx + dx, ny = cy + dy;
      if (nx < 0 || ny < 0 || nx >= TW || ny >= TH) continue;
      const i = idx(nx, ny);
      if (seen[i] || !grid[i]) continue;
      seen[i] = 1; q.push(i);
    }
  }
  return seen;
}

let gates = 0;
for (let iter = 0; iter < 200; iter++) {
  const main = flood(21, 37);
  // collect main tiles and find nearest unreached walkable tile pair
  const mainTiles = [], others = [];
  for (let i = 0; i < TW * TH; i++) {
    if (!grid[i]) continue;
    (main[i] ? mainTiles : others).push(i);
  }
  if (!others.length) break;
  let bd = 1e9, ba = -1, bb = -1;
  for (const b of others) {
    const bx = b % TW, by = (b / TW) | 0;
    for (const a of mainTiles) {
      const ax = a % TW, ay = (a / TW) | 0;
      const d = Math.abs(ax - bx) + Math.abs(ay - by);
      if (d < bd) { bd = d; ba = a; bb = b; }
    }
  }
  // carve L-path a -> b, 2 tiles wide
  let ax = ba % TW, ay = (ba / TW) | 0;
  const bx = bb % TW, by = (bb / TW) | 0;
  const carve = (x, y, horiz) => {
    stampTile(x, y);
    if (horiz) { if (y + 1 < TH) stampTile(x, y + 1); if (y - 1 >= 0) stampTile(x, y - 1); }
    else { if (x + 1 < TW) stampTile(x + 1, y); if (x - 1 >= 0) stampTile(x - 1, y); }
  };
  while (ax !== bx) { ax += ax < bx ? 1 : -1; carve(ax, ay, true); }
  while (ay !== by) { ay += ay < by ? 1 : -1; carve(ax, ay, false); }
  gates++;
}
const finalSeen = flood(21, 37);
let walk = 0, reach = 0;
for (let i = 0; i < TW * TH; i++) { walk += grid[i]; reach += finalSeen[i]; }
console.log(`carved ${gates} gates; walkable ${walk}, reachable ${reach} (${(100*reach/walk).toFixed(1)}%)`);
fs.writeFileSync("level_big.png", PNG.sync.write(img));
fs.writeFileSync("walk_big.bin", Buffer.from(grid));
