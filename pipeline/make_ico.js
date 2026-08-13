// Build an .ico (PNG-format entries) from Zeke's face region, nearest-neighbor upscaled.
const fs = require("fs");
const { PNG } = require("pngjs");
const sheet = PNG.sync.read(fs.readFileSync("C:/zombis/assets_raw/zeke.png"));
// zeke_down frame 0 rect from sprites.h selection (blob 14): approximate via known sheet layout
// use the big Zeke artwork at top-left of the sheet (0,0,88,110) for a recognizable icon
const SX = 2, SY = 2, SW = 84, SH = 108;
function makeSize(N) {
  const img = new PNG({ width: N, height: N });
  // fit height, center horizontally, transparent bg
  const scale = SH / N > SW / N ? SH / N : SW / N;
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const sx = SX + Math.floor((x - (N - SW / scale) / 2) * scale);
    const sy = SY + Math.floor(y * scale);
    const di = (y * N + x) * 4;
    if (sx < SX || sx >= SX + SW || sy < SY || sy >= SY + SH) { img.data[di + 3] = 0; continue; }
    const si = (sy * sheet.width + sx) * 4;
    const r = sheet.data[si], g = sheet.data[si + 1], b = sheet.data[si + 2];
    if (r === 8 && g === 112 && b === 80) { img.data[di + 3] = 0; continue; } // key bg
    img.data[di] = r; img.data[di + 1] = g; img.data[di + 2] = b; img.data[di + 3] = 255;
  }
  return PNG.sync.write(img);
}
const sizes = [16, 32, 48, 256];
const pngs = sizes.map(makeSize);
// ICO: header + dir entries + png blobs
const count = sizes.length;
let offset = 6 + 16 * count;
const header = Buffer.alloc(6);
header.writeUInt16LE(0, 0); header.writeUInt16LE(1, 2); header.writeUInt16LE(count, 4);
const entries = [], blobs = [];
for (let i = 0; i < count; i++) {
  const e = Buffer.alloc(16);
  e.writeUInt8(sizes[i] === 256 ? 0 : sizes[i], 0);
  e.writeUInt8(sizes[i] === 256 ? 0 : sizes[i], 1);
  e.writeUInt8(0, 2); e.writeUInt8(0, 3);
  e.writeUInt16LE(1, 4); e.writeUInt16LE(32, 6);
  e.writeUInt32LE(pngs[i].length, 8);
  e.writeUInt32LE(offset, 12);
  offset += pngs[i].length;
  entries.push(e); blobs.push(pngs[i]);
}
fs.writeFileSync("C:/zombis/ZamnNative/src/app.ico", Buffer.concat([header, ...entries, ...blobs]));
fs.writeFileSync("C:/zombis/ZamnNative/src/app.rc", '1 ICON "app.ico"\n');
console.log("app.ico + app.rc written");
