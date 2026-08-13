// ZAMN - Python Edition bootstrap: Pyodide + assets + keyboard + audio glue.
"use strict";
const statusEl = document.getElementById("status");
const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

const K_UP = 1073741906, K_DOWN = 1073741905, K_LEFT = 1073741904, K_RIGHT = 1073741903;

window._gameCanvas = canvas;
window._events = [];
window._keys = {};
window._keyState = function (k) { return window._keys[k] ? 1 : 0; };
window._shift = false;
window._ctrl = false;
window._images = {};
window._getImage = function (name) { return window._images[name] || null; };

function mapKey(e) {
    const c = e.code;
    if (e.key === "|") return 124;
    if (c.startsWith("Arrow")) {
        if (c === "ArrowUp") return K_UP;
        if (c === "ArrowDown") return K_DOWN;
        if (c === "ArrowLeft") return K_LEFT;
        return K_RIGHT;
    }
    if (c.startsWith("Key")) return (c.charCodeAt(3) | 32); // lowercase a-z (pygame K_a..K_z)
    if (c.startsWith("Digit")) return 48 + parseInt(c.slice(5), 10);
    if (c.startsWith("Numpad")) {
        const n = c.slice(6);
        if (n === "Decimal") return 266;
        if (n === "Enter") return 13;
        const d = parseInt(n, 10);
        if (!isNaN(d)) return d === 0 ? 256 : 256 + d;
        return 0;
    }
    switch (c) {
        case "Enter": return 13;
        case "Escape": return 27;
        case "Space": return 32;
        case "Backspace": return 8;
        case "Period": return 46;
        case "Minus": return 45;
        case "Slash": return 47;
    }
    return e.key ? e.key.charCodeAt(0) : 0;
}

