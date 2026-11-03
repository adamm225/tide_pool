#!/usr/bin/env python3
"""
Tide Pool
=========
A tide-driven action platformer. You are a hermit crab in a sunlit rock pool.

The hook: the water level rises and falls on a fixed rhythm, and that is what
carries you upward. You can hop (hold to charge), you can punch with your claw,
but you cannot climb. Read the tide, commit at the right moment.

    Move / swim ....... Arrows or WASD, all eight directions.
                        In water, up and down swim; diagonals work.
                        On rock, hold Down to grip so the tide can't lift you.
                        The crab's pose follows the BUTTON you hold, not the
                        direction it happens to be drifting.
    Charge hop ........ hold Space, release to jump
                        (works on rock AND at the water surface)
    Claw punch ........ B  (or X / Z)
    Retry pool ........ R
    Fullscreen ........ F11  (or F)
    Settings / pause .. Esc, or the gear at the top right

What lives in the pools (each one turns up a pool at a time)
    Urchin ......... static spines. Cannot be punched - the spines win.
    Sea star ....... walks its ledge. Punch it and it flips over, harmless.
    Jellyfish ...... blinks faster and faster, then discharges a shock ring.
                     Punch it and it tumbles away - and stays where it lands.
    Anemone ........ land on it and it flings you higher than any hop.
                     Hold Down as you land to settle on it instead.
    Riptide ........ a band of moving water that shoves anything swimming.
    Sandstone ...... holds you for a moment, cracks, drops, grows back.
    Gull ........... dives at you in the open. Duck under rock, or sidestep
                     late and let it hit the stone.
    Bubble vent .... rumbles, then blows a column that throws you upward.
    Pistol shrimp .. its claw glows, then it snaps a bubble along its ledge.
                     Jump the bubble, punch the bubble, or punch the shrimp
                     quiet for a few seconds.
    Sea turtle ..... paddles across open water on the surface. Ride it.

Bosses
    Pool 10 ....... the Gull King. Too big to punch - make it meet the rock.
    Pool 20 ....... five lost hatchlings to lead up.
    Pool 31 ....... the Great Octopus. Dodge the slam, punch the stuck arm.

Pearls are shy - get close and they leap toward you.
You can take two hits (three on Relaxed pace). The next one ends the run.

Requires: pygame   ->   pip install pygame
Run with: python3 tide_pool.py
"""

import asyncio
import json
import math
import os
import random
import sys

import pygame

# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

WORLD_W, WORLD_H = 420, 620
AD_H = 64
HUD_H = 36
WIN_W, WIN_H = WORLD_W, AD_H + HUD_H + WORLD_H
FPS = 60

SAVE_PATH = os.path.join(os.path.expanduser("~"), ".tide_pool_save.json")

# physics
GRAVITY = 0.46
MAX_FALL = 9.0
WALK_SPEED = 2.45
SWIM_SPEED = 1.55
GROUND_ACCEL = 0.34
WATER_ACCEL = 0.14
WATER_DRAG = 0.90
BUOYANCY = 1.95          # > 1 means a fully sunk crab rises
JUMP_MIN = 5.2
JUMP_MAX = 10.4
UP_THRUST = 0.30         # swim up, on top of buoyancy
DIVE_THRUST = 0.66       # must beat buoyancy or you could never go down
CHARGE_TIME = 0.52
PUNCH_TIME = 0.30        # windup, thrust, recover - all three are visible
PUNCH_COOLDOWN = 0.38
PUNCH_HIT_R = 11.0       # radius of the claw hitbox, centred on the drawn claw
IFRAME_TIME = 3.0        # longer mercy window after a hit
MAX_HP = 3
DANCE_AFTER = 4.0        # seconds of stillness before the idle dance starts
ZAP_TIME = 0.85          # how long the crab rattles after a shock
RAINBOW_STREAK = 3       # clean pools in a row that earn rainbow mode

CRAB_W, CRAB_H = 26, 16

# ---- palette: a sunlit tropical pool, not a grey one ----------------------
C_SKY_TOP = (255, 212, 158)       # low warm sun
C_SKY_BOT = (152, 230, 232)       # pale turquoise haze
C_SUN = (255, 243, 198)
C_WATER_TOP = (86, 212, 205)
C_WATER_MID = (34, 158, 178)
C_WATER_DEEP = (16, 82, 118)
C_FOAM = (236, 255, 250)
C_CAUSTIC = (190, 255, 244)
C_ROCK = (180, 140, 100)
C_ROCK_TOP = (214, 176, 118)
C_ROCK_LIT = (246, 218, 158)
C_ROCK_DARK = (104, 74, 56)
C_KELP = (46, 150, 112)
C_KELP_DARK = (28, 104, 84)
C_CRAB = (255, 104, 58)
C_CRAB_DARK = (198, 56, 30)
C_CRAB_PALE = (255, 178, 134)
C_SHELL = (255, 204, 74)
C_SHELL_DARK = (214, 148, 32)
C_URCHIN = (92, 46, 118)
C_URCHIN_LIT = (178, 98, 214)
C_EEL = (92, 206, 140)
C_EEL_DARK = (30, 128, 98)
C_EEL_BELLY = (230, 252, 196)
C_PUFFER = (246, 186, 92)
C_PUFFER_DARK = (190, 124, 44)
C_STAR = (242, 118, 108)
C_STAR_DARK = (186, 64, 60)
C_GULL = (248, 250, 252)
C_GULL_DARK = (152, 170, 184)
C_GULL_BEAK = (250, 176, 60)
C_JELLY = (232, 116, 198)
C_JELLY_DARK = (168, 62, 150)
C_JELLY_HOT = (255, 248, 164)
C_JELLY_DRY = (190, 182, 158)          # sun-bleached, stranded on dry rock
C_JELLY_DRY_DARK = (140, 132, 112)
C_INK = (24, 46, 54)
C_MUTED = (104, 136, 142)
C_PANEL = (255, 251, 242)
C_PANEL_2 = (255, 255, 255)
C_DANGER = (236, 74, 68)
C_WHITE = (255, 255, 255)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(a, b, t):
    t = clamp(t, 0, 1)
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


def approach(v, target, rate):
    if v < target:
        return min(v + rate, target)
    return max(v - rate, target)


_shadow_cache = {}


def shadow(surf, x, y, rx, ry, alpha=70):
    """Soft contact shadow. Cached per size so this stays cheap."""
    key = (int(rx), int(ry), int(alpha))
    sh = _shadow_cache.get(key)
    if sh is None:
        sh = pygame.Surface((rx * 2 + 8, ry * 2 + 8), pygame.SRCALPHA)
        steps = 4
        for i in range(steps, 0, -1):
            k = i / steps
            a = int(alpha * (1.0 - k) ** 1.5 + alpha * 0.25)
            pygame.draw.ellipse(sh, (12, 32, 40, a),
                                (4 + rx * (1 - k), 4 + ry * (1 - k),
                                 rx * 2 * k, ry * 2 * k))
        _shadow_cache[key] = sh
    surf.blit(sh, (int(x - rx - 4), int(y - ry - 4)))


# ----------------------------------------------------------------------------
# Levels
# ----------------------------------------------------------------------------

LEVELS = [
    # ---- pool 1
    dict(
        name='Shallows',
        period=10.0,
        tide_low=606,
        tide_high=362,
        spawn=(30, 575),
        goal=(340, 360),
        plats=[(0, 600, 420, 20), (100, 490, 110, 16), (250, 380, 130, 16)],
        urchins=[(232, 592)],
        crawlers=[],
        jellies=[],
        gulls=[],
        pearls=[(150, 470), (62, 580)],
        tip='Arrows swim all 8 ways. SPACE charges a hop. Hold DOWN to grip rock.',
    ),
    # ---- pool 2
    dict(
        name='Tidemarks',
        period=11.0,
        tide_low=606,
        tide_high=228,
        spawn=(30, 575),
        goal=(350, 230),
        plats=[(0, 600, 420, 20), (20, 500, 120, 16), (180, 420, 110, 16), (40, 330, 130, 16), (270, 250, 150, 16)],
        urchins=[(380, 592)],
        crawlers=[((180, 420, 110, 16), 220, 26)],
        jellies=[],
        gulls=[],
        pearls=[(80, 482), (235, 402), (100, 312)],
        tip='That star walks its ledge. Punch it with B and it flips over, harmless.',
    ),
    # ---- pool 3
    dict(
        name='Anemone cove',
        period=11.0,
        tide_low=606,
        tide_high=380,
        spawn=(30, 575),
        goal=(320, 230),
        plats=[(0, 600, 420, 20), (0, 520, 140, 16), (250, 470, 170, 16), (60, 380, 160, 16), (240, 250, 160, 16)],
        urchins=[(330, 462)],
        crawlers=[],
        jellies=[],
        gulls=[],
        anemones=[(195, 380)],
        pearls=[(390, 452), (222, 300), (40, 502)],
        tip="The tide won't reach the top. Land on the anemone to fly - hold DOWN to land soft.",
    ),
    # ---- pool 4
    dict(
        name='Jelly drift',
        period=12.0,
        tide_low=606,
        tide_high=218,
        spawn=(30, 575),
        goal=(60, 220),
        plats=[(0, 600, 420, 20), (240, 520, 180, 16), (60, 440, 140, 16), (250, 350, 170, 16), (0, 240, 140, 16)],
        urchins=[(300, 512)],
        crawlers=[],
        jellies=[((160, 560), (160, 400), 0.34)],
        gulls=[],
        anemones=[(320, 350)],
        pearls=[(130, 422), (390, 332), (30, 222)],
        tip='Jellyfish blink faster and faster before they fire. Swim wide of them.',
    ),
    # ---- pool 5
    dict(
        name='Overhang',
        period=12.0,
        tide_low=606,
        tide_high=208,
        spawn=(30, 575),
        goal=(55, 210),
        plats=[(0, 600, 420, 20), (0, 520, 110, 16), (160, 440, 140, 16), (310, 360, 110, 16), (110, 320, 150, 16), (0, 230, 130, 16)],
        urchins=[(362, 352)],
        crawlers=[((110, 320, 150, 16), 160, 30)],
        jellies=[((360, 540), (360, 420), 0.36)],
        gulls=[],
        pearls=[(230, 422), (185, 302), (40, 502)],
        tip='Ledges overhead stop the tide lifting you. Swim out from under them early.',
    ),
    # ---- pool 6
    dict(
        name='Riptide',
        period=11.0,
        tide_low=606,
        tide_high=228,
        spawn=(30, 575),
        goal=(350, 230),
        plats=[(0, 600, 420, 20), (0, 500, 130, 16), (280, 460, 140, 16), (140, 380, 120, 16), (0, 290, 120, 16), (280, 250, 140, 16)],
        urchins=[(340, 452)],
        crawlers=[],
        jellies=[],
        gulls=[],
        currents=[(0, 315, 420, 70, -2.0), (120, 212, 170, 75, 2.0)],
        pearls=[(200, 362), (400, 442), (40, 272)],
        tip='Currents shove anything swimming in them. Ride them, or swim hard against them.',
    ),
    # ---- pool 7
    dict(
        name='Sandstone',
        period=11.0,
        tide_low=606,
        tide_high=330,
        spawn=(30, 575),
        goal=(330, 190),
        plats=[(0, 600, 420, 20), (0, 520, 140, 16), (270, 450, 150, 16), (120, 390, 120, 16), (260, 210, 160, 16)],
        urchins=[(340, 442)],
        crawlers=[],
        jellies=[],
        gulls=[],
        crumbles=[(40, 300, 80, 14), (150, 252, 70, 14)],
        pearls=[(80, 282), (185, 234), (60, 502)],
        tip='The tide stops short. Sandstone holds you for a moment, then drops - keep moving.',
    ),
    # ---- pool 8
    dict(
        name='Gull run',
        period=12.0,
        tide_low=606,
        tide_high=128,
        spawn=(30, 575),
        goal=(50, 130),
        plats=[(0, 600, 420, 20), (240, 530, 180, 16), (40, 460, 160, 16), (250, 370, 170, 16), (60, 290, 140, 16), (220, 210, 160, 16), (0, 150, 140, 16)],
        urchins=[(320, 522)],
        crawlers=[((60, 290, 140, 16), 110, 26)],
        jellies=[],
        gulls=[(150, 90, 110), (320, 110, 90)],
        pearls=[(400, 512), (100, 442), (330, 352)],
        tip='Two birds. Duck under a ledge, or step aside late and let them hit the rock.',
    ),
    # ---- pool 9
    dict(
        name='Breathing rock',
        period=11.0,
        tide_low=606,
        tide_high=340,
        spawn=(30, 575),
        goal=(300, 175),
        plats=[(0, 600, 420, 20), (0, 500, 140, 16), (260, 440, 160, 16), (120, 330, 120, 16), (230, 195, 190, 16)],
        urchins=[],
        crawlers=[],
        jellies=[((60, 430), (60, 340), 0.3)],
        gulls=[],
        vents=[(180, 330, 190, 3.4, 1.6), (340, 440, 110, 3.0, 1.3)],
        pearls=[(180, 250), (340, 300), (60, 482)],
        tip='Rock that rumbles is about to breathe. Stand over it and ride the bubbles up.',
    ),
    # ---- pool 10
    dict(
        name='Gull King',
        period=12.0,
        tide_low=606,
        tide_high=118,
        spawn=(30, 575),
        goal=(210, 120),
        special='gullking',
        boss=(210, 86, 140),
        plats=[(0, 600, 420, 20), (0, 520, 130, 16), (290, 520, 130, 16), (145, 430, 130, 16), (0, 330, 120, 16), (300, 330, 120, 16), (150, 240, 120, 16), (150, 140, 120, 16)],
        urchins=[(360, 512)],
        crawlers=[],
        jellies=[],
        gulls=[],
        pearls=[(60, 502), (210, 412), (360, 312)],
        tip='The Gull King. Too big to punch. Make it meet the rock.',
    ),
    # ---- pool 11
    dict(
        name='Snap alley',
        period=11.0,
        tide_low=606,
        tide_high=223,
        spawn=(30, 575),
        goal=(60, 225),
        plats=[(0, 600, 420, 20), (200, 520, 220, 16), (0, 440, 180, 16), (220, 350, 200, 16), (0, 245, 140, 16)],
        urchins=[],
        crawlers=[],
        jellies=[],
        gulls=[],
        shrimps=[(400, 520, -1, 3.4), (110, 440, 1, 3.2), (400, 350, -1, 3.6)],
        pearls=[(300, 500), (60, 420), (300, 330)],
        tip='Pistol shrimp glow before they snap. Jump the bubble, or punch the shrimp quiet.',
    ),
    # ---- pool 12
    dict(
        name='Turtle crossing',
        period=12.0,
        tide_low=606,
        tide_high=193,
        spawn=(30, 575),
        goal=(375, 195),
        plats=[(0, 600, 420, 20), (0, 500, 80, 16), (0, 380, 80, 16), (340, 440, 80, 16), (340, 320, 80, 16), (0, 250, 80, 16), (330, 215, 90, 16)],
        urchins=[(150, 592), (210, 592), (270, 592)],
        crawlers=[],
        jellies=[],
        gulls=[],
        currents=[(80, 170, 260, 430, -2.6)],
        turtles=[(120, 300, 200, 40)],
        pearls=[(210, 230), (40, 362), (380, 302)],
        tip="The middle current is a slog to swim. The turtle doesn't mind it.",
    ),
    # ---- pool 13
    dict(
        name='Undertow',
        period=8.5,
        tide_low=606,
        tide_high=118,
        spawn=(30, 575),
        goal=(345, 120),
        plats=[(0, 600, 420, 20), (0, 520, 130, 16), (290, 520, 130, 16), (150, 430, 120, 16), (0, 330, 110, 16), (310, 330, 110, 16), (0, 200, 110, 16), (280, 140, 140, 16)],
        urchins=[(370, 512)],
        crawlers=[],
        jellies=[((360, 470), (360, 380), 0.4)],
        gulls=[],
        currents=[(130, 450, 160, 70, 2.2), (0, 230, 160, 70, -1.8)],
        vents=[(210, 430, 200, 3.2, 1.4)],
        pearls=[(210, 300), (60, 312), (360, 312)],
        tip='Fast water. The vent throws you clear of the undertow.',
    ),
    # ---- pool 14
    dict(
        name='The bloom',
        period=13.0,
        tide_low=606,
        tide_high=118,
        spawn=(30, 575),
        goal=(140, 120),
        plats=[(0, 600, 420, 20), (0, 530, 160, 16), (260, 460, 160, 16), (40, 370, 150, 16), (250, 270, 170, 16), (60, 140, 160, 16)],
        urchins=[],
        crawlers=[],
        jellies=[((210, 500), (210, 400), 0.36), ((330, 380), (200, 380), 0.4), ((120, 240), (120, 180), 0.4)],
        gulls=[],
        anemones=[(330, 460), (110, 370)],
        pearls=[(330, 380), (110, 300), (330, 252)],
        tip='A bloom. Spring over them - the anemones fling you clear.',
    ),
    # ---- pool 15
    dict(
        name='Crosscurrent',
        period=10.5,
        tide_low=606,
        tide_high=123,
        spawn=(30, 575),
        goal=(225, 125),
        plats=[(0, 600, 420, 20), (300, 540, 120, 16), (0, 470, 130, 16), (260, 400, 160, 16), (0, 320, 150, 16), (270, 250, 150, 16), (170, 145, 110, 16)],
        urchins=[],
        crawlers=[],
        jellies=[],
        gulls=[],
        currents=[(0, 490, 420, 50, 1.8), (0, 350, 420, 45, -2.0), (0, 265, 420, 45, 1.6)],
        shrimps=[(110, 470, 1, 3.6), (400, 400, -1, 3.4)],
        pearls=[(380, 522), (60, 302), (340, 232)],
        tip='Three currents, three directions. Read them before you jump in.',
    ),
    # ---- pool 16
    dict(
        name='Crumble stair',
        period=11.0,
        tide_low=606,
        tide_high=320,
        spawn=(30, 575),
        goal=(350, 160),
        plats=[(0, 600, 420, 20), (0, 520, 140, 16), (270, 470, 150, 16), (120, 400, 140, 16), (280, 180, 140, 16)],
        urchins=[(340, 462)],
        crawlers=[],
        jellies=[],
        gulls=[(200, 100, 120)],
        crumbles=[(20, 292, 80, 14), (130, 246, 70, 14), (215, 214, 50, 14)],
        pearls=[(60, 274), (165, 228), (240, 196)],
        tip="A sandstone stair and a bird watching it. Don't stop.",
    ),
    # ---- pool 17
    dict(
        name='Moon pool',
        period=15.0,
        tide_low=606,
        tide_high=113,
        spawn=(30, 575),
        goal=(355, 115),
        plats=[(0, 600, 420, 20), (330, 560, 90, 14), (40, 450, 80, 14), (200, 380, 70, 14), (330, 320, 80, 14), (60, 270, 80, 14), (190, 200, 70, 14), (300, 135, 110, 14)],
        urchins=[(85, 442)],
        crawlers=[],
        jellies=[((150, 520), (150, 420), 0.3), ((290, 440), (290, 340), 0.32), ((130, 330), (130, 230), 0.3)],
        gulls=[],
        pearls=[(235, 362), (100, 252), (225, 182)],
        tip='Long, slow tide. Small stones. Jellies drifting in the dark.',
    ),
    # ---- pool 18
    dict(
        name='Rookery',
        period=12.0,
        tide_low=606,
        tide_high=108,
        spawn=(30, 575),
        goal=(210, 110),
        plats=[(0, 600, 420, 20), (0, 520, 170, 16), (140, 440, 160, 16), (0, 350, 140, 16), (280, 350, 140, 16), (140, 270, 140, 16), (280, 190, 140, 16), (140, 130, 140, 16)],
        urchins=[(250, 432)],
        crawlers=[((140, 270, 140, 16), 180, 28)],
        jellies=[],
        gulls=[(90, 80, 70), (330, 80, 70), (210, 95, 110)],
        anemones=[(350, 350)],
        pearls=[(80, 332), (350, 172), (210, 252)],
        tip="The rookery. Get under a ledge and they can't reach you.",
    ),
    # ---- pool 19
    dict(
        name='Last ledge',
        period=10.0,
        tide_low=606,
        tide_high=116,
        spawn=(30, 575),
        goal=(225, 118),
        plats=[(0, 600, 420, 20), (0, 530, 130, 16), (290, 500, 130, 16), (140, 420, 130, 16), (300, 330, 120, 16), (0, 300, 130, 16), (150, 138, 150, 16)],
        urchins=[(60, 292)],
        crawlers=[],
        jellies=[((370, 420), (370, 260), 0.42)],
        gulls=[(210, 90, 120)],
        currents=[(0, 440, 140, 80, 1.8)],
        crumbles=[(160, 232, 60, 14), (250, 196, 50, 14)],
        shrimps=[(400, 500, -1, 3.2)],
        pearls=[(200, 402), (360, 312), (190, 214)],
        tip='Everything so far, in one climb.',
    ),
    # ---- pool 20
    dict(
        name='Open water',
        period=13.0,
        tide_low=606,
        tide_high=113,
        spawn=(28, 575),
        goal=(360, 115),
        plats=[(0, 600, 420, 20), (0, 515, 160, 16), (230, 455, 190, 16), (40, 370, 170, 16), (250, 290, 170, 16), (30, 215, 150, 16), (240, 135, 180, 16)],
        urchins=[(120, 507), (300, 447), (90, 362)],
        crawlers=[],
        jellies=[((180, 400), (180, 310), 0.34)],
        gulls=[],
        anemones=[(290, 290)],
        hatchlings=[(70, 509), (390, 449), (190, 364), (340, 284), (90, 209)],
        pearls=[(40, 497), (290, 437), (160, 352)],
        tip='Five little ones are lost on these ledges. Bring them all up.',
    ),
    # ---- pool 21
    dict(
        name='Bubble ladder',
        period=11.0,
        tide_low=606,
        tide_high=380,
        spawn=(30, 575),
        goal=(355, 110),
        plats=[(0, 600, 420, 20), (300, 480, 120, 16), (60, 340, 140, 16), (130, 210, 140, 16), (290, 130, 130, 16)],
        urchins=[(360, 472)],
        crawlers=[],
        jellies=[((360, 560), (360, 420), 0.32)],
        gulls=[],
        vents=[(230, 600, 230, 3.6, 1.7), (80, 340, 190, 3.4, 1.6), (250, 210, 150, 3.4, 1.6)],
        pearls=[(230, 340), (80, 230), (250, 120)],
        tip='A ladder made of air. Wait for each vent to breathe.',
    ),
    # ---- pool 22
    dict(
        name='Ferry and shrimp',
        period=12.0,
        tide_low=606,
        tide_high=118,
        spawn=(30, 575),
        goal=(370, 120),
        plats=[(0, 600, 420, 20), (0, 480, 90, 16), (330, 430, 90, 16), (0, 330, 90, 16), (330, 260, 90, 16), (0, 180, 85, 16), (320, 140, 100, 16)],
        urchins=[(150, 592), (270, 592)],
        crawlers=[],
        jellies=[],
        gulls=[],
        currents=[(90, 110, 240, 490, -2.4)],
        turtles=[(125, 290, 120, 40)],
        shrimps=[(380, 430, -1, 3.4), (40, 330, 1, 3.6)],
        pearls=[(210, 280), (40, 312), (370, 242)],
        tip='Ride the shell, and mind the snaps from either side.',
    ),
    # ---- pool 23
    dict(
        name='Sinking steps',
        period=11.0,
        tide_low=606,
        tide_high=300,
        spawn=(30, 575),
        goal=(355, 150),
        plats=[(0, 600, 420, 20), (0, 480, 120, 16), (300, 430, 120, 16), (140, 360, 100, 16), (290, 170, 130, 16)],
        urchins=[(350, 422)],
        crawlers=[],
        jellies=[((60, 430), (60, 340), 0.36)],
        gulls=[(250, 90, 110)],
        currents=[(0, 300, 420, 90, 2.0)],
        crumbles=[(30, 270, 70, 14), (130, 232, 60, 14), (220, 200, 50, 14)],
        pearls=[(65, 252), (160, 214), (245, 182)],
        tip='The steps sink, and the current wants you on the wrong side.',
    ),
    # ---- pool 24
    dict(
        name='Spring garden',
        period=11.0,
        tide_low=606,
        tide_high=560,
        spawn=(30, 575),
        goal=(300, 70),
        plats=[(0, 600, 420, 20), (0, 360, 90, 16), (130, 470, 110, 16), (250, 340, 110, 16), (140, 210, 120, 16), (230, 90, 140, 16)],
        urchins=[(380, 592)],
        crawlers=[],
        jellies=[],
        gulls=[(80, 60, 60)],
        anemones=[(80, 600), (200, 470), (320, 340), (170, 210)],
        pearls=[(40, 342), (320, 250), (170, 120)],
        tip='Spring by spring to the top. Hold DOWN when you want to stay put.',
    ),
    # ---- pool 25
    dict(
        name='The narrows',
        period=11.0,
        tide_low=606,
        tide_high=108,
        spawn=(30, 575),
        goal=(210, 110),
        plats=[(0, 600, 420, 20), (0, 500, 150, 16), (270, 500, 150, 16), (0, 380, 160, 16), (260, 380, 160, 16), (0, 260, 170, 16), (250, 260, 170, 16), (150, 130, 120, 16)],
        urchins=[(120, 492)],
        crawlers=[],
        jellies=[],
        gulls=[],
        currents=[(0, 520, 420, 70, 1.6), (0, 400, 420, 90, -1.8), (0, 280, 420, 90, 1.8), (0, 150, 420, 100, -1.6)],
        shrimps=[(400, 500, -1, 3.6)],
        pearls=[(80, 362), (340, 242), (40, 242)],
        tip='The narrows. Each layer of water runs the other way.',
    ),
    # ---- pool 26
    dict(
        name='Lighthouse',
        period=12.0,
        tide_low=606,
        tide_high=98,
        spawn=(210, 575),
        goal=(210, 100),
        plats=[(0, 600, 420, 20), (150, 520, 120, 16), (0, 430, 110, 16), (310, 430, 110, 16), (150, 330, 120, 16), (0, 230, 100, 16), (320, 230, 100, 16), (150, 120, 120, 16)],
        urchins=[],
        crawlers=[],
        jellies=[((60, 560), (60, 470), 0.34), ((360, 370), (360, 270), 0.36)],
        gulls=[(210, 70, 140)],
        crumbles=[(110, 280, 40, 14), (270, 280, 40, 14)],
        shrimps=[(200, 330, 1, 3.8)],
        pearls=[(40, 412), (380, 212), (240, 312)],
        tip="Climb the lighthouse. The sandstone bridges won't wait.",
    ),
    # ---- pool 27
    dict(
        name='Shrimp fort',
        period=11.0,
        tide_low=606,
        tide_high=118,
        spawn=(30, 575),
        goal=(220, 120),
        plats=[(0, 600, 420, 20), (0, 510, 140, 16), (280, 450, 140, 16), (0, 380, 140, 16), (280, 310, 140, 16), (0, 240, 140, 16), (160, 140, 120, 16)],
        urchins=[],
        crawlers=[],
        jellies=[],
        gulls=[],
        shrimps=[(130, 510, 1, 3.0), (290, 450, -1, 3.2), (130, 380, 1, 3.0), (290, 310, -1, 3.2), (130, 240, 1, 3.4)],
        pearls=[(380, 432), (40, 362), (380, 292)],
        tip='A fort of shrimp. Punch one quiet and slip past while it sulks.',
    ),
    # ---- pool 28
    dict(
        name='Storm tide',
        period=7.5,
        tide_low=606,
        tide_high=108,
        spawn=(30, 575),
        goal=(365, 110),
        plats=[(0, 600, 420, 20), (0, 470, 100, 16), (320, 470, 100, 16), (0, 300, 100, 16), (320, 300, 100, 16), (0, 160, 110, 16), (310, 130, 110, 16)],
        urchins=[(50, 462)],
        crawlers=[],
        jellies=[((210, 420), (210, 250), 0.5)],
        gulls=[(210, 80, 140)],
        currents=[(110, 100, 200, 500, -2.4)],
        turtles=[(140, 280, 120, 48)],
        pearls=[(210, 220), (50, 282), (370, 282)],
        tip="Storm tide. The water won't wait, and neither will the turtle.",
    ),
    # ---- pool 29
    dict(
        name='Kelp cathedral',
        period=13.0,
        tide_low=606,
        tide_high=128,
        spawn=(210, 575),
        goal=(210, 130),
        plats=[(0, 600, 420, 20), (0, 480, 130, 16), (290, 480, 130, 16), (150, 380, 120, 16), (0, 260, 110, 16), (310, 260, 110, 16), (150, 150, 120, 16)],
        urchins=[],
        crawlers=[((150, 380, 120, 16), 180, 26)],
        jellies=[((210, 310), (210, 230), 0.3)],
        gulls=[],
        anemones=[(60, 480), (360, 480)],
        pearls=[(60, 400), (360, 400), (60, 242)],
        tip='Quiet water for once. Enjoy the springs.',
    ),
    # ---- pool 30
    dict(
        name='High-water mark',
        period=11.0,
        tide_low=606,
        tide_high=88,
        spawn=(210, 575),
        goal=(340, 90),
        plats=[(0, 600, 420, 20), (0, 520, 120, 16), (300, 520, 120, 16), (150, 440, 120, 16), (0, 350, 110, 16), (310, 350, 110, 16), (160, 250, 100, 16), (260, 110, 160, 16)],
        urchins=[(60, 512)],
        crawlers=[],
        jellies=[((210, 330), (210, 280), 0.42)],
        gulls=[(120, 70, 90)],
        currents=[(120, 460, 180, 60, 2.0)],
        vents=[(365, 350, 120, 3.4, 1.5)],
        shrimps=[(400, 520, -1, 3.0), (20, 350, 1, 3.2)],
        pearls=[(210, 422), (80, 332), (210, 232)],
        tip="The high-water mark. Everything you've learned, and then some.",
    ),
    # ---- pool 31
    dict(
        name='The deep',
        period=12.0,
        tide_low=606,
        tide_high=98,
        spawn=(40, 480),
        goal=(210, 100),
        special='octopus',
        octopus=(210, 600),
        plats=[(0, 600, 420, 20), (0, 500, 120, 16), (300, 500, 120, 16), (140, 400, 140, 16), (0, 300, 120, 16), (300, 300, 120, 16), (40, 200, 100, 16), (280, 200, 100, 16), (150, 120, 120, 16)],
        urchins=[],
        crawlers=[],
        jellies=[],
        gulls=[],
        pearls=[(60, 282), (360, 282), (90, 182)],
        tip="The Great Octopus. Dodge the slam, then punch the arm while it's stuck.",
        dialogue=[
            ('Old hermit', 'So. The old octopus finally let someone through.'),
            ('Old hermit', 'All the way up from the shallows. Good.'),
            ('Old hermit', "Careful at that edge. It isn't another pool."),
            ('Old hermit', "That's all of them, at once, going out."),
            ('Old hermit', "I've been in this one since the spring tide."),
            ('Old hermit', 'Good rock. Good light. I stopped climbing.'),
            ('Old hermit', 'Every pool you crossed is still down there,'),
            ('Old hermit', 'filling and emptying, with or without you in it.'),
            ('Old hermit', "That's the thing about a tide. It isn't taking"),
            ('Old hermit', 'anything from you. It only ever keeps moving.'),
            ('Old hermit', "Go on, then. The water's high enough."),
            ('', 'The crab lets go of the rock,'),
            ('', 'and the sea carries it the rest of the way.'),
        ],
    ),
]


