# ZOMBICITO - Python Edition
# Full port of the native C remake (ZamnNative/src/main.c) to Python + pygame-ce.
# Same features: single player, LAN multiplayer, dedicated server on
# zombicito.duckdns.org:6969, auto-connect, StarCraft-style lobby, CPU bots,
# LAN lobby browse. The wire protocol is byte-compatible with the C build.
import os
import sys
import math
import random
import socket
import struct
import io
import json
import base64
import threading
import urllib.request
import urllib.parse
import traceback

import pygame

from zamn_font import FONT8X8, FONT8X8_EXT

IS_WEB = bool(getattr(pygame, "__web__", False))

VIEW_W, VIEW_H = 480, 270
WIN_SCALE = 3
# World art/collision are enlarged by 20% from the original 132x78 tile maps.
MAP_W, MAP_H = 2528, 1504
TS = 16
TW, TH = 158, 94
BASE_TW, BASE_TH = 132, 78

MAX_PLAYERS, MAX_ZOMBIES, MAX_BULLETS, MAX_VICTIMS, MAX_FX, MAX_MED = 12, 32, 128, 16, 16, 8
MAX_LOBBIES = 8
NET_PORT = 6969
DEFAULT_SERVER = "zombicito.duckdns.org"

ASSETS = "/assets" if IS_WEB else os.path.join(os.path.dirname(os.path.abspath(__file__)), "ZamnNative", "assets")

MODE_SP, MODE_TEAMS = 0, 1
CTRL_LOCAL, CTRL_NET, CTRL_BOT = 0, 1, 2
ST_MENU, ST_LOBBY, ST_OPTIONS, ST_PLAY, ST_PAUSE, ST_WIN, ST_GAMEOVER, ST_CREATOR, ST_PROFILE, ST_EDITOR, ST_GALLERY, ST_WEAPONS, ST_CHARACTERS, ST_WORLDS, ST_WORLD_EDITOR = range(15)

TEAMCOL = [(110, 235, 70), (235, 70, 70), (90, 150, 255), (255, 220, 60)]
TEAMNAME = ["GREEN", "RED", "BLUE", "YELLOW"]

VSPOTS_DAY = [
    (200, 190, 0), (700, 150, 3), (620, 470, 2), (1060, 420, 0), (1250, 350, 2),
    (250, 700, 3), (620, 700, 0), (660, 300, 1), (1000, 100, 1), (1370, 480, 2),
    (1756, 420, 1), (1566, 350, 2), (1816, 100, 4), (620, 1194, 3), (250, 964, 0), (620, 964, 4),
]
TSPAWN_DAY = [(340, 600), (364, 600), (340, 624),      # GREEN (north-west spawn)
              (1384, 456), (1408, 456), (1384, 480),    # RED (north-east spawn)
              (340, 1000), (364, 1000), (340, 1024),    # BLUE (south-west spawn)
              (1576, 952), (1600, 952), (1576, 976)]    # YELLOW (south-east spawn)
MEDKITS_DAY = [(170, 420), (1300, 480), (900, 640), (1600, 900),
               (1526, 160), (400, 1000), (700, 900), (1750, 320)]
MEDKITS = list(MEDKITS_DAY)
# level 2 (night suburbs): recomposed layout, same sizes
VSPOTS2 = [
    (168, 536, 0), (840, 536, 2), (1512, 536, 1), (1896, 536, 3), (488, 536, 4), (936, 488, 0),
    (1512, 488, 2), (2024, 488, 1), (200, 1064, 3), (744, 1160, 4), (1352, 1064, 0), (1928, 712, 2),
    (424, 840, 1), (1352, 840, 3), (1320, 840, 4), (936, 648, 0),
]
TSPAWN2 = [(296, 584), (456, 616), (264, 616),      # GREEN (NW)
           (1672, 584), (1800, 616), (1544, 616),   # RED (NE)
           (296, 1032), (456, 1000), (264, 1000),   # BLUE (SW)
           (1416, 1000), (1480, 1032), (1384, 1064)]  # YELLOW (SE)
MEDKITS2 = [(648, 232), (1480, 232), (328, 648), (1800, 648),
            (488, 488), (1480, 424), (424, 904), (1800, 904)]
VSPOTS = list(VSPOTS_DAY)
TSPAWN = list(TSPAWN_DAY)
MEDKITS = list(MEDKITS_DAY)

# ---- worlds 3..6 (recomposed layouts over the same two maps) ----
VSPOTS3 = [  # FACTORY
    (168, 536, 5), (840, 536, 2), (1512, 536, 1), (2290, 536, 3), (488, 536, 6), (936, 488, 0),
    (2260, 488, 2), (2380, 1000, 1), (200, 1320, 3), (744, 1400, 7), (1352, 1320, 0), (2250, 820, 2),
    (424, 840, 1), (1352, 840, 5), (1320, 840, 4), (936, 648, 6),
]
TSPAWN3 = [(296, 584), (456, 616), (264, 616), (1672, 584), (1800, 616), (1544, 616),
           (296, 1032), (456, 1000), (264, 1000), (1416, 1000), (1480, 1032), (1384, 1064)]
MEDKITS3 = [(648, 232), (1480, 232), (328, 648), (1800, 648), (488, 488), (1480, 424), (424, 904), (1800, 904)]
VSPOTS4 = [  # SWAMP
    (200, 190, 7), (700, 150, 3), (620, 470, 5), (2290, 420, 0), (2250, 350, 2),
    (250, 700, 3), (620, 700, 6), (660, 300, 1), (2240, 100, 1), (2280, 480, 5),
    (2350, 420, 1), (2100, 350, 2), (2300, 100, 7), (620, 1400, 3), (250, 1240, 6), (620, 1260, 4),
]
TSPAWN4 = [(340, 600), (364, 600), (340, 624), (1384, 456), (1408, 456), (1384, 480),
           (340, 1000), (364, 1000), (340, 1024), (1576, 952), (1600, 952), (1576, 976)]
MEDKITS4 = [(170, 420), (1300, 480), (900, 640), (1600, 900), (1526, 160), (400, 1000), (700, 900), (1750, 320)]
VSPOTS5 = [  # CASTLE
    (168, 536, 6), (840, 536, 2), (1512, 536, 5), (2290, 536, 3), (488, 536, 4), (936, 488, 7),
    (2260, 488, 2), (2380, 1000, 1), (200, 1320, 3), (744, 1400, 5), (1352, 1320, 6), (2250, 820, 2),
    (424, 840, 1), (1352, 840, 3), (1320, 840, 7), (936, 648, 0),
]
TSPAWN5 = [(296, 584), (456, 616), (264, 616), (1672, 584), (1800, 616), (1544, 616),
           (296, 1032), (456, 1000), (264, 1000), (1416, 1000), (1480, 1032), (1384, 1064)]
MEDKITS5 = [(648, 232), (1480, 232), (328, 648), (1800, 648), (488, 488), (1480, 424), (424, 904), (1800, 904)]
VSPOTS6 = [  # MILITARY BASE
    (200, 190, 5), (700, 150, 3), (620, 470, 6), (2290, 420, 7), (2250, 350, 2),
    (250, 700, 3), (620, 700, 0), (660, 300, 1), (2240, 100, 1), (2280, 480, 5),
    (2350, 420, 1), (2100, 350, 2), (2300, 100, 7), (620, 1400, 3), (250, 1240, 6), (620, 1260, 4),
]
TSPAWN6 = [(340, 600), (364, 600), (340, 624), (1384, 456), (1408, 456), (1384, 480),
           (340, 1000), (364, 1000), (340, 1024), (1576, 952), (1600, 952), (1576, 976)]
MEDKITS6 = [(170, 420), (1300, 480), (900, 640), (1600, 900), (1526, 160), (400, 1000), (700, 900), (1750, 320)]

WORLD_NAMES = ["SUBURBIOS DIA", "SUBURBIOS NOCHE", "FABRICA", "PANTANO", "CASTILLO", "BASE MILITAR"]
WORLD_TINT = [(110, 235, 70), (60, 255, 200), (255, 180, 60), (90, 220, 255), (200, 120, 255), (255, 90, 120)]
WORLD_LAYOUT = [(VSPOTS_DAY, TSPAWN_DAY, MEDKITS_DAY), (VSPOTS2, TSPAWN2, MEDKITS2),
                (VSPOTS3, TSPAWN3, MEDKITS3), (VSPOTS4, TSPAWN4, MEDKITS4),
                (VSPOTS5, TSPAWN5, MEDKITS5), (VSPOTS6, TSPAWN6, MEDKITS6)]
WORLD_COUNT = len(WORLD_NAMES)
BOUNCE_LAYOUT = [[(720, 320)], [(1480, 320)], [(720, 980)],
                 [(1480, 980)], [(720, 720)], [(1480, 720)]]
gWorldEditSel = 5
gWorldExpand = [0] * WORLD_COUNT
gWorldEditLayer = "upper"
gWorldEditorBase = None
gWorldEditorUpper = None
gWorldEditorDirty = False

# frame rects (mirror sprites.h, jitter-free recentered sheets)
ZEKE_DOWN = [(86, 5, 16, 36), (108, 4, 16, 37), (128, 4, 16, 37), (148, 4, 16, 37)]
ZEKE_LEFT = [(86, 44, 17, 37), (108, 44, 13, 37), (125, 44, 23, 37), (151, 44, 15, 37)]
ZEKE_UP = [(87, 86, 16, 35), (108, 85, 14, 36), (129, 86, 16, 35), (153, 85, 14, 36)]
JULIE_DOWN = [(7, 4, 20, 38), (8, 52, 18, 38), (10, 102, 16, 38), (7, 154, 16, 38), (7, 205, 16, 38)]
JULIE_LEFT = [(108, 6, 20, 37), (105, 54, 23, 36), (102, 103, 22, 36), (101, 154, 22, 36), (94, 205, 27, 35)]
JULIE_UP = [(76, 5, 20, 37), (76, 53, 14, 37), (74, 101, 15, 37), (73, 152, 14, 37), (74, 204, 15, 37)]
JULIE_RIGHT = [(41, 5, 18, 37), (38, 55, 25, 36), (39, 103, 24, 36), (39, 153, 20, 36), (36, 206, 29, 35)]
ZOM_DOWN = [(8, 22, 27, 47), (41, 21, 27, 48), (74, 21, 27, 48), (108, 22, 27, 47)]
ZOM_RIGHT = [(145, 23, 32, 46), (177, 24, 32, 45), (209, 23, 33, 46), (242, 24, 31, 45)]
ZOM_UP = [(286, 23, 23, 46), (313, 23, 25, 46), (343, 23, 23, 46), (374, 23, 23, 46)]
ZOM_RISE = [(11, 135, 12, 6), (30, 128, 24, 13), (63, 125, 32, 15), (148, 100, 32, 41), (189, 94, 28, 47)]
ZOM_DIE = [(43, 154, 4, 7), (48, 165, 34, 51), (61, 156, 7, 5)]
VIC_CHEER = [(40, 109, 44, 41), (184, 95, 44, 41), (280, 97, 44, 41), (376, 103, 44, 41)]
VIC_DOG = [(2, 56, 33, 27), (35, 54, 30, 29), (67, 52, 30, 31), (100, 54, 31, 29)]
VIC_SOLDIER = [(4, 220, 33, 46), (40, 218, 33, 48), (76, 218, 32, 48)]
VIC_KID = [(37, 384, 31, 29), (72, 379, 37, 34), (113, 373, 46, 40)]
VIC_TOURIST = [(7, 167, 41, 39), (59, 174, 41, 32)]
FX_ANGEL = [(242, 430, 16, 46), (274, 430, 22, 46), (312, 430, 38, 46)]
FX_SPARKLE = [(101, 428, 40, 45), (159, 439, 23, 26), (198, 436, 28, 32)]
DOOR_CLOSED, DOOR_OPEN = (178, 12, 32, 48), (226, 12, 32, 48)

VIC_FRAMES = [VIC_CHEER, VIC_DOG, VIC_SOLDIER, VIC_KID, VIC_TOURIST]
# extra neighbor types reuse base frames with a color tint
VIC_BASE = [0, 1, 2, 3, 4, 2, 3, 0]
VIC_TINT = [None, None, None, None, None, (255, 140, 180), (255, 150, 60), (120, 160, 255)]
VIC_NAMES = ["VECINA", "PERRO", "SOLDADO", "NINO", "TURISTA", "BOMBERA", "MEDICA", "MONJA"]
_victim_cache = {}
# zombie variants: name, hp, speed mul, damage, tint
ZOMBIE_KINDS = [
    ("ZOMBIE", 3, 1.0, 1, None),
    ("RAPIDO", 2, 1.6, 1, (210, 60, 60)),
    ("TANQUE", 8, 0.65, 2, (90, 130, 255)),
]
_zom_kind_cache = {}

# 8-frame interpolated walk cycles (generated by anim_interp.py; used when
# the *_walk.png sheets exist). Rows: one direction per row, fixed frame size.
def _row8(w, h, y):
    return [(i * w, y, w, h) for i in range(8)]

ZEKE2_DOWN = _row8(23, 38, 0)
ZEKE2_LEFT = _row8(23, 38, 38)
ZEKE2_UP = _row8(23, 38, 76)
JULIE2_DOWN = _row8(29, 38, 0)
JULIE2_LEFT = _row8(29, 38, 114)
JULIE2_UP = _row8(29, 38, 76)
JULIE2_RIGHT = _row8(29, 38, 38)
ZOM2_DOWN = _row8(33, 48, 0)
ZOM2_RIGHT = _row8(33, 48, 48)
ZOM2_UP = _row8(33, 48, 96)

# ---------------- packets (python-only protocol) ----------------
PACK_JOIN = struct.Struct("<B")
PACK_LOBBY = struct.Struct("<4B" + "12B" + "12B" + "12B" + "12B" + "12B")
PACK_INPUT = struct.Struct("<4B")
PACK_SNAP = struct.Struct("<BBBBBBBB" + "4h" + "4l" + "2h8B" * 12 + "2h6B" * 32 + "2hB" * 64 + "2B" * 16 + "3h2B" * 16 + "2B" * 8 + "40s" + "B")
PACK_BEACON = struct.Struct("<5B16s16sB")
PACK_EDIT = struct.Struct("<6B")
PACK_PING = struct.Struct("<2B")
PACK_PONG = struct.Struct("<2B")
PACK_CUSTOM = struct.Struct("<7B12s")
PACK_CHAT = struct.Struct("<3B32s")

# name, fireCd, pellets, spread(rad), speed(tiles/s), ammoMax, regen/s, ttl
ARMS = [("RIFLE", 0.22, 1, 0.0, 250.0, 60, 0.4, 0.75),
        ("SHOTGUN", 0.55, 5, 0.13, 220.0, 30, 0.16, 0.5),
        ("SMG", 0.095, 1, 0.035, 280.0, 90, 0.55, 0.6),
        ("PISTOLA", 0.16, 1, 0.02, 240.0, 48, 0.35, 0.8),
        ("MAGNUM", 0.45, 1, 0.0, 300.0, 18, 0.12, 0.9),
        ("METRALLA", 0.07, 1, 0.05, 290.0, 120, 0.7, 0.55),
        ("LLAMAS", 0.12, 3, 0.1, 180.0, 80, 0.3, 0.6),
        ("COHETE", 1.1, 1, 0.0, 320.0, 10, 0.08, 1.2),
        ("RAYO", 0.3, 1, 0.0, 400.0, 24, 0.2, 1.0)]
WEAPON_ICON_NAMES = ["weapon_rifle.png", "weapon_shotgun.png", "weapon_smg.png", "weapon_pistol.png",
                     "weapon_magnum.png", "weapon_minigun.png", "weapon_flamethrower.png",
                     "weapon_rocket.png", "weapon_ray.png"]
MAX_WPNPICK = 8
MAX_AMMOPICK = 10
WPNPICK_SPOTS = [
    [(200, 300, 1), (900, 600, 3), (1500, 250, 4), (1100, 900, 6)],
    [(400, 300, 2), (1200, 500, 4), (600, 900, 5), (1700, 300, 7)],
    [(300, 400, 3), (1000, 300, 5), (1400, 800, 6), (700, 1000, 7)],
    [(500, 350, 1), (1300, 400, 5), (900, 900, 6), (1600, 500, 8)],
    [(350, 500, 3), (1100, 250, 6), (1500, 950, 7), (600, 700, 8)],
    [(450, 300, 4), (1250, 600, 5), (1700, 900, 7), (800, 1100, 8)],
]
AMMO_SPOTS = [(520, 260), (1180, 360), (1780, 620), (2240, 1180), (760, 1280)]

SND_SHOOT, SND_HIT, SND_ZDIE, SND_RESCUE, SND_HURT, SND_EATEN, SND_MENU, SND_CONFIRM, SND_DOOR, SND_SPAWN, SND_STUN = range(11)
# Resident Evil-style sound design: dark, muffled, low booms and eerie tones.
# wave: 0 square, 1 noise (lowpassed), 2 sine, 3 saw
SND_DEFS = {
    SND_SHOOT: [(1, 0, 0, 0.10, 0.85), (0, 72, 38, 0.28, 0.5)],
    SND_HIT: [(2, 135, 80, 0.09, 0.45), (1, 0, 0, 0.05, 0.3)],
    SND_ZDIE: [(1, 0, 0, 0.45, 0.5), (2, 95, 42, 0.5, 0.38)],
    SND_RESCUE: [(2, 880, 880, 0.4, 0.2), (2, 659, 659, 0.45, 0.18), (2, 523, 523, 0.85, 0.16)],
    SND_HURT: [(0, 95, 48, 0.22, 0.45), (1, 0, 0, 0.12, 0.28)],
    SND_EATEN: [(1, 0, 0, 0.05, 0.5), (1, 0, 0, 0.05, 0.5), (1, 0, 0, 0.07, 0.55), (2, 62, 34, 0.22, 0.4)],
    SND_MENU: [(2, 205, 185, 0.05, 0.2)],
    SND_CONFIRM: [(2, 118, 82, 0.2, 0.38)],
    SND_DOOR: [(2, 300, 155, 0.8, 0.28), (1, 0, 0, 0.8, 0.12)],
    SND_SPAWN: [(0, 46, 26, 0.6, 0.28)],
    SND_STUN: [(2, 1120, 600, 0.22, 0.28)],
}


def synth_sound(specs):
    sr = 48000
    out = bytearray()
    lp = 0.0
    for wave, fa, fb, dur, vol in specs:
        n = int(sr * dur)
        phase = 0.0
        rng = 0xC0FFEE
        for i in range(n):
            k = i / n
            f = fa + (fb - fa) * k
            env = (1.0 - k)
            env *= env
            if wave == 0:
                s = 1.0 if (phase % 1.0) < 0.5 else -1.0
            elif wave == 1:
                rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
                s = ((rng >> 16) & 0x7FFF) / 16383.5 - 1.0
            elif wave == 2:
                s = math.sin(phase * 6.2831853)
            else:
                s = 2.0 * ((phase % 1.0) - 0.5)
            alpha = 0.12 if wave == 1 else 1.0
            lp += alpha * (s - lp)
            v = int(max(-1.0, min(1.0, lp * env * vol * 0.85)) * 32767)
            out += struct.pack("<h", v)
            phase += f / sr
    return bytes(out)


def synth_ambient():
    sr = 48000
    out = bytearray()
    total = int(sr * 4.8)
    for i in range(total):
        t = i / sr
        seg = t % 1.2
        d = (math.sin(6.2831853 * 55 * t) + 0.6 * math.sin(6.2831853 * 82.5 * t)
             + 0.35 * math.sin(6.2831853 * 110 * t))
        trem = 0.7 + 0.3 * math.sin(6.2831853 * t / 4.8)
        th = 0.0
        if seg < 0.2:
            th = math.sin(6.2831853 * 40 * seg * 9) * math.exp(-seg * 16) * 0.9
        seg2 = seg - 0.55
        if 0.0 < seg2 < 0.2:
            th += math.sin(6.2831853 * 40 * seg2 * 9) * math.exp(-seg2 * 16) * 0.7
        s = d * 0.14 * trem + th
        v = int(max(-1.0, min(1.0, s)) * 32767 * 0.85)
        out += struct.pack("<h", v)
    return bytes(out)


# ---------------- entity classes ----------------
class Player:
    __slots__ = ("x", "y", "vx", "vy", "dir", "animT", "frame", "hp", "lives", "score", "fireCd",
                 "hurtT", "deadT", "stunT", "charId", "team", "ctrl", "alive", "used",
                 "netButtons", "netLastT", "botTarget", "botRepathT", "botAvoidT",
                 "botAvX", "botAvY", "botLastX", "botLastY", "botStuckT",
                 "botPath", "botPathLen", "botPathPos", "ammo", "recoilT", "wpn", "inv", "stamina", "kills", "deaths", "shieldT", "jumpT", "jumpV")

    def __init__(self):
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.dir = 0
        self.animT = 0.0
        self.frame = 0
        self.hp = 5
        self.lives = 3
        self.score = 0
        self.fireCd = 0.0
        self.hurtT = 0.0
        self.deadT = 0.0
        self.stunT = 0.0
        self.charId = 0
        self.team = 0
        self.ctrl = CTRL_BOT
        self.alive = 0
        self.used = 0
        self.netButtons = 0
        self.netLastT = 0.0
        self.botTarget = -1
        self.botRepathT = 0.0
        self.botAvoidT = 0.0
        self.botAvX = self.botAvY = 0.0
        self.botLastX = self.botLastY = 0.0
        self.botStuckT = 0.0
        self.botPath = [0] * 160
        self.botPathLen = 0
        self.botPathPos = 0
        self.ammo = 60
        self.recoilT = 0.0
        self.wpn = 0
        self.inv = [0]
        self.stamina = 100.0
        self.kills = 0
        self.deaths = 0
        self.shieldT = 0.0
        self.jumpT = 0.0
        self.jumpV = 0.0


class Zombie:
    __slots__ = ("x", "y", "st", "animT", "hurtT", "frame", "hp", "dir", "used", "kind", "team", "respawns")

    def __init__(self):
        self.x = self.y = 0.0
        self.st = 0
        self.animT = 0.0
        self.hurtT = 0.0
        self.frame = 0
        self.hp = 3
        self.dir = 0
        self.used = 0
        self.kind = 0
        self.team = 0
        self.respawns = 0


class Bullet:
    __slots__ = ("x", "y", "vx", "vy", "ttl", "owner", "used")

    def __init__(self):
        self.x = self.y = self.vx = self.vy = self.ttl = 0.0
        self.owner = 0
        self.used = 0


class Victim:
    __slots__ = ("x", "y", "type", "st", "animT", "frame")

    def __init__(self):
        self.x = self.y = 0.0
        self.type = 0
        self.st = 0
        self.animT = 0.0
        self.frame = 0


class Fx:
    __slots__ = ("x", "y", "t", "type", "used")

    def __init__(self):
        self.x = self.y = self.t = 0.0
        self.type = 0
        self.used = 0


class Medkit:
    __slots__ = ("x", "y", "respawnT", "taken")

    def __init__(self):
        self.x = self.y = self.respawnT = 0.0
        self.taken = 0


class Team:
    __slots__ = ("rescues", "score")

    def __init__(self):
        self.rescues = 0
        self.score = 0


class LobbyEntry:
    __slots__ = ("addr", "port", "started", "filled", "slots", "mode2teams", "name", "host", "lastSeen",
                 "region", "world", "bots", "free", "details", "ping", "pingSeq", "pingSentT")

    def __init__(self):
        self.addr = ""
        self.port = 0
        self.started = 0
        self.filled = 0
        self.slots = 0
        self.mode2teams = 0
        self.name = ""
        self.host = ""
        self.lastSeen = 0.0
        self.region = 0
        self.world = 0
        self.bots = 0
        self.free = 0
        self.details = []
        self.ping = -1
        self.pingSeq = 0
        self.pingSentT = 0.0


# ---------------- globals ----------------
gMode = MODE_SP
gTeamCount = 4
gP = [Player() for _ in range(MAX_PLAYERS)]
gNumPlayers = 1
gLocalSlot = 0
gZ = [Zombie() for _ in range(MAX_ZOMBIES)]
gB = [Bullet() for _ in range(MAX_BULLETS)]
gV = [Victim() for _ in range(MAX_VICTIMS)]
gNumVictims = MAX_VICTIMS
gFx = [Fx() for _ in range(MAX_FX)]
gMed = [Medkit() for _ in range(MAX_MED)]
gTeam = [Team() for _ in range(4)]
gSpawnT = 0.0
gElapsed = 0.0
gDoorOpen = 0
gRescued = 0
gEaten = 0
gDoorX, gDoorY = 480.0, 78.0
gCamX = gCamY = 0.0
gCamShakeT = 0.0
gMouseX = gMouseY = 0.0
gMouseIn = False
gMouseDown = False
gMouseErase = False
gWheel = 0
gCursorHidden = -1
gMsg = ""
gMsgT = 0.0

gWalk = bytearray(TW * TH)
gEdgeTiles = []
gNetTime = 0.0

# level select: 0 = suburbios (día), 1 = suburbios de noche (nivel 2)
gLevelSel = 0
texLevel1 = texLevel2 = None
gWalk1 = gWalk2 = None
texWorlds = []
walkWorlds = []
upperWorlds = []

gShowFps = 0
gFpsDisp = 60.0
_mini_cache = None
_mini_key = None
_mini_mask = None

texZeke2 = texJulie2 = texZombie2 = None
gAnimMul = 1

# character creator state
gCust = [0, 1, 2, 1, 0]        # sexo, pelo, polera, pantalon, zapatos (mine)
gCustName = ""
gCustNameMine = ""
gCustMine = tuple(gCust)
gCustNet = [None] * MAX_PLAYERS
gCustNameNet = [""] * MAX_PLAYERS
gCustomCache = {}
gCustTex = None
gCreatorIdx = 0
gCustSent = 0
gCreatorPress = (-1, -1)
gCreatorFlashT = 0.0

# networking
gSock = None
gHosting = 0
gNetStarted = 0
gNetPhase = 1
gMySlot = 0
gClientKnown = [0] * MAX_PLAYERS
gClientAddr = [None] * MAX_PLAYERS
gKinds = [0] * MAX_PLAYERS
gBotEnabled = [1] * MAX_PLAYERS
gLobTeam = [i // 3 for i in range(MAX_PLAYERS)]
gLobChar = [i & 1 for i in range(MAX_PLAYERS)]
gLobReady = [0] * MAX_PLAYERS
gLobName = "ZOMBICITO PARTY"
gLocalHost = 0
gHostAddr = None
gLobbyGot = 0
gNetLastRx = 0.0
gLobbyBcastT = 0.0
gJoinReqT = 0.0
gJoinStartT = 0.0
gLastSndSeq = 0
gSndRing = []
gSndSeq = 0
gServerMode = 0
gServerStartT = 0.0
gServerRestartT = 0.0
gAutoConnect = 0
gBeaconT = 0.0
gLobList = [LobbyEntry() for _ in range(MAX_LOBBIES)]
gLobCount = 0
gLobSel = 0
gPingSeq = 1
gPingT = 0.0
gAnnounceT = 0.0
gDirectoryT = 0.0
gWebHostId = 0
gWebLobbyId = ""
gWebSyncT = 0.0
gWebClients = {}
gConsoleOpen = False
gConsoleInput = ""
gWpnMenuSel = 0
gWpnMenuLock = False

gSt = ST_MENU
gMenuIdx = 0
gMenuT = 0.0
gZomWalkT = 0.0
gLobStage = 0
gLobRow = 0
gLobSelRow = 0
gLobIp = DEFAULT_SERVER
gOptIdx = 0
gFullscreen = 0
gSmooth = 0
gVolume = 7
g3D = 0
pauseIdx = 0

# lobby chat
gChatLines = []
gChatTyping = 0
gChatInput = ""
CHAT_MAX = 30

# profile stats
gWins = 0
gLosses = 0
gEndRecorded = 0

# assets
texZeke = texJulie = texZombie = texVict = texItems = texDoor = texLevel = None
texChars = []
texWeapons = []
CHARNAME = ["ZEKE", "JULIE", "RUSTY", "AZURA", "DANTE", "VERA", "MAX", "REX", "CUSTOM"]

# ---------------- character creator ----------------
# params stored ints: sexo 0/1, pelo, polera, pantalon, zapatos (indices of palettes)
CC_PAL = [
    [(20, 14, 10), (104, 72, 40), (232, 190, 120), (196, 60, 40), (88, 44, 120),
     (30, 30, 34), (236, 120, 160), (168, 128, 78)],                # pelo
    [(232, 32, 48), (32, 48, 112), (64, 150, 60), (240, 200, 40), (152, 56, 190),
     (240, 120, 160), (28, 28, 32), (248, 248, 248), (240, 120, 40), (56, 190, 210)],  # polera
    [(28, 40, 90), (90, 96, 104), (24, 24, 30), (40, 90, 50), (110, 60, 40),
     (140, 40, 40), (220, 190, 60), (248, 248, 248)],               # pantalon
    [(16, 16, 20), (248, 248, 248), (150, 40, 40), (90, 60, 40), (30, 60, 130),
     (40, 110, 60)],                                                # zapatos
]
CC_LABELS = ["DISE\xd1O", "PELO", "POLERA", "PANTALON", "ZAPATOS", "LISTO"]
CC_LABELS_EN = ["BASE", "HAIR", "SHIRT", "PANTS", "SHOES", "DONE"]
CC_BASE_NAME = [["ZEKE", "JULIE", "RUSTY", "AZURA", "DANTE", "VERA", "MAX"],
                ["ZEKE", "JULIE", "RUSTY", "AZURA", "DANTE", "VERA", "MAX"]]
CC_COLOR_NAMES = [["NEGRO", "MARRON", "RUBIO", "ROJO", "MORADO", "GRIS", "ROSA", "DORADO"],
                  ["ROJO", "AZUL", "VERDE", "AMARILLO", "MORADO", "ROSA", "NEGRO", "BLANCO", "NARANJA", "CIAN"],
                  ["AZUL", "GRIS", "NEGRO", "VERDE", "MARRON", "ROJO", "DORADO", "BLANCO"],
                  ["NEGRO", "BLANCO", "ROJO", "MARRON", "AZUL", "VERDE"]]
CC_COLOR_NAMES_EN = [["BLACK", "BROWN", "BLOND", "RED", "PURPLE", "GRAY", "PINK", "GOLD"],
                     ["RED", "BLUE", "GREEN", "YELLOW", "PURPLE", "PINK", "BLACK", "WHITE", "ORANGE", "CYAN"],
                     ["BLUE", "GRAY", "BLACK", "GREEN", "BROWN", "RED", "GOLD", "WHITE"],
                     ["BLACK", "WHITE", "RED", "BROWN", "BLUE", "GREEN"]]
# base hair colors per sex (identified on the source sheets)
ZEKE_HAIR = {(248, 176, 8), (160, 120, 0)}
JULIE_HAIR = {(232, 32, 48), (144, 24, 64), (96, 16, 16), (104, 48, 8)}
ZEKE_RECTS = ZEKE_DOWN + ZEKE_LEFT + ZEKE_UP
JULIE_RECTS = JULIE_DOWN + JULIE_LEFT + JULIE_UP + JULIE_RIGHT
ZEKE2_RECTS = ZEKE2_DOWN + ZEKE2_LEFT + ZEKE2_UP
JULIE2_RECTS = JULIE2_DOWN + JULIE2_LEFT + JULIE2_UP + JULIE2_RIGHT
CHAR_TARGET = [(None, None, None), (None, None, None), (200, 60, 40), (60, 110, 220), (140, 70, 200),
               (40, 180, 160), (240, 150, 40)]
sounds = {}
gPad = None
vbuf = None

# ---------------- character pixel editor ("diseña personaje") ----------------
# Draws the CUSTOM character frame by frame: 4 actions (walk down/left/up/right)
# x 8 frames, same layout as the walk sheets. texDrawn is the composed sheet.
EDIT_PAL = [(20, 20, 24), (255, 255, 255, ), (250, 190, 160), (150, 100, 60),
            (70, 110, 190), (200, 70, 70), (240, 200, 90), (140, 140, 150),
            (70, 190, 170), (180, 80, 210), (245, 120, 60), (100, 190, 80),
            (80, 150, 220), (235, 220, 90), (210, 120, 180), (245, 245, 245)]
ED_ACTIONS = [["CAMINAR ABAJO", "WALK DOWN"], ["CAMINAR IZQ", "WALK LEFT"],
              ["CAMINAR ARRIBA", "WALK UP"], ["CAMINAR DER", "WALK RIGHT"]]
texDrawn = None
gEdFrames = []
gEdFW = gEdFH = 23
gEdAction = gEdFrame = 0
gEdColor = 2
gEdErase = False
gEdBrush = 1
gEdL1 = True        # layer 1: your drawing (painted pixels)
gEdL2 = True        # layer 2: gallery guide (transparent reference)
gEdPlay = False
gEdT = 0.0
gEdFlashT = 0.0
gEdButtonT = 0.0
gEdPressed = ""
gEdNameTyping = False
gEdMode = "character"
gNeighborDrawn = None
gEdRefTex = None       # downloaded gallery design used as drawing guide
gEdGuide = None        # raw first cell (red border included) of the character plantilla
gEdGhostMirrorLeft = True  # Zeke-like templates have no native LEFT row after row swap
gEdGhostIsTemplate = True
ED_ZOOM = 4            # minimum drawing scale
ED_CX = 54             # pad left edge (after palette)
ED_CY = 46             # pad top area start (below tabs)

# global design gallery (server = "este PC": zombicito.duckdns.org:7070)
SITE = "http://zombicito.duckdns.org:7070"
gWpnPick = []          # weapon pickups: [x, y, wpn, active, taken, respawnT]
gWpnMsgT = 0.0
gAmmoPick = []         # ammo boxes: [x, y, active, taken, respawnT]
gDesigns = []
gGalState = "idle"        # idle/loading/done/error (list fetch)
gGalDataState = "idle"    # idle/loading/done/error (selected design download)
gGalSel = 0
gDesignData = None        # (id, surface, png_bytes or None)
gGalFlashT = 0.0
gGalUseReq = False
gGalReturnState = ST_EDITOR
gGalMode = "characters"
gGalMine = False
gGalRenameInput = ""
gGalNameTyping = False
gUpState = 0              # design upload: 0 idle 1 uploading 2 ok 3 error


def zombie_tex(kind):
    """Texture for a zombie variant (recolored cache of the base sheet)."""
    base = texZombie2 if texZombie2 is not None else texZombie
    if kind <= 0:
        return base
    t = _zom_kind_cache.get(kind)
    if t is None:
        t = recolor(base, ZOMBIE_KINDS[kind][4])
        _zom_kind_cache[kind] = t
    return t


def victim_tex(vtype):
    """(tex, frames) for a neighbor type, recoloring extended types."""
    base = VIC_BASE[vtype] if vtype < len(VIC_BASE) else 0
    tint = VIC_TINT[vtype] if vtype < len(VIC_TINT) else None
    if tint is None:
        return texVict, VIC_FRAMES[base]
    key = (base, tint)
    t = _victim_cache.get(key)
    if t is None:
        t = recolor(texVict, tint)
        _victim_cache[key] = t
    return t, VIC_FRAMES[base]


def recolor(tex, target):
    if IS_WEB:
        return pygame._recolor(tex._c, target[0], target[1], target[2])
    s = tex.copy()
    w, h = s.get_size()
    px = pygame.PixelArray(s)
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            r, g, b, a = s.unmap_rgb(c)
            if a < 40:
                continue
            lum = r * 0.3 + g * 0.6 + b * 0.1
            is_skin = r > 170 and 120 < g < 215 and b < 190 and r > b + 40
            if is_skin or lum < 55:
                continue
            px[x, y] = s.map_rgb((int(r + (target[0] - r) * 0.55),
                                  int(g + (target[1] - g) * 0.55),
                                  int(b + (target[2] - b) * 0.55), a))
    del px
    return s


def _is_skin_c(r, g, b):
    if r > 165 and 110 < g < 220 and b > 45 and b < 200:
        if r > b + 30 and b < r * 0.62:
            if b >= r * 0.30 and b >= g * 0.40:
                return True
            if g > 170 and b > 150 and r > 185:
                return True
    return False


def _sheet_rects(base):
    w, h = base.get_size()
    fw = w // 8
    if h % 38 == 0:
        fh, rows = 38, h // 38
    else:
        fh, rows = h // 3, 3
    return [(i * fw, j * fh, fw, fh) for j in range(rows) for i in range(8)]


def build_custom_tex(params):
    """Recolor a base walk sheet per clothing part.
    Base designs: 0 zeke, 1 julie, 2 rusty, 3 azura, 4 dante (the latter three
    are recolored sheets of the first two). Parts are identified by vertical
    regions of each walk frame plus the base hair colors of that body type;
    outlines, skin and eye whites stay."""
    base_i, hair_i, shirt_i, legs_i, shoes_i = params
    if base_i < 0 or base_i >= len(texChars) or not texChars[base_i]:
        base = texZeke if base_i in (0, 2, 4, 6) else texJulie
    else:
        base = texChars[base_i]
    zeke_like = base_i in (0, 2, 4, 6)
    if base in (texZeke, texJulie):
        rects_zeke, rects_julie = ZEKE_RECTS, JULIE_RECTS
    else:
        rects_zeke = rects_julie = _sheet_rects(base)
    if IS_WEB:
        return pygame._recolorCustom(base._c, base_i, hair_i, shirt_i, legs_i, shoes_i,
                                     rects_zeke, rects_julie,
                                     list(ZEKE_HAIR), list(JULIE_HAIR), CC_PAL)
    rects = rects_zeke if zeke_like else rects_julie
    hair_base = ZEKE_HAIR if zeke_like else JULIE_HAIR
    s = base.copy()
    w, h = s.get_size()
    px = pygame.PixelArray(s)
    targets = [CC_PAL[0][hair_i], CC_PAL[1][shirt_i],
               CC_PAL[2][legs_i], CC_PAL[3][shoes_i]]
    for (x0, y0, fw, fh) in rects:
        for yy in range(fh):
            ly = yy / float(fh)
            part = 0 if ly < 0.30 else (1 if ly < 0.62 else (2 if ly < 0.86 else 3))
            for xx in range(fw):
                c = px[x0 + xx, y0 + yy]
                r, g, b, a = s.unmap_rgb(c)
                if a < 40:
                    continue
                lum = r * 0.3 + g * 0.6 + b * 0.1
                if (r, g, b) in hair_base:
                    part = 0
                elif _is_skin_c(r, g, b):
                    continue
                elif lum < 42:
                    continue
                elif part == 0 and lum > 185:
                    continue
                f = 0.35 + 0.78 * lum / 255.0
                t = targets[part]
                px[x0 + xx, y0 + yy] = s.map_rgb((
                    int(min(255, t[0] * f)), int(min(255, t[1] * f)), int(min(255, t[2] * f)), a))
    del px
    return s


def custom_tex(params):
    key = tuple(params)
    t = gCustomCache.get(key)
    if t is None:
        t = build_custom_tex(key)
        if t is None:
            return None
        gCustomCache[key] = t
    return t


def custom_params(slot):
    p = gCustNet[slot] if 0 <= slot < MAX_PLAYERS and gCustNet[slot] else None
    return p if p else tuple(gCust)


def step_creator(d):
    i = gCreatorIdx
    if i == 1:
        gCust[0] = (gCust[0] + d) % 7
    elif i in (0, 6):
        pass
    else:
        n = len(CC_PAL[i - 2])
        gCust[i - 1] = (gCust[i - 1] + d) % n


def random_creator():
    gCust[0] = (gCust[0] + 2) % 7
    for i in range(2, 6):
        gCust[i - 1] = (gCust[i - 1] + 1 + (2 if gCust[0] in (1, 3, 5) else 0)) % len(CC_PAL[i - 2])
    gCust[1] = (gCust[1] + 2) % len(CC_PAL[0])


def custom_display_name(slot=-1):
    n = gCustNameNet[slot] if slot >= 0 and gCustNameNet[slot] else gCustName
    return n or "CUSTOM"


def char_name(charl, slot=-1):
    if charl == 8:
        return custom_display_name(slot)
    return CHARNAME[charl]


# ---------------- profile ----------------
RANK_THRESHOLDS = [0, 1, 3, 6, 12, 20]
RANK_COLORS = [(170, 170, 180), (110, 200, 110), (110, 170, 255),
               (255, 140, 90), (255, 215, 90), (255, 90, 160)]


def profile_rank():
    w = gWins
    r = 0
    for i, t in enumerate(RANK_THRESHOLDS):
        if w >= t:
            r = i
    return r


def profile_rank_name():
    return tr("profile_rank%d" % profile_rank())


def endcard_win():
    if gMode == MODE_TEAMS:
        order = sorted(range(gTeamCount), key=lambda t: (-gTeam[t].rescues, -gTeam[t].score))
        return order[0] == gLobTeam[gMySlot]
    return gSt == ST_WIN


def record_match():
    global gWins, gLosses, gEndRecorded
    if gEndRecorded:
        return
    gEndRecorded = 1
    if endcard_win():
        gWins += 1
    else:
        gLosses += 1
    save_lang()

# ---------------- loading ----------------
def load_sheet(name, key_mode):
    if IS_WEB:
        return pygame._load_keyed(name, key_mode)
    surf = pygame.image.load(os.path.join(ASSETS, name)).convert_alpha()
    w, h = surf.get_size()
    key = surf.get_at((0, 0))
    if key_mode:
        if key_mode == 2:
            extra = []
            for y in range(h):
                for x in range(w):
                    c = surf.get_at((x, y))
                    if abs(c.r - 8) <= 26 and abs(c.g - 176) <= 26 and abs(c.b - 120) <= 26:
                        extra.append((x, y))
                    elif abs(c.r - 8) <= 20 and abs(c.g - 112) <= 20 and abs(c.b - 80) <= 20:
                        extra.append((x, y))
            for x, y in extra:
                surf.set_at((x, y), (0, 0, 0, 0))
        px = pygame.PixelArray(surf)
        px.replace((key.r, key.g, key.b, 255), (0, 0, 0, 0))
        del px
    return surf


def expand_world(tex, walk, connect=True):
    """Scale a world and its walk mask together, preserving pixel collisions."""
    source_tw = max(1, tex.get_width() // TS)
    source_th = max(1, tex.get_height() // TS)
    if len(walk) != source_tw * source_th:
        source_tw = BASE_TW
        source_th = BASE_TH
    tex = pygame.transform.scale(tex, (MAP_W, MAP_H))
    expanded = bytearray(TW * TH)
    for ty in range(TH):
        sy = min(source_th - 1, int(ty * source_th / TH))
        for tx in range(TW):
            sx = min(source_tw - 1, int(tx * source_tw / TW))
            expanded[ty * TW + tx] = walk[sy * source_tw + sx]
    return tex, connect_walk_regions(expanded) if connect else expanded


def connect_walk_regions(mask):
    """Bridge disconnected walkable islands so every map region can be reached."""
    seen = bytearray(len(mask))
    reps = []
    for start, value in enumerate(mask):
        if not value or seen[start]:
            continue
        reps.append((start % TW, start // TW))
        queue = [start]
        seen[start] = 1
        for cur in queue:
            x, y = cur % TW, cur // TW
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < TW and 0 <= ny < TH:
                    ni = ny * TW + nx
                    if mask[ni] and not seen[ni]:
                        seen[ni] = 1
                        queue.append(ni)
    if len(reps) <= 1:
        return mask
    connected = [reps[0]]
    for x, y in reps[1:]:
        tx, ty = min(connected, key=lambda p: abs(p[0] - x) + abs(p[1] - y))
        step = 1 if x >= tx else -1
        for cx in range(tx, x + step, step):
            mask[y * TW + cx] = 1
        step = 1 if y >= ty else -1
        for cy in range(ty, y + step, step):
            mask[cy * TW + x] = 1
        connected.append((x, y))
    return mask


def build_world_variants():
    global texWorlds, walkWorlds
    bases = [texLevel1, texLevel2, texLevel3, texLevel4, texLevel5, texLevel6]
    walks = [gWalk1, gWalk2, gWalk3, gWalk4, gWalk5, gWalk6]
    texWorlds, walkWorlds = [], []
    for base, walk in zip(bases, walks):
        texWorlds.append(base)
        walkWorlds.append(walk)


def world_upper():
    if upperWorlds:
        return upperWorlds[gLevelSel % len(upperWorlds)]
    return None


def load_assets():
    global texZeke, texJulie, texZombie, texVict, texItems, texDoor, texLevel, gWalk, texChars, texWeapons
    global texLevel1, texLevel2, texLevel3, texLevel4, texLevel5, texLevel6
    global gWalk1, gWalk2, gWalk3, gWalk4, gWalk5, gWalk6
    global texZeke2, texJulie2, texZombie2, gAnimMul, texDrawn, gNeighborDrawn, upperWorlds
    texZeke = load_sheet("zeke.png", 1)
    texJulie = load_sheet("julie.png", 1)
    texZombie = load_sheet("zombie.png", 2)
    texVict = load_sheet("victims.png", 1)
    texItems = load_sheet("items.png", 1)
    texDoor = load_sheet("exitdoor.png", 0)
    texWeapons = [load_sheet(name, 0) for name in WEAPON_ICON_NAMES]
    gAnimMul = 1
    texZeke2 = texJulie2 = texZombie2 = None
    if os.path.exists(os.path.join(ASSETS, "zeke_walk.png")):
        try:
            texZeke2 = load_sheet("zeke_walk.png", 1)
            texJulie2 = load_sheet("julie_walk.png", 1)
            texZombie2 = load_sheet("zombie_walk.png", 2)
            gAnimMul = 2
        except OSError:
            texZeke2 = texJulie2 = texZombie2 = None
    def load_world_file(number, fallback_image, fallback_walk):
        image_path = os.path.join(ASSETS, "level%d_snes.png" % number)
        walk_path = os.path.join(ASSETS, "walk%d_snes.bin" % number)
        if os.path.exists(image_path) and os.path.exists(walk_path):
            image = pygame.image.load(image_path).convert()
            with open(walk_path, "rb") as f:
                walk = bytearray(f.read())
            return expand_world(image, walk, connect=False)
        return fallback_image, fallback_walk

    base_image = pygame.image.load(os.path.join(ASSETS, "level_big.png")).convert()
    with open(os.path.join(ASSETS, "walk_big.bin"), "rb") as f:
        base_walk = bytearray(f.read())
    fallback1 = expand_world(base_image, base_walk)
    worlds = [load_world_file(1, *fallback1)]
    for i in range(2, 7):
        worlds.append(load_world_file(i, *fallback1))
    texLevel1, texLevel2, texLevel3, texLevel4, texLevel5, texLevel6 = [w[0] for w in worlds]
    gWalk1, gWalk2, gWalk3, gWalk4, gWalk5, gWalk6 = [w[1] for w in worlds]
    upperWorlds = []
    for i in range(1, 7):
        upper_path = os.path.join(ASSETS, "level%d_snes_upper.png" % i)
        if os.path.exists(upper_path):
            upper = pygame.image.load(upper_path).convert_alpha()
            upper = pygame.transform.scale(upper, (MAP_W, MAP_H))
        else:
            upper = pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
        upperWorlds.append(upper)
    build_world_variants()
    texLevel = texLevel1
    gWalk = gWalk1
    texRex = None
    if os.path.exists(os.path.join(ASSETS, "rex_walk.png")):
        try:
            texRex = load_sheet("rex_walk.png", 1)
        except OSError:
            texRex = None
    if texRex is None and os.path.exists(os.path.join(ASSETS, "rex.png")):
        try:
            texRex = load_sheet("rex.png", 1)
        except OSError:
            texRex = None
    if texZeke2 is not None and texJulie2 is not None:
        texChars = [texZeke2, texJulie2,
                    recolor(texZeke2, CHAR_TARGET[2]),
                    recolor(texJulie2, CHAR_TARGET[3]),
                    recolor(texZeke2, CHAR_TARGET[4]),
                    recolor(texJulie2, CHAR_TARGET[5]),
                    recolor(texZeke2, CHAR_TARGET[6])]
    else:
        texChars = [texZeke, texJulie,
                    recolor(texZeke, CHAR_TARGET[2]),
                    recolor(texJulie, CHAR_TARGET[3]),
                    recolor(texZeke, CHAR_TARGET[4]),
                    recolor(texJulie, CHAR_TARGET[5]),
                    recolor(texZeke, CHAR_TARGET[6])]
    texChars.append(texRex if texRex is not None else (texZeke2 if texZeke2 is not None else texZeke))
    texDrawn = None
    gNeighborDrawn = None
    try:
        if IS_WEB:
            from js import window
            v = window.localStorage.getItem("zamn_drawn")
            d = window.localStorage.getItem("zamn_drawn_dim")
            if v and d:
                import base64
                data = base64.b64decode(v)
                w, h = (int(x) for x in d.split("x"))
                texDrawn = pygame._fromRGBA(data, w, h)
        else:
            if os.path.exists(os.path.join(ASSETS, "custom_drawn.png")):
                texDrawn = load_sheet("custom_drawn.png", 0)
    except Exception:
        texDrawn = None
    try:
        if IS_WEB:
            from js import window
            v = window.localStorage.getItem("zamn_neighbor_drawn")
            d = window.localStorage.getItem("zamn_neighbor_drawn_dim")
            if v and d:
                data = base64.b64decode(v)
                w, h = (int(x) for x in d.split("x"))
                gNeighborDrawn = pygame._fromRGBA(data, w, h)
        elif os.path.exists(os.path.join(ASSETS, "custom_neighbor.png")):
            gNeighborDrawn = load_sheet("custom_neighbor.png", 0)
    except Exception:
        gNeighborDrawn = None
    init_world()


def init_world():
    global gEdgeTiles
    gEdgeTiles = []
    for ty in range(1, TH - 1):
        for tx in range(1, TW - 1):
            if not gWalk[ty * TW + tx]:
                continue
            is_edge = False
            for d in range(4):
                nx = tx + (1 if d == 0 else -1 if d == 1 else 0)
                ny = ty + (1 if d == 2 else -1 if d == 3 else 0)
                if not gWalk[ny * TW + nx]:
                    is_edge = True
                    break
            if is_edge:
                gEdgeTiles.append(ty * TW + tx)


# ---------------- text ----------------
gLang = 0  # 0 = es, 1 = en

TR = {
    "menu_list": ["LISTA DE LOBBIES", "LOBBY LIST"],
    "menu_create": ["CREAR LOBBY", "CREATE LOBBY"],
    "menu_options": ["CONFIGURACION", "SETTINGS"],
    "menu_creator": ["CREAR PERSONAJE", "CHARACTER CREATOR"],
    "menu_weapons": ["ARMAS", "WEAPONS"],
    "menu_characters": ["PERSONAJES", "CHARACTERS"],
    "menu_worlds": ["MUNDOS", "WORLDS"],
    "lobby_join": ["UNIR", "JOIN"],
    "menu_profile": ["PERFIL", "PROFILE"],
    "menu_design": ["DISEÑAR", "DESIGN"],
    "ed_title": ["DISEÑA PERSONAJE", "CHARACTER DESIGN"],
    "ed_frame": ["MARCO %d/%d", "FRAME %d/%d"],
    "ed_save": ["GUARDAR", "SAVE"],
    "ed_back": ["VOLVER", "BACK"],
    "ed_clear": ["LIMPIAR", "CLEAR"],
    "ed_preview": ["PREVIEW", "PREVIEW"],
    "ed_erase": ["BORRAR", "ERASE"],
    "ed_saved": ["¡GUARDADO!", "SAVED!"],
    "ed_ref": ["REF: %s", "REF: %s"],
    "ed_action_short": ["CAM IZQ ARR ABA", "WALK LEFT UP DOWN"],
    "ed_hint": ["IZQ/DER: MARCO  ARR/ABA: ACCION  1-8: COLOR  E: BORRAR  T: REF  P: PREV  S: GUARDAR  C: LIMPIAR  ESC: VOLVER",
                "LEFT/RIGHT: FRAME  UP/DOWN: ACTION  1-8: COLOR  E: ERASE  T: REF  P: PREV  S: SAVE  C: CLEAR  ESC: BACK"],
    "ed_gallery": ["GALERÍA", "GALLERY"],
    "ed_sending": ["ENVIANDO A LA GALERÍA...", "UPLOADING TO GALLERY..."],
    "ed_saved_g": ["¡GUARDADO EN LA GALERÍA GLOBAL!", "SAVED TO THE GLOBAL GALLERY!"],
    "ed_local": ["¡GUARDADO LOCAL! SIN RED", "SAVED LOCALLY! OFFLINE"],
    "ed_incomplete": ["INCOMPLETO: SOLO LOCAL", "INCOMPLETE: LOCAL ONLY"],
    "gal_title": ["GALERÍA GLOBAL", "GLOBAL GALLERY"],
    "gal_count": ["DISEÑOS: %d", "DESIGNS: %d"],
    "gal_loading": ["CARGANDO...", "LOADING..."],
    "gal_noconn": ["SIN CONEXIÓN", "NO CONNECTION"],
    "gal_use": ["USAR", "USE"],
    "gal_refresh": ["REFRESCAR", "REFRESH"],
    "gal_used": ["¡USADO!", "USED!"],
    "gal_hint": ["CLIC O ENTER: USAR  R: REFRESCAR  ESC: VOLVER",
                 "CLICK OR ENTER: USE  R: REFRESH  ESC: BACK"],
    "creator_title": ["CREADOR DE PERSONAJE", "CHARACTER CREATOR"],
    "creator_ok": ["GUARDAR", "SAVE"],
    "creator_name": ["NOMBRE", "NAME"],
    "creator_hint": ["FLECHAS IZQ/DER O CLIC: CAMBIAR   R ALEATORIO   ENTER/ESC SALIR",
                     "LEFT/RIGHT ARROWS OR CLICK: CHANGE   R RANDOM   ENTER/ESC BACK"],
    "menu_hint": ["MOUSE O FLECHAS: ELEGIR   CLIC/ENTER: CONFIRMAR   ESC SALIR",
                  "MOUSE OR ARROWS: SELECT   CLICK/ENTER: CONFIRM   ESC QUIT"],
    "menu_level1": ["NIVEL: 1 - SUBURBIOS", "LEVEL: 1 - SUBURBS"],
    "menu_level2": ["NIVEL: 2 - NOCHE", "LEVEL: 2 - NIGHT"],
    "menu_sub": ["ZOMBICITO - EDICION NATIVA - LAN + SERVIDOR ONLINE",
                 "ZOMBICITO - NATIVE EDITION - LAN + ONLINE SERVER"],
    "menu_sub_web": ["ZOMBICITO - EDICION BROWSER", "ZOMBICITO - BROWSER EDITION"],
    "title_sub": ["RESCATA A TUS VECINOS", "RESCUE YOUR NEIGHBORS"],
    "profile_title": ["PERFIL", "PROFILE"],
    "profile_name": ["NOMBRE", "NAME"],
    "profile_rank": ["RANGO", "RANK"],
    "profile_wins": ["VICTORIAS: %d", "WINS: %d"],
    "profile_losses": ["DERROTAS: %d", "LOSSES: %d"],
    "profile_total": ["PARTIDAS: %d", "MATCHES: %d"],
    "profile_rate": ["EFECTIVIDAD: %d%%", "WIN RATE: %d%%"],
    "profile_back": ["CLIC O ENTER: VOLVER", "CLICK OR ENTER: BACK"],
    "profile_rank0": ["NOVATO", "ROOKIE"],
    "profile_rank1": ["SUPERVIVIENTE", "SURVIVOR"],
    "profile_rank2": ["CAZADOR DE ZOMBIS", "ZOMBIE HUNTER"],
    "profile_rank3": ["ELIMINADOR", "SLAYER"],
    "profile_rank4": ["LEYENDA", "LEGEND"],
    "profile_rank5": ["MITO VIVIENTE", "LIVING MYTH"],
    "lobby_list_title": ["LISTA DE LOBBIES", "LOBBY LIST"],
    "lobby_list_hdr": ["LOBBY                       JUGADORES", "LOBBY                      PLAYERS"],
    "lobby_scan": ["BUSCANDO LOBBIES", "SCANNING FOR LOBBIES"],
    "lobby_none": ["NINGUNO - CREE UNO O UNASE POR IP", "NONE - CREATE ONE OR JOIN BY IP"],
    "lobby_playing": ["JUGANDO", "IN GAME"],
    "lobby_waiting": ["ESPERANDO", "WAITING"],
    "lobby_hint_list": ["", ""],
    "create_title": ["CREAR LOBBY", "CREATE LOBBY"],
    "create_name": ["NOMBRE DEL LOBBY:", "LOBBY NAME:"],
    "create_teams": ["4 EQUIPOS DE 3 - 12 JUGADORES", "4 TEAMS OF 3 - 12 PLAYERS"],
    "create_bots": ["LOS BOTS COMPLETAN LOS LUGARES VACÍOS", "BOTS FILL EMPTY SLOTS"],
    "create_hint": ["ESCRIBA EL NOMBRE   ENTER CREAR   ESC VOLVER", "TYPE THE NAME   ENTER CREATE   ESC BACK"],
    "you": ["TU", "YOU"],
    "cpu": ["CPU", "CPU"],
    "bot_ready": ["BOT LISTO", "BOT READY"],
    "ready": ["LISTO", "READY"],
    "not_ready": ["NO LISTO", "NOT READY"],
    "lobby_hint_host": ["", ""],
    "chat_title": ["CHAT", "CHAT"],
    "chat_hint": ["HAGA CLIC PARA ESCRIBIR", "CLICK TO TYPE"],
    "chat_welcome": ["BIENVENIDO AL LOBBY", "WELCOME TO THE LOBBY"],
    "chat_you": ["TU", "YOU"],
    "chat_sys": ["SISTEMA", "SYSTEM"],
    "lobby_ready_n": ["%d/12 LISTOS", "%d/12 READY"],
    "lobby_auto": ["EL HOST EMPIEZA CUANDO TODOS ESTÉN LISTOS", "HOST STARTS WHEN EVERYONE IS READY"],
    "lobby_connect": ["CONECTANDO AL LOBBY...", "CONNECTING TO LOBBY..."],
    "lobby_ip": ["TU LAN IP: %s - PUERTO %d", "YOUR LAN IP: %s - PORT %d"],
    "lobby_pc": ["TU PC: %s", "YOUR PC: %s"],
    "opts_full": ["PANTALLA COMPLETA  %s", "FULLSCREEN  %s"],
    "opts_filter": ["FILTRO  %s", "FILTER  %s"],
    "opts_vol": ["VOLUMEN SFX  %d", "SFX VOLUME  %d"],
    "opts_lang": ["IDIOMA  %s", "LANGUAGE  %s"],
    "opts_3d": ["VISTA 3D  %s", "3D VIEW  %s"],
    "opts_fps": ["MOSTRAR FPS  %s", "SHOW FPS  %s"],
    "opts_back": ["VOLVER", "BACK"],
    "opts_hint": ["IZQ/DER CAMBIAR   ESC VOLVER", "LEFT/RIGHT CHANGE   ESC BACK"],
    "hud_hp": ["HP", "HP"],
    "hud_en": ["EN", "EN"],
    "hud_ammo": ["AMMO", "AMMO"],
    "hud_low": ["BAJA!", "LOW!"],
    "hud_neighbors": ["VECINOS %d", "NEIGHBORS %d"],
    "hud_left": ["VECINOS RESTANTES %d", "NEIGHBORS LEFT %d"],
    "msg_rescues": ["GANA EL QUE MÁS RESCATE!", "MOST RESCUES WINS!"],
    "msg_rescue": ["RESCATA A LOS VECINOS!", "RESCUE THE NEIGHBORS!"],
    "msg_saved": ["¡SALVADO! QUEDAN %d", "SAVED! %d LEFT"],
    "msg_eaten": ["UN VECINO FUE ¡COMIDO!", "A NEIGHBOR WAS EATEN!"],
    "msg_door": ["LA PUERTA DE SALIDA ESTA ¡ABIERTA!", "THE EXIT DOOR IS OPEN!"],
    "msg_team_saved": ["EL EQUIPO %s SALVO A UNO!", "TEAM %s SAVED ONE!"],
    "end_wins": ["EL EQUIPO %s ¡GANÓ!", "TEAM %s WINS!"],
    "end_rescues": ["%d. %s  RESCATES %d  PUNTOS %06d", "%d. %s  RESCUES %d  SCORE %06d"],
    "end_eaten": ["VECINOS COMIDOS POR ZOMBIES: %d", "NEIGHBORS EATEN BY ZOMBIES: %d"],
    "end_clear": ["NIVEL COMPLETADO!", "LEVEL CLEAR!"],
    "end_saved": ["VECINOS SALVADOS: %d / %d", "NEIGHBORS SAVED: %d / %d"],
    "end_score": ["PUNTOS %06d", "SCORE %06d"],
    "end_over": ["FIN DEL JUEGO", "GAME OVER"],
    "end_zombies": ["LOS ZOMBIES GANARON...", "THE ZOMBIES WON..."],
    "end_back": ["ENTER: VOLVER AL MENU", "ENTER: BACK TO MENU"],
    "pause_title": ["PAUSA", "PAUSED"],
    "pause_resume": ["CONTINUAR", "RESUME"],
    "pause_quit": ["SALIR AL MENU", "QUIT TO MENU"],
}


def tr(key, *args):
    s = TR.get(key, key)
    if gLang == 1:
        s = s[1]
    else:
        s = s[0]
    if args:
        try:
            return s % args
        except Exception:
            return s
    return s


def load_lang():
    global gLang, gShowFps, gCust, gCustName, gWins, gLosses
    try:
        if IS_WEB:
            from js import window
            v = window.localStorage.getItem("zamn_lang")
            gLang = int(v) if v is not None else 0
            v = window.localStorage.getItem("zamn_showfps")
            gShowFps = int(v) if v is not None else 0
            v = window.localStorage.getItem("zamn_custom")
            if v is not None:
                gCust = [int(x) for x in v.split(",")[:5]]
            v = window.localStorage.getItem("zamn_cname")
            gCustName = v if v is not None else ""
            v = window.localStorage.getItem("zamn_wins")
            gWins = int(v) if v is not None else 0
            v = window.localStorage.getItem("zamn_losses")
            gLosses = int(v) if v is not None else 0
        else:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "zamn.cfg")) as f:
                parts = f.read().strip().split("|")
                gLang = int(parts[0]) if parts[0] else 0
                gShowFps = int(parts[1]) if len(parts) > 1 and parts[1] else 0
                if len(parts) > 2 and parts[2]:
                    gCust = [int(x) for x in parts[2].split(",")[:5]]
                gCustName = parts[3] if len(parts) > 3 else ""
                gWins = int(parts[4]) if len(parts) > 4 and parts[4] else 0
                gLosses = int(parts[5]) if len(parts) > 5 and parts[5] else 0
    except Exception:
        pass
    gCust = [gCust[0] if gCust[0] < 7 else 0] + [
        (x if x < len(CC_PAL[i - 1]) else 0) for i, x in enumerate(gCust[1:5])]
    while len(gCust) < 5:
        gCust.append(0)


def save_lang():
    try:
        cust = ",".join(str(x) for x in gCust[:5])
        if IS_WEB:
            from js import window
            window.localStorage.setItem("zamn_lang", str(gLang))
            window.localStorage.setItem("zamn_showfps", str(gShowFps))
            window.localStorage.setItem("zamn_custom", cust)
            window.localStorage.setItem("zamn_cname", gCustName)
            window.localStorage.setItem("zamn_wins", str(gWins))
            window.localStorage.setItem("zamn_losses", str(gLosses))
        else:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "zamn.cfg"), "w") as f:
                f.write("%d|%d|%s|%s|%d|%d" % (gLang, gShowFps, cust, gCustName, gWins, gLosses))
    except Exception:
        pass


_text_cache = {}


def draw_text(surf, x, y, sc, color, s):
    key = (s, color, sc)
    t = _text_cache.get(key)
    if t is None:
        w = len(s) * 8 * sc
        t = pygame.Surface((w or 1, 8 * sc), pygame.SRCALPHA)
        cx = 0
        for ch in s:
            o = ord(ch)
            if o > 127:
                rows = FONT8X8_EXT.get(o)
            else:
                rows = FONT8X8[o]
            if rows is not None:
                for ry in range(8):
                    bits = int(rows[ry * 2:ry * 2 + 2], 16)
                    for rx in range(8):
                        if bits & (1 << rx):
                            t.fill(color, (cx + rx * sc, ry * sc, sc, sc))
            cx += 8 * sc
        if len(_text_cache) > 320:
            _text_cache.clear()
        _text_cache[key] = t
    surf.blit(t, (x, y))


def text_w(sc, s):
    return len(s) * 8 * sc


def draw_text_c(surf, cx, y, sc, color, s):
    draw_text(surf, cx - text_w(sc, s) // 2, y, sc, color, s)


def draw_text_sh(surf, x, y, sc, color, s):
    draw_text(surf, x + sc, y + sc, sc, (10, 25, 10), s)
    draw_text(surf, x, y, sc, color, s)


def draw_text_cs(surf, cx, y, sc, color, s):
    draw_text_sh(surf, cx - text_w(sc, s) // 2, y, sc, color, s)


# ---------------- audio ----------------
gAmbientSnd = None
gAmbientPlaying = False


def init_audio():
    global sounds, gAmbientSnd
    try:
        pygame.mixer.init(48000, -16, 1, 256)
        for sid, specs in SND_DEFS.items():
            snd = pygame.mixer.Sound(buffer=synth_sound(specs))
            snd.set_volume(0.7 * (gVolume / 10.0))
            sounds[sid] = snd
        gAmbientSnd = pygame.mixer.Sound(buffer=synth_ambient())
        gAmbientSnd.set_volume(0.5 * (gVolume / 10.0))
    except Exception:
        pass


def update_ambient():
    global gAmbientPlaying
    if gAmbientSnd is None:
        return
    want = gSt == ST_PLAY
    if want and not gAmbientPlaying:
        gAmbientSnd.play(loops=-1)
        gAmbientPlaying = True
    elif not want and gAmbientPlaying:
        gAmbientSnd.stop()
        gAmbientPlaying = False


def play_snd(sid):
    snd = sounds.get(sid)
    if snd:
        snd.play()


def snd_event(sid):
    global gSndSeq
    play_snd(sid)
    if gHosting:
        gSndSeq = (gSndSeq + 1) & 0xFF
        gSndRing.insert(0, (gSndSeq, sid))
        del gSndRing[8:]


# ---------------- world helpers ----------------
def walkable_px(x, y):
    if x < 0 or y < 0 or x >= MAP_W or y >= MAP_H:
        return 0
    return gWalk[int(y / TS) * TW + int(x / TS)]


def box_free(x, y, hw, hh):
    points = ((x - hw, y - hh), (x, y - hh), (x + hw, y - hh),
              (x - hw, y), (x + hw, y),
              (x - hw, y + hh), (x, y + hh), (x + hw, y + hh))
    return all(walkable_px(px, py) for px, py in points)


def nudge_walkable(x, y):
    if box_free(x, y + 4, 5, 3):
        return x, y
    for r in range(1, 12):
        for a in range(16):
            nx = x + math.cos(a * 0.3927) * r * 12.0
            ny = y + math.sin(a * 0.3927) * r * 12.0
            if 16 < nx < MAP_W - 16 and 16 < ny < MAP_H - 16 and box_free(nx, ny + 4, 5, 3):
                return nx, ny
    return x, y


def team_spawn_idx(team):
    return (3 if team else 0) if gTeamCount == 2 else team


def add_fx(x, y, ftype):
    for f in gFx:
        if not f.used:
            f.x, f.y, f.t, f.type, f.used = x, y, 0.0, ftype, 1
            return


def msg(s):
    global gMsg, gMsgT
    gMsg = s
    gMsgT = 2.2


def setup_victims_medkits():
    for i in range(gNumVictims):
        v = gV[i]
        v.x, v.y, v.type, v.st = float(VSPOTS[i][0]), float(VSPOTS[i][1]), VSPOTS[i][2], 0
        v.animT = (i * 37 % 10) / 10.0
        v.frame = 0
        v.x, v.y = nudge_walkable(v.x, v.y)
    for i in range(gNumVictims, MAX_VICTIMS):
        gV[i].st = 3
    for i in range(MAX_MED):
        gMed[i].x, gMed[i].y, gMed[i].respawnT, gMed[i].taken = float(MEDKITS[i][0]), float(MEDKITS[i][1]), 0.0, 0
        gMed[i].x, gMed[i].y = nudge_walkable(gMed[i].x, gMed[i].y)


def setup_weapon_pickups():
    global gWpnPick
    spots = WPNPICK_SPOTS[gLevelSel % len(WPNPICK_SPOTS)]
    gWpnPick = []
    for i in range(MAX_WPNPICK):
        if i < len(spots):
            x, y, wpn = spots[i]
            nx, ny = nudge_walkable(float(x), float(y))
            gWpnPick.append([nx, ny, wpn, 1, 0, 0.0])
        else:
            gWpnPick.append([0.0, 0.0, 0, 0, 0, 0.0])


def setup_ammo_pickups():
    global gAmmoPick
    gAmmoPick = []
    for x, y in AMMO_SPOTS:
        nx, ny = nudge_walkable(float(x), float(y))
        gAmmoPick.append([nx, ny, 1, 0, 0.0])
    while len(gAmmoPick) < MAX_AMMOPICK:
        gAmmoPick.append([0.0, 0.0, 0, 0, 0.0])


def world_texture():
    """Return the integrated texture/collision pair for the selected world."""
    if texWorlds and walkWorlds:
        i = gLevelSel % min(len(texWorlds), len(walkWorlds))
        return texWorlds[i], walkWorlds[i]
    if (gLevelSel & 1) and gWalk2 is not None:
        return texLevel2, gWalk2
    return texLevel1, gWalk1


def game_reset(mode, char_sel):
    global gMode, gNumPlayers, gNumVictims, gSpawnT, gElapsed, gDoorOpen, gRescued, gEaten, gNetPhase, gWpnMsgT
    global VSPOTS, TSPAWN, MEDKITS, texLevel, gWalk, gLevelSel, gEndRecorded
    gEndRecorded = 0
    gWpnMsgT = 0.0
    if mode == MODE_SP and char_sel >= 0:
        gLobChar[0] = (0, 1, 7, 8)[char_sel % 4]
    texLevel, gWalk = world_texture()
    VSPOTS, TSPAWN, MEDKITS = WORLD_LAYOUT[gLevelSel % WORLD_COUNT]
    init_world()
    for z in gZ:
        z.used = 0
    for b in gB:
        b.used = 0
    for f in gFx:
        f.used = 0
    for p in gP:
        p.used = 0
        p.alive = 0
    for t in gTeam:
        t.rescues = 0
        t.score = 0
    gMode = mode
    gNumPlayers = MAX_PLAYERS
    gNumVictims = MAX_VICTIMS
    for i in range(gNumPlayers):
        P = gP[i]
        P.used = 1 if (i == gMySlot or gKinds[i] >= 2 or gBotEnabled[i]) else 0
        P.alive = 1
        P.hp = 5
        P.ammo = 60
        P.wpn = 0
        P.inv = [0]
        P.stamina = 100.0
        P.kills = 0
        P.deaths = 0
        P.shieldT = 0.0
        P.recoilT = 0.0
        P.lives = 99
        P.botTarget = -1
        P.team = i // 3
        P.charId = gLobChar[i] % 9
        if i == gMySlot:
            P.ctrl = CTRL_LOCAL
        elif gKinds[i] >= 2:
            P.ctrl = CTRL_NET
        else:
            P.ctrl = CTRL_BOT
        P.x = float(TSPAWN[i][0])
        P.y = float(TSPAWN[i][1])
        P.x, P.y = nudge_walkable(P.x, P.y)
        P.netLastT = gNetTime
    setup_victims_medkits()
    setup_weapon_pickups()
    setup_ammo_pickups()
    gSpawnT = 1.2
    gElapsed = 0.0
    gDoorOpen = 0
    gRescued = 0
    gEaten = 0
    gNetPhase = 1
    msg(tr("msg_rescues"))


# ---------------- bots ----------------
def bfs_path(sx, sy, gx, gy):
    def fix(tx, ty):
        if 0 <= tx < TW and 0 <= ty < TH and gWalk[ty * TW + tx]:
            return tx, ty
        for r in range(1, 5):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    nx, ny = tx + dx, ty + dy
                    if 0 <= nx < TW and 0 <= ny < TH and gWalk[ny * TW + nx]:
                        return nx, ny
        return tx, ty

    if sx < 0 or sy < 0 or sx >= TW or sy >= TH or gx < 0 or gy < 0 or gx >= TW or gy >= TH:
        return []
    sx, sy = fix(sx, sy)
    gx, gy = fix(gx, gy)
    start = sy * TW + sx
    goal = gy * TW + gx
    seen = bytearray(TW * TH)
    came = [-1] * (TW * TH)
    q = [start]
    seen[start] = 1
    head = 0
    while head < len(q):
        cur = q[head]
        head += 1
        if cur == goal:
            break
        cx, cy = cur % TW, cur // TW
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if nx < 0 or ny < 0 or nx >= TW or ny >= TH:
                continue
            ni = ny * TW + nx
            if seen[ni] or not gWalk[ni]:
                continue
            seen[ni] = 1
            came[ni] = cur
            q.append(ni)
    if not seen[goal]:
        return []
    path = []
    cur = goal
    while cur != start and cur != -1 and len(path) < TW * TH:
        path.append(cur)
        cur = came[cur]
    path.reverse()
    return path


def bot_input(P, dt):
    ix = iy = 0.0
    fire = 0
    fdx, fdy = 0.0, 1.0
    P.botRepathT -= dt
    retarget = 0
    if P.botTarget >= 0 and gV[P.botTarget].st != 0:
        P.botTarget = -1
        retarget = 1
        P.botAvoidT = 0.9
        P.botAvX = P.botAvY = 0.0
    if P.botTarget < 0 or P.botRepathT <= 0:
        best = 1e18
        bi = -1
        me = gP.index(P)
        for v in range(gNumVictims):
            if gV[v].st != 0:
                continue
            dx = gV[v].x - P.x
            dy = gV[v].y - P.y
            d = dx * dx + dy * dy
            for o in range(gNumPlayers):
                if o != me and gP[o].used and gP[o].team == P.team and gP[o].botTarget == v:
                    d *= 3.0
            if d < best:
                best = d
                bi = v
        if bi != P.botTarget:
            retarget = 1
        P.botTarget = bi
    have = False
    if P.botTarget >= 0:
        tx, ty = gV[P.botTarget].x, gV[P.botTarget].y
        have = True
    else:
        tx, ty = P.x, P.y
        best = 1e18
        for z in gZ:
            if not z.used or z.st != 1:
                continue
            dx = z.x - P.x
            dy = z.y - P.y
            d = dx * dx + dy * dy
            if d < best:
                best = d
                tx, ty = z.x, z.y
                have = True
    if have and (retarget or P.botRepathT <= 0):
        P.botRepathT = 0.7 + random.random() * 0.3
        P.botPath = bfs_path(int(P.x / TS), int((P.y + 4) / TS), int(tx / TS), int((ty + 4) / TS))
        P.botPathLen = len(P.botPath)
        P.botPathPos = 0
    wx, wy = tx, ty
    while P.botPathPos < P.botPathLen:
        t = P.botPath[P.botPathPos]
        wx = (t % TW) * TS + 8.0
        wy = (t // TW) * TS + 8.0
        ddx, ddy = wx - P.x, wy - P.y
        if ddx * ddx + ddy * ddy < 36:
            P.botPathPos += 1
            continue
        break
    if P.botPathPos >= P.botPathLen:
        wx, wy = tx, ty
    P.botStuckT += dt
    if P.botStuckT > 0.5:
        if abs(P.x - P.botLastX) + abs(P.y - P.botLastY) < 5.0:
            P.botAvoidT = 0.5
            a = random.random() * 6.28
            P.botAvX = math.cos(a)
            P.botAvY = math.sin(a)
            P.botRepathT = 0.0
        P.botLastX, P.botLastY = P.x, P.y
        P.botStuckT = 0.0
    if P.botAvoidT > 0:
        P.botAvoidT -= dt
        ix, iy = P.botAvX, P.botAvY
    elif have:
        dx, dy = wx - P.x, wy - P.y
        L = math.sqrt(dx * dx + dy * dy)
        if L > 3:
            ix, iy = dx / L, dy / L
    best = 8100.0
    zi = -1
    for i in range(MAX_ZOMBIES):
        z = gZ[i]
        if not z.used or z.st != 1:
            continue
        dx, dy = z.x - P.x, z.y - P.y
        d = dx * dx + dy * dy
        if d < best:
            best = d
            zi = i
    if zi >= 0:
        return ix, iy, 1, gZ[zi].x - P.x, gZ[zi].y - P.y
    return ix, iy, 0, fdx, fdy


def read_local_input():
    keys = pygame.key.get_pressed()
    ix = float((keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a]))
    iy = float((keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w]))
    fire = keys[pygame.K_z] or keys[pygame.K_SPACE] or keys[pygame.K_f] or gMouseDown
    if gPad is not None:
        ax = gPad.get_axis(0)
        ay = gPad.get_axis(1)
        if abs(ax) > 0.28:
            ix = ax
        if abs(ay) > 0.28:
            iy = ay
        if gPad.get_button(13):
            ix = -1
        if gPad.get_button(14):
            ix = 1
        if gPad.get_button(11):
            iy = -1
        if gPad.get_button(12):
            iy = 1
        if gPad.get_button(0) or gPad.get_button(2):
            fire = 1
    return ix, iy, fire


def pack_buttons(ix, iy, fire):
    b = 0
    if iy < -0.2:
        b |= 1
    if iy > 0.2:
        b |= 2
    if ix < -0.2:
        b |= 4
    if ix > 0.2:
        b |= 8
    if fire:
        b |= 16
    return b


# ---------------- zombies / bullets ----------------
def respawn_zombie(z):
    for _ in range(40):
        if gEdgeTiles:
            tile = random.choice(gEdgeTiles)
            tx, ty = tile % TW, tile // TW
        else:
            tx, ty = random.randrange(TW), random.randrange(TH)
        if not gWalk[ty * TW + tx]:
            continue
        x, y = tx * TS + 8.0, ty * TS + 8.0
        if any((x - gP[i].x) ** 2 + (y - gP[i].y) ** 2 < 120 * 120
               for i in range(gNumPlayers) if gP[i].used):
            continue
        z.x, z.y = x, y
        z.st, z.animT, z.hurtT, z.frame, z.dir = 0, 0.0, 0.0, 0, 0
        z.hp = ZOMBIE_KINDS[z.kind][1]
        return True
    return False


def spawn_zombie():
    used = sum(1 for z in gZ if z.used)
    cap = (4 + 3 * gNumPlayers) if gMode == MODE_TEAMS else 20
    cap = min(cap, MAX_ZOMBIES)
    if used >= cap:
        return
    for tries in range(40):
        if tries < 24 and gEdgeTiles:
            t = random.choice(gEdgeTiles)
            tx, ty = t % TW, t // TW
        else:
            tx, ty = random.randrange(TW), random.randrange(TH)
        if not gWalk[ty * TW + tx]:
            continue
        x, y = tx * TS + 8.0, ty * TS + 8.0
        too_close = False
        near_enough = False
        for i in range(gNumPlayers):
            dx, dy = x - gP[i].x, y - gP[i].y
            d = dx * dx + dy * dy
            if d < 130 * 130:
                too_close = True
            if d < 420 * 420:
                near_enough = True
        if not too_close:
            for v in range(gNumVictims):
                if gV[v].st != 0:
                    continue
                dx, dy = x - gV[v].x, y - gV[v].y
                if dx * dx + dy * dy < 48 * 48:
                    too_close = True
                    break
        if too_close or not near_enough:
            continue
        for z in gZ:
            if not z.used:
                # later worlds mix in tougher/faster variants
                r = random.random()
                if gLevelSel >= 4 and r < 0.30:
                    kind = 2
                elif gLevelSel >= 2 and r < 0.55:
                    kind = 1
                else:
                    kind = 0
                z.x, z.y, z.st, z.animT, z.hurtT, z.frame, z.dir, z.used, z.kind = x, y, 0, 0.0, 0.0, 0, 0, 1, kind
                z.team = 0
                z.respawns = 0
                z.hp = ZOMBIE_KINDS[kind][1]
                snd_event(SND_SPAWN)
                return


def spawn_bullet(P, dx, dy, wpn=0):
    name, cd, pellets, spread, spd, amax, regen, ttl = ARMS[wpn]
    L = math.sqrt(dx * dx + dy * dy)
    if L < 0.1:
        dx, dy = 0.0, 1.0
        L = 1.0
    ux, uy = dx / L, dy / L
    add_fx(P.x + ux * 11, P.y - 6 + uy * 11, 3)  # muzzle flash
    for pi in range(pellets):
        a = math.atan2(uy, ux) + random.uniform(-spread, spread)
        bx, by = math.cos(a), math.sin(a)
        for b in gB:
            if not b.used:
                b.x = P.x + bx * 8
                b.y = P.y - 4 + by * 8
                b.vx = bx * spd
                b.vy = by * spd
                b.ttl = ttl
                b.owner = gP.index(P)
                b.used = 1
                break
    snd_event(SND_SHOOT)

# ---------------- networking ----------------
def net_close():
    global gSock, gHosting, gNetStarted, gLobbyGot, gNetPhase
    if gSock is not None:
        try:
            gSock.close()
        except Exception:
            pass
        gSock = None
    gHosting = 0
    gNetStarted = 0
    gLobbyGot = 0
    gNetPhase = 1
    gChatLines[:] = []
    gChatTyping = 0
    gChatInput = ""
    for i in range(MAX_PLAYERS):
        gClientKnown[i] = 0


def net_host_open():
    global gSock, gHosting, gMySlot, gNetPhase, gNetStarted
    if IS_WEB:
        return False
    net_close()
    gNetStarted = 0
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", NET_PORT))
        s.setblocking(False)
    except OSError:
        return False
    gSock = s
    for i in range(MAX_PLAYERS):
        gKinds[i] = 0
        gLobTeam[i] = i // 3
        gBotEnabled[i] = 0
        if i != 0:
            gLobChar[i] = i % 7
        gLobReady[i] = 0
    gKinds[0] = 1
    gMySlot = 0
    gLobReady[0] = 0
    gCustNet[0] = tuple(gCust)
    gCustSent = 1
    gHosting = 1
    gNetPhase = 1
    chat_add(90, tr("chat_welcome"))
    return True


def host_open_local():
    global gHosting, gMySlot, gLocalHost, gNetStarted, gNetPhase
    gNetStarted = 0
    gNetPhase = 1
    for i in range(MAX_PLAYERS):
        gKinds[i] = 0
        gLobTeam[i] = i // 3
        gBotEnabled[i] = 0
        if i != 0:
            gLobChar[i] = i % 7
        gLobReady[i] = 0
    gKinds[0] = 1
    gMySlot = 0
    gLobReady[0] = 0
    gCustNet[0] = tuple(gCust)
    gCustSent = 1
    gHosting = 1
    gLocalHost = 1
    chat_add(90, tr("chat_welcome"))
    if IS_WEB:
        web_host_announce()
    return True


def net_browse_open():
    global gSock
    if IS_WEB:
        return False
    net_close()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("0.0.0.0", NET_PORT))
        s.setblocking(False)
    except OSError:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind(("0.0.0.0", 0))
            s.setblocking(False)
        except OSError:
            return False
    gSock = s
    return True


def net_client_open(host):
    global gSock, gHostAddr, gNetLastRx
    if IS_WEB:
        return False
    net_close()
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        return False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setblocking(False)
    except OSError:
        return False
    gSock = s
    gHostAddr = (ip, NET_PORT)
    gNetLastRx = gNetTime
    return True


def next_free_human_slot():
    for i in range(MAX_PLAYERS):
        if gKinds[i] == 0 and not gBotEnabled[i]:
            return i
    for i in range(MAX_PLAYERS):
        if gKinds[i] == 0:
            return i
    return -1


def lobby_upsert(from_addr, b):
    global gLobCount
    if b[3] <= 0 and not b[2]:
        return
    i = 0
    while i < gLobCount:
        if gLobList[i].addr == from_addr[0] and gLobList[i].port == from_addr[1]:
            break
        i += 1
    if i == gLobCount:
        if gLobCount >= MAX_LOBBIES:
            return
        gLobCount += 1
    e = gLobList[i]
    e.addr, e.port = from_addr[0], from_addr[1]
    e.started, e.filled, e.slots, e.mode2teams = b[2], b[3], b[4], b[1]
    e.host = b[5].split(b"\0")[0].decode("latin1", "replace")
    e.name = b[6].split(b"\0")[0].decode("latin1", "replace") or e.host
    e.region = b[7] if len(b) > 7 else 0
    e.lastSeen = gNetTime


def lobby_prune():
    global gLobCount, gLobSel
    i = 0
    while i < gLobCount:
        if gNetTime - gLobList[i].lastSeen > 2.5:
            for j in range(i, gLobCount - 1):
                gLobList[j] = gLobList[j + 1]
            gLobCount -= 1
        else:
            i += 1
    if gLobSel >= gLobCount:
        gLobSel = max(0, gLobCount - 1)


def host_send_beacon():
    filled = sum(1 for k in gKinds if k)
    hname = socket.gethostname()[:15].encode("latin1", "replace")[:16].ljust(16, b"\0")
    lname = gLobName[:15].encode("latin1", "replace")[:16].ljust(16, b"\0")
    region = 1 if gServerMode else 0
    try:
        gSock.sendto(PACK_BEACON.pack(5, 0, gNetStarted, filled, MAX_PLAYERS, hname, lname, region),
                     ("255.255.255.255", NET_PORT))
    except OSError:
        pass


def host_send_lobby(to, slot):
    try:
        gSock.sendto(PACK_LOBBY.pack(2, gLevelSel, gNetStarted, slot,
                                     *gKinds, *gLobTeam, *gLobChar, *gLobReady, *gBotEnabled), to)
    except OSError:
        pass


def host_broadcast_lobby():
    for i in range(MAX_PLAYERS):
        if gClientKnown[i]:
            host_send_lobby(gClientAddr[i], i)


def send_custom(to, slot, params, name=""):
    name = name.encode("latin1", "replace")[:12].ljust(12, b"\0")
    try:
        gSock.sendto(PACK_CUSTOM.pack(9, slot, *params, name), to)
    except OSError:
        pass


def host_send_custom(to, slot):
    p = gCustNet[slot]
    if p:
        send_custom(to, slot, p, gCustNameNet[slot])


# ---------------- lobby chat ----------------
def chat_add(slot, text):
    if not text:
        return
    gChatLines.append((slot, text))
    if len(gChatLines) > CHAT_MAX:
        del gChatLines[0]


def chat_send():
    global gChatInput
    text = gChatInput.strip()[:32]
    if text:
        if IS_WEB and gWebLobbyId:
            try:
                from js import window
                window._webLobbyAction(gWebLobbyId, "chat", gMySlot, 0, text)
            except Exception:
                pass
        elif gSock is not None and gLobStage == 2:
            try:
                gSock.sendto(PACK_CHAT.pack(10, gMySlot, len(text),
                             text.encode("latin1", "replace")[:32].ljust(32, b"\0")), gHostAddr)
            except OSError:
                pass
        chat_add(gMySlot, text)
    gChatInput = ""


def chat_name(slot):
    if slot >= 90:
        return tr("chat_sys")
    if slot == gMySlot:
        return tr("chat_you")
    n = gCustNameNet[slot] if 0 <= slot < MAX_PLAYERS and gCustNameNet[slot] else ""
    if n:
        return n
    if 0 <= slot < MAX_PLAYERS and gKinds[slot] >= 2:
        return "PC %d" % gKinds[slot]
    return char_name(gLobChar[slot] % 9, slot) if 0 <= slot < MAX_PLAYERS else "?"


def host_poll():
    while True:
        try:
            data, from_addr = gSock.recvfrom(2048)
        except (BlockingIOError, OSError):
            return
        if len(data) < 1:
            continue
        t = data[0]
        if t == 1:
            slot = -1
            for i in range(MAX_PLAYERS):
                if gClientKnown[i] and gClientAddr[i][0] == from_addr[0] and gClientAddr[i][1] == from_addr[1]:
                    slot = i
                    break
            if slot < 0 and not gNetStarted:
                slot = next_free_human_slot()
                if slot >= 0:
                    client_no = 2 + sum(1 for k in gKinds if k >= 2)
                    gKinds[slot] = client_no
                    gBotEnabled[slot] = 0
                    gLobReady[slot] = 0
                    gClientAddr[slot] = from_addr
                    gClientKnown[slot] = 1
                    if gNumPlayers > slot:
                        gP[slot].netLastT = gNetTime
                    if gServerMode:
                        print("SERVER: PC %d joined" % client_no)
            if slot < 0 and gNetStarted and gServerMode:
                slot = next_free_human_slot()
                if slot >= 0:
                    client_no = 2 + sum(1 for k in gKinds if k >= 2)
                    gKinds[slot] = client_no
                    gBotEnabled[slot] = 0
                    gClientAddr[slot] = from_addr
                    gClientKnown[slot] = 1
                    gLobReady[slot] = 0
                    P = gP[slot]
                    P.ctrl = CTRL_NET
                    P.alive = 1
                    P.hp = 5
                    P.hurtT = 2.0
                    P.team = slot // 3
                    P.charId = slot % 7
                    P.x, P.y = nudge_walkable(float(TSPAWN[slot][0]), float(TSPAWN[slot][1]))
                    P.netLastT = gNetTime
                    print("SERVER: PC %d joined mid-match" % client_no)
            if slot >= 0:
                host_send_lobby(from_addr, slot)
                host_send_custom(from_addr, 0)
                for i in range(MAX_PLAYERS):
                    if i != slot and gCustNet[i]:
                        host_send_custom(from_addr, i)
        elif t == 9 and len(data) >= PACK_CUSTOM.size:
            slot, a, b, c, d, e = data[1], data[2], data[3], data[4], data[5], data[6]
            if 0 <= slot < MAX_PLAYERS and a < 7 and b < 8 and c < 10 and d < 8 and e < 6:
                gCustNet[slot] = (a, b, c, d, e)
                gCustNameNet[slot] = data[7:19].decode("latin1").rstrip("\x00")
                for j in range(MAX_PLAYERS):
                    if gClientKnown[j] and j != slot:
                        host_send_custom(gClientAddr[j], slot)
        elif t == 3 and len(data) >= PACK_INPUT.size:
            slot, buttons = data[1], data[2]
            if slot < MAX_PLAYERS and gClientKnown[slot]:
                gP[slot].netButtons = buttons
                gP[slot].netLastT = gNetTime
        elif t == 7 and len(data) >= PACK_PING.size:
            try:
                gSock.sendto(PACK_PONG.pack(8, data[1]), from_addr)
            except OSError:
                pass
        elif t == 8 and len(data) >= PACK_PONG.size:
            seq = data[1]
            for e in gLobList[:gLobCount]:
                if e.pingSeq == seq and e.pingSeq != 0:
                    e.ping = int((gNetTime - e.pingSentT) * 1000.0)
                    e.pingSeq = 0
                    break
        elif t == 6 and len(data) >= PACK_EDIT.size:
            slot, team, char_id, ready, sit = data[1], data[2], data[3], data[4], data[5]
            who = -1
            for i in range(MAX_PLAYERS):
                if gClientKnown[i] and gClientAddr[i][0] == from_addr[0] and gClientAddr[i][1] == from_addr[1]:
                    who = i
                    break
            if who < 0 or slot >= MAX_PLAYERS:
                continue
            if sit and slot < MAX_PLAYERS and (slot == who or gKinds[slot] == 0):
                # move this player into the chosen slot (bots are displaced)
                if slot != who:
                    gKinds[slot] = gKinds[who]
                    gClientAddr[slot] = gClientAddr[who]
                    gClientKnown[slot] = 1
                    gKinds[who] = 0
                    gClientKnown[who] = 0
                    gLobReady[slot] = 0
                    gLobReady[who] = 1
                gBotEnabled[slot] = 0
                gLobTeam[slot] = slot // 3
                gLobChar[slot] = slot % 7
                if who == 0 and gServerMode:
                    pass
                host_broadcast_lobby()
            elif not sit and who == slot and ready < 2:
                gLobReady[slot] = ready
                host_broadcast_lobby()
            elif not sit and who == slot and char_id < 9:
                gLobChar[slot] = char_id
                host_broadcast_lobby()
        elif t == 10 and len(data) >= PACK_CHAT.size:
            slot, ln = data[1], data[2]
            text = data[3:35].decode("latin1").rstrip("\x00")[:ln]
            if 0 <= slot < MAX_PLAYERS and gClientKnown[slot] and text:
                chat_add(slot, text)
                for j in range(MAX_PLAYERS):
                    if gClientKnown[j] and j != slot:
                        try:
                            gSock.sendto(data[:PACK_CHAT.size], gClientAddr[j])
                        except OSError:
                            pass


def build_snapshot_data():
    pl = []
    for i in range(gNumPlayers):
        P = gP[i]
        pl += [int(P.x), int(P.y), P.dir, P.frame, max(0, P.hp), P.alive, P.team, P.charId,
               1 if P.stunT > 0 else 0, 1 if P.ctrl == CTRL_BOT else 0]
    zb = []
    for z in gZ:
        zb += [int(z.x), int(z.y), z.st, z.frame, z.dir, z.used,
               max(0, min(255, z.hp)), z.team % 4]
    bl = []
    bn = 0
    for b in gB:
        if b.used and bn < 64:
            bl += [int(b.x), int(b.y), 1]
            bn += 1
    while len(bl) < 64 * 3:
        bl += [0, 0, 0]
    vc = []
    for v in range(gNumVictims):
        vc += [gV[v].st, gV[v].frame]
    while len(vc) < MAX_VICTIMS * 2:
        vc += [0, 0]
    fx = []
    for f in gFx:
        fx += [int(f.x), int(f.y), int(f.t * 100), f.type, f.used]
    snd = []
    for i in range(7, -1, -1):
        if i < len(gSndRing):
            snd += [gSndRing[i][0], gSndRing[i][1]]
        else:
            snd += [0, 0]
    med = 0
    for m in range(MAX_MED):
        if gMed[m].taken:
            med |= 1 << m
    msg_bytes = gMsg.encode("latin1", "replace")[:40]
    msg_bytes = msg_bytes.ljust(40, b"\0")
    return PACK_SNAP.pack(4, gNetPhase, gTeamCount, gNumPlayers,
                          gRescued, gEaten, gNumVictims, med,
                          gTeam[0].rescues, gTeam[1].rescues, gTeam[2].rescues, gTeam[3].rescues,
                          gTeam[0].score, gTeam[1].score, gTeam[2].score, gTeam[3].score,
                          *pl, *zb, *bl, *vc, *fx, *snd, msg_bytes, 1 if gMsgT > 0 else 0)


def host_send_snapshot():
    data = build_snapshot_data()
    for i in range(MAX_PLAYERS):
        if gClientKnown[i]:
            try:
                gSock.sendto(data, gClientAddr[i])
            except OSError:
                pass


def client_apply_snapshot(data):
    global gNetPhase, gTeamCount, gNumPlayers, gRescued, gEaten, gNumVictims, gLastSndSeq, gMsg, gMsgT, gSt
    v = PACK_SNAP.unpack(data)
    gNetPhase = v[1]
    gTeamCount = v[2]
    gNumPlayers = v[3]
    gRescued = v[4]
    gEaten = v[5]
    gNumVictims = v[6]
    med_bits = v[7]
    for m in range(MAX_MED):
        gMed[m].taken = (med_bits >> m) & 1
    rescues = v[8:12]
    scores = v[12:16]
    for t in range(4):
        gTeam[t].rescues = rescues[t]
        gTeam[t].score = scores[t]
    idx = 16
    for i in range(min(gNumPlayers, MAX_PLAYERS)):
        P = gP[i]
        P.used = 1
        P.x, P.y = float(v[idx]), float(v[idx + 1])
        P.dir, P.frame = v[idx + 2], v[idx + 3]
        P.hp, P.alive = v[idx + 4], v[idx + 5]
        P.team, P.charId = v[idx + 6], v[idx + 7]
        P.stunT = 1.0 if v[idx + 8] else 0.0
        P.hurtT = 0.0
        P.ctrl = CTRL_BOT if v[idx + 9] else CTRL_NET
        idx += 10
    for i in range(MAX_ZOMBIES):
        z = gZ[i]
        z.x, z.y = float(v[idx]), float(v[idx + 1])
        z.st, z.frame, z.dir, z.used = v[idx + 2], v[idx + 3], v[idx + 4], v[idx + 5]
        z.hp, z.team = v[idx + 6], v[idx + 7]
        z.hurtT = 0.0
        idx += 8
    for b in gB:
        b.used = 0
    for i in range(64):
        if v[idx + 2]:
            gB[i].x, gB[i].y, gB[i].used = float(v[idx]), float(v[idx + 1]), 1
        idx += 3
    for vi in range(min(gNumVictims, MAX_VICTIMS)):
        gV[vi].st, gV[vi].frame = v[idx], v[idx + 1]
        idx += 2
    for i in range(MAX_FX):
        gFx[i].x, gFx[i].y = float(v[idx]), float(v[idx + 1])
        gFx[i].t = v[idx + 2] / 100.0
        gFx[i].type, gFx[i].used = v[idx + 3], v[idx + 4]
        idx += 5
    snd_start = idx
    for i in range(7, -1, -1):
        seq, sid = v[snd_start + i * 2], v[snd_start + i * 2 + 1]
        if seq and ((seq - gLastSndSeq) & 0xFF) <= 128 and seq != gLastSndSeq:
            if ((seq - gLastSndSeq) & 0xFF) < 8 and sid < 11:
                play_snd(sid)
    if v[snd_start]:
        gLastSndSeq = v[snd_start]
    idx = snd_start + 16
    gMsg = v[idx].split(b"\0")[0].decode("latin1", "replace")
    gMsgT = 0.5 if v[idx + 1] else 0.0


def client_poll():
    global gLobbyGot, gNetStarted, gNetLastRx, gTeamCount, gMySlot, gCustSent
    global gLevelSel
    got = False
    while True:
        try:
            data, from_addr = gSock.recvfrom(4096)
        except (BlockingIOError, OSError):
            return got
        if len(data) < 1:
            continue
        t = data[0]
        if t == 2 and len(data) >= PACK_LOBBY.size:
            v = PACK_LOBBY.unpack(data[:PACK_LOBBY.size])
            gTeamCount = 4
            gMySlot = v[3]
            if v[1] != gLevelSel:
                # host picked another map: mirror it locally
                gLevelSel = v[1]
                play_snd(SND_MENU)
            for i in range(MAX_PLAYERS):
                gKinds[i] = v[4 + i]
                gLobTeam[i] = v[16 + i]
                gLobChar[i] = v[28 + i]
                gLobReady[i] = v[40 + i]
                gBotEnabled[i] = v[52 + i]
            gLobbyGot = 1
            if v[2]:
                gNetStarted = 1
            gNetLastRx = gNetTime
            got = True
            if gMySlot >= 0 and not gCustSent:
                send_custom(gHostAddr, gMySlot, tuple(gCust), gCustName)
                gCustSent = 1
        elif t == 9 and len(data) >= PACK_CUSTOM.size:
            v9 = PACK_CUSTOM.unpack(data[:PACK_CUSTOM.size])
            slot, a, b, c, d, e = v9[1], v9[2], v9[3], v9[4], v9[5], v9[6]
            if 0 <= slot < MAX_PLAYERS and a < 7 and b < 8 and c < 10 and d < 8 and e < 6:
                gCustNet[slot] = (a, b, c, d, e)
                gCustNameNet[slot] = v9[7].decode("latin1").rstrip("\x00")
        elif t == 4 and len(data) >= PACK_SNAP.size:
            client_apply_snapshot(data[:PACK_SNAP.size])
            gNetStarted = 1
            gNetLastRx = gNetTime
            got = True
        elif t == 5 and len(data) >= PACK_BEACON.size:
            b = PACK_BEACON.unpack(data[:PACK_BEACON.size])
            lobby_upsert(from_addr, b)
        elif t == 10 and len(data) >= PACK_CHAT.size:
            slot, ln = data[1], data[2]
            text = data[3:35].decode("latin1").rstrip("\x00")[:ln]
            if text:
                chat_add(slot, text)

# ---------------- update (authoritative sim, host / SP) ----------------
def update_game(dt):
    global gElapsed, gMsgT, gSpawnT, gDoorOpen, gRescued, gEaten, gCamShakeT, gWheel, gWpnMsgT
    gElapsed += dt
    if gMsgT > 0:
        gMsgT -= dt

    for m in range(MAX_MED):
        if gMed[m].taken and gMode == MODE_TEAMS and gMed[m].respawnT > 0:
            gMed[m].respawnT -= dt
            if gMed[m].respawnT <= 0:
                gMed[m].taken = 0
    for w in gWpnPick:
        if w[3] and w[4] and gMode == MODE_TEAMS and w[5] > 0:
            w[5] -= dt
            if w[5] <= 0:
                w[4] = 0
    for a in gAmmoPick:
        if a[3] and gMode == MODE_TEAMS and a[4] > 0:
            a[4] -= dt
            if a[4] <= 0:
                a[3] = 0
    if gWpnMsgT > 0:
        gWpnMsgT -= dt

    for pi in range(gNumPlayers):
        P = gP[pi]
        if not P.used:
            continue
        if P.ctrl == CTRL_NET and gNetTime - P.netLastT > 4.0:
            P.ctrl = CTRL_BOT
        if not P.alive:
            P.deadT -= dt
            if P.deadT <= 0 and P.lives > 0:
                P.alive = 1
                P.hp = 5
                P.hurtT = 2.0
                if gMode == MODE_TEAMS:
                    P.x = float(TSPAWN[team_spawn_idx(P.team)][0])
                    P.y = float(TSPAWN[team_spawn_idx(P.team)][1])
                    P.x, P.y = nudge_walkable(P.x, P.y)
            continue
        ix = iy = 0.0
        fdx = fdy = 0.0
        fire = 0
        aim_explicit = False
        if P.stunT > 0:
            P.stunT -= dt
        if P.shieldT > 0:
            P.shieldT -= dt
        if P.ctrl == CTRL_LOCAL and (pygame.key.get_mods() & pygame.KMOD_CTRL):
            P.shieldT = 0.12
        if P.ctrl == CTRL_LOCAL:
            ix, iy, fire = read_local_input()
            if gWheel:
                inv = P.inv if P.inv else [0]
                idx = inv.index(P.wpn) if P.wpn in inv else 0
                idx = (idx + (1 if gWheel > 0 else -1)) % len(inv)
                P.wpn = inv[idx]
                P.ammo = min(P.ammo, ARMS[P.wpn][5])
                play_snd(SND_MENU)
                gWheel = 0
            if gMouseIn:
                win_w, win_h = gWin.get_size()
                mx = gMouseX * VIEW_W // max(1, win_w)
                my = gMouseY * VIEW_H // max(1, win_h)
                adx = gCamX + mx - P.x
                ady = gCamY + my - (P.y - 4)
                al = math.hypot(adx, ady)
                if al > 0.5:
                    fdx, fdy = adx / al, ady / al
                    aim_explicit = True
        elif P.ctrl == CTRL_NET:
            b = P.netButtons
            iy = float(((b >> 1) & 1) - (b & 1))
            ix = float(((b >> 3) & 1) - ((b >> 2) & 1))
            fire = (b >> 4) & 1
        else:
            ix, iy, fire, fdx, fdy = bot_input(P, dt)
            aim_explicit = True
        L2 = ix * ix + iy * iy
        if L2 > 1.0:
            L = math.sqrt(L2)
            ix /= L
            iy /= L
        sprinting = False
        if P.ctrl == CTRL_LOCAL and (ix * ix + iy * iy) > 0.01:
            sprinting = bool(pygame.key.get_mods() & pygame.KMOD_SHIFT) and P.stamina > 0
            if sprinting:
                P.stamina = max(0.0, P.stamina - 34.0 * dt)
        if not sprinting:
            P.stamina = min(100.0, P.stamina + 18.0 * dt)
        sp = 74.0 if P.ctrl == CTRL_BOT else (132.0 if sprinting else 88.0)
        accel = 1.0 - math.exp(-9.0 * dt)
        P.vx += (ix * sp - P.vx) * accel
        P.vy += (iy * sp - P.vy) * accel
        nx = P.x + P.vx * dt
        ny = P.y + P.vy * dt
        if box_free(nx, P.y + 4, 5, 3):
            P.x = nx
        else:
            P.vx = 0.0
        if box_free(P.x, ny + 4, 5, 3):
            P.y = ny
        else:
            P.vy = 0.0
        if P.jumpT > 0:
            P.jumpT = max(0.0, P.jumpT - dt)
            P.jumpV -= 420.0 * dt
        else:
            for bx, by in BOUNCE_LAYOUT[gLevelSel % WORLD_COUNT]:
                if (P.x - bx) ** 2 + (P.y - by) ** 2 < 18 * 18:
                    P.jumpT = 0.55
                    P.jumpV = 230.0
                    play_snd(SND_MENU)
                    break
        if P.ctrl == CTRL_BOT and (abs(P.vx) > 2.0 or abs(P.vy) > 2.0):
            # Face the direction actually achieved after collision resolution.
            ix, iy = P.vx, P.vy
        if abs(ix) > 0.05 or abs(iy) > 0.05:
            P.animT += dt * 9.0 * gAnimMul
            if abs(ix) > abs(iy) * 0.99:
                P.dir = 3 if ix > 0 else 1
            else:
                P.dir = 0 if iy > 0 else 2
        else:
            P.animT = 0
        P.frame = int(P.animT) % (4 * gAnimMul)
        if P.fireCd > 0:
            P.fireCd -= dt
        if P.hurtT > 0:
            P.hurtT -= dt
        if P.recoilT > 0:
            P.recoilT -= dt
        if P.ammo < ARMS[P.wpn][5]:
            P.ammo = min(float(ARMS[P.wpn][5]), P.ammo + dt * ARMS[P.wpn][6])
        if fire and P.fireCd <= 0 and P.stunT <= 0 and P.ammo >= 1:
            if aim_explicit and (abs(fdx) > 0.05 or abs(fdy) > 0.05):
                if abs(fdx) > abs(fdy):
                    P.dir = 3 if fdx > 0 else 1
                else:
                    P.dir = 0 if fdy > 0 else 2
            P.fireCd = ARMS[P.wpn][1]
            P.ammo -= 1
            P.recoilT = 0.09
            if P.ctrl == CTRL_LOCAL:
                gCamShakeT = 0.08
            if not aim_explicit:
                if abs(ix) > 0.05 or abs(iy) > 0.05:
                    fdx, fdy = ix, iy
                else:
                    fdx = 1.0 if P.dir == 3 else -1.0 if P.dir == 1 else 0.0
                    fdy = 1.0 if P.dir == 0 else -1.0 if P.dir == 2 else 0.0
            spawn_bullet(P, fdx, fdy, P.wpn)
        for v in range(gNumVictims):
            if gV[v].st != 0:
                continue
            dx = gV[v].x - P.x
            dy = gV[v].y - P.y
            if dx * dx + dy * dy < 14 * 14:
                gV[v].st = 1
                gRescued += 1
                P.score += 1000
                add_fx(gV[v].x, gV[v].y, 1)
                snd_event(SND_RESCUE)
                if gMode == MODE_TEAMS:
                    gTeam[P.team].rescues += 1
                    gTeam[P.team].score += 1000
                    msg(tr("msg_team_saved") % TEAMNAME[P.team])
                else:
                    msg(tr("msg_saved") % (gNumVictims - gRescued - gEaten))
        for m in range(MAX_MED):
            if gMed[m].taken:
                continue
            dx = gMed[m].x - P.x
            dy = gMed[m].y - P.y
            if dx * dx + dy * dy < 20 * 20:
                gMed[m].taken = 1
                gMed[m].respawnT = 25.0
                P.hp = 5
                P.ammo = min(float(ARMS[P.wpn][5]), P.ammo + 20)
                snd_event(SND_CONFIRM)
        for w in gWpnPick:
            if not w[3] or w[4]:
                continue
            dx = w[0] - P.x
            dy = w[1] - P.y
            if dx * dx + dy * dy < 20 * 20:
                w[4] = 1
                w[5] = 30.0
                wpn = w[2]
                if wpn not in P.inv and len(P.inv) < 9:
                    P.inv.append(wpn)
                P.wpn = wpn
                P.ammo = float(ARMS[wpn][5])
                gWpnMsgT = 2.2
                snd_event(SND_CONFIRM)
        for a in gAmmoPick:
            if not a[2] or a[3]:
                continue
            dx = a[0] - P.x
            dy = a[1] - P.y
            if dx * dx + dy * dy < 20 * 20:
                a[3] = 1
                a[4] = 30.0
                P.ammo = min(float(ARMS[P.wpn][5]), P.ammo + 30)
                snd_event(SND_CONFIRM)

    if gMode != MODE_TEAMS and not gDoorOpen and gRescued + gEaten == gNumVictims and gRescued > 0:
        gDoorOpen = 1
        snd_event(SND_DOOR)
        msg(tr("msg_door"))

    gSpawnT -= dt
    interval = 2.8 - gElapsed * 0.02
    if interval < 1.15:
        interval = 1.15
    if gMode == MODE_TEAMS:
        interval *= 0.8 if gTeamCount == 2 else 0.55
    if gSpawnT <= 0:
        gSpawnT = interval
        spawn_zombie()

    for i in range(MAX_ZOMBIES):
        z = gZ[i]
        if not z.used:
            continue
        z.animT += dt
        if z.st == 0:
            z.frame = int(z.animT * 5.0)
            if z.frame >= len(ZOM_RISE):
                z.st = 1
                z.animT = 0.0
                z.frame = 0
            continue
        if z.st == 2:
            z.frame = int(z.animT * 9.0)
            if z.frame >= len(ZOM_DIE):
                if z.respawns < 3 and respawn_zombie(z):
                    z.respawns += 1
                else:
                    z.used = 0
            continue
        if z.hurtT > 0:
            z.hurtT -= dt
        tx = ty = 0.0
        best = 1e18
        found = False
        for p in range(gNumPlayers):
            if not gP[p].used or not gP[p].alive:
                continue
            dx = gP[p].x - z.x
            dy = gP[p].y - z.y
            d = dx * dx + dy * dy
            if d < best:
                best = d
                tx, ty = gP[p].x, gP[p].y
                z.team = gP[p].team
                found = True
        for v in range(gNumVictims):
            if gV[v].st != 0:
                continue
            dx = gV[v].x - z.x
            dy = gV[v].y - z.y
            d = (dx * dx + dy * dy) * 3.2
            if d < best:
                best = d
                tx, ty = gV[v].x, gV[v].y
                found = True
        if not found:
            continue
        dx = tx - z.x
        dy = ty - z.y
        L = math.sqrt(dx * dx + dy * dy)
        if L > 1:
            dx /= L
            dy /= L
        sp = (34.0 + min(18.0, gElapsed * 0.22)) * ZOMBIE_KINDS[z.kind][2]
        nx = z.x + dx * sp * dt
        ny = z.y + dy * sp * dt
        moved_x = 0
        if box_free(nx, z.y + 4, 5, 3):
            z.x = nx
            moved_x = 1
        if box_free(z.x, ny + 4, 5, 3):
            z.y = ny
        elif not moved_x:
            if box_free(z.x + (1.0 if dx > 0 else -1.0) * sp * dt, z.y + 4, 5, 3):
                z.x += (1.0 if dx > 0 else -1.0) * sp * dt
        z.dir = 3 if abs(dx) > abs(dy) and dx > 0 else 1 if abs(dx) > abs(dy) else (0 if dy > 0 else 2)
        z.frame = int(z.animT * 6.0 * gAnimMul) % (4 * gAnimMul)
        for v in range(gNumVictims):
            if gV[v].st != 0:
                continue
            vx = gV[v].x - z.x
            vy = gV[v].y - z.y
            if vx * vx + vy * vy < 11 * 11:
                gV[v].st = 2
                gEaten += 1
                add_fx(gV[v].x, gV[v].y, 2)
                snd_event(SND_EATEN)
                msg(tr("msg_eaten"))
        for p in range(gNumPlayers):
            P = gP[p]
            if not P.used or not P.alive or P.hurtT > 0:
                continue
            px = P.x - z.x
            py = P.y - z.y
            if px * px + py * py < 11 * 11:
                P.hp -= ZOMBIE_KINDS[z.kind][3]
                P.hurtT = 1.0
                snd_event(SND_HURT)
                if P.hp <= 0:
                    P.lives -= 1
                    P.alive = 0
                    P.deaths += 1
                    P.deadT = 3.0 if gMode == MODE_TEAMS else 1.5
                    add_fx(P.x, P.y, 2)
                    if P.lives <= 0:
                        P.deadT = 1e9

    for i in range(MAX_BULLETS):
        b = gB[i]
        if not b.used:
            continue
        b.ttl -= dt
        b.x += b.vx * dt
        b.y += b.vy * dt
        if b.ttl <= 0 or not walkable_px(b.x, b.y):
            add_fx(b.x, b.y, 0)
            b.used = 0
            continue
        for j in range(MAX_ZOMBIES):
            z = gZ[j]
            if not b.used or not z.used or z.st != 1:
                continue
            dx = z.x - b.x
            dy = (z.y - 8) - b.y
            if dx * dx + dy * dy < 10 * 10:
                b.used = 0
                add_fx(b.x, b.y, 0)
                z.hp -= 1
                z.hurtT = 0.1
                snd_event(SND_HIT)
                if z.hp <= 0:
                    z.st = 2
                    z.animT = 0.0
                    snd_event(SND_ZDIE)
                    O = gP[b.owner]
                    O.score += 150
                    if gMode == MODE_TEAMS:
                        gTeam[O.team].score += 150
                break
        if gMode == MODE_TEAMS and b.used:
            for p in range(gNumPlayers):
                if not b.used:
                    break
                T = gP[p]
                if not T.used or not T.alive or p == b.owner:
                    continue
                if T.team == gP[b.owner].team:
                    continue
                if T.stunT > 0:
                    continue
                dx = T.x - b.x
                dy = (T.y - 6) - b.y
                if dx * dx + dy * dy < 9 * 9:
                    if T.shieldT > 0:
                        b.owner = p
                        b.vx = -b.vx
                        b.vy = -b.vy
                        b.x = T.x + (b.vx / max(1.0, math.hypot(b.vx, b.vy))) * 10.0
                        b.y = T.y + (b.vy / max(1.0, math.hypot(b.vx, b.vy))) * 10.0
                        snd_event(SND_STUN)
                        continue
                    b.used = 0
                    add_fx(b.x, b.y, 0)
                    T.stunT = 0.7
                    kx = b.vx * 0.03
                    ky = b.vy * 0.03
                    if box_free(T.x + kx, T.y + 4, 5, 3):
                        T.x += kx
                    if box_free(T.x, T.y + ky + 4, 5, 3):
                        T.y += ky
                    T.hp -= 1
                    if T.hp <= 0:
                        T.alive = 0
                        T.deadT = 2.0
                        T.deaths += 1
                        O = gP[b.owner]
                        O.kills += 1
                        O.score += 500
                        gTeam[O.team].score += 500
                    snd_event(SND_STUN)

    for i in range(MAX_FX):
        f = gFx[i]
        if not f.used:
            continue
        f.t += dt
        lim = 1.1 if f.type == 1 else 0.4
        if f.t > lim:
            f.used = 0
    for v in range(gNumVictims):
        if gV[v].st == 0:
            gV[v].animT += dt * 5.0
            gV[v].frame = int(gV[v].animT) % len(VIC_FRAMES[VIC_BASE[gV[v].type] if gV[v].type < len(VIC_BASE) else 0])


# ---------------- 3D perspective ----------------
HZ3D = 92                    # horizon row
F3D = 260.0                  # focal length (world px)
CAM_D3D = 132.0              # camera sits this far south of the player
VOID3D = (12, 16, 14)        # out-of-map color
gCam3DX = gCam3DY = 0.0
_sky_cache_day = None
_sky_cache_night = None


def proj3d(wx, wy):
    d = gCam3DY - wy
    if d <= 4.0:
        return None
    s = F3D / (F3D + d)
    sx = VIEW_W / 2.0 + (wx - gCam3DX) * s
    sy = HZ3D + (VIEW_H - HZ3D) * s
    return sx, sy, s


def shadow3d(surf, wx, wy, wpx):
    p = proj3d(wx, wy)
    if p is None:
        return
    sx, sy, s = p
    w = max(3, int(wpx * s))
    surf.fill((10, 14, 12), (int(sx - w / 2.0), int(sy - w * 0.22), w, max(2, int(w * 0.22))))


def blit3d(surf, tex, fr, wx, wy, flip):
    p = proj3d(wx, wy)
    if p is None:
        return
    sx, sy, s = p
    x, y, w, h = fr
    w2 = max(2, int(w * s))
    h2 = max(2, int(h * s))
    src = pygame.Rect(x, y, w, h)
    sub = tex.subsurface(src)
    if flip:
        sub = pygame.transform.flip(sub, True, False)
    if w2 != w or h2 != h:
        sub = pygame.transform.scale(sub, (w2, h2))
    surf.blit(sub, (int(sx - w2 / 2.0), int(sy - h2)))


def draw_sky_3d():
    global _sky_cache_day, _sky_cache_night
    night = gLevelSel == 1
    cache = _sky_cache_night if night else _sky_cache_day
    if cache is None or cache.get_size() != (VIEW_W, HZ3D):
        s = pygame.Surface((VIEW_W, HZ3D))
        if night:
            stops = [(2, 2, 10), (6, 6, 22), (12, 10, 34), (30, 20, 54), (66, 34, 84)]
            n = len(stops)
            for yy in range(HZ3D):
                t = yy / max(1, HZ3D - 1)
                i = min(n - 2, int(t * (n - 1)))
                f = t * (n - 1) - i
                c1, c2 = stops[i], stops[i + 1]
                s.fill((int(c1[0] + (c2[0] - c1[0]) * f),
                        int(c1[1] + (c2[1] - c1[1]) * f),
                        int(c1[2] + (c2[2] - c1[2]) * f)), (0, yy, VIEW_W, 1))
            rnd = 12345
            for k in range(140):
                rnd = (rnd * 16807) % 2147483647
                sx = rnd % VIEW_W
                rnd = (rnd * 16807) % 2147483647
                sy = rnd % (HZ3D - 8)
                rnd = (rnd * 16807) % 2147483647
                b = rnd % 3
                s.fill((180 + b * 25, 190 + b * 20, 220), (sx, sy, 1, 1))
        else:
            stops = [(8, 10, 26), (18, 22, 44), (36, 40, 62), (64, 72, 86), (96, 110, 96)]
            n = len(stops)
            for yy in range(HZ3D):
                t = yy / max(1, HZ3D - 1)
                i = min(n - 2, int(t * (n - 1)))
                f = t * (n - 1) - i
                c1, c2 = stops[i], stops[i + 1]
                s.fill((int(c1[0] + (c2[0] - c1[0]) * f),
                        int(c1[1] + (c2[1] - c1[1]) * f),
                        int(c1[2] + (c2[2] - c1[2]) * f)), (0, yy, VIEW_W, 1))
        if night:
            _sky_cache_night = s
        else:
            _sky_cache_day = s
        cache = s
    vbuf.blit(cache, (0, 0))


def draw_ground_3d():
    step = 6
    sy0 = HZ3D
    span = float(VIEW_H - HZ3D)
    while sy0 <= VIEW_H:
        sy1 = min(VIEW_H, sy0 + step - 1)
        sm = (sy0 + sy1) / 2.0
        t = (sm - HZ3D) / span
        if t <= 0.001:
            vbuf.fill(VOID3D, (0, sy0, VIEW_W, sy1 - sy0 + 1))
            sy0 = sy1 + 1
            continue
        d = F3D * (VIEW_H - sm) / (sm - HZ3D)
        worldY = gCam3DY - d
        band_h = sy1 - sy0 + 1
        if worldY < -60 or worldY >= MAP_H:
            vbuf.fill(VOID3D, (0, sy0, VIEW_W, band_h))
            sy0 = sy1 + 1
            continue
        wyi = max(0, min(MAP_H - 1, int(worldY)))
        halfW = (VIEW_W / 2.0) / t
        x0 = gCam3DX - halfW
        x1 = gCam3DX + halfW
        src_x0 = max(0, int(x0))
        src_x1 = min(MAP_W, int(x1))
        if src_x1 <= src_x0:
            vbuf.fill(VOID3D, (0, sy0, VIEW_W, band_h))
            sy0 = sy1 + 1
            continue
        ww = src_x1 - src_x0
        sub = texLevel.subsurface(pygame.Rect(src_x0, wyi, ww, 1))
        scaled = pygame.transform.scale(sub, (VIEW_W, band_h))
        vis_w = int((x1 - x0) > 0 and (ww * VIEW_W) / (x1 - x0) + 0.999) or VIEW_W
        vis_w = min(VIEW_W, vis_w)
        off = min(VIEW_W, max(0, int((src_x0 - x0) * VIEW_W / (x1 - x0))))
        if off > 0:
            vbuf.fill(VOID3D, (0, sy0, off, band_h))
        vbuf.blit(scaled, (off, sy0), pygame.Rect(0, 0, vis_w, band_h))
        tail = VIEW_W - off - vis_w
        if tail > 0:
            vbuf.fill(VOID3D, (off + vis_w, sy0, tail, band_h))
        sy0 = sy1 + 1


def render_game_3d():
    update_camera()
    draw_sky_3d()
    draw_ground_3d()
    objs = []
    if gMode != MODE_TEAMS:
        objs.append((gDoorY, ("door", 0)))
    for m in range(MAX_MED):
        if not gMed[m].taken:
            objs.append((gMed[m].y, ("med", m)))
    for wi in range(len(gWpnPick)):
        if gWpnPick[wi][3] and not gWpnPick[wi][4]:
            objs.append((gWpnPick[wi][1], ("wpn", wi)))
    for ai in range(len(gAmmoPick)):
        if gAmmoPick[ai][2] and not gAmmoPick[ai][3]:
            objs.append((gAmmoPick[ai][1], ("ammo", ai)))
    for v in range(gNumVictims):
        if gV[v].st == 0:
            objs.append((gV[v].y, ("vic", v)))
    for i in range(MAX_ZOMBIES):
        if gZ[i].used:
            objs.append((gZ[i].y, ("zom", i)))
    for p in range(gNumPlayers):
        P = gP[p]
        if P.used and P.alive:
            objs.append((P.y, ("pl", p)))
    for i in range(MAX_BULLETS):
        if gB[i].used:
            objs.append((gB[i].y, ("bul", i)))
    for i in range(MAX_FX):
        if gFx[i].used:
            objs.append((gFx[i].y, ("fx", i)))
    objs.sort(key=lambda o: o[0], reverse=True)
    for _, (kind, i) in objs:
        draw3d_obj(kind, i)
    if gMsgT > 0 and gMsg:
        draw_text_c(vbuf, VIEW_W // 2, VIEW_H - 18, 1, (255, 255, 255), gMsg)
    draw_map_frame()
    draw_dota_hud()


def draw3d_obj(kind, i):
    if kind == "door":
        shadow3d(vbuf, gDoorX, gDoorY + 38, 34)
        blit3d(vbuf, texDoor, DOOR_OPEN if gDoorOpen else DOOR_CLOSED, gDoorX, gDoorY + 38, False)
    elif kind == "med":
        m = gMed[i]
        shadow3d(vbuf, m.x, m.y + 8, 16)
        blit3d(vbuf, texItems, (64, 89, 16, 13), m.x, m.y + 8, False)
    elif kind == "wpn":
        w = gWpnPick[i]
        shadow3d(vbuf, w[0], w[1] + 8, 22)
        icon = pygame.transform.scale(texWeapons[w[2]], (24, 16))
        blit3d(vbuf, icon, (0, 0, 24, 16), w[0], w[1] + 8, False)
    elif kind == "ammo":
        a = gAmmoPick[i]
        shadow3d(vbuf, a[0], a[1] + 8, 20)
        p = proj3d(a[0], a[1])
        if p is not None:
            sx, sy, s = p
            r = max(3, int(8 * s))
            vbuf.fill((38, 112, 60), (int(sx) - r, int(sy) - r, r * 2, r * 2))
            pygame.draw.rect(vbuf, (180, 255, 130), (int(sx) - r, int(sy) - r, r * 2, r * 2), 1)
    elif kind == "vic":
        v = gV[i]
        vtex, vframes = victim_tex(v.type)
        fr = vframes[v.frame % len(vframes)]
        shadow3d(vbuf, v.x, v.y + 8, 30)
        blit3d(vbuf, vtex, fr, v.x, v.y + 8, False)
    elif kind == "zom":
        z = gZ[i]
        ztex = zombie_tex(z.kind)
        if z.st == 0:
            f = min(z.frame, len(ZOM_RISE) - 1)
            shadow3d(vbuf, z.x, z.y + 8, 34)
            blit3d(vbuf, ztex, ZOM_RISE[f], z.x, z.y + 8, False)
        elif z.st == 2:
            f = min(z.frame, len(ZOM_DIE) - 1)
            blit3d(vbuf, ztex, ZOM_DIE[f], z.x, z.y + 8, False)
        else:
            flip = False
            if gAnimMul == 2:
                tz = ztex
                if z.dir == 0:
                    set_f = ZOM2_DOWN
                elif z.dir == 2:
                    set_f = ZOM2_UP
                elif z.dir == 3:
                    set_f = ZOM2_RIGHT
                else:
                    set_f = ZOM2_RIGHT
                    flip = True
            else:
                tz = ztex
                if z.dir == 0:
                    set_f = ZOM_DOWN
                elif z.dir == 2:
                    set_f = ZOM_UP
                elif z.dir == 3:
                    set_f = ZOM_RIGHT
                else:
                    set_f = ZOM_RIGHT
                    flip = True
            fr = set_f[z.frame % len(set_f)]
            dip = int(math.sin((z.animT % 1.0) * 6.28318)) if z.st == 1 else 0
            shadow3d(vbuf, z.x, z.y + 8, 34)
            blit3d(vbuf, tz, fr, z.x + (dip if z.dir == 3 else -dip if z.dir == 1 else 0),
                   z.y + 8 + (dip if z.dir == 0 else -dip if z.dir == 2 else 0), flip)
    elif kind == "pl":
        render_player_3d(gP[i], i)
    elif kind == "bul":
        b = gB[i]
        p = proj3d(b.x, b.y)
        if p is None:
            return
        sx, sy, s = p
        r = max(1, int(1.6 * s))
        vbuf.fill((90, 160, 255), (int(sx) - r, int(sy) - r, r * 2 + 1, r * 2 + 1))
        vbuf.fill((220, 240, 255), (int(sx) - max(1, r // 2), int(sy) - max(1, r // 2), max(1, r), max(1, r)))
    elif kind == "fx":
        f = gFx[i]
        if f.type == 1:
            fi = min(int(f.t * 3.0), 2)
            shadow3d(vbuf, f.x, f.y + 8, 26)
            blit3d(vbuf, texVict, FX_ANGEL[fi], f.x, f.y + 8 - f.t * 22.0, False)
        elif f.type == 3:
            p = proj3d(f.x, f.y)
            if p is None:
                return
            sx, sy, s = p
            big = f.t < 0.03
            r = max(2, int((4 if big else 2) * s))
            vbuf.fill((255, 240, 140), (int(sx) - r, int(sy) - r, r * 2 + 1, r * 2 + 1))
            vbuf.fill((255, 255, 255), (int(sx) - r // 2, int(sy) - r // 2, r + 1, r + 1))
            vbuf.fill((255, 200, 60), (int(sx) - 1, int(sy) - 1, 3, 3))
        else:
            fi = min(int(f.t * 8.0), 2)
            shadow3d(vbuf, f.x, f.y, 20)
            blit3d(vbuf, texVict, FX_SPARKLE[fi], f.x, f.y, False)


def update_camera():
    s = gLocalSlot
    if s >= gNumPlayers or not gP[s].used:
        s = 0
    global gCamX, gCamY, gCamShakeT, gCam3DX, gCam3DY
    gCamX = gP[s].x - VIEW_W / 2.0
    gCamY = gP[s].y - VIEW_H / 2.0
    if g3D:
        gCam3DX = gP[s].x
        gCam3DY = gP[s].y + CAM_D3D
        if gCamShakeT > 0:
            gCam3DX += random.uniform(-2.0, 2.0)
            gCam3DY += random.uniform(-2.0, 2.0)
        gCam3DX = max(-VIEW_W, min(MAP_W + VIEW_W, gCam3DX))
        gCam3DY = max(-VIEW_H, min(MAP_H + VIEW_H, gCam3DY))
    else:
        if gCamShakeT > 0:
            gCamShakeT -= 1.0 / 60.0
            gCamX += random.uniform(-2.0, 2.0)
            gCamY += random.uniform(-2.0, 2.0)
        if gCamX < 0:
            gCamX = 0
        if gCamY < 0:
            gCamY = 0
        if gCamX > MAP_W - VIEW_W:
            gCamX = MAP_W - VIEW_W
        if gCamY > MAP_H - VIEW_H:
            gCamY = MAP_H - VIEW_H


# ---------------- rendering ----------------
def blit_sheet(surf, tex, fr, wx, wy, flip):
    x, y, w, h = fr
    dx = int(wx - w / 2.0 - gCamX)
    dy = int(wy - h - gCamY)
    src = pygame.Rect(x, y, w, h)
    if flip:
        bl = tex.subsurface(src)
        bl = pygame.transform.flip(bl, True, False)
        surf.blit(bl, (dx, dy))
    else:
        surf.blit(tex, (dx, dy), src)


def blit_centered(surf, tex, fr, wx, wy):
    x, y, w, h = fr
    dx = int(wx - w / 2.0 - gCamX)
    dy = int(wy - h / 2.0 - gCamY)
    surf.blit(tex, (dx, dy), pygame.Rect(x, y, w, h))


def player_sprite(P, slot_idx=0):
    if P.charId == 8:
        # custom character: sex + palette recolor, extras per net params.
        # If the player designed a sprite in the editor, it overrides the recolor.
        params = custom_params(slot_idx)
        tex = custom_tex_any(params)
        sexo = params[0]
        if tex is None:
            tex = texZeke if sexo == 0 else texJulie
        flip = False
        if tex is texDrawn:
            rects = _sheet_rects(tex)
            rows = len(rects) // 8
            if rows >= 4:
                # Custom sheets have the canonical order: DOWN, LEFT, UP,
                # RIGHT. Do not mirror or swap the lateral rows.
                set_f = rects[P.dir * 8:(P.dir + 1) * 8]
                flip = False
            elif P.dir == 1 and rows >= 2:
                # Swapped legacy sheets have RIGHT only; mirror it for LEFT.
                set_f = rects[8:16]
                flip = True
            elif P.dir == 3 and rows >= 2:
                set_f = rects[8:16]
                flip = False
            elif P.dir >= rows:
                set_f = rects[(P.dir % rows) * 8:(P.dir % rows) * 8 + 8]
                flip = False
            else:
                set_f = rects[P.dir * 8:(P.dir + 1) * 8]
                flip = False
            return tex, set_f, 8, flip
        if gAnimMul == 2:
            if sexo == 0:
                if P.dir == 0:
                    set_f, set_n = ZEKE2_DOWN, len(ZEKE2_DOWN)
                elif P.dir == 2:
                    set_f, set_n = ZEKE2_UP, len(ZEKE2_UP)
                else:
                    set_f, set_n = ZEKE2_LEFT, len(ZEKE2_LEFT)
                    flip = P.dir == 1
            else:
                if P.dir == 0:
                    set_f, set_n = JULIE2_DOWN, len(JULIE2_DOWN)
                elif P.dir == 2:
                    set_f, set_n = JULIE2_UP, len(JULIE2_UP)
                elif P.dir == 3:
                    set_f, set_n = JULIE2_RIGHT, len(JULIE2_RIGHT)
                else:
                    set_f, set_n = JULIE2_LEFT, len(JULIE2_LEFT)
        else:
            if sexo == 0:
                if P.dir == 0:
                    set_f, set_n = ZEKE_DOWN, len(ZEKE_DOWN)
                elif P.dir == 2:
                    set_f, set_n = ZEKE_UP, len(ZEKE_UP)
                elif P.dir == 1:
                    set_f, set_n = ZEKE_LEFT, len(ZEKE_LEFT)
                    flip = True
                else:
                    set_f, set_n = ZEKE_LEFT, len(ZEKE_LEFT)
            else:
                if P.dir == 0:
                    set_f, set_n = JULIE_DOWN, len(JULIE_DOWN)
                elif P.dir == 2:
                    set_f, set_n = JULIE_UP, len(JULIE_UP)
                elif P.dir == 3:
                    set_f, set_n = JULIE_RIGHT, len(JULIE_RIGHT)
                else:
                    set_f, set_n = JULIE_LEFT, len(JULIE_LEFT)
        return tex, set_f, set_n, flip
    char = P.charId % 8
    is_zeke = char in (0, 2, 4, 6, 7)
    tex = texChars[char]
    flip = False
    if gAnimMul == 2:
        if is_zeke:
            if P.dir == 0:
                set_f, set_n = ZEKE2_DOWN, len(ZEKE2_DOWN)
            elif P.dir == 2:
                set_f, set_n = ZEKE2_UP, len(ZEKE2_UP)
            else:
                set_f, set_n = ZEKE2_LEFT, len(ZEKE2_LEFT)
                flip = P.dir == 1
        else:
            if P.dir == 0:
                set_f, set_n = JULIE2_DOWN, len(JULIE2_DOWN)
            elif P.dir == 2:
                set_f, set_n = JULIE2_UP, len(JULIE2_UP)
            elif P.dir == 3:
                set_f, set_n = JULIE2_RIGHT, len(JULIE2_RIGHT)
            else:
                set_f, set_n = JULIE2_LEFT, len(JULIE2_LEFT)
    else:
        if is_zeke:
            if P.dir == 0:
                set_f, set_n = ZEKE_DOWN, len(ZEKE_DOWN)
            elif P.dir == 2:
                set_f, set_n = ZEKE_UP, len(ZEKE_UP)
            elif P.dir == 1:
                set_f, set_n = ZEKE_LEFT, len(ZEKE_LEFT)
                flip = True
            else:
                set_f, set_n = ZEKE_LEFT, len(ZEKE_LEFT)
        else:
            if P.dir == 0:
                set_f, set_n = JULIE_DOWN, len(JULIE_DOWN)
            elif P.dir == 2:
                set_f, set_n = JULIE_UP, len(JULIE_UP)
            elif P.dir == 3:
                set_f, set_n = JULIE_RIGHT, len(JULIE_RIGHT)
            else:
                set_f, set_n = JULIE_LEFT, len(JULIE_LEFT)
    return tex, set_f, set_n, flip


def render_player(P, slot_idx):
    if not P.used or not P.alive:
        return
    if P.hurtT > 0 and (int(P.hurtT * 12) & 1):
        return
    # drop shadow (2D mode only — 3D has its own shadow3d)
    if not g3D:
        shadow2d(vbuf, P.x, P.y + 8, 24)
    tex, set_f, set_n, flip = player_sprite(P, slot_idx)
    ox = oy = 0.0
    if P.recoilT > 0:
        if P.dir == 3:
            ox = -2.0
        elif P.dir == 1:
            ox = 2.0
        elif P.dir == 0:
            oy = -2.0
        elif P.dir == 2:
            oy = 2.0
    dip = int(math.sin((P.animT % 1.0) * 6.28318)) if P.animT > 0 else 0
    ox += (dip if P.dir == 3 else -dip if P.dir == 1 else 0)
    oy += (dip if P.dir == 0 else -dip if P.dir == 2 else 0)
    oy -= max(0, min(80, int(P.jumpV * P.jumpT)))
    if P.stunT > 0:
        fr = set_f[P.frame % set_n]
        x, y, w, h = fr
        sub = tex.subsurface(pygame.Rect(x, y, w, h))
        sub = sub.copy()
        tint = pygame.Surface(sub.get_size(), pygame.SRCALPHA)
        tint.fill((130, 160, 255, 0))
        tint.blit(sub, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        # lighter tint: blend
        tint2 = pygame.Surface(sub.get_size(), pygame.SRCALPHA)
        tint2.fill((130, 160, 255))
        tint2.blit(sub, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sub = tint2
        dx = int(P.x - w / 2.0 - gCamX)
        dy = int(P.y + 8 - h - gCamY)
        if flip:
            sub = pygame.transform.flip(sub, True, False)
        vbuf.blit(sub, (dx, dy))
    else:
        if flip:
            blit_sheet(vbuf, tex, set_f[P.frame % set_n], P.x + ox, P.y + 8 + oy, True)
        else:
            blit_sheet(vbuf, tex, set_f[P.frame % set_n], P.x + ox, P.y + 8 + oy, False)
    if P.shieldT > 0:
        sx, sy = int(P.x - gCamX), int(P.y - gCamY - 16)
        pygame.draw.circle(vbuf, (95, 190, 255), (sx, sy), 15, 2)
        pygame.draw.arc(vbuf, (220, 250, 255), (sx - 17, sy - 17, 34, 34), 0.4, 2.7, 2)
    if gMode == MODE_TEAMS:
        c = TEAMCOL[P.team]
        sx = int(P.x - gCamX)
        sy = int(P.y - gCamY)
        vbuf.fill(c, (sx - 2, sy - 34, 5, 3))
        vbuf.fill(c, (sx - 1, sy - 31, 3, 2))
        vbuf.fill((20, 20, 20), (sx - 8, sy - 28, 16, 3))
        hpc = (80, 220, 60) if P.hp > 2 else (230, 60, 60)
        vbuf.fill(hpc, (sx - 7, sy - 27, int(14 * min(5, P.hp) / 5), 1))
        if slot_idx == gLocalSlot:
            draw_text(vbuf, sx - 14, sy - 38, 1, (255, 255, 255), "YOU")
        elif P.ctrl == CTRL_BOT:
            draw_text(vbuf, sx + 6, sy - 36, 1, (160, 160, 160), "C")


def render_player_3d(P, slot_idx):
    if not P.used or not P.alive:
        return
    if P.hurtT > 0 and (int(P.hurtT * 12) & 1):
        return
    tex, set_f, set_n, flip = player_sprite(P, slot_idx)
    ox = oy = 0.0
    if P.recoilT > 0:
        if P.dir == 3:
            ox = -2.0
        elif P.dir == 1:
            ox = 2.0
        elif P.dir == 0:
            oy = -2.0
        elif P.dir == 2:
            oy = 2.0
    dip = int(math.sin((P.animT % 1.0) * 6.28318)) if P.animT > 0 else 0
    ox += (dip if P.dir == 3 else -dip if P.dir == 1 else 0)
    oy += (dip if P.dir == 0 else -dip if P.dir == 2 else 0)
    oy -= max(0, min(80, int(P.jumpV * P.jumpT)))
    wx = P.x + ox
    wy = P.y + 8 + oy
    if P.stunT > 0:
        fr = set_f[P.frame % set_n]
        x, y, w, h = fr
        sub = tex.subsurface(pygame.Rect(x, y, w, h)).copy()
        tint2 = pygame.Surface(sub.get_size(), pygame.SRCALPHA)
        tint2.fill((130, 160, 255))
        tint2.blit(sub, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        sub = tint2
        p = proj3d(wx, wy)
        if p is None:
            return
        sx, sy, s = p
        w2 = max(2, int(w * s))
        h2 = max(2, int(h * s))
        if flip:
            sub = pygame.transform.flip(sub, True, False)
        if w2 != w or h2 != h:
            sub = pygame.transform.scale(sub, (w2, h2))
        vbuf.blit(sub, (int(sx - w2 / 2.0), int(sy - h2)))
    else:
        shadow3d(vbuf, wx, wy, 26)
        blit3d(vbuf, tex, set_f[P.frame % set_n], wx, wy, flip)
    if P.shieldT > 0:
        p = proj3d(wx, wy)
        if p is not None:
            sx, sy, s = p
            r = max(5, int(15 * s))
            pygame.draw.circle(vbuf, (95, 190, 255), (int(sx), int(sy - 16 * s)), r, max(1, int(2 * s)))
    if gMode == MODE_TEAMS:
        p = proj3d(wx, wy)
        if p is None:
            return
        sx, sy, s = p
        c = TEAMCOL[P.team]
        vbuf.fill(c, (int(sx - 2), int(sy - 24 * s), max(2, int(5 * s)), max(1, int(3 * s))))
        vbuf.fill(c, (int(sx - 1), int(sy - 21 * s), max(2, int(3 * s)), max(1, int(2 * s))))
        vbuf.fill((20, 20, 20), (int(sx - 6), int(sy - 19 * s), max(4, int(16 * s)), max(2, int(3 * s))))
        hpc = (80, 220, 60) if P.hp > 2 else (230, 60, 60)
        vbuf.fill(hpc, (int(sx - 5), int(sy - 18 * s), max(2, int(14 * min(5, P.hp) / 5 * s)), 1))
        if slot_idx == gLocalSlot:
            draw_text(vbuf, int(sx - 14), int(sy - 27 * s), 1, (255, 255, 255), "YOU")
        elif P.ctrl == CTRL_BOT:
            draw_text(vbuf, int(sx + 6), int(sy - 25 * s), 1, (160, 160, 160), "C")


def shadow2d(surf, wx, wy, wpx):
    sx = int(wx - gCamX)
    sy = int(wy - gCamY)
    surf.fill((10, 14, 12), (sx - wpx // 2, sy - max(2, wpx // 8), wpx, max(2, wpx // 5)))


def draw_water_edges():
    """Draw a restrained cyan lip on walkable/non-walkable water boundaries."""
    for tile in gEdgeTiles:
        tx, ty = tile % TW, tile // TW
        sx, sy = tx * TS - int(gCamX), ty * TS - int(gCamY)
        if sx < -TS or sy < -TS or sx >= VIEW_W or sy >= VIEW_H:
            continue
        edge = (55, 145, 175)
        if tx > 0 and not gWalk[ty * TW + tx - 1]:
            pygame.draw.line(vbuf, edge, (sx, sy + 2), (sx, sy + TS - 2), 1)
        if tx + 1 < TW and not gWalk[ty * TW + tx + 1]:
            pygame.draw.line(vbuf, edge, (sx + TS - 1, sy + 2), (sx + TS - 1, sy + TS - 2), 1)
        if ty > 0 and not gWalk[(ty - 1) * TW + tx]:
            pygame.draw.line(vbuf, edge, (sx + 2, sy), (sx + TS - 2, sy), 1)
        if ty + 1 < TH and not gWalk[(ty + 1) * TW + tx]:
            pygame.draw.line(vbuf, edge, (sx + 2, sy + TS - 1), (sx + TS - 2, sy + TS - 1), 1)


def render_game():
    update_camera()
    vbuf.blit(texLevel, (0, 0), pygame.Rect(int(gCamX), int(gCamY), VIEW_W, VIEW_H))
    draw_water_edges()
    for bx, by in BOUNCE_LAYOUT[gLevelSel % WORLD_COUNT]:
        sx, sy = int(bx - gCamX), int(by - gCamY)
        pygame.draw.ellipse(vbuf, (190, 70, 210), (sx - 12, sy - 5, 24, 10), 2)
        pygame.draw.line(vbuf, (255, 180, 255), (sx - 8, sy), (sx + 8, sy), 2)
    if gMode != MODE_TEAMS:
        shadow2d(vbuf, gDoorX, gDoorY + 38, 32)
        blit_sheet(vbuf, texDoor, DOOR_OPEN if gDoorOpen else DOOR_CLOSED, gDoorX, gDoorY + 38, False)
    for m in range(MAX_MED):
        if not gMed[m].taken:
            shadow2d(vbuf, gMed[m].x, gMed[m].y + 8, 14)
            blit_sheet(vbuf, texItems, (64, 89, 16, 13), gMed[m].x, gMed[m].y + 8, False)
    for w in gWpnPick:
        if not w[3] or w[4]:
            continue
        sx = int(w[0] - gCamX)
        sy = int(w[1] - gCamY)
        pulse = 1 + int(gZomWalkT * 6) % 2
        shadow2d(vbuf, w[0], w[1] + 8, 22)
        icon = texWeapons[w[2]]
        icon = pygame.transform.scale(icon, (24, 16 + pulse))
        vbuf.blit(icon, (sx - 12, sy - 10 - pulse))
    for a in gAmmoPick:
        if not a[2] or a[3]:
            continue
        sx, sy = int(a[0] - gCamX), int(a[1] - gCamY)
        vbuf.fill((38, 112, 60), (sx - 8, sy - 6, 16, 12))
        pygame.draw.rect(vbuf, (180, 255, 130), (sx - 8, sy - 6, 16, 12), 1)
        draw_text(vbuf, sx - 5, sy - 4, 1, (235, 255, 180), "AM")
    for v in range(gNumVictims):
        if gV[v].st != 0:
            continue
        shadow2d(vbuf, gV[v].x, gV[v].y + 8, 28)
        vtex, frames = victim_tex(gV[v].type)
        blit_sheet(vbuf, vtex, frames[gV[v].frame % len(frames)], gV[v].x, gV[v].y + 8, False)
    for i in range(MAX_ZOMBIES):
        z = gZ[i]
        if not z.used:
            continue
        shadow2d(vbuf, z.x, z.y + 8, 30)
        ztex = zombie_tex(z.kind)
        if z.st == 0:
            f = min(z.frame, len(ZOM_RISE) - 1)
            blit_sheet(vbuf, ztex, ZOM_RISE[f], z.x, z.y + 8, False)
        elif z.st == 2:
            f = min(z.frame, len(ZOM_DIE) - 1)
            blit_sheet(vbuf, ztex, ZOM_DIE[f], z.x, z.y + 8, False)
        else:
            flip = False
            if gAnimMul == 2:
                tz = ztex
                if z.dir == 0:
                    set_f = ZOM2_DOWN
                elif z.dir == 2:
                    set_f = ZOM2_UP
                elif z.dir == 3:
                    set_f = ZOM2_RIGHT
                else:
                    set_f = ZOM2_RIGHT
                    flip = True
            else:
                tz = ztex
                if z.dir == 0:
                    set_f = ZOM_DOWN
                elif z.dir == 2:
                    set_f = ZOM_UP
                elif z.dir == 3:
                    set_f = ZOM_RIGHT
                else:
                    set_f = ZOM_RIGHT
                    flip = True
            fr = set_f[z.frame % len(set_f)]
            dip = int(math.sin((z.animT % 1.0) * 6.28318)) if z.st == 1 else 0
            ox = (dip if z.dir == 3 else -dip if z.dir == 1 else 0)
            oy = (dip if z.dir == 0 else -dip if z.dir == 2 else 0)
            if z.hurtT > 0:
                x, y, w, h = fr
                sub = tz.subsurface(pygame.Rect(x, y, w, h)).copy()
                tint = pygame.Surface(sub.get_size(), pygame.SRCALPHA)
                tint.fill((255, 120, 120))
                tint.blit(sub, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                sub = tint
                dx = int(z.x + ox - w / 2.0 - gCamX)
                dy = int(z.y + 8 + oy - h - gCamY)
                if flip:
                    sub = pygame.transform.flip(sub, True, False)
                vbuf.blit(sub, (dx, dy))
            else:
                blit_sheet(vbuf, tz, fr, z.x + ox, z.y + 8 + oy, flip)
        if z.st != 2:
            sx, sy = int(z.x - gCamX), int(z.y - gCamY)
            max_hp = max(1, ZOMBIE_KINDS[z.kind][1])
            bar_w = 28
            fill_w = max(1, int(bar_w * max(0, z.hp) / max_hp))
            team_col = TEAMCOL[z.team % len(TEAMCOL)]
            vbuf.fill((12, 8, 16), (sx - bar_w // 2, sy - 45, bar_w, 5))
            pygame.draw.rect(vbuf, team_col, (sx - bar_w // 2, sy - 45, bar_w, 5), 1)
            vbuf.fill(team_col, (sx - bar_w // 2 + 1, sy - 44, fill_w - 1, 3))
    for p in range(gNumPlayers):
        render_player(gP[p], p)
    upper = world_upper()
    if upper is not None:
        vbuf.blit(upper, (0, 0), pygame.Rect(int(gCamX), int(gCamY), VIEW_W, VIEW_H))
    for i in range(MAX_BULLETS):
        b = gB[i]
        if not b.used:
            continue
        vbuf.fill((90, 160, 255), (int(b.x - gCamX) - 1, int(b.y - gCamY) - 1, 3, 3))
        vbuf.fill((220, 240, 255), (int(b.x - gCamX), int(b.y - gCamY), 1, 1))
    for i in range(MAX_FX):
        f = gFx[i]
        if not f.used:
            continue
        if f.type == 1:
            fi = min(int(f.t * 3.0), 2)
            blit_sheet(vbuf, texVict, FX_ANGEL[fi], f.x, f.y + 8 - f.t * 22.0, False)
        elif f.type == 3:
            # muzzle flash
            sx = int(f.x - gCamX)
            sy = int(f.y - gCamY)
            big = f.t < 0.03
            s = 4 if big else 2
            vbuf.fill((255, 240, 140), (sx - s, sy - s, s * 2 + 1, s * 2 + 1))
            vbuf.fill((255, 255, 255), (sx - s // 2, sy - s // 2, s + 1, s + 1))
            vbuf.fill((255, 200, 60), (sx - 1, sy - 1, 3, 3))
        else:
            fi = min(int(f.t * 8.0), 2)
            blit_sheet(vbuf, texVict, FX_SPARKLE[fi], f.x, f.y, False)
    if gMsgT > 0 and gMsg:
        draw_text_c(vbuf, VIEW_W // 2, VIEW_H - 18, 1, (255, 255, 255), gMsg)
    draw_map_frame()
    draw_dota_hud()


def draw_dota_hud():
    # Minimal gameplay status: no full-width top bar.
    left = gNumVictims - gRescued - gEaten
    if gMode == MODE_TEAMS:
        for t in range(gTeamCount):
            hy = 4 + t * 11
            vbuf.fill(TEAMCOL[t], (6, hy, 7, 7))
            pygame.draw.rect(vbuf, (235, 230, 210), (6, hy, 7, 7), 1)
            draw_text(vbuf, 17, hy, 1, TEAMCOL[t], "%s  %02d" % (TEAMNAME[t][0], gTeam[t].rescues))
        draw_text_sh(vbuf, VIEW_W - 82, 5, 1, (255, 230, 120), "%02d/%02d" % (left, gNumVictims))
    else:
        P = gP[0]
        draw_text_sh(vbuf, 6, 5, 1, (120, 255, 120), "%s %06d" % (char_name(min(P.charId, 7)), P.score))
        draw_text_sh(vbuf, VIEW_W - 82, 5, 1, (255, 230, 120), "%02d/%02d" % (left, gNumVictims))

    me = gP[gLocalSlot] if (gMode == MODE_TEAMS and 0 <= gLocalSlot < gNumPlayers and gP[gLocalSlot].used) else \
        (gP[0] if gMode != MODE_TEAMS else None)
    if me is None:
        return
    # hero panel bottom-center (Dota-style)
    px, py = 132, 226
    neon = gLevelSel == 1
    hborder = (90, 220, 255) if neon else _gold
    angular_panel(vbuf, (px, py, 218, 40), (12, 8, 20, 210), hborder, 6)
    mchar = me.charId % 8
    if me.charId == 8:
        tex = custom_tex_any(custom_params(gLocalSlot))
        if tex is None:
            tex = texChars[0] if gCust[0] == 0 else texChars[1]
        if tex is texDrawn:
            fr = custom_fr0(tex)
        else:
            mframes = ZEKE2_DOWN if gAnimMul == 2 else ZEKE_DOWN
            fr = mframes[0]
    else:
        zl = mchar in (0, 2, 4, 6, 7)
        if gAnimMul == 2:
            mframes = ZEKE2_DOWN if zl else JULIE2_DOWN
        else:
            mframes = ZEKE_DOWN if zl else JULIE_DOWN
        fr = mframes[0]
        tex = texChars[mchar]
    vbuf.blit(tex, (px + 6, py + 2), pygame.Rect(fr[0], fr[1], fr[2], fr[3]))
    pygame.draw.rect(vbuf, (60, 45, 80), (px + 4, py, fr[2] + 4, 40), 1)
    # HP bar (red, Dota-style segmented with dark trail)
    draw_text_sh(vbuf, px + 26, py + 1, 1, (255, 255, 255), tr("hud_hp"))
    for i in range(5):
        vbuf.fill((25, 12, 16), (px + 46 + i * 14, py + 2, 12, 8))
        if i < me.hp:
            vbuf.fill((255, 70, 60), (px + 46 + i * 14, py + 2, 12, 8))
            vbuf.fill((255, 150, 130), (px + 46 + i * 14, py + 2, 12, 3))
        pygame.draw.rect(vbuf, (60, 25, 30), (px + 46 + i * 14, py + 2, 12, 8), 1)
    # energy bar (blue, ammo)
    draw_text_sh(vbuf, px + 26, py + 12, 1, (255, 255, 255), tr("hud_en"))
    vbuf.fill((8, 12, 26), (px + 46, py + 13, 66, 8))
    ammo = max(0, int(me.ammo))
    frac = min(1.0, ammo / 60.0)
    if frac > 0:
        vbuf.fill((90, 160, 255), (px + 46, py + 13, int(66 * frac), 8))
        vbuf.fill((200, 230, 255), (px + 46, py + 13, int(66 * frac), 3))
    pygame.draw.rect(vbuf, (40, 60, 95), (px + 46, py + 13, 66, 8), 1)
    # stamina below EN; SHIFT sprint consumes it.
    draw_text_sh(vbuf, px + 26, py + 23, 1, (255, 255, 255), "ST")
    vbuf.fill((12, 20, 18), (px + 46, py + 24, 66, 5))
    stamina_w = int(66 * max(0.0, min(100.0, me.stamina)) / 100.0)
    if stamina_w:
        scol = (110, 235, 170) if me.stamina > 25 else (255, 140, 70)
        vbuf.fill(scol, (px + 46, py + 24, stamina_w, 5))
    pygame.draw.rect(vbuf, (50, 90, 75), (px + 46, py + 24, 66, 5), 1)
    # lives (skull-ish counter)
    draw_text_sh(vbuf, px + 120, py + 13, 1, (255, 220, 120), "x%d" % me.lives)
    # ammo readout + weapon name
    amax = ARMS[me.wpn][5]
    ac = (255, 230, 120) if ammo > 15 else ((255, 140, 60) if ammo > 5 else (255, 60, 60))
    draw_text_sh(vbuf, px + 146, py + 2, 1, (255, 200, 110), ARMS[me.wpn][0])
    draw_text_sh(vbuf, px + 146, py + 12, 1, ac, tr("hud_ammo"))
    draw_text_sh(vbuf, px + 182, py + 12, 2, ac, "%02d/%02d" % (ammo, amax))
    vbuf.blit(pygame.transform.scale(texWeapons[me.wpn], (30, 20)), (px + 144, py + 20))
    # weapon hotkeys 1-9 (owned inventory)
    inv = me.inv if getattr(me, "inv", None) else [0]
    for i, wpn in enumerate(inv[:9]):
        hsx = px + 4 + i * 11
        hsy = py + 31
        on = wpn == me.wpn
        vbuf.fill((30, 22, 44) if on else (16, 10, 26), (hsx, hsy, 10, 9))
        pygame.draw.rect(vbuf, (255, 230, 120) if on else (120, 100, 60), (hsx, hsy, 10, 9), 1)
        draw_text(vbuf, hsx + 1, hsy, 1, (255, 230, 120) if on else (150, 140, 160), str(i + 1))
    if gWpnMsgT > 0:
        draw_text_sh(vbuf, px + 4, py - 12, 1, (255, 230, 120), "ARMA: " + ARMS[me.wpn][0])
    if ammo <= 5 and int(gZomWalkT * 4) % 2 == 0:
        draw_text_sh(vbuf, px + 178, py + 26, 1, (255, 90, 90), tr("hud_low"))
    draw_minimap()
    if gMouseIn:
        win_w, win_h = gWin.get_size()
        mx = gMouseX * VIEW_W // max(1, win_w)
        my = gMouseY * VIEW_H // max(1, win_h)
        if 0 <= mx < VIEW_W and 0 <= my < VIEW_H:
            r = 7
            col = (255, 60, 60)
            pygame.draw.circle(vbuf, col, (mx, my), r, 1)
            pygame.draw.line(vbuf, col, (mx - r - 5, my), (mx - r + 2, my), 1)
            pygame.draw.line(vbuf, col, (mx + r - 2, my), (mx + r + 5, my), 1)
            pygame.draw.line(vbuf, col, (mx, my - r - 5), (mx, my - r + 2), 1)
            pygame.draw.line(vbuf, col, (mx, my + r - 2), (mx, my + r + 5), 1)
            vbuf.fill((255, 255, 255), (mx - 1, my - 1, 3, 3))


def draw_minimap():
    global _mini_cache, _mini_key, _mini_mask
    cx, cy = 64, 224
    R = 40
    world = 620.0
    sc = 2.0 * R / world
    x0 = gCamX + VIEW_W / 2.0 - world / 2.0
    y0 = gCamY + VIEW_H / 2.0 - world / 2.0
    x0 = max(0.0, min(MAP_W - world, x0))
    y0 = max(0.0, min(MAP_H - world, y0))
    # cache the scaled minimap: rebuild only when the view drifts ~8 world px
    key = (int(x0) >> 3, int(y0) >> 3, id(texLevel))
    if _mini_cache is None or _mini_key != key:
        _mini_cache = pygame.transform.scale(texLevel.subsurface(
            pygame.Rect(int(x0), int(y0), int(world), int(world))), (R * 2, R * 2))
        if _mini_mask is None:
            _mini_mask = pygame.Surface((R * 2, R * 2), pygame.SRCALPHA)
            pygame.draw.circle(_mini_mask, (255, 255, 255, 255), (R, R), R - 1)
        _mini_cache.blit(_mini_mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        _mini_key = key
    mini = _mini_cache
    neon = gLevelSel == 1
    mborder = (90, 220, 255) if neon else _gold
    pygame.draw.circle(vbuf, (12, 6, 18), (cx, cy), R + 6)
    vbuf.blit(mini, (cx - R, cy - R))
    pygame.draw.circle(vbuf, mborder, (cx, cy), R + 1, 2)
    # angular (octagon) frame, Dota-style
    pts = []
    for a in range(0, 360, 45):
        rad = math.radians(a + 22.5)
        pts.append((int(cx + math.cos(rad) * (R + 7)), int(cy + math.sin(rad) * (R + 7))))
    pygame.draw.polygon(vbuf, mborder, pts, 2)
    pts2 = []
    for a in range(0, 360, 45):
        rad = math.radians(a + 22.5)
        pts2.append((int(cx + math.cos(rad) * (R - 2)), int(cy + math.sin(rad) * (R - 2))))
    pygame.draw.polygon(vbuf, (90, 60, 20) if not neon else (40, 90, 110), pts2, 1)
    if gDoorOpen:
        dxw = (gDoorX - x0) * sc
        dyw = (gDoorY + 30 - y0) * sc
        if -R <= dxw <= R and -R <= dyw <= R:
            pulse = 6 + int(gZomWalkT * 8) % 3
            gx, gy = int(cx - R + dxw), int(cy - R + dyw)
            pygame.draw.circle(vbuf, (255, 235, 120), (gx, gy), pulse, 2)
            pygame.draw.circle(vbuf, (255, 255, 255), (gx, gy), 2)
    for p in range(gNumPlayers):
        P = gP[p]
        if not P.used or not P.alive:
            continue
        mx = int(cx + (P.x - x0) * sc)
        my = int(cy + (P.y - y0) * sc)
        if mx < cx - R + 2 or mx > cx + R - 2 or my < cy - R + 2 or my > cy + R - 2:
            continue
        if gMode == MODE_TEAMS:
            c = (255, 255, 255) if p == gLocalSlot else TEAMCOL[P.team]
        else:
            c = (255, 255, 255)
        vbuf.fill(c, (mx - 2, my - 2, 4, 4))
    for i in range(MAX_ZOMBIES):
        z = gZ[i]
        if not z.used or z.st != 1:
            continue
        mx = int(cx + (z.x - x0) * sc)
        my = int(cy + (z.y - y0) * sc)
        if mx < cx - R + 2 or mx > cx + R - 2 or my < cy - R + 2 or my > cy + R - 2:
            continue
        vbuf.fill((220, 60, 60), (mx - 1, my - 1, 2, 2))
    for v in range(gNumVictims):
        if gV[v].st != 0:
            continue
        mx = int(cx + (gV[v].x - x0) * sc)
        my = int(cy + (gV[v].y - y0) * sc)
        if mx < cx - R + 2 or mx > cx + R - 2 or my < cy - R + 2 or my > cy + R - 2:
            continue
        vbuf.fill((110, 235, 70), (mx - 1, my - 1, 2, 2))


# ---------------- PoE-style map chrome ----------------
_frame_static = None
_gold = (200, 160, 66)


def angular_panel(surf, rect, fill, border, cut=6, inner=True):
    x, y, w, h = rect
    pts = [(x + cut, y), (x + w - cut, y), (x + w, y + cut), (x + w, y + h - cut),
           (x + w - cut, y + h), (x + cut, y + h), (x, y + h - cut), (x, y + cut)]
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, border, pts, 1)
    if inner:
        pts2 = [(x + cut + 2, y + 2), (x + w - cut - 2, y + 2), (x + w - 2, y + cut + 2),
                (x + w - 2, y + h - cut - 2), (x + w - cut - 2, y + h - 2), (x + cut + 2, y + h - 2),
                (x + 2, y + h - cut - 2), (x + 2, y + cut + 2)]
        pygame.draw.polygon(surf, (70, 50, 90), pts2, 1)


def build_frame():
    global _frame_static
    s = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    g = _gold
    for i in range(36):
        a = int(75 * (1 - i / 36.0))
        s.fill((6, 3, 10, a), (0, i, VIEW_W, 1))
        s.fill((6, 3, 10, a), (0, VIEW_H - 1 - i, VIEW_W, 1))
        s.fill((6, 3, 10, a), (i, 0, 1, VIEW_H))
        s.fill((6, 3, 10, a), (VIEW_W - 1 - i, 0, 1, VIEW_H))
    pygame.draw.rect(s, g + (140,), (3, 3, VIEW_W - 6, VIEW_H - 6), 1)
    for (cx, cy) in [(4, 4), (VIEW_W - 4, 4), (4, VIEW_H - 4), (VIEW_W - 4, VIEW_H - 4)]:
        pygame.draw.line(s, g, (cx - 15, cy), (cx, cy), 3)
        pygame.draw.line(s, g, (cx, cy - 15), (cx, cy), 3)
        pygame.draw.line(s, g, (cx - 24, cy), (cx - 15, cy), 2)
        pygame.draw.line(s, g, (cx, cy - 24), (cx, cy - 15), 2)
        pygame.draw.circle(s, g, (cx, cy), 7, 2)
        for a in range(0, 360, 45):
            rad = math.radians(a)
            pygame.draw.line(s, g, (cx + math.cos(rad) * 4, cy + math.sin(rad) * 4),
                             (cx + math.cos(rad) * 8, cy + math.sin(rad) * 8), 2)
    _frame_static = s


def draw_map_frame():
    global _frame_static
    if _frame_static is None:
        build_frame()
    vbuf.blit(_frame_static, (0, 0))


def _lobby_sit_local(slot):
    global gMySlot, gLocalSlot
    old = gMySlot
    if slot == old or slot >= MAX_PLAYERS:
        return
    if gKinds[slot] == 0:
        gKinds[slot] = gKinds[old]
        gBotEnabled[slot] = 0
        gBotEnabled[old] = 0
        gKinds[old] = 0
        gLobReady[slot] = 0
        gLobReady[old] = 1
        gMySlot = slot
        gLocalSlot = slot


def _lobby_sit_net(slot):
    if gSock is None:
        return
    try:
        gSock.sendto(PACK_EDIT.pack(6, slot, 0, 0, 0, 1), gHostAddr)
    except OSError:
        pass


def _lobby_ready_net(slot, ready):
    if gSock is None:
        return
    try:
        gSock.sendto(PACK_EDIT.pack(6, slot, 0, 0, ready, 0), gHostAddr)
    except OSError:
        pass


def lobby_all_ready():
    return all(gLobReady[i] for i in range(MAX_PLAYERS))


def lobby_start_match():
    global gNetStarted, gSt, gLocalSlot
    if gNetStarted:
        return
    gNetStarted = 1
    if gSock is not None:
        host_broadcast_lobby()
    if IS_WEB:
        web_host_announce()
    gLocalSlot = gMySlot
    game_reset(MODE_TEAMS, 0)
    gSt = ST_PLAY


def _web_lobby_ingest():
    global gLobCount, gLobSel
    try:
        from js import window
        arr = window._lobbies
        n = int(arr.length)
        gLobCount = 0
        for i in range(min(n, MAX_LOBBIES)):
            o = arr[i]
            host = str(o.host) or ""
            if not host.startswith("web-"):
                continue
            if int(o.filled) <= 0 and not int(o.started):
                continue
            e = gLobList[gLobCount]
            e.name = str(o.name) or "?"
            e.host = str(o.host) or ""
            e.filled = int(o.filled)
            e.slots = int(o.slots)
            e.started = int(o.started)
            e.region = int(o.region)
            e.world = int(getattr(o, "world", 0) or 0)
            e.bots = int(getattr(o, "bots", 0) or 0)
            e.free = int(getattr(o, "free", 0) or 0)
            e.details = []
            details = getattr(o, "details", None)
            if details is not None:
                for d in details:
                    e.details.append({"slot": int(d.slot), "kind": int(d.kind),
                                      "bot": int(d.bot), "ready": int(d.ready),
                                      "team": int(d.team), "char": int(d.char)})
            e.addr = e.host
            e.port = NET_PORT
            e.ping = int(window._apiPing)
            e.lastSeen = gNetTime
            gLobCount += 1
        if gLobSel >= gLobCount:
            gLobSel = max(0, gLobCount - 1)
    except Exception:
        pass


def host_announce():
    try:
        import json as _json
        import urllib.request
        body = _json.dumps({
            "name": (gLobName.strip() or "LOBBY")[:15], "host": "zombicito.duckdns.org",
            "region": 1 if gServerMode else 0,
            "filled": sum(1 for k in gKinds if k), "slots": MAX_PLAYERS,
            "world": gLevelSel, "kinds": list(gKinds), "bots": list(gBotEnabled),
            "teams": list(gLobTeam), "chars": list(gLobChar), "ready": list(gLobReady),
            "started": gNetStarted}).encode()
        req = urllib.request.Request("http://zombicito.duckdns.org:7070/api/announce",
                                     data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=1).read()
    except Exception:
        pass


# ---------------- menus ----------------
MENU_ITEMS = ["LISTA DE LOBBIES", "CREAR LOBBY", "CONFIGURACION"]


# ---------------- StarCraft-style UI ----------------
_bg_grad = None


def render_bg_sc():
    global _bg_grad
    if _bg_grad is None or _bg_grad.get_size() != (VIEW_W, VIEW_H):
        s = pygame.Surface((VIEW_W, VIEW_H))
        stops = [(3, 2, 10), (8, 6, 22), (14, 10, 34), (10, 14, 30), (6, 10, 22)]
        n = len(stops)
        for yy in range(VIEW_H):
            t = yy / max(1, VIEW_H - 1)
            i = min(n - 2, int(t * (n - 1)))
            f = t * (n - 1) - i
            c1, c2 = stops[i], stops[i + 1]
            s.fill((int(c1[0] + (c2[0] - c1[0]) * f),
                    int(c1[1] + (c2[1] - c1[1]) * f),
                    int(c1[2] + (c2[2] - c1[2]) * f)), (0, yy, VIEW_W, 1))
        _bg_grad = s
    vbuf.blit(_bg_grad, (0, 0))
    t = gMenuT
    # drifting starfield (2 parallax layers) + twinkle
    for layer in (0, 1):
        n = 52 if layer == 0 else 30
        for i in range(n):
            h1 = (math.sin(i * 127.1 + 311.7 + layer * 13.0) * 43758.5453) % 1.0
            h2 = (math.sin(i * 269.5 + 183.3 + layer * 7.0) * 28001.8384) % 1.0
            spd = (14.0 + layer * 34.0) * (0.5 + h2 * 0.8)
            x = (h1 * (VIEW_W + 40) - t * spd) % (VIEW_W + 40.0) - 20.0
            y = h2 * (VIEW_H - 40) + (layer * 6)
            tw = 0.5 + 0.5 * math.sin(t * (1.8 + h1 * 2.0) + i * 1.7)
            b = int(70 + 130 * tw) if layer == 1 else int(40 + 70 * tw)
            sz = 2 if layer == 1 else 1
            vbuf.fill((b, b, min(255, int(b * 1.25))), (int(x), int(y), sz, sz))
            if layer == 1 and tw > 0.86:
                vbuf.fill((b, b, min(255, int(b * 1.3))), (int(x), int(y) + 1, sz, sz))
    # shooting stars
    for i in range(3):
        ph = (t * 0.13 + i * 0.37) % 1.0
        if ph < 0.09:
            fx = int(VIEW_W * (0.15 + 0.7 * ((ph * 11) % 1.0)))
            fy = int(40 + ph * 120)
            ln = int(26 * (1.0 - ph / 0.09))
            vbuf.fill((200, 210, 255), (fx, fy, ln, 1))
            vbuf.fill((150, 160, 220), (fx - 3, fy - 1, 3, 2))
    # bottom fog band
    for i in range(34):
        a = int(60 * (1 - i / 34.0))
        vbuf.fill((30, 20, 60), (0, VIEW_H - 34 + i, VIEW_W, 1))
    # drifting fog wisps
    for i in range(4):
        fx = (t * (8.0 + i * 5.0) + i * 173) % (VIEW_W + 220.0) - 110.0
        fw = 90 + i * 30
        for yy in range(10):
            vbuf.fill((int(38 + 12 * math.sin(t * 1.3 + i)), int(26 + 8 * math.sin(t + i)),
                       int(66 + 16 * math.sin(t * 0.7 + i * 2))),
                      (int(fx + math.sin(t * 2 + i) * 18), VIEW_H - 12 - yy, int(fw * (1 - yy / 14.0)), 1))


def sc_panel(surf, rect, fill=(16, 10, 30), border=(200, 160, 66), cut=8, dark=True):
    x, y, w, h = rect
    pts = [(x + cut, y), (x + w - cut, y), (x + w, y + cut), (x + w, y + h - cut),
           (x + w - cut, y + h), (x + cut, y + h), (x, y + h - cut), (x, y + cut)]
    pygame.draw.polygon(surf, fill, pts)
    pygame.draw.polygon(surf, border, pts, 2)
    if dark:
        pts2 = [(x + cut + 3, y + 3), (x + w - cut - 3, y + 3), (x + w - 3, y + cut + 3),
                (x + w - 3, y + h - cut - 3), (x + w - cut - 3, y + h - 3), (x + cut + 3, y + h - 3),
                (x + 3, y + h - cut - 3), (x + 3, y + cut + 3)]
        pygame.draw.polygon(surf, (48, 30, 72), pts2, 1)
    # animated corner brackets (SC targeting feel)
    m = int(gMenuT * 3) % 8
    bl = 14 if m >= 4 else 10
    for (bx, by, dx, dy) in [(x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)]:
        pygame.draw.line(surf, border, (bx, by), (bx + dx * bl, by), 2)
        pygame.draw.line(surf, border, (bx, by), (bx, by + dy * bl), 2)
    # sliding energy dot along top edge
    ex = x + 10 + int((gMenuT * 46) % max(10, w - 20))
    pygame.draw.line(surf, border, (ex, y + 1), (ex + 5, y + 1))
    pygame.draw.line(surf, (255, 235, 150), (ex, y + 2), (ex + 2, y + 2))


def sc_title(cx, y, text, color, sc=3, glow=True):
    if glow:
        for (dx, dy) in ((-2, 0), (2, 0), (0, -2), (0, 2), (-1, 1), (1, 1)):
            draw_text_cs(vbuf, cx + dx, y + dy, sc, (20, 60, 30) if color[1] > 150 else (60, 20, 30), text)
    draw_text_cs(vbuf, cx + 2, y + 2, sc, (4, 10, 6), text)
    draw_text_cs(vbuf, cx, y, sc, color, text)
    w = text_w(sc, text)
    a = int(gMenuT * 6) % (w + 24) - 12
    for k in range(0, w, 14):
        bx = cx - w // 2 + ((k + a) % (w + 24)) - 12
        if 0 <= bx < VIEW_W:
            vbuf.fill((200, 160, 66), (bx, y + sc * 8 + 2, 8, 2))
            vbuf.fill((120, 90, 40), (bx, y + sc * 8 + 4, 8, 1))


def sc_row(cx, y, w, label, idx, sel, stagger=0.16, sc=2, scolor=(255, 230, 120), color=(205, 198, 220), side=True):
    k = min(1.0, max(0.0, gMenuT * 2.4 - idx * stagger))
    ease = 1.0 - (1.0 - k) ** 3
    off = int((1.0 - ease) * 52.0)
    col = scolor if sel else color
    draw_text_cs(vbuf, cx + off, y + 1, sc, (10, 14, 10), label)
    draw_text_cs(vbuf, cx + off, y, sc, col, label)
    if sel:
        uw = max(8, int(w * ease))
        vbuf.fill((200, 160, 66), (cx - uw // 2, y + sc * 7 + 1, uw, 2))
        vbuf.fill((255, 240, 170), (cx - uw // 2, y + sc * 7 + 1, uw // 2, 1))
        if side:
            a = int(gMenuT * 8) % 3
            draw_text_c(vbuf, cx - w // 2 - 14 - a, y + 1, 1, (200, 160, 66), ">")
            draw_text_c(vbuf, cx + w // 2 + 14 - a, y + 1, 1, (200, 160, 66), "<")


def marquee(cx, y, txt, color, sc=1, speed=46.0):
    w = text_w(sc, txt)
    total = VIEW_W + w
    x = (VIEW_W - cx) - int((gMenuT * speed) % total) + w / 2.0
    draw_text(vbuf, int(cx + x - w), y, sc, color, txt)
    draw_text(vbuf, int(cx + x - w + total), y, sc, color, txt)


def menu_cursor(cx, y, label, sc=2):
    f = int(gZomWalkT * (6.0 * gAnimMul)) % (4 * gAnimMul)
    fr = (ZOM2_RIGHT if texZombie2 is not None else ZOM_RIGHT)[f]
    x, y0, w, h = fr
    dst = (int(cx - text_w(sc, label) / 2.0 - 34), y - 10, w, h)
    vbuf.blit(texZombie2 if texZombie2 is not None else texZombie, (dst[0], dst[1]), pygame.Rect(x, y0, w, h))


def render_menu():
    render_bg_sc()
    # Haunted house silhouette anchors the menu background without adding
    # another animated foreground layer.
    hx, hy = 18, 112
    pygame.draw.polygon(vbuf, (12, 8, 24), [(hx - 4, hy + 28), (hx + 30, hy - 4),
                                            (hx + 64, hy + 28), (hx + 58, hy + 28),
                                            (hx + 58, hy + 108), (hx, hy + 108), (hx, hy + 28)])
    vbuf.fill((20, 12, 34), (hx + 8, hy + 30, 42, 76))
    pygame.draw.rect(vbuf, (90, 62, 116), (hx + 8, hy + 30, 42, 76), 1)
    vbuf.fill((7, 5, 14), (hx + 24, hy + 72, 12, 34))
    for wx in (hx + 13, hx + 36):
        vbuf.fill((214, 180, 90), (wx, hy + 48, 9, 12))
        pygame.draw.line(vbuf, (20, 14, 30), (wx + 4, hy + 48), (wx + 4, hy + 60), 1)
    pygame.draw.line(vbuf, (90, 62, 116), (hx + 30, hy - 4), (hx + 30, hy - 18), 2)
    pygame.draw.circle(vbuf, (90, 62, 116), (hx + 30, hy - 20), 3, 1)
    # StarCraft-style title (world tint)
    sc_title(VIEW_W // 2, 16, "ZOMBI-CITO", WORLD_TINT[gLevelSel % WORLD_COUNT], 3)
    sc_title(VIEW_W // 2, 44, tr("title_sub"), (235, 70, 85), 1)
    draw_text_c(vbuf, VIEW_W // 2, 72, 1, (230, 210, 255),
                tr("menu_sub_web") if IS_WEB else tr("menu_sub"))
    # main options panel
    sc_panel(vbuf, (VIEW_W // 2 - 160, 76, 320, 190), (14, 8, 26), _gold, 10)
    labels = [tr("menu_list"), tr("menu_create"), tr("menu_worlds"), tr("menu_weapons"),
              tr("menu_characters"), tr("menu_options"), tr("menu_design"), tr("menu_profile")]
    for i in range(8):
        y = 82 + i * 21
        sc_row(VIEW_W // 2, y, 220, labels[i], i, i == gMenuIdx, 0.14, 2)
    # your custom character preview (right side)
    cp = tuple(gCust)
    zlike = cp[0] in (0, 2, 4, 6)
    ptex = custom_tex_any(cp)
    if ptex is None:
        ptex = (texChars[cp[0]] if 0 <= cp[0] < len(texChars) and texChars[cp[0]]
                else (texZeke if zlike else texJulie))
    if ptex is texDrawn:
        pfr = custom_fr0(ptex)
    else:
        pfr = ((ZEKE2_DOWN if texZeke2 is not None else ZEKE_DOWN) if zlike
               else (JULIE2_DOWN if texJulie2 is not None else JULIE_DOWN))[0]
    ps = 3
    sc_panel(vbuf, (VIEW_W - 82, 88, 70, 146), (14, 8, 26), _gold, 8)
    draw_text_c(vbuf, VIEW_W - 47, 92, 1, (200, 160, 66), custom_display_name())
    vbuf.blit(pygame.transform.scale(ptex.subsurface(pygame.Rect(*pfr)),
                                     (pfr[2] * ps, pfr[3] * ps)),
              (VIEW_W - 47 - pfr[2] * ps // 2, 102))
    draw_text_c(vbuf, VIEW_W - 47, 102 + pfr[3] * ps + 6, 1, (255, 230, 120), custom_display_name())
    vbuf.fill((14, 8, 26), (390, 246, 82, 16))
    pygame.draw.rect(vbuf, (200, 160, 66), (390, 246, 82, 16), 1)
    draw_text_c(vbuf, 431, 248, 1, (255, 230, 120), "SALIR")


def account_logout():
    global gRunning, gSt
    if IS_WEB:
        try:
            from js import window
            window._logout()
        except Exception:
            gSt = ST_MENU
    else:
        gRunning = False


def render_lobby():
    render_bg_sc()
    g = (200, 160, 66)
    if gLobStage == 3:
        # lobby list (improved rows + editor-style bottom buttons)
        sc_panel(vbuf, (14, 26, VIEW_W - 28, VIEW_H - 82), (16, 9, 24), g, 10)
        draw_text_c(vbuf, VIEW_W // 2, 32, 1, g, tr("lobby_list_title"))
        draw_text(vbuf, 22, 44, 1, (170, 160, 185), "SALAS DISPONIBLES")
        draw_text(vbuf, 276, 44, 1, (170, 160, 185), "DETALLE DE LA SALA")
        if gLobCount == 0:
            dots = "." * (1 + int(gMenuT * 2.5) % 3)
            draw_text_c(vbuf, VIEW_W // 2, 110, 1, (230, 210, 255), tr("lobby_scan") + dots)
            draw_text_c(vbuf, VIEW_W // 2, 126, 1, (150, 140, 160), tr("lobby_none"))
        else:
            order = sorted(range(gLobCount), key=lambda i: (gLobList[i].started, -gLobList[i].filled))
            for pos in range(min(gLobCount, 6)):
                e = gLobList[order[pos]]
                sy = 58 + pos * 26
                sel = pos == gLobSel
                if sel:
                    vbuf.fill((30, 18, 44), (20, sy - 3, 230, 22))
                    pygame.draw.rect(vbuf, g, (20, sy - 3, 230, 22), 1)
                name = e.name[:17].ljust(17)
                mc = (255, 255, 120) if sel else ((110, 110, 110) if e.started else (220, 215, 230))
                draw_text(vbuf, 22, sy, 1, mc, name)
                rc = (120, 200, 255) if e.region == 1 else (140, 230, 140)
                draw_text(vbuf, 22, sy + 10, 1, rc, "ONLINE" if e.region == 1 else "LAN")
                draw_text(vbuf, 140, sy + 10, 1, mc, "%d/%d" % (e.filled, e.slots or 12))
                if sel:
                    menu_cursor(14, sy + 4, "x", 1)
            draw_text(vbuf, 22, 214, 1, (170, 160, 185), "%d SALA%s" % (gLobCount, "" if gLobCount == 1 else "S"))
        if gLobCount > 0:
            order = sorted(range(gLobCount), key=lambda i: (gLobList[i].started, -gLobList[i].filled))
            selected_entry = gLobList[order[min(gLobSel, len(order) - 1)]]
            sc_panel(vbuf, (264, 50, 204, 166), (12, 8, 20), g, 6)
            draw_text(vbuf, 274, 58, 1, (255, 230, 120), selected_entry.name[:22])
            world_name = WORLD_NAMES[selected_entry.world % WORLD_COUNT]
            draw_text(vbuf, 274, 70, 1, WORLD_TINT[selected_entry.world % WORLD_COUNT], world_name[:22])
            draw_text(vbuf, 274, 82, 1, (205, 198, 220),
                      "%d/%d JUG  %d BOT  %d LIBRES" %
                      (selected_entry.filled, selected_entry.slots or 12,
                       selected_entry.bots, selected_entry.free))
            draw_text(vbuf, 274, 94, 1, (110, 235, 110) if not selected_entry.started else (235, 70, 70),
                      tr("lobby_waiting") if not selected_entry.started else tr("lobby_playing"))
            details = selected_entry.details
            for di in range(min(len(details), 10)):
                d = details[di]
                if d["kind"] == 0 and d["bot"]:
                    label = "BOT"
                elif d["kind"] == 0:
                    label = "LIBRE"
                elif d["kind"] == 1:
                    label = "HOST"
                else:
                    label = "PC %d" % d["kind"]
                ready_label = "OK" if d["ready"] else "--"
                draw_text(vbuf, 274, 106 + di * 10, 1,
                          TEAMCOL[d["team"] % len(TEAMCOL)],
                          "S%02d %-5s %s" % (d["slot"] + 1, label, ready_label))
        for b, cx, label in ((0, 60, tr("ed_back")), (1, 240, tr("gal_refresh")), (2, 420, tr("lobby_join"))):
            vbuf.fill((14, 8, 26), (cx - 42, 238, 84, 18))
            pygame.draw.rect(vbuf, (200, 160, 66), (cx - 42, 238, 84, 18), 1)
            draw_text_c(vbuf, cx, 240, 1, (255, 230, 120), label)
    elif gLobStage == 4:
        # Compact left controls and a larger right-side map preview.
        draw_text(vbuf, 22, 22, 1, WORLD_TINT[gLevelSel % WORLD_COUNT], tr("create_title"))
        draw_text(vbuf, 22, 48, 1, (200, 190, 210), tr("create_name"))
        name_w = max(112, min(220, text_w(1, gLobName) + 18))
        sc_panel(vbuf, (22, 60, name_w, 22), (16, 9, 24), g, 5)
        draw_text(vbuf, 30, 67, 1, (255, 255, 120), gLobName + "_")
        draw_text(vbuf, 22, 98, 1, (200, 190, 210), "MUNDO")
        vbuf.fill((30, 18, 44), (22, 112, 22, 18))
        pygame.draw.rect(vbuf, (200, 160, 66), (22, 112, 22, 18), 1)
        draw_text_c(vbuf, 33, 114, 1, (255, 230, 120), "<")
        draw_text(vbuf, 52, 117, 1, WORLD_TINT[gLevelSel % WORLD_COUNT], WORLD_NAMES[gLevelSel % WORLD_COUNT][:19])
        vbuf.fill((30, 18, 44), (208, 112, 22, 18))
        pygame.draw.rect(vbuf, (200, 160, 66), (208, 112, 22, 18), 1)
        draw_text_c(vbuf, 219, 114, 1, (255, 230, 120), ">")
        draw_text(vbuf, 22, 145, 1, (230, 210, 255), tr("create_teams"))
        draw_text(vbuf, 22, 158, 1, (150, 140, 160), tr("create_bots"))
        # Six direct stage buttons and a preview of the selected SNES map.
        sc_panel(vbuf, (252, 34, 216, 142), (16, 9, 24), g, 6)
        for i in range(WORLD_COUNT):
            col, row = i % 2, i // 2
            rx, ry = 260 + col * 104, 42 + row * 23
            selected = i == gLevelSel
            vbuf.fill((40, 25, 55) if selected else (14, 8, 26), (rx, ry, 96, 18))
            pygame.draw.rect(vbuf, WORLD_TINT[i] if selected else (100, 75, 110),
                             (rx, ry, 96, 18), 1)
            draw_text(vbuf, rx + 5, ry + 4, 1,
                      (255, 230, 120) if selected else (205, 198, 220),
                      "%d. %s" % (i + 1, WORLD_NAMES[i][:12]))
        ptex = world_texture()[0]
        pw, ph = ptex.get_size()
        psc = min(196.0 / pw, 48.0 / ph)
        tw, th = max(1, int(pw * psc)), max(1, int(ph * psc))
        vbuf.blit(pygame.transform.scale(ptex, (tw, th)),
                  (262 + (196 - tw) // 2, 119 + (48 - th) // 2))
        # editor-style buttons
        for cx, label in ((62, tr("ed_back")), (160, tr("create_title"))):
            vbuf.fill((14, 8, 26), (cx - 42, 202, 84, 18))
            pygame.draw.rect(vbuf, (200, 160, 66), (cx - 42, 202, 84, 18), 1)
            draw_text_c(vbuf, cx, 204, 1, (255, 230, 120), label)
    else:
        # lobby: 4 teams x 3 slots + chat window
        filled = sum(1 for k in gKinds if k)
        draw_text_cs(vbuf, VIEW_W // 2, 7, 1, g, gLobName)
        draw_text(vbuf, 10, 7, 1, (150, 200, 255), "%d/12" % filled)
        lv = WORLD_NAMES[gLevelSel % WORLD_COUNT]
        draw_text(vbuf, VIEW_W - 14 - text_w(1, lv), 7, 1, WORLD_TINT[gLevelSel % WORLD_COUNT], lv)
        sc_panel(vbuf, (4, 18, VIEW_W - 8, 124), (14, 8, 22), g, 6)
        bw, bh = 114, 118
        bx0 = 6
        for t in range(4):
            bx = bx0 + t * (bw + 2)
            tc = TEAMCOL[t]
            pygame.draw.rect(vbuf, tc, (bx, 20, bw, bh), 1)
            draw_text_c(vbuf, bx + bw // 2, 21, 1, tc, TEAMNAME[t])
            for m in range(3):
                slot = t * 3 + m
                sy = 28 + m * 36
                sel = slot == gLobSelRow
                mine = slot == gMySlot
                if gKinds[slot] == 1:
                    who = tr("you")
                elif gKinds[slot] >= 2:
                    who = tr("you") if mine else "PC %d" % gKinds[slot]
                else:
                    who = tr("cpu") if gBotEnabled[slot] else ""
                rowc = (255, 255, 120) if sel else ((230, 255, 190) if mine else
                       ((220, 215, 230) if gKinds[slot] else (130, 125, 150)))
                if sel:
                    vbuf.fill((30, 18, 44), (bx + 2, sy - 5, bw - 4, 32))
                    pygame.draw.rect(vbuf, g, (bx + 2, sy - 5, bw - 4, 32), 1)
                bot_active = gKinds[slot] == 0 and bool(gBotEnabled[slot])
                charl = gLobChar[slot] % 9
                if gKinds[slot] != 0 or bot_active:
                    if charl == 8:
                        cp = gCustNet[slot] if gCustNet[slot] else tuple(gCust)
                        stex = custom_tex_any(cp) if slot == gMySlot else custom_tex(cp)
                        z_like = cp[0] in (0, 2, 4, 6)
                        if stex is None:
                            stex = (texChars[cp[0]] if 0 <= cp[0] < len(texChars)
                                    and texChars[cp[0]] else (texZeke if z_like else texJulie))
                        if stex is texDrawn:
                            sfr = custom_fr0(stex)
                        elif texZeke2 is not None:
                            sfr = (ZEKE2_DOWN if z_like else JULIE2_DOWN)[0]
                        else:
                            sfr = (ZEKE_DOWN if z_like else JULIE_DOWN)[0]
                        sdx = bx + 4
                    else:
                        is_z = charl in (0, 2, 4, 6, 7)
                        if texZeke2 is not None:
                            sfr = (ZEKE2_DOWN if is_z else JULIE2_DOWN)[0]
                            base_w = (ZEKE_DOWN if is_z else JULIE_DOWN)[0][2]
                            sdx = bx + 4 - (sfr[2] - base_w) // 2
                        else:
                            sfr = (ZEKE_DOWN if is_z else JULIE_DOWN)[0]
                            sdx = bx + 4
                        stex = texChars[charl]
                    vbuf.blit(stex, (sdx, sy - 4), pygame.Rect(sfr[0], sfr[1], sfr[2], sfr[3]))
                draw_text(vbuf, bx + 26, sy + 1, 1, rowc, who)
                cc = (255, 255, 255) if mine else (150, 145, 170)
                if gKinds[slot] != 0 or bot_active:
                    draw_text(vbuf, bx + 26, sy + 10, 1, cc, char_name(charl, slot))
                rdy = gLobReady[slot] if slot < MAX_PLAYERS else 1
                if gKinds[slot] == 0 and not bot_active:
                    draw_text(vbuf, bx + 26, sy + 19, 1, (130, 125, 150), "LIBRE")
                elif gKinds[slot] == 0:
                    draw_text(vbuf, bx + 26, sy + 19, 1, (110, 235, 110), "BOT ON")
                elif rdy:
                    draw_text(vbuf, bx + 26, sy + 19, 1, (110, 235, 70), tr("ready"))
                else:
                    draw_text(vbuf, bx + 26, sy + 19, 1, (255, 200, 60), tr("not_ready"))
                if mine:
                    vbuf.fill((30, 18, 44), (bx + 72, sy + 13, 38, 13))
                    pygame.draw.rect(vbuf, (200, 160, 66), (bx + 72, sy + 13, 38, 13), 1)
                    draw_text_c(vbuf, bx + 91, sy + 15, 1, (255, 230, 120), "OK" if rdy else "LISTO")
                if mine and rdy:
                    vbuf.fill((110, 235, 70), (bx + 96, sy + 4, 12, 10))
                    vbuf.fill((40, 90, 40), (bx + 96, sy + 8, 12, 2))
        # chat window
        sc_panel(vbuf, (4, 146, VIEW_W - 8, 92), (16, 9, 24), g, 8)
        draw_text(vbuf, 10, 148, 1, g, tr("chat_title"))
        chk = tr("chat_hint")
        draw_text(vbuf, VIEW_W - 12 - text_w(1, chk), 148, 1, (150, 140, 160), chk)
        for k, (slot, txt) in enumerate(gChatLines[-6:]):
            y = 156 + k * 12
            if slot >= 90:
                col = (170, 160, 185)
            elif slot == gMySlot:
                col = (255, 230, 120)
            elif 0 <= slot < MAX_PLAYERS:
                col = TEAMCOL[gLobTeam[slot] % 4]
            else:
                col = (170, 160, 185)
            nm = chat_name(slot) + ":"
            draw_text(vbuf, 10, y, 1, col, nm)
            draw_text(vbuf, 12 + text_w(1, nm), y, 1, (215, 210, 230), txt[:42])
        # chat input line
        pygame.draw.rect(vbuf, (30, 18, 44), (8, 228, VIEW_W - 16, 10))
        pygame.draw.rect(vbuf, (90, 70, 40), (8, 228, VIEW_W - 16, 10), 1)
        if gChatTyping:
            cur = "_" if int(gMenuT * 2) % 2 == 0 else " "
            draw_text(vbuf, 10, 229, 1, (255, 255, 120), ">" + gChatInput + cur)
        else:
            draw_text(vbuf, 10, 229, 1, (150, 140, 160), "> " + tr("chat_hint"))
        # status lines
        ready_n = sum(1 for i in range(MAX_PLAYERS) if gLobReady[i])
        if gLobStage == 1:
            draw_text_c(vbuf, VIEW_W // 2, VIEW_H - 38, 1, (255, 255, 120),
                        tr("lobby_ready_n") % ready_n)
            try:
                ip = socket.gethostbyname(socket.gethostname())
                draw_text_c(vbuf, VIEW_W // 2, VIEW_H - 26, 1, (230, 210, 255),
                            tr("lobby_ip") % (ip, NET_PORT))
            except OSError:
                draw_text_c(vbuf, VIEW_W // 2, VIEW_H - 26, 1, (230, 210, 255),
                            tr("lobby_pc") % socket.gethostname())
        else:
            if gLobbyGot:
                draw_text_c(vbuf, VIEW_W // 2, VIEW_H - 26, 1, (255, 255, 120),
                            tr("lobby_ready_n") % ready_n)
            else:
                draw_text_c(vbuf, VIEW_W // 2, VIEW_H - 26, 1, (255, 255, 120), tr("lobby_connect"))
        # Back, remove-all-bots and creator-only launch controls.
        buttons = [(52, tr("ed_back"))]
        if gLobStage == 1 and gMySlot == 0:
            buttons.append((236, "SIN BOTS"))
            buttons.append((420, "LANZAR"))
        for cx, label in buttons:
            fill = (30, 18, 44)
            vbuf.fill(fill, (cx - 42, 254, 84, 14))
            pygame.draw.rect(vbuf, (200, 160, 66), (cx - 42, 254, 84, 14), 1)
            draw_text_c(vbuf, cx, 255, 1, (255, 230, 120), label[:12])


def render_options():
    render_bg_sc()
    sc_title(VIEW_W // 2, 24, "OPTIONS", (200, 160, 66), 3)
    vbuf.fill((14, 8, 26), (8, 8, 80, 18))
    pygame.draw.rect(vbuf, (200, 160, 66), (8, 8, 80, 18), 1)
    draw_text_c(vbuf, 48, 10, 1, (255, 230, 120), tr("opts_back"))
    sc_panel(vbuf, (VIEW_W // 2 - 160, 60, 320, 178), (14, 8, 26), _gold, 10)
    rows = [tr("opts_filter") % ("SMOOTH" if gSmooth else "CRISP"),
            tr("opts_vol") % gVolume,
            tr("opts_lang") % ("ES" if gLang == 0 else "EN"),
            tr("opts_fps") % ("ON" if gShowFps else "OFF"),
            tr("opts_back")]
    h = hover_row(68, 26, 5, 130, 350)
    for i in range(5):
        sc_row(VIEW_W // 2, 68 + i * 26, 240, rows[i], i, i == gOptIdx or i == h, 0.12, 2, side=False)
        if i == 1:
            # Volume controls stay inside the options panel.
            pygame.draw.polygon(vbuf, (200, 160, 66), [(94, 94), (106, 86), (106, 102)])
            pygame.draw.polygon(vbuf, (200, 160, 66), [(386, 94), (374, 86), (374, 102)])
            # volume bars
            for seg in range(8):
                on = gVolume >= (seg + 1) * 12
                vbuf.fill((90, 60, 20), (VIEW_W // 2 - 108 + seg * 8, 82, 6, 5))
                if on:
                    vbuf.fill((255, 210, 110), (VIEW_W // 2 - 108 + seg * 8, 82, 6, 5))
                    vbuf.fill((255, 240, 190), (VIEW_W // 2 - 108 + seg * 8, 82, 6, 2))


_world_preview_cache = None
_world_preview_key = None


def world_editor_preview():
    global _world_preview_cache, _world_preview_key
    key = (gWorldEditSel, gWorldExpand[gWorldEditSel])
    if _world_preview_cache is not None and _world_preview_key == key:
        return _world_preview_cache
    base = texWorlds[gWorldEditSel % len(texWorlds)] if texWorlds else texLevel1
    extra = gWorldExpand[gWorldEditSel] * 128
    if extra:
        preview = pygame.Surface((base.get_width() + extra * 2, base.get_height()), pygame.SRCALPHA)
        preview.fill((8, 5, 16, 255))
        preview.blit(base, (extra, 0))
    else:
        preview = base
    _world_preview_cache = preview
    _world_preview_key = key
    return preview


def render_worlds():
    render_bg_sc()
    sc_title(VIEW_W // 2, 22, tr("menu_worlds"), (200, 160, 66), 3)
    sc_panel(vbuf, (12, 44, 132, 174), (14, 8, 26), _gold, 8)
    for i in range(WORLD_COUNT):
        y = 52 + i * 25
        selected = i == gWorldEditSel
        if selected:
            vbuf.fill((40, 25, 55), (20, y - 2, 116, 20))
            pygame.draw.rect(vbuf, WORLD_TINT[i], (20, y - 2, 116, 20), 1)
        draw_text(vbuf, 26, y + 3, 1,
                  (255, 230, 120) if selected else (205, 198, 220),
                  "%d. %s" % (i + 1, WORLD_NAMES[i][:15]))
    sc_panel(vbuf, (156, 44, 312, 174), (14, 8, 26), WORLD_TINT[gWorldEditSel], 8)
    preview = world_editor_preview()
    pw, ph = preview.get_size()
    scale = min(292.0 / pw, 132.0 / ph)
    sw, sh = max(1, int(pw * scale)), max(1, int(ph * scale))
    vbuf.blit(pygame.transform.scale(preview, (sw, sh)),
              (166 + (292 - sw) // 2, 50 + (132 - sh) // 2))
    draw_text(vbuf, 166, 188, 1, (180, 170, 195), "SELECCIONA UN MUNDO PARA EDITARLO")
    for cx, label in ((330, "EDITAR"), (430, tr("ed_back"))):
        vbuf.fill((14, 8, 26), (cx - 46, 230, 92, 16))
        pygame.draw.rect(vbuf, (200, 160, 66), (cx - 46, 230, 92, 16), 1)
        draw_text_c(vbuf, cx, 232, 1, (255, 230, 120), label)


def worlds_click(mx, my):
    global gWorldEditSel, _world_preview_cache, _world_preview_key, gSt
    for i in range(WORLD_COUNT):
        y = 52 + i * 25
        if 20 <= mx <= 136 and y - 2 <= my <= y + 18:
            gWorldEditSel = i
            _world_preview_cache = None
            play_snd(SND_MENU)
            return
    if 284 <= mx <= 376 and 230 <= my <= 248:
        world_editor_open()
        play_snd(SND_CONFIRM)
    elif 384 <= mx <= 476 and 230 <= my <= 248:
        gSt = ST_MENU
        play_snd(SND_MENU)


def world_editor_open():
    global gWorldEditorBase, gWorldEditorUpper, gWorldEditLayer, gWorldEditorDirty, gSt
    gWorldEditorBase = texWorlds[gWorldEditSel].copy()
    gWorldEditorUpper = upperWorlds[gWorldEditSel].copy() if upperWorlds else pygame.Surface((MAP_W, MAP_H), pygame.SRCALPHA)
    gWorldEditLayer = "upper"
    gWorldEditorDirty = False
    gSt = ST_WORLD_EDITOR


def render_world_editor():
    render_bg_sc()
    sc_title(VIEW_W // 2, 18, "EDITOR DE MUNDO", WORLD_TINT[gWorldEditSel], 2)
    draw_text(vbuf, 12, 34, 1, (255, 230, 120), "%d. %s" % (gWorldEditSel + 1, WORLD_NAMES[gWorldEditSel]))
    sc_panel(vbuf, (10, 48, 460, 150), (14, 8, 26), _gold, 8)
    base = gWorldEditorBase or texWorlds[gWorldEditSel]
    upper = gWorldEditorUpper
    scale = min(444.0 / base.get_width(), 134.0 / base.get_height())
    sw, sh = max(1, int(base.get_width() * scale)), max(1, int(base.get_height() * scale))
    px, py = 18 + (444 - sw) // 2, 56 + (134 - sh) // 2
    vbuf.blit(pygame.transform.scale(base, (sw, sh)), (px, py))
    if upper is not None:
        vbuf.blit(pygame.transform.scale(upper, (sw, sh)), (px, py))
    draw_text(vbuf, 12, 204, 1, (205, 198, 220),
              "CAPA: " + ("SUPERIOR" if gWorldEditLayer == "upper" else "FONDO"))
    for cx, label in ((62, "FONDO"), (160, "SUPERIOR"), (270, "GUARDAR"), (420, tr("ed_back"))):
        vbuf.fill((14, 8, 26), (cx - 46, 222, 92, 18))
        pygame.draw.rect(vbuf, WORLD_TINT[gWorldEditSel] if label == ("SUPERIOR" if gWorldEditLayer == "upper" else "FONDO") else (200, 160, 66),
                         (cx - 46, 222, 92, 18), 1)
        draw_text_c(vbuf, cx, 225, 1, (255, 230, 120), label)


def world_editor_click(mx, my):
    global gWorldEditLayer, gWorldEditorDirty, gSt, texWorlds, upperWorlds
    if 16 <= mx <= 464 and 54 <= my <= 190:
        base = gWorldEditorBase or texWorlds[gWorldEditSel]
        scale = min(444.0 / base.get_width(), 134.0 / base.get_height())
        sw, sh = max(1, int(base.get_width() * scale)), max(1, int(base.get_height() * scale))
        px, py = 18 + (444 - sw) // 2, 56 + (134 - sh) // 2
        if px <= mx < px + sw and py <= my < py + sh:
            wx = int((mx - px) / scale)
            wy = int((my - py) / scale)
            target = gWorldEditorUpper if gWorldEditLayer == "upper" else gWorldEditorBase
            if target is not None:
                color = (255, 210, 110, 180) if gWorldEditLayer == "upper" else (120, 90, 50)
                pygame.draw.rect(target, color, (wx - 12, wy - 12, 24, 24), 2)
                gWorldEditorDirty = True
            return
    if 16 <= mx <= 108 and 222 <= my <= 244:
        gWorldEditLayer = "base"
    elif 114 <= mx <= 206 and 222 <= my <= 244:
        gWorldEditLayer = "upper"
    elif 224 <= mx <= 316 and 222 <= my <= 244:
        if gWorldEditorBase is not None:
            texWorlds[gWorldEditSel] = gWorldEditorBase
        if gWorldEditorUpper is not None and upperWorlds:
            upperWorlds[gWorldEditSel] = gWorldEditorUpper
        gWorldEditorDirty = False
    elif 374 <= mx <= 466 and 222 <= my <= 244:
        gSt = ST_WORLDS


def mouse_vbuf():
    if not gMouseIn:
        return (-9999, -9999)
    w, h = gWin.get_size()
    return gMouseX * VIEW_W // max(1, w), gMouseY * VIEW_H // max(1, h)


def mouse_event_vbuf(pos):
    """Convert the coordinates carried by the actual mouse event."""
    w, h = gWin.get_size()
    return pos[0] * VIEW_W // max(1, w), pos[1] * VIEW_H // max(1, h)


def hover_row(y0, span, n, x0=-9999, x1=9999, pad=9):
    mx, my = mouse_vbuf()
    if not (x0 <= mx <= x1):
        return -1
    for i in range(n):
        if abs(my - (y0 + i * span)) <= pad:
            return i
    return -1


def menu_enter():
    global gSt, gLobStage, gLobCount, gLobSel, gLevelSel
    play_snd(SND_CONFIRM)
    if gMenuIdx == 0:
        gSt = ST_LOBBY
        gLobStage = 3
        gLobCount = 0
        gLobSel = 0
        if not IS_WEB:
            net_browse_open()
    elif gMenuIdx == 1:
        gSt = ST_LOBBY
        gLobStage = 4
        gLevelSel = WORLD_COUNT - 1
    elif gMenuIdx == 2:
        gSt = ST_WORLDS
    elif gMenuIdx == 3:
        gSt = ST_WEAPONS
    elif gMenuIdx == 4:
        gal_open(ST_CHARACTERS)
    elif gMenuIdx == 5:
        gSt = ST_OPTIONS
    elif gMenuIdx == 6:
        editor_open()
    elif gMenuIdx == 7:
        gSt = ST_PROFILE


def option_enter():
    global gFullscreen, gSmooth, gVolume, gLang, gShowFps, gSt
    g3D = 0
    if gOptIdx == 4:
        gSt = ST_MENU
        play_snd(SND_MENU)
        return
    play_snd(SND_MENU)
    if gOptIdx == 0:
        gSmooth = not gSmooth
    elif gOptIdx == 1:
        gVolume = max(0, min(10, gVolume + 1))
        play_snd(SND_CONFIRM)
    elif gOptIdx == 2:
        gLang ^= 1
        save_lang()
        play_snd(SND_CONFIRM)
    elif gOptIdx == 3:
        gShowFps = not gShowFps
        save_lang()
        play_snd(SND_CONFIRM)


def options_click(mx, my):
    global gOptIdx, gSt, gVolume
    if 8 <= mx <= 88 and 8 <= my <= 26:
        gSt = ST_MENU
        play_snd(SND_MENU)
        return
    if 88 <= mx <= 116 and 78 <= my <= 110:
        gVolume = max(0, gVolume - 1)
        play_snd(SND_CONFIRM)
        return
    if 364 <= mx <= 392 and 78 <= my <= 110:
        gVolume = min(10, gVolume + 1)
        play_snd(SND_CONFIRM)
        return
    i = -1
    if 130 <= mx <= 350:
        for row in range(7):
            if abs(my - (68 + row * 26)) <= 9:
                i = row
                break
    if i >= 0:
        gOptIdx = i
        option_enter()


def weapons_click(mx, my):
    global gWpnMenuSel, gWpnMenuLock, gSt
    if 8 <= mx <= 88 and 8 <= my <= 26:
        gSt = ST_MENU
        gWpnMenuLock = False
        play_snd(SND_MENU)
        return
    for i in range(len(ARMS)):
        y = 56 + i * 19
        if 28 <= mx <= 278 and y - 2 <= my <= y + 14:
            gWpnMenuSel = i
            gWpnMenuLock = True
            play_snd(SND_MENU)
            return
def execute_console_command(command):
    global gConsoleOpen, gConsoleInput, gLevelSel, gSt, gLocalSlot, gMySlot, gTeamCount
    cmd = command.strip().lower()
    if cmd == "menu":
        gConsoleOpen = False
        gConsoleInput = ""
        gSt = ST_MENU
        return
    parts = cmd.split()
    if len(parts) == 2 and parts[0] == "test":
        try:
            world = int(parts[1])
        except ValueError:
            return
        if 1 <= world <= WORLD_COUNT:
            net_close()
            gLevelSel = world - 1
            gTeamCount = 4
            gMySlot = 0
            gLocalSlot = 0
            for i in range(MAX_PLAYERS):
                gKinds[i] = 0
                gBotEnabled[i] = 1
                gLobTeam[i] = i // 3
                gLobChar[i] = i % 7
                gLobReady[i] = 1
            gBotEnabled[0] = 0
            gKinds[0] = 1
            gLobChar[0] = gLobChar[0] % 9
            try:
                game_reset(MODE_TEAMS, -1)
                gSt = ST_PLAY
            except Exception as exc:
                traceback.print_exc()
                try:
                    with open("test_error.log", "a", encoding="utf-8") as log:
                        log.write("test %d: %r\n" % (world, exc))
                        traceback.print_exc(file=log)
                except OSError:
                    pass
                gSt = ST_MENU
                msg("ERROR TEST %d: REVISA test_error.log" % world)
            gConsoleOpen = False
            gConsoleInput = ""


def render_console_overlay():
    if not gConsoleOpen:
        return
    vbuf.fill((8, 5, 16), (18, 18, VIEW_W - 36, 42))
    pygame.draw.rect(vbuf, (200, 160, 66), (18, 18, VIEW_W - 36, 42), 1)
    draw_text(vbuf, 28, 26, 1, (110, 235, 70), "CONSOLE | test 1-6 / menu")
    draw_text(vbuf, 28, 42, 1, (255, 230, 120), ">" + gConsoleInput + "_")


def lobby_click(mx, my):
    global gLobSel, gLobStage, gLobSelRow, gLobCount, gSt, gLocalSlot, gLobbyGot, gJoinReqT, gJoinStartT
    global gChatTyping, gChatInput, gLevelSel, gBotEnabled, gLobIpTyping, gLobIp, gWebLobbyId
    if gLobStage == 3:
        for b, cx in ((0, 42), (1, 142), (2, 282), (3, 430)):
            if abs(mx - cx) <= 42 and 238 <= my <= 256:
                if b == 0:
                    play_snd(SND_MENU)
                    gSt = ST_MENU
                elif b == 1:
                    gLobIpTyping = True
                    play_snd(SND_MENU)
                elif b == 2:
                    gLobCount = 0
                    if IS_WEB:
                        try:
                            from js import window
                            window._refreshLobbies()
                        except Exception:
                            pass
                    else:
                        net_browse_open()
                    play_snd(SND_MENU)
                else:
                    if gLobIpTyping and gLobIp.strip():
                        lobby_connect_ip()
                        return
                    if IS_WEB:
                        web_join_lobby(e.host)
                    elif gLobCount > 0:
                        order = sorted(range(gLobCount),
                                       key=lambda i: (gLobList[i].started, -gLobList[i].filled))
                        e = gLobList[order[min(gLobSel, len(order) - 1)]]
                        if e.started:
                            play_snd(SND_MENU)
                        elif net_client_open(e.addr):
                            gLobStage = 2
                            gLobSelRow = 0
                            gLobbyGot = 0
                            gJoinReqT = 0.0
                            gJoinStartT = gNetTime
                            play_snd(SND_CONFIRM)
                        else:
                            msg("NO SE PUDO CONECTAR")
                return
        for pos in range(min(gLobCount, 6)):
            sy = 58 + pos * 26
            if 20 <= mx <= VIEW_W - 20 and sy - 10 <= my <= sy + 12:
                gLobSel = pos
                if gLobCount > 0:
                    order = sorted(range(gLobCount),
                                   key=lambda i: (gLobList[i].started, -gLobList[i].filled))
                    if IS_WEB:
                        web_join_lobby(gLobList[order[min(gLobSel, len(order) - 1)]].host)
                    else:
                        e = gLobList[order[min(gLobSel, len(order) - 1)]]
                        if e.started:
                            play_snd(SND_MENU)
                        elif net_client_open(e.addr):
                            gLobStage = 2
                            gLobSelRow = 0
                            gLobbyGot = 0
                            gJoinReqT = 0.0
                            gJoinStartT = gNetTime
                            play_snd(SND_CONFIRM)
                        else:
                            msg("NO SE PUDO CONECTAR")
                return
        return
    if gLobStage == 4:
        for i in range(WORLD_COUNT):
            col, row = i % 2, i // 2
            rx, ry = 260 + col * 104, 42 + row * 23
            if rx <= mx <= rx + 96 and ry <= my <= ry + 18:
                gLevelSel = i
                play_snd(SND_MENU)
                return
        # world selector arrows
        if 22 <= mx <= 44 and 112 <= my <= 130:
            gLevelSel = (gLevelSel + WORLD_COUNT - 1) % WORLD_COUNT
            play_snd(SND_MENU)
            return
        if 208 <= mx <= 230 and 112 <= my <= 130:
            gLevelSel = (gLevelSel + 1) % WORLD_COUNT
            play_snd(SND_MENU)
            return
        if 20 <= mx <= 104 and 202 <= my <= 220:
            play_snd(SND_MENU)
            gLobStage = 0
            gSt = ST_MENU
            return
        if 118 <= mx <= 202 and 202 <= my <= 220:
            play_snd(SND_CONFIRM)
            ok = host_open_local() if IS_WEB else net_host_open()
            if ok:
                gLobStage = 1
                gLobSelRow = 0
                gLocalSlot = gMySlot
            else:
                msg("NO SE PUDO CREAR EL LOBBY")
            return
        return
    if gLobStage in (1, 2):
        # Only the creator can launch; READY lives in the player's card.
        for b, cx in ((0, 52), (1, 236), (2, 420)):
            if abs(mx - cx) <= 42 and 254 <= my <= 268:
                if b == 0:
                    play_snd(SND_MENU)
                    gSt = ST_MENU
                elif b == 1 and gLobStage == 1 and gMySlot == 0:
                    for si in range(MAX_PLAYERS):
                        if si != gMySlot:
                            gBotEnabled[si] = 0
                            if gKinds[si] == 0:
                                gLobReady[si] = 0
                    if gSock is not None and not IS_WEB:
                        host_broadcast_lobby()
                    if IS_WEB:
                        web_host_announce()
                    play_snd(SND_MENU)
                elif b == 2 and gLobStage == 1 and gMySlot == 0:
                    lobby_start_match()
                    play_snd(SND_CONFIRM)
                return
        # click the level tag (top right): only the host changes the map
        if my < 20 and mx > VIEW_W - 110 and gHosting:
            gLevelSel = (gLevelSel + 1) % WORLD_COUNT
            play_snd(SND_CONFIRM)
            if gLobStage == 1:
                host_broadcast_lobby()
            return
        # click the chat input line to start typing
        if 8 <= mx <= 472 and 226 <= my <= 238:
            gChatTyping = 1
            gChatInput = ""
            play_snd(SND_MENU)
            return
        for t in range(4):
            bx = 6 + t * 116
            if not (bx <= mx <= bx + 114):
                continue
            for m in range(3):
                sy = 28 + m * 36
                if sy - 5 <= my <= sy + 31:
                    gLobSelRow = t * 3 + m
                    if (gLobStage == 1 and gMySlot == 0 and gKinds[gLobSelRow] == 0 and
                            bx + 72 <= mx <= bx + 110 and sy + 13 <= my <= sy + 28):
                        gBotEnabled[gLobSelRow] ^= 1
                        gLobReady[gLobSelRow] = 1 if gBotEnabled[gLobSelRow] else 0
                        if IS_WEB:
                            web_host_announce()
                        elif gSock is not None:
                            host_broadcast_lobby()
                        play_snd(SND_MENU)
                        return
                    if gLobSelRow == gMySlot and bx + 72 <= mx <= bx + 110 and sy + 13 <= my <= sy + 28:
                        gLobReady[gMySlot] ^= 1
                        if gLobStage == 2 and IS_WEB:
                            try:
                                from js import window
                                window._webLobbyAction(gWebLobbyId, "ready", gMySlot, gLobReady[gMySlot])
                            except Exception:
                                pass
                        elif gLobStage == 1 and IS_WEB:
                            web_host_announce()
                        play_snd(SND_MENU)
                        return
                    if gLobStage == 1:
                        if gKinds[gLobSelRow] == 0 and gLobSelRow != gMySlot:
                            # The leader's seat is fixed: an empty seat only
                            # toggles its bot; it never moves the leader.
                            if gBotEnabled[gLobSelRow]:
                                gBotEnabled[gLobSelRow] = 0
                                if IS_WEB:
                                    web_host_announce()
                                play_snd(SND_MENU)
                        elif gLobSelRow == gMySlot:
                            _lobby_sit_local(gLobSelRow)
                            play_snd(SND_CONFIRM)
                    else:
                        if IS_WEB:
                            try:
                                from js import window
                                window._webLobbyAction(gWebLobbyId, "sit", gLobSelRow, 0)
                            except Exception:
                                pass
                        else:
                            _lobby_sit_net(gLobSelRow)
                        play_snd(SND_CONFIRM)
                    return


def lobby_connect_ip():
    global gLobIpTyping, gLobStage, gLobSelRow, gLobbyGot, gJoinReqT, gJoinStartT
    gLobIpTyping = False
    if IS_WEB:
        msg("LA CONEXION IP REQUIERE LA VERSION NATIVA")
        return
    host = gLobIp.strip()
    if not host:
        msg("ESCRIBE UNA IP")
        return
    if net_client_open(host):
        gLobStage = 2
        gLobSelRow = 0
        gLobbyGot = 0
        gJoinReqT = 0.0
        gJoinStartT = gNetTime
        play_snd(SND_CONFIRM)
    else:
        msg("NO SE PUDO CONECTAR")


def web_join_lobby(host):
    global gWebLobbyId, gLobStage, gLobbyGot, gMySlot, gLocalSlot, gHosting
    if not host.startswith("web-"):
        msg("LOBBY NATIVO NO DISPONIBLE EN WEB")
        return
    gWebLobbyId = host
    gHosting = 0
    gLobStage = 2
    gLobbyGot = 1
    gMySlot = -1
    gLocalSlot = -1
    try:
        from js import window
        window._webLobbyRevision = -1
        window._webLobbyAction(host, "join", -1, 0)
        play_snd(SND_CONFIRM)
    except Exception:
        msg("NO SE PUDO CONECTAR")


def creator_click(mx, my):
    global gCreatorIdx, gCustMine, gCustNameMine, gSt, gCreatorFlashT
    if mx < 210 and 70 <= my <= 248:
        # click on the character preview: cycle base design
        gCreatorIdx = 1
        step_creator(1)
        gCreatorFlashT = 0.18
        play_snd(SND_MENU)
        return
    i = hover_row(78, 24, 7, 210, 470)
    if i < 0:
        return
    if i == 0:
        gCreatorIdx = 0
        play_snd(SND_MENU)
    elif i == 6:
        play_snd(SND_CONFIRM)
        gCustMine = tuple(gCust)
        gCustNameMine = gCustName
        save_lang()
        gSt = ST_MENU
    else:
        gCreatorIdx = i
        if mx < 316:
            step_creator(-1)
            gCreatorFlashT = 0.18
        elif mx > 436:
            step_creator(1)
            gCreatorFlashT = 0.18
        play_snd(SND_MENU)


def render_creator():
    render_bg_sc()
    sc_title(VIEW_W // 2, 20, tr("creator_title"), (200, 160, 66), 3)
    cp = tuple(gCust)
    tex = custom_tex_any(cp)
    if tex is None:
        tex = texChars[cp[0]] if 0 <= cp[0] < len(texChars) and texChars[cp[0]] else texZeke
    zeke_like = cp[0] in (0, 2, 4, 6)
    if tex is texDrawn:
        fr = custom_fr0(tex)
    elif texZeke2 is not None:
        fr = (ZEKE2_DOWN if zeke_like else JULIE2_DOWN)[0]
    else:
        fr = (ZEKE_DOWN if zeke_like else JULIE_DOWN)[0]
    s = 4
    sc_panel(vbuf, (10, 70, 190, 178), (14, 8, 26), _gold, 10)
    draw_text_c(vbuf, 105, 76, 1, (200, 160, 66), tr("creator_name") + ":")
    bx, by = 105 - fr[2] * s // 2, 84
    pygame.draw.rect(vbuf, (34, 20, 50), (bx - 4, by - 4, fr[2] * s + 8, fr[3] * s + 8), 1)
    vbuf.blit(pygame.transform.scale(tex.subsurface(pygame.Rect(fr[0], fr[1], fr[2], fr[3])),
                                     (fr[2] * s, fr[3] * s)), (bx, by))
    draw_text_c(vbuf, 105, 240, 1, (255, 230, 120), custom_display_name())
    labels = [tr("creator_name")] + (CC_LABELS_EN if gLang else CC_LABELS) + [tr("creator_ok")]
    hover = hover_row(78, 24, 7, 210, 470)
    mx2, my2 = mouse_vbuf()
    for i in range(7):
        y = 78 + i * 24
        sel = gCreatorIdx == i
        hov = hover == i
        if sel:
            vbuf.fill((30, 18, 44), (214, y - 3, 252, 20))
            pygame.draw.rect(vbuf, (200, 160, 66), (214, y - 3, 252, 20), 1)
        col = (255, 230, 120) if sel else ((235, 215, 235) if hov else (200, 190, 210))
        draw_text(vbuf, 224, y, 1, col, labels[i])
        if sel or hov:
            draw_text(vbuf, 216, y, 1, (200, 160, 66), ">")
        if i == 0:
            draw_text(vbuf, 348, y, 1, col, gCustName or "...")
            if sel and int(gMenuT * 2) % 2 == 0:
                draw_text(vbuf, 348 + len(gCustName) * 8, y, 1, col, "_")
        elif i == 6:
            draw_text(vbuf, 348, y, 1, col, tr("creator_ok"))
        elif i == 1:
            draw_text(vbuf, 348, y, 1, col, CC_BASE_NAME[gLang][cp[0]])
        else:
            ci = gCust[i - 1]
            name = (CC_COLOR_NAMES_EN if gLang else CC_COLOR_NAMES)[i - 2][ci]
            draw_text(vbuf, 348, y, 1, col, name)
            sw = CC_PAL[i - 2][ci]
            vbuf.fill(sw, (322, y + 2, 14, 9))
            pygame.draw.rect(vbuf, (10, 8, 20), (322, y + 2, 14, 9), 1)
        if 1 <= i <= 5:
            pr = gCreatorPress
            pl = pr == (i, 0)
            prr = pr == (i, 1)
            flash = gCreatorFlashT > 0 and sel
            onl = sel or (hov and mx2 < 316)
            onr = sel or (hov and mx2 > 436)
            lc = (255, 230, 120) if (onl or flash or pl) else ((180, 158, 195) if hov else (110, 96, 130))
            rc = (255, 230, 120) if (onr or flash or prr) else ((180, 158, 195) if hov else (110, 96, 130))
            if pl:
                vbuf.fill(lc, (296, y - 2, 20, 20))
                draw_text_c(vbuf, 306, y + 1, 1, (20, 12, 34), "<")
            else:
                pygame.draw.rect(vbuf, (20, 12, 34), (296, y - 4, 20, 20))
                pygame.draw.rect(vbuf, lc, (296, y - 4, 20, 20), 1)
                draw_text_c(vbuf, 306, y, 1, lc, "<")
            if prr:
                vbuf.fill(rc, (442, y - 2, 20, 20))
                draw_text_c(vbuf, 452, y + 1, 1, (20, 12, 34), ">")
            else:
                pygame.draw.rect(vbuf, (20, 12, 34), (442, y - 4, 20, 20))
                pygame.draw.rect(vbuf, rc, (442, y - 4, 20, 20), 1)
                draw_text_c(vbuf, 452, y, 1, rc, ">")


# ---------------- character pixel editor ----------------
# Templates with red lines for reference - loaded from plantillas_personajes folder
TEMPLATES_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "plantillas_personajes")
texTemplateZeke = None
texTemplateJulie = None
texTemplateRusty = None
texTemplateAzura = None
texTemplateDante = None

def _load_template_from_folder(template_file, fw, fh, rows=4):
    """Load complete red-grid cells from a character template."""
    path = os.path.join(TEMPLATES_FOLDER, template_file)
    if not IS_WEB and not os.path.exists(path):
        print(f"Template not found: {path}")
        return None
    try:
        surf = pygame.image.load(template_file if IS_WEB else path).convert_alpha()
        w, h = surf.get_size()
        cols = 8
        print(f"Loading template: {template_file} ({w}x{h})")
        # Keep the complete cell: the editor canvas must match one red grid
        # segment exactly, including its 1px reference border.
        frames = []
        for r in range(rows):
            for c in range(cols):
                # The source sheets label the lateral rows in reverse order.
                # Store them in the editor's canonical DOWN, LEFT, UP, RIGHT
                # order by exchanging source rows 2 and 4.
                source_r = 3 if rows == 4 and r == 1 else 1 if rows == 4 and r == 3 else r
                x = c * fw
                y = source_r * fh
                frame_w = fw
                frame_h = fh
                if x + frame_w <= w and y + frame_h <= h:
                    frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
                    frame.blit(surf, (0, 0), pygame.Rect(x, y, frame_w, frame_h))
                    frames.append(frame)
        # If only 3 rows (24 frames), add 8 empty frames for 4th row (RIGHT)
        while len(frames) < 32:
            frames.append(pygame.Surface((frame_w, frame_h), pygame.SRCALPHA))
        print(f"  Extracted {len(frames)} frames of size {frame_w}x{frame_h}")
        return frames
    except Exception as e:
        print(f"Error loading template {template_file}: {e}")
        return None

_TPL_SOURCES = [
    ("1_ZEKErojo.png", "1_ZEKE_rojo.png", "1_ZEKE.png", 23, 38),
    ("2_JULIE_rojo.png", "2_JULIE.png", None, 29, 38),
    ("3_RUSTY_rojo.png", "3_RUSTY.png", None, 23, 38),
    ("4_AZURA_rojo.png", "4_AZURA.png", None, 29, 38),
    ("5_DANTE_rojo.png", "5_DANTE.png", None, 23, 38),
]


def _load_guide_cell(bi):
    """Raw top-left cell (with its red border) of the character's plantilla
    file - the template reference, never the charsel sprite."""
    src = _TPL_SOURCES[bi] if 0 <= bi < len(_TPL_SOURCES) else _TPL_SOURCES[0]
    fw, fh = src[3], src[4]
    for fn in src[:3]:
        if fn is None:
            continue
        path = os.path.join(TEMPLATES_FOLDER, fn)
        if os.path.exists(path):
            try:
                surf = pygame.image.load(path).convert_alpha()
                return surf.subsurface(pygame.Rect(0, 0, fw, fh)).copy()
            except Exception:
                return None
    return None


def editor_open():
    global gEdFrames, gEdFW, gEdFH, gEdAction, gEdFrame, gEdColor, gEdErase, gEdBrush, gEdL1, gEdL2, gEdPlay, gEdT, gEdFlashT, gEdButtonT, gEdPressed, gEdMode, gSt, gEdRefTex, gEdGuide, gEdGhostMirrorLeft, gEdGhostIsTemplate
    global texTemplateZeke, texTemplateJulie, texTemplateRusty, texTemplateAzura, texTemplateDante
    
    # Load templates from plantillas_personajes folder if not already loaded
    if texTemplateZeke is None:
        print("\n=== Loading character templates from plantillas_personajes ===")
        # Zeke: 1_ZEKErojo.png or 1_ZEKE_rojo.png (23x38, 3 rows)
        texTemplateZeke = _load_template_from_folder("1_ZEKErojo.png", 23, 38, rows=3)
        if texTemplateZeke is None:
            texTemplateZeke = _load_template_from_folder("1_ZEKE_rojo.png", 23, 38, rows=3)
        
        # Julie: 2_JULIE_rojo.png (29x38, 4 rows)
        texTemplateJulie = _load_template_from_folder("2_JULIE_rojo.png", 29, 38, rows=4)
        
        # Rusty: 3_RUSTY_rojo.png (23x38, 3 rows)
        texTemplateRusty = _load_template_from_folder("3_RUSTY_rojo.png", 23, 38, rows=3)
        
        # Azura: 4_AZURA_rojo.png (29x38, 4 rows)
        texTemplateAzura = _load_template_from_folder("4_AZURA_rojo.png", 29, 38, rows=4)
        
        # Dante: 5_DANTE_rojo.png (23x38, 3 rows)
        texTemplateDante = _load_template_from_folder("5_DANTE_rojo.png", 23, 38, rows=3)
        print("=== Templates loaded ===\n")
    
    # A newly opened editor starts from the selected character template. A
    # gallery reference is assigned explicitly by gal_select().
    gEdRefTex = None
    gEdMode = "character"
    bi = gCust[0]
    gEdGhostMirrorLeft = bi not in (1, 3)
    gEdGhostIsTemplate = True
    templates = [texTemplateZeke, texTemplateJulie, texTemplateRusty,
                 texTemplateAzura, texTemplateDante]
    default_template = templates[bi] if 0 <= bi < len(templates) else texTemplateZeke
    if default_template:
        fw, fh = default_template[0].get_size()
        gEdRefTex = pygame.Surface((fw * 8, fh * 4), pygame.SRCALPHA)
        for idx, frame in enumerate(default_template[:32]):
            gEdRefTex.blit(frame, ((idx % 8) * fw, (idx // 8) * fh))
    if texDrawn is not None:
        # User has already drawn something, use that
        gEdGuide = None
        # Normalize old/gallery sheets to the selected character cell size.
        # Otherwise a previously saved full sheet can become the drawing cell.
        gEdFW = 29 if gCust[0] in (1, 3) else 23
        gEdFH = 38
        src_fw = max(1, texDrawn.get_width() // 8)
        src_fh = max(1, texDrawn.get_height() // 4)
        gEdFrames = []
        for r in range(4):
            for f in range(8):
                s = pygame.Surface((gEdFW, gEdFH), pygame.SRCALPHA)
                src = texDrawn.subsurface(pygame.Rect(f * src_fw, r * src_fh, src_fw, src_fh))
                s.blit(pygame.transform.scale(src, (gEdFW, gEdFH)), (0, 0))
                gEdFrames.append(s)
    else:
        # No custom drawing yet, load template for the selected character
        template = None
        
        # Map character index to template
        if bi == 0:
            template = texTemplateZeke
        elif bi == 1:
            template = texTemplateJulie
        elif bi == 2:
            template = texTemplateRusty
        elif bi == 3:
            template = texTemplateAzura
        elif bi == 4:
            template = texTemplateDante
        else:
            # Fallback to Zeke
            template = texTemplateZeke
        
        if template is not None and len(template) > 0:
            # Blank canvas for the design - the template art is ONLY shown as
            # the small red-bordered guide, never pre-filled into the drawing
            gEdFW = template[0].get_width()
            gEdFH = template[0].get_height()
            gEdFrames = [pygame.Surface((gEdFW, gEdFH), pygame.SRCALPHA) for _ in range(32)]
            
            # Create reference texture for ghost overlay
            gEdRefTex = pygame.Surface((gEdFW * 8, gEdFH * 4), pygame.SRCALPHA)
            for idx, frame in enumerate(template):
                r = idx // 8
                c = idx % 8
                gEdRefTex.blit(frame, (c * gEdFW, r * gEdFH))
            
            print(f"Using template for character {bi}: {gEdFW}x{gEdFH} frames")
            gEdGuide = _load_guide_cell(bi)
        else:
            # Fallback: create empty frames
            gEdGuide = None
            base = texChars[bi] if 0 <= bi < len(texChars) and texChars[bi] else texZeke
            fr0 = _sheet_rects(base)[0]
            gEdFW, gEdFH = fr0[2], fr0[3]
            gEdFrames = [pygame.Surface((gEdFW, gEdFH), pygame.SRCALPHA) for _ in range(32)]
            print(f"Using empty frames: {gEdFW}x{gEdFH}")
    
    gEdAction = gEdFrame = 0
    gEdColor = 2
    gEdErase = False
    gEdL1 = True
    gEdL2 = True
    gEdPlay = False
    gEdT = 0.0
    gEdFlashT = 0.0
    gEdButtonT = 0.0
    gEdPressed = ""
    gEdNameTyping = False
    gSt = ST_EDITOR


def neighbors_open():
    """Open the same pixel editor using the neighbor walk-cycle canvas."""
    global gEdFrames, gEdFW, gEdFH, gEdAction, gEdFrame, gEdColor, gEdErase
    global gEdL1, gEdL2, gEdPlay, gEdT, gEdFlashT, gEdButtonT, gEdPressed
    global gEdMode, gEdRefTex, gEdGuide, gEdGhostMirrorLeft, gEdGhostIsTemplate, gSt
    gEdMode = "neighbor"
    gEdFW, gEdFH = 44, 41
    gEdFrames = [pygame.Surface((gEdFW, gEdFH), pygame.SRCALPHA) for _ in range(32)]
    if gNeighborDrawn is not None:
        src_fw = max(1, gNeighborDrawn.get_width() // 8)
        src_fh = max(1, gNeighborDrawn.get_height() // 4)
        for n in range(32):
            src = gNeighborDrawn.subsurface(pygame.Rect((n % 8) * src_fw, (n // 8) * src_fh, src_fw, src_fh))
            gEdFrames[n].blit(pygame.transform.scale(src, (gEdFW, gEdFH)), (0, 0))
    gEdRefTex = pygame.Surface((gEdFW * 8, gEdFH * 4), pygame.SRCALPHA)
    for n in range(32):
        fr = VIC_CHEER[n % len(VIC_CHEER)]
        cell = pygame.Surface((gEdFW, gEdFH), pygame.SRCALPHA)
        cell.blit(texVict, (0, 0), pygame.Rect(*fr))
        gEdRefTex.blit(cell, ((n % 8) * gEdFW, (n // 8) * gEdFH))
    gEdGuide = None
    gEdGhostMirrorLeft = False
    gEdGhostIsTemplate = False
    gEdAction = gEdFrame = 0
    gEdColor = 2
    gEdErase = False
    gEdBrush = 1
    gEdBrush = 1
    gEdL1 = gEdL2 = True
    gEdPlay = False
    gEdT = gEdFlashT = gEdButtonT = 0.0
    gEdPressed = ""
    gSt = ST_EDITOR


def ed_px(fr, x, y, c):
    if IS_WEB:
        pygame._setPxRGBA(fr._c, x, y, c[0], c[1], c[2], c[3])
    else:
        fr.set_at((x, y), c)


def ed_clear_frame():
    fr = gEdFrames[gEdAction * 8 + gEdFrame]
    if IS_WEB:
        for yy in range(gEdFH):
            for xx in range(gEdFW):
                pygame._setPxRGBA(fr._c, xx, yy, 0, 0, 0, 0)
    else:
        fr.fill((0, 0, 0, 0))


# -- drawing pad helpers (zoom fills the screen) --
def _ed_zoom():
    """max zoom so the full frame fits in the free screen area."""
    max_w = VIEW_W - ED_CX - 12
    max_h = VIEW_H - ED_CY - 44       # 44px = timeline + buttons + hint
    if gEdMode == "neighbor":
        return 3
    return max(ED_ZOOM, min(max_w // max(1, gEdFW), max_h // max(1, gEdFH)))


def _ed_pad_rect():
    """Return the drawing pad rectangle in the shared editor layout."""
    z = _ed_zoom()
    cw = gEdFW * z
    # Julie/Azura need a little more vertical room for their taller silhouette
    # while the saved sprite cell remains the canonical 29x38.
    ch = gEdFH * z + (8 if gEdFW == 29 else 0)
    work_x = 58
    # Reserve the right column for the PERSONAJES/VECINOS mode buttons.
    work_w = VIEW_W - work_x - 94
    avail_h = VIEW_H - ED_CY - 44
    preview_gap = 18
    x0 = work_x + (work_w - (cw * 2 + preview_gap)) // 2
    y0 = ED_CY + (avail_h - ch) // 2
    return (x0, y0, cw, ch)


def _ed_preview_rect():
    x0, y0, cw, ch = _ed_pad_rect()
    return (x0 + cw + 18, y0, cw, ch)


def _ed_bottom_buttons():
    x0, y0, cw, ch = _ed_pad_rect()
    by = y0 + ch + 30
    return [("back", 52, by), ("clear", 142, by), ("save", 232, by),
            ("gallery", 332, by), ("preview", 428, by)]


def _ed_rect_contains(rect, mx, my):
    x, y, w, h = rect
    return x <= mx <= x + w and y <= my <= y + h


def _ed_tab_rect(a):
    cx = 84 + a * 104
    return (cx - 52, 26, 104, 16)


def _ed_layer_rect(layer):
    return (3, 153 if layer == 1 else 168 if layer == 2 else 184,
            46, 14 if layer < 3 else 18)


def _ed_arrow_rect(delta):
    x0, y0, cw, ch = _ed_pad_rect()
    yc = y0 + ch // 2
    return ((x0 - 32, yc - 16, 24, 32) if delta < 0 else
            (x0 + cw + 4, yc - 16, 24, 32))


def _ed_mode_rect(mode):
    return (434, 44 if mode == "character" else 58, 42, 10)


def _ed_press(name):
    global gEdButtonT, gEdPressed
    gEdButtonT = 0.18
    gEdPressed = name


def _ed_pressed(name):
    return gEdPressed == name and gEdButtonT > 0


def _ed_sprite_px(mx, my):
    """convert screen coords to sprite pixel (rx, ry) inside the pad, or (-1,-1)."""
    x0, y0, cw, ch = _ed_pad_rect()
    z = _ed_zoom()
    rx = (mx - x0) // z
    ry = int((my - y0) * gEdFH / max(1, ch))
    if 0 <= rx < gEdFW and 0 <= ry < gEdFH:
        return (rx, ry)
    return (-1, -1)


def _ed_arrow_hit(mx, my):
    """(-1)=left, (+1)=right, 0=miss."""
    if _ed_rect_contains(_ed_arrow_rect(-1), mx, my):
        return -1
    if _ed_rect_contains(_ed_arrow_rect(1), mx, my):
        return 1
    return 0


def _ed_palette_hit(mx, my):
    for i in range(len(EDIT_PAL)):
        col, row = i // 8, i % 8
        if _ed_rect_contains((8 + col * 20, 46 + row * 12, 18, 10), mx, my):
            return i
    return -1


def _ed_tab_hit(mx, my):
    """Return the animation tab under the pointer, or -1."""
    for a in range(4):
        if _ed_rect_contains(_ed_tab_rect(a), mx, my):
            return a
    return -1


# -- timeline (below the pad) --
def _tl_frame(mx):
    tlx = 54
    tsp = 52
    return max(0, min(7, round((mx - tlx) / tsp)))


def _tl_hit(mx, my):
    return 34 <= mx <= 438 and 204 <= my <= 236


# -- paint --
def ed_paint(mx, my, force_erase=False):
    rx, ry = _ed_sprite_px(mx, my)
    if rx < 0:
        return
    idx = gEdAction * 8 + gEdFrame
    color = (0, 0, 0, 0) if gEdErase or force_erase else (*EDIT_PAL[gEdColor], 255)
    radius = gEdBrush // 2
    for py in range(ry - radius, ry + radius + 1):
        for px in range(rx - radius, rx + radius + 1):
            if 0 <= px < gEdFW and 0 <= py < gEdFH:
                ed_px(gEdFrames[idx], px, py, color)


def editor_brush_wheel(delta):
    global gEdBrush
    gEdBrush = max(1, min(5, gEdBrush + (1 if delta > 0 else -1)))


def ed_complete():
    """True when every one of the 32 animation frames has real content."""
    for fr in gEdFrames:
        op = 0
        if IS_WEB:
            data = pygame._canvasData(fr._c)
            for i in range(3, len(data), 4):
                if data[i] > 40:
                    op += 1
        else:
            px = pygame.PixelArray(fr)
            for yy in range(gEdFH):
                for xx in range(gEdFW):
                    if fr.unmap_rgb(px[xx, yy])[3] > 40:
                        op += 1
            del px
        if op < 12:
            return False
    return True


def editor_save():
    global texDrawn, gNeighborDrawn, gUpState, gEdFlashT, gCustMine, gCustNameMine
    fw, fh = gEdFW, gEdFH
    sheet = pygame.Surface((fw * 8, fh * 4), pygame.SRCALPHA)
    for r in range(4):
        for f in range(8):
            sheet.blit(gEdFrames[r * 8 + f], (f * fw, r * fh))
    if gEdMode == "neighbor":
        gNeighborDrawn = sheet
        if IS_WEB:
            from js import window
            try:
                data = bytes(pygame._canvasData(sheet._c))
                window.localStorage.setItem("zamn_neighbor_drawn", base64.b64encode(data).decode("ascii"))
                window.localStorage.setItem("zamn_neighbor_drawn_dim", "%dx%d" % (fw * 8, fh * 4))
            except Exception:
                pass
        else:
            try:
                pygame.image.save(sheet, os.path.join(ASSETS, "custom_neighbor.png"))
            except Exception:
                pass
        gUpState = 3
        gEdFlashT = 1.2
        play_snd(SND_CONFIRM)
        return


    if IS_WEB:
        from js import window
        try:
            data = bytes(pygame._canvasData(sheet._c))
            b64 = base64.b64encode(data).decode("ascii")
            window.localStorage.setItem("zamn_drawn", b64)
            window.localStorage.setItem("zamn_drawn_dim", "%dx%d" % (fw * 8, fh * 4))
        except Exception:
            pass
    else:
        try:
            pygame.image.save(sheet, os.path.join(ASSETS, "custom_drawn.png"))
        except Exception:
            pass
    texDrawn = sheet
    gCustMine = tuple(gCust)
    gCustNameMine = gCustName
    # Every saved character is persisted privately on the server. Publication
    # is a separate action from MIS DISENOS.
    gal_start_upload(custom_display_name())
    save_lang()
    gEdFlashT = 2.2 if gUpState else 1.2
    play_snd(SND_CONFIRM)


# ---------------- global design gallery ----------------
def neighbor_sheet(vtype):
    base = VIC_BASE[vtype] if 0 <= vtype < len(VIC_BASE) else 0
    tint = VIC_TINT[vtype] if 0 <= vtype < len(VIC_TINT) else None
    tex = texVict
    if tint is not None:
        key = (base, tint)
        tex = _victim_cache.get(key)
        if tex is None:
            tex = recolor(texVict, tint)
            _victim_cache[key] = tex
    sheet = pygame.Surface((44 * 8, 41 * 4), pygame.SRCALPHA)
    frames = VIC_FRAMES[base]
    for n in range(32):
        sheet.blit(tex, ((n % 8) * 44, (n // 8) * 41), pygame.Rect(*frames[n % len(frames)]))
    return sheet


def _gal_locales():
    """Local character or neighbor references for the active editor mode."""
    if gGalMode == "neighbors":
        return ([{"id": "n%d" % i, "name": VIC_NAMES[i], "local": True, "neighbor": True}
                 for i in range(len(VIC_NAMES))]
                + ([{"id": "nmine", "name": "MI VECINO", "local": True, "neighbor": True}]
                   if gNeighborDrawn is not None else []))
    lst = []
    names = ["ZEKE", "JULIE", "RUSTY", "AZURA", "DANTE"]
    for i, name in enumerate(names):
        lst.append({"id": "t%d" % i, "name": "PLANTILLA " + name, "local": True, "template": True})
    if texDrawn is not None:
        lst.append({"id": "lmine", "name": gCustName or "MI DISENO", "local": True})
    return lst


def _gal_combine(remote):
    # Remote designs are user skins; keep their original proxy/object type so
    # the browser and native gallery paths behave identically.
    if gGalMine:
        return list(remote)
    return _gal_locales() + ([] if gGalMode == "neighbors" else list(remote))


def design_owner_id():
    if IS_WEB:
        try:
            from js import window
            return str(window._designOwnerId)
        except Exception:
            return "browser"
    return socket.gethostname()


def _gal_worker_list():
    global gDesigns, gGalState
    try:
        url = SITE + "/api/designs"
        if gGalMine:
            url += "/mine/" + urllib.parse.quote(design_owner_id())
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8"))
        if isinstance(data, dict):
            data = [data]
        gDesigns = _gal_combine(data)
        gGalState = "done"
    except Exception:
        gGalState = "error"


def _gal_worker_fetch(pid):
    global gDesignData, gGalDataState, gEdRefTex, gEdGhostIsTemplate
    try:
        with urllib.request.urlopen(SITE + "/api/designs/" + urllib.parse.quote(pid), timeout=6) as r:
            png = r.read()
        surf = pygame.image.load(io.BytesIO(png)).convert_alpha()
        gDesignData = (pid, surf, png)
        gEdRefTex = surf
        gEdGhostIsTemplate = False
        gGalDataState = "done"
    except Exception:
        gDesignData = ("err", None, None)
        gGalDataState = "error"


def _gal_worker_upload(name, png_b64):
    global gUpState
    try:
        body = json.dumps({"name": name, "png": png_b64,
                           "owner": design_owner_id(), "public": False}).encode("utf-8")
        req = urllib.request.Request(SITE + "/api/designs", data=body,
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=8)
        gUpState = 2
    except Exception:
        gUpState = 3


def gal_fetch_list():
    global gGalState
    gGalState = "loading"
    if IS_WEB:
        try:
            from js import window
            (window._refreshMyDesigns() if gGalMine else window._refreshDesigns())
        except Exception:
            gGalState = "error"
    else:
        threading.Thread(target=_gal_worker_list, daemon=True).start()


def gal_fetch_design(pid):
    global gGalDataState, gDesignData
    gGalDataState = "loading"
    gDesignData = None
    if IS_WEB:
        try:
            from js import window
            window._getDesign(pid)
        except Exception:
            gGalDataState = "error"
    else:
        threading.Thread(target=_gal_worker_fetch, args=(pid,), daemon=True).start()


def gal_start_upload(name):
    global gUpState
    gUpState = 1
    if IS_WEB:
        try:
            from js import window
            window._uploadDesign(name, pygame._toPngBase64(texDrawn._c))
        except Exception:
            gUpState = 3
    else:
        try:
            tmp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp_upload.png")
            pygame.image.save(texDrawn, tmp)
            with open(tmp, "rb") as f:
                png_b64 = base64.b64encode(f.read()).decode("ascii")
            try:
                os.remove(tmp)
            except Exception:
                pass
            threading.Thread(target=_gal_worker_upload, args=(name, png_b64), daemon=True).start()
        except Exception:
            gUpState = 3


def gal_open(return_state=ST_EDITOR):
    global gGalSel, gGalState, gGalDataState, gDesignData, gDesigns, gGalFlashT, gGalUseReq, gSt, gGalReturnState, gGalMode, gGalMine, gGalRenameInput, gGalNameTyping
    gGalSel = 0
    gGalState = "idle"
    gGalDataState = "idle"
    gDesignData = None
    gGalFlashT = 0.0
    gGalUseReq = False
    gGalReturnState = return_state
    gGalMode = "characters" if return_state == ST_CHARACTERS else ("neighbors" if gEdMode == "neighbor" else "characters")
    gGalMine = False
    gGalRenameInput = ""
    gGalNameTyping = False
    gDesigns = _gal_locales()
    gal_fetch_list()
    gSt = ST_GALLERY


def gal_publish_selected():
    global gGalFlashT
    if not gGalMine or not (0 <= gGalSel < len(gDesigns)):
        return
    pid = gDesigns[gGalSel].get("id")
    if not pid:
        return
    if IS_WEB:
        try:
            from js import window
            window._publishDesign(pid, design_owner_id(), gGalRenameInput.strip()[:24])
            gGalFlashT = 1.2
        except Exception:
            pass
    else:
        try:
            body = json.dumps({"id": pid, "owner": design_owner_id(),
                               "name": gGalRenameInput.strip()[:24]}).encode("utf-8")
            req = urllib.request.Request(SITE + "/api/designs/publish", data=body,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=6).read()
            gal_fetch_list()
            gGalFlashT = 1.2
        except Exception:
            pass


def gal_rename_selected():
    global gGalFlashT, gGalNameTyping
    if not gGalMine or not (0 <= gGalSel < len(gDesigns)):
        return
    pid = gDesigns[gGalSel].get("id")
    name = gGalRenameInput.strip()[:24]
    if not pid or not name:
        return
    gGalNameTyping = False
    if IS_WEB:
        try:
            from js import window
            window._renameDesign(pid, design_owner_id(), name)
            gGalFlashT = 1.2
        except Exception:
            pass
    else:
        try:
            body = json.dumps({"id": pid, "owner": design_owner_id(), "name": name}).encode("utf-8")
            req = urllib.request.Request(SITE + "/api/designs/rename", data=body,
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=6).read()
            gal_fetch_list()
            gGalFlashT = 1.2
        except Exception:
            pass
def gal_select(i):
    global gGalSel, gGalRenameInput, gDesignData, gGalDataState, gEdRefTex, gEdGhostMirrorLeft, gEdGhostIsTemplate
    gGalSel = i
    if 0 <= i < len(gDesigns):
        g = gDesigns[i]
        gGalRenameInput = g.get("name", "") if gGalMine else ""
        if g.get("local"):
            if g.get("neighbor"):
                if g["id"] == "nmine":
                    tex = gNeighborDrawn
                else:
                    tex = neighbor_sheet(int(g["id"][1:]))
                if tex is not None:
                    gEdRefTex = tex
                    gEdGhostIsTemplate = False
                    gDesignData = (g["id"], tex, None)
                    gGalDataState = "done"
                return
            if g.get("template"):
                bi = int(g["id"][1:])
                templates = [texTemplateZeke, texTemplateJulie, texTemplateRusty,
                             texTemplateAzura, texTemplateDante]
                frames = templates[bi] if 0 <= bi < len(templates) else None
                if frames:
                    gEdGhostMirrorLeft = bi not in (1, 3)
                    gEdGhostIsTemplate = True
                    fw, fh = frames[0].get_size()
                    tex = pygame.Surface((fw * 8, fh * 4), pygame.SRCALPHA)
                    for n, frame in enumerate(frames[:32]):
                        tex.blit(frame, ((n % 8) * fw, (n // 8) * fh))
                    gEdRefTex = tex
                    gDesignData = (g["id"], tex, None)
                    gGalDataState = "done"
                return
            if g["id"] == "lmine":
                tex = texDrawn
            else:
                tex = texChars[int(g["id"][1:])] if int(g["id"][1:]) < len(texChars) else None
            if tex is not None:
                if g["id"] == "lmine":
                    gEdRefTex = tex
                    gEdGhostIsTemplate = False
                else:
                    gEdRefTex = None  # local chars are gameplay sheets - never use as ghost
                gDesignData = (g["id"], tex, None)
                gGalDataState = "done"
            return
        gal_fetch_design(g["id"])


def gal_use_now():
    global gGalUseReq, gGalFlashT
    if gGalDataState == "done" and gDesignData and gDesignData[0] != "err" \
            and 0 <= gGalSel < len(gDesigns) and gDesignData[0] == gDesigns[gGalSel]["id"]:
        gal_apply()
    else:
        gGalUseReq = True


def gal_apply():
    global texDrawn, gCustName, gCustNameMine, gGalFlashT, gCustMine, gEdRefTex
    global gEdFrames, gEdFW, gEdFH, gEdAction, gEdFrame, gSt, gEdMode, gEdGhostMirrorLeft, gEdGhostIsTemplate, gLobChar
    pid, surf, png = gDesignData
    if pid.startswith("n"):
        gEdMode = "neighbor"
        gEdRefTex = surf
        gEdFW, gEdFH = 44, 41
        gEdFrames = [pygame.Surface((gEdFW, gEdFH), pygame.SRCALPHA) for _ in range(32)]
        gEdAction = gEdFrame = 0
        gSt = ST_EDITOR
        gGalFlashT = 0.0
        play_snd(SND_CONFIRM)
        return
    if pid.startswith("t"):
        # Templates are guides, never playable red-bordered character sheets.
        gEdRefTex = surf
        gEdGhostMirrorLeft = int(pid[1:]) not in (1, 3)
        gEdGhostIsTemplate = True
        gEdFW, gEdFH = surf.get_width() // 8, surf.get_height() // 4
        gEdFrames = [pygame.Surface((gEdFW, gEdFH), pygame.SRCALPHA) for _ in range(32)]
        gEdAction = gEdFrame = 0
        if gGalReturnState == ST_CHARACTERS:
            selected = int(pid[1:])
            gLobChar[0] = selected
            if 0 <= selected < len(CHARNAME):
                gCustName = CHARNAME[selected]
                gCustNameMine = gCustName
                save_lang()
            gSt = ST_MENU
        else:
            gSt = ST_EDITOR if gGalReturnState != ST_LOBBY else ST_LOBBY
        gGalFlashT = 0.0
        play_snd(SND_CONFIRM)
        return
    if pid.startswith("l") and pid != "lmine":
        gEdRefTex = None  # gameplay character sheets never serve as ghost
    else:
        gEdRefTex = surf
        gEdGhostIsTemplate = False
    if IS_WEB:
        try:
            from js import window
            data = bytes(pygame._canvasData(surf._c))
            b64 = base64.b64encode(data).decode("ascii")
            w, h = surf.get_size()
            window.localStorage.setItem("zamn_drawn", b64)
            window.localStorage.setItem("zamn_drawn_dim", "%dx%d" % (w, h))
        except Exception:
            pass
    else:
        try:
            if png is not None:
                with open(os.path.join(ASSETS, "custom_drawn.png"), "wb") as f:
                    f.write(png)
            else:
                pygame.image.save(surf, os.path.join(ASSETS, "custom_drawn.png"))
        except Exception:
            pass
    texDrawn = surf
    if 0 <= gGalSel < len(gDesigns):
        gCustName = gDesigns[gGalSel]["name"]
    gCustMine = tuple(gCust)
    save_lang()
    if gGalReturnState == ST_LOBBY and 0 <= gMySlot < MAX_PLAYERS:
        # A gallery design is the local player's custom skin in the lobby.
        gLobChar[gMySlot] = 8
        if gSock is not None and gHostAddr is not None:
            send_custom(gHostAddr, gMySlot, tuple(gCust), gCustName)
    elif gGalReturnState == ST_CHARACTERS:
        gLobChar[0] = 8
    gGalFlashT = 1.6
    gSt = ST_MENU if gGalReturnState == ST_CHARACTERS else gGalReturnState
    play_snd(SND_CONFIRM)


def gal_click(mx, my):
    global gGalSel, gSt, gGalReturnState, gGalMine, gDesignData, gGalNameTyping
    if gGalMine and 326 <= mx <= 468 and 174 <= my <= 190:
        gGalNameTyping = True
        return
    rows = min(len(gDesigns), 12)
    for i in range(rows):
        if 20 <= mx <= 310 and abs(my - (44 + i * 12 + 5)) <= 6:
            if i == gGalSel:
                gal_use_now()
            else:
                gal_select(i)
            play_snd(SND_MENU)
            return
    buttons = [(65, 0), (175, 1), (285, 2)]
    if gGalReturnState == ST_CHARACTERS:
        buttons.append((415, 3))
    for cx, b in buttons:
        if abs(mx - cx) <= 50 and 196 <= my <= 212:
            if b == 0:
                play_snd(SND_MENU)
                gSt = ST_MENU if gGalReturnState == ST_CHARACTERS else gGalReturnState
            elif b == 1:
                if gGalMine:
                    if 0 <= gGalSel < len(gDesigns) and gDesigns[gGalSel].get("public"):
                        gal_rename_selected()
                    else:
                        gal_publish_selected()
                else:
                    gal_use_now()
            elif b == 2:
                gal_fetch_list()
            else:
                gGalMine = not gGalMine
                gGalSel = 0
                gDesignData = None
                gal_fetch_list()
            return


def custom_tex_any(params):
    if texDrawn is not None and list(params) == list(gCust):
        return texDrawn
    return custom_tex(params)


def custom_fr0(tex):
    return (0, 0, tex.get_width() // 8, tex.get_height() // 4)


def _editor_ghost():
    """Return a semi-transparent reference frame for the editor - ONLY from templates, NEVER from gameplay sheets."""
    try:
        # ONLY use gEdRefTex (from templates), NEVER use texChars
        if gEdRefTex is not None:
            row = gEdAction if gEdAction < 4 else 0
            # Gallery sheets can use a different cell size. Read their own
            # grid and scale only the selected cell into the editor pad.
            src_fw = max(1, gEdRefTex.get_width() // 8)
            src_fh = max(1, gEdRefTex.get_height() // 4)
            mirror = gEdGhostMirrorLeft and row in (1, 3)
            if row == 3 and gEdGhostMirrorLeft:
                # Three-row templates have no native right-facing row.
                row = 1
                mirror = True
            x = gEdFrame * src_fw
            y = row * src_fh
            # Scale the reference cell to exactly the drawing pad. This keeps
            # the red template segment and the editable grid aligned.
            z = _ed_zoom()
            source = gEdRefTex.subsurface(pygame.Rect(x, y, src_fw, src_fh))
            if gEdGhostIsTemplate and src_fw > 2 and src_fh > 2:
                # Template borders are guides, not part of the ghost.
                source = source.subsurface(pygame.Rect(1, 1, src_fw - 2, src_fh - 2))
            g = pygame.transform.scale(
                source,
                (gEdFW * z, gEdFH * z)).copy()
            if mirror:
                g = pygame.transform.flip(g, True, False)
            # Keep the reference strong enough against the dark editor canvas,
            # including the browser canvas where alpha is composited twice.
            g.set_alpha(165)
            return g
    except Exception:
        pass
    
    # Keep a visible direction guide even if a browser asset failed to decode.
    try:
        z = _ed_zoom()
        g = pygame.Surface((gEdFW * z, gEdFH * z), pygame.SRCALPHA)
        pygame.draw.rect(g, (235, 70, 70, 220), (1, 1, gEdFW * z - 2, gEdFH * z - 2), max(1, z // 2))
        pygame.draw.line(g, (255, 150, 90, 220), (gEdFW * z // 2, z),
                         (gEdFW * z // 2, gEdFH * z - z), max(1, z // 2))
        g.set_alpha(165)
        return g
    except Exception:
        return None


def _ed_template_guide():
    """First frame (top-left cell) of the character plantilla, red border
    included - scaled to FIT inside the drawing box without covering it."""
    if gEdGuide is None:
        return None
    try:
        x0, y0, cw, ch = _ed_pad_rect()
        gw, gh = gEdGuide.get_size()
        g = pygame.transform.scale(gEdGuide, (cw, ch)).copy()
        g.set_alpha(120)
        return g
    except Exception:
        return None


def editor_click(mx, my):
    global gEdAction, gEdColor, gEdErase, gEdPlay, gEdFlashT, gSt, gEdL1, gEdL2, gEdFrame, gEdNameTyping
    global gCustName
    if 414 <= mx <= 476 and 74 <= my <= 92:
        gEdNameTyping = True
        play_snd(SND_MENU)
        return
    if _ed_rect_contains(_ed_mode_rect("character"), mx, my):
        _ed_press("mode_character")
        editor_open()
        return
    if _ed_rect_contains(_ed_mode_rect("neighbor"), mx, my):
        _ed_press("mode_neighbor")
        neighbors_open()
        return
    # 1) action tabs (top)
    a = _ed_tab_hit(mx, my)
    if a >= 0:
        gEdAction = a
        _ed_press("tab%d" % a)
        play_snd(SND_MENU)
        return
    # 2) palette (two columns, eight colors per column)
    i = _ed_palette_hit(mx, my)
    if i >= 0:
        gEdColor = i
        gEdErase = False
        _ed_press("color%d" % i)
        play_snd(SND_MENU)
        return
    # 3) layer toggles L1 / L2 (below palette)
    if _ed_rect_contains(_ed_layer_rect(1), mx, my):
        gEdL1 = not gEdL1
        _ed_press("l1")
        play_snd(SND_MENU)
        return
    if _ed_rect_contains(_ed_layer_rect(2), mx, my):
        gEdL2 = not gEdL2
        _ed_press("l2")
        play_snd(SND_MENU)
        return
    # 4) eye toggles both layers together (master visibility).
    if _ed_rect_contains(_ed_layer_rect(3), mx, my):
        gEdL1 = not gEdL1
        gEdL2 = not gEdL2
        _ed_press("eye")
        play_snd(SND_MENU)
        return
    # 5) frame arrows (spaced outside the pad)
    dx = _ed_arrow_hit(mx, my)
    if dx != 0:
        gEdFrame = (gEdFrame + dx) % 8
        _ed_press("arrow_left" if dx < 0 else "arrow_right")
        play_snd(SND_MENU)
        return
    # 6) drawing pad
    rx, ry = _ed_sprite_px(mx, my)
    if rx >= 0:
        ed_paint(mx, my)
        return
    # 7) timeline (below pad)
    if _tl_hit(mx, my):
        gEdFrame = _tl_frame(mx)
        _ed_press("timeline")
        play_snd(SND_MENU)
        return
    # 8) bottom buttons  [ VOLVER  CLEAR  GUARDAR  GALERIA  PREVIEW ]
    for name, cx, by in _ed_bottom_buttons():
        if _ed_rect_contains((cx - 42, by, 84, 18), mx, my):
            _ed_press(name)
            if name == "back":
                play_snd(SND_MENU)
                gSt = ST_MENU
            elif name == "clear":
                ed_clear_frame()
                play_snd(SND_MENU)
            elif name == "save":
                editor_save()
            elif name == "gallery":
                gal_open()
            else:
                gEdPlay = not gEdPlay
                gEdT = 0.0
                play_snd(SND_MENU)
            return


def _tl_frame(mx):
    """frame index from a timeline x position."""
    tlx = 54
    tsp = 52
    return max(0, min(7, round((mx - tlx) / tsp)))


def _tl_hit(mx, my):
    x0, y0, cw, ch = _ed_pad_rect()
    tly = y0 + ch + 18
    return 34 <= mx <= 438 and (tly - 8) <= my <= (tly + 8)

def render_editor():
    render_bg_sc()
    # title
    title = tr("ed_title") if gEdMode == "character" else "DISEÑA VECINO"
    sc_title(VIEW_W // 2, 10, title, (200, 160, 66), 2)
    draw_text_c(vbuf, VIEW_W - 20, 6, 1, (120, 100, 160), "v99")
    for name, mode, label, active in (("mode_character", "character", "PERS", gEdMode == "character"),
                                      ("mode_neighbor", "neighbor", "VEC", gEdMode == "neighbor")):
        _, y, bw, bh = _ed_mode_rect(mode)
        pressed = _ed_pressed(name)
        fill = (70, 42, 78) if pressed else ((30, 18, 44) if active else (14, 8, 26))
        draw_y = y + 2 if pressed else y
        if pressed:
            vbuf.fill((5, 3, 12), (434, y, bw, bh))
        vbuf.fill(fill, (434, draw_y, bw, bh))
        pygame.draw.rect(vbuf, (255, 245, 160) if pressed else (200, 160, 66), (434, draw_y, bw, bh), 1)
        draw_text_c(vbuf, 455, draw_y + 1, 1, (255, 230, 120), label)
    # Name belongs to the design itself and stays below the PERS/VEC switch.
    vbuf.fill((30, 18, 44), (414, 74, 62, 18))
    pygame.draw.rect(vbuf, (200, 160, 66), (414, 74, 62, 18), 1)
    draw_text(vbuf, 418, 78, 1, (255, 230, 120), (gCustName or "NOMBRE")[:8])
    if gEdNameTyping:
        draw_text(vbuf, 418 + min(8, len(gCustName)) * 8, 78, 1, (255, 255, 120), "_")
    # action tabs (the neighbor editor has no direction tabs)
    for a in range(4) if gEdMode == "character" else []:
        cx = 84 + a * 104
        sel = a == gEdAction
        pressed = _ed_pressed("tab%d" % a)
        ty = 28 if pressed else 26
        fill = (70, 42, 78) if pressed else ((30, 18, 44) if sel else (14, 8, 26))
        col = (255, 245, 160) if pressed else ((255, 230, 120) if sel else (200, 160, 66))
        if pressed:
            vbuf.fill((5, 3, 12), (cx - 52, 26, 104, 16))
        vbuf.fill(fill, (cx - 52, ty, 104, 16))
        pygame.draw.rect(vbuf, col, (cx - 52, ty, 104, 16), 1)
        draw_text_c(vbuf, cx, ty + 2, 1, (255, 230, 120) if sel else (205, 198, 220),
                    ED_ACTIONS[a][gLang])
    # layer status (top-left)
    on_txt = ("SI", "ON")[gLang]
    off_txt = ("NO", "OFF")[gLang]
    draw_text(vbuf, 8, 8, 1, (205, 198, 220),
              "C1:%s C2:%s" % (on_txt if gEdL1 else off_txt, on_txt if gEdL2 else off_txt))
    draw_text_c(vbuf, VIEW_W - 8, 8, 1, (205, 198, 220), tr("ed_frame") % (gEdFrame + 1, 8))
    # palette: 16 colors in two columns, leaving the erase control separate.
    for i, color in enumerate(EDIT_PAL):
        col_i, row = i // 8, i % 8
        px, py = 8 + col_i * 20, 46 + row * 12
        vbuf.fill(color, (px, py, 18, 10))
        selected = i == gEdColor and not gEdErase
        pressed = _ed_pressed("color%d" % i)
        border = (255, 245, 160) if pressed else ((255, 230, 120) if selected else (110, 80, 50))
        pygame.draw.rect(vbuf, border, (px, py, 18, 10), 2 if pressed else 1)
    # layer toggles L1 (drawing) / L2 (guide)
    for i, on in ((1, gEdL1), (2, gEdL2)):
        by = 153 + (i - 1) * 15
        pressed = _ed_pressed("l%d" % i)
        draw_by = by + 2 if pressed else by
        if pressed:
            vbuf.fill((5, 3, 12), (3, by, 46, 14))
        vbuf.fill((70, 42, 78) if pressed else ((40, 26, 58) if on else (14, 8, 26)), (3, draw_by, 46, 14))
        col = (255, 245, 160) if pressed else ((255, 230, 120) if on else (110, 80, 50))
        pygame.draw.rect(vbuf, col, (3, draw_by, 46, 14), 1)
        draw_text_c(vbuf, 26, draw_by + 3, 1, (255, 230, 120) if on else (150, 140, 160),
                    "L%d" % i)
    # Eye control: master visibility, both layers follow the eye state.
    eye_pressed = _ed_pressed("eye")
    eye_on = gEdL1 and gEdL2
    eye_y = 186 if eye_pressed else 184
    if eye_pressed:
        vbuf.fill((5, 3, 12), (3, 184, 46, 18))
    vbuf.fill((70, 42, 78) if eye_pressed else ((40, 26, 58) if eye_on else (26, 14, 34)), (3, eye_y, 46, 18))
    pygame.draw.rect(vbuf, (255, 245, 160) if eye_pressed else ((255, 230, 120) if eye_on else (140, 80, 90)),
                     (3, eye_y, 46, 18), 1)
    draw_text_c(vbuf, 26, eye_y + 4, 1, (255, 230, 120) if eye_on else (150, 140, 160), "O")
    # ---- drawing pad ----
    x0, y0, cw, ch = _ed_pad_rect()
    z = _ed_zoom()
    px0, py0, pcw, pch = _ed_preview_rect()
    draw_text_c(vbuf, x0 + cw // 2, y0 - 10, 1, (200, 160, 66), "DIBUJO")
    draw_text_c(vbuf, px0 + pcw // 2, py0 - 10, 1, (200, 160, 66), "PREVIEW")
    # frame arrows (sides of the pad)
    yc = y0 + ch // 2
    for dx in (-1, 1):
        ax = (x0 - 24) if dx < 0 else (x0 + cw - 4)
        arrow_name = "arrow_left" if dx < 0 else "arrow_right"
        pressed = _ed_pressed(arrow_name)
        shift = 2 if pressed else 0
        col = (255, 245, 160) if pressed else ((255, 230, 120) if gEdFlashT > 0 else (200, 160, 66))
        pygame.draw.line(vbuf, col, (ax + 8 + shift, yc - 10 + shift), (ax + 8 + shift, yc + 10 + shift), 3 if pressed else 2)
        pygame.draw.line(vbuf, col, (ax + 8 + shift, yc - 10 + shift), (ax + (2 if dx < 0 else 14) + shift, yc + shift), 3 if pressed else 2)
        pygame.draw.line(vbuf, col, (ax + 8 + shift, yc + 10 + shift), (ax + (2 if dx < 0 else 14) + shift, yc + shift), 3 if pressed else 2)
    # pad background + border
    vbuf.fill((16, 10, 30), (x0, y0, cw, ch))
    pygame.draw.rect(vbuf, (200, 160, 66), (x0 - 1, y0 - 1, cw + 2, ch + 2), 1)
    # layer 2: the selected gallery/template cell, aligned with the pad
    if gEdL2 and not gEdPlay:
        try:
            g = _editor_ghost()
            if g is not None:
                vbuf.blit(g, (x0, y0))
        except Exception:
            pass
    # layer 1: your drawing + grid
    if gEdL1:
        idx = gEdAction * 8 + gEdFrame
        try:
            vbuf.blit(pygame.transform.scale(gEdFrames[idx], (cw, ch)), (x0, y0))
        except Exception:
            pass
        for px in range(gEdFW + 1):
            pygame.draw.line(vbuf, (70, 58, 92), (x0 + px * z, y0), (x0 + px * z, y0 + ch))
        for py in range(gEdFH + 1):
            gy = y0 + int(py * ch / gEdFH)
            pygame.draw.line(vbuf, (70, 58, 92), (x0, gy), (x0 + cw, gy))
    # Preview is a second, non-editable box. Its animation never changes the
    # drawing frame or the ghost layer.
    vbuf.fill((16, 10, 30), (px0, py0, pcw, pch))
    pygame.draw.rect(vbuf, (200, 160, 66), (px0 - 1, py0 - 1, pcw + 2, pch + 2), 1)
    try:
        preview_idx = gEdAction * 8 + (int(gEdT * 8) % 8 if gEdPlay else gEdFrame)
        vbuf.blit(pygame.transform.scale(gEdFrames[preview_idx], (pcw, pch)), (px0, py0))
    except Exception:
        pass

    # ---- timeline (line + dots + playhead) ----
    x0, y0, cw, ch = _ed_pad_rect()
    tlx, tsp, tly = 54, 52, y0 + ch + 18
    pygame.draw.line(vbuf, (60, 50, 80), (tlx - 20, tly), (tlx + 7 * tsp + 20, tly), 2)
    for f in range(8):
        pygame.draw.circle(vbuf, (60, 50, 80), (tlx + f * tsp, tly), 3)
    tx = tlx + gEdFrame * tsp
    pygame.draw.circle(vbuf, (200, 160, 66), (tx, tly), 7, 2)
    pygame.draw.circle(vbuf, (255, 230, 120), (tx, tly), 2)
    draw_text_c(vbuf, tx, tly + 10, 1, (255, 230, 120), "%d/8" % (gEdFrame + 1))
    # ---- bottom buttons [VOLVER CLEAR GUARDAR GALERIA PREVIEW] ----
    labels = {"back": tr("ed_back"), "clear": tr("ed_clear"), "save": tr("ed_save"),
              "gallery": tr("ed_gallery"), "preview": tr("ed_preview")}
    for name, cx, by in _ed_bottom_buttons():
        w = 84
        pressed = _ed_pressed(name)
        draw_by = by + 2 if pressed else by
        if pressed:
            vbuf.fill((5, 3, 12), (cx - w // 2, by, w, 18))
        fill = (70, 42, 78) if pressed else ((30, 18, 44) if name in ("back", "clear") else (14, 8, 26))
        vbuf.fill(fill, (cx - w // 2, draw_by, w, 18))
        pygame.draw.rect(vbuf, (255, 245, 160) if pressed else (200, 160, 66), (cx - w // 2, draw_by, w, 18), 1)
        draw_text_c(vbuf, cx, draw_by + 2, 1, (255, 230, 120), labels[name])
    if gEdFlashT > 0:
        if gUpState == 1:
            m = tr("ed_sending")
        elif gUpState == 2:
            m = tr("ed_saved_g")
        elif gUpState == 3:
            m = tr("ed_local")
        else:
            m = tr("ed_incomplete")
        draw_text_c(vbuf, VIEW_W // 2, 118, 2, (120, 255, 160), m)


def directory_poll():
    """Merge public relay lobbies into the native browser list."""
    global gLobCount
    try:
        import json as _json
        import urllib.request
        data = urllib.request.urlopen(
            "http://zombicito.duckdns.org:7070/api/lobbies", timeout=0.8).read()
        rows = _json.loads(data.decode("utf-8"))
        for row in rows:
            host = str(row.get("host") or "")
            name = str(row.get("name") or host or "LOBBY")
            if int(row.get("filled", 0)) <= 0 and not int(row.get("started", 0)):
                continue
            found = -1
            for i in range(gLobCount):
                if gLobList[i].host == host and gLobList[i].name == name:
                    found = i
                    break
            if found < 0:
                if gLobCount >= MAX_LOBBIES:
                    continue
                found = gLobCount
                gLobCount += 1
            e = gLobList[found]
            e.host, e.addr, e.port = host, host, NET_PORT
            e.name = name[:24]
            e.region = int(row.get("region", 1))
            e.filled = int(row.get("filled", 0))
            e.slots = int(row.get("slots", MAX_PLAYERS))
            e.started = int(row.get("started", 0))
            e.world = int(row.get("world", 0))
            e.bots = int(row.get("bots", 0))
            e.free = int(row.get("free", 0))
            e.details = list(row.get("details", []))
            e.ping = -1
            e.lastSeen = gNetTime
    except Exception:
        pass


def web_host_announce():
    """Publish a browser lobby through the same-origin directory relay."""
    global gWebHostId, gWebLobbyId
    try:
        from js import window
        gWebLobbyId = "web-" + design_owner_id()
        window._announceLobby({
            "name": (gLobName.strip() or "LOBBY")[:15],
            "host": gWebLobbyId,
            "owner": gWebLobbyId,
            "region": 1,
            "filled": sum(1 for k in gKinds if k),
            "slots": MAX_PLAYERS,
            "world": gLevelSel,
            "started": gNetStarted,
            "kinds": list(gKinds), "bots": list(gBotEnabled),
            "teams": list(gLobTeam), "chars": list(gLobChar),
            "ready": list(gLobReady), "clients": dict(gWebClients),
        })
    except Exception:
        pass


def web_host_snapshot():
    """Publish the authoritative match state for web clients."""
    if not IS_WEB or not gWebLobbyId:
        return
    try:
        import base64 as _b64
        from js import window
        data = build_snapshot_data()
        window._webLobbyAction(gWebLobbyId, "snap", 0, 0,
                               _b64.b64encode(data).decode("ascii"))
    except Exception:
        pass


def web_send_input():
    if not IS_WEB or not gWebLobbyId:
        return
    try:
        from js import window
        ix, iy, fire = read_local_input()
        window._webLobbyAction(gWebLobbyId, "input", pack_buttons(ix, iy, fire), 0, "")
    except Exception:
        pass


def web_apply_inputs(state):
    """Host side: apply remote inputs arriving through the relay."""
    if gSock is not None:
        return
    try:
        inputs = getattr(state, "inputs", None)
        if inputs is None:
            return
        clients = getattr(state, "clients", None)
        if clients is None:
            return
        for client in inputs:
            slot = int(clients[client])
            if 0 <= slot < MAX_PLAYERS:
                gP[slot].netButtons = int(inputs[client])
                gP[slot].netLastT = gNetTime
    except Exception:
        pass


def web_lobby_sync():
    """Synchronize a browser lobby through the HTTP directory relay."""
    global gWebSyncT, gMySlot, gLobReady, gKinds, gBotEnabled, gLobTeam, gLobChar, gChatLines, gSt, gNetStarted
    if not IS_WEB or not gWebLobbyId:
        return
    try:
        import base64 as _b64
        from js import window
        window._pollWebLobby(gWebLobbyId)
        state = window._webLobbyState
        if state is None:
            return
        kinds = state.kinds
        bots = state.bots
        teams = state.teams
        chars = state.chars
        ready = state.ready
        for i in range(MAX_PLAYERS):
            gKinds[i] = int(kinds[i])
            gBotEnabled[i] = int(bots[i])
            gLobTeam[i] = int(teams[i])
            gLobChar[i] = int(chars[i])
            gLobReady[i] = int(ready[i])
        slot = int(window._webLobbySlot)
        if slot >= 0:
            gMySlot = slot
            gLocalSlot = slot
        clients = getattr(state, "clients", None)
        chat = getattr(state, "chat", None)
        if chat is not None:
            gChatLines[:] = []
            for item in chat:
                client = str(getattr(item, "client", ""))
                if client == gWebLobbyId:
                    chat_slot = 0
                else:
                    try:
                        chat_slot = int(clients[client]) if clients is not None else 90
                    except Exception:
                        chat_slot = 90
                chat_add(chat_slot, str(getattr(item, "text", "")))
        started = int(getattr(state, "started", 0) or 0)
        snap = str(getattr(state, "snap", "") or "")
        world = int(getattr(state, "world", 0) or 0)
        if world != gLevelSel and not gHosting:
            gLevelSel = world % WORLD_COUNT
            texLevel, gWalk = world_texture()
        if gHosting:
            web_apply_inputs(state)
            return
        if started and gSt == ST_LOBBY:
            client_setup()
            gSt = ST_PLAY
        if snap and gSt == ST_PLAY:
            try:
                client_apply_snapshot(_b64.b64decode(snap))
            except Exception:
                pass
    except Exception:
        pass


def render_gallery():
    render_bg_sc()
    gallery_title = "MIS PERSONAJES" if gGalMine else ("VECINOS" if gGalMode == "neighbors" else (tr("menu_characters") if gGalReturnState == ST_CHARACTERS else tr("gal_title")))
    sc_title(VIEW_W // 2, 12, gallery_title, (200, 160, 66), 2)
    n = len(gDesigns)
    if gGalState == "loading":
        draw_text_c(vbuf, VIEW_W // 2, 120, 1, (205, 198, 220), tr("gal_loading"))
    elif gGalState == "error" and not gDesigns:
        draw_text_c(vbuf, VIEW_W // 2, 120, 1, (255, 140, 90), tr("gal_noconn"))
    else:
        draw_text(vbuf, 300, 20, 1, (205, 198, 220), tr("gal_count") % n)
        rows = min(n, 12)
        for i in range(rows):
            y = 44 + i * 12
            sel = i == gGalSel
            if sel:
                vbuf.fill((30, 18, 44), (20, y - 2, 290, 11))
                pygame.draw.rect(vbuf, (200, 160, 66), (20, y - 2, 290, 11), 1)
            g = gDesigns[i]
            label = g["name"] if g.get("local") else "SKIN " + g["name"]
            draw_text(vbuf, 24, y, 1, (255, 230, 120) if sel else (200, 190, 210),
                      label[:22])
            if "date" in g:
                draw_text(vbuf, 196, y, 1, (150, 140, 160), g["date"])
    sc_panel(vbuf, (326, 44, 142, 144), (14, 8, 26), _gold, 8)
    if gGalMine:
        vbuf.fill((30, 18, 44), (326, 174, 142, 16))
        pygame.draw.rect(vbuf, _gold, (326, 174, 142, 16), 1)
        draw_text(vbuf, 332, 177, 1, (255, 230, 120), (gGalRenameInput or "NOMBRE")[:16])
    if gGalDataState == "loading":
        draw_text_c(vbuf, 397, 110, 1, (205, 198, 220), tr("gal_loading"))
    elif gGalDataState == "error":
        draw_text_c(vbuf, 397, 110, 1, (255, 140, 90), tr("gal_noconn"))
    elif gDesignData and gDesignData[0] != "err":
        surf = gDesignData[1]
        rects = _sheet_rects(surf)
        if rects:
            r = rects[0]                            # single static frame (stand pose)
            fw, fh = r[2], r[3]
            sc = min(3.0, 130.0 / max(1, fw), 100.0 / max(1, fh))
            tw, th = max(1, int(fw * sc)), max(1, int(fh * sc))
            try:
                vbuf.blit(pygame.transform.scale(surf.subsurface(pygame.Rect(*r)),
                                                 (tw, th)),
                          (397 - tw // 2, 56))
            except Exception:
                pass
            nm = gDesigns[gGalSel]["name"] if 0 <= gGalSel < len(gDesigns) else ""
            draw_text_c(vbuf, 397, 56 + th + 8, 1, (255, 230, 120), nm)
        else:
            draw_text_c(vbuf, 397, 110, 1, (255, 140, 90), tr("gal_noconn"))
    buttons = [(65, 0), (175, 1), (285, 2)]
    if gGalReturnState == ST_CHARACTERS:
        buttons.append((415, 3))
    for cx, b in buttons:
        vbuf.fill((14, 8, 26), (cx - 50, 196, 100, 16))
        pygame.draw.rect(vbuf, (200, 160, 66), (cx - 50, 196, 100, 16), 1)
        current_public = bool(gGalMine and 0 <= gGalSel < len(gDesigns) and gDesigns[gGalSel].get("public"))
        labels = [tr("ed_back"), ("RENOMBRAR" if current_public else "PUBLICAR") if gGalMine else tr("gal_use"),
                  tr("gal_refresh"), "PUBLICOS" if gGalMine else "MIS PERSONAJES"]
        draw_text_c(vbuf, cx, 198, 1, (255, 230, 120), labels[b])
    if gGalFlashT > 0:
        draw_text_c(vbuf, VIEW_W // 2, 182, 1, (120, 255, 160), tr("gal_used"))


def render_profile():
    render_bg_sc()
    sc_title(VIEW_W // 2, 18, tr("profile_title"), (200, 160, 66), 3)
    r = profile_rank()
    rc = RANK_COLORS[r]
    total = gWins + gLosses
    rate = int(100 * gWins / max(1, total))
    sc_panel(vbuf, (70, 52, 340, 160), (14, 8, 26), _gold, 10)
    # name
    draw_text(vbuf, 90, 60, 1, (200, 190, 210), tr("profile_name"))
    nm = custom_display_name()
    draw_text(vbuf, 160, 60, 1, (255, 230, 120), nm)
    # rank box
    sc_panel(vbuf, (90, 78, 300, 36), (30, 18, 44), rc, 6)
    draw_text_c(vbuf, 240, 85, 2, rc, profile_rank_name())
    # rank progress pips
    for i in range(6):
        on = i <= r
        vbuf.fill(rc if on else (40, 32, 56), (98 + i * 52, 120, 44, 6))
        vbuf.fill((255, 255, 255) if on else (24, 18, 36), (98 + i * 52, 120, 44, 2))
    # stats grid
    draw_text(vbuf, 90, 134, 1, (110, 235, 70), tr("profile_wins") % gWins)
    draw_text(vbuf, 250, 134, 1, (235, 70, 70), tr("profile_losses") % gLosses)
    draw_text(vbuf, 90, 156, 1, (170, 160, 185), tr("profile_total") % total)
    draw_text(vbuf, 250, 156, 1, (170, 160, 185), tr("profile_rate") % rate)
    # win rate bar
    vbuf.fill((24, 16, 36), (90, 176, 300, 8))
    if rate > 0:
        vbuf.fill(rc, (90, 176, int(300 * rate / 100.0), 8))
        vbuf.fill((255, 255, 255), (90, 176, int(300 * rate / 100.0), 2))
    pygame.draw.rect(vbuf, (90, 70, 40), (90, 176, 300, 8), 1)


def render_weapons():
    render_bg_sc()
    sc_title(VIEW_W // 2, 14, tr("menu_weapons"), (200, 160, 66), 3)
    vbuf.fill((14, 8, 26), (8, 8, 80, 18))
    pygame.draw.rect(vbuf, (200, 160, 66), (8, 8, 80, 18), 1)
    draw_text_c(vbuf, 48, 10, 1, (255, 230, 120), tr("opts_back"))
    sc_panel(vbuf, (18, 48, 270, 188), (14, 8, 26), _gold, 10)
    for i, w in enumerate(ARMS):
        y = 56 + i * 19
        selected = i == gWpnMenuSel
        if selected:
            vbuf.fill((30, 18, 44), (28, y - 2, 250, 16))
            pygame.draw.rect(vbuf, _gold, (28, y - 2, 250, 16), 1)
        col = (255, 230, 120) if selected else (205, 198, 220)
        draw_text(vbuf, 34, y, 1, col, "%d. %s" % (i + 1, w[0]))
        draw_text(vbuf, 132, y, 1, (170, 160, 185),
                  "CAD %d  BAL %d  VEL %d" % (int(round(1.0 / w[1])), w[5], int(w[4])))
    w = ARMS[gWpnMenuSel]
    sc_panel(vbuf, (306, 48, 156, 188), (14, 8, 26), WORLD_TINT[gLevelSel % WORLD_COUNT], 10)
    draw_text_c(vbuf, 384, 60, 2, (255, 230, 120), w[0])
    # actual pixel-art weapon portrait
    vbuf.fill((24, 16, 34), (326, 82, 116, 76))
    pygame.draw.rect(vbuf, (200, 160, 66), (326, 82, 116, 76), 1)
    weapon_icon = pygame.transform.scale(texWeapons[gWpnMenuSel], (96, 64))
    vbuf.blit(weapon_icon, (336, 88))
    draw_text_c(vbuf, 384, 174, 1, (205, 198, 220), "CADENCIA %d" % int(round(1.0 / w[1])))
    draw_text_c(vbuf, 384, 188, 1, (205, 198, 220), "MUNICION %d" % w[5])
    draw_text_c(vbuf, 384, 202, 1, (205, 198, 220), "VELOCIDAD %d" % int(w[4]))


def render_endcard(win):
    render_bg_sc()
    sc_panel(vbuf, (VIEW_W // 2 - 180, 26, 360, 200), (14, 8, 26), _gold, 12)
    if gMode == MODE_TEAMS:
        order = sorted(range(gTeamCount), key=lambda t: (-gTeam[t].rescues, -gTeam[t].score))
        sc_title(VIEW_W // 2, 40, tr("end_wins") % TEAMNAME[order[0]], TEAMCOL[order[0]], 2)
        for i in range(gTeamCount):
            t = order[i]
            y = 92 + i * 24
            k = min(1.0, max(0.0, gMenuT * 2.0 - i * 0.14))
            ease = 1.0 - (1.0 - k) ** 3
            draw_text_cs(vbuf, VIEW_W // 2 + 1, y + 1, 1, (10, 14, 10), tr("end_rescues") % (i + 1, TEAMNAME[t], gTeam[t].rescues, gTeam[t].score))
            draw_text_c(vbuf, VIEW_W // 2, y, 1, TEAMCOL[t],
                        tr("end_rescues") % (i + 1, TEAMNAME[t], gTeam[t].rescues, gTeam[t].score))
            if ease > 0.5:
                vbuf.fill((200, 160, 66), (VIEW_W // 2 - int(90 * ease), y + 14, int(180 * ease), 1))
        draw_text_c(vbuf, VIEW_W // 2, 196, 1, (200, 190, 210), tr("end_eaten") % gEaten)
    elif win:
        sc_title(VIEW_W // 2, 52, tr("end_clear"), (110, 235, 70), 3)
        draw_text_c(vbuf, VIEW_W // 2, 110, 2, (255, 255, 255), tr("end_saved") % (gRescued, gNumVictims))
        draw_text_c(vbuf, VIEW_W // 2, 140, 2, (255, 230, 120), tr("end_score") % gP[0].score)
    else:
        sc_title(VIEW_W // 2, 52, tr("end_over"), (235, 60, 70), 3)
        draw_text_c(vbuf, VIEW_W // 2, 110, 2, (255, 255, 255), tr("end_zombies"))


def rerender_current():
    if gSt == ST_MENU:
        render_menu()
    elif gSt == ST_LOBBY:
        render_lobby()
    elif gSt == ST_OPTIONS:
        render_options()
    elif gSt == ST_WORLDS:
        render_worlds()
    elif gSt == ST_WORLD_EDITOR:
        render_world_editor()
    elif gSt == ST_CREATOR:
        render_creator()
    elif gSt == ST_WIN:
        render_endcard(True)
    elif gSt == ST_GAMEOVER:
        render_endcard(False)
    elif gSt == ST_PROFILE:
        render_profile()
    elif gSt == ST_WEAPONS:
        render_weapons()
    elif gSt == ST_EDITOR:
        render_editor()
    elif gSt == ST_GALLERY:
        render_gallery()
    else:
        render_game()

# ---------------- main ----------------
def save_frame_png(file):
    pygame.image.save(vbuf, file)
    print("frame saved: %s" % file)


def setup_window(hidden):
    global vbuf
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy" if hidden else "windows")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy" if hidden else "directsound")
    pygame.init()
    flags = pygame.HIDDEN if hidden else 0
    win = pygame.display.set_mode((VIEW_W * WIN_SCALE, VIEW_H * WIN_SCALE), flags)
    pygame.display.set_caption("Zombicito - Python Edition")
    vbuf = pygame.Surface((VIEW_W, VIEW_H))
    global gPad
    if not hidden:
        pygame.joystick.init()
        for i in range(pygame.joystick.get_count()):
            try:
                j = pygame.joystick.Joystick(i)
                j.init()
                gPad = j
                break
            except Exception:
                pass
    return win


def main():
    global gSt, gMode, gTeamCount, gMySlot, gLocalSlot, gServerMode, gAutoConnect, gLobStage, gLobRow
    global gLobbyGot, gJoinReqT, gJoinStartT, gNetTime, gMenuT, gZomWalkT, gFullscreen, gSmooth
    global gNetStarted, gNetPhase, gLobSelRow, gLobSel, gLobCount, gLobbyBcastT, gBeaconT
    global gServerStartT, gServerRestartT, gOptIdx, gVolume, pauseIdx, gSndSeq, gLobIp, gWin
    global gLobName, gLocalHost, gAutoFrames, gAutoIp, gAutoTeams, gShotFile, gRunning, gFrameNo, gSnapT, gInputSeq
    shot_mode = 0
    shot_state = ""
    gShotFile = ""
    shot_frames = 0
    auto = 0
    gAutoFrames = 0
    gAutoIp = "127.0.0.1"
    gAutoTeams = 4

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--shot" and i + 2 < len(args):
            shot_mode = 1
            shot_state = args[i + 1]
            gShotFile = args[i + 2]
            if i + 3 < len(args):
                shot_frames = int(args[i + 3])
        elif a == "--host-test" and i + 2 < len(args):
            auto = 1
            gAutoFrames = int(args[i + 1])
            gShotFile = args[i + 2]
            if i + 3 < len(args):
                gAutoTeams = 2 if int(args[i + 3]) == 2 else 4
        elif a == "--join-test" and i + 3 < len(args):
            auto = 2
            gAutoFrames = int(args[i + 1])
            gShotFile = args[i + 2]
            gAutoIp = args[i + 3]
        elif a == "--browse-test" and i + 2 < len(args):
            auto = 3
            gAutoFrames = int(args[i + 1])
            gShotFile = args[i + 2]
        elif a == "--server":
            gServerMode = 1
        elif a == "--no-autoconnect":
            pass
        i += 1

    gServerMode = 1 if os.environ.get("ZAMN_SERVER") else gServerMode
    gAutoConnect = 0
    hidden = shot_mode or auto or gServerMode
    load_lang()

    gWin = setup_window(hidden)
    load_assets()
    if not hidden and not gServerMode:
        init_audio()

    # legacy --shot for static screens + sim
    if shot_mode:
        global gLobStage0
        if shot_state == "options":
            gSt = ST_OPTIONS
        elif shot_state == "lobby":
            gSt = ST_LOBBY
            host_open_local()
            gLobStage = 1
        elif shot_state == "lobbycust":
            gSt = ST_LOBBY
            host_open_local()
            gLobChar[0] = 8
            gLobStage = 1
        elif shot_state == "creator":
            gSt = ST_CREATOR
            gCreatorIdx = 2
            gCust[:] = [0, 3, 5, 4, 2]
        elif shot_state == "profile":
            gSt = ST_PROFILE
            gWins = 14
            gLosses = 3
            gCustName = "JUAN"
        elif shot_state == "customplay":
            gSt = ST_PLAY
            gLocalSlot = 0
            game_reset(MODE_SP, 2)
        elif shot_state == "play":
            gSt = ST_PLAY
            gLocalSlot = 0
            game_reset(MODE_SP, 0)
        elif shot_state == "playteams":
            gSt = ST_PLAY
            gTeamCount = 4
            for k in range(MAX_PLAYERS):
                gKinds[k] = 0
            gKinds[0] = 1
            gMySlot = 0
            gLocalSlot = 0
            game_reset(MODE_TEAMS, 0)
        elif shot_state == "endcard":
            gSt = ST_WIN
            gMode = MODE_TEAMS
            gTeamCount = 4
            gRescued = 0
            gEaten = 3
            for t in range(gTeamCount):
                gTeam[t].rescues = 4 - t
                gTeam[t].score = 500 - t * 100
        elif shot_state == "pause":
            gSt = ST_PLAY
            gLocalSlot = 0
            game_reset(MODE_SP, 0)
            gSt = ST_PAUSE
            pauseIdx = 1
        gMenuT = 1.2
        for f in range(shot_frames):
            if gSt == ST_PLAY:
                update_game(1.0 / 60.0)
            gMenuT += 1.0 / 60.0
            gZomWalkT += 1.0 / 60.0
        rerender_current()
        if gSt == ST_PAUSE:
            render_pause()
        save_frame_png(gShotFile)
        return 0

    # dedicated server
    if gServerMode:
        gTeamCount = 4
        gLobName = "PUBLIC ZOMBICITO"
        if not net_host_open():
            print("SERVER: FAILED to bind port %d" % NET_PORT)
            return 1
        gKinds[0] = 0
        gLobReady[0] = 1
        gMySlot = -1
        gLocalSlot = -1
        gSt = ST_LOBBY
        gLobStage = 1
        print("SERVER: listening on UDP port %d (%s)" % (NET_PORT, DEFAULT_SERVER))
    elif gAutoConnect:
        gAutoConnect = 0
        if net_client_open(gLobIp):
            gSt = ST_LOBBY
            gLobStage = 2
            gLobbyGot = 0
            gJoinReqT = 0.0
            gJoinStartT = gNetTime
            gMySlot = -1
        else:
            gSt = ST_MENU

    clock = pygame.time.Clock()
    gFrameNo = 0
    gRunning = True
    gSnapT = 0.0
    gInputSeq = 0
    while gRunning:
        frame(clock, auto)
    net_close()
    pygame.quit()
    return 0


gFrameNo = 0
gRunning = True
gSnapT = 0.0
gInputSeq = 0
gWin = None
_web_clock = None
gAutoFrames = 0
gAutoIp = "127.0.0.1"
gAutoTeams = 4
gShotFile = ""


def web_boot():
    global gWin, gSt, _web_clock
    gServerMode = 0
    gAutoConnect = 0
    load_lang()
    gWin = setup_window(False)
    _web_clock = pygame.time.Clock()
    load_assets()
    init_audio()
    gSt = ST_MENU
    gMenuT = 1.2
    return True


def frame(clock=None, auto=0):
    global gFrameNo, gRunning, gSnapT, gInputSeq, gMenuT, gZomWalkT, gNetTime
    global gSt, gMenuIdx, gLobStage, gLobRow, gLobIp, gLobIpTyping, gTeamCount, gLobSelRow
    global gLobTeam, gLobChar, gNetStarted, gMySlot, gLocalSlot, gLobbyGot, gJoinReqT
    global gJoinStartT, gLobSel, gLobCount, gOptIdx, gFullscreen, gSmooth, gVolume
    global pauseIdx, gServerStartT, gServerRestartT, gLobbyBcastT, gBeaconT, gSndSeq, gNetPhase
    global gAutoFrames, gAutoIp, gAutoTeams, gShotFile, gLobName, gLocalHost, gLang
    global gPingT, gPingSeq, gAnnounceT, gDirectoryT, gWebSyncT, gShowFps, gFpsDisp
    global gCustName, gCustNameMine, gCreatorIdx, gCustMine, gEdNameTyping, gGalNameTyping, gGalRenameInput
    global gChatLines, gChatTyping, gChatInput
    global gCreatorPress, gCreatorFlashT
    global gEdFrame, gEdAction, gEdColor, gEdErase, gEdL1, gEdL2, gEdPlay, gEdT, gEdFlashT, gEdGhostIsTemplate, gEdButtonT, gEdPressed
    global gMouseX, gMouseY, gMouseIn, gMouseDown, gWheel, gCursorHidden
    global gMouseErase
    global gDesigns, gGalState, gGalDataState, gGalSel, gDesignData, gGalFlashT, gGalUseReq, gUpState
    global gConsoleOpen, gConsoleInput, gWpnMenuSel, gWpnMenuLock
    if clock is None:
        clock = _web_clock
    dt = min(1.0 / 30.0, clock.tick(60) / 1000.0)
    if auto:
        dt = 1.0 / 60.0
    gMenuT += dt
    gZomWalkT += dt
    gNetTime += dt
    gFrameNo += 1
    if gCreatorFlashT > 0:
        gCreatorFlashT -= dt
    if gEdPlay:
        gEdT += dt
    if gSt == ST_GALLERY:
        gEdT += dt
    if gEdFlashT > 0:
        gEdFlashT -= dt
    if gEdButtonT > 0:
        gEdButtonT -= dt
        if gEdButtonT <= 0:
            gEdPressed = ""
    if gGalFlashT > 0:
        gGalFlashT -= dt
    if IS_WEB and (gSt == ST_EDITOR or gSt == ST_GALLERY):
        try:
            from js import window
            if gGalState == "loading":
                st = window._gGalState
                if st and st != "loading":
                    gGalState = st
                    if st == "done":
                        lst = window._gGalList
                        if isinstance(lst, dict):
                            lst = [lst]
                        gDesigns = _gal_combine(lst)
            if gGalDataState == "loading":
                st = window._gGalDataState
                if st and st != "loading":
                    gGalDataState = st
                    if st == "done" and window._gGalRGB is not None:
                        try:
                            data = base64.b64decode(window._gGalRGB)
                            dim = [int(x) for x in str(window._gGalDim).split("x")]
                            surf = pygame._fromRGBA(bytearray(data), dim[0], dim[1])
                            gDesignData = (window._gGalId, surf, data)
                            gEdRefTex = surf
                            gEdGhostIsTemplate = False
                        except Exception:
                            gGalDataState = "error"
                    elif st == "done":
                        gGalDataState = "loading"
            if gUpState == 1:
                st = window._gUpState
                if st and st != 1:
                    gUpState = st
            if gGalUseReq:
                gGalUseReq = False
                if gGalDataState == "done" and gDesignData and gDesignData[0] != "err":
                    gal_apply()
        except Exception:
            pass
    if dt > 0.0001 and not auto:
        gFpsDisp = gFpsDisp * 0.9 + 0.1 * (1.0 / dt)
    update_ambient()

    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            gRunning = False
        if ev.type == pygame.MOUSEMOTION:
            gMouseX, gMouseY = ev.pos
            gMouseIn = True
            if gSt == ST_MENU:
                i = hover_row(82, 21, 8, 110, 370)
                if i >= 0 and i != gMenuIdx:
                    gMenuIdx = i
            elif gSt == ST_WEAPONS and not gWpnMenuLock:
                mx, my = mouse_vbuf()
                for i in range(len(ARMS)):
                    y = 56 + i * 19
                    if 28 <= mx <= 278 and y - 2 <= my <= y + 14:
                        gWpnMenuSel = i
                        break
            elif gSt == ST_EDITOR and gMouseDown:
                mx, my = mouse_vbuf()
                if _tl_hit(mx, my):
                    f = _tl_frame(mx)
                    if f != gEdFrame:
                        gEdFrame = f
                        play_snd(SND_MENU)
                else:
                    ed_paint(mx, my, gMouseErase)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 3:
                gMouseDown = True
                gMouseErase = True
                mx, my = mouse_event_vbuf(ev.pos)
                if gSt == ST_EDITOR:
                    ed_paint(mx, my, True)
            if ev.button == 1:
                gMouseDown = True
                gMouseErase = False
                mx, my = mouse_event_vbuf(ev.pos)
                if gSt == ST_MENU:
                    if 390 <= mx <= 472 and 244 <= my <= 266:
                        account_logout()
                        continue
                    i = hover_row(82, 21, 8, 110, 370)
                    if i >= 0:
                        gMenuIdx = i
                        menu_enter()
                elif gSt == ST_OPTIONS:
                    options_click(mx, my)
                elif gSt == ST_WORLDS:
                    worlds_click(mx, my)
                elif gSt == ST_WORLD_EDITOR:
                    world_editor_click(mx, my)
                elif gSt == ST_LOBBY:
                    lobby_click(mx, my)
                elif gSt == ST_CREATOR:
                    creator_click(mx, my)
                    i = hover_row(78, 24, 7, 210, 470)
                    if 1 <= i <= 5:
                        gCreatorPress = (i, 0 if mx < 316 else (1 if mx > 436 else -1))
                    else:
                        gCreatorPress = (-1, -1)
                elif gSt == ST_EDITOR:
                    editor_click(mx, my)
                elif gSt == ST_GALLERY:
                    gal_click(mx, my)
                elif gSt == ST_WEAPONS:
                    weapons_click(mx, my)
                elif gSt == ST_PAUSE:
                    i = hover_row(106, 26, 2, 110, 370)
                    if i >= 0:
                        pauseIdx = i
                        play_snd(SND_CONFIRM)
                        if pauseIdx == 0:
                            gSt = ST_PLAY
                        else:
                            gSt = ST_MENU
                elif gSt in (ST_WIN, ST_GAMEOVER):
                    if my > 220:
                        play_snd(SND_CONFIRM)
                        net_close()
                        gSt = ST_MENU
                elif gSt == ST_PROFILE:
                    play_snd(SND_CONFIRM)
                    gSt = ST_MENU
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button in (1, 3):
                gMouseDown = False
                gMouseErase = False
                gCreatorPress = (-1, -1)
        elif ev.type == pygame.MOUSEWHEEL:
            mx, my = mouse_vbuf()
            if gSt == ST_EDITOR and _ed_rect_contains(_ed_pad_rect(), mx, my):
                editor_brush_wheel(ev.y)
            elif gSt == ST_OPTIONS and 130 <= mx <= 350 and abs(my - 94) <= 9:
                gVolume = max(0, min(10, gVolume + (1 if ev.y > 0 else -1)))
                play_snd(SND_CONFIRM)
            else:
                gWheel += ev.y
        if ev.type != pygame.KEYDOWN or auto:
            continue
        kc = ev.key
        if kc == 124:
            gConsoleOpen = not gConsoleOpen
            if not gConsoleOpen:
                gConsoleInput = ""
            continue
        if gConsoleOpen:
            if kc == pygame.K_RETURN:
                execute_console_command(gConsoleInput)
            elif kc == pygame.K_BACKSPACE:
                gConsoleInput = gConsoleInput[:-1]
            elif kc == pygame.K_SPACE and len(gConsoleInput) < 32:
                gConsoleInput += " "
            elif kc == pygame.K_MINUS and len(gConsoleInput) < 32:
                gConsoleInput += "-"
            elif 32 <= kc < 127 and len(gConsoleInput) < 32:
                gConsoleInput += chr(kc)
            continue
        if gSt == ST_MENU:
            if kc in (pygame.K_UP, pygame.K_w):
                gMenuIdx = (gMenuIdx + 7) % 8
                play_snd(SND_MENU)
            if kc in (pygame.K_DOWN, pygame.K_s):
                gMenuIdx = (gMenuIdx + 1) % 8
                play_snd(SND_MENU)
            if kc in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                menu_enter()
            if kc == pygame.K_ESCAPE:
                gRunning = False
        elif gSt == ST_CREATOR:
            if gCreatorIdx == 0:
                ch = None
                if pygame.K_a <= kc <= pygame.K_z and len(gCustName) < 12:
                    ch = chr(kc)
                elif pygame.K_0 <= kc <= pygame.K_9 and len(gCustName) < 12:
                    ch = chr(kc)
                elif kc == pygame.K_SPACE and len(gCustName) < 12:
                    ch = " "
                elif kc == pygame.K_MINUS and len(gCustName) < 12:
                    ch = "-"
                if ch:
                    if ch.isalpha() and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        ch = ch.upper()
                    gCustName += ch
                    play_snd(SND_MENU)
                if kc == pygame.K_BACKSPACE and gCustName:
                    gCustName = gCustName[:-1]
                    play_snd(SND_MENU)
                if kc in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT,
                          pygame.K_RETURN):
                    gCreatorIdx = 1
                    play_snd(SND_MENU)
                if kc == pygame.K_ESCAPE:
                    gCust[:] = list(gCustMine)
                    gCustName = gCustNameMine
                    play_snd(SND_MENU)
                    gSt = ST_MENU
            else:
                if kc in (pygame.K_UP, pygame.K_w):
                    gCreatorIdx = (gCreatorIdx + 6) % 7
                    play_snd(SND_MENU)
                if kc in (pygame.K_DOWN, pygame.K_s):
                    gCreatorIdx = (gCreatorIdx + 1) % 7
                    play_snd(SND_MENU)
                if kc in (pygame.K_LEFT, pygame.K_a) and gCreatorIdx != 0:
                    step_creator(-1)
                    gCreatorFlashT = 0.18
                    play_snd(SND_MENU)
                if kc in (pygame.K_RIGHT, pygame.K_d) and gCreatorIdx != 0:
                    step_creator(1)
                    gCreatorFlashT = 0.18
                    play_snd(SND_MENU)
                if kc == pygame.K_r:
                    random_creator()
                    gCreatorFlashT = 0.24
                    play_snd(SND_MENU)
                if kc in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                    if gCreatorIdx == 6:
                        play_snd(SND_CONFIRM)
                        gCustMine = tuple(gCust)
                        gCustNameMine = gCustName
                        save_lang()
                        gSt = ST_MENU
                    else:
                        gCreatorIdx = (gCreatorIdx + 1) % 7
                        play_snd(SND_MENU)
                if kc == pygame.K_ESCAPE:
                    gCust[:] = list(gCustMine)
                    gCustName = gCustNameMine
                    play_snd(SND_MENU)
                    gSt = ST_MENU
        elif gSt == ST_LOBBY:
            if gLobStage == 4:
                # create lobby: type a name
                L = len(gLobName)
                ch = None
                if pygame.K_0 <= kc <= pygame.K_9 and L < 14:
                    ch = chr(ord("0") + (kc - pygame.K_0))
                elif pygame.K_a <= kc <= pygame.K_z and L < 14:
                    ch = chr(ord("a") + (kc - pygame.K_a))
                    if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                        ch = ch.upper()
                elif kc == pygame.K_SPACE and L < 14:
                    ch = " "
                if ch:
                    gLobName += ch
                    play_snd(SND_MENU)
                if kc == pygame.K_BACKSPACE and L > 0:
                    gLobName = gLobName[:-1]
                    play_snd(SND_MENU)
                if kc in (pygame.K_LEFT, pygame.K_a):
                    gLevelSel = (gLevelSel + WORLD_COUNT - 1) % WORLD_COUNT
                    play_snd(SND_MENU)
                if kc in (pygame.K_RIGHT, pygame.K_d):
                    gLevelSel = (gLevelSel + 1) % WORLD_COUNT
                    play_snd(SND_MENU)
                if kc == pygame.K_RETURN:
                    play_snd(SND_CONFIRM)
                    ok = False
                    if IS_WEB:
                        ok = host_open_local()
                    else:
                        ok = net_host_open()
                    if ok:
                        gLobStage = 1
                        gLobSelRow = 0
                        gLocalSlot = gMySlot
                    else:
                        msg("NO SE PUDO CREAR EL LOBBY")
                if kc == pygame.K_ESCAPE:
                    net_close()
                    gLobStage = 0
                    gSt = ST_MENU
            elif gLobStage in (1, 2):
                if gChatTyping:
                    # chat input consumes every key
                    if kc == pygame.K_ESCAPE:
                        gChatTyping = 0
                        gChatInput = ""
                        play_snd(SND_MENU)
                    elif kc in (pygame.K_RETURN, pygame.K_z):
                        chat_send()
                        gChatTyping = 0
                        play_snd(SND_CONFIRM)
                    else:
                        ch = None
                        if pygame.K_a <= kc <= pygame.K_z:
                            ch = chr(kc)
                        elif pygame.K_0 <= kc <= pygame.K_9:
                            ch = chr(kc)
                        elif kc == pygame.K_SPACE:
                            ch = " "
                        elif kc == pygame.K_MINUS:
                            ch = "-"
                        elif kc in (pygame.K_PERIOD, pygame.K_COMMA):
                            ch = chr(kc)
                        if ch:
                            if ch.isalpha() and pygame.key.get_mods() & pygame.KMOD_SHIFT:
                                ch = ch.upper()
                            if len(gChatInput) < 32:
                                gChatInput += ch
                                play_snd(SND_MENU)
                        if kc == pygame.K_BACKSPACE and gChatInput:
                            gChatInput = gChatInput[:-1]
                            play_snd(SND_MENU)
                    continue
            elif gLobStage == 3 and gLobIpTyping:
                if kc == pygame.K_BACKSPACE:
                    gLobIp = gLobIp[:-1]
                elif kc == pygame.K_RETURN:
                    lobby_connect_ip()
                elif kc == pygame.K_ESCAPE:
                    gLobIpTyping = False
                elif (pygame.K_0 <= kc <= pygame.K_9 or
                      pygame.K_a <= kc <= pygame.K_z or kc in (pygame.K_PERIOD, pygame.K_MINUS)):
                    if len(gLobIp) < 48:
                        gLobIp += chr(kc)
        elif gSt == ST_OPTIONS:
            if kc in (pygame.K_UP, pygame.K_w):
                gOptIdx = (gOptIdx + 4) % 5
                play_snd(SND_MENU)
            if kc in (pygame.K_DOWN, pygame.K_s):
                gOptIdx = (gOptIdx + 1) % 5
                play_snd(SND_MENU)
            if kc in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_a, pygame.K_d, pygame.K_RETURN):
                dirn = -1 if kc in (pygame.K_LEFT, pygame.K_a) else 1
                play_snd(SND_MENU)
                if gOptIdx == 0:
                    gSmooth = not gSmooth
                elif gOptIdx == 1:
                    gVolume = max(0, min(10, gVolume + dirn))
                    play_snd(SND_CONFIRM)
                elif gOptIdx == 2:
                    gLang ^= 1
                    save_lang()
                    play_snd(SND_CONFIRM)
                elif gOptIdx == 3:
                    gShowFps = not gShowFps
                    save_lang()
                    play_snd(SND_CONFIRM)
                elif gOptIdx == 4 and kc == pygame.K_RETURN:
                    gSt = ST_MENU
            if kc == pygame.K_ESCAPE:
                gSt = ST_MENU
        elif gSt == ST_EDITOR:
            if gEdNameTyping:
                if kc == pygame.K_ESCAPE or kc == pygame.K_RETURN:
                    gEdNameTyping = False
                elif kc == pygame.K_BACKSPACE:
                    gCustName = gCustName[:-1]
                else:
                    ch = None
                    if pygame.K_a <= kc <= pygame.K_z:
                        ch = chr(kc)
                    elif pygame.K_0 <= kc <= pygame.K_9:
                        ch = chr(kc)
                    elif kc in (pygame.K_SPACE, pygame.K_MINUS):
                        ch = " " if kc == pygame.K_SPACE else "-"
                    if ch and len(gCustName) < 18:
                        gCustName += ch.upper() if ch.isalpha() and pygame.key.get_mods() & pygame.KMOD_SHIFT else ch
                continue
            if kc in (pygame.K_LEFT, pygame.K_a):
                gEdFrame = (gEdFrame + 7) % 8
                play_snd(SND_MENU)
            if kc in (pygame.K_RIGHT, pygame.K_d):
                gEdFrame = (gEdFrame + 1) % 8
                play_snd(SND_MENU)
            if kc in (pygame.K_UP, pygame.K_w):
                gEdAction = (gEdAction + 3) % 4
                play_snd(SND_MENU)
            if kc == pygame.K_DOWN:
                gEdAction = (gEdAction + 1) % 4
                play_snd(SND_MENU)
            if pygame.K_1 <= kc <= pygame.K_8:
                gEdColor = kc - pygame.K_1
                gEdErase = False
                play_snd(SND_MENU)
            if kc == pygame.K_e:
                gEdErase = not gEdErase
                play_snd(SND_MENU)
            if kc == pygame.K_t:
                gEdL2 = not gEdL2
                play_snd(SND_MENU)
            if kc == pygame.K_p:
                gEdPlay = not gEdPlay
                gEdT = 0.0
                play_snd(SND_MENU)
            if kc == pygame.K_c:
                ed_clear_frame()
                play_snd(SND_MENU)
            if kc == pygame.K_s:
                editor_save()
            if kc == pygame.K_g:
                gal_open()
            if kc == pygame.K_ESCAPE:
                play_snd(SND_MENU)
                gSt = ST_MENU
        elif gSt == ST_GALLERY:
            if gGalNameTyping:
                if kc in (pygame.K_RETURN, pygame.K_ESCAPE):
                    gGalNameTyping = False
                elif kc == pygame.K_BACKSPACE:
                    gGalRenameInput = gGalRenameInput[:-1]
                else:
                    ch = None
                    if pygame.K_a <= kc <= pygame.K_z:
                        ch = chr(kc)
                    elif pygame.K_0 <= kc <= pygame.K_9:
                        ch = chr(kc)
                    elif kc in (pygame.K_SPACE, pygame.K_MINUS):
                        ch = " " if kc == pygame.K_SPACE else "-"
                    if ch and len(gGalRenameInput) < 24:
                        gGalRenameInput += ch.upper() if ch.isalpha() and pygame.key.get_mods() & pygame.KMOD_SHIFT else ch
                continue
            if kc in (pygame.K_UP, pygame.K_w) and gDesigns:
                gal_select((gGalSel - 1) % len(gDesigns))
                play_snd(SND_MENU)
            if kc in (pygame.K_DOWN, pygame.K_s) and gDesigns:
                gal_select((gGalSel + 1) % len(gDesigns))
                play_snd(SND_MENU)
            if kc in (pygame.K_RETURN, pygame.K_z, pygame.K_SPACE):
                play_snd(SND_CONFIRM)
                gal_use_now()
            if kc == pygame.K_r:
                gal_fetch_list()
                play_snd(SND_MENU)
            if kc == pygame.K_ESCAPE:
                play_snd(SND_MENU)
                gSt = ST_EDITOR
        elif gSt == ST_PLAY:
            if pygame.K_1 <= kc <= pygame.K_9:
                slot = kc - pygame.K_1
                me = gP[gLocalSlot] if 0 <= gLocalSlot < gNumPlayers and gP[gLocalSlot].used else None
                if me is not None and getattr(me, "inv", None) and slot < len(me.inv):
                    wpn = me.inv[slot]
                    if wpn < len(ARMS):
                        me.wpn = wpn
                        me.ammo = min(me.ammo, ARMS[wpn][5])
                        play_snd(SND_MENU)
            if kc in (pygame.K_ESCAPE, pygame.K_p):
                if gSock is None:
                    gSt = ST_PAUSE
                    pauseIdx = 0
                    play_snd(SND_MENU)
                else:
                    net_close()
                    gSt = ST_MENU
        elif gSt == ST_PAUSE:
            if kc in (pygame.K_UP, pygame.K_DOWN, pygame.K_w, pygame.K_s):
                pauseIdx ^= 1
                play_snd(SND_MENU)
            if kc in (pygame.K_RETURN, pygame.K_z):
                play_snd(SND_CONFIRM)
                if pauseIdx == 0:
                    gSt = ST_PLAY
                else:
                    gSt = ST_MENU
            if kc == pygame.K_ESCAPE:
                gSt = ST_PLAY
        elif gSt in (ST_WIN, ST_GAMEOVER):
            if kc in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_z):
                net_close()
                gSt = ST_MENU
                play_snd(SND_CONFIRM)
        elif gSt == ST_PROFILE:
            if kc in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_z, pygame.K_SPACE):
                gSt = ST_MENU
                play_snd(SND_CONFIRM)
        elif gSt == ST_WEAPONS:
            if kc in (pygame.K_UP, pygame.K_w):
                gWpnMenuSel = (gWpnMenuSel + len(ARMS) - 1) % len(ARMS)
                play_snd(SND_MENU)
            if kc in (pygame.K_DOWN, pygame.K_s):
                gWpnMenuSel = (gWpnMenuSel + 1) % len(ARMS)
                play_snd(SND_MENU)
            if kc in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_z, pygame.K_SPACE):
                gSt = ST_MENU
                play_snd(SND_CONFIRM)

    # autopilot tests
    if auto == 1:
        if gFrameNo == 30:
            gTeamCount = gAutoTeams
            net_host_open()
            gSt = ST_LOBBY
            gLobStage = 1
        joined = sum(gClientKnown)
        if gSt == ST_LOBBY and gLobStage == 1 and gFrameNo > 120 and (joined or gFrameNo > 1500):
            gNetStarted = 1
            host_broadcast_lobby()
            gMySlot = 0
            gLocalSlot = 0
            game_reset(MODE_TEAMS, 0)
            gSt = ST_PLAY
        if gFrameNo >= gAutoFrames:
            rerender_current()
            save_frame_png(gShotFile)
            net_close()
            gRunning = False
    elif auto == 2:
        if gFrameNo == 30:
            net_client_open(gAutoIp)
            gSt = ST_LOBBY
            gLobStage = 2
            gLobbyGot = 0
        if gFrameNo >= gAutoFrames:
            rerender_current()
            save_frame_png(gShotFile)
            net_close()
            gRunning = False
    elif auto == 3:
        if gFrameNo == 30:
            net_browse_open()
            gSt = ST_LOBBY
            gLobStage = 3
            gLobCount = 0
            gLobSel = 0
        if gFrameNo >= gAutoFrames:
            print("lobbies %d" % gLobCount)
            for i in range(gLobCount):
                e = gLobList[i]
                print("  %s %d/%d %s" % (e.name, e.filled, e.slots, "IN GAME" if e.started else "WAITING"))
            rerender_current()
            save_frame_png(gShotFile)
            net_close()
            gRunning = False

    # network pumps
    if gSock is not None:
        if gHosting:
            host_poll()
            if gSt == ST_LOBBY and gLobStage == 1:
                gLobbyBcastT -= dt
                if gLobbyBcastT <= 0:
                    gLobbyBcastT = 0.2
                    host_broadcast_lobby()
        else:
            client_poll()
            if gSt == ST_LOBBY and gLobStage == 2:
                gJoinReqT -= dt
                if gJoinReqT <= 0:
                    gJoinReqT = 0.5
                    try:
                        gSock.sendto(PACK_JOIN.pack(1), gHostAddr)
                    except OSError:
                        pass
                if gNetStarted:
                    client_setup()
                    gSt = ST_PLAY
                if gLobbyGot and gNetTime - gNetLastRx > 6.0:
                    net_close()
                    gLobStage = 0
                if not gLobbyGot and gNetTime - gJoinStartT > 6.0:
                    net_close()
                    gLobStage = 0
            if gSt == ST_LOBBY and gLobStage == 3:
                lobby_prune()
                if not IS_WEB and gSock is not None:
                    gDirectoryT -= dt
                    if gDirectoryT <= 0:
                        gDirectoryT = 2.0
                        directory_poll()
                    gPingT -= dt
                    if gPingT <= 0:
                        gPingT = 0.8
                        for i in range(gLobCount):
                            e = gLobList[i]
                            if e.pingSeq == 0:
                                e.pingSeq = gPingSeq
                                gPingSeq = (gPingSeq % 250) + 1
                                e.pingSentT = gNetTime
                                try:
                                    gSock.sendto(PACK_PING.pack(7, e.pingSeq), (e.addr, e.port))
                                except OSError:
                                    e.pingSeq = 0
            if gSt == ST_WIN and gNetPhase == 1:
                client_setup()
                gSt = ST_PLAY
    if gHosting:
        if gSock is not None:
            gBeaconT -= dt
            if gBeaconT <= 0:
                gBeaconT = 0.5
                host_send_beacon()
        gAnnounceT -= dt
        if gAnnounceT <= 0:
            gAnnounceT = 3.0
            web_host_announce() if IS_WEB else host_announce()

    # Browsers have no UDP socket, so their lobby directory is polled here.
    if IS_WEB and gSt == ST_LOBBY and gLobStage == 3:
        _web_lobby_ingest()
    if IS_WEB and gSt == ST_LOBBY and gLobStage in (1, 2):
        gWebSyncT -= dt
        if gWebSyncT <= 0:
            gWebSyncT = 0.35
            web_lobby_sync()

    # Web match transport: host publishes snapshots, clients send inputs.
    if IS_WEB and gSt == ST_PLAY:
        if gHosting:
            gSnapT -= dt
            if gSnapT <= 0:
                gSnapT = 0.15
                web_host_snapshot()
        else:
            gWebSyncT -= dt
            if gWebSyncT <= 0:
                gWebSyncT = 0.12
                web_lobby_sync()
                web_send_input()

    # Ready is only a status. The lobby creator launches explicitly.

    if gSt == ST_PLAY:
        if IS_WEB and not gHosting:
            if gNetPhase == 2:
                gSt = ST_WIN
            for f in gFx:
                if f.used:
                    f.t += dt * 0.5
        elif gSock is not None and not gHosting:
            ix, iy, fire = read_local_input()
            gInputSeq = (gInputSeq + 1) & 0xFF
            try:
                gSock.sendto(PACK_INPUT.pack(3, gMySlot, pack_buttons(ix, iy, fire), gInputSeq), gHostAddr)
            except OSError:
                pass
            if gNetTime - gNetLastRx > 5.0:
                net_close()
                gSt = ST_MENU
            if gNetPhase == 2:
                gSt = ST_WIN
            for f in gFx:
                if f.used:
                    f.t += dt * 0.5
        else:
            update_game(dt)
            if gHosting:
                gSnapT -= dt
                if gSnapT <= 0:
                    gSnapT = 1.0 / 30.0
                    host_send_snapshot()
            if gMode == MODE_TEAMS:
                if gRescued + gEaten == gNumVictims:
                    gNetPhase = 2
                    if gHosting:
                        host_send_snapshot()
                    gSt = ST_WIN
                    if gServerMode:
                        gServerRestartT = 8.0
                        print("SERVER: match over - next in 8s")
            else:
                if not gP[0].alive and gP[0].lives <= 0:
                    gSt = ST_GAMEOVER
                if gRescued + gEaten == gNumVictims and gRescued == 0:
                    gSt = ST_GAMEOVER
                if gDoorOpen:
                    dx = gP[0].x - gDoorX
                    dy = gP[0].y - (gDoorY + 30)
                    if gP[0].alive and dx * dx + dy * dy < 18 * 18:
                        gSt = ST_WIN
                        play_snd(SND_RESCUE)
    elif gSt == ST_WIN and gHosting:
        gSnapT -= dt
        if gSnapT <= 0:
            gSnapT = 0.2
            gNetPhase = 2
            host_send_snapshot()
        if gServerMode:
            gServerRestartT -= dt
            if gServerRestartT <= 0:
                game_reset(MODE_TEAMS, 0)
                gNetPhase = 1
                gSt = ST_PLAY
                host_broadcast_lobby()
                print("SERVER: next match")

    if gSt in (ST_WIN, ST_GAMEOVER) and not gServerMode and not gShotFile:
        record_match()

    rerender_current()
    if gSt == ST_PAUSE:
        render_pause()
    render_console_overlay()
    if gShowFps:
        cc = (140, 255, 140) if gFpsDisp >= 55 else ((255, 220, 90) if gFpsDisp >= 40 else (255, 100, 90))
        draw_text_sh(vbuf, VIEW_W - 58, 2, 1, cc, "%d" % gFpsDisp)
    hide = 1 if gSt == ST_PLAY else 0
    if gCursorHidden != hide:
        pygame.mouse.set_visible(not hide)
        gCursorHidden = hide
    gWin.blit(vbuf, (0, 0)) if gWin.get_size() == (VIEW_W, VIEW_H) else \
        gWin.blit(pygame.transform.scale(vbuf, gWin.get_size()), (0, 0))
    pygame.display.flip()


def render_pause():
    ov = pygame.Surface((VIEW_W, VIEW_H), pygame.SRCALPHA)
    ov.fill((0, 0, 0, 170))
    vbuf.blit(ov, (0, 0))
    sc_panel(vbuf, (VIEW_W // 2 - 130, 54, 260, 132), (16, 9, 24), _gold, 10)
    sc_title(VIEW_W // 2, 62, tr("pause_title"), (110, 235, 70), 2)
    h = hover_row(106, 26, 2, 110, 370)
    sc_row(VIEW_W // 2, 106, 180, tr("pause_resume"), 0, pauseIdx == 0 or h == 0, 0.2, 2)
    sc_row(VIEW_W // 2, 132, 180, tr("pause_quit"), 1, pauseIdx == 1 or h == 1, 0.2, 2)
    draw_text_c(vbuf, VIEW_W // 2, 168, 1, (150, 140, 160), tr("pause_hint"))


def client_setup():
    global gMode, gNumPlayers, gNumVictims, gLocalSlot, gEndRecorded
    gEndRecorded = 0
    for z in gZ:
        z.used = 0
    for b in gB:
        b.used = 0
    for f in gFx:
        f.used = 0
    for p in gP:
        p.used = 0
        p.alive = 0
    for t in gTeam:
        t.rescues = 0
        t.score = 0
    gMode = MODE_TEAMS
    gNumPlayers = gTeamCount * 2
    gNumVictims = MAX_VICTIMS
    setup_victims_medkits()
    gLocalSlot = gMySlot
    global gMsg, gMsgT
    gMsg = ""
    gMsgT = 0.0


if __name__ == "__main__":
    sys.exit(main())
