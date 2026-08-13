const fs = require("fs");
const { PNG } = require("pngjs");
const img = PNG.sync.read(fs.readFileSync(process.argv[2]));
const counts = {};
for (let i = 0; i < img.data.length; i += 4) {
  const c = img.data[i] + "," + img.data[i+1] + "," + img.data[i+2];
  counts[c] = (counts[c] || 0) + 1;
}
const total = img.width * img.height;
Object.entries(counts).sort((a,b) => b[1]-a[1]).slice(0, 25)
  .forEach(([c, n]) => console.log(c.padEnd(15), (100*n/total).toFixed(2) + "%"));
console.log("size:", img.width, "x", img.height, "unique:", Object.keys(counts).length);
