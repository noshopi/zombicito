# pygame shim for the browser (Pyodide). Draws into an HTML canvas via the JS
# 2D API - keeps the whole game logic in pure Python. Only the subset of
# pygame used by zamn.py is implemented.
import math
import struct

from js import window, document

__web__ = True

QUIT = 256
KEYDOWN = 768
KEYUP = 769
MOUSEMOTION = 1024
MOUSEBUTTONDOWN = 1025
MOUSEBUTTONUP = 1026
MOUSEWHEEL = 1027
SRCALPHA = 65536
HIDDEN = 16
BLEND_RGB_ADD = 2
BLEND_RGBA_MIN = 5
BLEND_RGBA_MULT = 9
KMOD_SHIFT = 1
KMOD_CTRL = 64

K_BACKSPACE = 8
K_RETURN = 13
K_ESCAPE = 27
K_SPACE = 32
K_0, K_9 = 48, 57
K_PERIOD = 46
K_MINUS = 45
K_a, K_z = 97, 122
K_KP0, K_KP1, K_KP9 = 256, 257, 265
K_KP_PERIOD = 266
K_UP, K_DOWN, K_LEFT, K_RIGHT = 1073741906, 1073741905, 1073741904, 1073741903
for _c in range(97, 123):
    globals()["K_" + chr(_c)] = _c
for _c in range(48, 58):
    globals()["K_" + chr(_c)] = _c

_canvas = None
_ctx = None


class Rect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x=0, y=0, w=0, h=0):
        if hasattr(x, "x") and len(getattr(x, "x", ())) == 4:
            pass
        self.x, self.y, self.w, self.h = int(x), int(y), int(w), int(h)

    def __iter__(self):
        return iter((self.x, self.y, self.w, self.h))


class Surface:
    __slots__ = ("_c", "_ctx", "_w", "_h", "_alpha")

    def __init__(self, size, flags=0):
        self._w, self._h = int(size[0]), int(size[1])
        self._c = document.createElement("canvas")
        self._c.width = self._w
        self._c.height = self._h
        self._ctx = self._c.getContext("2d")
        self._alpha = 255

    @classmethod
    def _from_canvas(cls, c):
        s = cls((c.width, c.height))
        s._c = c
        s._ctx = c.getContext("2d")
        return s

    def set_alpha(self, alpha):
        self._alpha = int(alpha)

    def get_size(self):
        return (self._w, self._h)

    def get_width(self):
        return self._w

    def get_height(self):
        return self._h

    def convert(self):
        return self

    def convert_alpha(self):
        return self

    def copy(self):
        s = Surface(self.get_size())
        s._ctx.drawImage(self._c, 0, 0)
        s._alpha = self._alpha
        return s

    def subsurface(self, rect):
        x, y, w, h = rect.x, rect.y, rect.w, rect.h
        s = Surface((w, h))
        s._ctx.drawImage(self._c, x, y, w, h, 0, 0, w, h)
        return s

    def fill(self, color, rect=None):
        r, g, b = color[0], color[1], color[2]
        a = color[3] if len(color) > 3 else 255
        if rect is None:
            x, y, w, h = 0, 0, self._w, self._h
        else:
            x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
        ctx = self._ctx
        if a <= 0:
            ctx.clearRect(x, y, w, h)
            return
        ctx.globalAlpha = a / 255.0
        ctx.fillStyle = "rgb(%d,%d,%d)" % (r, g, b)
        ctx.fillRect(x, y, w, h)
        ctx.globalAlpha = 1.0

    def blit(self, src, dest, area=None, special_flags=0):
        if area is None:
            sx, sy, sw, sh = 0, 0, src._w, src._h
        else:
            sx, sy, sw, sh = int(area.x), int(area.y), int(area.w), int(area.h)
        dx, dy = int(dest[0]), int(dest[1])
        ctx = self._ctx
        if special_flags == BLEND_RGBA_MIN:
            window._blendMin(self._c, src._c)
            return
        if special_flags == BLEND_RGBA_MULT:
            ctx.globalCompositeOperation = "multiply"
            try:
                ctx.drawImage(src._c, sx, sy, sw, sh, dx, dy, sw, sh)
            finally:
                ctx.globalCompositeOperation = "source-over"
            return
        a = getattr(src, "_alpha", 255)
        if a != 255:
            ctx.globalAlpha = a / 255.0
            try:
                ctx.drawImage(src._c, sx, sy, sw, sh, dx, dy, sw, sh)
            finally:
                ctx.globalAlpha = 1.0
            return
        ctx.drawImage(src._c, sx, sy, sw, sh, dx, dy, sw, sh)

    def get_at(self, pos):
        d = self._ctx.getImageData(int(pos[0]), int(pos[1]), 1, 1).data
        return (d[0], d[1], d[2], d[3])

    def set_at(self, pos, color):
        self._ctx.fillStyle = "rgb(%d,%d,%d)" % (color[0], color[1], color[2])
        self._ctx.fillRect(int(pos[0]), int(pos[1]), 1, 1)


