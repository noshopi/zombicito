import sys, time
sys.argv = ["zamn.py"]
import zamn as z
import pygame

z.load_lang()
z.gWin = z.setup_window(True)
z.load_assets()
z.gCust = [0, 0, 0, 0, 0]

class DummyClock:
    def tick(self, fps=60):
        return 16
def go():
    z.frame(DummyClock(), 0)
    time.sleep(0.002)

def click(mx, my):
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(mx * 3, my * 3)))
    go()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(mx * 3, my * 3)))
    go()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(mx * 3, my * 3)))
    go()

# ---- dynamic zoom fills the screen ----
z.gSt = z.ST_EDITOR
z.editor_open()
zoo = z._ed_zoom()
x0, y0, cw, ch = z._ed_pad_rect()
print(f"zoom={zoo}  pad=({x0},{y0},{cw},{ch})  frame={z.gEdFW}x{z.gEdFH}")
assert zoo >= 4, f"zoom should be at least 4, got {zoo}"
assert x0 + cw <= 480 and y0 + ch <= 226, f"pad inside screen: ({x0+ cw},{y0+ch})"
assert cw == z.gEdFW * zoo and ch == z.gEdFH * zoo
print("ZOOM_OK")

# ---- pad fills available height ----
avail_h = z.VIEW_H - z.ED_CY - 44
print(f"available height: {avail_h}, pad height: {ch}, zoom: {zoo}")
assert ch <= avail_h + 4  # may be slightly larger due to centering

# ---- grid lines at the right spacing ----
z.rerender_current()
v = z.vbuf
# grid line at first column
assert v.get_at((x0 + zoo, y0 + 2)) == (70, 58, 92, 255), "grid line at zoom spacing"
print("GRID_OK")

# ---- paint still maps correctly ----
z.gEdFrame = 0
click(x0 + zoo, y0 + zoo)
assert z.gEdFrames[0].get_at((1, 1))[3] > 200
print("PAINT_OK")

# ---- all UI elements still work ----
click(292, 34)
assert z.gEdAction == 2
click(25, 159)
assert not z.gEdL1
click(25, 159)
z.gEdFrame = 0
# timeline might have moved...
tl_y = z.VIEW_H - 48  # 270 - 48 = 222
click(54 + 3 * 52, tl_y)
click(60, 245)
assert z.gSt == z.ST_MENU
print("UI_OK")

z.gRunning = False
print("ALL_OK")