# ----------------------------------------------------------------------------
# Particles
# ----------------------------------------------------------------------------

class Particles:
    def __init__(self):
        self.items = []

    def clear(self):
        self.items.clear()

    def add(self, x, y, vx, vy, life, color, radius=2.5, grav=0.0, glow=False):
        self.items.append(dict(x=x, y=y, vx=vx, vy=vy, life=life, t=life,
                               color=color, r=radius, g=grav, glow=glow))

    def burst(self, x, y, n, color, speed=3.0, life=0.45, radius=2.6, grav=0.1,
              glow=False):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(speed * 0.35, speed)
            self.add(x, y, math.cos(a) * s, math.sin(a) * s,
                     life * random.uniform(0.6, 1.2), color,
                     radius * random.uniform(0.6, 1.3), grav, glow)

    def ring(self, x, y, n, color, speed=4.0, life=0.4):
        for i in range(n):
            a = math.tau * i / n
            self.add(x, y, math.cos(a) * speed, math.sin(a) * speed,
                     life, color, 2.8, 0.0, True)

    def splash(self, x, y, strength=1.0):
        for _ in range(int(10 * strength)):
            self.add(x + random.uniform(-10, 10), y,
                     random.uniform(-2.4, 2.4),
                     random.uniform(-4.8, -1.8) * strength,
                     0.55, C_FOAM, random.uniform(1.5, 3.4), 0.30)

    def sparkle(self, x, y, color=C_SHELL):
        self.add(x + random.uniform(-4, 4), y + random.uniform(-4, 4),
                 random.uniform(-0.4, 0.4), random.uniform(-0.9, -0.3),
                 0.5, color, random.uniform(1.2, 2.2), 0.0, True)

    def update(self, dt):
        for p in self.items:
            p["vy"] += p["g"]
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vx"] *= 0.97
            p["t"] -= dt
        self.items = [p for p in self.items if p["t"] > 0]

    def draw(self, surf):
        glowbuf = None
        for p in self.items:
            k = clamp(p["t"] / p["life"], 0, 1)
            r = max(1, int(p["r"] * (0.3 + 0.7 * k)))
            if p["glow"]:
                if glowbuf is None:
                    glowbuf = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
                gc = tuple(int(c * k / 9) for c in p["color"])
                pygame.draw.circle(glowbuf, gc,
                                   (int(p["x"]), int(p["y"])), r * 3)
            pygame.draw.circle(surf, p["color"], (int(p["x"]), int(p["y"])), r)
        if glowbuf is not None:
            surf.blit(glowbuf, (0, 0), special_flags=pygame.BLEND_ADD)


# ----------------------------------------------------------------------------
# Entities
# ----------------------------------------------------------------------------

class Crab:
    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.face = 1
        self.on_ground = False
        self.walk = 0.0
        self.charge = 0.0
        self.charging = False
        self.punch_t = 0.0
        self.punch_cd = 0.0
        self.punch_ang = 0.0        # locked in when the swing starts
        self.punch_hit = 0.0        # impact flash timer
        self.punch_ang = 0.0
        self.punch_hit = False
        self.iframe = 0.0
        self.squash = 0.0
        self.was_wet = False
        self.blink = random.uniform(1.5, 4.0)
        self.ant = [0.0, 0.0]
        self.trail = []
        # 8-way pose. in_x/in_y are the BUTTONS held this frame; sx/sy are the
        # smoothed version used for drawing. The pose never reads velocity, so
        # drifting sideways on a current does not change which way the crab
        # holds itself - only a pressed direction does.
        self.in_x = self.in_y = 0
        self.sx = self.sy = 0.0
        self.pose_amt = 0.0
        self.kick = 0.0
        self.gripping = False
        self.safe_spot = (float(x), float(y))
        self.safe_t = 0.0
        # idle_t counts seconds with no button held at all; once it passes
        # DANCE_AFTER the dance ramps in through dance (0..1) and ramps back
        # out the instant anything is pressed.
        self.idle_t = 0.0
        self.dance = 0.0
        self.dance_t = 0.0
        self.zap = 0.0           # electrocution animation timer
        # resting on rock, gravity re-lands the crab every other frame, so
        # on_ground flickers. air_t smooths that into "has had its feet down
        # recently", which is what idling actually means.
        self.air_t = 0.0

    @property
    def rect(self):
        """Solid body. Used against platforms."""
        return pygame.Rect(int(self.x - CRAB_W / 2), int(self.y - CRAB_H / 2),
                           CRAB_W, CRAB_H)

    @property
    def hurt_rect(self):
        """Damage box, deliberately smaller than the drawn crab. Legs, claw
        and eyestalks stick out past the shell, and taking a hit because a
        leg tip grazed a spine is what makes a hitbox feel wrong."""
        return pygame.Rect(int(self.x - 8), int(self.y - 5), 16, 11)

    # ---- claw geometry -----------------------------------------------------
    # Drawing and collision both go through claw_point(), so the hitbox is
    # literally wherever the claw is drawn. No second set of numbers to drift.

    def aim_angle(self):
        """Direction the claw points when not mid-punch."""
        if self.in_x or self.in_y:
            return math.atan2(self.in_y, self.in_x if self.in_x else 0.0001 * self.face)
        return 0.0 if self.face > 0 else math.pi

    def punch_phase(self):
        if self.punch_t <= 0:
            return None
        return 1.0 - self.punch_t / PUNCH_TIME

    @staticmethod
    def claw_reach(u, idle_bob=0.0):
        if u is None:
            return 11.0 + idle_bob
        if u < 0.22:                              # anticipation: pull back
            return 11.0 - 7.0 * (u / 0.22)
        if u < 0.55:                              # thrust
            k = (u - 0.22) / 0.33
            return 4.0 + 24.0 * (1 - (1 - k) ** 3)
        k = (u - 0.55) / 0.45                     # recover
        return 28.0 - 17.0 * k

    def claw_point(self, idle_bob=0.0):
        """(x, y, angle, reach) of the claw this frame."""
        u = self.punch_phase()
        ang = self.punch_ang if u is not None else self.aim_angle()
        reach = self.claw_reach(u, idle_bob)
        return (self.x + math.cos(ang) * reach,
                self.y - 1 + math.sin(ang) * reach, ang, reach)

    def punch_active(self):
        """True only during the part of the swing that can connect."""
        u = self.punch_phase()
        return u is not None and 0.26 <= u <= 0.72


class Urchin:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.spin = random.uniform(0, math.tau)
        self.breathe = random.uniform(0, math.tau)

    def update(self, dt):
        self.spin += dt * 0.30
        self.breathe += dt * 1.6

    def hits(self, rect):
        return rect.colliderect(pygame.Rect(self.x - 10, self.y - 10, 20, 20))


