import sys, os
os.environ["SDL_VIDEODRIVER"] = "dummy"
sys.argv = ["zamn.py", "--shot", "play", "dbg3d.png", "5"]
import zamn

zamn.setup_window(True)
zamn.load_assets()
zamn.game_reset(zamn.MODE_SP, 0)
zamn.update_camera()
zamn.render_game_3d()

img = zamn.vbuf
for y in range(0, 270, 4):
    c = img.get_at((240, y))
    print(f"y={y:3d}: {tuple(c)[:3]}")
zamn.pygame.image.save(img, "dbg_vbuf.png")
print("player:", zamn.gP[0].x, zamn.gP[0].y, "cam3d:", zamn.gCam3DX, zamn.gCam3DY)
print("saved")
