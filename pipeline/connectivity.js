const fs = require("fs");
const g = fs.readFileSync("walk_big.bin");
const TW = 132, TH = 78;
const idx = (x, y) => y * TW + x;
// flood from spawn tile (21,37)
const seen = new Uint8Array(TW * TH);
const q = [idx(21, 37)];
if (!g[q[0]]) console.log("spawn tile blocked!");
seen[q[0]] = 1;
let n = 0;
while (q.length) {
  const c = q.pop(); n++;
  const cx = c % TW, cy = (c / TW) | 0;
  for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
    const nx = cx + dx, ny = cy + dy;
    if (nx < 0 || ny < 0 || nx >= TW || ny >= TH) continue;
    const i = idx(nx, ny);
    if (seen[i] || !g[i]) continue;
    seen[i] = 1; q.push(i);
  }
}
let walk = 0;
for (let i = 0; i < TW * TH; i++) walk += g[i];
console.log(`walkable ${walk}, reachable from spawn ${n} (${(100*n/walk).toFixed(1)}%)`);
for (const [x, y, name] of [[14,41,"bot"],[15,44,"kidV5"],[38,29,"V2"],[110,26,"V10 area"],[15,60,"V14"],[110,60,"T4 spawn"]])
  console.log(name, x, y, "walk=", g[idx(x,y)], "reach=", seen[idx(x,y)]);
// largest disconnected regions
const seen2 = new Uint8Array(TW * TH);
const regions = [];
for (let s = 0; s < TW * TH; s++) {
  if (!g[s] || seen2[s] || seen[s]) continue;
  let cnt = 0; const st = [s]; seen2[s] = 1;
  const sample = s;
  while (st.length) {
    const c = st.pop(); cnt++;
    const cx = c % TW, cy = (c / TW) | 0;
    for (const [dx, dy] of [[1,0],[-1,0],[0,1],[0,-1]]) {
      const nx = cx + dx, ny = cy + dy;
      if (nx < 0 || ny < 0 || nx >= TW || ny >= TH) continue;
      const i = idx(nx, ny);
      if (seen2[i] || seen[i] || !g[i]) continue;
      seen2[i] = 1; st.push(i);
    }
  }
  regions.push([cnt, sample % TW, (sample / TW) | 0]);
}
regions.sort((a, b) => b[0] - a[0]);
console.log("disconnected regions:", regions.length, "largest:", regions.slice(0, 8).map(r => `${r[0]}t@(${r[1]},${r[2]})`).join(" "));