class PixelArray:
    def __init__(self, surf):
        self._s = surf

    def replace(self, old, new):
        window._pxReplace(self._s._c, old[0], old[1], old[2], old[3] if len(old) > 3 else 255,
                          new[0], new[1], new[2], new[3] if len(new) > 3 else 255)

    def __del__(self):
        pass


class Event:
    __slots__ = ("type", "key")

    def __init__(self, t, k):
        self.type = t
        self.key = k


class Clock:
    def tick(self, fps):
        try:
            dt = window._dtMs
            if dt:
                return min(dt, 100.0)
        except Exception:
            pass
        return 16


def init():
    pass


def quit():
    pass


def _load_keyed(name, key_mode):
    c = window._keyedCanvas(window._getImage(name), key_mode)
    return Surface._from_canvas(c)


def _recolor(canvas, r, g, b):
    return Surface._from_canvas(window._recolorCanvas(canvas, r, g, b))


def _recolorCustom(canvas, sexo, hair_i, shirt_i, legs_i, shoes_i, zeke_rects,
                   julie_rects, zeke_hair, julie_hair, palette):
    params = [sexo, hair_i, shirt_i, legs_i, shoes_i]
    c = window._recolorCustomCanvas(canvas, params, zeke_rects, julie_rects,
                                    zeke_hair, julie_hair, palette)
    return Surface._from_canvas(c)


def _setPxRGBA(canvas, x, y, r, g, b, a):
    ctx = canvas.getContext("2d")
    if a <= 0:
        ctx.clearRect(int(x), int(y), 1, 1)
        return
    ctx.fillStyle = "rgba(%d,%d,%d,%d)" % (r, g, b, a)
    ctx.fillRect(int(x), int(y), 1, 1)


def _canvasData(canvas):
    return canvas.getContext("2d").getImageData(0, 0, canvas.width, canvas.height).data


def _fromRGBA(data, w, h):
    s = Surface((w, h))
    img = window._makeImageData(data, w, h)
    s._ctx.putImageData(img, 0, 0)
    return s


def _toPngBase64(canvas):
    return canvas.toDataURL("image/png").split(",")[1]


class _Image:
    def load(self, path):
        name = path.rsplit("/", 1)[-1]
        bmp = window._getImage(name)
        if bmp is None:
            raise IOError("no image %s" % name)
        s = Surface((bmp.width, bmp.height))
        s._ctx.drawImage(bmp, 0, 0)
        return s

    def save(self, surf, file):
        pass


class _Transform:
    def scale(self, surf, size):
        w, h = int(size[0]), int(size[1])
        out = Surface((w, h))
        ctx = out._ctx
        ctx.imageSmoothingEnabled = False
        ctx.drawImage(surf._c, 0, 0, w, h)
        return out

    def flip(self, surf, x, y):
        w, h = surf.get_size()
        out = Surface((w, h))
        ctx = out._ctx
        if x:
            ctx.translate(w, 0)
            ctx.scale(-1, 1)
        if y:
            ctx.translate(0, h)
            ctx.scale(1, -1)
        ctx.drawImage(surf._c, 0, 0)
        return out


class _Draw:
    @staticmethod
    def _norm_rect(rect):
        return int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])

    @staticmethod
    def _style(ctx, color, alpha=None):
        r, g, b = color[0], color[1], color[2]
        a = color[3] if len(color) > 3 else (alpha if alpha is not None else 255)
        ctx.globalAlpha = a / 255.0
        ctx.fillStyle = "rgb(%d,%d,%d)" % (r, g, b)
        ctx.strokeStyle = "rgb(%d,%d,%d)" % (r, g, b)

    def rect(self, surf, color, rect, width=0):
        x, y, w, h = self._norm_rect(rect)
        ctx = surf._ctx
        self._style(ctx, color)
        if width:
            ctx.lineWidth = width
            ctx.strokeRect(x, y, w, h)
        else:
            ctx.fillRect(x, y, w, h)
        ctx.globalAlpha = 1.0

    def circle(self, surf, color, center, radius, width=0):
        ctx = surf._ctx
        self._style(ctx, color)
        ctx.beginPath()
        ctx.arc(int(center[0]), int(center[1]), radius, 0, 6.2831853)
        if width:
            ctx.lineWidth = width
            ctx.stroke()
        else:
            ctx.fill()
        ctx.globalAlpha = 1.0

    def ellipse(self, surf, color, rect, width=0):
        x, y, w, h = self._norm_rect(rect)
        ctx = surf._ctx
        self._style(ctx, color)
        ctx.beginPath()
        ctx.ellipse(x + w / 2.0, y + h / 2.0, w / 2.0, h / 2.0, 0, 0, 6.2831853)
        if width:
            ctx.lineWidth = width
            ctx.stroke()
        else:
            ctx.fill()
        ctx.globalAlpha = 1.0

    def line(self, surf, color, a, b, width=1):
        ctx = surf._ctx
        self._style(ctx, color)
        ctx.lineWidth = width
        ctx.beginPath()
        ctx.moveTo(int(a[0]), int(a[1]))
        ctx.lineTo(int(b[0]), int(b[1]))
        ctx.stroke()
        ctx.globalAlpha = 1.0

    def polygon(self, surf, color, points, width=0):
        ctx = surf._ctx
        self._style(ctx, color)
        ctx.beginPath()
        pts = list(points)
        ctx.moveTo(int(pts[0][0]), int(pts[0][1]))
        for p in pts[1:]:
            ctx.lineTo(int(p[0]), int(p[1]))
        ctx.closePath()
        if width:
            ctx.lineWidth = width
            ctx.stroke()
        else:
            ctx.fill()
        ctx.globalAlpha = 1.0


