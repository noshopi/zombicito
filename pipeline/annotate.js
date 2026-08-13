// Overlay blob indices on the original sheet (scaled) to identify frames in context.
const fs = require("fs");
const { PNG } = require("pngjs");
const DIGITS = {
  "0":[7,5,5,5,7],"1":[2,6,2,2,7],"2":[7,1,7,4,7],"3":[7,1,7,1,7],"4":[5,5,7,1,1],
  "5":[7,4,7,1,7],"6":[7,4,7,5,7],"7":[7,1,2,2,2],"8":[7,5,7,5,7],"9":[7,5,7,1,7]
};
const [,, sheetFile, jsonFile, outFile, scaleArg] = process.argv;
const scale = scaleArg ? +scaleArg : 2;
const img = PNG.sync.read(fs.readFileSync(sheetFile));
const { blobs } = JSON.parse(fs.readFileSync(jsonFile, "utf8"));
const W = img.width * scale, H = img.height * scale;
const out = new PNG({ width: W, height: H });
for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
  const si = ((y/scale|0) * img.width + (x/scale|0)) * 4, di = (y * W + x) * 4;
  out.data[di] = img.data[si]; out.data[di+1] = img.data[si+1]; out.data[di+2] = img.data[si+2]; out.data[di+3] = 255;
}
const put = (x,y,r,g,b) => { if (x<0||y<0||x>=W||y>=H) return; const i=(y*W+x)*4; out.data[i]=r; out.data[i+1]=g; out.data[i+2]=b; out.data[i+3]=255; };
blobs.forEach((bl, idx) => {
  const bx = bl.x*scale, by = bl.y*scale;
  for (let x = 0; x < bl.w*scale; x++) { put(bx+x, by, 255,0,0); put(bx+x, by+bl.h*scale-1, 255,0,0); }
  for (let y = 0; y < bl.h*scale; y++) { put(bx, by+y, 255,0,0); put(bx+bl.w*scale-1, by+y, 255,0,0); }
  const s = String(idx);
  // black backing plate then yellow digits
  for (let y = -1; y < 6; y++) for (let x = -1; x < s.length*4; x++) put(bx+x, by+y, 0,0,0);
  for (let d = 0; d < s.length; d++) {
    const bm = DIGITS[s[d]];
    for (let ry = 0; ry < 5; ry++) for (let rx = 0; rx < 3; rx++)
      if (bm[ry] & (4 >> rx)) put(bx+d*4+rx, by+ry, 255,255,0);
  }
});
fs.writeFileSync(outFile, PNG.sync.write(out));
console.log(`${outFile}: ${blobs.length} blobs annotated at ${scale}x`);
