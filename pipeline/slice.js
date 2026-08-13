// Auto-slice irregular sprite sheets: find connected non-background blobs,
// merge near-touching ones, emit JSON + numbered contact sheet for visual mapping.
const fs = require("fs");
const { PNG } = require("pngjs");

const DIGITS = { // 3x5 digit bitmaps for labeling cells
  "0":[7,5,5,5,7],"1":[2,6,2,2,7],"2":[7,1,7,4,7],"3":[7,1,7,1,7],"4":[5,5,7,1,1],
  "5":[7,4,7,1,7],"6":[7,4,7,5,7],"7":[7,1,2,2,2],"8":[7,5,7,5,7],"9":[7,5,7,1,7]
};

function load(p) { return PNG.sync.read(fs.readFileSync(p)); }
function px(img, x, y) { const i = (y * img.width + x) * 4; return [img.data[i], img.data[i+1], img.data[i+2], img.data[i+3]]; }
function same(a, b, tol) { return Math.abs(a[0]-b[0])<=tol && Math.abs(a[1]-b[1])<=tol && Math.abs(a[2]-b[2])<=tol; }

function slice(file, out, opts = {}) {
  const img = load(file);
  const { width: W, height: H } = img;
  // background = most frequent color among border pixels
  const counts = {};
  for (let x = 0; x < W; x++) for (const y of [0, H-1]) { const c = px(img,x,y).slice(0,3).join(","); counts[c] = (counts[c]||0)+1; }
  for (let y = 0; y < H; y++) for (const x of [0, W-1]) { const c = px(img,x,y).slice(0,3).join(","); counts[c] = (counts[c]||0)+1; }
  const bg = Object.entries(counts).sort((a,b) => b[1]-a[1])[0][0].split(",").map(Number);
  const tol = opts.tol ?? 8;
  const isBg = (x,y) => { const c = px(img,x,y); return c[3] < 40 || same(c, bg, tol); };

  // connected components, 8-connectivity, iterative flood
  const seen = new Uint8Array(W*H);
  let blobs = [];
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    if (seen[y*W+x] || isBg(x,y)) continue;
    let minX=x, maxX=x, minY=y, maxY=y, n=0;
    const stack = [[x,y]]; seen[y*W+x] = 1;
    while (stack.length) {
      const [cx,cy] = stack.pop(); n++;
      if (cx<minX)minX=cx; if (cx>maxX)maxX=cx; if (cy<minY)minY=cy; if (cy>maxY)maxY=cy;
      for (let dy=-1; dy<=1; dy++) for (let dx=-1; dx<=1; dx++) {
        const nx=cx+dx, ny=cy+dy;
        if (nx<0||ny<0||nx>=W||ny>=H||seen[ny*W+nx]||isBg(nx,ny)) continue;
        seen[ny*W+nx]=1; stack.push([nx,ny]);
      }
    }
    if (n >= (opts.minPix ?? 12)) blobs.push({x:minX, y:minY, w:maxX-minX+1, h:maxY-minY+1, n});
  }
  // merge blobs whose bboxes (expanded by gap) intersect
  const gap = opts.gap ?? 3;
  let merged = true;
  while (merged) {
    merged = false;
    outer: for (let i = 0; i < blobs.length; i++) for (let j = i+1; j < blobs.length; j++) {
      const a = blobs[i], b = blobs[j];
      if (a.x - gap < b.x + b.w && b.x - gap < a.x + a.w && a.y - gap < b.y + b.h && b.y - gap < a.y + a.h) {
        const nx = Math.min(a.x,b.x), ny = Math.min(a.y,b.y);
        blobs[i] = { x:nx, y:ny, w:Math.max(a.x+a.w,b.x+b.w)-nx, h:Math.max(a.y+a.h,b.y+b.h)-ny, n:a.n+b.n };
        blobs.splice(j,1); merged = true; break outer;
      }
    }
  }
  // sort into row bands (top edge within band height) then by x
  blobs.sort((a,b) => a.y - b.y);
  const rows = [];
  for (const b of blobs) {
    const row = rows.find(r => b.y < r.yMax);
    if (row) { row.items.push(b); row.yMax = Math.max(row.yMax, b.y + b.h); }
    else rows.push({ yMax: b.y + b.h, items: [b] });
  }
  blobs = [];
  for (const r of rows) { r.items.sort((a,b) => a.x - b.x); blobs.push(...r.items); }

  fs.writeFileSync(out + ".json", JSON.stringify({ file, bg, blobs }, null, 1));

  // numbered contact sheet: grid cells sized to max blob, 10 per row, 2x scale, index stamped top-left
  const cols = opts.cols ?? 10, scale = opts.scale ?? 2;
  const cw = Math.max(...blobs.map(b=>b.w)) + 4, ch = Math.max(...blobs.map(b=>b.h)) + 10;
  const gw = cols * cw * scale, gh = Math.ceil(blobs.length / cols) * ch * scale;
  const sheet = new PNG({ width: gw, height: gh });
  sheet.data.fill(40);
  const put = (x,y,r,g,b) => { if (x<0||y<0||x>=gw||y>=gh) return; const i=(y*gw+x)*4; sheet.data[i]=r; sheet.data[i+1]=g; sheet.data[i+2]=b; sheet.data[i+3]=255; };
  blobs.forEach((b, idx) => {
    const gx = (idx % cols) * cw, gy = Math.floor(idx / cols) * ch;
    // checker border per cell
    for (let x = 0; x < cw; x++) for (const yy of [0, ch-1]) put((gx+x)*scale, (gy+yy)*scale, 90, 90, 90);
    for (let sy = 0; sy < b.h; sy++) for (let sx = 0; sx < b.w; sx++) {
      const c = px(img, b.x+sx, b.y+sy);
      if (c[3] < 40 || same(c, bg, tol)) continue;
      for (let py = 0; py < scale; py++) for (let pxs = 0; pxs < scale; pxs++)
        put((gx+2+sx)*scale+pxs, (gy+8+sy)*scale+py, c[0], c[1], c[2]);
    }
    // stamp index digits
    const s = String(idx);
    for (let d = 0; d < s.length; d++) {
      const bm = DIGITS[s[d]];
      for (let ry = 0; ry < 5; ry++) for (let rx = 0; rx < 3; rx++)
        if (bm[ry] & (4 >> rx))
          for (let py = 0; py < scale; py++) for (let pxs = 0; pxs < scale; pxs++)
            put((gx+1+d*4+rx)*scale+pxs, (gy+1+ry)*scale+py, 255, 255, 0);
    }
  });
  fs.writeFileSync(out + ".png", PNG.sync.write(sheet));
  console.log(`${file}: ${blobs.length} sprites, bg=${bg}, contact=${out}.png`);
}

const [,, file, out, tol, gap] = process.argv;
slice(file, out, { tol: tol ? +tol : undefined, gap: gap ? +gap : undefined });
