#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ZAMN - Editor de Mapas (green glass UI, estilo editor de StarCraft)
# Vista fullscreen; el mapa se ve como en el juego (480x270 a escala 1:1).
# Pincel pinta la muralla (capa 2); guardar escribe las capas PNG + zamn.py.

import sys, os, json, math, ast, shutil, datetime, io, base64
import tkinter as tk
import tkinter.simpledialog as sd
from PIL import Image, ImageTk, ImageDraw
import urllib.request, urllib.error

if getattr(sys, "frozen", False):
    ROOT = os.path.dirname(sys.executable)
else:
    ROOT = os.path.dirname(os.path.abspath(__file__))
# Locate the project root (folder that holds ZamnNative/assets) whether the
# script runs from the root, from a sub-folder, or as a frozen exe in root.
while not os.path.isdir(os.path.join(ROOT, "ZamnNative", "assets")):
    parent = os.path.dirname(ROOT)
    if parent == ROOT:
        break
    ROOT = parent
ASSETS = os.path.join(ROOT, "ZamnNative", "assets")
ZAMN_PY = os.path.join(ROOT, "zamn.py")
JSON_OUT = os.path.join(ROOT, "mapa_layouts.json")
SITE = os.environ.get("ZAMN_SITE", "http://zombicito.duckdns.org:7070")

TS = 16
MAP_W, MAP_H = 2528, 1504
TW, TH = MAP_W // TS, MAP_H // TS
GAME_W, GAME_H = 480, 270

LEVELS = 6
NAMES = ["SUBURBIOS DIA", "SUBURBIOS NOCHE", "FABRICA", "PANTANO", "CASTILLO", "BASE MILITAR"]
TEAM_COLORS = ["#7dff4f", "#ff5c5c", "#63b0ff", "#ffe34d"]
TEAM_NAMES = ["GREEN", "RED", "BLUE", "YELLOW"]
VICT_COLORS = ["#ffd75e", "#ff8a5c", "#9dffab", "#6fd8ff", "#ff7ae0", "#c9a1ff", "#ff6f6f", "#8be8e0"]

GL_BG = "#0a170a"
LEVEL_KEYS = {
    0: ("VSPOTS_DAY", "TSPAWN_DAY", "MEDKITS_DAY"),
    1: ("VSPOTS2", "TSPAWN2", "MEDKITS2"),
    2: ("VSPOTS3", "TSPAWN3", "MEDKITS3"),
    3: ("VSPOTS4", "TSPAWN4", "MEDKITS4"),
    4: ("VSPOTS5", "TSPAWN5", "MEDKITS5"),
    5: ("VSPOTS6", "TSPAWN6", "MEDKITS6"),
}

TOOLS = [
    ("sel", "SELECCIONAR", "flecha / mover"),
    ("paint", "PINCEL MURALLA", "pinta muro (capa 2)"),
    ("erase", "BORRAR MURALLA", "borra muro (caminable)"),
    ("spawn", "+ SPAWN", "click coloca spawn"),
    ("victim", "+ VICTIMA", "click coloca victima"),
    ("medkit", "+ MEDKIT", "click coloca medkit"),
]


class LevelData:
    def __init__(self, n):
        self.n = n
        self.spawns = []
        self.victims = []
        self.medkits = []
        self.bounce = []


# ---------------- data ----------------
def parse_zamn():
    src = open(ZAMN_PY, encoding="utf-8").read()
    tree = ast.parse(src)
    consts = {}
    door = (480.0, 78.0)
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                consts[node.targets[0].id] = node.value
            elif all(isinstance(t, ast.Name) for t in node.targets) and isinstance(node.value, ast.Tuple):
                for t, e in zip(node.targets, node.value.elts):
                    if isinstance(e, ast.Constant):
                        consts[t.id] = e.value
    if "gDoorX" in consts and "gDoorY" in consts:
        door = (float(consts["gDoorX"]), float(consts["gDoorY"]))
    def get_list(name):
        v = consts.get(name)
        if v is None:
            return []
        if isinstance(v, ast.Call) and v.args and isinstance(v.args[0], ast.Name):
            v = consts.get(v.args[0].id)
        if not isinstance(v, ast.List):
            return []
        out = []
        for el in v.elts:
            if isinstance(el, ast.Tuple):
                out.append(tuple(e.value for e in el.elts if isinstance(e, ast.Constant)))
            elif isinstance(el, ast.List):
                inner = []
                for e2 in el.elts:
                    if isinstance(e2, ast.Tuple):
                        inner.append(tuple(e.value for e in e2.elts if isinstance(e, ast.Constant)))
                out.append(inner)
        return out
    levels = []
    for n in range(LEVELS):
        vk, tk_, mk = LEVEL_KEYS[n]
        L = LevelData(n)
        L.victims = [tuple(v) for v in get_list(vk)]
        L.spawns = [tuple(v) for v in get_list(tk_)]
        L.medkits = [tuple(v) for v in get_list(mk)]
        levels.append(L)
    bounce = get_list("BOUNCE_LAYOUT")
    for i, L in enumerate(levels):
        if i < len(bounce) and bounce[i]:
            L.bounce = [tuple(bounce[i][0])]
    return levels, door


def load_capa2(n):
    p = os.path.join(ASSETS, "level%d_snes_upper.png" % (n + 1))
    if os.path.exists(p):
        return Image.open(p).convert("RGBA")
    p1 = os.path.join(ASSETS, "level%d_snes.png" % (n + 1))
    base = Image.open(p1).convert("RGBA") if os.path.exists(p1) else Image.new("RGBA", (1280, 720))
    return Image.new("RGBA", base.size, (0, 0, 0, 0))


def mask_from_capa2(img):
    w, h = img.size
    stw, sth = w // TS, h // TS
    b = img.tobytes()
    m = bytearray(stw * sth)
    for ty in range(sth):
        for tx in range(stw):
            wall = False
            for dy in range(TS):
                row = ((ty * TS + dy) * w + tx * TS) * 4 + 3
                if max(b[row:row + TS * 4:4]) > 200:
                    wall = True
                    break
            m[ty * stw + tx] = 0 if wall else 1
    return m


