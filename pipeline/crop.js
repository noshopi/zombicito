const fs = require("fs");
const { PNG } = require("pngjs");
const [,, inFile, outFile, x, y, w, h] = process.argv;
const img = PNG.sync.read(fs.readFileSync(inFile));
const cw = Math.min(+w, img.width - +x), ch = Math.min(+h, img.height - +y);
const out = new PNG({ width: cw, height: ch });
PNG.bitblt(img, out, +x, +y, cw, ch, 0, 0);
fs.writeFileSync(outFile, PNG.sync.write(out));
console.log(`${outFile}: ${cw}x${ch}`);
