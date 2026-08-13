// Compose the 1.5x map: mirror-tile the original right/bottom, punch lawn
// passages through the seam walls so all zones connect.
const fs = require("fs");
const { PNG } = require("pngjs");
const src = PNG.sync.read(fs.readFileSync("C:/proy/zombis/assets_raw/level01.png"));
const SW = src.width, SH = src.height;          // 1408 x 832
const W = Math.round(SW * 1.5), H = Math.round(SH * 1.5); // 2112 x 1248
const out = new PNG({ width: W, height: H });

const getS = (x, y) => { const i = (y * SW + x) * 4; return [src.data[i], src.data[i+1], src.data[i+2]]; };
const put = (x, y, c) => { const i = (y * W + x) * 4; out.data[i] = c[0]; out.data[i+1] = c[1]; out.data[i+2] = c[2]; out.data[i+3] = 255; };

// 1) original at (0,0)
for (let y = 0; y < SH; y++) for (let x = 0; x < SW; x++) put(x, y, getS(x, y));
// 2) right extension: right half mirrored
for (let y = 0; y < SH; y++) for (let x = 0; x < SW / 2; x++)
  put(SW + x, y, getS(SW - 1 - x, y));
// 3) bottom extension: mirror band of what is now rows [H-SH .. SH) i.e. y in [416,832)
const getO = (x, y) => { const i = (y * W + x) * 4; return [out.data[i], out.data[i+1], out.data[i+2]]; };
for (let y = 0; y < H - SH; y++) for (let x = 0; x < W; x++)
  put(x, SH + y, getO(x, SH - 1 - y));

// 4) punch passages: stamp lawn patches over seam walls
//    lawn sample: clean grass area
const LX = 176, LY = 396, LS = 40;   // sample block from original lawn
function stamp(px, py, w, h) {
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++)
    put(px + x, py + y, getS(LX + (x % LS), LY + (y % LS)));
}
// vertical seam wall around x = 1392..1424 (mirrored border strip)
stamp(1370, 224, 76, 64);
stamp(1370, 496, 76, 64);
stamp(1370, 1000, 76, 64);   // in the mirrored bottom zone
// horizontal seam wall around y = 816..848 (mirrored border band)
stamp(230, 770, 72, 120);
stamp(700, 770, 72, 120);
stamp(1240, 770, 72, 120);
stamp(1830, 770, 72, 120);

fs.writeFileSync("level_big.png", PNG.sync.write(out));
console.log(`level_big.png: ${W}x${H}`);