window.addEventListener("keydown", e => {
    const k = mapKey(e);
    if (!k) return;
    window._shift = e.shiftKey;
    window._ctrl = e.ctrlKey;
    if (!window._keys[k]) {
        window._keys[k] = 1;
        window._events.push({ type: 768, key: k, x: 0, y: 0, relx: 0, rely: 0, button: 0, y_wheel: 0 });
    }
    if (["Space", "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.code)) e.preventDefault();
    if (window._audio && window._audio.state === "suspended") {
        window._audio.resume().catch(() => {});
    }
});
window.addEventListener("keyup", e => {
    const k = mapKey(e);
    if (!k) return;
    window._shift = e.shiftKey;
    window._ctrl = e.ctrlKey;
    window._keys[k] = 0;
    window._events.push({ type: 769, key: k, x: 0, y: 0, relx: 0, rely: 0, button: 0, y_wheel: 0 });
});

// ---- mouse (aim + fire + weapon wheel) ----
canvas.addEventListener("contextmenu", e => { e.preventDefault(); });
window._mousePos = { x: 0, y: 0 };
window._mouseBtns = [0, 0, 0];
window._mouseIn = false;

function scaleMouse(e) {
    const r = canvas.getBoundingClientRect();
    const scale = Math.max(1e-3, Math.min(r.width / canvas.width, r.height / canvas.height));
    const cw = canvas.width * scale;
    const ch = canvas.height * scale;
    const ox = (r.width - cw) / 2;
    const oy = (r.height - ch) / 2;
    return {
        x: (e.clientX - r.left - ox) / scale,
        y: (e.clientY - r.top - oy) / scale,
    };
}

canvas.addEventListener("mousemove", e => {
    const p = scaleMouse(e);
    window._mousePos.x = p.x;
    window._mousePos.y = p.y;
    window._mouseIn = true;
    window._events.push({ type: 1024, x: p.x, y: p.y, relx: 0, rely: 0, button: 0, y_wheel: 0 });
});
canvas.addEventListener("mousedown", e => {
    const p = scaleMouse(e);
    ensureAudio();
    if (window._audio && window._audio.state === "suspended") window._audio.resume().catch(() => {});
    if (e.button >= 0 && e.button < window._mouseBtns.length) window._mouseBtns[e.button] = 1;
    window._events.push({ type: 1025, x: p.x, y: p.y, relx: 0, rely: 0, button: e.button + 1, y_wheel: 0 });
    e.preventDefault();
});
window.addEventListener("mouseup", e => {
    if (e.button >= 0 && e.button < window._mouseBtns.length) window._mouseBtns[e.button] = 0;
    window._events.push({ type: 1026, x: 0, y: 0, relx: 0, rely: 0, button: e.button + 1, y_wheel: 0 });
});
canvas.addEventListener("wheel", e => {
    const dy = e.deltaY < 0 ? 1 : e.deltaY > 0 ? -1 : 0;
    if (dy) window._events.push({ type: 1027, x: 0, y: 0, relx: 0, rely: 0, button: 0, y_wheel: dy });
    e.preventDefault();
}, { passive: false });
canvas.addEventListener("mouseleave", () => {
    window._mouseIn = false;
});

// ---- canvas helpers used by the pygame shim ----
window._pxReplace = function (cv, r, g, b, a, nr, ng, nb, na) {
    const c = cv.getContext("2d");
    const img = c.getImageData(0, 0, cv.width, cv.height);
    const d = img.data;
    for (let i = 0; i < d.length; i += 4) {
        if (d[i] === r && d[i + 1] === g && d[i + 2] === b && d[i + 3] === a) {
            d[i] = nr; d[i + 1] = ng; d[i + 2] = nb; d[i + 3] = na;
        }
    }
    c.putImageData(img, 0, 0);
};

window._blendMin = function (dst, src) {
    const dc = dst.getContext("2d");
    const sc = src.getContext("2d");
    const di = dc.getImageData(0, 0, dst.width, dst.height);
    const si = sc.getImageData(0, 0, src.width, src.height);
    const dd = di.data, sd = si.data;
    for (let i = 3; i < dd.length; i += 4) {
        if (sd[i] === 0) dd[i] = 0;
    }
    dc.putImageData(di, 0, 0);
};

window._makeImageData = function (data, w, h) {
    return new ImageData(new Uint8ClampedArray(data), w, h);
};

window._keyedCanvas = function (bmp, keyMode) {
    const c = document.createElement("canvas");
    c.width = bmp.width;
    c.height = bmp.height;
    const cx = c.getContext("2d");
    cx.drawImage(bmp, 0, 0);
    if (keyMode) {
        const img = cx.getImageData(0, 0, c.width, c.height);
        const d = img.data;
        const kr = d[0], kg = d[1], kb = d[2];
        for (let i = 0; i < d.length; i += 4) {
            const r = d[i], g = d[i + 1], b = d[i + 2];
            let key = (r === kr && g === kg && b === kb);
            if (!key && keyMode === 2) {
                key = (Math.abs(r - 8) <= 26 && Math.abs(g - 176) <= 26 && Math.abs(b - 120) <= 26) ||
                      (Math.abs(r - 8) <= 20 && Math.abs(g - 112) <= 20 && Math.abs(b - 80) <= 20);
            }
            if (key) d[i + 3] = 0;
        }
        cx.putImageData(img, 0, 0);
    }
    return c;
};

window._recolorCanvas = function (cv, tr, tg, tb) {
    const c = document.createElement("canvas");
    c.width = cv.width;
    c.height = cv.height;
    const cx = c.getContext("2d");
    cx.drawImage(cv, 0, 0);
    const img = cx.getImageData(0, 0, c.width, c.height);
    const d = img.data;
    for (let i = 0; i < d.length; i += 4) {
        const a = d[i + 3];
        if (a < 40) continue;
        const r = d[i], g = d[i + 1], b = d[i + 2];
        const lum = r * 0.3 + g * 0.6 + b * 0.1;
        const isSkin = r > 170 && g > 120 && g < 215 && b < 190 && r > b + 40;
        if (isSkin || lum < 55) continue;
        d[i] = r + (tr - r) * 0.55;
        d[i + 1] = g + (tg - g) * 0.55;
        d[i + 2] = b + (tb - b) * 0.55;
    }
    cx.putImageData(img, 0, 0);
    return c;
};

// character creator recolor: mirror of build_custom_tex (parts by vertical
// region of each walk frame; hair colors, skin and outlines stay).
window._recolorCustomCanvas = function (bmp, params, zeke_rects, julie_rects, zeke_hair, julie_hair, palette) {
    const c = document.createElement("canvas");
    c.width = bmp.width;
    c.height = bmp.height;
    const cx = c.getContext("2d");
    cx.drawImage(bmp, 0, 0);
    const img = cx.getImageData(0, 0, c.width, c.height);
    const d = img.data;
    const W = c.width;
    const sexo = params[0];
    const zekeLike = sexo === 0 || sexo === 2 || sexo === 4;
    const rects = zekeLike ? zeke_rects : julie_rects;
    const hairSet = new Set((zekeLike ? zeke_hair : julie_hair).map(c2 => (c2[0] << 16) | (c2[1] << 8) | c2[2]));
    const targets = [palette[0][params[1]], palette[1][params[2]], palette[2][params[3]], palette[3][params[4]]];
    const isSkin = (r, g, b) => {
        if (r > 165 && g > 110 && g < 220 && b > 45 && b < 200) {
            if (r > b + 30 && b < r * 0.62) {
                if (b >= r * 0.30 && b >= g * 0.40) return true;
                if (g > 170 && b > 150 && r > 185) return true;
            }
        }
        return false;
    };
    for (const rect of rects) {
        const x0 = rect[0], y0 = rect[1], fw = rect[2], fh = rect[3];
        for (let yy = 0; yy < fh; yy++) {
            const ly = yy / fh;
            let part = ly < 0.30 ? 0 : (ly < 0.62 ? 1 : (ly < 0.86 ? 2 : 3));
            for (let xx = 0; xx < fw; xx++) {
                const i = ((y0 + yy) * W + (x0 + xx)) * 4;
                const a = d[i + 3];
                if (a < 40) continue;
                const r = d[i], g = d[i + 1], b = d[i + 2];
                const lum = r * 0.3 + g * 0.6 + b * 0.1;
                if (hairSet.has((r << 16) | (g << 8) | b)) part = 0;
                else if (isSkin(r, g, b)) continue;
                else if (lum < 42) continue;
                else if (part === 0 && lum > 185) continue;
                const f = 0.35 + 0.78 * lum / 255.0;
                const t = targets[part];
                d[i] = Math.min(255, Math.floor(t[0] * f));
                d[i + 1] = Math.min(255, Math.floor(t[1] * f));
                d[i + 2] = Math.min(255, Math.floor(t[2] * f));
            }
        }
    }
    cx.putImageData(img, 0, 0);
    return c;
};

// ---- lobby directory relay polling ----
window._lobbies = [];
window._apiPing = 0;
window._announceLobby = async function (lobby) {
    try {
        await fetch("/api/announce", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(lobby),
            cache: "no-store"
        });
    } catch (e) {
        // The lobby can still run locally if the directory is unavailable.
    }
};
async function pollLobbies() {
    try {
        const t0 = performance.now();
        const r = await fetch("/api/lobbies", { cache: "no-store" });
        window._apiPing = Math.round(performance.now() - t0);
        window._lobbies = await r.json();
    } catch (e) {
        window._lobbies = [];
    }
}
window._refreshLobbies = pollLobbies;
setInterval(pollLobbies, 2000);
pollLobbies();

// ---- global design gallery helpers (mirror of the native urllib path) ----
window._gGalState = "idle";       // idle/loading/done/error (list)
window._gGalDataState = "idle";   // idle/loading/done/error (single design)
window._gGalList = [];
window._gGalId = null;
window._gGalPng = null;           // b64 of the PNG bytes
window._gGalRGB = null;           // b64 RGBA pixels (filled by async PNG decode)
window._gGalDim = null;           // "WxH" of the decoded image
window._gUpState = 0;             // 0 idle 1 uploading 2 ok 3 error

window._refreshDesigns = async function () {
    window._gGalState = "loading";
    try {
        const r = await fetch("/api/designs", { cache: "no-store" });
        window._gGalList = await r.json();
        window._gGalState = "done";
    } catch (e) {
        window._gGalState = "error";
    }
};

window._getDesign = async function (id) {
    window._gGalDataState = "loading";
    window._gGalPng = null;
    window._gGalRGB = null;
    window._gGalDim = null;
    try {
        const r = await fetch("/api/designs/" + encodeURIComponent(id), { cache: "no-store" });
        if (!r.ok) throw new Error("not found");
        const b8 = new Uint8Array(await r.arrayBuffer());
        let bin = "";
        for (let i = 0; i < b8.length; i++) bin += String.fromCharCode(b8[i]);
        const b64 = btoa(bin);
        window._gGalId = id;
        window._gGalPng = b64;
        const img = new Image();
        img.onload = function () {
            const c = document.createElement("canvas");
            c.width = img.width;
            c.height = img.height;
            const cx = c.getContext("2d");
            cx.drawImage(img, 0, 0);
            const d = cx.getImageData(0, 0, c.width, c.height).data;
            let s = "";
            for (let i = 0; i < d.length; i++) s += String.fromCharCode(d[i]);
            window._gGalRGB = btoa(s);
            window._gGalDim = c.width + "x" + c.height;
            window._gGalDataState = "done";
        };
        img.onerror = function () { window._gGalDataState = "error"; };
        img.src = "data:image/png;base64," + b64;
    } catch (e) {
        window._gGalDataState = "error";
    }
};

window._uploadDesign = async function (name, pngB64) {
    window._gUpState = 1;
    try {
        const r = await fetch("/api/designs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: name, png: pngB64 })
        });
        const o = await r.json();
        window._gUpState = (o && o.ok) ? 2 : 3;
    } catch (e) {
        window._gUpState = 3;
    }
};

