import sys, time
sys.argv = ["zamn.py"]
import zamn as z
import pygame

z.load_lang()
z.gWin = z.setup_window(True)
z.load_assets()
z.gCust = [0, 0, 0, 0, 0]
z.texDrawn = None

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

z.gSt = z.ST_EDITOR
z.editor_open()
x0, y0, cw, ch = z._ed_pad_rect()

# ---- click on timeline (outside pad) must NOT paint ----
z.gEdFrame = 0
before = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
click(54 + 5 * 52, 220)
assert z.gEdFrame == 5, "timeline click changed frame"
after = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
assert before == after, "timeline click did NOT paint"
print("TL_CLICK_NO_PAINT_OK")

# ---- click on button (outside pad) must NOT paint ----
z.gEdFlashT = 0
before = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
click(150, 245)   # LIMPIAR
after = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
assert before == after, "button click did NOT paint"
print("BTN_CLICK_NO_PAINT_OK")

# ---- click on tab (outside pad) must NOT paint ----
before = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
click(292, 34)
assert z.gEdAction == 2
after = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
assert before == after, "tab click did NOT paint"
print("TAB_CLICK_NO_PAINT_OK")

# ---- click outside everything (void area) must do nothing ----
before = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
click(300, 100)  # empty right side
after = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
assert before == after, "void click did NOT paint"
print("VOID_CLICK_OK")

# ---- BUT: drag from pad to outside must not paint outside ----
px0, py0 = x0 + 8, y0 + 8   # inside pad
def drag(x1, y1, x2, y2):
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(x1 * 3, y1 * 3)))
    go()
    for i in range(0, 21, 4):
        xi = x1 + (x2 - x1) * i // 20
        yi = y1 + (y2 - y1) * i // 20
        pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=(xi * 3, yi * 3)))
        go()
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(x2 * 3, y2 * 3)))
    go()
before = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
drag(px0, py0, 400, 100)
after = sum(1 for yy in range(38) for xx in range(23) if z.gEdFrames[0].get_at((xx, yy))[3] > 40)
assert after > before, "drag painted on pad"
# pad should only have paint where it was dragged, not outside
print("DRAG_OK")

z.gRunning = False
print("ALL_OK")