class _Display:
    def set_mode(self, size, flags=0):
        global _canvas, _ctx
        _canvas = window._gameCanvas
        _ctx = _canvas.getContext("2d")
        s = Surface(size)
        s._c = _canvas
        s._ctx = _ctx
        return s

    def set_caption(self, title):
        document.title = title

    def flip(self):
        pass

    def toggle_fullscreen(self):
        try:
            window._gameCanvas.requestFullscreen()
        except Exception:
            pass


class _Event:
    def get(self):
        arr = window._events
        n = int(arr.length)
        out = []
        for i in range(n):
            e = arr[i]
            out.append(Event(int(e.type),
                             int(getattr(e, "key", 0) or 0),
                             int(getattr(e, "x", 0) or 0),
                             int(getattr(e, "y", 0) or 0),
                             (int(getattr(e, "relx", 0) or 0), int(getattr(e, "rely", 0) or 0)),
                             int(getattr(e, "button", 0) or 0),
                             int(getattr(e, "y_wheel", 0) or 0)))
        arr.splice(0, n)
        return out


class Event:
    def __init__(self, type, key=0, x=0, y=0, rel=(0, 0), button=0, wheel=0):
        self.type = int(type)
        self.key = int(key)
        self.x = int(x)
        self.y = int(y)
        self.rel = rel
        self.button = int(button)
        self.pos = (self.x, self.y)
        if self.type == MOUSEWHEEL:
            self.y = int(wheel)


class _Key:
    def get_pressed(self):
        return _KeyState()

    def get_mods(self):
        return (KMOD_SHIFT if window._shift else 0) | (KMOD_CTRL if window._ctrl else 0)


class _Mouse:
    def get_pos(self):
        return (int(window._mousePos.x), int(window._mousePos.y))

    def get_pressed(self):
        return (int(window._mouseBtns[0]), int(window._mouseBtns[1]), int(window._mouseBtns[2]))

    def set_visible(self, v):
        document.body.style.cursor = "none" if not v else "auto"
        return v

    def get_focused(self):
        return bool(window._mouseIn)


class _KeyState:
    def __getitem__(self, k):
        return window._keyState(int(k))

    def __len__(self):
        return 512


class _Time:
    Clock = Clock


class _Joystick:
    def init(self):
        pass

    def get_count(self):
        return 0


class _Mixer:
    def init(self, *a, **k):
        pass

    def pre_init(self, *a, **k):
        pass

    def quit(self):
        pass


class Sound:
    def __init__(self, buffer=None, file=None):
        self._data = bytes(buffer) if buffer is not None else b""
        self._vol = 1.0

    def play(self, loops=0):
        if not self._data:
            return
        try:
            window._playPCM(self._data, loops, self._vol)
        except Exception:
            pass

    def stop(self):
        try:
            window._stopAll()
        except Exception:
            pass

    def set_volume(self, v):
        self._vol = float(v)


transform = _Transform()
draw = _Draw()
display = _Display()
class Event:
    def __init__(self, type, key=0, x=0, y=0, rel=(0, 0), button=0, y_wheel=0):
        self.type = int(type)
        self.key = int(key)
        self.x = int(x)
        self.y = int(y)
        self.rel = rel
        self.button = int(button)
        self.y = int(y_wheel) if y_wheel else int(y)
        self.pos = (self.x, self.y)


event = _Event()
key = _Key()
mouse = _Mouse()
time = _Time()
joystick = _Joystick()
mixer = _Mixer()
image = _Image()
pygame = None