// ---- audio (WebAudio, Resident Evil style PCM) ----
let soundNodes = [];
window._audio = null;

function ensureAudio() {
    if (!window._audio) {
        try {
            window._audio = new AudioContext();
        } catch (e) {
            window._audio = null;
        }
    }
    if (window._audio && window._audio.state === "suspended") window._audio.resume().catch(() => {});
    return window._audio;
}

window._playPCM = function (data, loops, vol) {
    const actx = ensureAudio();
    if (!actx) return;
    const n = data.length / 2;
    const buf = actx.createBuffer(1, n, 48000);
    const ch = buf.getChannelData(0);
    const dv = new DataView(data.buffer || data, data.byteOffset || 0, data.byteLength);
    for (let i = 0; i < n; i++) ch[i] = dv.getInt16(i * 2, true) / 32768;
    const src = actx.createBufferSource();
    src.buffer = buf;
    if (loops < 0) src.loop = true;
    const gain = actx.createGain();
    gain.gain.value = vol;
    src.connect(gain);
    gain.connect(actx.destination);
    src.start();
    soundNodes.push(src);
};

window._stopAll = function () {
    for (const s of soundNodes) {
        try { s.stop(); } catch (e) {}
    }
    soundNodes = [];
};

// ---- boot ----
async function boot() {
    try {
        statusEl.textContent = "cargando python (pyodide)...";
        const pyodide = await loadPyodide();
        window.pyodide = pyodide;

        statusEl.textContent = "cargando assets...";
        const names = ["zeke.png", "julie.png", "zombie.png", "victims.png", "items.png",
                       "exitdoor.png", "level_big.png", "level2_big.png", "level3_big.png", "level4_big.png",
                       "level5_big.png", "level6_big.png", "rex.png", "weapon_rifle.png",
                       "weapon_shotgun.png", "weapon_smg.png", "weapon_pistol.png", "weapon_magnum.png",
                       "weapon_minigun.png", "weapon_flamethrower.png", "weapon_rocket.png", "weapon_ray.png"];
        for (const n of names) {
            statusEl.textContent = "cargando asset " + n + "...";
            const blob = await (await fetch("/ZamnNative/assets/" + n)).blob();
            window._images[n] = await createImageBitmap(blob);
        }
        const templates = ["1_ZEKErojo.png", "1_ZEKE_rojo.png", "2_JULIE_rojo.png",
                           "3_RUSTY_rojo.png", "4_AZURA_rojo.png", "5_DANTE_rojo.png"];
        for (const n of templates) {
            if (window._images[n]) continue;
            const blob = await (await fetch("/plantillas_personajes/" + n)).blob();
            window._images[n] = await createImageBitmap(blob);
        }
        statusEl.textContent = "preparando filesystem...";
        const walk = await (await fetch("/ZamnNative/assets/walk_big.bin")).arrayBuffer();
        const walk2 = await (await fetch("/ZamnNative/assets/walk2_big.bin")).arrayBuffer();
        pyodide.FS.mkdir("/assets");
        pyodide.FS.writeFile("/assets/walk_big.bin", new Uint8Array(walk));
        pyodide.FS.writeFile("/assets/walk2_big.bin", new Uint8Array(walk2));
        for (let i = 3; i <= 6; i++) {
            const wi = await (await fetch("/ZamnNative/assets/walk" + i + "_big.bin")).arrayBuffer();
            pyodide.FS.writeFile("/assets/walk" + i + "_big.bin", new Uint8Array(wi));
        }
        for (const n of names) pyodide.FS.writeFile("/assets/" + n, new Uint8Array(0));

        statusEl.textContent = "cargando modulos python...";
        const files = ["/zamn_font.py", "/zamn.py"];
        for (const f of files) {
            const src = await (await fetch(f + "?v=71")).text();
            pyodide.FS.writeFile("/" + f.split("/").pop(), src);
        }
        const shim = await (await fetch("pygame.py?v=71")).text();
        pyodide.FS.writeFile("/pygame.py", shim);
        statusEl.textContent = "arrancando juego...";
        await pyodide.runPythonAsync(
            "import sys; sys.path.insert(0, '/'); import pygame; import zamn; zamn.web_boot()"
        );
        statusEl.textContent = "juego corriendo";
        let last = performance.now();
        const step = (now) => {
            window._dtMs = now - last;
            last = now;
            try {
                pyodide.runPython("zamn.frame()");
            } catch (e) {
                console.error("[ZAMN FRAME]", e);
                statusEl.textContent = "error: " + (e && e.message ? e.message : e);
                return;
            }
            requestAnimationFrame(step);
        };
        requestAnimationFrame(step);
        window._frameLoop = true;
    } catch (err) {
        console.error("[ZAMN BOOT]", err);
        statusEl.textContent = "error: " + (err && err.message ? err.message : err);
    }
}

boot();