def expand_mask(m, stw, sth):
    out = bytearray(TW * TH)
    for ty in range(TH):
        sy = min(sth - 1, int(ty * sth / TH))
        for tx in range(TW):
            sx = min(stw - 1, int(tx * stw / TW))
            out[ty * TW + tx] = m[sy * stw + sx]
    return out


def edge_tiles(mask):
    out = []
    for ty in range(1, TH - 1):
        for tx in range(1, TW - 1):
            if not mask[ty * TW + tx]:
                continue
            if not (mask[ty * TW + tx - 1] and mask[ty * TW + tx + 1] and
                    mask[(ty - 1) * TW + tx] and mask[(ty + 1) * TW + tx]):
                out.append((tx, ty))
    return out


# ---------------- green glass ----------------
_glass_cache = {}


def glass_image(w, h, state="normal", r=12):
    key = (w, h, state, r)
    if key in _glass_cache:
        return _glass_cache[key]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
    base = Image.new("RGBA", (w, h))
    d = ImageDraw.Draw(base)
    for y in range(h):
        t = y / max(1, h - 1)
        col = (int(24 + 22 * (1 - t)), int(58 + 30 * (1 - t)), int(26 + 16 * (1 - t)), 255)
        d.line([(0, y), (w, y)], fill=col)
    if state == "hover":
        sheen = Image.new("RGBA", (w, h))
        sd = ImageDraw.Draw(sheen)
        for y in range(h):
            t = y / max(1, h - 1)
            sd.line([(0, y), (w, y)], fill=(120, 255, 150, int(120 * (1 - t) * 0.55)))
        base.alpha_composite(sheen)
    elif state == "pressed":
        base = base.point(lambda v: max(0, v - 28))
    img.paste(base, (0, 0), mask)
    d2 = ImageDraw.Draw(img)
    d2.rounded_rectangle([0, 0, w - 1, h - 1], radius=r, outline=(150, 255, 170, 190), width=1)
    d2.rounded_rectangle([3, 3, w - 4, max(4, h // 2)], radius=max(2, r - 4),
                         outline=(255, 255, 255, 45), width=1)
    _glass_cache[key] = img
    return img


class Glass:
    FONT = ("Segoe UI", 10, "bold")
    FONT_SM = ("Segoe UI", 9)
    FONT_T = ("Segoe UI", 14, "bold")

    @staticmethod
    def panel(cv, x, y, w, h, r=14):
        img = glass_image(w, h, "normal", r)
        ph = ImageTk.PhotoImage(img)
        cv._keep.append(ph)
        return cv.create_image(x, y, image=ph, anchor="nw")

    @staticmethod
    def label(cv, x, y, text, color="#d7ffd7", font=None, anchor="w"):
        return cv.create_text(x, y, text=text, fill=color,
                              font=font or Glass.FONT_SM, anchor=anchor)


class GlassButton:
    def __init__(self, cv, x, y, w, h, text, command=None, color="#c8ffc8",
                 font=None, checked=False, group=None, enabled=True):
        self.cv = cv
        self.x, self.y, self.w, self.h = x, y, w, h
        self.text = text
        self.command = command
        self.color = color
        self.font = font or Glass.FONT_SM
        self.checked = checked
        self.group = group
        self.enabled = enabled
        self._img = None
        self._hover = False
        self.draw()
        cv.tag_bind(self._item, "<Enter>", lambda e: self._set_hover(True))
        cv.tag_bind(self._item, "<Leave>", lambda e: self._set_hover(False))
        cv.tag_bind(self._item, "<Button-1>", lambda e: self._click())

    def draw(self):
        if self._img is not None:
            self.cv.delete(self._item)
            self.cv.delete(self._txt)
        state = "pressed" if (self.checked and self.group) else ("hover" if self._hover else "normal")
        if not self.enabled:
            state = "normal"
        img = glass_image(self.w, self.h, state)
        self._img = ImageTk.PhotoImage(img)
        self.cv._keep.append(self._img)
        self._item = self.cv.create_image(self.x, self.y, image=self._img, anchor="nw", tags=("btn",))
        col = self.color if self.enabled else "#6f8f6f"
        if self.checked and self.group:
            col = "#9dffab"
        self._txt = self.cv.create_text(self.x + self.w // 2, self.y + self.h // 2,
                                        text=self.text, fill=col, font=self.font)

    def _set_hover(self, v):
        if not self.enabled:
            return
        self._hover = v
        self.draw()

    def _click(self):
        if not self.enabled:
            return
        if self.group is not None:
            for b in self.group:
                b.checked = (b is self)
                b.draw()
        if self.command:
            self.command()

    def set_enabled(self, v):
        self.enabled = v
        self.draw()


class GlassToggle:
    def __init__(self, cv, x, y, w, h, text, on, command=None, color="#b8ffb8"):
        self.cv = cv
        self.on = on
        self.command = command
        self.btn = GlassButton(cv, x, y, w, h, "", command=self._click, color=color)
        self._led = cv.create_oval(x + 8, y + h // 2 - 4, x + 16, y + h // 2 + 4,
                                   fill="#39d353" if on else "#3a4a3a", outline="#8fe89f")
        self._txt = cv.create_text(x + 24, y + h // 2, text=text, fill=color,
                                   font=Glass.FONT_SM, anchor="w")
        cv.tag_bind(self.btn._item, "<Button-1>", lambda e: self._click())
        cv.tag_bind(self.btn._txt, "<Button-1>", lambda e: self._click())

    def _click(self):
        self.on = not self.on
        self.cv.itemconfig(self._led, fill="#39d353" if self.on else "#3a4a3a")
        if self.command:
            self.command()

    def value(self):
        return self.on


# ---------------- app ----------------
class MapEditor:
    def __init__(self, root):
        self.root = root
        root.title("ZAMN - EDITOR DE MAPAS (estilo StarCraft)")
        root.configure(bg=GL_BG)
        root.attributes("-fullscreen", True)
        self.cv = tk.Canvas(root, bg=GL_BG, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.cv._keep = []

        self.levels, self.door = parse_zamn()
        self.cur = 0
        self.scale = 1.0
        self.view_mode = "game"      # game | fit
        self.tool = "sel"
        self.brush = 1
        self.mask = [None] * LEVELS
        self.capa2 = [None] * LEVELS
        self.edges = [None] * LEVELS
        self.grid = True
        for n in range(LEVELS):
            self.capa2[n] = load_capa2(n)
            m = mask_from_capa2(self.capa2[n])
            w, h = self.capa2[n].size
            self.mask[n] = expand_mask(m, w // TS, h // TS)

        self.show = {"capa1": True, "capa2": True, "mask": False, "edges": True, "grid": True}
        self.sel = None
        self.drag = None
        self.pan = None
        self.back_ph = None
        self.map_items = {}
        self.obj_ids = {}
        self.minimap_ph = None
        self.minimap_obj = {}
        self._resize_job = None

        self.root.bind("<Control-MouseWheel>", self._wheel_zoom)
        self.root.bind("<Delete>", lambda e: self.delete_sel())
        self.root.bind("<Escape>", lambda e: self.toggle_fullscreen())
        self.root.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.root.bind("<Left>", lambda e: self._pan_by(40, 0))
        self.root.bind("<Right>", lambda e: self._pan_by(-40, 0))
        self.root.bind("<Up>", lambda e: self._pan_by(0, 40))
        self.root.bind("<Down>", lambda e: self._pan_by(0, -40))
        self.cv.bind("<Configure>", self._on_resize)
        root.after(120, self._build)

    def _on_resize(self, e):
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(150, self._build)

    def toggle_fullscreen(self):
        self.root.attributes("-fullscreen", not self.root.attributes("-fullscreen"))
        self._build()

    # ---------------- ui ----------------
    def _build(self):
        w = self.cv.winfo_width()
        h = self.cv.winfo_height()
        if w < 200 or h < 200:
            self.root.after(100, self._build)
            return
        self.cv.delete("all")
        self.cv._keep = []
        # top bar
        Glass.panel(self.cv, 8, 8, w - 16, 52, r=14)
        Glass.label(self.cv, 22, 20, "ZAMN - EDITOR DE MAPAS", "#9dffab", Glass.FONT_T)
        Glass.label(self.cv, 22, 42, "pincel pinta muralla (capa 2) - guardar escribe PNG + zamn.py", "#6fbf7a")
        self.level_btns = []
        bw = min(150, (w - 900) // LEVELS - 6)
        x0 = w - 40 - LEVELS * (bw + 8)
        for n in range(LEVELS):
            b = GlassButton(self.cv, x0 + n * (bw + 8), 20, bw, 26, "%d %s" % (n + 1, NAMES[n]),
                            command=lambda k=n: self.set_level(k), checked=(n == 0),
                            group=self.level_btns, font=("Segoe UI", 8, "bold"))
            self.level_btns.append(b)

        # left palette (StarCraft style)
        lx, ly, lw = 8, 68, 236
        Glass.panel(self.cv, lx, ly, lw, h - 120, r=14)
        Glass.label(self.cv, lx + 12, ly + 14, "HERRAMIENTAS", "#9dffab", Glass.FONT)
        self.tool_btns = []
        ty = ly + 34
        for key, lab, tip in TOOLS:
            b = GlassButton(self.cv, lx + 10, ty, lw - 20, 26, lab,
                            command=lambda k=key: self.set_tool(k), checked=(key == "sel"),
                            group=self.tool_btns, font=("Segoe UI", 8, "bold"))
            self.tool_btns.append(b)
            Glass.label(self.cv, lx + 14, ty + 14, tip, "#6fbf7a")
            ty += 34
        Glass.label(self.cv, lx + 12, ty + 4, "PINCEL", "#9dffab", Glass.FONT)
        self.brush_btns = []
        for i, bsz in enumerate((1, 2, 3)):
            b = GlassButton(self.cv, lx + 10 + i * (lw - 20) // 3 + 2, ty + 24, 66, 24, "%dx%d" % (bsz, bsz),
                            command=lambda s=bsz: self.set_brush(s), checked=(i == 0),
                            group=self.brush_btns, font=("Segoe UI", 8, "bold"))
            self.brush_btns.append(b)
        ty += 56
        Glass.label(self.cv, lx + 12, ty + 4, "CAPAS (vista 2D desde arriba)", "#9dffab", Glass.FONT)
        self.tgl_capa1 = GlassToggle(self.cv, lx + 10, ty + 24, lw - 20, 26, "Capa 1 (terreno)", True, self.re_render)
        self.tgl_capa2 = GlassToggle(self.cv, lx + 10, ty + 54, lw - 20, 26, "Capa 2 (muralla)", True, self.re_render)
        self.tgl_mask = GlassToggle(self.cv, lx + 10, ty + 84, lw - 20, 26, "Máscara caminable", False, self.re_render)
        self.tgl_edges = GlassToggle(self.cv, lx + 10, ty + 114, lw - 20, 26, "Vecinos (zombies)", True, self.re_render)
        self.tgl_grid = GlassToggle(self.cv, lx + 10, ty + 144, lw - 20, 26, "Rejilla", True, self.re_render)
        ty += 176
        Glass.label(self.cv, lx + 12, ty + 4, "VISTA", "#9dffab", Glass.FONT)
        self.view_btns = []
        for lab, mode, sc in (("JUEGO", "game", 1.0), ("COMPLETO", "fit", 0), ("50%", "zoom", 0.5),
                              ("100%", "zoom", 1.0), ("200%", "zoom", 2.0)):
            b = GlassButton(self.cv, lx + 10 + len(self.view_btns) * 44, ty + 24, 40, 24, lab,
                            command=lambda m=mode, s=sc: self.set_view(m, s), checked=(lab == "JUEGO"),
                            group=self.view_btns, font=("Segoe UI", 8, "bold"))
            self.view_btns.append(b)

        # map area (fixed 480x270 in game view, letterboxed like the game)
        mx = lx + lw + 10
        mw = w - mx - 268
        mh = h - 128
        if self.view_mode == "game":
            frame_w, frame_h = GAME_W + 4, GAME_H + 4
            self.cv.create_rectangle(mx - 2, 68 - 2, mx + frame_w + 2, 68 + frame_h + 2,
                                     fill="", outline="#39d353", width=1)
        else:
            frame_w, frame_h = mw, mh
        self.map_frame = tk.Frame(self.root, bg="#041004")
        self.cv.create_window(mx, 68, window=self.map_frame, anchor="nw", width=frame_w, height=frame_h)
        self.hsb = tk.Scrollbar(self.map_frame, orient="horizontal")
        self.vsb = tk.Scrollbar(self.map_frame, orient="vertical")
        self.mapc = tk.Canvas(self.map_frame, bg="#041004", highlightthickness=0,
                              xscrollcommand=self.hsb.set, yscrollcommand=self.vsb.set)
        self.hsb.config(command=self.mapc.xview)
        self.vsb.config(command=self.mapc.yview)
        self.vsb.pack(side="right", fill="y")
        self.hsb.pack(side="bottom", fill="x")
        self.mapc.pack(side="left", fill="both", expand=True)
        self.mapc.bind("<Button-1>", self._map_press)
        self.mapc.bind("<B1-Motion>", self._map_drag)
        self.mapc.bind("<ButtonRelease-1>", self._map_release)
        self.mapc.bind("<Button-3>", self._map_right)
        self.mapc.bind("<Motion>", self._map_hover)

        # right panel
        rx = w - 258
        rw = 250
        Glass.panel(self.cv, rx, 68, rw, h - 148, r=14)
        Glass.label(self.cv, rx + 12, 82, "OBJETOS - %s" % NAMES[self.cur], "#9dffab", Glass.FONT)
        self.listbox = tk.Listbox(self.root, bg="#0d2110", fg="#d7ffd7", selectbackground="#1d5c2a",
                                  selectforeground="#ffffff", highlightthickness=0,
                                  font=("Consolas", 9), bd=0, activestyle="none")
        self.cv.create_window(rx + 6, 100, window=self.listbox, anchor="nw",
                              width=rw - 12, height=min(220, h - 400))
        self.listbox.bind("<<ListboxSelect>>", self._list_select)
        dy = 100 + min(220, h - 400) + 8
        Glass.label(self.cv, rx + 12, dy, "DETALLES", "#9dffab", Glass.FONT)
        self.detail = Glass.label(self.cv, rx + 12, dy + 20, "(sin selección)", "#c8ffc8")
        by = dy + 44
        b1 = GlassButton(self.cv, rx + 6, by, 112, 24, "BORRAR", command=self.delete_sel, font=("Segoe UI", 8, "bold"))
        b2 = GlassButton(self.cv, rx + 126, by, 118, 24, "TIPO +1", command=self.cycle_victim, font=("Segoe UI", 8, "bold"))
        b3 = GlassButton(self.cv, rx + 6, by + 30, 112, 24, "QUITAR", command=self.clear_sel, font=("Segoe UI", 8, "bold"))
        Glass.label(self.cv, rx + 12, by + 64, "zombies: spawn aleatorio en", "#6fbf7a", Glass.FONT_SM)
        Glass.label(self.cv, rx + 12, by + 80, "los vecinos (tiles amarillos)", "#6fbf7a", Glass.FONT_SM)
        Glass.label(self.cv, rx + 12, by + 96, "click en lista = seleccionar", "#6fbf7a", Glass.FONT_SM)

        # bottom bar
        by2 = h - 50
        Glass.panel(self.cv, 8, by2, w - 16, 40, r=10)
        self.status = Glass.label(self.cv, 20, by2 + 20, "listo", "#c8ffc8")
        self.msg = Glass.label(self.cv, w // 2, by2 + 20, "", "#ffd75e", anchor="center")
        self.save_btn = GlassButton(self.cv, w - 490, by2 + 8, 150, 24, "ENVIAR MAPA", command=self.submit_map,
                                    color="#ffd75e", font=("Segoe UI", 8, "bold"))
        self.save_btn = GlassButton(self.cv, w - 330, by2 + 8, 150, 24, "GUARDAR (PNG+ZAMN)", command=self.save_all,
                                    color="#9dffab", font=("Segoe UI", 8, "bold"))
        self.json_btn = GlassButton(self.cv, w - 172, by2 + 8, 56, 24, "JSON", command=self.save_json, font=("Segoe UI", 8, "bold"))
        self.fs_btn = GlassButton(self.cv, w - 108, by2 + 8, 100, 24, "FULLSCREEN", command=self.toggle_fullscreen,
                                  font=("Segoe UI", 8, "bold"))

        # minimap (SC style, bottom-right of map)
        self._mm_panel = None
        self._draw_minimap(mx, 68, frame_w, frame_h)
        self._refresh_list()
        if self.view_mode == "game":
            self._center_game_view()
        self._status_info()

    # ---------------- minimap ----------------
    def _draw_minimap(self, mx, my, mw, mh):
        mmw, mmh = 168, 100
        mmx = mx + mw - mmw - 8
        mmy = my + mh - mmh - 8
        base = Image.open(os.path.join(ASSETS, "level%d_snes.png" % (self.cur + 1))).convert("RGBA")
        if self.show["capa2"]:
            base.alpha_composite(self.capa2[self.cur].resize(base.size, Image.BILINEAR))
        mini = base.resize((mmw, mmh), Image.BILINEAR)
        d = ImageDraw.Draw(mini)
        L = self.levels[self.cur]
        for i, (x, y) in enumerate(L.spawns):
            d.ellipse([x * mmw / MAP_W - 2, y * mmh / MAP_H - 2, x * mmw / MAP_W + 2, y * mmh / MAP_H + 2],
                      fill=TEAM_COLORS[i // 3], outline="white")
        for x, y, t in L.victims:
            d.rectangle([x * mmw / MAP_W - 1, y * mmh / MAP_H - 1, x * mmw / MAP_W + 1, y * mmh / MAP_H + 1],
                        fill=VICT_COLORS[t % 8], outline="white")
        for x, y in L.medkits:
            d.line([x * mmw / MAP_W - 2, y * mmh / MAP_H, x * mmw / MAP_W + 2, y * mmh / MAP_H], fill="#39d353")
            d.line([x * mmw / MAP_W, y * mmh / MAP_H - 2, x * mmw / MAP_W, y * mmh / MAP_H + 2], fill="#39d353")
        d.rectangle([self._cam_x() * mmw / MAP_W, self._cam_y() * mmh / MAP_H,
                     (self._cam_x() + self._cam_w()) * mmw / MAP_W, (self._cam_y() + self._cam_h()) * mmh / MAP_H],
                    outline="#ffffff", width=1)
        self.minimap_ph = ImageTk.PhotoImage(mini)
        self._mm = self.cv.create_image(mmx, mmy, image=self.minimap_ph, anchor="nw")
        self.cv.tag_bind(self._mm, "<Button-1>", lambda e: self._mm_jump(e, mx, my, mw, mh, mmx, mmy))

    def _mm_jump(self, e, mx, my, mw, mh, mmx, mmy):
        fx = (e.x - mmx) / 168.0
        fy = (e.y - mmy) / 100.0
        self.mapc.xview_moveto(max(0.0, min(1.0, fx - 0.5 * self._cam_w() / (MAP_W * self.scale))))
        self.mapc.yview_moveto(max(0.0, min(1.0, fy - 0.5 * self._cam_h() / (MAP_H * self.scale))))
        self.re_render(keep_cam=True)

    def _cam_x(self):
        return self.mapc.canvasx(0) / self.scale

    def _cam_y(self):
        return self.mapc.canvasy(0) / self.scale

    def _cam_w(self):
        return (self.mapc.winfo_width() or GAME_W) / self.scale

    def _cam_h(self):
        return (self.mapc.winfo_height() or GAME_H) / self.scale

    def _pan_by(self, dx, dy):
        self.mapc.xview_scroll(dx, "units")
        self.mapc.yview_scroll(dy, "units")

    # ---------------- tools / view ----------------
    def set_tool(self, key):
        self.tool = key
        self.set_msg({"sel": "Seleccionar/mover (arrastrar en vacío = mover cámara)",
                      "paint": "Pincel: pinta muralla sobre el mapa",
                      "erase": "Borrador: quita muralla (vuelve caminable)",
                      "spawn": "Clic en el mapa coloca un spawn",
                      "victim": "Clic en el mapa coloca una víctima",
                      "medkit": "Clic en el mapa coloca un medkit"}[key])

    def set_brush(self, s):
        self.brush = s

    def set_view(self, mode, sc):
        self.view_mode = mode
        if mode == "fit":
            self.scale = 0.25
            self._build()
            self._center_game_view()
        elif mode == "game":
            self.scale = 1.0
            self._build()
            self._center_game_view()
        else:
            self.scale = sc
            self.re_render(keep_cam=True)

    def _center_game_view(self):
        L = self.levels[self.cur]
        sx, sy = L.spawns[0] if L.spawns else (340, 600)
        x = max(0.0, sx - GAME_W / 2)
        y = max(0.0, sy - GAME_H / 2)
        self.mapc.xview_moveto(x / (MAP_W * self.scale))
        self.mapc.yview_moveto(y / (MAP_H * self.scale))

    def set_level(self, n):
        self.cur = n
        for i, b in enumerate(self.level_btns):
            b.checked = (i == n)
            b.draw()
        self.clear_sel()
        self.re_render(keep_cam=True)
        self.set_msg("Nivel %d: %s" % (n + 1, NAMES[n]))

    def set_msg(self, t):
        try:
            self.cv.itemconfig(self.msg, text=t)
        except Exception:
            pass

    # ---------------- rendering ----------------
    def re_render(self, keep_cam=False):
        L = self.levels[self.cur]
        n = self.cur + 1
        self.show["capa1"] = self.tgl_capa1.value()
        self.show["capa2"] = self.tgl_capa2.value()
        self.show["mask"] = self.tgl_mask.value()
        self.show["edges"] = self.tgl_edges.value()
        self.show["grid"] = self.tgl_grid.value()
        s = self.scale
        W, H = int(MAP_W * s), int(MAP_H * s)
        base = Image.new("RGBA", (W, H), (10, 22, 10, 255))
        p1 = os.path.join(ASSETS, "level%d_snes.png" % n)
        if self.show["capa1"] and os.path.exists(p1):
            base = Image.open(p1).convert("RGBA").resize((W, H), Image.BILINEAR)
        if self.show["capa2"]:
            up = self.capa2[self.cur].resize((W, H), Image.BILINEAR)
            base.alpha_composite(up)
        if self.show["mask"]:
            ov = Image.new("RGBA", (TW, TH))
            d = ImageDraw.Draw(ov)
            m = self.mask[self.cur]
            for ty in range(TH):
                for tx in range(TW):
                    if not m[ty * TW + tx]:
                        d.rectangle([tx, ty, tx + 1, ty + 1], fill=(255, 70, 70, 110))
            ov = ov.resize((W, H), Image.NEAREST)
            base.alpha_composite(ov)
        if self.show["edges"] and self.edges[self.cur]:
            d = ImageDraw.Draw(base)
            es = max(1, int(TS * s * 0.55))
            for tx, ty in self.edges[self.cur]:
                cx, cy = int((tx + 0.5) * TS * s), int((ty + 0.5) * TS * s)
                d.rectangle([cx - es, cy - es, cx + es, cy + es], fill=(255, 220, 60, 215))
        if self.show["grid"] and s >= 0.5:
            d = ImageDraw.Draw(base)
            for gx in range(0, W, max(1, int(TS * s))):
                d.line([(gx, 0), (gx, H)], fill=(160, 255, 170, 26))
            for gy in range(0, H, max(1, int(TS * s))):
                d.line([(0, gy), (W, gy)], fill=(160, 255, 170, 26))
        self.back_ph = ImageTk.PhotoImage(base)
        vx = self.mapc.xview()[0] if keep_cam and self.mapc.xview() else 0.0
        vy = self.mapc.yview()[0] if keep_cam and self.mapc.yview() else 0.0
        self.mapc.delete("all")
        self.map_items = {}
        self.obj_ids = {}
        self.mapc.create_image(0, 0, image=self.back_ph, anchor="nw", tags=("bkg",))
        self.mapc.configure(scrollregion=(0, 0, W, H))
        self.mapc.xview_moveto(vx)
        self.mapc.yview_moveto(vy)
        self._draw_objects()
        self._refresh_list()
        self._status_info()

    def _pt(self, x, y):
        return x * self.scale, y * self.scale

    def _draw_objects(self):
        L = self.levels[self.cur]
        for i, (x, y) in enumerate(L.spawns):
            self._add_obj("spawn", i, x, y, fill=TEAM_COLORS[i // 3], outline="#ffffff")
        for i, (x, y, t) in enumerate(L.victims):
            self._add_obj("victim", i, x, y, fill=VICT_COLORS[t % 8], outline="#ffffff", shape="rect")
        for i, (x, y) in enumerate(L.medkits):
            self._add_obj("medkit", i, x, y, fill="#39d353", outline="#dfffd0", shape="cross")
        for i, (x, y) in enumerate(L.bounce):
            self._add_obj("bounce", i, x, y, fill=None, outline="#ff9d3d", shape="ring")
        dx, dy = self.door
        self._add_obj("door", 0, dx, dy, fill="#ffe34d", outline="#fff0a0", shape="door")
        self._update_sel_ring()

    def _add_obj(self, kind, idx, x, y, fill, outline, shape="circle"):
        cx, cy = self._pt(x, y)
        r = 5
        if shape == "circle":
            item = self.mapc.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=1)
        elif shape == "rect":
            item = self.mapc.create_rectangle(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=outline, width=1)
        elif shape == "cross":
            self.mapc.create_line(cx - 4, cy, cx + 4, cy, fill=fill, width=2)
            item = self.mapc.create_line(cx, cy - 4, cx, cy + 4, fill=fill, width=2)
        elif shape == "ring":
            item = self.mapc.create_oval(cx - 7, cy - 7, cx + 7, cy + 7, outline=outline, width=2)
        else:
            item = self.mapc.create_rectangle(cx - 7, cy - 7, cx + 7, cy + 7, fill=fill, outline=outline, width=2)
        self.map_items[(kind, idx)] = item
        self.obj_ids[item] = (kind, idx)
        self.mapc.tag_bind(item, "<Button-1>", lambda e, k=(kind, idx): self._obj_click(k))

    def _update_sel_ring(self):
        self.mapc.delete("selring")
        if self.sel:
            it = self.map_items.get(self.sel)
            if it:
                x0, y0, x1, y1 = self.mapc.bbox(it)
                self.mapc.create_rectangle(x0 - 4, y0 - 4, x1 + 4, y1 + 4,
                                           outline="#ffffff", width=1, dash=(3, 2), tags=("selring",))

    def _obj_click(self, key):
        self.sel = key
        self._update_sel_ring()
        self._sync_list_sel()
        self._status_info()

    # ---------------- map interactions ----------------
    def _hit(self, x, y):
        for it in reversed(self.mapc.find_overlapping(x - 4, y - 4, x + 4, y + 4)):
            if it in self.obj_ids:
                return self.obj_ids[it]
        return None

    def _map_press(self, e):
        if self.tool in ("paint", "erase"):
            self._paint_at(e.x, e.y)
            return
        if self.tool in ("spawn", "victim", "medkit"):
            self._add_at(self.tool, e.x, e.y)
            return
        key = self._hit(e.x, e.y)
        if key:
            self.sel = key
            self._update_sel_ring()
            self._sync_list_sel()
            self._status_info()
            it = self.map_items[key]
            x0, y0, x1, y1 = self.mapc.bbox(it)
            self.drag = (key, e.x - (x0 + x1) / 2, e.y - (y0 + y1) / 2)
        else:
            self.pan = (e.x, e.y)
            self.sel = None
            self._update_sel_ring()
            self._sync_list_sel()
            self._status_info()

    def _map_drag(self, e):
        if self.drag:
            key, ox, oy = self.drag
            cx, cy = e.x - ox, e.y - oy
            x = max(0, min(MAP_W - 1, int(cx / self.scale)))
            y = max(0, min(MAP_H - 1, int(cy / self.scale)))
            self._set_pos(key, x, y)
        elif self.pan:
            dx, dy = self.pan
            self.mapc.scan_dragto(e.x, e.y, gain=1)
            self.pan = (e.x, e.y)

    def _map_release(self, e):
        self.drag = None
        self.pan = None
        self._refresh_list()

    def _map_right(self, e):
        if self.tool in ("paint", "erase"):
            self._paint_at(e.x, e.y, invert=True)
        elif self.tool == "sel":
            self.set_tool("spawn")

    def _paint_at(self, cx, cy, invert=False):
        x = int(cx / self.scale)
        y = int(cy / self.scale)
        tx, ty = x // TS, y // TS
        b = self.brush
        capa2 = self.capa2[self.cur]
        cw, ch = capa2.size
        stw, sth = cw // TS, ch // TS
        for oy in range(-(b // 2), -(b // 2) + b):
            for ox in range(-(b // 2), -(b // 2) + b):
                t2x = min(stw - 1, max(0, int((tx + ox) * stw / TW)))
                t2y = min(sth - 1, max(0, int((ty + oy) * sth / TH)))
                wall = not invert
                self._set_source_tile(capa2, t2x, t2y, wall)
        m = mask_from_capa2(capa2)
        self.mask[self.cur] = expand_mask(m, stw, sth)
        self.edges[self.cur] = edge_tiles(self.mask[self.cur])
        self.re_render(keep_cam=True)

    def _set_source_tile(self, img, tx, ty, wall):
        px = img.load()
        for dy in range(TS):
            for dx in range(TS):
                if wall:
                    px[tx * TS + dx, ty * TS + dy] = (48, 48, 48, 255)
                else:
                    px[tx * TS + dx, ty * TS + dy] = (0, 0, 0, 0)

    def _add_at(self, kind, cx, cy):
        x = max(0, min(MAP_W - 1, int(cx / self.scale)))
        y = max(0, min(MAP_H - 1, int(cy / self.scale)))
        L = self.levels[self.cur]
        if kind == "spawn":
            L.spawns.append((x, y))
        elif kind == "victim":
            L.victims.append((x, y, 0))
        else:
            L.medkits.append((x, y))
        self.re_render(keep_cam=True)
        self.set_msg("Objeto agregado en %d,%d" % (x, y))

    def _set_pos(self, key, x, y):
        kind, idx = key
        L = self.levels[self.cur]
        if kind == "spawn" and idx < len(L.spawns):
            L.spawns[idx] = (x, y)
        elif kind == "victim" and idx < len(L.victims):
            v = L.victims[idx]
            L.victims[idx] = (x, y, v[2])
        elif kind == "medkit" and idx < len(L.medkits):
            L.medkits[idx] = (x, y)
        elif kind == "bounce" and idx < len(L.bounce):
            L.bounce[idx] = (x, y)
        elif kind == "door":
            self.door = (x, y)
        it = self.map_items.get(key)
        if it:
            cx, cy = self._pt(x, y)
            if kind in ("spawn", "victim", "medkit"):
                self.mapc.coords(it, cx - 5, cy - 5, cx + 5, cy + 5)
            else:
                self.mapc.coords(it, cx - 7, cy - 7, cx + 7, cy + 7)
        self._update_sel_ring()

    def delete_sel(self):
        if not self.sel:
            return
        kind, idx = self.sel
        L = self.levels[self.cur]
        if kind == "spawn" and idx < len(L.spawns):
            L.spawns.pop(idx)
        elif kind == "victim" and idx < len(L.victims):
            L.victims.pop(idx)
        elif kind == "medkit" and idx < len(L.medkits):
            L.medkits.pop(idx)
        self.clear_sel()
        self.re_render(keep_cam=True)

    def cycle_victim(self):
        if not self.sel or self.sel[0] != "victim":
            self.set_msg("Selecciona una víctima")
            return
        kind, idx = self.sel
        L = self.levels[self.cur]
        if idx >= len(L.victims):
            return
        x, y, t = L.victims[idx]
        L.victims[idx] = (x, y, (t + 1) % 8)
        self.re_render(keep_cam=True)
        self._sync_list_sel()
        self.set_msg("Víctima tipo %d" % ((t + 1) % 8))

    def clear_sel(self):
        self.sel = None
        self._update_sel_ring()
        self._sync_list_sel()
        self._status_info()

    # ---------------- lists / info ----------------
    def _refresh_list(self):
        L = self.levels[self.cur]
        self.listbox.delete(0, "end")
        for i, (x, y) in enumerate(L.spawns):
            self.listbox.insert("end", "S%02d %4d,%4d  %s" % (i + 1, x, y, TEAM_NAMES[i // 3]))
        for i, (x, y, t) in enumerate(L.victims):
            self.listbox.insert("end", "V%02d %4d,%4d  tipo %d" % (i + 1, x, y, t))
        for i, (x, y) in enumerate(L.medkits):
            self.listbox.insert("end", "M%02d %4d,%4d  medkit" % (i + 1, x, y))
        for i, (x, y) in enumerate(L.bounce):
            self.listbox.insert("end", "B%02d %4d,%4d  trampolín" % (i + 1, x, y))
        self.listbox.insert("end", "P   %4d,%4d  puerta salida" % self.door)
        if self.sel:
            self._sync_list_sel()

    def _sync_list_sel(self):
        self.listbox.selection_clear(0, "end")
        if self.sel:
            kind, idx = self.sel
            off = {"spawn": 0, "victim": 12, "medkit": 28, "bounce": 36, "door": 37}[kind]
            row = off + idx
            self.listbox.selection_set(row)
            self.listbox.see(row)

    def _list_select(self, e):
        sel = self.listbox.curselection()
        if not sel:
            return
        row = sel[0]
        if row < 12:
            self.sel = ("spawn", row)
        elif row < 28:
            self.sel = ("victim", row - 12)
        elif row < 36:
            self.sel = ("medkit", row - 28)
        elif row < 37:
            self.sel = ("bounce", row - 36)
        else:
            self.sel = ("door", 0)
        self._update_sel_ring()
        self._status_info()

    def _status_info(self):
        L = self.levels[self.cur]
        m = self.mask[self.cur]
        if self.sel:
            kind, idx = self.sel
            if kind == "spawn":
                x, y = L.spawns[idx]
                t = "SPAWN %d  %d,%d  equipo %s" % (idx + 1, x, y, TEAM_NAMES[idx // 3])
            elif kind == "victim":
                x, y, ty = L.victims[idx]
                t = "VÍCTIMA %d  %d,%d  tipo %d" % (idx + 1, x, y, ty)
            elif kind == "medkit":
                x, y = L.medkits[idx]
                t = "MEDKIT %d  %d,%d" % (idx + 1, x, y)
            elif kind == "bounce":
                x, y = L.bounce[idx]
                t = "TRAMPOLÍN  %d,%d" % (x, y)
            else:
                t = "PUERTA  %d,%d" % self.door
        else:
            t = "(sin selección)"
        try:
            self.cv.itemconfig(self.detail, text=t)
        except Exception:
            pass
        if m is not None:
            walls = sum(1 for b in m if not b)
            self.cv.itemconfig(self.status, text="nivel %d %s | tiles %d | caminable %.0f%% | muralla %.0f%% | vecinos: %d" %
                               (self.cur + 1, NAMES[self.cur], len(m), 100 * sum(m) / len(m),
                                100 * walls / len(m), len(self.edges[self.cur])))

    # ---------------- save ----------------
    def _block(self, name, entries, per_line=4):
        lines = ["%s = [" % name]
        for i in range(0, len(entries), per_line):
            chunk = entries[i:i + per_line]
            lines.append("    " + ", ".join("(%s)" % ", ".join(str(v) for v in e) for e in chunk) +
                         ("," if i + per_line < len(entries) else ""))
        lines.append("]")
        return "\n".join(lines)

    def save_all(self):
        try:
            src = open(ZAMN_PY, encoding="utf-8").read()
            tree = ast.parse(src)
            spans = {}
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and isinstance(node.value, (ast.List, ast.Call)):
                            spans[t.id] = (node.value.lineno, node.value.end_lineno)
            repl = []
            for n in range(LEVELS):
                vk, tk_, mk = LEVEL_KEYS[n]
                L = self.levels[n]
                for name, entries in ((vk, L.victims), (tk_, L.spawns), (mk, L.medkits)):
                    if name in spans:
                        s, e = spans[name]
                        repl.append((s, e, self._block(name, entries)))
            if "BOUNCE_LAYOUT" in spans:
                bounce = [L.bounce[0] if L.bounce else (720, 320) for L in self.levels]
                s, e = spans["BOUNCE_LAYOUT"]
                repl.append((s, e, self._block("BOUNCE_LAYOUT", [[b] for b in bounce], per_line=3)))
            for node in tree.body:
                if (isinstance(node, ast.Assign) and len(node.targets) == 2
                        and isinstance(node.value, ast.Tuple)
                        and [t.id for t in node.targets if isinstance(t, ast.Name)] == ["gDoorX", "gDoorY"]):
                    repl.append((node.lineno, node.end_lineno,
                                 "gDoorX, gDoorY = %.1f, %.1f" % self.door))
            lines = src.split("\n")
            for s, e, txt in sorted(repl, key=lambda r: -r[0]):
                lines[s - 1:e] = [txt]
            new_src = "\n".join(lines)
            ast.parse(new_src)
            bak = ZAMN_PY + ".bak_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            shutil.copy2(ZAMN_PY, bak)
            with open(ZAMN_PY, "w", encoding="utf-8", newline="\n") as f:
                f.write(new_src)
            for n in range(LEVELS):
                self.capa2[n].save(os.path.join(ASSETS, "level%d_snes_upper.png" % (n + 1)), "PNG")
            self.set_msg("Guardado: zamn.py + capas PNG (backup %s)" % os.path.basename(bak))
        except Exception as ex:
            self.set_msg("ERROR al guardar: %s" % ex)

    def save_json(self):
        out = {"door": list(self.door), "levels": []}
        for n in range(LEVELS):
            L = self.levels[n]
            out["levels"].append({
                "name": NAMES[n],
                "spawns": [list(s) for s in L.spawns],
                "victims": [list(v) for v in L.victims],
                "medkits": [list(m) for m in L.medkits],
                "bounce": [list(b) for b in L.bounce],
                "walkable_pct": round(100 * sum(self.mask[n]) / len(self.mask[n]), 1),
                "edge_tiles": len(self.edges[n]),
            })
        with open(JSON_OUT, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        self.set_msg("Exportado a mapa_layouts.json")

    # ---------------- community submit ----------------
    def _post_json(self, url, payload):
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json",
                                              "Cookie": getattr(self, "_cookie", "") or ""})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8")
            setc = r.headers.get("Set-Cookie")
            if setc:
                self._cookie = setc.split(";")[0]
            return json.loads(body)

    def submit_map(self):
        email = sd.askstring("ENVIAR MAPA AL SERVIDOR", "Email de tu cuenta:", parent=self.root)
        if not email:
            return
        pw = sd.askstring("ENVIAR MAPA AL SERVIDOR", "Contraseña:", show="*", parent=self.root)
        if pw is None:
            return
        self._cookie = ""
        try:
            r = self._post_json(SITE + "/api/auth/login",
                                {"email": email.strip(), "password": pw, "remember": False})
            if not r.get("ok"):
                self.set_msg("LOGIN FALLIDO: %s" % r.get("error", "?"))
                return
        except Exception as ex:
            self.set_msg("ERROR DE CONEXION: %s" % ex)
            return
        try:
            n = self.cur + 1
            with open(os.path.join(ASSETS, "level%d_snes.png" % n), "rb") as f:
                base_b64 = base64.b64encode(f.read()).decode("ascii")
            buf = io.BytesIO()
            self.capa2[self.cur].save(buf, "PNG")
            upper_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            L = self.levels[self.cur]
            layout = {"spawns": [list(s) for s in L.spawns],
                      "victims": [list(v) for v in L.victims],
                      "medkits": [list(m) for m in L.medkits],
                      "bounce": [list(b) for b in L.bounce],
                      "door": [float(self.door[0]), float(self.door[1])]}
            r = self._post_json(SITE + "/api/maps/submit",
                                {"name": NAMES[self.cur], "base": base_b64,
                                 "upper": upper_b64, "layout": layout})
            if r.get("ok"):
                self.set_msg("ENVIADO! CODIGO: %s (pendiente de aprobacion)" % r.get("code"))
            else:
                self.set_msg("ERROR AL ENVIAR: %s" % r.get("error", "?"))
        except Exception as ex:
            self.set_msg("ERROR AL ENVIAR: %s" % ex)

    def _wheel_zoom(self, e):
        sc = self.scale * (1.15 if e.delta > 0 else 0.87)
        self.scale = max(0.2, min(4.0, sc))
        self.view_mode = "zoom"
        self.re_render(keep_cam=True)


def main():
    root = tk.Tk()
    MapEditor(root)
    root.mainloop()


if __name__ == "__main__":
    main()