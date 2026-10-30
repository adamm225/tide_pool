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
    Claw punch ........ J  (or X / Z)
    Retry pool ........ R
    Fullscreen ........ F11  (or F)
    Settings / pause .. Esc, or the gear at the top right

Hazards
    Urchin ....... static spines. Cannot be punched - the spines win.
    Eel .......... rises and falls out of its burrow like a snapping plant.
                   Punch it and the half you hit folds away at an angle,
                   then springs back to vertical.
    Jellyfish .... blinks faster and faster, then discharges a shock ring.
                   Punch it to send it tumbling and reset its charge, but
                   never while it is lit up.

Pearls are shy - get close and they leap toward you.
You can take two hits. The third one ends the run.

Requires: pygame   ->   pip install pygame
Run with: python3 tide_pool.py
"""

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
DANCE_AFTER = 3.0        # seconds of stillness before the idle dance starts
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
    dict(
        name="Shallows",
        period=10.0, tide_low=606, tide_high=362,
        spawn=(35, 575), goal=(340, 360),
        plats=[(0, 600, 420, 20), (100, 490, 110, 16), (250, 380, 130, 16)],
        urchins=[(232, 592)],
        eels=[],
        jellies=[],
        pearls=[(150, 470), (62, 580)],
        puffers=[], crawlers=[], gulls=[],
        tip="Arrows swim all 8 ways. SPACE charges a hop. Hold DOWN to grip rock.",
    ),
    dict(
        name="Burrow",
        period=11.0, tide_low=606, tide_high=218,
        spawn=(30, 480), goal=(370, 220),
        plats=[(0, 600, 420, 20), (0, 500, 140, 16), (190, 415, 120, 16),
               (50, 320, 140, 16), (280, 240, 140, 16)],
        urchins=[(120, 492), (304, 592), (232, 407)],
        eels=[(170, 600, "up", 124, 3.4)],
        jellies=[],
        pearls=[(72, 482), (172, 560)],
        puffers=[], crawlers=[((100, 490, 110, 16), 150, 26)], gulls=[],
        tip="Punch the eel with J. The half you hit folds out of the way.",
    ),
    dict(
        name="Overhang",
        period=12.0, tide_low=606, tide_high=208,
        spawn=(30, 500), goal=(55, 210),
        plats=[(0, 600, 420, 20), (0, 520, 110, 16), (140, 430, 160, 14),
               (320, 450, 100, 16), (110, 330, 150, 16), (0, 230, 130, 16)],
        urchins=[(362, 442), (90, 322)],
        eels=[(220, 444, "down", 112, 3.0)],
        jellies=[((362, 548), (362, 352), 0.36)],
        pearls=[(192, 560), (182, 312)],
        puffers=[((150, 560), (150, 400), 0.34)],
        crawlers=[((110, 330, 150, 16), 160, 30)],
        gulls=[],
        tip="Jellyfish blink faster before they fire. Punch them dark, not lit.",
    ),
    dict(
        name="Jelly bloom",
        period=12.0, tide_low=606, tide_high=183,
        spawn=(30, 520), goal=(372, 185),
        plats=[(0, 600, 420, 20), (0, 540, 100, 16), (150, 500, 90, 16),
               (290, 420, 130, 16), (110, 340, 140, 16), (0, 255, 110, 16),
               (250, 205, 170, 16)],
        urchins=[(202, 492), (384, 412), (72, 247)],
        eels=[(252, 600, "up", 148, 3.2), (170, 356, "down", 104, 2.9)],
        jellies=[((180, 432), (304, 432), 0.42), ((70, 492), (70, 382), 0.50)],
        pearls=[(42, 522), (166, 322), (322, 186)],
        puffers=[((60, 470), (240, 470), 0.30)],
        crawlers=[((290, 420, 130, 16), 330, 28)],
        gulls=[(210, 120, 90)],
        tip="A shock ring reaches further than the bell. Give it room.",
    ),
    dict(
        name="Spring tide",
        period=9.0, tide_low=606, tide_high=163,
        spawn=(30, 530), goal=(390, 165),
        plats=[(0, 600, 420, 20), (0, 550, 90, 16), (140, 545, 80, 16),
               (270, 480, 150, 16), (70, 410, 140, 16), (250, 340, 170, 16),
               (40, 265, 140, 16), (230, 185, 190, 16)],
        urchins=[(192, 537), (402, 472), (102, 402), (292, 332), (132, 257)],
        eels=[(232, 600, "up", 158, 2.8), (150, 426, "down", 108, 3.1),
              (344, 356, "down", 88, 2.6)],
        jellies=[((200, 470), (200, 332), 0.46), ((330, 252), (182, 252), 0.52)],
        pearls=[(36, 532), (112, 392), (352, 166)],
        puffers=[((110, 500), (330, 500), 0.32),
                 ((300, 300), (300, 200), 0.38)],
        crawlers=[((70, 410, 140, 16), 110, 32),
                  ((230, 185, 190, 16), 300, 30)],
        gulls=[(180, 104, 110)],
        tip="The tide swings faster here. Plan two moves ahead.",
    ),
    dict(
        name="Kelp gate",
        period=11.5, tide_low=606, tide_high=153,
        spawn=(32, 560), goal=(40, 155),
        plats=[(0, 600, 420, 20), (300, 545, 120, 16), (160, 470, 120, 16),
               (0, 395, 140, 16), (210, 320, 150, 16), (60, 240, 130, 16),
               (0, 175, 120, 16)],
        urchins=[(352, 537), (212, 462), (92, 387), (262, 312)],
        eels=[(190, 600, "up", 136, 3.0), (120, 411, "down", 96, 2.8)],
        jellies=[((340, 470), (200, 470), 0.40), ((90, 300), (90, 196), 0.46)],
        pearls=[(344, 527), (56, 377), (272, 302)],
        puffers=[((380, 400), (380, 260), 0.34)],
        crawlers=[((210, 320, 150, 16), 250, 28)],
        gulls=[(240, 112, 96)],
        tip="Two ways up here. The slow one is usually the dry one.",
    ),
    dict(
        name="The shelf",
        period=10.5, tide_low=606, tide_high=143,
        spawn=(390, 570), goal=(372, 145),
        plats=[(0, 600, 420, 20), (0, 530, 150, 16), (230, 470, 190, 16),
               (60, 390, 160, 16), (280, 310, 140, 16), (0, 300, 130, 16),
               (140, 215, 150, 16), (300, 165, 120, 16)],
        urchins=[(102, 522), (266, 462), (172, 382), (46, 292), (196, 207)],
        eels=[(300, 600, "up", 142, 2.9), (330, 486, "down", 104, 2.7),
              (90, 406, "down", 86, 3.1)],
        jellies=[((150, 440), (150, 330), 0.44), ((240, 250), (380, 250), 0.48)],
        pearls=[(30, 512), (110, 372), (340, 292)],
        puffers=[((200, 540), (380, 540), 0.32)],
        crawlers=[((230, 470, 190, 16), 300, 30), ((140, 215, 150, 16), 180, 26)],
        gulls=[(200, 100, 120)],
        tip="A wide shelf is a long way to be caught standing on.",
    ),
    dict(
        name="Gull run",
        period=12.0, tide_low=606, tide_high=133,
        spawn=(30, 570), goal=(50, 135),
        plats=[(0, 600, 420, 20), (250, 540, 170, 16), (60, 465, 150, 16),
               (270, 385, 150, 16), (90, 310, 140, 16), (260, 230, 160, 16),
               (0, 155, 150, 16)],
        urchins=[(330, 532), (130, 457), (350, 377), (160, 302), (330, 222)],
        eels=[(210, 600, "up", 128, 3.2), (300, 401, "down", 98, 2.8)],
        jellies=[((120, 420), (120, 330), 0.42)],
        pearls=[(300, 522), (40, 447), (120, 292)],
        puffers=[((60, 540), (210, 540), 0.30), ((380, 300), (380, 180), 0.36)],
        crawlers=[((90, 310, 140, 16), 130, 28)],
        gulls=[(140, 96, 110), (310, 120, 90)],
        tip="Two birds. The water is the only roof you have.",
    ),
    dict(
        name="Siphon",
        period=9.5, tide_low=606, tide_high=123,
        spawn=(200, 575), goal=(210, 125),
        plats=[(0, 600, 420, 20), (0, 525, 130, 16), (290, 525, 130, 16),
               (120, 450, 180, 16), (0, 370, 120, 16), (300, 370, 120, 16),
               (130, 290, 160, 16), (0, 210, 120, 16), (300, 210, 120, 16),
               (140, 145, 140, 16)],
        urchins=[(72, 517), (352, 517), (210, 442), (46, 362), (346, 362),
                 (200, 282)],
        eels=[(160, 600, "up", 118, 2.7), (240, 600, "up", 118, 3.3),
              (210, 466, "down", 92, 2.6)],
        jellies=[((60, 480), (60, 390), 0.46), ((360, 330), (360, 232), 0.46)],
        pearls=[(210, 432), (60, 352), (210, 272)],
        puffers=[((150, 340), (280, 340), 0.34)],
        crawlers=[((130, 290, 160, 16), 170, 32)],
        gulls=[(210, 90, 100)],
        tip="Narrow chimney, fast tide. Grip, wait, climb, grip again.",
    ),
    dict(
        name="Open water",
        period=13.0, tide_low=606, tide_high=113,
        spawn=(28, 575), goal=(360, 115),
        plats=[(0, 600, 420, 20), (0, 515, 160, 16), (230, 455, 190, 16),
               (40, 370, 170, 16), (250, 290, 170, 16), (30, 215, 150, 16),
               (240, 135, 180, 16)],
        urchins=[(120, 507), (300, 447), (90, 362)],
        eels=[(200, 600, "up", 120, 3.6)],
        jellies=[((180, 400), (180, 310), 0.34)],
        pearls=[(40, 497), (290, 437), (160, 352)],
        puffers=[((300, 380), (380, 380), 0.28)],
        crawlers=[],
        gulls=[],
        tip="The last pool. Nothing here is in a hurry. Neither are you.",
        dialogue=[
            ("Old hermit", "Careful at that edge. It isn't another pool."),
            ("Old hermit", "That's all of them, at once, going out."),
            ("Old hermit", "I've been in this one since the spring tide."),
            ("Old hermit", "Good rock. Good light. I stopped climbing."),
            ("Old hermit", "Every pool you crossed is still down there,"),
            ("Old hermit", "filling and emptying, with or without you in it."),
            ("Old hermit", "That's the thing about a tide. It isn't taking"),
            ("Old hermit", "anything from you. It only ever keeps moving."),
            ("Old hermit", "Go on, then. The water's high enough."),
            ("", "The crab lets go of the rock,"),
            ("", "and the sea carries it the rest of the way."),
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


class Jelly:
    """Patrols, charges with an accelerating blink, then discharges a ring."""

    R = 13
    CHARGE_TIME = 3.4
    SHOCK_TIME = 1.0
    SHOCK_R = 40

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

    @property
    def lit(self):
        return self.shock > 0

    def target(self):
        return (lerp(self.p1[0], self.p2[0], self.u),
                lerp(self.p1[1], self.p2[1], self.u))

    def update(self, dt):
        self.pulse += dt * 2.6
        if self.knock > 0:
            self.knock -= dt
            self.spin += self.vx * 0.05
        else:
            self.u += self.dir * self.speed * dt
            if self.u >= 1:
                self.u, self.dir = 1.0, -1
            elif self.u <= 0:
                self.u, self.dir = 0.0, 1
            self.spin *= 0.88

        tx, ty = self.target()
        pull = 0.9 if self.knock <= 0 else 0.12
        self.vx += (tx - self.x) * 0.035 * pull
        self.vy += (ty - self.y) * 0.035 * pull
        self.vx *= 0.90
        self.vy *= 0.90
        self.x += self.vx
        self.y += self.vy

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
        r = self.SHOCK_R if self.lit else self.R
        return rect.colliderect(pygame.Rect(self.x - r, self.y - r, r * 2, r * 2))

    def punched(self, px, py, pr):
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
        pull = 0.9 if self.knock <= 0 else 0.1
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
    the water. Takes two punches: the first sends it flapping back up in a
    temper, the second breaks its nerve and it leaves the pool for good."""

    R = 13
    HP = 2

    def __init__(self, x, y, span):
        self.home = (float(x), float(y))
        self.span = span
        self.x, self.y = float(x), float(y)
        self.t = random.uniform(0, math.tau)
        self.state = "hover"
        self.cool = random.uniform(1.0, 2.5)
        self.vx = self.vy = 0.0
        self.face = 1
        self.flap = random.uniform(0, math.tau)
        self.hp = self.HP
        self.hurt_flash = 0.0
        self.gone = False
        self.sad_t = 0.0

    @property
    def leaving(self):
        return self.state == "flee"

    def body_rect(self):
        return pygame.Rect(int(self.x - 12), int(self.y - 9), 24, 18)

    def collide(self, plats):
        """A gull is a solid bird. It does not fly through rock."""
        r = self.body_rect()
        for p in plats:
            if not r.colliderect(p):
                continue
            # push out along whichever axis is least embedded
            dl = r.right - p.left
            dr = p.right - r.left
            dt_ = r.bottom - p.top
            db = p.bottom - r.top
            m = min(dl, dr, dt_, db)
            if m == dt_:
                self.y = p.top - 9
                self.vy = min(self.vy, 0.0)
            elif m == db:
                self.y = p.bottom + 9
                self.vy = max(self.vy, 0.0)
            elif m == dl:
                self.x = p.left - 12
                self.vx = min(self.vx, 0.0)
            else:
                self.x = p.right + 12
                self.vx = max(self.vx, 0.0)
            if self.state == "dive":
                self.state = "climb"     # clipped a ledge, pull out of the stoop
            r = self.body_rect()

    def update(self, dt, crab, crab_dry, plats):
        self.t += dt * 0.8
        self.hurt_flash = max(0.0, self.hurt_flash - dt)
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
            if self.y < -40 or self.x < -50 or self.x > WORLD_W + 50:
                self.gone = True
            return

        if self.state == "hover":
            self.cool -= dt
            tx = self.home[0] + math.sin(self.t) * self.span
            ty = self.home[1] + math.sin(self.t * 1.7) * 6
            self.vx += (tx - self.x) * 0.02
            self.vy += (ty - self.y) * 0.03
            if self.cool <= 0 and crab_dry and abs(crab.x - self.x) < 150 \
                    and crab.y > self.y:
                self.state = "dive"
                self.tgt = (crab.x, crab.y)
        elif self.state == "dive":
            dx = self.tgt[0] - self.x
            dy = self.tgt[1] - self.y
            d = max(1.0, math.hypot(dx, dy))
            self.vx += dx / d * 0.55
            self.vy += dy / d * 0.60
            if d < 14 or self.y > WORLD_H - 20:
                self.state = "climb"
        else:                                    # climb
            self.vx += (self.home[0] - self.x) * 0.012
            self.vy -= 0.34
            if self.y <= self.home[1] + 8:
                self.state = "hover"
                self.cool = random.uniform(2.2, 4.0)
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
        return rect.colliderect(pygame.Rect(self.x - 10, self.y - 7, 20, 14))

    def punched(self, px, py, pr):
        if self.gone or self.leaving:
            return False
        return math.hypot(self.x - px, self.y - py) <= self.R + pr

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
        self.cool = random.uniform(3.0, 5.0)
        return False


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
        self.eels = [Eel(*e) for e in L["eels"]]
        self.jellies = [Jelly(*j) for j in L["jellies"]]
        self.puffers = [Puffer(*p) for p in L.get("puffers", [])]
        self.crawlers = [Crawler(pygame.Rect(*r), x, sp)
                         for (r, x, sp) in L.get("crawlers", [])]
        self.gulls = [Gull(*g) for g in L.get("gulls", [])]
        self.pearls = [Pearl(*p) for p in L["pearls"]]
        self.crab = Crab(*L["spawn"])
        self.clean = True            # rainbow mode is earned pool by pool
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

    def hurt(self, src_x, src_y):
        c = self.crab
        if c.iframe > 0:
            return
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
            self.state = DEAD
            self.build_dead_menu()
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
        c.vy = clamp(c.vy, -MAX_FALL, MAX_FALL)

        was_ground = c.on_ground
        c.on_ground = False
        c.x += c.vx
        r = c.rect
        for p in self.plats:
            if r.colliderect(p):
                if c.vx > 0:
                    c.x = p.left - CRAB_W / 2
                elif c.vx < 0:
                    c.x = p.right + CRAB_W / 2
                c.vx = 0
                r = c.rect
        c.x = clamp(c.x, CRAB_W / 2, WORLD_W - CRAB_W / 2)

        c.y += c.vy
        r = c.rect
        for p in self.plats:
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
            gl.update(dt, c, depth < 0.25, self.plats)
        self.gulls = [g for g in self.gulls if not g.gone]
        for j in self.jellies:
            if j.update(dt) == "discharge":
                self.parts.ring(j.x, j.y, 20, C_JELLY_HOT, 5.2, 0.6)
                self.parts.burst(j.x, j.y, 12, C_JELLY, 3.2, 0.5, 2.6, 0.0, True)
                self.shake = max(self.shake, 6)

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
                for u in self.urchins:
                    if math.hypot(u.x - px, u.y - py) <= 11 + PUNCH_HIT_R:
                        self.hurt(u.x, u.y)
                        break

        cr = c.hurt_rect
        if c.iframe <= 0:
            for mob in (list(self.urchins) + list(self.eels) + list(self.jellies) +
                        list(self.puffers) + list(self.crawlers) + list(self.gulls)):
                if mob.hits(cr):
                    sx = getattr(mob, "x", None)
                    if sx is None:
                        sx, sy = mob.ax, mob.ay
                    else:
                        sy = mob.y
                    self.hurt(sx, sy)
                    break

        for p in self.pearls:
            p.update(dt, c, self.plats, wy, self.parts)
            if not p.got and math.hypot(p.x - c.x, p.y - c.y) < 20:
                p.got = True
                self.run_pearls += 1
                self.wallet += 1          # spendable in the shop, and it keeps
                self.parts.burst(p.x, p.y, 14, C_SHELL, 3.6, 0.45, 2.4, 0.04, True)

        gx, gy = self.L["goal"]
        if math.hypot(c.x - gx, c.y - gy) < 21 and self.state == PLAY:
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
        b = j.bright()
        col = lerp3(C_JELLY, C_JELLY_HOT, b)
        dark = lerp3(C_JELLY_DARK, C_JELLY_HOT, b * 0.6)
        if j.lit:
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

        squash = 1.0 + math.sin(j.pulse) * 0.11
        rw, rh = Jelly.R * squash, Jelly.R * 0.84 / squash
        for i in range(-2, 3):
            x0 = j.x + i * 4.6
            pts = [(x0, j.y + 2)]
            for k in range(1, 4):
                pts.append((x0 + math.sin(j.pulse * 1.2 + i - k * 0.7) * (2.0 * k),
                            j.y + 2 + k * 6.2))
            pygame.draw.lines(s, dark, False, pts, 3)
            pygame.draw.lines(s, col, False, pts, 1)
        bell = pygame.Rect(int(j.x - rw), int(j.y - rh), int(rw * 2), int(rh * 2))
        pygame.draw.ellipse(s, dark, bell.inflate(3, 3))
        pygame.draw.ellipse(s, col, bell)
        pygame.draw.arc(s, C_WHITE, bell.inflate(-5, -5), 0.6, 2.3, 2)
        # charge meter reads as a filling arc inside the bell
        if not j.lit:
            k = clamp(j.charge / j.charge_time, 0, 1)
            if k > 0.05:
                pygame.draw.arc(s, C_JELLY_HOT, bell.inflate(6, 6),
                                math.pi / 2, math.pi / 2 + math.tau * k, 2)
        if j.knock > 0:
            pygame.draw.arc(s, C_WHITE, bell.inflate(10, 10), j.spin, j.spin + 1.2, 2)

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
        if c.iframe > 0 and int(c.iframe * 22) % 2 == 0:
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
                hip = P(i * 6, 2)
                knee = P(i * 6 + sgn * 3 + trail_x * 0.5, 5 + trail_y * 0.5)
                foot = P(i * 6 + sgn * 6 + trail_x, 10 + trail_y + ph)
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
            if closed:
                pygame.draw.line(s, C_CRAB_DARK, (eye[0] - 3, eye[1]),
                                 (eye[0] + 3, eye[1]), 2)
            else:
                look = P(tipx + c.sx * 1.2 * amt + (f * 0.8 if amt < 0.3 else 0),
                         tipy + c.sy * 1.2 * amt)
                pygame.draw.circle(s, C_INK, (int(look[0]), int(look[1])), 2)

        if self.hat:
            self.draw_hat(s, P, bh, pitch, dnc)

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

    def draw_world(self):
        s = self.world
        wy = self.water_y()
        self.draw_backdrop(s, wy)
        self.draw_plats(s, wy)
        self.draw_water(s, wy)
        self.draw_light(s, wy)
        self.relight_plats(s)
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
        for j in self.jellies:
            self.draw_jelly(s, j)
        for gl in self.gulls:
            self.draw_gull(s, gl)
        self.parts.draw(s)
        self.draw_crab(s, self.crab)
        self.draw_tide_gauge(s, wy)

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
               "hop  hold space, release    punch  J",
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
            ("PUNCH", "J, X, or Z", "aims the way you're holding"),
            ("GRIP", "Hold DOWN on rock", "anchors you against the tide"),
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
                        if ev.key in (pygame.K_j, pygame.K_x, pygame.K_z):
                            c = self.crab
                            if c.punch_cd <= 0:
                                # lock the swing to the direction held at the
                                # moment of the press, facing if nothing is
                                c.punch_ang = c.aim_angle()
                                c.punch_t = PUNCH_TIME
                                c.punch_cd = PUNCH_COOLDOWN
                                c.punch_hit = False
                                self.parts.burst(
                                    c.x + math.cos(c.punch_ang) * 14,
                                    c.y + math.sin(c.punch_ang) * 14,
                                    5, C_FOAM, 2.2, 0.2, 1.8, 0.0)
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
                    self.draw_overlay_card(
                        self.screen, "Washed out",
                        ["The pool took you.",
                         "Pearls this run: %d" % self.run_pearls], C_DANGER)
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