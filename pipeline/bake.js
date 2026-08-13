// Bake walkability grid from level map by per-tile color classification.
// Outputs walk.bin (width*height bytes, 1=walkable 0=blocked) + overlay preview.
const fs = require("fs");
const { PNG } = require("pngjs");
const img = PNG.sync.read(fs.readFileSync(process.argv[2]));
const TS = 16;
const TW = Math.floor(img.width / TS), TH = Math.floor(img.height / TS);

const fam = (r, g, b) => {
  const near = (cr,cg,cb,t=24) => Math.abs(r-cr)<=t && Math.abs(g-cg)<=t && Math.abs(b-cb)<=t;
  if (near(8,112,80) || near(16,88,72) || near(8,176,64)) return "lawn";
  if (near(0,0,0,30)) return "dark";                       // outlines/shadow dots
  if (near(24,64,64) || near(0,72,40) || near(0,56,0)) return "dgreen"; // deep shadow greens
  if (near(48,88,216,40) || near(16,48,88,28)) return "water";
  if (near(248,160,152,30) || near(224,96,96,30) || near(144,24,16,30)) return "brick";
  if (near(16,248,160,40) || near(128,248,200,40) || near(104,248,64,40) || near(8,176,120,20)) return "hedge";
  if (near(120,64,32,30) || near(80,32,16,25) || near(144,96,48,30)) return "brown";
  if (near(104,104,104,30) || near(64,64,64,20) || near(160,160,160,30) || near(248,248,248,20)) return "gray";
  return "other";
};

const grid = new Uint8Array(TW * TH);
for (let ty = 0; ty < TH; ty++) for (let tx = 0; tx < TW; tx++) {
  const c = {};
  for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
    const i = ((ty*TS+y) * img.width + (tx*TS+x)) * 4;
    const f = fam(img.data[i], img.data[i+1], img.data[i+2]);
    c[f] = (c[f] || 0) + 1;
  }
  const n = TS*TS;
  const hard = (c.water||0) + (c.brick||0) + (c.hedge||0) + (c.brown||0) + (c.gray||0) + (c.other||0);
  const blocked = hard / n > 0.45
    || (c.dgreen||0) / n > 0.55   // dark-teal hedges are mostly deep shadow greens
    || (c.dark||0) / n > 0.60;    // off-map / solid black areas
  grid[ty*TW+tx] = blocked ? 0 : 1;
}
const outBin = process.argv[3] || "walk.bin";
const outOverlay = process.argv[4] || "walk_overlay.png";
fs.writeFileSync(outBin, Buffer.from(grid));

// overlay: blocked tiles tinted red
const out = new PNG({ width: img.width, height: img.height });
img.data.copy(out.data);
for (let ty = 0; ty < TH; ty++) for (let tx = 0; tx < TW; tx++) {
  if (grid[ty*TW+tx]) continue;
  for (let y = 0; y < TS; y++) for (let x = 0; x < TS; x++) {
    const i = ((ty*TS+y) * img.width + (tx*TS+x)) * 4;
    out.data[i] = Math.min(255, out.data[i] * 0.5 + 140);
    out.data[i+1] *= 0.45; out.data[i+2] *= 0.45;
  }
}
fs.writeFileSync(outOverlay, PNG.sync.write(out));
const free = grid.reduce((a,b) => a+b, 0);
console.log(`grid ${TW}x${TH}, walkable ${free} (${(100*free/(TW*TH)).toFixed(1)}%)`);