class Eel:
    """Burrow eel. Extends and retracts along its axis like a snapping plant.

    Punching it folds one half away at an angle; the fold springs back."""

    SEG = 11.0
    R = 7.5

    def __init__(self, ax, ay, direction, reach, period):
        self.ax, self.ay = float(ax), float(ay)
        self.dir = direction
        self.reach = float(reach)
        self.period = float(period)
        self.t = random.uniform(0, period)
        self.age = random.uniform(0, 10)
        self.length = 0.0
        self.stun = 0.0
        self.bend_near = 0.0
        self.bend_near_v = 0.0
        self.bend_far = 0.0
        self.bend_far_v = 0.0
        self.segments = []
        self.flash = 0.0
        self.gape = 0.0
        self.safe = 0.0      # cannot damage while folding away from a punch

    def base_angle(self):
        return -math.pi / 2 if self.dir == "up" else math.pi / 2

    def update(self, dt):
        self.t += dt
        self.age += dt
        self.stun = max(0.0, self.stun - dt)
        self.flash = max(0.0, self.flash - dt)
        self.safe = max(0.0, self.safe - dt)

        ph = (self.t % self.period) / self.period
        if ph < 0.42:
            target = 0.06
        elif ph < 0.56:
            target = (ph - 0.42) / 0.14
        elif ph < 0.80:
            target = 1.0
        else:
            target = 1.0 - (ph - 0.80) / 0.20
        target = clamp(target, 0.0, 1.0) * self.reach
        if self.stun > 0:
            target = min(target, self.reach * 0.25)
        rate = 320.0 if target > self.length else 150.0
        self.length = approach(self.length, target, rate * dt)

        want_gape = 1.0 if (0.5 < ph < 0.82 and self.stun <= 0) else 0.0
        self.gape = approach(self.gape, want_gape, dt * 5.0)

        # The fold springs back to vertical, but it is clamped and heavily
        # damped: an underdamped spring whips the head back THROUGH the
        # player, which reads as the eel lunging at you after a clean hit.
        for attr, lim in (("near", 1.05), ("far", 1.25)):
            a = getattr(self, "bend_" + attr)
            v = getattr(self, "bend_%s_v" % attr)
            v += (-a) * 14.0 * dt
            v *= 0.82
            a += v * dt
            if a > lim:
                a, v = lim, min(v, 0.0)
            elif a < -lim:
                a, v = -lim, max(v, 0.0)
            setattr(self, "bend_" + attr, a)
            setattr(self, "bend_%s_v" % attr, v)

        self.rebuild()

    def rebuild(self):
        self.segments = []
        n = max(1, int(self.length / self.SEG))
        base = self.base_angle()
        x, y = self.ax, self.ay
        half = max(1, n // 2)
        swim = 0.10 if self.stun <= 0 else 0.26
        for i in range(n):
            bend = self.bend_near if i < half else self.bend_near + self.bend_far
            wave = math.sin(self.age * 5.0 - i * 0.7) * swim * (i / max(1, n - 1))
            ang = base + bend + wave
            x += math.cos(ang) * self.SEG
            y += math.sin(ang) * self.SEG
            self.segments.append((x, y, i))

    def hits(self, rect):
        if self.length < 14 or self.safe > 0:
            return False
        for (sx, sy, _i) in self.segments:
            if rect.colliderect(pygame.Rect(sx - self.R, sy - self.R,
                                            self.R * 2, self.R * 2)):
                return True
        return False

    def punched(self, px, py, pr, crab_x):
        """px,py,pr = the claw hitbox circle. Returns the struck point."""
        if self.length < 14:
            return None
        n = len(self.segments)
        half = max(1, n // 2)
        for (sx, sy, i) in self.segments:
            if math.hypot(sx - px, sy - py) <= self.R + pr:
                # Always fold AWAY from the crab. Which bend sign moves the
                # body away depends on whether the eel grows up or down, so
                # derive it instead of reusing the crab's facing.
                away = 1.0 if sx >= crab_x else -1.0
                axis = 1.0 if self.dir == "up" else -1.0
                kick = 3.4 * away * axis
                if i < half:
                    self.bend_near_v += kick
                    self.bend_far_v += kick * 0.4
                else:
                    self.bend_far_v += kick * 1.6
                self.stun = 0.95
                self.flash = 0.22
                self.safe = 0.55
                return (sx, sy)
        return None


def reanchor(mob):
    """After a punch the creature keeps its new spot: its whole patrol line
    slides over to wherever it was knocked, instead of it swimming straight
    back to the old line - which was usually right where you were standing."""
    tx = lerp(mob.p1[0], mob.p2[0], mob.u)
    ty = lerp(mob.p1[1], mob.p2[1], mob.u)
    ox, oy = mob.x - tx, mob.y - ty
    lo_x = min(mob.p1[0], mob.p2[0]) + ox
    hi_x = max(mob.p1[0], mob.p2[0]) + ox
    lo_y = min(mob.p1[1], mob.p2[1]) + oy
    hi_y = max(mob.p1[1], mob.p2[1]) + oy
    # keep the shifted line inside the pool
    ox += max(0.0, 24 - lo_x) - max(0.0, hi_x - (WORLD_W - 24))
    oy += max(0.0, 24 - lo_y) - max(0.0, hi_y - (WORLD_H - 24))
    mob.p1 = (mob.p1[0] + ox, mob.p1[1] + oy)
    mob.p2 = (mob.p2[0] + ox, mob.p2[1] + oy)


class Jelly:
    """Patrols, charges with an accelerating blink, then discharges a ring.

    All of that needs water. A jelly the tide has left behind strands at the
    surface instead of patrolling on into open air, and goes inert: no
    charge, no blink, no shock, and it can't be run into. It picks back up
    the instant the water returns over it - the charge it had is still there,
    just paused."""

    R = 13
    CHARGE_TIME = 3.4
    SHOCK_TIME = 1.0
    SHOCK_R = 40
    STRAND_PAD = 4.0        # how far the bell can poke above the waterline

    def __init__(self, p1, p2, speed):
        self.p1, self.p2 = p1, p2
        self.speed = speed
        self.u = random.random()
        self.dir = 1
        self.x, self.y = float(p1[0]), float(p1[1])
        self.vx = self.vy = 0.0
        self.charge = random.uniform(0, 1.6)
        self.charge_time = self.CHARGE_TIME
        self.shock = 0.0
        self.knock = 0.0
        self.spin = 0.0
        self.blink = 0.0
        self.pulse = random.uniform(0, math.tau)
        self.stranded = False
        self.droop = 0.0         # 0 afloat, 1 fully beached - purely visual

    @property
    def lit(self):
        return self.shock > 0

    def target(self):
        return (lerp(self.p1[0], self.p2[0], self.u),
                lerp(self.p1[1], self.p2[1], self.u))

    def update(self, dt, water_y=None):
        self.pulse += dt * 2.6
        if self.knock > 0:
            self.knock -= dt
            self.spin += self.vx * 0.05
            if self.knock <= 0:
                reanchor(self)
        else:
            self.u += self.dir * self.speed * dt
            if self.u >= 1:
                self.u, self.dir = 1.0, -1
            elif self.u <= 0:
                self.u, self.dir = 0.0, 1
            self.spin *= 0.88

        tx, ty = self.target()
        # smaller y is higher on screen and water fills the region BELOW
        # water_y, so a patrol target above the surface is a dry target - it
        # can't float up into open air to reach it, so it settles at the
        # surface instead
        if water_y is not None and ty < water_y - self.STRAND_PAD:
            ty = water_y - self.STRAND_PAD
        pull = 0.9 if self.knock <= 0 else 0.0     # coast while knocked away
        self.vx += (tx - self.x) * 0.035 * pull
        self.vy += (ty - self.y) * 0.035 * pull
        drag = 0.90 if self.knock <= 0 else 0.93
        self.vx *= drag
        self.vy *= drag
        self.x += self.vx
        self.y += self.vy
        self.x = clamp(self.x, 16, WORLD_W - 16)

        # smaller y is higher on screen, and water fills the region BELOW
        # water_y, so "at or above the clamped resting line" is dry
        self.stranded = water_y is not None and self.y <= water_y - self.STRAND_PAD + 0.5
        self.droop = approach(self.droop, 1.0 if self.stranded else 0.0, dt * 2.6)

        if self.stranded:
            return None             # the clock itself pauses - no free charge on the rocks

        if self.shock > 0:
            self.shock -= dt
        else:
            self.charge += dt
            k = clamp(self.charge / self.charge_time, 0, 1)
            self.blink += dt * (2.0 + k * k * 26.0)
            if self.charge >= self.charge_time:
                self.charge = 0.0
                self.shock = self.SHOCK_TIME
                return "discharge"
        return None

    def bright(self):
        if self.lit:
            return 1.0
        k = clamp(self.charge / self.charge_time, 0, 1)
        return (0.5 + 0.5 * math.sin(self.blink)) * (0.25 + 0.75 * k * k)

    def hits(self, rect):
        if self.stranded:
            return False
        r = self.SHOCK_R if self.lit else self.R
        return rect.colliderect(pygame.Rect(self.x - r, self.y - r, r * 2, r * 2))

    def punched(self, px, py, pr):
        if self.stranded:
            return False
        return math.hypot(self.x - px, self.y - py) <= self.R + pr

    def knock_back(self, fx, fy):
        self.vx += fx
        self.vy += fy
        self.knock = 1.0
        self.charge = 0.0
        self.blink = 0.0


class Puffer:
    """Drifts a patrol line. Inflates on a timer: spiked and unpunchable
    while swollen, soft and knockable while slack."""

    R_SLACK = 11
    R_PUFF = 19
    CYCLE = 3.8
    PUFF_TIME = 1.3

    def __init__(self, p1, p2, speed):
        self.p1, self.p2 = p1, p2
        self.speed = speed
        self.u = random.random()
        self.dir = 1
        self.x, self.y = float(p1[0]), float(p1[1])
        self.vx = self.vy = 0.0
        self.cycle = self.CYCLE
        self.t = random.uniform(0, self.cycle)
        self.puff = 0.0          # 0 slack .. 1 fully inflated
        self.knock = 0.0
        self.wob = random.uniform(0, math.tau)
        self.face = 1

    @property
    def spiky(self):
        return self.puff > 0.55

    @property
    def radius(self):
        return lerp(self.R_SLACK, self.R_PUFF, self.puff)

    def update(self, dt):
        self.t += dt
        self.wob += dt * 3.0
        swollen = (self.t % self.cycle) > (self.cycle - self.PUFF_TIME)
        self.puff = approach(self.puff, 1.0 if swollen else 0.0,
                             dt * (5.0 if swollen else 2.0))
        if self.knock > 0:
            self.knock -= dt
            if self.knock <= 0:
                reanchor(self)
        else:
            self.u += self.dir * self.speed * dt
            if self.u >= 1:
                self.u, self.dir = 1.0, -1
            elif self.u <= 0:
                self.u, self.dir = 0.0, 1
        tx = lerp(self.p1[0], self.p2[0], self.u)
        ty = lerp(self.p1[1], self.p2[1], self.u)
        if tx != self.x:
            self.face = 1 if tx > self.x else -1
        pull = 0.9 if self.knock <= 0 else 0.0
        self.vx += (tx - self.x) * 0.04 * pull
        self.vy += (ty - self.y) * 0.04 * pull
        self.vx *= 0.90
        self.vy *= 0.90
        self.x += self.vx
        self.y += self.vy

    def hits(self, rect):
        r = self.radius
        return rect.colliderect(pygame.Rect(self.x - r, self.y - r, r * 2, r * 2))

    def punched(self, px, py, pr):
        return math.hypot(self.x - px, self.y - py) <= self.radius + pr

    def knock_back(self, fx, fy):
        self.vx += fx
        self.vy += fy
        self.knock = 0.9


class Crawler:
    """Spiny star that walks the top of a ledge. A punch flips it onto its
    back, where it is harmless until it rights itself."""

    R = 11

    def __init__(self, plat, x, speed):
        self.plat = plat
        self.x = float(x)
        self.y = float(plat.top - 9)
        self.dir = 1 if speed > 0 else -1
        self.speed = abs(speed)
        self.flip = 0.0
        self.spin = random.uniform(0, math.tau)
        self.wob = random.uniform(0, math.tau)

    @property
    def flipped(self):
        return self.flip > 0

    def update(self, dt):
        self.wob += dt * 4.0
        if self.flip > 0:
            self.flip -= dt
            self.spin += dt * 5.0 * self.dir
            return
        self.x += self.dir * self.speed * dt
        if self.x < self.plat.left + 10:
            self.x, self.dir = self.plat.left + 10, 1
        elif self.x > self.plat.right - 10:
            self.x, self.dir = self.plat.right - 10, -1
        self.y = self.plat.top - 9

    def hits(self, rect):
        if self.flipped:
            return False
        return rect.colliderect(pygame.Rect(self.x - 10, self.y - 9, 20, 18))

    def punched(self, px, py, pr):
        return (not self.flipped and
                math.hypot(self.x - px, self.y - py) <= self.R + pr)


class Gull:
    """Circles above the waterline and stoops at you whenever you are out of
    the water. Takes two hits: the first sends it flapping back up in a
    temper, the second breaks its nerve and it leaves the pool for good.

    A hit is a punch, or the bird's own fault: it commits to a stoop and aims
    at where you were standing, so stepping aside at the last moment lands it
    beak-first in the rock. That counts.

    It is not stupid about it, though. It only stoops along a clear line of
    sight - if there's a ledge between it and you, it slides along the sky
    looking for an angle under the edge instead of diving into the roof. And
    if you duck under cover mid-stoop, it pulls up rather than eating the
    ceiling."""

    R = 13
    HP = 2
    CRASH_SPEED = 3.4        # how fast a stoop has to be to hurt the bird
    REACH = 150              # how far sideways it will consider a stoop

    def __init__(self, x, y, span, boss=False):
        self.home = (float(x), float(y))
        self.span = span
        self.x, self.y = float(x), float(y)
        self.t = random.uniform(0, math.tau)
        self.state = "hover"
        self.cool = random.uniform(1.0, 2.5)
        self.vx = self.vy = 0.0
        self.face = 1
        self.flap = random.uniform(0, math.tau)
        self.boss = boss
        self.scale = 1.65 if boss else 1.0
        self.hp = 4 if boss else self.HP
        self.max_hp = self.hp
        self.hurt_flash = 0.0
        self.gone = False
        self.sad_t = 0.0
        self.crash_pending = 0.0     # impact speed, read and cleared by Game
        self.daze = 0.0              # stars over the head after a crash
        self.seek_x = None           # where it is sliding to for a clear shot
        self.windup = 0.0            # boss only: the screech before a stoop
        self.tgt = (x, y)
        self.prey = None             # the crab's damage box, this frame

    @property
    def leaving(self):
        return self.state == "flee"

    @property
    def hw(self):
        return 12 * self.scale

    @property
    def hh(self):
        return 9 * self.scale

    def body_rect(self):
        return pygame.Rect(int(self.x - self.hw), int(self.y - self.hh),
                           int(self.hw * 2), int(self.hh * 2))

    def clear_line(self, x0, y0, x1, y1, plats):
        """True if the bird's body could travel this segment without
        touching rock. Platforms are fattened by its own half-size."""
        for p in plats:
            if p.inflate(int(self.hw * 2 - 4), int(self.hh * 2 - 4)).clipline(
                    x0, y0, x1, y1):
                return False
        return True

    def sight(self, crab, plats, x=None, y=None):
        x = self.x if x is None else x
        y = self.y if y is None else y
        # aim at the space just above the crab, so the ledge it stands on
        # doesn't count as cover
        return self.clear_line(x, y, crab.x, crab.y - 14, plats)

    def find_angle(self, crab, plats):
        """Somewhere along its flight altitude with a clear line down to
        the crab, nearest first. None if the crab is properly under cover."""
        best = None
        for k in range(0, WORLD_W // 14 + 1):
            cx = 16 + k * 14
            if cx > WORLD_W - 16 or abs(cx - crab.x) > self.REACH:
                continue
            if self.sight(crab, plats, cx, self.home[1]):
                d = abs(cx - self.x)
                if best is None or d < best[0]:
                    best = (d, cx)
        return None if best is None else best[1]

    def collide(self, plats):
        """A gull is a solid bird. It does not fly through rock - and if it
        arrives at speed in the middle of a stoop, at the spot it was aiming
        for, the rock wins."""
        r = self.body_rect()
        for p in plats:
            if not r.colliderect(p):
                continue
            spd = math.hypot(self.vx, self.vy)
            # only the ledge you were standing on counts. Clipping some other
            # bit of rock on the way down is just a scuffed approach.
            at_mark = self.state == "dive" and p.top >= self.tgt[1] - 20 \
                and p.left - 6 <= self.tgt[0] <= p.right + 6
            # landing on you isn't a crash, even on the same frame it hits
            # the rock under you - you got hit, the bird didn't
            got_you = self.prey is not None and self.hits(self.prey)
            if at_mark and spd >= self.CRASH_SPEED and not got_you:
                self.crash_pending = spd
                self.daze = 1.1
            # push out along whichever axis is least embedded
            dl = r.right - p.left
            dr = p.right - r.left
            dt_ = r.bottom - p.top
            db = p.bottom - r.top
            m = min(dl, dr, dt_, db)
            if m == dt_:
                self.y = p.top - self.hh
                self.vy = min(self.vy, 0.0)
            elif m == db:
                self.y = p.bottom + self.hh
                self.vy = max(self.vy, 0.0)
            elif m == dl:
                self.x = p.left - self.hw
                self.vx = min(self.vx, 0.0)
            else:
                self.x = p.right + self.hw
                self.vx = max(self.vx, 0.0)
            if self.state == "dive":
                self.state = "climb"     # pull out of the stoop
            r = self.body_rect()

    def start_dive(self, crab):
        self.state = "dive"
        self.seek_x = None
        # it aims a little past you, not at you, so a committed stoop
        # carries into whatever you were standing on once you move
        self.tgt = (crab.x, crab.y + 12)

    def update(self, dt, crab, crab_dry, plats):
        self.t += dt * 0.8
        self.prey = crab.hurt_rect
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
        self.daze = max(0.0, self.daze - dt)
        self.flap += dt * (7.0 if self.state != "dive" else 2.0)

        if self.state == "flee":
            # beat one: it hangs there, deflated, long enough to read the face.
            # beat two: a slow, sulking climb out of the pool.
            self.sad_t += dt
            if self.sad_t < 0.85:
                self.flap += dt * 4.0
                self.vx *= 0.86
                self.vy = self.vy * 0.86 + 0.26      # sags a little
            else:
                self.flap += dt * 11.0
                self.vy = max(self.vy - 0.09, -2.6)
                self.vx = clamp(self.vx + 0.07 * self.face, -2.4, 2.4)
            self.x += self.vx
            self.y += self.vy
            if self.y < -60 or self.x < -70 or self.x > WORLD_W + 70:
                self.gone = True
            return

        if self.state == "hover":
            self.cool -= dt
            want = self.cool <= 0 and crab_dry and crab.y > self.y + 20 \
                and abs(crab.x - self.x) < self.REACH + 60
            if want and self.sight(crab, plats):
                if self.boss:
                    self.state = "windup"
                    self.windup = 0.5
                else:
                    self.start_dive(crab)
            elif want:
                # no clear line - slide along the sky for an angle under the
                # edge rather than stooping into the roof
                self.seek_x = self.find_angle(crab, plats)
            else:
                self.seek_x = None
            if self.seek_x is not None:
                tx = self.seek_x
            else:
                tx = self.home[0] + math.sin(self.t) * self.span
            ty = self.home[1] + math.sin(self.t * 1.7) * 6
            self.vx += (tx - self.x) * (0.035 if self.seek_x is not None else 0.02)
            self.vy += (ty - self.y) * 0.03
        elif self.state == "windup":
            # the king screeches and rears back before it commits, and only
            # picks its mark at the end - so you dodge the stoop, not the tell
            self.windup -= dt
            self.flap += dt * 14.0
            self.vx *= 0.8
            self.vy = self.vy * 0.8 - 0.12
            if self.windup <= 0:
                if crab_dry and self.sight(crab, plats):
                    self.start_dive(crab)
                else:
                    self.state = "hover"
                    self.cool = 0.6
        elif self.state == "dive" and self.hits(crab.hurt_rect):
            # reached you: the stoop is spent and it pulls up. Checked before
            # anything else so a bird landing on you and the rock in the same
            # frame never gets scored as a crash. The Game still sees the
            # contact this frame and deals the damage.
            self.state = "climb"
            self.cool = random.uniform(1.2, 2.2) if self.boss \
                else random.uniform(2.4, 4.0)
        elif self.state == "dive":
            dx = self.tgt[0] - self.x
            dy = self.tgt[1] - self.y
            d = max(1.0, math.hypot(dx, dy))
            acc = 1.25 if self.boss else 1.0
            self.vx += dx / d * 0.55 * acc
            self.vy += dy / d * 0.60 * acc
            # look a few frames ahead: if there's rock in the way that ISN'T
            # the ledge it's aiming at (you ducked under a roof), pull up
            nx, ny = self.x + self.vx * 4, self.y + self.vy * 4
            for p in plats:
                if p.top < self.tgt[1] - 20 and p.inflate(
                        int(self.hw * 2), int(self.hh * 2)).clipline(
                        self.x, self.y, nx, ny):
                    self.state = "climb"
                    self.cool = random.uniform(0.8, 1.6)
                    self.vy = min(self.vy, 0.0) - 1.0
                    break
            # it only pulls up once it is right on the mark, so a stoop at an
            # empty ledge carries all the way into the wood
            if self.state == "dive" and (d < 9 or self.y > WORLD_H - 20):
                self.state = "climb"
        else:                                    # climb
            # a ledge overhead between it and the sky? slide out past its
            # nearer edge first, rather than pressing up against the
            # underside of it forever
            block = None
            for p in plats:
                if p.bottom <= self.y - self.hh + 6 and p.bottom > self.home[1] \
                        and p.left - self.hw < self.x < p.right + self.hw:
                    if block is None or p.bottom > block.bottom:
                        block = p
            if block is not None:
                lx = block.left - self.hw - 8
                rx = block.right + self.hw + 8
                if lx < 16:
                    tx = rx
                elif rx > WORLD_W - 16:
                    tx = lx
                else:
                    tx = lx if abs(self.x - lx) <= abs(self.x - rx) else rx
                self.vx += (tx - self.x) * 0.05
                self.vy -= 0.08
            else:
                self.vx += (self.home[0] - self.x) * 0.012
                self.vy -= 0.34
            if self.y <= self.home[1] + 8:
                self.state = "hover"
                self.cool = random.uniform(1.2, 2.2) if self.boss \
                    else random.uniform(2.2, 4.0)
        self.vx *= 0.93
        self.vy *= 0.93
        self.x += self.vx
        self.y += self.vy
        self.x = clamp(self.x, 14, WORLD_W - 14)
        self.collide(plats)
        if abs(self.vx) > 0.3:
            self.face = 1 if self.vx > 0 else -1

    def hits(self, rect):
        if self.gone or self.leaving:
            return False
        w, h = 20 * self.scale, 14 * self.scale
        return rect.colliderect(pygame.Rect(self.x - w / 2, self.y - h / 2, w, h))

    def punched(self, px, py, pr):
        if self.gone or self.leaving:
            return False
        return math.hypot(self.x - px, self.y - py) <= self.R * self.scale + pr

    def take_hit(self, fx):
        """Returns True if this was the hit that drove it off."""
        self.hp -= 1
        self.hurt_flash = 0.3
        self.vx += fx
        self.vy -= 4.0
        if self.hp <= 0:
            self.state = "flee"
            self.face = 1 if fx >= 0 else -1
            self.sad_t = 0.0
            self.vx = clamp(self.vx, -2.0, 2.0)
            self.vy = -1.2
            return True
        self.state = "climb"
        self.cool = random.uniform(1.4, 2.4) if self.boss else random.uniform(3.0, 5.0)
        return False

    def shrug_off(self, fx):
        """The king takes a punch like weather: it rocks, it doesn't hurt."""
        self.hurt_flash = 0.12
        self.vx += fx * 0.5
        self.vy -= 1.5
        self.state = "climb"


class Hatchling:
    """A lost baby crab, for the last pool. It waits on its ledge until you
    walk into it, then falls in line behind you, stepping exactly where you
    stepped. If you take a hit, the newest one in line loses its nerve and
    scurries back to where you found it."""

    GAP = 9                    # frames of your trail between each little one

    def __init__(self, x, y):
        self.home = (float(x), float(y))
        self.x, self.y = float(x), float(y)
        self.state = "wait"        # wait | follow | return
        self.slot = 0
        self.t = random.uniform(0, math.tau)
        self.face = 1

    def update(self, dt, trail):
        self.t += dt * 9.0
        if self.state == "follow" and trail:
            idx = min(len(trail) - 1, (self.slot + 1) * self.GAP)
            tx, ty = trail[idx]
            if abs(tx - self.x) > 0.4:
                self.face = 1 if tx > self.x else -1
            self.x += (tx - self.x) * 0.4
            self.y += (ty + 4 - self.y) * 0.4
        elif self.state == "return":
            hx, hy = self.home
            d = math.hypot(hx - self.x, hy - self.y)
            if d < 3.5:
                self.x, self.y = hx, hy
                self.state = "wait"
            else:
                step = min(d, 3.4)
                self.face = 1 if hx > self.x else -1
                self.x += (hx - self.x) / d * step
                self.y += (hy - self.y) / d * step


# ----------------------------------------------------------------------------
# The pool itself: currents, vents, anemones, sandstone, turtles, shrimp
# ----------------------------------------------------------------------------

class Current:
    """A riptide channel. Anything swimming inside it is shoved along; you
    can ride it, or fight it slowly. Out of the water it does nothing."""

    def __init__(self, x, y, w, h, push):
        self.rect = pygame.Rect(x, y, w, h)
        self.push = float(push)          # px/frame the water is moving
        self.t = random.uniform(0, 10)

    def update(self, dt):
        self.t += dt


class Vent:
    """A crack in the rock that breathes. It rumbles, then blows a column of
    bubbles that lifts anything above it - fast, in the water or out of it."""

    WARN = 0.8

    def __init__(self, x, y, height, period=3.4, blow=1.5):
        self.x, self.y = float(x), float(y)       # y = the rock it sits in
        self.height = float(height)
        self.period, self.blow = float(period), float(blow)
        self.t = random.uniform(0, period)
        self.power = 0.0                           # 0..1, eased

    @property
    def phase(self):
        return self.t % self.period

    @property
    def blowing(self):
        return self.phase > self.period - self.blow

    @property
    def warming(self):
        p = self.phase
        return self.period - self.blow - self.WARN < p <= self.period - self.blow

    def column(self):
        return pygame.Rect(int(self.x - 15), int(self.y - self.height), 30, int(self.height))

    def update(self, dt):
        self.t += dt
        self.power = approach(self.power, 1.0 if self.blowing else 0.0, dt * 5.0)


class Anemone:
    """A fat anemone on a ledge. Land on it and it flings you up, higher
    than any hop. Hold DOWN as you land and it lets you settle instead."""

    BOUNCE = 11.8
    W = 34

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)       # y = top of the ledge
        self.squish = 0.0
        self.sway = random.uniform(0, math.tau)

    @property
    def top(self):
        return self.y - 9

    def update(self, dt):
        self.sway += dt * 2.2
        self.squish = approach(self.squish, 0.0, dt * 3.0)


class Crumble:
    """A sandstone shelf. It takes your weight for a moment, cracks, drops
    away, and grows back a few seconds later."""

    HOLD = 0.55
    GONE = 3.6

    def __init__(self, x, y, w, h=14):
        self.rect = pygame.Rect(x, y, w, h)
        self.state = "solid"          # solid | cracking | fallen
        self.t = 0.0
        self.fall = 0.0               # how far the falling pieces have dropped
        self.regrow = 0.0             # 0..1 fade back in

    @property
    def solid(self):
        return self.state in ("solid", "cracking")

    def step_on(self):
        if self.state == "solid":
            self.state, self.t = "cracking", 0.0

    def update(self, dt, crab_rect):
        self.t += dt
        if self.state == "cracking" and self.t >= self.HOLD:
            self.state, self.t, self.fall = "fallen", 0.0, 0.0
            return "drop"
        if self.state == "fallen":
            self.fall += dt * 260 * min(1.0, self.t * 2)
            # grows back only where nothing is standing in the way
            if self.t >= self.GONE and not crab_rect.colliderect(self.rect.inflate(4, 10)):
                self.state, self.t, self.regrow = "solid", 0.0, 0.0
        if self.state == "solid":
            self.regrow = approach(self.regrow, 1.0, dt * 2.5)
        return None


class Turtle:
    """A sea turtle that paddles back and forth across open water, riding
    the surface as the tide moves. Stand on its shell for a lift."""

    W, H = 58, 12

    def __init__(self, x1, x2, top, speed=38):
        self.x1, self.x2 = float(x1), float(x2)
        self.x = float(x1)
        self.top_limit = float(top)       # it won't surface above this line
        self.y = WORLD_H - 30.0
        self.speed = float(speed)
        self.dir = 1
        self.pause = 0.0
        self.dx = self.dy = 0.0
        self.paddle = random.uniform(0, math.tau)

    @property
    def rect(self):
        return pygame.Rect(int(self.x - self.W / 2), int(self.y - self.H / 2), self.W, self.H)

    def update(self, dt, water_y):
        ox, oy = self.x, self.y
        # the shell rides just proud of the surface; on a big low tide it
        # settles on the sand, and it never climbs out of the water
        want = clamp(water_y - 2, self.top_limit, WORLD_H - 30)
        self.y = approach(self.y, want, dt * 120)
        if self.pause > 0:
            self.pause -= dt
        else:
            self.paddle += dt * 6.0
            self.x += self.dir * self.speed * dt
            if self.x >= self.x2:
                self.x, self.dir, self.pause = self.x2, -1, 0.9
            elif self.x <= self.x1:
                self.x, self.dir, self.pause = self.x1, 1, 0.9
        self.dx, self.dy = self.x - ox, self.y - oy


class Shrimp:
    """Pistol shrimp. It cocks its big claw - the glow tells you it's coming
    - and snaps a bubble that shoots along its ledge. Punch it and it sulks
    for a few seconds. Bumping into the shrimp itself doesn't hurt; only the
    bubble does."""

    COCK = 0.75
    R = 10

    def __init__(self, x, y, face, period=3.4):
        self.x, self.y = float(x), float(y) - 7      # y = top of its ledge
        self.face = 1 if face >= 0 else -1
        self.period = float(period)
        self.t = random.uniform(0, period * 0.5)
        self.stun = 0.0
        self.cock = 0.0
        self.recoil = 0.0

    def update(self, dt):
        self.recoil = approach(self.recoil, 0.0, dt * 6)
        if self.stun > 0:
            self.stun -= dt
            self.t = 0.0
            self.cock = approach(self.cock, 0.0, dt * 4)
            return None
        self.t += dt
        lead = self.period - self.COCK
        self.cock = clamp((self.t - lead) / self.COCK, 0.0, 1.0) if self.t > lead else 0.0
        if self.t >= self.period:
            self.t = 0.0
            self.cock = 0.0
            self.recoil = 1.0
            return "snap"
        return None

    def punched(self, px, py, pr):
        return math.hypot(self.x - px, self.y - py) <= self.R + pr


class Bubble:
    """The shrimp's shot: a cavitation bubble that skims along fast."""

    R = 7

    def __init__(self, x, y, vx):
        self.x, self.y = float(x), float(y)
        self.vx = vx
        self.life = 2.6
        self.wob = random.uniform(0, math.tau)
        self.dead = False

    def update(self, dt):
        self.x += self.vx
        self.wob += dt * 14
        self.life -= dt
        if self.life <= 0 or self.x < -20 or self.x > WORLD_W + 20:
            self.dead = True

    def rect(self):
        return pygame.Rect(int(self.x - 6), int(self.y - 6), 12, 12)

    def punched(self, px, py, pr):
        return math.hypot(self.x - px, self.y - py) <= self.R + pr


class Tentacle:
    """One arm of the Great Octopus. It rears up out of the deep (that's the
    warning), slams down where you were standing, then lies stuck in the rock
    for a moment with its tip glowing - that's when you punch it."""

    def __init__(self, base):
        self.base = base
        self.state = "idle"       # idle | aim | strike | stuck | retract
        self.t = 0.0
        self.tgt = (0.0, 0.0)
        self.u = 0.0              # how far along its arc the tip has reached
        self.flinch = 0.0
        self.times = dict(aim=0.95, strike=0.22, stuck=1.7, retract=0.5)

    def start(self, x, y, times):
        self.times = times
        self.state, self.t = "aim", 0.0
        self.tgt = (float(x), float(y))

    def ctrl(self):
        bx, by = self.base
        tx, ty = self.tgt
        return ((bx + tx) / 2, min(by, ty) - 170)

    def point(self, u):
        """Position on the arc, 0 = at the octopus, 1 = at the target."""
        (bx, by), (cx, cy), (tx, ty) = self.base, self.ctrl(), self.tgt
        a, b, c = (1 - u) * (1 - u), 2 * (1 - u) * u, u * u
        return (a * bx + b * cx + c * tx, a * by + b * cy + c * ty)

    def update(self, dt):
        self.flinch = approach(self.flinch, 0.0, dt * 4)
        if self.state == "idle":
            self.u = approach(self.u, 0.0, dt * 2)
            return None
        self.t += dt
        if self.state == "aim":
            self.u = 0.18 + math.sin(self.t * 9) * 0.03          # reared, quivering
            if self.t >= self.times["aim"]:
                self.state, self.t = "strike", 0.0
        elif self.state == "strike":
            k = clamp(self.t / self.times["strike"], 0, 1)
            self.u = 0.18 + (1 - 0.18) * k * k
            if self.t >= self.times["strike"]:
                self.state, self.t, self.u = "stuck", 0.0, 1.0
                return "impact"
        elif self.state == "stuck":
            self.u = 1.0
            if self.t >= self.times["stuck"]:
                self.state, self.t = "retract", 0.0
        elif self.state == "retract":
            self.u = max(0.0, 1.0 - self.t / self.times["retract"])
            if self.t >= self.times["retract"]:
                self.state, self.t = "idle", 0.0
        return None

    def tip(self):
        return self.point(self.u)

    def punchable(self, px, py, pr):
        if self.state != "stuck":
            return False
        tx, ty = self.tgt
        return math.hypot(tx - px, ty - py) <= 16 + pr


class Octopus:
    """The Great Octopus, at the bottom of the last pool. Three phases: one
    arm at a time, then two, then two that come faster."""

    HP = 9

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.hp = self.HP
        self.arms = [Tentacle((x - 70, y - 30)), Tentacle((x + 70, y - 30))]
        self.next = 2.4
        self.flash = 0.0
        self.blink = 2.0
        self.beaten = False
        self.sink = 0.0
        self.t = 0.0
        self.ease = 1.0           # relaxed pace gives you longer to read it

    @property
    def phase(self):
        return 1 if self.hp > 6 else 2 if self.hp > 3 else 3

    def timing(self):
        p = self.phase
        e = self.ease
        return dict(aim=(0.95, 0.8, 0.68)[p - 1] * e, strike=0.22,
                    stuck=(1.8, 1.6, 1.4)[p - 1] * e, retract=0.5)

    def update(self, dt, crab):
        self.t += dt
        self.flash = max(0.0, self.flash - dt)
        self.blink -= dt
        if self.blink < -0.15:
            self.blink = random.uniform(1.5, 3.5)
        events = []
        if self.beaten:
            self.sink += dt
            self.y += 46 * dt
            for a in self.arms:
                if a.state != "idle":
                    a.state, a.t = "retract", max(a.t, 0.0)
                a.update(dt)
            return events
        for a in self.arms:
            if a.update(dt) == "impact":
                events.append(a)
        self.next -= dt
        busy = [a for a in self.arms if a.state != "idle"]
        limit = 1 if self.phase == 1 else 2
        if self.next <= 0 and len(busy) < limit:
            # the arm on your side reaches for you
            idle = [a for a in self.arms if a.state == "idle"]
            idle.sort(key=lambda a: abs(a.base[0] - crab.x))
            idle[0].start(crab.x, crab.y + 4, self.timing())
            self.next = (2.6, 1.8, 1.25)[self.phase - 1] * self.ease
        return events

    def take_hit(self, arm):
        before = self.phase
        self.hp -= 1
        self.flash = 0.35
        arm.flinch = 1.0
        arm.state, arm.t = "retract", 0.0
        self.next = max(self.next, 1.1)
        if self.hp <= 0:
            self.beaten = True
            return "beaten"
        return "phase" if self.phase != before else "hit"


class Pearl:
    """Sits still until you come near, then leaps toward you."""

    R = 6

    def __init__(self, x, y):
        self.x, self.y = float(x), float(y)
        self.vx = self.vy = 0.0
        self.cool = random.uniform(0, 0.6)
        self.got = False
        self.bob = random.uniform(0, math.tau)
        self.spin = random.uniform(0, math.tau)
        self.on_ground = False

    def update(self, dt, crab, plats, water_y, parts):
        if self.got:
            return
        self.bob += dt * 3.0
        self.spin += dt * 2.2
        self.cool -= dt
        dx, dy = crab.x - self.x, crab.y - self.y
        dist = math.hypot(dx, dy)
        submerged = self.y > water_y

        if dist < 150 and self.cool <= 0 and (self.on_ground or submerged):
            s = 1 if dx > 0 else -1
            self.vx = s * random.uniform(2.1, 3.0)
            self.vy = random.uniform(-7.0, -5.2) if not submerged \
                else random.uniform(-3.4, -2.2)
            self.cool = random.uniform(0.55, 0.95)
            self.on_ground = False
            parts.burst(self.x, self.y, 6, C_SHELL, 2.0, 0.3, 1.8, 0.08, True)

        if submerged:
            self.vy += GRAVITY * 0.18 - 0.30
            self.vx *= 0.96
            self.vy *= 0.94
        else:
            self.vy += GRAVITY * 0.85
        self.vy = clamp(self.vy, -7, MAX_FALL)

        if abs(self.vx) + abs(self.vy) > 2.5 and random.random() < 0.3:
            parts.sparkle(self.x, self.y)

        self.x += self.vx
        self.on_ground = False
        for p in plats:
            if self._overlap(p):
                self.x -= self.vx
                self.vx *= -0.4
                break
        self.y += self.vy
        for p in plats:
            if self._overlap(p):
                if self.vy > 0:
                    self.y = p.top - self.R
                    self.on_ground = True
                    if self.vy > 3:
                        parts.burst(self.x, self.y + 4, 3, C_FOAM, 1.4, 0.22, 1.4, 0.1)
                    self.vy = 0
                    self.vx *= 0.55
                else:
                    self.y = p.bottom + self.R
                    self.vy = 0
                break
        self.x = clamp(self.x, self.R, WORLD_W - self.R)
        if self.y > WORLD_H + 60:
            self.y = WORLD_H + 60
            self.vy = 0

    def _overlap(self, p):
        return pygame.Rect(self.x - self.R, self.y - self.R,
                           self.R * 2, self.R * 2).colliderect(p)


# ----------------------------------------------------------------------------
# Shop
# ----------------------------------------------------------------------------
# Hats are mutually exclusive - one head, one hat. The dance is independent of
# whichever hat is on, so you can wear a top hat and still dance in it.

SHOP_ITEMS = [
    dict(key="dance", name="IDLE DANCE", cost=8, kind="dance",
         blurb="stand still 3s and the crab dances"),
    dict(key="spinner", name="SPINNER HAT", cost=3, kind="hat",
         blurb="rainbow spiral, propeller on top"),
    dict(key="tophat", name="TOP HAT", cost=2, kind="hat",
         blurb="for a crab of some standing"),
]
SHOP_KEYS = [it["key"] for it in SHOP_ITEMS]
RAINBOW = [(255, 92, 92), (255, 164, 66), (255, 226, 92), (118, 214, 118),
           (96, 178, 246), (158, 124, 238)]


# ----------------------------------------------------------------------------
# Ad banner (fictional brands only)
# ----------------------------------------------------------------------------

ADS = [
    dict(brand="BRINE & BUBBLE", line="Sea-salt soda. Impossibly cold.",
         bg=(14, 86, 96), fg=(238, 252, 250), accent=(255, 198, 84), tag="SODA"),
    dict(brand="KELP CRUNCH", line="Nine greens. One satisfying snap.",
         bg=(32, 96, 56), fg=(238, 250, 232), accent=(196, 240, 118), tag="SNACK"),
    dict(brand="LOW TIDE LAGER", line="Brewed on the rocks since '04.",
         bg=(122, 62, 36), fg=(252, 240, 224), accent=(255, 180, 86), tag="DRINK"),
]


class AdBanner:
    """Mock inventory slot at the top of the screen. All brands are invented."""

    def __init__(self, fonts):
        self.fonts = fonts
        self.i = random.randrange(len(ADS))
        self.t = 0.6          # start past the fade-in so the slot reads at once
        self.hold = 7.0

    def update(self, dt):
        self.t += dt
        if self.t > self.hold:
            self.t = 0.0
            self.i = (self.i + 1) % len(ADS)

    def draw(self, surf):
        ad = ADS[self.i]
        pygame.draw.rect(surf, ad["bg"], (0, 0, WIN_W, AD_H))
        sheen = pygame.Surface((WIN_W, AD_H), pygame.SRCALPHA)
        pygame.draw.ellipse(sheen, (*ad["accent"], 26), (-60, -46, WIN_W + 120, 80))
        surf.blit(sheen, (0, 0))
        for k in range(9):
            bx = (k * 61 + self.t * (16 + k * 4)) % (WIN_W + 40) - 20
            by = AD_H - 8 - ((self.t * (20 + k * 7) + k * 37) % (AD_H + 16))
            pygame.draw.circle(surf, ad["accent"], (int(bx), int(by)), 2 + (k % 3), 1)

        fade = clamp(min(self.t, self.hold - self.t) / 0.45, 0, 1)
        brand = self.fonts["ad"].render(ad["brand"], True, ad["fg"])
        line = self.fonts["small"].render(ad["line"], True, ad["accent"])
        brand.set_alpha(int(255 * fade))
        line.set_alpha(int(220 * fade))
        surf.blit(brand, (14, 11))
        surf.blit(line, (14, 36))

        tag = self.fonts["tiny"].render("AD", True, ad["bg"])
        tw = tag.get_width() + 12
        tr = pygame.Rect(WIN_W - tw - 12, 11, tw, 16)
        pygame.draw.rect(surf, ad["accent"], tr, border_radius=3)
        surf.blit(tag, (tr.x + 6, tr.y + 2))
        cat = self.fonts["tiny"].render(ad["tag"], True, ad["accent"])
        surf.blit(cat, (WIN_W - cat.get_width() - 12, 36))
        pygame.draw.line(surf, (0, 0, 0), (0, AD_H - 1), (WIN_W, AD_H - 1), 1)


# ----------------------------------------------------------------------------
# Save file
# ----------------------------------------------------------------------------

DEFAULT_SAVE = dict(level=0, unlocked=0, pearls=0, fullscreen=False,
                    pace="relaxed", wallet=0, owned=[], hat="", dance=False,
                    streak=0)


def load_save():
    try:
        with open(SAVE_PATH, "r") as f:
            d = json.load(f)
        owned = [str(k) for k in d.get("owned", []) if str(k) in SHOP_KEYS]
        hat = str(d.get("hat", ""))
        return dict(level=int(d.get("level", 0)),
                    unlocked=int(d.get("unlocked", 0)),
                    pearls=int(d.get("pearls", 0)),
                    fullscreen=bool(d.get("fullscreen", False)),
                    pace=str(d.get("pace", "relaxed")),
                    wallet=max(0, int(d.get("wallet", 0))),
                    owned=owned,
                    hat=hat if hat in owned else "",
                    dance=bool(d.get("dance", False)) and "dance" in owned,
                    streak=max(0, int(d.get("streak", 0))))
    except Exception:
        return dict(DEFAULT_SAVE, owned=[])


def write_save(d):
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(d, f)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Game
# ----------------------------------------------------------------------------

MENU, PLAY, DEAD, CLEARED, SETTINGS, CONTROLS, SHOP, DIALOGUE = \
    "menu", "play", "dead", "cleared", "settings", "controls", "shop", "dialogue"


class Button:
    def __init__(self, label, rect, enabled=True, sub="", primary=False):
        self.label = label
        self.rect = pygame.Rect(rect)
        self.enabled = enabled
        self.sub = sub
        self.primary = primary
        self.hover = 0.0


class MergedKeys:
    """Wraps pygame.key.get_pressed() so the on-screen touch controls read as
    the same keys the keyboard would send. update_play never knows the
    difference - it just asks for K_LEFT, K_SPACE, and so on."""

    def __init__(self, real, extra):
        self.real = real
        self.extra = extra

    def __getitem__(self, k):
        return self.real[k] or self.extra.get(k, False)


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Tide Pool")
        self.save = load_save()
        self.fullscreen = bool(self.save["fullscreen"])
        self.pace = self.save.get("pace", "relaxed")
        flags = pygame.SCALED | pygame.RESIZABLE
        if self.fullscreen:
            flags |= pygame.FULLSCREEN
        try:
            self.screen = pygame.display.set_mode((WIN_W, WIN_H), flags)
        except Exception:
            self.fullscreen = False
            self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()
        self.fonts = {
            "title": pygame.font.SysFont("georgia,times new roman,serif", 46, bold=True),
            "h2": pygame.font.SysFont("georgia,times new roman,serif", 26, bold=True),
            "ad": pygame.font.SysFont("arial,helvetica,sans-serif", 20, bold=True),
            "ui": pygame.font.SysFont("arial,helvetica,sans-serif", 16, bold=True),
            "small": pygame.font.SysFont("arial,helvetica,sans-serif", 13),
            "tiny": pygame.font.SysFont("arial,helvetica,sans-serif", 11, bold=True),
        }
        self.ad = AdBanner(self.fonts)
        self.parts = Particles()
        self.world = pygame.Surface((WORLD_W, WORLD_H))
        self.build_backdrops()

        self.state = MENU
        self.prev_state = MENU
        self.next_level = self.save["level"]
        self.cleared_last = False
        self.level_i = self.save["level"]
        self.unlocked = self.save["unlocked"]
        self.run_pearls = self.save["pearls"]
        # wallet is the spendable purse and survives new runs; run_pearls is
        # just what this run has turned up.
        self.wallet = self.save["wallet"]
        self.owned = list(self.save["owned"])
        self.hat = self.save["hat"]
        self.dance_on = self.save["dance"]
        self.streak = self.save["streak"]
        self.clean = True            # no damage taken in this pool yet
        self.rainbow = self.streak >= RAINBOW_STREAK
        self.rain_t = 0.0
        self.earned_rainbow = False
        self.dlg_i = 0
        self.dlg_t = 0.0
        self.shop_msg = ""
        self.shop_msg_t = 0.0
        self.shop_from = MENU
        self.lost_pearls = 0
        self.wallet_in = self.wallet
        self.run_pearls_in = self.run_pearls
        self.max_hp = MAX_HP
        self.hp = MAX_HP
        self.shake = self.freeze = self.flash = 0.0
        self.fade = 1.0
        self.msg = ""
        self.msg_t = 0.0
        self.menu_t = 0.0
        self.L = LEVELS[0]
        self.gear_rect = pygame.Rect(WORLD_W - 40, 10, 30, 30)
        self.gear_spin = 0.0
        self.kelp = [(random.randint(0, WORLD_W), random.uniform(34, 70),
                      random.uniform(0, math.tau)) for _ in range(7)]
        self.buttons = []
        self.special = ""
        self.boss_done = False
        self.hatchlings = []
        self.currents, self.vents, self.anemones = [], [], []
        self.crumbles, self.turtles, self.shrimps, self.bubbles = [], [], [], []
        self.octopus = None
        self.solid = []
        self.trail_hist = []
        self.goal_nag = 0.0

        # -- touch controls ---------------------------------------------
        # one active pointer per id: "stick" claims the first touch that
        # lands in the left-hand zone, "jump" and "punch" are small round
        # buttons bottom-right. A real mouse click is tracked the same way
        # under the id "mouse", so the layout can be tried with a mouse on
        # desktop before it ever reaches a phone.
        self.touches = {}              # id -> "stick" | "jump" | "punch"
        self.stick_id = None
        self.stick_origin = (0.0, 0.0)
        self.stick_vec = (0.0, 0.0)    # -1..1 on each axis
        self.touch_jump_held = False
        self.stick_zone = pygame.Rect(0, AD_H + HUD_H, int(WIN_W * 0.58), WORLD_H)
        self.jump_btn = (WIN_W - 54, WIN_H - 62, 36)     # (cx, cy, r)
        self.punch_btn = (WIN_W - 130, WIN_H - 100, 31)

        self.build_menu()

    # -- precomputed gradients ----------------------------------------------

    def build_backdrops(self):
        sky = pygame.Surface((1, WORLD_H))
        for y in range(WORLD_H):
            sky.set_at((0, y), lerp3(C_SKY_TOP, C_SKY_BOT, (y / WORLD_H) ** 0.6))
        self.sky = pygame.transform.smoothscale(sky, (WORLD_W, WORLD_H))

        grad = pygame.Surface((1, WORLD_H), pygame.SRCALPHA)
        for y in range(WORLD_H):
            t = y / WORLD_H
            col = lerp3(C_WATER_TOP, C_WATER_MID, min(1.0, t * 2.4)) if t < 0.42 \
                else lerp3(C_WATER_MID, C_WATER_DEEP, (t - 0.42) / 0.58)
            grad.set_at((0, y), (*col, int(68 + 84 * t)))
        self.water_grad = pygame.transform.smoothscale(grad, (WORLD_W, WORLD_H))

    # -- menus ---------------------------------------------------------------

    def build_menu(self):
        cx = WORLD_W // 2
        self.buttons = [
            Button("CONTINUE", (cx - 105, 340, 210, 54), primary=True,
                   sub="Pool %d - %s" % (self.level_i + 1,
                                         LEVELS[min(self.level_i, len(LEVELS) - 1)]["name"])),
            Button("SHOP", (cx - 105, 402, 210, 44),
                   sub="%d pearl%s saved" % (self.wallet,
                                             "" if self.wallet == 1 else "s")),
            Button("QUIT", (cx - 105, 454, 210, 38)),
        ]

    def build_dead_menu(self):
        cx = WORLD_W // 2
        self.buttons = [
            Button("CONTINUE", (cx - 105, 330, 210, 50), primary=True,
                   sub="retry pool %d" % (self.level_i + 1)),
            Button("MAIN SCREEN", (cx - 105, 396, 210, 46)),
        ]

    def build_cleared_menu(self):
        cx = WORLD_W // 2
        self.buttons = [
            Button("PLAY AGAIN" if self.cleared_last else "CONTINUE",
                   (cx - 105, 346, 210, 50), primary=True,
                   sub="" if self.cleared_last else "pool %d" % (self.next_level + 1)),
            Button("MAIN SCREEN", (cx - 105, 412, 210, 46)),
        ]

    def build_settings_menu(self):
        cx = WORLD_W // 2
        self.buttons = [
            Button("FULLSCREEN: %s" % ("ON" if self.fullscreen else "OFF"),
                   (cx - 110, 236, 220, 48), sub="F11 toggles any time"),
            Button("PACE: %s" % self.pace.upper(), (cx - 110, 290, 220, 48),
                   sub="relaxed slows the tide and every hazard"),
            Button("CONTROLS", (cx - 110, 344, 220, 44),
                   sub="how to move, hop, punch, and grip"),
            Button("SHOP", (cx - 110, 394, 220, 44),
                   sub="%d pearl%s saved" % (self.wallet,
                                             "" if self.wallet == 1 else "s")),
            Button("NEW GAME", (cx - 110, 444, 220, 44),
                   sub="wipes pool progress, keeps your pearls"),
            Button("MAIN SCREEN", (cx - 110, 494, 220, 40)),
            Button("BACK", (cx - 110, 540, 220, 40), primary=True),
        ]

    def build_controls_menu(self):
        cx = WORLD_W // 2
        self.buttons = [
            Button("BACK", (cx - 105, 536, 210, 42), primary=True),
        ]

    def shop_state(self, it):
        """(label, sub, enabled) for one shop row, from what you own and
        what you can afford."""
        key, cost = it["key"], it["cost"]
        if key not in self.owned:
            can = self.wallet >= cost
            return ("BUY  %d" % cost,
                    it["blurb"] if can else "needs %d more pearl%s" % (
                        cost - self.wallet, "" if cost - self.wallet == 1 else "s"),
                    can)
        worn = (self.hat == key) if it["kind"] == "hat" else self.dance_on
        return ("TAKE OFF" if worn else "WEAR", it["blurb"], True)

    def build_shop_menu(self):
        cx = WORLD_W // 2
        self.buttons = []
        y = 262
        for it in SHOP_ITEMS:
            label, sub, enabled = self.shop_state(it)
            self.buttons.append(
                Button("%s: %s" % (it["name"], label), (cx - 130, y, 260, 48),
                       enabled=enabled, sub=sub))
            y += 60
        self.buttons.append(Button("BACK", (cx - 105, y + 8, 210, 42),
                                   primary=True))

    # -- persistence ---------------------------------------------------------

    def persist(self, level=None):
        write_save(dict(level=self.level_i if level is None else level,
                        unlocked=self.unlocked, pearls=self.run_pearls,
                        fullscreen=self.fullscreen, pace=self.pace,
                        wallet=self.wallet, owned=self.owned, hat=self.hat,
                        dance=self.dance_on, streak=self.streak))

    def toggle_fullscreen(self):
        """SCALED letterboxes the fixed playfield to whatever the display is,
        so fullscreen fills the monitor without distorting the art."""
        want = not self.fullscreen
        try:
            pygame.display.toggle_fullscreen()
            self.fullscreen = want
        except Exception:
            try:
                flags = pygame.SCALED | pygame.RESIZABLE
                if want:
                    flags |= pygame.FULLSCREEN
                self.screen = pygame.display.set_mode((WIN_W, WIN_H), flags)
                self.fullscreen = want
            except Exception:
                self.set_msg("This display cannot switch to fullscreen.", 2.5)
                return
        self.persist()

    # -- level lifecycle -----------------------------------------------------

    def start_level(self, i, reset_run=False):
        self.level_i = clamp(i, 0, len(LEVELS) - 1)
        L = LEVELS[self.level_i]
        if reset_run:
            self.run_pearls = 0
        self.L = L
        self.t = 0.0
        self.plats = [pygame.Rect(*p) for p in L["plats"]]
        self.urchins = [Urchin(*u) for u in L["urchins"]]
        self.eels = [Eel(*e) for e in L.get("eels", [])]
        self.jellies = [Jelly(*j) for j in L["jellies"]]
        self.puffers = [Puffer(*p) for p in L.get("puffers", [])]
        self.crawlers = [Crawler(pygame.Rect(*r), x, sp)
                         for (r, x, sp) in L.get("crawlers", [])]
        self.gulls = [Gull(*g) for g in L.get("gulls", [])]
        self.pearls = [Pearl(*p) for p in L["pearls"]]
        self.crab = Crab(*L["spawn"])
        # special pools: a level can carry special="gullking" (a boss you
        # can only beat by baiting it into rock) or hatchlings=[...] (an
        # escort). Either one keeps the goal shell shut until it's done.
        self.special = L.get("special", "")
        self.boss_done = False
        if self.special == "gullking":
            self.gulls.append(Gull(*L["boss"], boss=True))
        self.hatchlings = [Hatchling(*h) for h in L.get("hatchlings", [])]
        self.currents = [Current(*c) for c in L.get("currents", [])]
        self.vents = [Vent(*v) for v in L.get("vents", [])]
        self.anemones = [Anemone(*a) for a in L.get("anemones", [])]
        self.crumbles = [Crumble(*r) for r in L.get("crumbles", [])]
        self.turtles = [Turtle(*t) for t in L.get("turtles", [])]
        self.shrimps = [Shrimp(*sh) for sh in L.get("shrimps", [])]
        self.bubbles = []
        self.octopus = Octopus(*L["octopus"]) if self.special == "octopus" else None
        self.solid = list(self.plats)
        self.trail_hist = []
        self.goal_nag = 0.0
        self.clean = True            # rainbow mode is earned pool by pool
        # pearls only stick if you get out of the pool alive, so remember what
        # you walked in with and hand it back if you drown
        self.wallet_in = self.wallet
        self.run_pearls_in = self.run_pearls
        self.apply_pace()
        # a moment of grace so you are never hit before you can react
        self.crab.iframe = 2.6 if self.pace == "relaxed" else 1.4
        self.parts.clear()
        self.state = PLAY
        self.fade = 1.0
        self.shake = self.freeze = self.flash = 0.0
        self.set_msg(L["tip"], 4.0)
        self.persist()

    def apply_pace(self):
        """Relaxed stretches every hazard's cycle and slows every patrol, so
        there is more time to read the pool and fewer overlapping threats."""
        relaxed = self.pace == "relaxed"
        slow = 1.6 if relaxed else 1.0
        self.tide_mul = 1.3 if relaxed else 1.0
        self.max_hp = MAX_HP + (1 if relaxed else 0)
        self.hp = self.max_hp
        for e in self.eels:
            e.period *= slow
        for j in self.jellies:
            j.speed /= slow
            j.charge_time *= slow
        for pf in self.puffers:
            pf.speed /= slow
            pf.cycle *= slow
        for cw in self.crawlers:
            cw.speed /= slow
        for gl in self.gulls:
            gl.cool *= slow
        for sh in self.shrimps:
            sh.period *= slow ** 0.6
        for v in self.vents:
            v.period *= slow ** 0.4
        if self.octopus:
            self.octopus.ease = 1.25 if relaxed else 1.0

    def goal_open(self):
        if self.special in ("gullking", "octopus"):
            return self.boss_done
        if self.hatchlings:
            return all(h.state == "follow" for h in self.hatchlings)
        return True

    def set_msg(self, text, dur=2.2):
        self.msg, self.msg_t = text, dur

    def water_y(self):
        L = self.L
        ph = math.tau * self.t / (L["period"] * getattr(self, "tide_mul", 1.0))
        return L["tide_low"] + (L["tide_high"] - L["tide_low"]) * (0.5 - 0.5 * math.cos(ph))

    def rising(self):
        return math.sin(math.tau * self.t /
                        (self.L["period"] * getattr(self, "tide_mul", 1.0))) > 0

    # -- damage --------------------------------------------------------------

    def hurt(self, src_x, src_y, kind="hit"):
        c = self.crab
        if c.iframe > 0:
            return
        if kind == "zap":
            # caught in the discharge: the crab locks up, rattles, and the
            # shell lights up from the inside before it drops
            c.zap = ZAP_TIME
            self.parts.burst(c.x, c.y, 16, C_JELLY_HOT, 5.0, 0.55, 2.6, 0.0, True)
            self.parts.ring(c.x, c.y, 14, C_JELLY_HOT, 4.4, 0.45)
            self.flash = 0.4
            self.shake = max(self.shake, 14)
            self.freeze = max(self.freeze, 0.14)
        self.hp -= 1
        c.iframe = IFRAME_TIME
        # one hit ends the clean run: the streak resets and the rainbow goes
        self.clean = False
        self.streak = 0
        lost_rainbow = self.rainbow
        if lost_rainbow:
            self.rainbow = False
            self.parts.burst(c.x, c.y, 22, RAINBOW[2], 4.0, 0.6, 3.0, 0.1, True)
        c.vx = (1 if c.x >= src_x else -1) * 4.6
        c.vy = -4.4
        self.shake = max(self.shake, 11)
        self.freeze = 0.09
        self.flash = 0.25
        self.parts.burst(c.x, c.y, 18, C_CRAB, 4.4, 0.5, 3.0, 0.14)
        if self.hp <= 0:
            self.parts.burst(c.x, c.y, 30, C_CRAB_DARK, 5.6, 0.85, 3.4, 0.2)
            self.shake = 18
            # anything picked up in this pool washes away with you
            self.lost_pearls = self.wallet - self.wallet_in
            self.wallet = self.wallet_in
            self.run_pearls = self.run_pearls_in
            self.persist()
            self.state = DEAD
            self.build_dead_menu()
        elif any(h.state == "follow" for h in self.hatchlings):
            # the newest one in line loses its nerve and runs home
            newest = max((h for h in self.hatchlings if h.state == "follow"),
                         key=lambda h: h.slot)
            newest.state = "return"
            self.set_msg("The littlest one got scared and ran back.", 2.2)
        elif lost_rainbow:
            self.set_msg("Rainbow washed off. Streak reset.", 2.0)
        else:
            self.set_msg("%d hit%s left" % (self.hp - 1, "" if self.hp - 1 == 1 else "s"),
                         1.6)

    # -- update --------------------------------------------------------------

    def update_play(self, dt, keys):
        if self.freeze > 0:
            self.freeze -= dt
            return
        self.t += dt
        c = self.crab
        wy = self.water_y()

        # ---- moving and breaking ground goes first, so the crab stands on
        # where it is this frame. A crab on a turtle's shell rides with it.
        for tu in self.turtles:
            # (on_ground flickers on alternate frames as gravity re-seats the
            # crab, so go by where its feet are, not by the flag)
            riding = c.vy >= -0.5 and -1 <= tu.rect.top - (c.y + CRAB_H / 2) <= 4 and \
                tu.rect.left - CRAB_W / 2 + 2 < c.x < tu.rect.right + CRAB_W / 2 - 2
            tu.update(dt, wy)
            if riding:
                c.x += tu.dx
                c.y += tu.dy
            elif c.rect.colliderect(tu.rect) and c.y < tu.y:
                # the shell came up underneath: scoop the crab up, don't
                # shove it out sideways
                c.y = tu.rect.top - CRAB_H / 2
                c.vy = min(c.vy, tu.dy)
        for cr in self.crumbles:
            if cr.update(dt, c.rect) == "drop":
                for k in range(6):
                    self.parts.add(cr.rect.x + random.uniform(0, cr.rect.w), cr.rect.y + 6,
                                   random.uniform(-0.6, 0.6), random.uniform(0.5, 2.0),
                                   0.6, (214, 186, 140), random.uniform(2, 3.5), 0.25)
                self.shake = max(self.shake, 3)
        for cur in self.currents:
            cur.update(dt)
        for v in self.vents:
            v.update(dt)
        for an in self.anemones:
            an.update(dt)
        self.solid = self.plats + [cr.rect for cr in self.crumbles if cr.solid] + \
            [tu.rect for tu in self.turtles]

        left = keys[pygame.K_LEFT] or keys[pygame.K_a]
        right = keys[pygame.K_RIGHT] or keys[pygame.K_d]
        up = keys[pygame.K_UP] or keys[pygame.K_w]
        down = keys[pygame.K_DOWN] or keys[pygame.K_s]
        jump_held = keys[pygame.K_SPACE]

        depth = clamp(((c.y + CRAB_H / 2) - wy) / CRAB_H, 0, 1)
        in_water = depth > 0.08
        swimming = depth > 0.25
        can_launch = c.on_ground or depth > 0.30

        # the eight directions come straight off the buttons
        c.in_x = (1 if right else 0) - (1 if left else 0)
        c.in_y = (1 if down else 0) - (1 if up else 0)
        d = c.in_x
        if d:
            c.face = d

        held = c.in_x or c.in_y
        c.pose_amt = approach(c.pose_amt, 1.0 if held else 0.0, dt * (6.0 if held else 4.0))
        c.sx = approach(c.sx, float(c.in_x), dt * 7.0)
        c.sy = approach(c.sy, float(c.in_y), dt * 7.0)
        if held and swimming:
            c.kick += dt * 13.0

        # ---- idle dance. Any button at all resets it, and it only starts
        # with both feet on rock, so it can never interrupt a swim or a fall.
        busy = held or jump_held or c.punch_t > 0 or c.charging
        c.air_t = 0.0 if c.on_ground else c.air_t + dt
        settled = c.air_t < 0.14 and abs(c.vx) < 0.3 and abs(c.vy) < 1.6
        c.idle_t = 0.0 if (busy or not settled) else c.idle_t + dt
        want = 1.0 if (self.dance_on and c.idle_t >= DANCE_AFTER) else 0.0
        c.dance = approach(c.dance, want, dt * (3.4 if want else 9.0))
        if c.dance > 0.02:
            c.dance_t += dt * 7.4

        # holding down on rock grips it, so a rising tide cannot lift you off
        c.gripping = (c.in_y > 0) and c.on_ground

        if jump_held and can_launch:
            c.charging = True
            c.charge = min(CHARGE_TIME, c.charge + dt)
        elif c.charging:
            power = JUMP_MIN + (JUMP_MAX - JUMP_MIN) * (c.charge / CHARGE_TIME)
            if depth > 0.30:
                power *= 0.86
            c.vy = -power
            c.on_ground = False
            c.squash = -0.5
            self.parts.burst(c.x, c.y + 7, 8, C_FOAM if in_water else C_ROCK_LIT,
                             2.6, 0.33, 2.2, 0.16)
            if in_water:
                self.parts.splash(c.x, wy, 0.9)
            c.charging = False
            c.charge = 0.0
        else:
            c.charging = False
            c.charge = 0.0

        speed = SWIM_SPEED if swimming else WALK_SPEED
        if c.charging:
            speed *= 0.45
        if c.gripping:
            speed *= 0.5
        accel = WATER_ACCEL if swimming else GROUND_ACCEL
        c.vx += (d * speed - c.vx) * accel
        if not d:
            c.vx *= 0.90 if swimming else 0.74
        if swimming:
            for cur in self.currents:
                if cur.rect.collidepoint(c.x, c.y):
                    c.vx += cur.push * 0.09
                    if random.random() < 0.2:
                        self.parts.add(c.x - cur.push * 4, c.y + random.uniform(-6, 6),
                                       cur.push * 0.6, 0, 0.35, C_FOAM, 1.4)

        if c.gripping:
            c.vy += GRAVITY * 0.55          # clamped to the rock, not floating
        else:
            c.vy += GRAVITY * (1 - depth * BUOYANCY)
        if swimming:
            if c.in_y < 0:
                c.vy -= UP_THRUST
            elif c.in_y > 0:
                c.vy += DIVE_THRUST
            if c.in_y and random.random() < 0.35:
                self.parts.add(c.x - c.in_x * 9, c.y - c.in_y * 9,
                               -c.in_x * 0.8, -c.in_y * 0.9, 0.5, C_FOAM,
                               random.uniform(1.2, 2.4))
        if depth > 0:
            c.vy *= WATER_DRAG
        for v in self.vents:
            if v.power > 0.05 and not c.gripping and v.column().collidepoint(c.x, c.y + 4):
                c.vy -= 1.05 * v.power
                c.vy = max(c.vy, -7.5)
                c.on_ground = False
        # an anemone throws harder than any hop, so for a moment after one
        # the usual speed limit on rising is lifted
        c.sprung = max(0.0, getattr(c, "sprung", 0.0) - dt)
        c.vy = clamp(c.vy, -(Anemone.BOUNCE + 0.5) if c.sprung > 0 else -MAX_FALL, MAX_FALL)

        was_ground = c.on_ground
        c.on_ground = False
        c.x += c.vx
        r = c.rect
        for p in self.solid:
            if r.colliderect(p):
                if c.vx > 0:
                    c.x = p.left - CRAB_W / 2
                elif c.vx < 0:
                    c.x = p.right + CRAB_W / 2
                c.vx = 0
                r = c.rect
        c.x = clamp(c.x, CRAB_W / 2, WORLD_W - CRAB_W / 2)

        prev_bottom = c.y + CRAB_H / 2
        c.y += c.vy
        # ---- anemones: land on one and it throws you up, unless you hold
        # DOWN, which lets you settle on it
        if c.vy > 0:
            for an in self.anemones:
                if abs(c.x - an.x) < an.W / 2 + 4 and prev_bottom <= an.top + 3 and \
                        c.y + CRAB_H / 2 >= an.top:
                    c.y = an.top - CRAB_H / 2
                    if down:
                        c.vy = 0.0
                        c.on_ground = True
                    else:
                        c.vy = -Anemone.BOUNCE * (0.72 if depth > 0.3 else 1.0)
                        c.sprung = 0.6
                        an.squish = 1.0
                        c.squash = -0.6
                        c.on_ground = False
                        self.parts.burst(c.x, an.top, 10, (255, 150, 200), 3.0, 0.4, 2.2, 0.12)
                    break
        r = c.rect
        for p in self.solid:
            if r.colliderect(p):
                if c.vy > 0:
                    c.y = p.top - CRAB_H / 2
                    if c.vy > 5 and not was_ground:
                        c.squash = min(0.75, c.vy * 0.085)
                        self.parts.burst(c.x, c.y + 8, 6, C_ROCK_LIT, 2.4, 0.26, 2.2, 0.2)
                    c.on_ground = True
                elif c.vy < 0:
                    c.y = p.bottom + CRAB_H / 2
                c.vy = 0
                r = c.rect

        if c.on_ground:
            for cr in self.crumbles:
                if cr.solid and abs((c.y + CRAB_H / 2) - cr.rect.top) <= 1 and \
                        cr.rect.left - 6 < c.x < cr.rect.right + 6:
                    cr.step_on()

        # remember solid ground, so a fall costs a heart but not your progress
        if c.on_ground and c.iframe <= 0:
            c.safe_t += dt
            if c.safe_t > 0.35:
                c.safe_spot = (c.x, c.y)
        else:
            c.safe_t = 0.0

        if c.y > WORLD_H + 40:
            self.hurt(c.x, WORLD_H)
            c.x, c.y = c.safe_spot
            c.vx = c.vy = 0

        wet = (c.y + CRAB_H / 2) > wy
        if wet != c.was_wet and abs(c.vy) > 1.4:
            self.parts.splash(c.x, wy, clamp(abs(c.vy) / 6, 0.4, 1.5))
        c.was_wet = wet

        if abs(c.vx) > 0.4 and c.on_ground:
            c.walk += dt * 13
        c.squash = approach(c.squash, 0.0, dt * 3.4)
        c.zap = max(0.0, c.zap - dt)
        c.iframe = max(0.0, c.iframe - dt)
        c.punch_t = max(0.0, c.punch_t - dt)
        if c.punch_t <= 0:
            c.punch_hit = False
        c.punch_cd = max(0.0, c.punch_cd - dt)
        c.blink -= dt
        if c.blink < -0.12:
            c.blink = random.uniform(1.8, 4.5)
        # antennae lag behind the body
        for i in (0, 1):
            c.ant[i] += (-c.vx * 0.25 - c.ant[i]) * 0.12 + math.sin(self.t * 3 + i) * 0.012

        c.trail.insert(0, (c.x, c.y, c.squash))
        del c.trail[7:]

        if depth > 0.5 and random.random() < 0.08:
            self.parts.add(c.x + random.uniform(-7, 7), c.y,
                           random.uniform(-0.3, 0.3), -0.8,
                           0.9, C_FOAM, random.uniform(1.2, 2.3))

        for u in self.urchins:
            u.update(dt)
        for e in self.eels:
            e.update(dt)
        for pf in self.puffers:
            pf.update(dt)
        for cw in self.crawlers:
            cw.update(dt)
        for gl in self.gulls:
            gl.update(dt, c, depth < 0.25, self.solid)
            if gl.crash_pending:
                # it stooped at where you were and found rock instead
                spd = gl.crash_pending
                gl.crash_pending = 0.0
                away = -1.0 if c.x >= gl.x else 1.0
                drove_off = gl.take_hit(away * 2.2)
                self.parts.burst(gl.x, gl.y + 6, 16 if drove_off else 12,
                                 C_GULL, 4.4, 0.6, 2.8, 0.06)
                self.parts.burst(gl.x, gl.y + 7, 8, C_ROCK_LIT,
                                 3.4, 0.4, 2.2, 0.16)
                self.shake = max(self.shake, 7 + min(5, spd))
                self.freeze = max(self.freeze, 0.07)
                self.set_msg("The gull has had enough." if drove_off
                             else "Beak first into the rock.", 1.8)
        self.gulls = [g for g in self.gulls if not g.gone]
        if self.special == "gullking" and not self.boss_done and \
                not any(g.boss and not g.leaving for g in self.gulls):
            self.boss_done = True
            gx, gy = self.L["goal"]
            for col in RAINBOW:
                self.parts.burst(gx, gy, 8, col, 5.0, 0.9, 3.0, 0.06, True)
            self.shake = max(self.shake, 10)
            self.set_msg("The Gull King is beaten. The shell is open.", 3.0)

        # ---- the little ones: they walk in your footsteps
        self.trail_hist.insert(0, (c.x, c.y))
        del self.trail_hist[(len(self.hatchlings) + 2) * Hatchling.GAP:]
        for h in self.hatchlings:
            h.update(dt, self.trail_hist)
            if h.state == "wait" and math.hypot(h.x - c.x, h.y - c.y) < 22:
                h.state = "follow"
                h.slot = sum(1 for o in self.hatchlings
                             if o.state == "follow" and o is not h)
                self.parts.burst(h.x, h.y - 4, 10, C_CRAB_PALE, 2.6, 0.4, 2.0, 0.05, True)
                n = sum(1 for o in self.hatchlings if o.state == "follow")
                total = len(self.hatchlings)
                self.set_msg("All of them. Now take them up to the shell." if n == total
                             else "%d of %d little ones with you." % (n, total), 2.2)
        for j in self.jellies:
            if j.update(dt, wy) == "discharge":
                self.parts.ring(j.x, j.y, 20, C_JELLY_HOT, 5.2, 0.6)
                self.parts.burst(j.x, j.y, 12, C_JELLY, 3.2, 0.5, 2.6, 0.0, True)
                self.shake = max(self.shake, 6)

        # ---- pistol shrimp and their bubbles
        for sh in self.shrimps:
            if sh.update(dt) == "snap":
                bx = sh.x + sh.face * 15
                self.bubbles.append(Bubble(bx, sh.y - 2, sh.face * 3.6))
                self.parts.burst(bx, sh.y - 2, 8, C_FOAM, 3.0, 0.25, 2.0, 0.0, True)
                self.shake = max(self.shake, 2)
        for b in self.bubbles:
            b.update(dt)
            if any(b.rect().colliderect(p) for p in self.solid):
                b.dead = True
                self.parts.burst(b.x, b.y, 8, C_FOAM, 2.4, 0.3, 2.0, 0.0)
        self.bubbles = [b for b in self.bubbles if not b.dead]

        # ---- the Great Octopus
        if self.octopus:
            for arm in self.octopus.update(dt, c):
                tx, ty = arm.tgt
                self.parts.burst(tx, ty + 6, 16, C_ROCK_LIT, 4.2, 0.5, 2.8, 0.2)
                self.parts.splash(tx, min(ty, wy) if ty > wy else ty, 0.8)
                self.shake = max(self.shake, 9)
                if math.hypot(c.x - tx, c.y - ty) < 30:
                    self.hurt(tx, ty + 20)
            if self.octopus.beaten and not self.boss_done:
                self.boss_done = True
                gx, gy = self.L["goal"]
                for col in RAINBOW:
                    self.parts.burst(gx, gy, 8, col, 5.0, 0.9, 3.0, 0.06, True)
                self.parts.burst(self.octopus.x, self.octopus.y - 40, 40, (40, 20, 60), 5.0, 1.2, 4.0, 0.0)
                self.shake = max(self.shake, 16)
                self.set_msg("The Great Octopus lets go. The way up is open.", 3.4)

        # ---- punch resolution, against the claw circle the player can see
        if c.punch_active() and not c.punch_hit:
            px, py, pang, _reach = c.claw_point()
            kx, ky = math.cos(pang), math.sin(pang)

            def recoil(strength=1.6):
                c.vx -= kx * strength
                c.vy -= ky * strength * 0.7
                c.punch_hit = True

            done = False
            for e in self.eels:
                hit = e.punched(px, py, PUNCH_HIT_R, c.x)
                if hit:
                    self.parts.burst(hit[0], hit[1], 14, C_EEL_BELLY, 4.2, 0.42, 2.6, 0.1)
                    self.shake = max(self.shake, 7)
                    self.freeze = max(self.freeze, 0.07)
                    recoil()
                    done = True
                    break
            if not done:
                for j in self.jellies:
                    if j.punched(px, py, PUNCH_HIT_R):
                        if j.lit:
                            self.hurt(j.x, j.y)
                        else:
                            j.knock_back(kx * 9.0, ky * 7.0 - 1.5)
                            self.parts.burst(j.x, j.y, 16, C_JELLY, 4.6, 0.45,
                                             2.8, 0.05, True)
                            self.shake = max(self.shake, 8)
                            self.freeze = max(self.freeze, 0.08)
                            recoil(1.4)
                        done = True
                        break
            if not done:
                for pf in self.puffers:
                    if pf.punched(px, py, PUNCH_HIT_R):
                        if pf.spiky:
                            self.hurt(pf.x, pf.y)
                        else:
                            pf.knock_back(kx * 10.0, ky * 7.5 - 1.0)
                            self.parts.burst(pf.x, pf.y, 14, C_PUFFER, 4.4, 0.45, 2.6)
                            self.shake = max(self.shake, 8)
                            self.freeze = max(self.freeze, 0.08)
                            recoil(1.5)
                        done = True
                        break
            if not done:
                for cw in self.crawlers:
                    if cw.punched(px, py, PUNCH_HIT_R):
                        cw.flip = 3.2
                        cw.dir = 1 if kx >= 0 else -1
                        self.parts.burst(cw.x, cw.y, 12, C_STAR, 4.0, 0.42, 2.4, 0.1)
                        self.shake = max(self.shake, 7)
                        self.freeze = max(self.freeze, 0.07)
                        recoil(1.3)
                        done = True
                        break
            if not done:
                for gl in self.gulls:
                    if gl.punched(px, py, PUNCH_HIT_R) and gl.boss:
                        gl.shrug_off(kx * 7.0)
                        self.parts.burst(gl.x, gl.y, 8, C_GULL, 3.0, 0.4, 2.2, 0.1)
                        self.set_msg("Too big to punch. Make it meet the rock.", 1.8)
                        self.shake = max(self.shake, 5)
                        recoil(2.0)
                        done = True
                        break
                    if gl.punched(px, py, PUNCH_HIT_R):
                        drove_off = gl.take_hit(kx * 7.0)
                        self.parts.burst(gl.x, gl.y, 18 if drove_off else 14,
                                         C_GULL, 4.6, 0.5, 2.6, 0.1)
                        if drove_off:
                            self.set_msg("The gull has had enough.", 1.8)
                        self.shake = max(self.shake, 8)
                        self.freeze = max(self.freeze, 0.08)
                        recoil(1.4)
                        done = True
                        break
            if not done:
                for b in self.bubbles:
                    if b.punched(px, py, PUNCH_HIT_R):
                        b.dead = True
                        self.parts.burst(b.x, b.y, 12, C_FOAM, 3.4, 0.35, 2.2, 0.0, True)
                        recoil(0.6)
                        done = True
                        break
            if not done:
                for sh in self.shrimps:
                    if sh.punched(px, py, PUNCH_HIT_R):
                        sh.stun = 3.6
                        sh.t = 0.0
                        self.parts.burst(sh.x, sh.y, 12, (255, 150, 120), 3.8, 0.4, 2.4, 0.1)
                        self.shake = max(self.shake, 6)
                        self.freeze = max(self.freeze, 0.06)
                        recoil(1.3)
                        done = True
                        break
            if not done and self.octopus and not self.octopus.beaten:
                for arm in self.octopus.arms:
                    if arm.punchable(px, py, PUNCH_HIT_R):
                        res = self.octopus.take_hit(arm)
                        tx, ty = arm.tgt
                        self.parts.burst(tx, ty, 18, (190, 90, 150), 4.8, 0.5, 2.8, 0.1)
                        self.shake = max(self.shake, 9)
                        self.freeze = max(self.freeze, 0.1)
                        if res == "phase":
                            self.set_msg("It's angry now. Two arms at once." if self.octopus.phase == 2
                                         else "Last stand. They come faster now.", 2.6)
                        elif res == "hit":
                            self.set_msg("Got it!", 1.0)
                        recoil(1.8)
                        done = True
                        break
            if not done:
                for u in self.urchins:
                    if math.hypot(u.x - px, u.y - py) <= 11 + PUNCH_HIT_R:
                        self.hurt(u.x, u.y)
                        break

        cr = c.hurt_rect
        if c.iframe <= 0:
            for b in self.bubbles:
                if b.rect().colliderect(cr):
                    b.dead = True
                    self.parts.burst(b.x, b.y, 10, C_FOAM, 3.0, 0.3, 2.0, 0.0)
                    self.hurt(b.x, b.y)
                    break
        if c.iframe <= 0:
            for mob in (list(self.urchins) + list(self.eels) + list(self.jellies) +
                        list(self.puffers) + list(self.crawlers) + list(self.gulls)):
                if mob.hits(cr):
                    sx = getattr(mob, "x", None)
                    if sx is None:
                        sx, sy = mob.ax, mob.ay
                    else:
                        sy = mob.y
                    # a stoop that actually connects is spent: the bird pulls
                    # up rather than carrying on into the rock for a free hit
                    if isinstance(mob, Gull) and mob.state == "dive":
                        mob.state = "climb"
                        mob.cool = random.uniform(2.4, 4.0)
                    zap = isinstance(mob, Jelly) and mob.lit
                    self.hurt(sx, sy, "zap" if zap else "hit")
                    break

        for p in self.pearls:
            p.update(dt, c, self.solid, wy, self.parts)
            if not p.got and math.hypot(p.x - c.x, p.y - c.y) < 20:
                p.got = True
                self.run_pearls += 1
                self.wallet += 1          # spendable in the shop, and it keeps
                self.parts.burst(p.x, p.y, 14, C_SHELL, 3.6, 0.45, 2.4, 0.04, True)

        gx, gy = self.L["goal"]
        self.goal_nag = max(0.0, self.goal_nag - dt)
        at_goal = math.hypot(c.x - gx, c.y - gy) < 21
        if at_goal and not self.goal_open() and self.goal_nag <= 0:
            self.goal_nag = 3.0
            if self.special == "gullking":
                self.set_msg("Sealed while the Gull King rules the pool.", 2.4)
            elif self.special == "octopus":
                self.set_msg("The octopus won't let go of the way out. Not yet.", 2.4)
            else:
                left = sum(1 for h in self.hatchlings if h.state != "follow")
                self.set_msg("Not without the little ones - %d still out there." % left, 2.4)
        if at_goal and self.goal_open() and self.state == PLAY:
            self.cleared_last = self.level_i >= len(LEVELS) - 1
            self.next_level = min(self.level_i + 1, len(LEVELS) - 1)
            self.unlocked = max(self.unlocked, self.next_level)
            # a pool crossed without a scratch extends the streak; three in a
            # row and the shell goes rainbow until something lands a hit
            self.earned_rainbow = False
            if self.clean:
                self.streak += 1
                if self.streak >= RAINBOW_STREAK and not self.rainbow:
                    self.rainbow = True
                    self.earned_rainbow = True
            self.persist(level=self.next_level)
            self.parts.burst(gx, gy, 28, C_SHELL, 5.2, 0.85, 3.0, 0.08, True)
            if self.earned_rainbow:
                for i, col in enumerate(RAINBOW):
                    self.parts.burst(gx, gy, 9, col, 5.6, 0.9, 3.2, 0.06, True)
            self.shake = max(self.shake, 8)
            # the last pool says its piece before the clear card
            if self.cleared_last and self.L.get("dialogue"):
                self.state = DIALOGUE
                self.dlg_i = 0
                self.dlg_t = 0.0
                self.buttons = []
            else:
                self.state = CLEARED
                self.build_cleared_menu()

    # -- drawing: world ------------------------------------------------------

    def draw_backdrop(self, s, wy):
        s.blit(self.sky, (0, 0))
        # additive layers must carry LOW rgb - BLEND_ADD sums channels and
        # ignores alpha, so a bright colour at low alpha still blows out white
        glow = pygame.Surface((220, 220), pygame.SRCALPHA)
        for i in range(5, 0, -1):
            pygame.draw.circle(glow, (9, 8, 3), (110, 110), 22 * i)
        s.blit(glow, (WORLD_W - 190, -70), special_flags=pygame.BLEND_ADD)
        frond = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        for (kx, kh, kp) in self.kelp:
            sway = math.sin(self.t * 0.9 + kp) * 9
            base_y = WORLD_H - 18
            pts = [(kx, base_y)]
            for i in range(1, 6):
                f = i / 5
                pts.append((kx + sway * f * f, base_y - kh * f * 1.7))
            for w, col in ((6, (*C_KELP_DARK, 120)), (3, (*C_KELP, 150))):
                pygame.draw.lines(frond, col, False, pts, w)
            for i in range(1, 5):
                px, py = pts[i]
                pygame.draw.line(frond, (*C_KELP, 110), (px, py),
                                 (px + (9 if i % 2 else -9), py + 5), 2)
        s.blit(frond, (0, 0))

    def draw_water(self, s, wy):
        top = int(wy)
        h = WORLD_H - top
        if h > 0:
            s.blit(self.water_grad, (0, top), (0, 0, WORLD_W, h))

        def wave(x):
            return (wy + math.sin(x * 0.055 + self.t * 1.7) * 2.8
                    + math.sin(x * 0.021 - self.t * 1.1) * 1.6
                    + math.sin(x * 0.11 + self.t * 2.9) * 0.8)

        crest = [(x, wave(x)) for x in range(0, WORLD_W + 6, 6)]

        # a brighter sheet just under the surface: sky bouncing off the water
        if h > 10:
            sheet = pygame.Surface((WORLD_W, 26), pygame.SRCALPHA)
            pygame.draw.polygon(sheet, (*C_WATER_TOP, 110),
                                [(0, 26)] + [(x, y - wy + 10) for x, y in crest] +
                                [(WORLD_W, 26)])
            pygame.draw.polygon(sheet, (236, 255, 252, 46),
                                [(0, 13)] + [(x, y - wy + 10) for x, y in crest] +
                                [(WORLD_W, 13)])
            s.blit(sheet, (0, top - 10))

        # drifting motes, so the water has something suspended in it
        if h > 30:
            motes = pygame.Surface((WORLD_W, h), pygame.SRCALPHA)
            for i in range(22):
                mx = (i * 97 + math.sin(self.t * 0.4 + i) * 16) % WORLD_W
                my = (i * 53 + self.t * (7 + i % 5) * -1) % h
                a = 40 + int(30 * (0.5 + 0.5 * math.sin(self.t * 1.3 + i)))
                pygame.draw.circle(motes, (236, 255, 250, a), (int(mx), int(my)),
                                   1 if i % 3 else 2)
            s.blit(motes, (0, top))

        pygame.draw.lines(s, C_FOAM, False, crest, 2)
        # foam caps riding the crest
        for i in range(9):
            fx = (i * 57 + self.t * 22) % WORLD_W
            fy = wave(fx)
            slope = wave(fx + 6) - wave(fx - 6)
            w = 3 + abs(slope) * 1.6
            pygame.draw.ellipse(s, C_FOAM, (fx - w, fy - 3, w * 2, 4))
        # the crest line again, thinner and brighter, for a wet highlight
        pygame.draw.lines(s, (255, 255, 255), False,
                          [(x, y - 1.5) for x, y in crest], 1)

    def draw_light(self, s, wy):
        if wy >= WORLD_H - 4:
            return
        rays = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        for i in range(4):
            x = (i * 128 + math.sin(self.t * 0.4 + i) * 26) % (WORLD_W + 120) - 60
            w = 26 + i * 8
            pygame.draw.polygon(rays, (11, 16, 14),
                                [(x, wy), (x + w, wy),
                                 (x + w + 48, WORLD_H), (x - 16, WORLD_H)])
        s.blit(rays, (0, 0), special_flags=pygame.BLEND_ADD)
        # caustic ripples, kept to a band just under the surface
        band_h = int(min(70, WORLD_H - wy))
        if band_h > 12:
            band = pygame.Surface((WORLD_W, band_h), pygame.SRCALPHA)
            for i in range(9):
                cx = (i * 47 + math.sin(self.t * 1.2 + i) * 22) % WORLD_W
                cy = 14 + (i % 3) * 20
                if cy < band_h - 6:
                    pygame.draw.arc(band, (*C_CAUSTIC, 70),
                                    (cx - 14, cy - 5, 28, 10),
                                    0.4 + math.sin(self.t + i) * 0.2, 2.5, 1)
            s.blit(band, (0, int(wy)))

    def draw_plats(self, s, wy):
        for p in self.plats:
            shadow(s, p.centerx, p.bottom + 3, p.w // 2, 6, 60)
            pygame.draw.rect(s, C_ROCK, p, border_radius=3)
            pygame.draw.rect(s, C_ROCK_TOP, (p.x, p.y, p.w, 5), border_top_left_radius=3,
                             border_top_right_radius=3)
            pygame.draw.rect(s, C_ROCK_LIT, (p.x + 2, p.y, p.w - 4, 2))
            pygame.draw.rect(s, C_ROCK_DARK, (p.x, p.bottom - 4, p.w, 4))
            # speckle so the slabs read as rock, not blocks
            rnd = random.Random(p.x * 7919 + p.y)
            for _ in range(max(2, p.w // 26)):
                sx = rnd.randint(p.x + 4, max(p.x + 5, p.right - 5))
                sy = rnd.randint(p.y + 6, max(p.y + 7, p.bottom - 5))
                pygame.draw.circle(s, C_ROCK_DARK, (sx, sy), rnd.choice((1, 1, 2)))

    def relight_plats(self, s):
        """Warm rim light, redrawn after the water tint so submerged ledges
        keep a readable edge instead of going flat teal."""
        for p in self.plats:
            pygame.draw.rect(s, C_ROCK_TOP, (p.x, p.y, p.w, 3))
            pygame.draw.rect(s, C_ROCK_LIT, (p.x + 2, p.y, p.w - 4, 2))

    def draw_urchin(self, s, u):
        breathe = 1.0 + math.sin(u.breathe) * 0.06
        shadow(s, u.x, u.y + 11, 11, 4, 55)
        for i in range(14):
            a = u.spin + i * math.tau / 14
            ln = (13 if i % 2 else 10.5) * breathe
            pygame.draw.line(s, C_URCHIN,
                             (u.x + math.cos(a) * 5, u.y + math.sin(a) * 5),
                             (u.x + math.cos(a) * ln, u.y + math.sin(a) * ln), 2)
            pygame.draw.circle(s, C_URCHIN_LIT,
                               (int(u.x + math.cos(a) * ln), int(u.y + math.sin(a) * ln)), 1)
        pygame.draw.circle(s, C_URCHIN, (int(u.x), int(u.y)), int(7 * breathe))
        pygame.draw.circle(s, C_URCHIN_LIT, (int(u.x - 2), int(u.y - 2)), 2)

    def draw_eel(self, s, e):
        if not e.segments:
            return
        n = len(e.segments)
        body = C_EEL_BELLY if e.flash > 0 else C_EEL
        for (x, y, i) in e.segments:
            k = i / max(1, n - 1)
            r = int(e.R * (1.0 - 0.30 * k) + 1)
            pygame.draw.circle(s, C_EEL_DARK, (int(x), int(y)), r + 2)
            pygame.draw.circle(s, body, (int(x), int(y)), r)
            pygame.draw.circle(s, C_EEL_BELLY, (int(x - r * 0.35), int(y)), max(1, r // 3))
        hx, hy, _ = e.segments[-1]
        if n > 1:
            px, py, _ = e.segments[-2]
            ang = math.atan2(hy - py, hx - px)
        else:
            ang = e.base_angle()
        pygame.draw.circle(s, C_EEL_DARK, (int(hx), int(hy)), 11)
        pygame.draw.circle(s, body, (int(hx), int(hy)), 9)
        pygame.draw.circle(s, C_EEL_BELLY, (int(hx - math.cos(ang) * 2),
                                            int(hy - math.sin(ang) * 2)), 4)
        ox, oy = math.cos(ang + 1.3) * 4.0, math.sin(ang + 1.3) * 4.0
        for sgn in (1, -1):
            ex, ey = hx + ox * sgn, hy + oy * sgn
            pygame.draw.circle(s, C_WHITE, (int(ex), int(ey)), 3)
            pygame.draw.circle(s, C_INK, (int(ex + math.cos(ang) * 1.2),
                                          int(ey + math.sin(ang) * 1.2)), 2)
        gape = e.gape * 8
        for sgn in (1, -1):
            a = ang + sgn * (0.30 + e.gape * 0.55)
            tip = (hx + math.cos(a) * (10 + gape), hy + math.sin(a) * (10 + gape))
            pygame.draw.line(s, C_EEL_DARK,
                             (hx + math.cos(ang) * 3, hy + math.sin(ang) * 3), tip, 5)
            pygame.draw.line(s, C_EEL_BELLY,
                             (hx + math.cos(ang) * 3, hy + math.sin(ang) * 3), tip, 2)
        pygame.draw.circle(s, C_ROCK_DARK, (int(e.ax), int(e.ay)), 10)
        pygame.draw.circle(s, (12, 26, 30), (int(e.ax), int(e.ay)), 7)

    def draw_jelly(self, s, j):
        wet = 1.0 - j.droop
        b = j.bright() * wet          # no charge-glow once it's drying out
        col = lerp3(lerp3(C_JELLY, C_JELLY_HOT, b), C_JELLY_DRY, j.droop * 0.8)
        dark = lerp3(lerp3(C_JELLY_DARK, C_JELLY_HOT, b * 0.6),
                     C_JELLY_DRY_DARK, j.droop * 0.8)
        if j.droop > 0.5:
            shadow(s, j.x, j.y + Jelly.R * 0.6, int(Jelly.R * 1.3), 4,
                  int(50 * j.droop))
        if j.lit and not j.stranded:
            k = clamp(j.shock / Jelly.SHOCK_TIME, 0, 1)
            rad = int(Jelly.SHOCK_R * (1.05 - 0.25 * k))
            ring = pygame.Surface((rad * 2 + 6, rad * 2 + 6), pygame.SRCALPHA)
            for i in range(3):
                pygame.draw.circle(ring, (26, 25, 9),
                                   (rad + 3, rad + 3), int(rad * (0.6 + 0.2 * i)))
            s.blit(ring, (int(j.x) - rad - 3, int(j.y) - rad - 3),
                   special_flags=pygame.BLEND_ADD)
            pygame.draw.circle(s, C_JELLY_HOT, (int(j.x), int(j.y)), rad, 3)
            for i in range(12):
                a = math.tau * i / 12 + j.pulse
                r1 = rad * 0.4
                mid = rad * 0.72
                jag = rad * random.uniform(0.85, 1.0)
                pygame.draw.lines(s, C_JELLY_HOT, False, [
                    (j.x + math.cos(a) * r1, j.y + math.sin(a) * r1),
                    (j.x + math.cos(a + 0.26) * mid, j.y + math.sin(a + 0.26) * mid),
                    (j.x + math.cos(a - 0.1) * jag, j.y + math.sin(a - 0.1) * jag)], 2)
        elif b > 0.35:
            halo = pygame.Surface((70, 70), pygame.SRCALPHA)
            g = int(26 * b)
            pygame.draw.circle(halo, (g, g, g // 3), (35, 35), int(16 + 10 * b))
            s.blit(halo, (int(j.x) - 35, int(j.y) - 35), special_flags=pygame.BLEND_ADD)

        # the bell pumps: it squeezes tall as it pushes, then spreads wide.
        # dried out, it stops pumping and sags - wider and flatter, resting
        # its weight on the rock instead of holding its shape in the water
        squash = 1.0 + math.sin(j.pulse) * 0.13 * wet
        rw = Jelly.R * squash * (1.0 + 0.22 * j.droop)
        rh = Jelly.R * 0.88 / squash * (1.0 - 0.4 * j.droop)
        k_ch = 0.0 if (j.lit or j.stranded) else clamp(j.charge / j.charge_time, 0, 1)

        hem = j.y + rh * 0.34          # where the bell ends and the trailing
        # ---- seven fine stingers, long and drifting, drawn behind everything.
        # out of water they go limp: less sway, and they lie close instead of
        # trailing out
        swayk = wet * (1.0 - 0.6 * j.droop)
        for i in range(-3, 4):
            x0 = j.x + i * (rw * 0.26)
            ln = 5 + (3 - abs(i))                 # longest in the middle
            pts = [(x0, hem)]
            for k in range(1, ln):
                sway = math.sin(j.pulse * 0.8 + i * 0.9 - k * 0.42) * (1.0 + k * 0.8) * swayk
                pts.append((x0 + sway, hem + k * 6.4 * (1.0 - 0.3 * j.droop)))
            pygame.draw.lines(s, dark, False, pts, 1)
            if j.lit:
                pygame.draw.circle(s, C_JELLY_HOT,
                                   (int(pts[-1][0]), int(pts[-1][1])), 1)

        # ---- four oral arms: short, thick, ruffled, hanging under the bell
        for i in (-1.5, -0.5, 0.5, 1.5):
            x0 = j.x + i * (rw * 0.36)
            pts = [(x0, hem - 2)]
            for k in range(1, 4):
                pts.append((x0 + math.sin(j.pulse * 1.2 + i * 2 - k * 0.8) * (1.6 * k) * swayk,
                            hem - 2 + k * 4.6))
            pygame.draw.lines(s, dark, False, pts, 4)
            pygame.draw.lines(s, col, False, pts, 2)

        # ---- the bell itself: a dome with a scalloped hem, not a circle
        dome = [(j.x + math.cos(math.pi + math.pi * k / 14) * rw,
                 j.y + math.sin(math.pi + math.pi * k / 14) * rh)
                for k in range(15)]
        for k in range(7):                        # hem, right back to left
            t = k / 6.0
            dome.append((j.x + rw - 2 * rw * t,
                         hem + math.sin(t * math.pi * 3 + j.pulse) * 1.8))
        pygame.draw.polygon(s, col, dome)
        pygame.draw.polygon(s, dark, dome, 2)

        # soft inner light, brightening as it charges
        gl = pygame.Surface((int(rw * 2), int(rh * 2.4)), pygame.SRCALPHA)
        q = int(30 + 90 * b)
        pygame.draw.ellipse(gl, (*C_JELLY_HOT, q),
                            (int(rw * 0.3), int(rh * 0.5),
                             int(rw * 1.4), int(rh * 1.3)))
        s.blit(gl, (j.x - rw, j.y - rh * 0.9))

        # four small horseshoe markings, the giveaway that it is a jellyfish
        for i in (-1, 1):
            for jj in (-1, 1):
                mr = pygame.Rect(0, 0, int(rw * 0.34), int(rh * 0.34))
                mr.center = (int(j.x + i * rw * 0.40), int(j.y + jj * rh * 0.22))
                pygame.draw.arc(s, lerp3(C_WHITE, C_JELLY_HOT, b), mr,
                                math.pi * 0.1, math.pi * 1.15, 2)
        pygame.draw.arc(s, lerp3(C_WHITE, dark, j.droop * 0.7),
                        (int(j.x - rw * 0.8), int(j.y - rh * 0.8),
                         int(rw * 1.1), int(rh * 1.1)), 0.9, 2.3, 2)

        # charge meter reads as a filling arc around the bell
        if k_ch > 0.05:
            ring_r = pygame.Rect(int(j.x - rw - 5), int(j.y - rh - 5),
                                 int(rw * 2 + 10), int(rh * 2 + 10))
            pygame.draw.arc(s, C_JELLY_HOT, ring_r,
                            math.pi / 2, math.pi / 2 + math.tau * k_ch, 2)
        # about to go off: sparks jump the rim
        if k_ch > 0.8 and random.random() < 0.45:
            a = random.uniform(0, math.tau)
            p0 = (j.x + math.cos(a) * rw, j.y + math.sin(a) * rh)
            p1 = (p0[0] + math.cos(a) * 6, p0[1] + math.sin(a) * 6)
            pygame.draw.line(s, C_JELLY_HOT, p0, p1, 2)
        if j.knock > 0:
            pygame.draw.arc(s, C_WHITE,
                            (int(j.x - rw - 5), int(j.y - rh - 5),
                             int(rw * 2 + 10), int(rh * 2 + 10)),
                            j.spin, j.spin + 1.2, 2)

    def draw_puffer(self, s, pf):
        r = pf.radius
        wob = math.sin(pf.wob) * 0.6
        shadow(s, pf.x, pf.y + r + 3, int(r * 0.8), 3, 45)
        if pf.puff > 0.15:
            for i in range(14):
                a = math.tau * i / 14 + pf.wob * 0.1
                ln = r + 3 + 7 * pf.puff
                pygame.draw.line(s, C_PUFFER_DARK,
                                 (pf.x + math.cos(a) * (r - 2),
                                  pf.y + math.sin(a) * (r - 2)),
                                 (pf.x + math.cos(a) * ln,
                                  pf.y + math.sin(a) * ln), 2)
        pygame.draw.circle(s, C_PUFFER_DARK, (int(pf.x), int(pf.y)), int(r + 1.5))
        pygame.draw.circle(s, C_PUFFER, (int(pf.x), int(pf.y)), int(r + wob))
        pygame.draw.arc(s, (255, 226, 170),
                        (pf.x - r + 3, pf.y - r + 2, r * 2 - 6, r * 2 - 4), 0.6, 2.3, 2)
        for i in range(3):
            pygame.draw.circle(s, C_PUFFER_DARK,
                               (int(pf.x - 4 + i * 5), int(pf.y + 2 + (i % 2) * 3)), 1)
        # tail and fins
        tf = -pf.face
        pygame.draw.polygon(s, C_PUFFER_DARK, [
            (pf.x + tf * r, pf.y),
            (pf.x + tf * (r + 8), pf.y - 6 + wob),
            (pf.x + tf * (r + 8), pf.y + 6 - wob)])
        ex = pf.x + pf.face * r * 0.45
        pygame.draw.circle(s, C_WHITE, (int(ex), int(pf.y - r * 0.3)), 4)
        pygame.draw.circle(s, C_INK, (int(ex + pf.face), int(pf.y - r * 0.3)), 2)
        pygame.draw.arc(s, C_PUFFER_DARK,
                        (ex - 2, pf.y + 1, 9, 6), 3.4, 6.0, 2)

    def draw_crawler(self, s, cw):
        shadow(s, cw.x, cw.plat.top + 2, 10, 3, 55)
        flipped = cw.flipped
        base = C_STAR_DARK if flipped else C_STAR
        tip = C_STAR if flipped else (255, 168, 150)
        wob = math.sin(cw.wob) * 0.12
        for i in range(5):
            a = -math.pi / 2 + math.tau * i / 5 + cw.spin + (math.pi if flipped else 0)
            ln = cw.R + (1.6 if i % 2 else -0.6) + wob * 6
            x2, y2 = cw.x + math.cos(a) * ln, cw.y + math.sin(a) * ln * 0.8
            pygame.draw.line(s, C_STAR_DARK, (cw.x, cw.y), (x2, y2), 7)
            pygame.draw.line(s, base, (cw.x, cw.y), (x2, y2), 4)
            pygame.draw.circle(s, tip, (int(x2), int(y2)), 2)
        pygame.draw.circle(s, C_STAR_DARK, (int(cw.x), int(cw.y)), 6)
        pygame.draw.circle(s, base, (int(cw.x), int(cw.y)), 4)
        if flipped:
            for sgn in (-1, 1):
                pygame.draw.line(s, C_INK, (cw.x + sgn * 3 - 2, cw.y - 2),
                                 (cw.x + sgn * 3 + 2, cw.y + 2), 2)
                pygame.draw.line(s, C_INK, (cw.x + sgn * 3 - 2, cw.y + 2),
                                 (cw.x + sgn * 3 + 2, cw.y - 2), 2)
        else:
            pygame.draw.circle(s, C_INK, (int(cw.x + cw.dir * 2), int(cw.y - 1)), 2)

    def draw_gull(self, s, gl):
        f = gl.face
        diving = gl.state == "dive"
        sad = gl.leaving
        flap = math.sin(gl.flap)
        body_col = C_WHITE if gl.hurt_flash > 0 else C_GULL
        if not sad:
            shadow(s, gl.x, gl.y + 30, 11, 3, 28)
        # tail fan behind
        pygame.draw.polygon(s, C_GULL_DARK, [
            (gl.x - f * 8, gl.y - 3), (gl.x - f * 21, gl.y - 6),
            (gl.x - f * 20, gl.y + 4), (gl.x - f * 8, gl.y + 4)])
        pygame.draw.polygon(s, body_col, [
            (gl.x - f * 8, gl.y - 2), (gl.x - f * 19, gl.y - 4),
            (gl.x - f * 18, gl.y + 3), (gl.x - f * 8, gl.y + 3)])
        # far wing first, then body, then near wing, so it layers like a bird
        for order, sgn in ((0, -1), (1, 1)):
            if order == 1:
                pygame.draw.ellipse(s, C_GULL_DARK, (gl.x - 13, gl.y - 9, 26, 18))
                pygame.draw.ellipse(s, body_col, (gl.x - 12, gl.y - 8, 24, 16))
                pygame.draw.arc(s, C_GULL_DARK,
                                (gl.x - 10, gl.y - 4, 20, 12), 3.4, 6.0, 2)
            if diving:                      # swept into a stoop
                root = (gl.x - f * 2, gl.y - 4)
                mid = (gl.x - f * 9, gl.y - 11 + sgn * 2)
                tip = (gl.x - f * 17, gl.y - 20 + sgn * 3)
                elb = (gl.x - f * 6, gl.y - 3 + sgn * 2)
            else:                           # slow beat
                lift = flap * 10 * (1.0 if sgn > 0 else 0.82)
                root = (gl.x - f * 1, gl.y - 4)
                mid = (gl.x + sgn * 11 - f * 2, gl.y - 7 + lift)
                tip = (gl.x + sgn * 23 - f * 3, gl.y - 4 + lift * 1.5)
                elb = (gl.x + sgn * 10, gl.y + 1 + lift * 0.5)
            pygame.draw.polygon(s, C_GULL_DARK, [root, mid, tip, elb])
            pygame.draw.polygon(s, body_col, [root, mid, (tip[0] * 0.82 + elb[0] * 0.18,
                                                        tip[1] * 0.82 + elb[1] * 0.18),
                                            elb])
            pygame.draw.circle(s, (54, 64, 72), (int(tip[0]), int(tip[1])), 3)
        hx, hy = gl.x + f * 10, gl.y - 7
        if sad:
            hx, hy = gl.x - f * 4, gl.y - 12       # head hangs, looking back
        pygame.draw.circle(s, C_GULL_DARK, (int(hx), int(hy)), 7)
        pygame.draw.circle(s, body_col, (int(hx), int(hy)), 6)
        if sad:
            # downcast eye, a drooping brow and a tear
            pygame.draw.arc(s, C_INK, (hx + f * 0.5 - 3, hy - 2, 6, 6),
                            3.5, 6.0, 2)
            pygame.draw.line(s, C_INK, (hx + f * 0.5 - 3, hy - 3),
                             (hx + f * 0.5 + 2, hy - 4), 1)
            pygame.draw.circle(s, (120, 190, 230), (int(hx + f), int(hy + 4)), 2)
            pygame.draw.polygon(s, C_GULL_BEAK, [
                (hx - f * 3, hy + 1), (hx - f * 13, hy + 7), (hx - f * 3, hy + 5)])
            # a downturned mouth line under the beak root
            pygame.draw.arc(s, C_GULL_DARK, (hx - f * 8 - 4, hy + 4, 9, 7),
                            0.5, 2.6, 1)
        else:
            pygame.draw.circle(s, C_INK, (int(hx + f * 2), int(hy - 1)), 2)
            pygame.draw.circle(s, C_WHITE, (int(hx + f * 2.6), int(hy - 1.8)), 1)
            pygame.draw.polygon(s, C_GULL_BEAK, [
                (hx + f * 4, hy - 1), (hx + f * 15, hy + (4 if diving else 1)),
                (hx + f * 4, hy + 4)])
            pygame.draw.line(s, (214, 134, 30), (hx + f * 6, hy + 1),
                             (hx + f * 13, hy + (3 if diving else 1.5)), 1)
        if diving:
            for sgn in (-1, 1):
                pygame.draw.line(s, C_GULL_BEAK, (gl.x + sgn * 3, gl.y + 8),
                                 (gl.x + sgn * 3 - f * 6, gl.y + 14), 2)

        # seeing stars after a face full of rock
        if gl.daze > 0:
            for k in range(3):
                a = self.menu_t * 5.2 + math.tau * k / 3
                sx_ = gl.x + math.cos(a) * 13
                sy_ = gl.y - 15 + math.sin(a) * 4
                col = (255, 226, 92) if k != 1 else C_WHITE
                for d in range(3):
                    aa = math.pi * d / 3 + a * 0.4
                    pygame.draw.line(s, col,
                                     (sx_ - math.cos(aa) * 3, sy_ - math.sin(aa) * 3),
                                     (sx_ + math.cos(aa) * 3, sy_ + math.sin(aa) * 3), 1)

    def draw_pearl(self, s, p):
        if p.got:
            return
        y = p.y + math.sin(p.bob) * 1.4
        shadow(s, p.x, y + 8, 6, 2.5, 45)
        halo = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(halo, (22, 17, 4), (15, 15), 10)
        s.blit(halo, (int(p.x) - 15, int(y) - 15), special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(s, C_SHELL_DARK, (int(p.x), int(y)), Pearl.R + 1)
        pygame.draw.circle(s, C_SHELL, (int(p.x), int(y)), Pearl.R)
        hx = p.x + math.cos(p.spin) * 1.6
        pygame.draw.circle(s, C_WHITE, (int(hx - 1.6), int(y - 2)), 2)

    def draw_goal(self, s):
        gx, gy = self.L["goal"]
        if not self.goal_open():
            # shut: no glow, no sparkle, a closed grey shell with a seam
            pts = [(gx + math.cos(math.pi + math.pi * i / 12) * 15,
                    gy + 9 + math.sin(math.pi + math.pi * i / 12) * 15)
                   for i in range(13)]
            pygame.draw.polygon(s, (120, 116, 108), pts)
            inner = [(gx + (x - gx) * 0.84, gy + 9 + (y - (gy + 9)) * 0.84)
                     for x, y in pts]
            pygame.draw.polygon(s, (168, 162, 150), inner)
            for i in range(-3, 4):
                pygame.draw.line(s, (120, 116, 108), (gx, gy + 8),
                                 (gx + i * 4.0, gy - 5), 1)
            pygame.draw.line(s, (90, 86, 80), (gx - 15, gy + 9), (gx + 15, gy + 9), 3)
            return
        glow = 0.5 + 0.5 * math.sin(self.t * 2.4)
        halo = pygame.Surface((90, 90), pygame.SRCALPHA)
        for i in range(3):
            pygame.draw.circle(halo, (16, 12, 3), (45, 45), int(16 + glow * 8 + i * 7))
        s.blit(halo, (gx - 45, gy - 45), special_flags=pygame.BLEND_ADD)
        if random.random() < 0.25:
            self.parts.sparkle(gx, gy - 4)
        wob = math.sin(self.t * 1.6) * 0.6
        pts = []
        for i in range(13):
            a = math.pi + math.pi * i / 12
            scallop = 1.0 if i in (0, 12) else (1.0 + 0.06 * math.sin(i * 3.0))
            pts.append((gx + math.cos(a) * 15,
                        gy + 9 + math.sin(a) * (16 + wob) * scallop))
        pygame.draw.polygon(s, C_SHELL_DARK, pts)
        inner = [(gx + (x - gx) * 0.84, gy + 9 + (y - (gy + 9)) * 0.84) for x, y in pts]
        pygame.draw.polygon(s, C_SHELL, inner)
        for i in range(-3, 4):
            pygame.draw.line(s, C_SHELL_DARK, (gx, gy + 8), (gx + i * 4.0, gy - 5), 1)
        pygame.draw.line(s, C_SHELL_DARK, (gx - 15, gy + 9), (gx + 15, gy + 9), 2)

    def draw_rainbow_shell(self, s, pts, cx, cy):
        """Slanted rainbow bands running left to right across the shell.

        The bands are painted on their own surface and multiplied by a mask of
        the shell polygon, so the colour stops exactly at the shell edge
        instead of bleeding over the legs and eyes."""
        pad, W, H = 26, 0, 0
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ox, oy = min(xs) - pad, min(ys) - pad
        W = int(max(xs) - min(xs) + pad * 2)
        H = int(max(ys) - min(ys) + pad * 2)
        if W <= 0 or H <= 0:
            return

        bands = pygame.Surface((W, H), pygame.SRCALPHA)
        bw_band = 7
        span = bw_band * len(RAINBOW)
        scroll = (self.rain_t * 54.0) % span
        k = 0
        x0 = -H - span - scroll
        while x0 < W + span:
            col = RAINBOW[k % len(RAINBOW)]
            pygame.draw.polygon(bands, (*col, 255), [
                (x0, 0), (x0 + bw_band, 0),
                (x0 + bw_band - H * 0.6, H), (x0 - H * 0.6, H)])
            x0 += bw_band
            k += 1

        mask = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.draw.polygon(mask, (255, 255, 255, 255),
                            [(x - ox, y - oy) for (x, y) in pts])
        bands.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        bands.set_alpha(200)
        s.blit(bands, (ox, oy))

    def draw_hat(self, s, P, bh, pitch, dnc):
        """Whatever is equipped, worn on the eyestalks and tilting with the
        body. Drawn last so it sits over the eyes, not under them."""
        # the brim rides above the eyestalk tips (about -bh-10) so the hat
        # perches on the stalks and the eyes still read
        base = -bh - 10.5
        if self.hat == "tophat":
            crown = [P(-6.0, base), P(6.0, base),
                     P(6.0, base - 12), P(-6.0, base - 12)]
            pygame.draw.polygon(s, (28, 28, 34), crown)
            pygame.draw.polygon(s, (10, 10, 14), crown, 1)
            band = [P(-6.0, base - 2.0), P(6.0, base - 2.0),
                    P(6.0, base - 4.6), P(-6.0, base - 4.6)]
            pygame.draw.polygon(s, (168, 42, 48), band)
            pygame.draw.line(s, (28, 28, 34), P(-10, base), P(10, base), 4)
            pygame.draw.line(s, (84, 84, 94), P(-3.5, base - 10.5),
                             P(1.5, base - 10.5), 1)
        elif self.hat == "spinner":
            hc = P(0, base)
            r = 9.5
            for i, col in enumerate(RAINBOW):
                a0 = math.pi + math.pi * i / len(RAINBOW) + pitch
                a1 = math.pi + math.pi * (i + 1) / len(RAINBOW) + pitch
                pygame.draw.polygon(s, col, [
                    hc,
                    (hc[0] + math.cos(a0) * r, hc[1] + math.sin(a0) * r),
                    (hc[0] + math.cos((a0 + a1) / 2) * r,
                     hc[1] + math.sin((a0 + a1) / 2) * r),
                    (hc[0] + math.cos(a1) * r, hc[1] + math.sin(a1) * r)])
            pygame.draw.line(s, (250, 248, 242), P(-10, base), P(10, base), 3)
            top = P(0, base - 11)
            pygame.draw.line(s, (62, 62, 70), P(0, base - 8.5), top, 2)
            # propeller: spins faster while the crab is dancing
            spin = self.rain_t * (9.0 + 11.0 * dnc)
            for j in (0, 1):
                a = spin + j * math.pi
                tip = (top[0] + math.cos(a) * 12, top[1] + math.sin(a) * 3.6)
                mid = (top[0] + math.cos(a) * 6.5, top[1] + math.sin(a) * 2.2 - 3.0)
                blade = [top, mid, tip]
                pygame.draw.polygon(s, RAINBOW[(j * 3) % len(RAINBOW)], blade)
                pygame.draw.polygon(s, (52, 44, 40), blade, 1)
            pygame.draw.circle(s, (248, 244, 236), (int(top[0]), int(top[1])), 2)

    def draw_crab(self, s, c, ghost=False):
        # the post-hit flicker is suppressed while the shock plays, so the
        # electrocution is actually visible instead of strobing in and out
        if c.zap <= 0 and c.iframe > 0 and int(c.iframe * 22) % 2 == 0:
            return
        if not ghost:
            # motion ghosts when moving fast
            if abs(c.vx) > 2.0 or abs(c.vy) > 5.0:
                for i, (tx, ty, _tsq) in enumerate(c.trail[2::2]):
                    gsurf = pygame.Surface((46, 40), pygame.SRCALPHA)
                    pygame.draw.ellipse(gsurf, (*C_CRAB, 38 - i * 12),
                                        (10, 12, 26, 16))
                    s.blit(gsurf, (tx - 23, ty - 20))
            # contact shadow on the nearest surface below
            best = None
            for p in self.plats:
                if p.left - 8 < c.x < p.right + 8 and p.top >= c.y:
                    if best is None or p.top < best:
                        best = p.top
            if best is not None and best - c.y < 150:
                k = 1.0 - (best - c.y) / 150.0
                shadow(s, c.x, best + 2, int(13 * (0.5 + 0.5 * k)),
                       int(4 * (0.5 + 0.5 * k)), int(80 * k))

        sq = c.squash + (0.35 * (c.charge / CHARGE_TIME) if c.charging else 0.0)
        bw, bh = 13 * (1.0 + sq * 0.55), 8 * (1.0 - sq * 0.55)
        cx, cy = c.x, c.y + (8 * sq * 0.5)
        f = c.face
        amt = c.pose_amt

        # ---- electrocuted: the whole crab rattles in place, legs stiff out
        zap = clamp(c.zap / ZAP_TIME, 0.0, 1.0)
        if zap > 0:
            cx += random.uniform(-2.6, 2.6) * zap
            cy += random.uniform(-2.2, 2.2) * zap

        # ---- idle dance: sway, bob, and a rocking roll. Purely drawn - it
        # moves nothing, and any button drops it before the next frame.
        dnc = c.dance
        if dnc > 0.01:
            cx += math.sin(c.dance_t) * 3.4 * dnc
            cy += abs(math.sin(c.dance_t * 2.0)) * -2.6 * dnc
            bw *= 1.0 + 0.06 * math.sin(c.dance_t * 2.0) * dnc

        # ---- pose, driven by the held direction only (never by velocity)
        pitch = 0.42 * c.sy * f * amt + (math.sin(c.dance_t) * 0.34 * dnc)
        cosp, sinp = math.cos(pitch), math.sin(pitch)

        def P(lx, ly):
            """local body space -> screen, through the pitch rotation"""
            return (cx + lx * cosp - ly * sinp, cy + lx * sinp + ly * cosp)

        # ---- legs: six, trailing away from the direction of travel
        swim = abs(c.sx) + abs(c.sy) > 0.05
        cyc = c.kick if swim else c.walk
        trail_x = -c.sx * 3.2 * amt
        trail_y = -c.sy * 3.6 * amt
        for i in (-1, 0, 1):
            for sgn in (-1, 1):
                ph = math.sin(cyc + i * 0.8 + (0 if sgn > 0 else math.pi)) * \
                    (3.8 if swim else 3.4)
                if zap > 0:          # legs lock out straight and judder
                    ph = ph * (1 - zap) + random.uniform(-2.6, 2.6) * zap
                hip = P(i * 6, 2)
                knee = P(i * 6 + sgn * (3 + 2.5 * zap) + trail_x * 0.5,
                         5 + trail_y * 0.5 - 2.0 * zap)
                foot = P(i * 6 + sgn * (6 + 5.0 * zap), 10 + trail_y + ph)
                pygame.draw.lines(s, C_CRAB_DARK, False, [hip, knee, foot], 3)
                pygame.draw.lines(s, C_CRAB, False, [hip, knee, foot], 1)

        # ---- shell, as a rotated polygon so the pitch actually reads
        ring = [math.tau * k / 16 for k in range(16)]
        shell_pts = [P(math.cos(a) * bw, math.sin(a) * bh) for a in ring]
        pygame.draw.polygon(s, C_CRAB_DARK,
                            [P(math.cos(a) * (bw + 1.4), math.sin(a) * (bh + 1.4))
                             for a in ring])
        pygame.draw.polygon(s, C_CRAB, shell_pts)
        hi = [P(math.cos(a) * bw * 0.72, math.sin(a) * bh * 0.72 - bh * 0.3)
              for a in [math.pi + math.pi * k / 7 for k in range(8)]]
        pygame.draw.lines(s, C_CRAB_PALE, False, hi, 3)
        if self.rainbow:
            self.draw_rainbow_shell(s, shell_pts, cx, cy)

        # ---- claws. Position comes from claw_point(), the same call the
        # hitbox uses, so what you see is still exactly what connects.
        idle_bob = math.sin(self.menu_t * 2.2) * 0.8 + 3 * amt
        clx, cly, cang, _reach = c.claw_point(idle_bob)
        # dancing raises the claws in turn. Only ever while no punch is in
        # flight, so the drawn claw still matches the punch hitbox exactly.
        lift_a = lift_b = 0.0
        if dnc > 0.01 and c.punch_t <= 0:
            lift_a = max(0.0, math.sin(c.dance_t)) * 9.0 * dnc
            lift_b = max(0.0, math.sin(c.dance_t + math.pi)) * 9.0 * dnc
            cly -= lift_a
        shoulder = P(f * 7, -1)
        pygame.draw.line(s, C_CRAB_DARK, shoulder, (clx, cly), 4)
        pygame.draw.circle(s, C_CRAB_DARK, (int(clx), int(cly)), 6)
        pygame.draw.circle(s, C_CRAB, (int(clx), int(cly)), 4)
        pygame.draw.line(s, C_CRAB_DARK, (clx, cly),
                         (clx + math.cos(cang - 0.7) * 6,
                          cly + math.sin(cang - 0.7) * 6), 2)

        sh2 = P(-f * 7, -1)
        sang = cang + math.pi * (0.62 if f > 0 else -0.62)
        s2 = (sh2[0] + math.cos(sang) * 6, sh2[1] + math.sin(sang) * 6 - lift_b)
        pygame.draw.line(s, C_CRAB_DARK, sh2, s2, 3)
        pygame.draw.circle(s, C_CRAB_DARK, (int(s2[0]), int(s2[1])), 4)
        pygame.draw.circle(s, C_CRAB, (int(s2[0]), int(s2[1])), 2)

        # ---- eyestalks: lean into the pressed direction, lag otherwise
        closed = c.blink < 0
        for i, sgn in enumerate((-1, 1)):
            root = P(sgn * 5, -bh + 1)
            tipx = sgn * 5 + c.ant[i] * 4 + c.sx * 4.5 * amt
            tipy = -bh - 7 + c.sy * 3.0 * amt
            eye = P(tipx, tipy)
            pygame.draw.line(s, C_CRAB, root, eye, 2)
            pygame.draw.circle(s, C_WHITE, (int(eye[0]), int(eye[1])), 3)
            if zap > 0.25:               # eyes go to crosses while it fries
                for dx in (-1, 1):
                    pygame.draw.line(s, C_INK, (eye[0] - 3 * dx, eye[1] - 3),
                                     (eye[0] + 3 * dx, eye[1] + 3), 2)
            elif closed:
                pygame.draw.line(s, C_CRAB_DARK, (eye[0] - 3, eye[1]),
                                 (eye[0] + 3, eye[1]), 2)
            else:
                look = P(tipx + c.sx * 1.2 * amt + (f * 0.8 if amt < 0.3 else 0),
                         tipy + c.sy * 1.2 * amt)
                pygame.draw.circle(s, C_INK, (int(look[0]), int(look[1])), 2)

        if self.hat:
            self.draw_hat(s, P, bh, pitch, dnc)

        # ---- the shock itself: the shell lights from inside and arcs crawl
        # over it, thinning out as the charge drains away
        if zap > 0:
            # BLEND_ADD sums channels, so this stays in single digits or it
            # blows the whole crab out to white
            glow = pygame.Surface((int(bw * 2.6), int(bh * 4.2)), pygame.SRCALPHA)
            gq = int(5 + 13 * zap)
            pygame.draw.ellipse(glow, (gq, gq, int(gq * 0.4)),
                                (0, 0, glow.get_width(), glow.get_height()))
            s.blit(glow, (cx - glow.get_width() / 2, cy - glow.get_height() / 2),
                   special_flags=pygame.BLEND_ADD)
            for k in range(int(2 + 5 * zap)):
                a = random.uniform(0, math.tau)
                r0 = bw * 0.5
                pts = [(cx + math.cos(a) * r0 * 0.3, cy + math.sin(a) * r0 * 0.3)]
                for seg in range(1, 4):
                    aa = a + random.uniform(-0.7, 0.7)
                    rr = r0 * (0.5 + seg * 0.52) + random.uniform(0, 5)
                    pts.append((cx + math.cos(aa) * rr, cy + math.sin(aa) * rr * 0.9))
                pygame.draw.lines(s, C_JELLY_HOT if k % 2 else C_WHITE,
                                  False, pts, 2)
            if random.random() < 0.5 * zap:
                self.parts.add(cx + random.uniform(-10, 10),
                               cy + random.uniform(-8, 8),
                               random.uniform(-1.4, 1.4), random.uniform(-2.2, -0.4),
                               0.4, C_JELLY_HOT, random.uniform(1.4, 2.6))

        # ---- two notes drift up while it dances
        if dnc > 0.3:
            for j in (0, 1):
                ph = (c.dance_t * 0.55 + j * 0.5) % 1.0
                nx = cx + (14 if j else -15) + math.sin(ph * 6.0 + j) * 3
                ny = cy - 16 - ph * 22
                a = int(210 * (1.0 - ph) * dnc)
                if a <= 4:
                    continue
                note = pygame.Surface((12, 14), pygame.SRCALPHA)
                col = (*RAINBOW[(j + int(c.dance_t * 0.6)) % len(RAINBOW)], a) \
                    if self.rainbow else (*C_WHITE, a)
                pygame.draw.circle(note, col, (4, 10), 3)
                pygame.draw.line(note, col, (7, 10), (7, 2), 2)
                pygame.draw.line(note, col, (7, 2), (11, 4), 2)
                s.blit(note, (nx - 6, ny - 7))

        if c.gripping:
            for sgn in (-1, 1):
                pygame.draw.line(s, C_ROCK_LIT, (cx + sgn * 11, cy + 10),
                                 (cx + sgn * 15, cy + 13), 2)

        if c.charging:
            k = c.charge / CHARGE_TIME
            bx, by = cx - 12, cy - bh - 17
            pygame.draw.rect(s, (14, 32, 38), (bx - 1, by - 1, 26, 5),
                             border_radius=2)
            pygame.draw.rect(s, lerp3(C_SHELL, C_DANGER, k),
                             (bx, by, int(24 * k), 3), border_radius=2)

    def draw_tide_gauge(self, s, wy):
        L = self.L
        x = WORLD_W - 14
        top, bot = 26, WORLD_H - 26
        pygame.draw.line(s, (255, 255, 255), (x, top), (x, bot), 3)
        pygame.draw.line(s, C_WATER_MID, (x, top), (x, bot), 1)
        f = (wy - L["tide_high"]) / max(1.0, (L["tide_low"] - L["tide_high"]))
        y = top + f * (bot - top)
        pygame.draw.polygon(s, C_INK, [(x - 8, y), (x + 4, y - 6), (x + 4, y + 6)])
        pygame.draw.polygon(s, C_WATER_TOP, [(x - 6, y), (x + 3, y - 4), (x + 3, y + 4)])
        d = -1 if self.rising() else 1
        pygame.draw.lines(s, C_FOAM, False,
                          [(x + 6, y - 1 * d), (x + 9, y - 5 * d), (x + 12, y - 1 * d)], 2)


    # -- drawing: the new pool features ---------------------------------------

    def draw_current(self, s, cur, wy):
        r = cur.rect
        top = max(r.top, int(wy) + 4)
        if top >= r.bottom:
            return
        band = pygame.Surface((r.w, r.bottom - top), pygame.SRCALPHA)
        band.fill((210, 255, 250, 22))
        s.blit(band, (r.x, top))
        d = 1 if cur.push > 0 else -1
        span = r.w + 40
        for i in range(max(4, r.w * (r.bottom - top) // 1400)):
            y = top + 6 + (i * 29) % max(1, r.bottom - top - 10)
            x = r.x - 20 + (i * 53 + cur.t * abs(cur.push) * 60) % span
            if d < 0:
                x = r.right + 20 - (x - r.x + 20)
            ln = 10 + (i % 3) * 5
            a = 70 + (i % 4) * 25
            pygame.draw.line(s, (236, 255, 250), (x, y), (x - d * ln, y), 2 if i % 3 == 0 else 1)
        # a couple of chevrons say which way it runs
        for k in range(2):
            cx = r.x + r.w * (0.3 + 0.4 * k) + d * ((cur.t * 30) % 14)
            cy = top + (r.bottom - top) * 0.5
            if cy > wy + 6:
                pygame.draw.lines(s, (255, 255, 255), False,
                                  [(cx - d * 5, cy - 6), (cx + d * 2, cy), (cx - d * 5, cy + 6)], 2)

    def draw_vent(self, s, v):
        # the crack in the rock
        pygame.draw.ellipse(s, (60, 40, 32), (v.x - 12, v.y - 3, 24, 7))
        pygame.draw.ellipse(s, (20, 14, 12), (v.x - 8, v.y - 2, 16, 4))
        t = self.t
        if v.warming:
            k = (v.phase - (v.period - v.blow - Vent.WARN)) / Vent.WARN
            for i in range(3):
                bx = v.x + math.sin(t * 20 + i * 2) * 5
                by = v.y - 4 - ((t * 40 + i * 9) % (10 + 16 * k))
                pygame.draw.circle(s, C_FOAM, (int(bx), int(by)), 2, 1)
        if v.power > 0.05:
            col = pygame.Surface((30, int(v.height)), pygame.SRCALPHA)
            col.fill((230, 255, 250, int(40 * v.power)))
            s.blit(col, (v.x - 15, v.y - v.height))
            n = int(16 * v.power)
            for i in range(n):
                f = ((t * (1.4 + (i % 3) * 0.3) + i * 0.137) % 1.0)
                by = v.y - f * v.height
                bx = v.x + math.sin(t * 6 + i * 1.7) * (4 + 6 * f)
                r = 2 + (i % 3) + int(2 * f)
                pygame.draw.circle(s, C_FOAM, (int(bx), int(by)), r, 1)

    def draw_anemone(self, s, an):
        sq = an.squish
        h = 14 * (1 - 0.45 * sq)
        base_y = an.y
        shadow(s, an.x, base_y + 1, 15, 3, 50)
        pygame.draw.ellipse(s, (170, 60, 110), (an.x - 13, base_y - 8, 26, 10))
        for i in range(11):
            a = math.pi + math.pi * (i + 0.5) / 11
            sway = math.sin(an.sway + i * 0.7) * 3
            tx = an.x + math.cos(a) * (15 + 4 * sq) + sway
            ty = base_y - 6 + math.sin(a) * h
            pygame.draw.line(s, (196, 72, 138), (an.x + math.cos(a) * 6, base_y - 6), (tx, ty), 5)
            pygame.draw.line(s, (255, 150, 200), (an.x + math.cos(a) * 6, base_y - 6), (tx, ty), 2)
            pygame.draw.circle(s, (255, 214, 236), (int(tx), int(ty)), 2)
        # a clownfish lives here
        fx = an.x + math.sin(an.sway * 0.6) * 6
        fy = base_y - 10 - h * 0.6
        pygame.draw.ellipse(s, (255, 130, 40), (fx - 5, fy - 3, 10, 6))
        pygame.draw.line(s, C_WHITE, (fx - 1, fy - 3), (fx - 1, fy + 3), 2)
        pygame.draw.polygon(s, (255, 130, 40), [(fx - 5, fy), (fx - 9, fy - 3), (fx - 9, fy + 3)])
        pygame.draw.circle(s, C_INK, (int(fx + 3), int(fy - 1)), 1)

    def draw_crumble(self, s, cr):
        r = cr.rect
        base, top, dark = (216, 186, 140), (238, 214, 168), (160, 128, 90)
        if cr.state == "fallen":
            # the pieces tumble away and fade
            k = clamp(1 - cr.t / 0.8, 0, 1)
            if k > 0:
                for i in range(4):
                    px = r.x + r.w * (i + 0.5) / 4 + (i - 1.5) * cr.fall * 0.08
                    py = r.y + cr.fall * (0.8 + 0.15 * i)
                    piece = pygame.Surface((r.w // 4 + 2, r.h), pygame.SRCALPHA)
                    piece.fill((*base, int(230 * k)))
                    s.blit(pygame.transform.rotate(piece, cr.fall * (0.3 if i % 2 else -0.3)),
                           (px - r.w // 8, py))
            # a faint outline where it will grow back
            pygame.draw.rect(s, (238, 214, 168), r, 1, border_radius=3)
            return
        ox = 0
        if cr.state == "cracking":
            ox = random.uniform(-1.6, 1.6) * (0.4 + cr.t / Crumble.HOLD)
        a = int(255 * (0.35 + 0.65 * cr.regrow))
        slab = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
        pygame.draw.rect(slab, (*base, a), (0, 0, r.w, r.h), border_radius=3)
        pygame.draw.rect(slab, (*top, a), (0, 0, r.w, 4), border_radius=3)
        pygame.draw.rect(slab, (*dark, a), (0, r.h - 3, r.w, 3))
        rnd = random.Random(r.x * 31 + r.y)
        for _ in range(max(2, r.w // 18)):
            pygame.draw.circle(slab, (*dark, a), (rnd.randint(3, r.w - 3), rnd.randint(5, r.h - 4)), 1)
        if cr.state == "cracking":
            k = cr.t / Crumble.HOLD
            for i in range(1 + int(k * 4)):
                cx = int(r.w * (i + 1) / 6)
                pygame.draw.lines(slab, (90, 60, 40, a), False,
                                  [(cx, 0), (cx + 3, r.h * 0.4), (cx - 2, r.h * 0.7), (cx + 1, r.h)], 1)
        s.blit(slab, (r.x + ox, r.y))

    def draw_turtle(self, s, tu):
        r = tu.rect
        x, top, f = tu.x, r.top, tu.dir
        pad = math.sin(tu.paddle)
        green, dark, belly = (96, 150, 92), (52, 96, 60), (226, 210, 150)
        # flippers paddle under the shell
        for sg in (-1, 1):
            fx = x + sg * 16
            pygame.draw.ellipse(s, (120, 170, 110),
                                (fx - 8 + pad * 3 * sg, top + 9 + pad * 2, 16, 7))
        # head, out front
        hx = x + f * 32
        pygame.draw.ellipse(s, (120, 170, 110), (hx - 7, top + 2, 14, 11))
        pygame.draw.circle(s, C_INK, (int(hx + f * 3), int(top + 6)), 1)
        # shell: a dome with plates
        pygame.draw.ellipse(s, belly, (x - 29, top + 4, 58, 10))
        dome = [(x + math.cos(math.pi + math.pi * k / 12) * 29,
                 top + 9 + math.sin(math.pi + math.pi * k / 12) * 11) for k in range(13)]
        pygame.draw.polygon(s, dark, dome)
        inner = [(x + (px - x) * 0.9, top + 9 + (py - top - 9) * 0.86) for px, py in dome]
        pygame.draw.polygon(s, green, inner)
        for k in (-1, 0, 1):
            pygame.draw.circle(s, dark, (int(x + k * 13), int(top + 4 + abs(k) * 2)), 5, 1)
        pygame.draw.line(s, (170, 210, 150), (x - 18, top + 1), (x + 4, top - 1), 2)

    def draw_shrimp(self, s, sh):
        x, y, f = sh.x - sh.face * sh.recoil * 3, sh.y, sh.face
        stunned = sh.stun > 0
        body = (255, 130, 110)
        shadow(s, x, y + 7, 11, 3, 45)
        # curled body and tail
        for i in range(4):
            pygame.draw.circle(s, (210, 90, 80), (int(x - f * i * 4), int(y + i * 0.8)), 6 - i)
            pygame.draw.circle(s, body, (int(x - f * i * 4), int(y + i * 0.8)), 5 - i)
        pygame.draw.polygon(s, (210, 90, 80), [(x - f * 15, y + 2), (x - f * 21, y - 3), (x - f * 21, y + 6)])
        # the big claw: it opens and swells as it cocks
        k = sh.cock
        cx, cy = x + f * (10 + 2 * k), y - 3 - 2 * k
        pygame.draw.ellipse(s, (210, 90, 80), (cx - 7 - 2 * k, cy - 5 - k, 14 + 4 * k, 10 + 2 * k))
        pygame.draw.ellipse(s, (255, 160, 140), (cx - 6 - 2 * k, cy - 4 - k, 12 + 4 * k, 8 + 2 * k))
        jaw = 0.2 + 0.9 * k
        pygame.draw.line(s, (180, 70, 60), (cx, cy), (cx + f * 9 * math.cos(jaw), cy - 9 * math.sin(jaw)), 3)
        if k > 0.25:                       # the tell
            glow = 0.5 + 0.5 * math.sin(self.t * 30)
            pygame.draw.circle(s, (255, 248, 164), (int(cx + f * 6), int(cy - 2)),
                               int(4 + 7 * k + glow * 2), 2)
        # eyes and feelers
        ex = x + f * 4
        pygame.draw.line(s, (220, 120, 100), (ex, y - 5), (ex + f * 12, y - 14), 1)
        pygame.draw.line(s, (220, 120, 100), (ex, y - 5), (ex + f * 16, y - 9), 1)
        if stunned:
            for d in (-1, 1):
                pygame.draw.line(s, C_INK, (ex - 2, y - 7 - d * 2), (ex + 2, y - 7 + d * 2), 1)
            for k2 in range(3):
                a = self.t * 5 + math.tau * k2 / 3
                pygame.draw.circle(s, (255, 226, 92), (int(x + math.cos(a) * 9), int(y - 14 + math.sin(a) * 3)), 1)
        else:
            pygame.draw.circle(s, C_INK, (int(ex), int(y - 6)), 2)

    def draw_bubble(self, s, b):
        w = 1 + math.sin(b.wob) * 0.18
        rx, ry = b.R * w, b.R / w
        for k in (1, 2):
            pygame.draw.circle(s, (220, 250, 250), (int(b.x - math.copysign(k * 7, b.vx)), int(b.y)), 3 - k, 1)
        pygame.draw.ellipse(s, (200, 245, 250), (b.x - rx, b.y - ry, rx * 2, ry * 2))
        pygame.draw.ellipse(s, (110, 200, 220), (b.x - rx, b.y - ry, rx * 2, ry * 2), 2)
        pygame.draw.circle(s, C_WHITE, (int(b.x - 2), int(b.y - 3)), 2)

    def draw_octopus_body(self, s):
        o = self.octopus
        x, y = o.x, o.y
        body = (156, 62, 112) if o.flash <= 0 else (255, 230, 240)
        dark = (104, 34, 76)
        # the mantle, half sunk in the sand at the back of the pool
        pygame.draw.ellipse(s, dark, (x - 76, y - 120, 152, 150))
        pygame.draw.ellipse(s, body, (x - 72, y - 116, 144, 142))
        pygame.draw.ellipse(s, (186, 92, 142), (x - 50, y - 108, 70, 40))
        for (sx, sy, r) in ((-40, -60, 6), (28, -86, 5), (46, -50, 7), (-14, -96, 4), (10, -40, 5)):
            pygame.draw.circle(s, dark, (int(x + sx), int(y + sy)), r)
        # eyes that follow you, and narrow as it gets angry
        c = self.crab
        for sg in (-1, 1):
            ex, ey = x + sg * 32, y - 24
            pygame.draw.ellipse(s, (255, 236, 200), (ex - 14, ey - 11, 28, 22))
            if o.beaten:
                pygame.draw.line(s, C_INK, (ex - 9, ey), (ex + 9, ey), 3)
                continue
            if o.blink < 0:
                pygame.draw.line(s, dark, (ex - 12, ey), (ex + 12, ey), 4)
                continue
            dx = clamp((c.x - ex) / 60, -1, 1) * 6
            dy = clamp((c.y - ey) / 120, -1, 1) * 4
            slit = 4 if o.phase == 1 else 3 if o.phase == 2 else 2
            pygame.draw.ellipse(s, C_INK, (ex + dx - slit, ey + dy - 8, slit * 2, 16))
            # brow, lower each phase
            tilt = (o.phase - 1) * 3
            pygame.draw.line(s, dark, (ex - 13, ey - 14 + sg * tilt * -0.5 + tilt),
                             (ex + 13, ey - 14 - sg * tilt * -0.5 + (tilt if sg < 0 else -tilt) * 0), 4)

    def draw_tentacle(self, s, arm):
        o = self.octopus
        if arm.state == "aim":
            tx, ty = arm.tgt
            k = arm.t / arm.times["aim"]
            pulse = 0.5 + 0.5 * math.sin(self.t * (16 + 20 * k))
            rr = int(30 - 10 * k)
            pygame.draw.circle(s, (255, 90, 80), (int(tx), int(ty)), rr, 2)
            pygame.draw.circle(s, (255, 200, 120), (int(tx), int(ty)), max(3, int(rr * 0.35 * pulse)), 2)
            g = self.fonts["ui"].render("!", True, (230, 60, 60))
            s.blit(g, (tx - g.get_width() // 2, ty - rr - 22))
        if arm.u <= 0.01:
            return
        n = 22
        pts = [arm.point(arm.u * i / n) for i in range(n + 1)]
        # sway and flinch
        sw = math.sin(self.t * 3 + arm.base[0]) * 6 * (1 - arm.u) + arm.flinch * 8
        pts = [(px + sw * math.sin(i * 0.4), py) for i, (px, py) in enumerate(pts)]
        body = (176, 74, 130)
        for i in range(n):
            w = int(18 - 13 * i / n)
            pygame.draw.line(s, (110, 38, 82), pts[i], pts[i + 1], w + 4)
        for i in range(n):
            w = int(18 - 13 * i / n)
            pygame.draw.line(s, body, pts[i], pts[i + 1], w)
        for i in range(2, n, 3):
            px, py = pts[i]
            pygame.draw.circle(s, (255, 214, 226), (int(px), int(py + 2)), max(2, int(5 - 3 * i / n)))
        tx, ty = pts[-1]
        if arm.state == "stuck":
            glow = 0.5 + 0.5 * math.sin(self.t * 12)
            pygame.draw.circle(s, (255, 248, 164), (int(tx), int(ty)), int(12 + glow * 5), 3)
            pygame.draw.circle(s, (255, 210, 120), (int(tx), int(ty)), 6)

    def draw_world(self):
        s = self.world
        wy = self.water_y()
        self.draw_backdrop(s, wy)
        if self.octopus:
            self.draw_octopus_body(s)
        self.draw_plats(s, wy)
        for cr in self.crumbles:
            self.draw_crumble(s, cr)
        self.draw_water(s, wy)
        for cur in self.currents:
            self.draw_current(s, cur, wy)
        self.draw_light(s, wy)
        self.relight_plats(s)
        for v in self.vents:
            self.draw_vent(s, v)
        for an in self.anemones:
            self.draw_anemone(s, an)
        for p in self.pearls:
            self.draw_pearl(s, p)
        self.draw_goal(s)
        for e in self.eels:
            self.draw_eel(s, e)
        for u in self.urchins:
            self.draw_urchin(s, u)
        for cw in self.crawlers:
            self.draw_crawler(s, cw)
        for pf in self.puffers:
            self.draw_puffer(s, pf)
        for sh in self.shrimps:
            self.draw_shrimp(s, sh)
        for tu in self.turtles:
            self.draw_turtle(s, tu)
        for j in self.jellies:
            self.draw_jelly(s, j)
        for b in self.bubbles:
            self.draw_bubble(s, b)
        if self.octopus:
            for arm in self.octopus.arms:
                self.draw_tentacle(s, arm)
        for gl in self.gulls:
            if gl.boss:
                self.draw_boss_gull(s, gl)
            else:
                self.draw_gull(s, gl)
        for h in self.hatchlings:
            self.draw_hatchling(s, h)
        self.parts.draw(s)
        self.draw_crab(s, self.crab)
        self.draw_tide_gauge(s, wy)
        self.draw_special_hud(s)

    def draw_boss_gull(self, s, gl):
        """The king is an ordinary gull drawn big: painted at normal size on a
        scratch surface, scaled up, then crowned. One drawing routine for
        every bird, so the king moves exactly like the rest."""
        S = 92
        tmp = pygame.Surface((S, S), pygame.SRCALPHA)
        ox, oy = gl.x, gl.y
        gl.x, gl.y = S / 2, S / 2
        self.draw_gull(tmp, gl)
        gl.x, gl.y = ox, oy
        big = pygame.transform.scale(tmp, (int(S * gl.scale), int(S * gl.scale)))
        s.blit(big, (ox - big.get_width() / 2, oy - big.get_height() / 2))
        # crown, riding the head
        f = gl.face
        hx = ox + f * 10 * gl.scale
        hy = oy - (12 if gl.leaving else 7) * gl.scale - 10
        if gl.leaving:
            hx = ox - f * 4 * gl.scale
        tilt = -0.35 * f if gl.leaving else 0.0
        pts = []
        for k, (dx, dy) in enumerate(((-9, 0), (-9, -8), (-4.5, -3), (0, -11),
                                      (4.5, -3), (9, -8), (9, 0))):
            ca, sa = math.cos(tilt), math.sin(tilt)
            pts.append((hx + dx * ca - dy * sa, hy + dx * sa + dy * ca))
        pygame.draw.polygon(s, (255, 206, 72), pts)
        pygame.draw.polygon(s, (186, 120, 30), pts, 2)
        for k in (1, 3, 5):
            pygame.draw.circle(s, (230, 70, 90), (int(pts[k][0]), int(pts[k][1])), 2)
        # the tell: it rears back and screams before every stoop
        if gl.state == "windup":
            a = 0.5 + 0.5 * math.sin(self.menu_t * 40)
            for r, w in ((28, 3), (36, 2)):
                ring = pygame.Rect(0, 0, int(r * 2 * (1.0 + 0.15 * a)),
                                   int(r * 2 * (1.0 + 0.15 * a)))
                ring.center = (int(ox), int(oy))
                pygame.draw.ellipse(s, (255, 110, 90), ring, w)
            g = self.fonts["h2"].render("!", True, (230, 60, 60))
            s.blit(g, (ox - g.get_width() / 2, oy - 70))

    def draw_hatchling(self, s, h):
        bob = abs(math.sin(h.t)) * (2.0 if h.state != "wait" else 1.0)
        x, y = h.x, h.y - bob
        if h.state == "wait":
            shadow(s, x, y + 6, 7, 2, 50)
        # little legs scurry
        for i in (-1, 1):
            for k in (-1, 1):
                ph = math.sin(h.t * 1.3 + i + k) * 1.6
                pygame.draw.line(s, C_CRAB_DARK, (x + i * 3, y + 2),
                                 (x + i * 3 + k * 4, y + 6 + ph), 2)
        pygame.draw.ellipse(s, C_CRAB_DARK, (x - 7, y - 4, 14, 9))
        pygame.draw.ellipse(s, C_CRAB_PALE, (x - 6, y - 3, 12, 7))
        # claws up, waving, while it waits to be found
        wave = math.sin(h.t * 0.9) * 2.5 if h.state == "wait" else 0
        for i in (-1, 1):
            pygame.draw.circle(s, C_CRAB, (int(x + i * 8), int(y - 2 - (wave if i > 0 else -wave))), 2)
        for i in (-1, 1):
            ex, ey = x + i * 2.5 + h.face * 0.6, y - 7
            pygame.draw.line(s, C_CRAB, (x + i * 2, y - 3), (ex, ey), 1)
            pygame.draw.circle(s, C_WHITE, (int(ex), int(ey)), 2)
            pygame.draw.circle(s, C_INK, (int(ex + h.face * 0.5), int(ey)), 1)
        if h.state == "wait" and math.sin(h.t * 0.35) > 0.6:
            g = self.fonts["tiny"].render("!", True, C_CRAB_DARK)
            s.blit(g, (x - g.get_width() / 2, y - 22))

    def draw_special_hud(self, s):
        if self.special == "octopus" and self.octopus:
            hp, mx = max(0, self.octopus.hp), Octopus.HP
            w = 190
            x0, y0 = WORLD_W // 2 - w // 2, 10
            pad = pygame.Surface((w + 16, 34), pygame.SRCALPHA)
            pygame.draw.rect(pad, (*C_PANEL, 220), (0, 0, w + 16, 34), border_radius=9)
            s.blit(pad, (x0 - 8, y0 - 4))
            t = self.fonts["tiny"].render("THE GREAT OCTOPUS", True, C_INK)
            s.blit(t, (WORLD_W // 2 - t.get_width() // 2, y0 - 1))
            seg = (w - (mx - 1) * 3) / mx
            for i in range(mx):
                r = pygame.Rect(int(x0 + i * (seg + 3)), y0 + 14, int(seg), 9)
                pygame.draw.rect(s, (176, 74, 130) if i < hp else (214, 204, 190), r, border_radius=3)
            return
        if self.special == "gullking":
            king = [g for g in self.gulls if g.boss]
            hp = king[0].hp if king else 0
            mx = king[0].max_hp if king else 4
            w = 170
            x0, y0 = WORLD_W // 2 - w // 2, 10
            pad = pygame.Surface((w + 16, 34), pygame.SRCALPHA)
            pygame.draw.rect(pad, (*C_PANEL, 220), (0, 0, w + 16, 34), border_radius=9)
            s.blit(pad, (x0 - 8, y0 - 4))
            t = self.fonts["tiny"].render("THE GULL KING", True, C_INK)
            s.blit(t, (WORLD_W // 2 - t.get_width() // 2, y0 - 1))
            seg = (w - (mx - 1) * 4) / mx
            for i in range(mx):
                r = pygame.Rect(int(x0 + i * (seg + 4)), y0 + 14, int(seg), 9)
                pygame.draw.rect(s, (230, 70, 70) if i < hp else (214, 204, 190), r,
                                 border_radius=3)
        elif self.hatchlings:
            n = sum(1 for h in self.hatchlings if h.state == "follow")
            total = len(self.hatchlings)
            pad = pygame.Surface((22 + total * 16 + 8, 26), pygame.SRCALPHA)
            pygame.draw.rect(pad, (*C_PANEL, 220), (0, 0, pad.get_width(), 26),
                             border_radius=9)
            s.blit(pad, (8, 8))
            t = self.fonts["tiny"].render("%d/%d" % (n, total), True, C_INK)
            s.blit(t, (14, 14))
            for i in range(total):
                on = i < n
                cx = 16 + 22 + i * 16
                pygame.draw.ellipse(s, C_CRAB_DARK if on else (196, 188, 176),
                                    (cx - 6, 15, 12, 9))
                pygame.draw.ellipse(s, C_CRAB_PALE if on else (226, 220, 210),
                                    (cx - 5, 16, 10, 7))

    # -- drawing: chrome -----------------------------------------------------

    def draw_gear(self, surf, rect, lit):
        cx, cy = rect.center
        col = C_INK if lit else C_MUTED
        pygame.draw.circle(surf, (255, 255, 255), (cx, cy), 13)
        pygame.draw.circle(surf, col, (cx, cy), 13, 2)
        for i in range(8):
            a = self.gear_spin + i * math.tau / 8
            pygame.draw.line(surf, col,
                             (cx + math.cos(a) * 8, cy + math.sin(a) * 8),
                             (cx + math.cos(a) * 13, cy + math.sin(a) * 13), 3)
        pygame.draw.circle(surf, col, (cx, cy), 4, 2)

    def draw_bar(self, surf, in_game):
        """The strip under the ad: pool name, hearts, pearls, and the gear.

        Drawn in every state so the gear never moves."""
        y = AD_H
        pygame.draw.rect(surf, C_PANEL, (0, y, WIN_W, HUD_H))
        pygame.draw.line(surf, (226, 214, 190), (0, y + HUD_H - 1),
                         (WIN_W, y + HUD_H - 1), 1)
        if in_game:
            name = self.fonts["ui"].render(
                "Pool %d  %s" % (self.level_i + 1, self.L["name"]), True, C_INK)
            surf.blit(name, (12, y + 9))
            for i in range(self.max_hp):
                cx = WIN_W - 68 - i * 22
                alive = i < self.hp
                pygame.draw.circle(surf, C_CRAB_DARK if alive else (210, 200, 186),
                                   (cx, y + 18), 8)
                pygame.draw.circle(surf, C_CRAB if alive else (226, 216, 200),
                                   (cx, y + 18), 6)
                pygame.draw.circle(surf, C_CRAB_PALE if alive else (238, 232, 222),
                                   (cx - 2, y + 16), 2)
            got = sum(1 for p in self.pearls if p.got)
            px = WIN_W - 80 - self.max_hp * 22
            pygame.draw.circle(surf, C_SHELL_DARK, (px, y + 18), 7)
            pygame.draw.circle(surf, C_SHELL, (px, y + 18), 6)
            pe = self.fonts["small"].render("%d/%d" % (got, len(self.pearls)),
                                            True, C_MUTED)
            surf.blit(pe, (px + 10, y + 11))
            # clean-run tracker, parked between the pearl count and the
            # hearts: pips while you build the streak, a rainbow bar once it
            # has earned you the shell
            tx = px - 48
            if self.rainbow:
                for i, col in enumerate(RAINBOW):
                    pygame.draw.rect(surf, col, (tx + i * 4, y + 14, 4, 9))
                pygame.draw.rect(surf, (226, 214, 190),
                                 (tx - 1, y + 13, 4 * len(RAINBOW) + 2, 11), 1)
            else:
                for i in range(RAINBOW_STREAK):
                    on = i < self.streak
                    pygame.draw.circle(surf, RAINBOW[i * 2] if on else (220, 210, 196),
                                       (tx + 3 + i * 10, y + 18), 3)
        else:
            cap = self.fonts["tiny"].render("A ROCK POOL GAME", True, C_MUTED)
            surf.blit(cap, (12, y + 13))
        self.gear_rect = pygame.Rect(WIN_W - 42, y + 4, 28, 28)
        self.draw_gear(surf, self.gear_rect,
                       self.gear_rect.collidepoint(pygame.mouse.get_pos()))

    def draw_buttons(self, surf, oy):
        mx, my = pygame.mouse.get_pos()
        my -= (AD_H + HUD_H)        # buttons live in world coordinates
        for b in self.buttons:
            r = b.rect.move(0, oy)
            hot = r.collidepoint(mx, my) and b.enabled
            b.hover = approach(b.hover, 1.0 if hot else 0.0, 0.18)
            lift = int(b.hover * 2)
            r = r.move(0, -lift)
            pygame.draw.rect(surf, (18, 40, 48, 60), r.move(0, 3 + lift), border_radius=12)
            if b.primary:
                bg = lerp3(C_CRAB, (255, 140, 96), b.hover)
                fg = C_WHITE
                edge = C_CRAB_DARK
            else:
                bg = lerp3(C_PANEL, C_PANEL_2, b.hover)
                fg = C_INK
                edge = (214, 198, 172)
            if not b.enabled:
                bg, fg, edge = (228, 220, 206), (170, 164, 152), (210, 200, 186)
            pygame.draw.rect(surf, bg, r, border_radius=12)
            pygame.draw.rect(surf, edge, r, 2, border_radius=12)
            lab = self.fonts["ui"].render(b.label, True, fg)
            ly = r.centery - lab.get_height() // 2 - (6 if b.sub else 0)
            surf.blit(lab, (r.centerx - lab.get_width() // 2, ly))
            if b.sub:
                sub = self.fonts["tiny"].render(
                    b.sub, True, (255, 226, 212) if b.primary else C_MUTED)
                surf.blit(sub, (r.centerx - sub.get_width() // 2, ly + 19))

    def draw_menu(self, surf):
        s = self.world
        wy = 300 + math.sin(self.menu_t * 0.8) * 26
        self.t = self.menu_t
        self.draw_backdrop(s, wy)
        pygame.draw.rect(s, C_ROCK, (0, 560, WORLD_W, 60))
        pygame.draw.rect(s, C_ROCK_TOP, (0, 560, WORLD_W, 5))
        pygame.draw.rect(s, C_ROCK_LIT, (2, 560, WORLD_W - 4, 2))
        self.draw_water(s, wy)
        self.draw_light(s, wy)
        pygame.draw.rect(s, C_ROCK_TOP, (0, 560, WORLD_W, 3))
        pygame.draw.rect(s, C_ROCK_LIT, (2, 560, WORLD_W - 4, 2))
        for i in range(6):
            bx = 40 + i * 70
            by = WORLD_H - 70 - ((self.menu_t * 34 + i * 55) % 300)
            if by > wy:
                pygame.draw.circle(s, C_FOAM, (int(bx), int(by)), 3 + i % 3, 1)

        title = self.fonts["title"].render("TIDE POOL", True, C_INK)
        tsh = self.fonts["title"].render("TIDE POOL", True, (255, 255, 255))
        s.blit(tsh, (WORLD_W // 2 - title.get_width() // 2 + 2, 150 + 3))
        s.blit(title, (WORLD_W // 2 - title.get_width() // 2, 150))
        sub = self.fonts["small"].render(
            "The water does the climbing. You do the timing.", True, C_INK)
        s.blit(sub, (WORLD_W // 2 - sub.get_width() // 2, 206))

        # the mascot rides the menu tide, which is the whole game in one image
        demo = Crab(WORLD_W // 2, wy - 5 + math.sin(self.menu_t * 2.0) * 3)
        demo.walk = self.menu_t * 6
        demo.blink = math.sin(self.menu_t * 0.7) + 0.4
        self.draw_crab(s, demo, ghost=True)

        self.draw_buttons(s, 0)
        ctl = ["swim  8 directions, arrows or wasd",
               "hop  hold space, release    punch  B",
               "grip the rock  hold down"]
        for i, line in enumerate(ctl):
            g = self.fonts["tiny"].render(line, True, C_INK)
            g.set_alpha(190)
            s.blit(g, (WORLD_W // 2 - g.get_width() // 2, 512 + i * 15))

    def draw_overlay_card(self, surf, title, body_lines, accent=C_INK):
        s = self.world
        veil = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        veil.fill((8, 40, 54, 170))
        s.blit(veil, (0, 0))
        plate = pygame.Rect(WORLD_W // 2 - 150, 200, 300, 300)
        pygame.draw.rect(s, (*C_PANEL, 250), plate, border_radius=18)
        pygame.draw.rect(s, (226, 206, 170), plate, 2, border_radius=18)
        t = self.fonts["h2"].render(title, True, accent)
        s.blit(t, (WORLD_W // 2 - t.get_width() // 2, 228))
        for i, line in enumerate(body_lines):
            g = self.fonts["small"].render(line, True, C_MUTED)
            s.blit(g, (WORLD_W // 2 - g.get_width() // 2, 272 + i * 20))
        self.draw_buttons(s, 0)

    def draw_settings(self, surf):
        s = self.world
        veil = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        veil.fill((8, 40, 54, 190))
        s.blit(veil, (0, 0))
        plate = pygame.Rect(WORLD_W // 2 - 140, 166, 280, 436)
        pygame.draw.rect(s, C_PANEL, plate, border_radius=18)
        pygame.draw.rect(s, (226, 206, 170), plate, 2, border_radius=18)
        t = self.fonts["h2"].render("Settings", True, C_INK)
        s.blit(t, (WORLD_W // 2 - t.get_width() // 2, 182))
        self.draw_buttons(s, 0)

    def draw_shop(self, surf):
        s = self.world
        veil = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        veil.fill((8, 40, 54, 190))
        s.blit(veil, (0, 0))
        plate = pygame.Rect(WORLD_W // 2 - 150, 150, 300, 440)
        pygame.draw.rect(s, C_PANEL, plate, border_radius=18)
        pygame.draw.rect(s, (226, 206, 170), plate, 2, border_radius=18)
        t = self.fonts["h2"].render("Pearl shop", True, C_INK)
        s.blit(t, (WORLD_W // 2 - t.get_width() // 2, 168))

        # purse
        px = WORLD_W // 2 - 34
        pygame.draw.circle(s, C_SHELL_DARK, (px, 214), 8)
        pygame.draw.circle(s, C_SHELL, (px, 214), 7)
        pygame.draw.circle(s, C_WHITE, (px - 2, 211), 2)
        cnt = self.fonts["ui"].render("%d" % self.wallet, True, C_INK)
        s.blit(cnt, (px + 14, 205))

        # the crab models whatever is on right now
        demo = Crab(WORLD_W // 2 + 86, 222)
        demo.walk = self.menu_t * 4
        demo.blink = math.sin(self.menu_t * 0.7) + 0.4
        if self.dance_on:
            demo.dance = 1.0
            demo.dance_t = self.menu_t * 7.4
        self.draw_crab(s, demo, ghost=True)

        self.draw_buttons(s, 0)
        if self.shop_msg_t > 0:
            g = self.fonts["tiny"].render(self.shop_msg, True, C_CRAB_DARK)
            s.blit(g, (WORLD_W // 2 - g.get_width() // 2, 240))

    def draw_dialogue(self, surf):
        """The last pool's send-off. One line at a time, click or press to go
        on; the pool keeps moving behind it."""
        s = self.world
        lines = self.L.get("dialogue", [])
        i = min(self.dlg_i, len(lines) - 1)
        speaker, text = lines[i]
        veil = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        veil.fill((8, 40, 54, 120))
        s.blit(veil, (0, 0))

        box = pygame.Rect(26, WORLD_H - 150, WORLD_W - 52, 96)
        pygame.draw.rect(s, C_PANEL, box, border_radius=14)
        pygame.draw.rect(s, (226, 206, 170), box, 2, border_radius=14)
        if speaker:
            nm = self.fonts["tiny"].render(speaker.upper(), True, C_CRAB_DARK)
            s.blit(nm, (box.x + 18, box.y + 14))
        # the line types itself in, so it reads at a speaking pace
        shown = text[:int(self.dlg_t * 34)]
        body = self.fonts["small"] if speaker else self.fonts["ui"]
        g = body.render(shown, True, C_INK if speaker else C_MUTED)
        s.blit(g, (box.x + 18, box.y + 36))

        done = len(shown) >= len(text)
        if done and math.sin(self.menu_t * 5.0) > -0.2:
            tip = "click or press to go on" if i < len(lines) - 1 else \
                  "click or press to finish"
            hint = self.fonts["tiny"].render(tip, True, C_MUTED)
            s.blit(hint, (box.right - hint.get_width() - 16, box.bottom - 20))

    def advance_dialogue(self):
        lines = self.L.get("dialogue", [])
        text = lines[min(self.dlg_i, len(lines) - 1)][1]
        if self.dlg_t * 34 < len(text):        # first press finishes the line
            self.dlg_t = len(text) / 34.0 + 0.1
            return
        self.dlg_i += 1
        self.dlg_t = 0.0
        if self.dlg_i >= len(lines):
            self.state = CLEARED
            self.build_cleared_menu()

    def draw_controls(self, surf):
        s = self.world
        veil = pygame.Surface((WORLD_W, WORLD_H), pygame.SRCALPHA)
        veil.fill((8, 40, 54, 190))
        s.blit(veil, (0, 0))
        plate = pygame.Rect(WORLD_W // 2 - 150, 140, 300, 460)
        pygame.draw.rect(s, C_PANEL, plate, border_radius=18)
        pygame.draw.rect(s, (226, 206, 170), plate, 2, border_radius=18)
        t = self.fonts["h2"].render("Controls", True, C_INK)
        s.blit(t, (WORLD_W // 2 - t.get_width() // 2, 158))

        rows = [
            ("MOVE", "Arrows or WASD", "swim or walk in all 8 directions"),
            ("HOP", "Hold SPACE, release", "hold longer for a higher jump"),
            ("PUNCH", "B, X, or Z", "aims the way you're holding"),
            ("GRIP", "Hold DOWN on rock", "tide can't lift you; soft anemone landing"),
            ("SETTINGS", "Gear icon, or ESC", ""),
            ("FULLSCREEN", "F11 or F", "works any time"),
            ("RESTART POOL", "R", "while playing"),
        ]
        lx = WORLD_W // 2 - 128
        y = 200
        for key, how, why in rows:
            kg = self.fonts["ui"].render(key, True, C_CRAB_DARK)
            s.blit(kg, (lx, y))
            hg = self.fonts["small"].render(how, True, C_INK)
            s.blit(hg, (lx, y + 20))
            if why:
                wg = self.fonts["tiny"].render(why, True, C_MUTED)
                s.blit(wg, (lx, y + 36))
            y += 46

        self.draw_buttons(s, 0)

    # -- input routing -------------------------------------------------------

    def trigger_punch(self):
        """Start a swing, if the claw is ready. Locked to the direction held
        at the moment of the press, facing if nothing is."""
        c = self.crab
        if c.punch_cd > 0:
            return
        c.punch_ang = c.aim_angle()
        c.punch_t = PUNCH_TIME
        c.punch_cd = PUNCH_COOLDOWN
        c.punch_hit = False
        self.parts.burst(c.x + math.cos(c.punch_ang) * 14,
                         c.y + math.sin(c.punch_ang) * 14,
                         5, C_FOAM, 2.2, 0.2, 1.8, 0.0)

    def click_at(self, pos):
        if self.gear_rect.collidepoint(pos):
            return "__gear__"
        x, y = pos[0], pos[1] - (AD_H + HUD_H)
        for b in self.buttons:
            if b.enabled and b.rect.collidepoint(x, y):
                return b.label
        return None

    def open_settings(self):
        if self.state == SETTINGS:
            return
        self.prev_state = self.state
        self.state = SETTINGS
        self.build_settings_menu()

    def close_settings(self):
        self.state = self.prev_state
        if self.state == MENU:
            self.build_menu()
        elif self.state == DEAD:
            self.build_dead_menu()
        elif self.state == CLEARED:
            self.build_cleared_menu()
        else:
            self.buttons = []

    def open_controls(self):
        self.state = CONTROLS
        self.build_controls_menu()

    def close_controls(self):
        self.state = SETTINGS
        self.build_settings_menu()

    def open_shop(self):
        self.shop_from = self.state if self.state in (MENU, SETTINGS) else MENU
        self.state = SHOP
        self.shop_msg_t = 0.0
        self.build_shop_menu()

    def close_shop(self):
        if self.shop_from == SETTINGS:
            self.state = SETTINGS
            self.build_settings_menu()
        else:
            self.state = MENU
            self.build_menu()

    def shop_click(self, label):
        """Buy an item, or put one on and take it off. Hats replace each
        other; the dance is its own switch."""
        for it in SHOP_ITEMS:
            if not label.startswith(it["name"] + ":"):
                continue
            key = it["key"]
            if key not in self.owned:
                if self.wallet < it["cost"]:
                    return True
                self.wallet -= it["cost"]
                self.owned.append(key)
                if it["kind"] == "hat":
                    self.hat = key
                else:
                    self.dance_on = True
                self.shop_msg, self.shop_msg_t = "Bought, and on.", 2.2
            elif it["kind"] == "hat":
                self.hat = "" if self.hat == key else key
            else:
                self.dance_on = not self.dance_on
            self.persist()
            self.build_shop_menu()
            return True
        return False

    def activate(self, label):
        if self.state == SHOP and label != "BACK" and self.shop_click(label):
            return
        if label == "__gear__":
            self.open_settings()
        elif label == "SHOP":
            self.open_shop()
        elif label == "CONTINUE":
            if self.state == CLEARED:
                self.start_level(self.next_level)
            else:
                self.start_level(self.level_i)
        elif label == "PLAY AGAIN":
            self.unlocked = 0
            self.run_pearls = 0
            self.start_level(0, reset_run=True)
        elif label in ("MAIN SCREEN", "MAIN MENU"):
            sv = load_save()
            self.level_i = clamp(sv["level"], 0, len(LEVELS) - 1)
            self.unlocked = sv["unlocked"]
            self.run_pearls = sv["pearls"]
            self.wallet = sv["wallet"]
            self.owned = list(sv["owned"])
            self.hat = sv["hat"]
            self.dance_on = sv["dance"]
            self.L = LEVELS[self.level_i]
            self.state = MENU
            self.build_menu()
        elif label == "NEW GAME":
            self.unlocked = 0
            self.run_pearls = 0
            self.start_level(0, reset_run=True)
        elif label == "CONTROLS":
            self.open_controls()
        elif label == "BACK":
            if self.state == CONTROLS:
                self.close_controls()
            elif self.state == SHOP:
                self.close_shop()
            else:
                self.close_settings()
        elif label.startswith("PACE"):
            self.pace = "normal" if self.pace == "relaxed" else "relaxed"
            self.persist()
            if self.state == SETTINGS and self.prev_state == PLAY:
                self.apply_pace()
            self.build_settings_menu()
        elif label.startswith("FULLSCREEN"):
            self.toggle_fullscreen()
            self.build_settings_menu()
        elif label == "QUIT":
            self.persist()
            pygame.quit()
            sys.exit(0)

    # -- main loop -----------------------------------------------------------

    def run(self, max_frames=None):
        frames = 0
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 20)
            self.menu_t += dt
            self.gear_spin += dt * 0.6

            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.persist()
                    pygame.quit()
                    return
                if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                    if self.state == DIALOGUE:
                        self.advance_dialogue()
                        continue
                    lab = self.click_at(ev.pos)
                    if lab:
                        self.activate(lab)
                    elif self.state == PLAY and self.gear_rect.collidepoint(ev.pos):
                        self.open_settings()
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_F11, pygame.K_f):
                        self.toggle_fullscreen()
                        if self.state == SETTINGS:
                            self.build_settings_menu()
                        continue
                    if ev.key == pygame.K_ESCAPE:
                        if self.state == CONTROLS:
                            self.close_controls()
                        elif self.state == SHOP:
                            self.close_shop()
                        elif self.state == DIALOGUE:
                            self.advance_dialogue()
                        elif self.state == SETTINGS:
                            self.close_settings()
                        elif self.state == MENU:
                            self.persist()
                            pygame.quit()
                            return
                        else:
                            self.open_settings()
                        continue
                    if self.state == PLAY:
                        if ev.key in (pygame.K_b, pygame.K_x, pygame.K_z):
                            self.trigger_punch()
                        elif ev.key == pygame.K_r:
                            self.start_level(self.level_i)
                    elif self.state == DIALOGUE:
                        self.advance_dialogue()
                    elif self.state in (MENU, DEAD, CLEARED):
                        if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                            for b in self.buttons:
                                if b.enabled:
                                    self.activate(b.label)
                                    break

            keys = pygame.key.get_pressed()
            self.ad.update(dt)

            if self.state == PLAY:
                self.update_play(dt, keys)
                self.parts.update(dt)
                self.msg_t = max(0.0, self.msg_t - dt)
            elif self.state in (DEAD, CLEARED, DIALOGUE):
                self.parts.update(dt)
                if self.state == DIALOGUE:
                    self.t += dt          # the pool keeps breathing behind it
                    self.dlg_t += dt
            self.rain_t += dt
            self.shop_msg_t = max(0.0, self.shop_msg_t - dt)

            self.shake = max(0.0, self.shake - dt * 44)
            self.flash = max(0.0, self.flash - dt * 3.2)
            self.fade = max(0.0, self.fade - dt * 2.2)

            self.screen.fill(C_SKY_BOT)
            self.ad.draw(self.screen)

            menu_behind = (self.state in (SETTINGS, CONTROLS) and
                           self.prev_state == MENU) or \
                          (self.state == SHOP and
                           (self.shop_from == MENU or self.prev_state == MENU))
            in_game = self.state not in (MENU,) and not menu_behind

            if self.state == MENU or menu_behind:
                self.draw_menu(self.screen)
            else:
                self.draw_world()
                if self.state == DEAD:
                    body = ["The pool took you."]
                    if self.lost_pearls:
                        body.append("%d pearl%s washed away." %
                                    (self.lost_pearls,
                                     "" if self.lost_pearls == 1 else "s"))
                    body.append("Pearls kept: %d" % self.wallet)
                    self.draw_overlay_card(self.screen, "Washed out", body, C_DANGER)
                elif self.state == CLEARED:
                    got = sum(1 for p in self.pearls if p.got)
                    if self.cleared_last:
                        body = ["That was the last pool.",
                                "Pearls in all: %d" % self.run_pearls]
                    else:
                        body = ["Pearls here: %d / %d" % (got, len(self.pearls)),
                                "Progress saved."]
                        if self.earned_rainbow:
                            body.append("Three clean pools - RAINBOW MODE")
                        elif self.clean and self.streak:
                            body.append("Clean run: %d of %d" %
                                        (self.streak, RAINBOW_STREAK))
                    self.draw_overlay_card(
                        self.screen,
                        "High water" if self.cleared_last else "Safe ashore",
                        body, C_INK)
                elif self.state == DIALOGUE:
                    self.draw_dialogue(self.screen)

            if self.state == SETTINGS:
                self.draw_settings(self.screen)
            elif self.state == CONTROLS:
                self.draw_controls(self.screen)
            elif self.state == SHOP:
                self.draw_shop(self.screen)

            ox = random.uniform(-self.shake, self.shake) if self.shake > 0 else 0
            oy = random.uniform(-self.shake, self.shake) if self.shake > 0 else 0
            self.screen.blit(self.world, (ox, AD_H + HUD_H + oy))
            self.draw_bar(self.screen, in_game)

            if self.msg_t > 0 and self.state == PLAY:
                a = int(255 * clamp(self.msg_t / 0.6, 0, 1))
                g = self.fonts["small"].render(self.msg, True, C_INK)
                g.set_alpha(a)
                bgr = pygame.Rect(0, 0, g.get_width() + 22, 28)
                bgr.center = (WIN_W // 2, AD_H + HUD_H + 42)
                pad = pygame.Surface(bgr.size, pygame.SRCALPHA)
                pygame.draw.rect(pad, (*C_PANEL, min(a, 235)),
                                 (0, 0, *bgr.size), border_radius=10)
                self.screen.blit(pad, bgr.topleft)
                self.screen.blit(g, (bgr.centerx - g.get_width() // 2, bgr.y + 6))

            if self.flash > 0:
                f = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                f.fill((255, 120, 100, int(110 * clamp(self.flash, 0, 1))))
                self.screen.blit(f, (0, 0))
            if self.fade > 0:
                f = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                f.fill((*C_SKY_BOT, int(255 * clamp(self.fade, 0, 1))))
                self.screen.blit(f, (0, 0))

            pygame.display.flip()
            frames += 1
            if max_frames and frames >= max_frames:
                pygame.quit()
                return


if __name__ == "__main__":
    Game().run()