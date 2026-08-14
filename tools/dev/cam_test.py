import os
os.environ["ZAMN_SERVER"] = "1"
import pygame
pygame.init()
import zamn
from PIL import Image

def grab():
    import zamn as z
    z.rerender_current()
    arr = pygame.image.tobytes(z.vbuf, "RGB")
    img = Image.frombytes("RGB", (z.VIEW_W, z.VIEW_H), arr)
    return img

def blue_com(img, y0=140, y1=250, x0=0, x1=None):
    px = img.load()
    xs = ys = n = 0
    x1 = x1 or img.size[0]
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            r, g, b = px[x, y]
            if b > 140 and b - r > 60:
                xs += x; ys += y; n += 1
    return (xs // n, ys // n, n) if n else None

z = zamn
z.gWin = z.setup_window(True)
z.load_assets()
z.gSt = z.ST_PLAY
z.gLocalSlot = 0
z.game_reset(z.MODE_SP, 0)
z.g3D = 1
z.gMenuT = 1.2
for f in range(10):
    z.update_game(1.0 / 60.0)
z.rerender_current()
p = z.gP[0]
print("spawn:", p.x, p.y)
img = grab()
print("idle COM(center window 210-270):", blue_com(img, 120, 240, 225, 255))
print("idle COM(full):", blue_com(img))
print("screen center:", z.VIEW_W // 2)

# move right 120 frames
from zamn import CTRL_LOCAL
p.ctrl = CTRL_LOCAL
z.gLocalSlot = 0
import zamn
zamn.keys = {}
class K:
    def __init__(self): self.state = {"RIGHT": True}
z.keys = {}
def fake_keys():
    return set(["RIGHT"])
z.read_local_input = lambda: (1.0, 0.0, 0)
for f in range(120):
    z.update_game(1.0 / 60.0)
    if f in (1, 5, 30, 60, 119):
        print("frame", f, "x=%.1f vx=%.1f alive=%d ctrl=%d" % (p.x, p.vx, p.alive, p.ctrl))
z.rerender_current()
print("after move:", p.x, p.y, "vx:", p.vx)
print("moving COM(center window):", blue_com(grab(), 120, 240, 225, 255), "center:", z.VIEW_W // 2)

# move to map corner (bottom-right) and check camera
z.gCam3DX = 0
p.x = 40.0
p.y = 40.0
p.vx = p.vy = 0
z.update_camera()
print("cam at corner:", z.gCam3DX, z.gCam3DY, " player:", p.x, p.y)
z.rerender_current()
img = grab()
print("corner COM(center window):", blue_com(img, 120, 240, 225, 255))
