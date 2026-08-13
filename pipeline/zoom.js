const fs = require("fs");
const { PNG } = require("pngjs");
const [,, inFile, outFile, x, y, w, h, s] = process.argv;
const img = PNG.sync.read(fs.readFileSync(inFile));
const scale = +s || 4;
const cw = Math.min(+w, img.width - +x), ch = Math.min(+h, img.height - +y);
const out = new PNG({ width: cw * scale, height: ch * scale });
for (let oy = 0; oy < ch * scale; oy++) for (let ox = 0; ox < cw * scale; ox++) {
  const si = (((+y + (oy/scale|0)) * img.width) + (+x + (ox/scale|0))) * 4;
  const di = (oy * cw * scale + ox) * 4;
  out.data[di] = img.data[si]; out.data[di+1] = img.data[si+1];
  out.data[di+2] = img.data[si+2]; out.data[di+3] = 255;
}
fs.writeFileSync(outFile, PNG.sync.write(out));
console.log(`${outFile}: ${cw*scale}x${ch*scale}`);
