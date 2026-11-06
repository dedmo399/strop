"""
OpenRazer Hardware RGB Matrix Controller & 60 FPS Lighting Studio Engine for Strop Suite.

Provides:
- Backward-compatible `RazerLightingEngine`, `COLOR_PALETTE`, and `get_lighting_engine()`
- Color math utilities (RGB <-> HSV <-> Hex, clamping, additive & linear blending, 2-6 stop gradients)
- Hardware LED topologies and preset zone clusters for Keyboard, Keypad, Mouse, and Controller
- All 16 real-time lighting effects operating on a standardized 60 FPS internal render loop:
  * Core Presets (8): Breathing, Fire, Ripple, Spectrum Cycling, Starlight, Static, Wave, Wheel
  * Common Additions (2): Reactive, Rain
  * Easy/Grid FX (6): Scanner, Color Pulse, Ripple Line, Gradient Fill, Checkerboard, Heatmap
- Multi-layer per-zone compositor, master brightness & speed scalars, and phase-locked device sync
- Persistent lighting profiles & 8 user-saveable swatches in ~/.config/strop/lighting_settings.json
"""

from __future__ import annotations

import colorsys
import json
import math
import os
import random
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from strop_core.layouts.keyboard import MAIN_KEYS, NAV_KEYS, NUMPAD_KEYS
from strop_core.layouts.keypad import (
    DPAD_DATA,
    KEYPAD_GRID,
    SCROLL_DOWN_DATA,
    SCROLL_UP_DATA,
    SPACEBAR_DATA,
    THUMB_BTN_DATA,
)

# ---------------------------------------------------------------------------
# Standard 8 Basic Colors + Black RGB Presets (Backward-compatible)
# ---------------------------------------------------------------------------
COLOR_PALETTE: Dict[str, Dict[str, Any]] = {
    "Green":  {"rgb": (0, 255, 0),     "hex": "#22c55e", "icon": "🟢", "tip": "Official Razer Green (0, 255, 0)"},
    "Red":    {"rgb": (255, 0, 0),     "hex": "#ef4444", "icon": "🔴", "tip": "Bright Red (255, 0, 0)"},
    "Blue":   {"rgb": (0, 100, 255),   "hex": "#3b82f6", "icon": "🔵", "tip": "Bright Blue (0, 100, 255)"},
    "Yellow": {"rgb": (255, 230, 0),   "hex": "#eab308", "icon": "🟡", "tip": "Vibrant Yellow (255, 230, 0)"},
    "Orange": {"rgb": (255, 120, 0),   "hex": "#f97316", "icon": "🟠", "tip": "Bright Orange (255, 120, 0)"},
    "Purple": {"rgb": (170, 0, 255),   "hex": "#a855f7", "icon": "🟣", "tip": "Electric Purple (170, 0, 255)"},
    "Brown":  {"rgb": (140, 70, 20),   "hex": "#854d0e", "icon": "🟤", "tip": "Warm Brown (140, 70, 20)"},
    "White":  {"rgb": (255, 255, 255), "hex": "#ffffff", "icon": "⚪", "tip": "Crisp White (255, 255, 255)"},
    "Black":  {"rgb": (0, 0, 0),       "hex": "#000000", "icon": "⚫", "tip": "LEDs Off / Black (0, 0, 0)"},
}

COLOR_STOCK_GREEN: Tuple[int, int, int] = COLOR_PALETTE["Green"]["rgb"]
COLOR_REMAPPED_RED: Tuple[int, int, int] = COLOR_PALETTE["Red"]["rgb"]
COLOR_OFF: Tuple[int, int, int] = COLOR_PALETTE["Black"]["rgb"]

# 8 Factory-preset vibrant quick swatches (Section 3.1)
FACTORY_SWATCHES: List[Tuple[int, int, int]] = [
    (0, 255, 0),     # Razer Green
    (255, 0, 85),    # Cyber Magenta
    (0, 210, 255),   # Electric Cyan
    (255, 120, 0),   # Solar Orange
    (170, 0, 255),   # Neon Violet
    (255, 230, 0),   # Gold Yellow
    (255, 30, 30),   # Crimson Red
    (255, 255, 255), # Pure White
]

DEFAULT_USER_SWATCHES: List[Tuple[int, int, int]] = [
    (34, 197, 94),
    (59, 130, 246),
    (236, 72, 153),
    (249, 115, 22),
    (168, 85, 247),
    (20, 184, 166),
    (234, 179, 8),
    (248, 250, 252),
]

# Standard physical key unit in millimeters
KEY_UNIT_MM: float = 19.05
TARGET_FPS: int = 60
FRAME_INTERVAL_MS: int = 16


# ---------------------------------------------------------------------------
# Color & Gradient Math Utilities (Section 3.1)
# ---------------------------------------------------------------------------
RGBTuple = Tuple[int, int, int]
GradientStop = Tuple[float, RGBTuple]


def clamp_channel(val: float | int) -> int:
    """Clamps a single color channel to [0, 255]."""
    return max(0, min(255, int(round(val))))


def clamp_rgb(r: float | int, g: float | int, b: float | int) -> RGBTuple:
    """Clamps an (R, G, B) tuple to integers in [0, 255]."""
    return (clamp_channel(r), clamp_channel(g), clamp_channel(b))


def rgb_to_hex(rgb: RGBTuple) -> str:
    """Formats an RGB tuple as a 6-character uppercase hex code (#RRGGBB)."""
    r, g, b = clamp_rgb(*rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def hex_to_rgb(hex_str: str) -> Optional[RGBTuple]:
    """Parses a 6-character (or 3-character) hex string into an RGB tuple."""
    if not isinstance(hex_str, str):
        return None
    s = hex_str.strip().lstrip("#")
    if len(s) == 3 and all(c in "0123456789abcdefABCDEF" for c in s):
        s = "".join(c * 2 for c in s)
    if len(s) != 6 or not all(c in "0123456789abcdefABCDEF" for c in s):
        return None
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def rgb_to_hsv(r: int, g: int, b: int) -> Tuple[float, float, float]:
    """Converts RGB (0-255) to HSV where H is [0, 360), S is [0, 1], V is [0, 1]."""
    rf, gf, bf = clamp_channel(r) / 255.0, clamp_channel(g) / 255.0, clamp_channel(b) / 255.0
    h, s, v = colorsys.rgb_to_hsv(rf, gf, bf)
    return ((h * 360.0) % 360.0, max(0.0, min(1.0, s)), max(0.0, min(1.0, v)))


def hsv_to_rgb(h_deg: float, s: float, v: float) -> RGBTuple:
    """Converts HSV (H in degrees [0, 360], S in [0, 1], V in [0, 1]) to RGB (0-255)."""
    h_norm = (float(h_deg) % 360.0) / 360.0
    s_clamped = max(0.0, min(1.0, float(s)))
    v_clamped = max(0.0, min(1.0, float(v)))
    rf, gf, bf = colorsys.hsv_to_rgb(h_norm, s_clamped, v_clamped)
    return clamp_rgb(rf * 255.0, gf * 255.0, bf * 255.0)


def lerp_color(c1: RGBTuple, c2: RGBTuple, t: float) -> RGBTuple:
    """Linearly interpolates between two RGB colors for t in [0, 1]."""
    tc = max(0.0, min(1.0, float(t)))
    return clamp_rgb(
        c1[0] + (c2[0] - c1[0]) * tc,
        c1[1] + (c2[1] - c1[1]) * tc,
        c1[2] + (c2[2] - c1[2]) * tc,
    )


def add_colors(c1: RGBTuple, c2: RGBTuple) -> RGBTuple:
    """Additively blends two RGB colors with clamping at 255."""
    return clamp_rgb(c1[0] + c2[0], c1[1] + c2[1], c1[2] + c2[2])


def scale_color(c: RGBTuple, factor: float) -> RGBTuple:
    """Scales an RGB color by a brightness scalar in [0, 1]."""
    f = max(0.0, min(1.0, float(factor)))
    return clamp_rgb(c[0] * f, c[1] * f, c[2] * f)


def sample_gradient(stops: List[GradientStop], pos: float, wrap: bool = False) -> RGBTuple:
    """
    Evaluates a multi-stop color gradient (2 to 6 stops) at position `pos` in [0, 1].
    Each stop is `(offset_0_to_1, (r, g, b))`.
    """
    if not stops:
        return (0, 255, 0)
    if len(stops) == 1:
        return clamp_rgb(*stops[0][1])

    ordered = sorted(stops, key=lambda item: float(item[0]))
    p = float(pos) % 1.0 if wrap else max(0.0, min(1.0, float(pos)))

    if p <= ordered[0][0]:
        return clamp_rgb(*ordered[0][1])
    if p >= ordered[-1][0]:
        return clamp_rgb(*ordered[-1][1])

    for i in range(len(ordered) - 1):
        p0, c0 = ordered[i]
        p1, c1 = ordered[i + 1]
        if p0 <= p <= p1:
            span = p1 - p0
            if span <= 1e-6:
                return clamp_rgb(*c1)
            local_t = (p - p0) / span
            return lerp_color(c0, c1, local_t)

    return clamp_rgb(*ordered[-1][1])


def sample_rainbow(pos: float) -> RGBTuple:
    """Evaluates a seamless 360-degree rainbow at normalized position `pos`."""
    return hsv_to_rgb((float(pos) % 1.0) * 360.0, 1.0, 1.0)


def _hash_noise_1d(x: int, seed: int = 1337) -> float:
    """Deterministic pseudo-random float in [0, 1] for integer coordinate x."""
    n = (x * 374761393 + seed * 668265263) & 0xFFFFFFFF
    n = (n ^ (n >> 13)) * 1274126177 & 0xFFFFFFFF
    n = n ^ (n >> 16)
    return (n & 0xFFFFFF) / float(0xFFFFFF)


def coherent_noise_2d(x: float, y: float, seed: int = 42) -> float:
    """Smooth 2D Perlin-style value noise returning a float in [0.0, 1.0]."""
    xi = math.floor(x)
    yi = math.floor(y)
    xf = x - xi
    yf = y - yi
    # Smoothstep fade curves
    u = xf * xf * (3.0 - 2.0 * xf)
    v = yf * yf * (3.0 - 2.0 * yf)

    n00 = _hash_noise_1d(xi + yi * 57, seed)
    n10 = _hash_noise_1d(xi + 1 + yi * 57, seed)
    n01 = _hash_noise_1d(xi + (yi + 1) * 57, seed)
    n11 = _hash_noise_1d(xi + 1 + (yi + 1) * 57, seed)

    nx0 = n00 + u * (n10 - n00)
    nx1 = n01 + u * (n11 - n01)
    return max(0.0, min(1.0, nx0 + v * (nx1 - nx0)))


# ---------------------------------------------------------------------------
# Device Topologies & Zone Mapping (Section 3.3)
# ---------------------------------------------------------------------------
@dataclass
class LEDNode:
    id: str
    label: str
    zone: str
    row: int
    col: int
    x_mm: float
    y_mm: float
    nx: float
    ny: float
    rx: float
    ry: float
    rw: float
    rh: float
    shape: str = "rect"
    scancode: Optional[int] = None


DEVICE_CATEGORIES = ("keyboard", "keypad", "mouse", "controller")


def _finalize_normalized_coords(nodes: List[LEDNode]) -> List[LEDNode]:
    if not nodes:
        return nodes
    min_x = min(n.rx for n in nodes)
    max_x = max(n.rx + n.rw for n in nodes)
    min_y = min(n.ry for n in nodes)
    max_y = max(n.ry + n.rh for n in nodes)
    span_x = max(1.0, max_x - min_x)
    span_y = max(1.0, max_y - min_y)
    for n in nodes:
        cx = n.rx + n.rw * 0.5
        cy = n.ry + n.rh * 0.5
        n.nx = max(0.0, min(1.0, (cx - min_x) / span_x))
        n.ny = max(0.0, min(1.0, (cy - min_y) / span_y))
        n.x_mm = (cx - min_x) * (KEY_UNIT_MM / 36.0)
        n.y_mm = (cy - min_y) * (KEY_UNIT_MM / 36.0)
    return nodes


# Standard OpenRazer 6x22 Keyboard Matrix Coordinate Map (Row, Col)
OPENRAZER_KEYBOARD_6X22_MAP: Dict[str, List[Tuple[int, int]]] = {
    # Row 0: Esc, F1..F12, PrtSc..Pause, Media
    "esc": [(0, 0), (0, 1)],
    "f1": [(0, 2), (0, 3)], "f2": [(0, 4)], "f3": [(0, 5)], "f4": [(0, 6)],
    "f5": [(0, 7)], "f6": [(0, 8)], "f7": [(0, 9)], "f8": [(0, 10)],
    "f9": [(0, 11)], "f10": [(0, 12)], "f11": [(0, 13)], "f12": [(0, 14)],
    "prtsc": [(0, 15)], "scrlk": [(0, 16)], "pause": [(0, 17)],
    "mute": [(0, 18)], "voldn": [(0, 19)], "volup": [(0, 20)], "play": [(0, 21)],
    # Row 1: Number Row, Ins..PgUp, Numpad Top
    "grave": [(1, 0), (1, 1)],
    "k1": [(1, 2)], "k2": [(1, 3)], "k3": [(1, 4)], "k4": [(1, 5)],
    "k5": [(1, 6)], "k6": [(1, 7)], "k7": [(1, 8)], "k8": [(1, 9)],
    "k9": [(1, 10)], "k0": [(1, 11)], "minus": [(1, 12)], "equal": [(1, 13)],
    "bsp": [(1, 14)],
    "ins": [(1, 15)], "home": [(1, 16)], "pgup": [(1, 17)],
    "numlk": [(1, 18)], "kp_slash": [(1, 19)], "kp_star": [(1, 20)], "kp_minus": [(1, 21)],
    # Row 2: Tab / QWERTY Row, Del..PgDn, Numpad 7..9/+
    "tab": [(2, 0), (2, 1)],
    "q": [(2, 2)], "w": [(2, 3)], "e": [(2, 4)], "r": [(2, 5)],
    "t": [(2, 6)], "y": [(2, 7)], "u": [(2, 8)], "i": [(2, 9)],
    "o": [(2, 10)], "p": [(2, 11)], "lbrk": [(2, 12)], "rbrk": [(2, 13)],
    "bslash": [(2, 14)],
    "del": [(2, 15)], "end": [(2, 16)], "pgdn": [(2, 17)],
    "kp_7": [(2, 18)], "kp_8": [(2, 19)], "kp_9": [(2, 20)], "kp_plus": [(2, 21), (3, 21)],
    # Row 3: Caps / Home Row, Numpad 4..6
    "caps": [(3, 0), (3, 1)],
    "a": [(3, 2)], "s": [(3, 3)], "d": [(3, 4)], "f": [(3, 5)],
    "g": [(3, 6)], "h": [(3, 7)], "j": [(3, 8)], "k": [(3, 9)],
    "l": [(3, 10)], "semi": [(3, 11)], "quote": [(3, 12)],
    "enter": [(3, 13), (3, 14)],
    "kp_4": [(3, 18)], "kp_5": [(3, 19)], "kp_6": [(3, 20)],
    # Row 4: Shift Row, Up Arrow, Numpad 1..3/Enter
    "lshift": [(4, 0), (4, 1), (4, 2)],
    "z": [(4, 3)], "x": [(4, 4)], "c": [(4, 5)], "v": [(4, 6)],
    "b": [(4, 7)], "n": [(4, 8)], "m": [(4, 9)], "comma": [(4, 10)],
    "dot": [(4, 11)], "slash": [(4, 12)],
    "rshift": [(4, 13), (4, 14)],
    "up": [(4, 16)],
    "kp_1": [(4, 18)], "kp_2": [(4, 19)], "kp_3": [(4, 20)], "kp_enter": [(4, 21), (5, 21)],
    # Row 5: Bottom Modifier Row, Left/Down/Right Arrows, Numpad 0/.
    "lctrl": [(5, 0), (5, 1)], "lwin": [(5, 2)], "lalt": [(5, 3)],
    "space": [(5, 4), (5, 5), (5, 6), (5, 7), (5, 8), (5, 9), (5, 10)],
    "ralt": [(5, 11)], "fn": [(5, 12)], "menu": [(5, 13)], "rctrl": [(5, 14)],
    "left": [(5, 15)], "down": [(5, 16)], "right": [(5, 17)],
    "kp_0": [(5, 18), (5, 19)], "kp_dot": [(5, 20)],
}


def build_keyboard_topology() -> List[LEDNode]:
    """Builds the full 108-key keyboard matrix + 18-segment perimeter underglow."""
    nodes: List[LEDNode] = []
    unit_px = 34.0
    row_h = 32.0
    gap_px = 3.0
    pad_x = 28.0
    pad_y = 26.0

    # 1. Main block (rows 0..5)
    for r, row in enumerate(MAIN_KEYS):
        cursor_u = 0.0
        for c_idx, k in enumerate(row):
            w_u = float(k.get("w", 1.0))
            rx = pad_x + cursor_u * (unit_px + gap_px)
            ry = pad_y + (r + (0.35 if r > 0 else 0.0)) * (row_h + gap_px)
            rw = w_u * unit_px + max(0.0, w_u - 1.0) * gap_px
            rh = row_h

            kid = k["id"]
            if r == 0 and kid.startswith("f"):
                zone = "function_row"
            elif r == 1 and kid in {"k1", "k2", "k3", "k4", "k5", "k6", "k7", "k8", "k9", "k0"}:
                zone = "number_row"
            elif kid in {"w", "a", "s", "d"}:
                zone = "wasd_arrows"
            else:
                zone = "main_keys"

            mapped_cells = OPENRAZER_KEYBOARD_6X22_MAP.get(kid)
            hw_col = mapped_cells[-1][1] if mapped_cells else (c_idx + 1)

            nodes.append(LEDNode(
                id=kid, label=k["l"], zone=zone,
                row=r, col=hw_col,
                x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
                rx=rx, ry=ry, rw=rw, rh=rh,
                shape="rect", scancode=k.get("c"),
            ))
            cursor_u += w_u + float(k.get("gap", 0.0))

    # 2. Navigation & Arrow cluster
    nav_start_u = 15.4
    for r, row in enumerate(NAV_KEYS):
        for c_idx, k in enumerate(row):
            col_off = k.get("col", c_idx)
            u_pos = nav_start_u + col_off
            rx = pad_x + u_pos * (unit_px + gap_px)
            ry = pad_y + (r + (0.35 if r > 0 else 0.0)) * (row_h + gap_px)
            kid = k["id"]
            zone = "wasd_arrows" if kid in {"up", "down", "left", "right"} else "nav_keys"
            nodes.append(LEDNode(
                id=kid, label=k["l"], zone=zone,
                row=r, col=15 + col_off,
                x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
                rx=rx, ry=ry, rw=unit_px, rh=row_h,
                shape="rect", scancode=k.get("c"),
            ))

    # 3. Numpad & Media cluster
    num_start_u = 18.8
    for r, row in enumerate(NUMPAD_KEYS):
        for c_idx, k in enumerate(row):
            col_off = k.get("col", c_idx)
            w_u = float(k.get("w", 1.0))
            h_u = float(k.get("h", 1.0))
            u_pos = num_start_u + col_off
            rx = pad_x + u_pos * (unit_px + gap_px)
            ry = pad_y + (r + (0.35 if r > 0 else 0.0)) * (row_h + gap_px)
            rw = w_u * unit_px + max(0.0, w_u - 1.0) * gap_px
            rh = h_u * row_h + max(0.0, h_u - 1.0) * gap_px
            kid = k["id"]
            zone = "numpad" if r >= 1 else "media"
            nodes.append(LEDNode(
                id=kid, label=k["l"], zone=zone,
                row=r, col=18 + col_off,
                x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
                rx=rx, ry=ry, rw=rw, rh=rh,
                shape="rect", scancode=k.get("c"),
            ))

    # 4. Perimeter Underglow (18 segments around chassis edges)
    total_w = pad_x + 22.8 * (unit_px + gap_px)
    total_h = pad_y + 6.35 * (row_h + gap_px)
    ug_idx = 0
    # Top edge (6 segments)
    for i in range(6):
        seg_w = (total_w - 20.0) / 6.0 - 4.0
        rx = 12.0 + i * (seg_w + 4.0)
        nodes.append(LEDNode(
            id=f"underglow_{ug_idx}", label=f"UG{ug_idx + 1}", zone="underglow",
            row=0, col=i * 4, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=rx, ry=6.0, rw=seg_w, rh=8.0, shape="bar",
        ))
        ug_idx += 1
    # Right edge (3 segments)
    for i in range(3):
        seg_h = (total_h - 16.0) / 3.0 - 4.0
        ry = 18.0 + i * (seg_h + 4.0)
        nodes.append(LEDNode(
            id=f"underglow_{ug_idx}", label=f"UG{ug_idx + 1}", zone="underglow",
            row=i * 2 + 1, col=23, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=total_w + 4.0, ry=ry, rw=8.0, rh=seg_h, shape="bar",
        ))
        ug_idx += 1
    # Bottom edge (6 segments, right-to-left)
    for i in range(6):
        seg_w = (total_w - 20.0) / 6.0 - 4.0
        rx = 12.0 + (5 - i) * (seg_w + 4.0)
        nodes.append(LEDNode(
            id=f"underglow_{ug_idx}", label=f"UG{ug_idx + 1}", zone="underglow",
            row=6, col=(5 - i) * 4, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=rx, ry=total_h + 8.0, rw=seg_w, rh=8.0, shape="bar",
        ))
        ug_idx += 1
    # Left edge (3 segments, bottom-to-top)
    for i in range(3):
        seg_h = (total_h - 16.0) / 3.0 - 4.0
        ry = 18.0 + (2 - i) * (seg_h + 4.0)
        nodes.append(LEDNode(
            id=f"underglow_{ug_idx}", label=f"UG{ug_idx + 1}", zone="underglow",
            row=(2 - i) * 2 + 1, col=0, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=6.0, ry=ry, rw=8.0, rh=seg_h, shape="bar",
        ))
        ug_idx += 1

    return _finalize_normalized_coords(nodes)


def build_keypad_topology() -> List[LEDNode]:
    """Builds the 20-key Tartarus/Orbweaver keypad grid + Scroll Wheel + Thumb/D-Pad cluster."""
    nodes: List[LEDNode] = []
    key_w, key_h = 54.0, 48.0
    gap = 6.0
    pad_x, pad_y = 40.0, 32.0

    movement_ids = {"grid-1-2", "grid-2-1", "grid-2-2", "grid-2-3"}
    for r, row in enumerate(KEYPAD_GRID):
        for c, item in enumerate(row):
            kid = f"grid-{r}-{c}"
            rx = pad_x + c * (key_w + gap)
            ry = pad_y + r * (key_h + gap)
            zone = "wasd_dpad" if kid in movement_ids else "main_grid"
            nodes.append(LEDNode(
                id=kid, label=item["l"], zone=zone,
                row=r, col=c, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
                rx=rx, ry=ry, rw=key_w, rh=key_h,
                shape="rect", scancode=item.get("c"),
            ))

    # Scroll Wheel in row 3 col 4
    scr_x = pad_x + 4 * (key_w + gap)
    scr_y = pad_y + 3 * (key_h + gap)
    nodes.append(LEDNode(
        id=SCROLL_UP_DATA["id"], label="Scr↑", zone="thumb_cluster",
        row=3, col=4, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=scr_x, ry=scr_y, rw=key_w, rh=22.0, shape="pill",
    ))
    nodes.append(LEDNode(
        id=SCROLL_DOWN_DATA["id"], label="Scr↓", zone="thumb_cluster",
        row=3, col=4, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=scr_x, ry=scr_y + 26.0, rw=key_w, rh=22.0, shape="pill",
    ))

    # Thumb cluster on the right
    thumb_x = pad_x + 5.6 * (key_w + gap)
    nodes.append(LEDNode(
        id=THUMB_BTN_DATA["id"], label="Thumb", zone="thumb_cluster",
        row=1, col=6, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=thumb_x + 36.0, ry=pad_y + 8.0, rw=68.0, rh=36.0,
        shape="pill", scancode=THUMB_BTN_DATA.get("c"),
    ))

    dpad_offsets = {
        "nw": (0, 0), "n": (1, 0), "ne": (2, 0),
        "w":  (0, 1),              "e":  (2, 1),
        "sw": (0, 2), "s": (1, 2), "se": (2, 2),
    }
    dpad_base_y = pad_y + 56.0
    for dkey, (dc, dr) in dpad_offsets.items():
        dinfo = DPAD_DATA[dkey]
        nodes.append(LEDNode(
            id=f"dpad-{dkey}", label=dinfo["l"], zone="wasd_dpad",
            row=1 + dr, col=5 + dc, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=thumb_x + dc * 44.0, ry=dpad_base_y + dr * 40.0, rw=40.0, rh=36.0,
            shape="rect", scancode=dinfo.get("c"),
        ))

    nodes.append(LEDNode(
        id=SPACEBAR_DATA["id"], label="Space (20)", zone="thumb_cluster",
        row=4, col=6, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=thumb_x + 12.0, ry=dpad_base_y + 130.0, rw=112.0, rh=42.0,
        shape="pill", scancode=SPACEBAR_DATA.get("c"),
    ))

    return _finalize_normalized_coords(nodes)


def build_mouse_topology() -> List[LEDNode]:
    """Builds the multi-zone Mouse LED topology (Scroll Wheel, Palm Logo, Left/Right Accent Rails, Click plates)."""
    nodes: List[LEDNode] = []
    cx = 260.0

    # Left & Right Click Top Plates (Row 0)
    nodes.append(LEDNode(
        id="btn_left", label="L-Click", zone="click_plates",
        row=0, col=1, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=cx - 72.0, ry=32.0, rw=54.0, rh=64.0, shape="pill", scancode=272,
    ))
    nodes.append(LEDNode(
        id="btn_right", label="R-Click", zone="click_plates",
        row=0, col=3, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=cx + 18.0, ry=32.0, rw=54.0, rh=64.0, shape="pill", scancode=273,
    ))

    # Scroll Wheel (2 LEDs: Top & Bottom of wheel)
    nodes.append(LEDNode(
        id="scroll_wheel_top", label="Wheel ↑", zone="scroll_wheel",
        row=0, col=2, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=cx - 12.0, ry=38.0, rw=24.0, rh=26.0, shape="pill", scancode=274,
    ))
    nodes.append(LEDNode(
        id="scroll_wheel_bottom", label="Wheel ↓", zone="scroll_wheel",
        row=1, col=2, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=cx - 12.0, ry=68.0, rw=24.0, rh=26.0, shape="pill", scancode=274,
    ))

    # Left & Right 7-segment Chroma Accent Rails (Rows 0..6)
    for i in range(7):
        ry = 36.0 + i * 28.0
        curve_offset = math.sin((i / 6.0) * math.pi) * 10.0
        nodes.append(LEDNode(
            id=f"left_rail_{i}", label=f"L{i + 1}", zone="accent_rails",
            row=i, col=0, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=cx - 96.0 - curve_offset, ry=ry, rw=16.0, rh=22.0, shape="bar",
        ))
        nodes.append(LEDNode(
            id=f"right_rail_{i}", label=f"R{i + 1}", zone="accent_rails",
            row=i, col=4, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=cx + 80.0 + curve_offset, ry=ry, rw=16.0, rh=22.0, shape="bar",
        ))

    # Palm / Body Logo (Centered lower body)
    nodes.append(LEDNode(
        id="palm_logo", label="THS Logo", zone="palm_logo",
        row=5, col=2, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=cx - 28.0, ry=152.0, rw=56.0, rh=56.0, shape="circle",
    ))

    return _finalize_normalized_coords(nodes)


def build_controller_topology() -> List[LEDNode]:
    """
    Builds the Controller LED topology:
    - Top Lightbar (5 LEDs) & Bottom Lightbar (5 LEDs)
    - Left & Right Shoulder Bumpers (2 LEDs, row 0)
    - Left Thumbstick Halo (8 radial LEDs) & Right Thumbstick Halo (8 radial LEDs)
    - Action Face Buttons A, B, X, Y (4 LEDs)
    """
    nodes: List[LEDNode] = []
    cx = 300.0

    # Shoulder Bumpers (Row 0)
    nodes.append(LEDNode(
        id="bumper_left", label="LB", zone="lightbar",
        row=0, col=1, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=cx - 175.0, ry=18.0, rw=76.0, rh=22.0, shape="pill",
    ))
    nodes.append(LEDNode(
        id="bumper_right", label="RB", zone="lightbar",
        row=0, col=7, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
        rx=cx + 99.0, ry=18.0, rw=76.0, rh=22.0, shape="pill",
    ))

    # Top Lightbar (5 segments)
    for i in range(5):
        nodes.append(LEDNode(
            id=f"top_lightbar_{i}", label=f"TL{i + 1}", zone="lightbar",
            row=0, col=2 + i, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=cx - 85.0 + i * 35.0, ry=26.0, rw=30.0, rh=12.0, shape="bar",
        ))

    # Left Thumbstick 8-LED Circular Halo (centered at cx - 115, y = 105)
    l_cx, l_cy, halo_r = cx - 115.0, 105.0, 38.0
    for i in range(8):
        angle = (i / 8.0) * 2.0 * math.pi - math.pi / 2.0
        hx = l_cx + math.cos(angle) * halo_r - 11.0
        hy = l_cy + math.sin(angle) * halo_r - 11.0
        row_idx = 1 if math.sin(angle) < -0.3 else (3 if math.sin(angle) > 0.3 else 2)
        nodes.append(LEDNode(
            id=f"lstick_halo_{i}", label=f"LS{i + 1}", zone="thumbstick_halos",
            row=row_idx, col=1 if math.cos(angle) < 0 else 2,
            x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=hx, ry=hy, rw=22.0, rh=22.0, shape="circle",
        ))

    # Right Thumbstick 8-LED Circular Halo (centered at cx + 45, y = 165)
    r_cx, r_cy = cx + 45.0, 165.0
    for i in range(8):
        angle = (i / 8.0) * 2.0 * math.pi - math.pi / 2.0
        hx = r_cx + math.cos(angle) * halo_r - 11.0
        hy = r_cy + math.sin(angle) * halo_r - 11.0
        row_idx = 3 if math.sin(angle) < -0.3 else (5 if math.sin(angle) > 0.3 else 4)
        nodes.append(LEDNode(
            id=f"rstick_halo_{i}", label=f"RS{i + 1}", zone="thumbstick_halos",
            row=row_idx, col=5 if math.cos(angle) < 0 else 6,
            x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=hx, ry=hy, rw=22.0, rh=22.0, shape="circle",
        ))

    # Action Face Buttons (X, Y, A, B diamond cluster at cx + 125, y = 98)
    f_cx, f_cy = cx + 125.0, 98.0
    face_defs = [
        ("face_y", "Y", f_cx, f_cy - 32.0, 1, 7, 21),
        ("face_x", "X", f_cx - 32.0, f_cy, 2, 6, 45),
        ("face_b", "B", f_cx + 32.0, f_cy, 2, 8, 48),
        ("face_a", "A", f_cx, f_cy + 32.0, 3, 7, 30),
    ]
    for fid, flbl, fx, fy, frow, fcol, sc in face_defs:
        nodes.append(LEDNode(
            id=fid, label=flbl, zone="face_buttons",
            row=frow, col=fcol, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=fx - 15.0, ry=fy - 15.0, rw=30.0, rh=30.0,
            shape="circle", scancode=sc,
        ))

    # Bottom Lightbar (5 segments)
    for i in range(5):
        nodes.append(LEDNode(
            id=f"bottom_lightbar_{i}", label=f"BL{i + 1}", zone="lightbar",
            row=6, col=2 + i, x_mm=0.0, y_mm=0.0, nx=0.0, ny=0.0,
            rx=cx - 85.0 + i * 35.0, ry=222.0, rw=30.0, rh=12.0, shape="bar",
        ))

    return _finalize_normalized_coords(nodes)


def build_device_topology(category: str) -> List[LEDNode]:
    """Returns the list of LEDNode definitions for a device category."""
    cat = (category or "keyboard").lower().strip()
    if cat == "keypad":
        return build_keypad_topology()
    if cat == "mouse":
        return build_mouse_topology()
    if cat == "controller":
        return build_controller_topology()
    return build_keyboard_topology()


def get_preset_clusters(category: str, nodes: Optional[List[LEDNode]] = None) -> Dict[str, Set[str]]:
    """
    Returns preset selection cluster mappings (cluster label -> set of LED IDs)
    matching Section 3.3 Zone Assignment & Hardware Mapping.
    """
    cat = (category or "keyboard").lower().strip()
    topo = nodes if nodes is not None else build_device_topology(cat)
    all_ids = {n.id for n in topo}

    if cat == "keyboard":
        return {
            "All Keys": {n.id for n in topo if n.zone != "underglow"},
            "WASD + Arrow Keys": {n.id for n in topo if n.zone == "wasd_arrows"},
            "Number Row (1–0)": {n.id for n in topo if n.zone == "number_row"},
            "Numpad": {n.id for n in topo if n.zone == "numpad"},
            "Function Row (F1–F12)": {n.id for n in topo if n.zone == "function_row"},
            "Perimeter Underglow": {n.id for n in topo if n.zone == "underglow"},
        }
    if cat == "keypad":
        return {
            "All Keys": all_ids,
            "Main Grid (01–19)": {n.id for n in topo if n.id.startswith("grid-")},
            "WASD + D-Pad": {n.id for n in topo if n.zone == "wasd_dpad"},
            "Thumb + Scroll": {n.id for n in topo if n.zone == "thumb_cluster"},
        }
    if cat == "mouse":
        return {
            "Scroll Wheel": {n.id for n in topo if n.zone == "scroll_wheel"},
            "Palm/Body Logo": {n.id for n in topo if n.zone == "palm_logo"},
            "Left/Right Accent Rails": {n.id for n in topo if n.zone == "accent_rails"},
        }
    if cat == "controller":
        return {
            "Left/Right Thumbstick Halos": {n.id for n in topo if n.zone == "thumbstick_halos"},
            "Action Face Buttons": {n.id for n in topo if n.zone == "face_buttons"},
            "Top/Bottom Lightbar": {n.id for n in topo if n.zone == "lightbar"},
        }
    return {"All LEDs": all_ids}


def select_nodes_in_rect(
    nodes: List[LEDNode],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> Set[str]:
    """Returns IDs of all LED nodes intersecting the marquee selection rectangle."""
    left, right = min(x1, x2), max(x1, x2)
    top, bottom = min(y1, y2), max(y1, y2)
    selected: Set[str] = set()
    for n in nodes:
        nr_right = n.rx + n.rw
        nr_bottom = n.ry + n.rh
        if n.rx <= right and nr_right >= left and n.ry <= bottom and nr_bottom >= top:
            selected.add(n.id)
    return selected


# ---------------------------------------------------------------------------
# Effect Catalog & Default Parameters (Sections 2.1, 2.2, 2.3)
# ---------------------------------------------------------------------------
CLASSIC_FLAME_GRADIENT: List[GradientStop] = [
    (0.0, (180, 0, 0)),
    (0.45, (255, 90, 0)),
    (0.85, (255, 210, 0)),
    (1.0, (255, 255, 180)),
]

BLUE_GAS_GRADIENT: List[GradientStop] = [
    (0.0, (0, 35, 160)),
    (0.5, (0, 180, 255)),
    (0.85, (140, 240, 255)),
    (1.0, (255, 255, 255)),
]

THERMAL_HEATMAP_GRADIENT: List[GradientStop] = [
    (0.0, (0, 60, 255)),    # Cold Blue
    (0.35, (0, 230, 100)),  # Warm Green
    (0.7, (255, 220, 0)),   # Hot Yellow
    (1.0, (255, 20, 20)),   # Peak Red
]

EFFECT_SPECIFICATIONS: Dict[str, Dict[str, Any]] = {
    # 2.1 Core Presets from Menu (8)
    "breathing": {
        "id": "breathing",
        "name": "Breathing",
        "group": "Core Presets",
        "icon": "🌬️",
        "description": "Smooth ease-in-out sine respiration curve with a 200 ms dark hold at 0% brightness.",
        "defaults": {
            "speed_s": 4.0,          # Slow 8.0s, Medium 4.0s, Fast 1.5s
            "color_mode": "Single",  # Single | Two Alternating | Random
            "color1": (0, 255, 0),
            "color2": (0, 180, 255),
        },
    },
    "fire": {
        "id": "fire",
        "name": "Fire",
        "group": "Core Presets",
        "icon": "🔥",
        "description": "Upward organic flames using 2D Perlin noise and a vertical cooling gradient.",
        "defaults": {
            "flicker_hz": 30.0,             # 10 Hz to 60 Hz
            "theme": "Classic Flame",       # Classic Flame | Blue Gas | Custom Duo-Tone
            "color1": (255, 30, 0),
            "color2": (255, 220, 0),
            "gradient_stops": list(CLASSIC_FLAME_GRADIENT),
        },
    },
    "ripple": {
        "id": "ripple",
        "name": "Ripple",
        "group": "Core Presets",
        "icon": "◎",
        "description": "Expanding circular ring originating from pressed keys with additive intersection blending.",
        "defaults": {
            "speed_mm_s": 220.0,     # 50 mm/s to 500 mm/s
            "spread_units": 2.0,     # 1 to 4 key-units
            "color_mode": "Single",  # Single | Random | Rainbow
            "color1": (0, 255, 128),
            "rest_color": (0, 0, 0),
        },
    },
    "spectrum_cycling": {
        "id": "spectrum_cycling",
        "name": "Spectrum Cycling",
        "group": "Core Presets",
        "icon": "🌈",
        "description": "Continuously shifts all LEDs through the 360° HSV gamut in unison.",
        "defaults": {
            "duration_s": 10.0,      # 2.0s (Fast) to 60.0s (Slow)
        },
    },
    "starlight": {
        "id": "starlight",
        "name": "Starlight",
        "group": "Core Presets",
        "icon": "✨",
        "description": "Asynchronous twinkling LEDs over a dark or dim base state.",
        "defaults": {
            "density": "Medium",         # Low (5%) | Medium (15%) | High (35%)
            "duration_s": 1.2,           # 0.3s to 3.0s
            "color_mode": "Monochrome",  # Monochrome | Two-Tone | Random
            "color1": (255, 255, 255),
            "color2": (0, 210, 255),
            "rest_color": (6, 10, 18),
        },
    },
    "static": {
        "id": "static",
        "name": "Static",
        "group": "Core Presets",
        "icon": "💡",
        "description": "Locks all selected LEDs to a constant, unchanging solid color.",
        "defaults": {
            "color1": (0, 255, 0),
        },
    },
    "wave": {
        "id": "wave",
        "name": "Wave",
        "group": "Core Presets",
        "icon": "🌊",
        "description": "Continuous smooth color gradient moving linearly or radially across the device.",
        "defaults": {
            "direction": "Left-to-Right",  # Left-to-Right | Right-to-Left | Top-to-Bottom | Bottom-to-Top | Radial Outward | Radial Inward
            "speed": 1.2,                  # cycles per second
            "wavelength": 1.0,
            "palette_mode": "Rainbow",     # Rainbow | Custom Gradient
            "gradient_stops": [
                (0.0, (0, 255, 100)),
                (0.5, (0, 160, 255)),
                (1.0, (170, 0, 255)),
            ],
        },
    },
    "wheel": {
        "id": "wheel",
        "name": "Wheel",
        "group": "Core Presets",
        "icon": "🎡",
        "description": "Rotates a circular color palette around the geometric center using atan2(Y, X).",
        "defaults": {
            "rpm": 30.0,                 # 5 RPM to 120 RPM
            "direction": "Clockwise",    # Clockwise | Counter-clockwise
            "palette_mode": "Rainbow",   # Rainbow | Custom Wheel
            "gradient_stops": [
                (0.0, (255, 0, 85)),
                (0.33, (0, 210, 255)),
                (0.66, (0, 255, 100)),
                (1.0, (255, 230, 0)),
            ],
        },
    },
    # 2.2 Standard Common Additions (2)
    "reactive": {
        "id": "reactive",
        "name": "Reactive",
        "group": "Common Additions",
        "icon": "⚡",
        "description": "Illuminates pressed keys immediately and smoothly decays back to rest upon release.",
        "defaults": {
            "color_mode": "Single",      # Single | Random
            "color1": (255, 0, 85),
            "rest_color": (0, 0, 0),
            "fade_duration_s": 1.0,      # Short (0.2s), Medium (1.0s), Long (3.0s)
        },
    },
    "rain": {
        "id": "rain",
        "name": "Rain",
        "group": "Common Additions",
        "icon": "🌧️",
        "description": "Spawns droplets along the top row that cascade downward with a fading 3-LED tail.",
        "defaults": {
            "step_ms": 110.0,            # 50 ms to 250 ms per row
            "density": "Medium",         # Low | Medium | High
            "theme": "Classic Rain",     # Classic Rain | Digital Matrix | Single Solid | Random
            "color1": (0, 190, 255),
        },
    },
    # 2.3 Suggested Easy-to-Implement Effects (6)
    "scanner": {
        "id": "scanner",
        "name": "Scanner (Visor)",
        "group": "Grid & Pulse FX",
        "icon": "🚨",
        "description": "Sweeps a bright bar back and forth from edge to edge with a fading comet tail.",
        "defaults": {
            "speed": 1.4,                # sweeps per second
            "tail_length": 3,            # 1 to 5 LEDs
            "color1": (255, 20, 40),
            "rest_color": (0, 0, 0),
            "axis": "Horizontal",        # Horizontal | Vertical
        },
    },
    "color_pulse": {
        "id": "color_pulse",
        "name": "Color Pulse (Heartbeat)",
        "group": "Grid & Pulse FX",
        "icon": "💓",
        "description": "Executes two rapid brightness pulses followed by a pause, mimicking a heartbeat.",
        "defaults": {
            "bpm": 72.0,                 # 40 to 160 BPM
            "color_mode": "Single",      # Single | Alternating Duo | Random
            "base_brightness": 0.08,     # 0.0 to 0.4
            "color1": (255, 0, 60),
            "color2": (170, 0, 255),
        },
    },
    "ripple_line": {
        "id": "ripple_line",
        "name": "Ripple Line",
        "group": "Grid & Pulse FX",
        "icon": "╋",
        "description": "Fires straight horizontal, vertical, or 4-way crosshair shockwaves from pressed keys.",
        "defaults": {
            "axis_mode": "Crosshair",    # Horizontal | Vertical | Crosshair
            "speed_rows_s": 18.0,        # rows/cols per second
            "color1": (0, 230, 255),
            "rest_color": (0, 0, 0),
        },
    },
    "gradient_fill": {
        "id": "gradient_fill",
        "name": "Gradient Fill",
        "group": "Grid & Pulse FX",
        "icon": "🎨",
        "description": "Progressively wipes the device one row/column at a time with cycling palette colors.",
        "defaults": {
            "direction": "Left-to-Right",  # Left-to-Right | Bottom-to-Top | Random Scatter
            "speed": 1.0,                  # fills per second
            "gradient_stops": [
                (0.0, (0, 255, 100)),
                (0.33, (0, 180, 255)),
                (0.66, (170, 0, 255)),
                (1.0, (255, 80, 0)),
            ],
        },
    },
    "checkerboard": {
        "id": "checkerboard",
        "name": "Checkerboard",
        "group": "Grid & Pulse FX",
        "icon": "🏁",
        "description": "Divides the matrix into odd and even coordinates ((X + Y) mod 2) and alternates colors.",
        "defaults": {
            "interval_s": 1.2,               # swap interval in seconds
            "transition": "Smooth Crossfade", # Instant Toggle | Smooth Crossfade
            "color1": (0, 255, 100),
            "color2": (140, 0, 255),
        },
    },
    "heatmap": {
        "id": "heatmap",
        "name": "Heatmap",
        "group": "Grid & Pulse FX",
        "icon": "🌡️",
        "description": "Shifts each key's color along a thermal gradient based on live keypress frequency.",
        "defaults": {
            "sensitivity": 10,           # presses required to reach peak Red
            "cooling_rate": 0.6,         # heat units decayed per second
            "cold_color": (0, 60, 255),
            "hot_color": (255, 20, 20),
        },
    },
}


def get_default_effect_params(effect_id: str) -> Dict[str, Any]:
    """Returns a deep-enough copy of the default parameters for an effect."""
    spec = EFFECT_SPECIFICATIONS.get(effect_id, EFFECT_SPECIFICATIONS["static"])
    defaults = dict(spec["defaults"])
    if "gradient_stops" in defaults:
        defaults["gradient_stops"] = [(float(pos), tuple(col)) for pos, col in defaults["gradient_stops"]]
    return defaults


# ---------------------------------------------------------------------------
# Runtime State & Evaluators for All 16 Effects
# ---------------------------------------------------------------------------
@dataclass
class PressEvent:
    node_id: str
    row: int
    col: int
    x_mm: float
    y_mm: float
    pressed_at: float
    released_at: Optional[float] = None
    color: RGBTuple = (0, 255, 128)


@dataclass
class EffectRuntimeState:
    press_events: List[PressEvent] = field(default_factory=list)
    active_keys: Dict[str, PressEvent] = field(default_factory=dict)
    heatmap_counts: Dict[str, float] = field(default_factory=dict)
    starlight_stars: Dict[str, Tuple[float, float, RGBTuple]] = field(default_factory=dict)  # node_id -> (start_t, dur, color)
    rain_drops: List[Dict[str, Any]] = field(default_factory=list)  # [{col, row_pos, color, last_step_t}]
    last_eval_time: float = 0.0
    rng: random.Random = field(default_factory=lambda: random.Random(2026))


def _random_vibrant_color(rng: random.Random, index_seed: Optional[int] = None) -> RGBTuple:
    if index_seed is not None:
        h = (_hash_noise_1d(index_seed, 9001) * 360.0) % 360.0
    else:
        h = rng.uniform(0.0, 360.0)
    return hsv_to_rgb(h, 1.0, 1.0)


def evaluate_effect(
    effect_id: str,
    nodes: List[LEDNode],
    t: float,
    dt: float,
    params: Dict[str, Any],
    runtime: EffectRuntimeState,
) -> Dict[str, RGBTuple]:
    """
    Evaluates `effect_id` at master clock timestamp `t` (seconds) across `nodes`.
    Returns a dictionary `{node.id: (r, g, b)}`.
    """
    if not nodes:
        return {}

    eff = (effect_id or "static").lower().strip()
    p = get_default_effect_params(eff)
    if params:
        p.update(params)

    # 1. STATIC
    if eff == "static":
        c = clamp_rgb(*p.get("color1", (0, 255, 0)))
        return {n.id: c for n in nodes}

    # 2. BREATHING
    if eff == "breathing":
        fade_dur = max(0.5, float(p.get("speed_s", 4.0)))
        hold_s = 0.2  # 200 ms dark hold at 0% brightness per spec
        cycle_total = fade_dur + hold_s
        cycle_idx = int(math.floor(t / cycle_total))
        phase_t = t - cycle_idx * cycle_total

        if phase_t >= fade_dur:
            lum = 0.0
        else:
            # Ease-in-out sine curve: 0% -> 100% -> 0%
            lum = 0.5 * (1.0 - math.cos(2.0 * math.pi * (phase_t / fade_dur)))

        cmode = p.get("color_mode", "Single")
        if cmode == "Two Alternating":
            base_c = p.get("color1", (0, 255, 0)) if (cycle_idx % 2 == 0) else p.get("color2", (0, 180, 255))
        elif cmode == "Random":
            base_c = _random_vibrant_color(runtime.rng, index_seed=cycle_idx + 1)
        else:
            base_c = p.get("color1", (0, 255, 0))

        scaled = scale_color(clamp_rgb(*base_c), lum)
        return {n.id: scaled for n in nodes}

    # 3. SPECTRUM CYCLING
    if eff == "spectrum_cycling":
        dur = max(0.5, float(p.get("duration_s", 10.0)))
        hue = ((t / dur) * 360.0) % 360.0
        rgb = hsv_to_rgb(hue, 1.0, 1.0)
        return {n.id: rgb for n in nodes}

    # 4. FIRE
    if eff == "fire":
        flicker_hz = max(10.0, min(60.0, float(p.get("flicker_hz", 30.0))))
        theme = p.get("theme", "Classic Flame")
        if theme == "Blue Gas":
            stops = BLUE_GAS_GRADIENT
        elif theme in ("Custom Duo-Tone", "Custom Gradient"):
            if "gradient_stops" in params and len(params["gradient_stops"]) >= 2:
                stops = params["gradient_stops"]
            else:
                stops = [
                    (0.0, clamp_rgb(*p.get("color1", (255, 30, 0)))),
                    (1.0, clamp_rgb(*p.get("color2", (255, 220, 0)))),
                ]
        else:
            stops = CLASSIC_FLAME_GRADIENT

        # Quantize noise time step by flicker_hz so refresh rate controls flicker speed
        quant_t = math.floor(t * flicker_hz) / flicker_hz
        out: Dict[str, RGBTuple] = {}
        for idx, n in enumerate(nodes):
            # Bottom rows (ny near 1.0) have highest base heat; upper rows cool down
            base_heat = 0.25 + 0.75 * float(n.ny)
            noise_val = coherent_noise_2d(
                n.nx * 4.5 + idx * 0.13,
                n.ny * 3.5 + quant_t * (flicker_hz * 0.12),
                seed=77,
            )
            heat = max(0.0, min(1.0, base_heat * 0.65 + noise_val * 0.55 - (1.0 - n.ny) * 0.25))
            col = sample_gradient(stops, heat)
            out[n.id] = scale_color(col, max(0.12, heat))
        return out

    # 5. RIPPLE
    if eff == "ripple":
        speed_mm_s = max(50.0, min(500.0, float(p.get("speed_mm_s", 220.0))))
        spread_mm = max(1.0, min(4.0, float(p.get("spread_units", 2.0)))) * KEY_UNIT_MM
        cmode = p.get("color_mode", "Single")
        c1 = clamp_rgb(*p.get("color1", (0, 255, 128)))
        rest = clamp_rgb(*p.get("rest_color", (0, 0, 0)))

        # Keep recent press events within travel window, or inject an ambient demo pulse if none exist
        active_events = [ev for ev in runtime.press_events if 0.0 <= (t - ev.pressed_at) <= 4.0]
        if not active_events:
            # Periodic ambient center ripple every 2.2s when idle so preview is always alive
            demo_period = 2.2
            demo_t0 = math.floor(t / demo_period) * demo_period
            mid = nodes[len(nodes) // 2]
            active_events = [PressEvent(
                node_id=mid.id, row=mid.row, col=mid.col,
                x_mm=mid.x_mm, y_mm=mid.y_mm, pressed_at=demo_t0,
                color=_random_vibrant_color(runtime.rng, int(demo_t0)) if cmode == "Random" else c1,
            )]

        out = {n.id: rest for n in nodes}
        for ev in active_events:
            age = max(0.0, t - ev.pressed_at)
            radius = age * speed_mm_s
            fade_env = max(0.0, 1.0 - (age / 2.5))
            if fade_env <= 0.0:
                continue
            for n in nodes:
                dist = math.hypot(n.x_mm - ev.x_mm, n.y_mm - ev.y_mm)
                delta = abs(dist - radius)
                if delta <= spread_mm:
                    ring_intensity = (1.0 - (delta / spread_mm)) * fade_env
                    if cmode == "Rainbow":
                        ring_col = sample_rainbow((dist / max(1.0, spread_mm * 3.0)) - age * 0.5)
                    elif cmode == "Random":
                        ring_col = ev.color
                    else:
                        ring_col = c1
                    contrib = scale_color(ring_col, ring_intensity)
                    out[n.id] = add_colors(out[n.id], contrib)
        return out

    # 6. STARLIGHT
    if eff == "starlight":
        density_map = {"Low": 0.05, "Medium": 0.15, "High": 0.35}
        cap_ratio = density_map.get(str(p.get("density", "Medium")), 0.15)
        max_stars = max(1, int(math.ceil(len(nodes) * cap_ratio)))
        dur = max(0.3, min(3.0, float(p.get("duration_s", 1.2))))
        cmode = p.get("color_mode", "Monochrome")
        c1 = clamp_rgb(*p.get("color1", (255, 255, 255)))
        c2 = clamp_rgb(*p.get("color2", (0, 210, 255)))
        rest = clamp_rgb(*p.get("rest_color", (6, 10, 18)))

        # Prune expired stars
        expired = [nid for nid, (st, sdur, _) in runtime.starlight_stars.items() if (t - st) >= sdur or t < st]
        for nid in expired:
            runtime.starlight_stars.pop(nid, None)

        # Spawn new stars asynchronously up to density cap
        available_ids = [n.id for n in nodes if n.id not in runtime.starlight_stars]
        while len(runtime.starlight_stars) < max_stars and available_ids:
            pick = runtime.rng.choice(available_ids)
            available_ids.remove(pick)
            if cmode == "Two-Tone":
                scol = c1 if (len(runtime.starlight_stars) % 2 == 0) else c2
            elif cmode == "Random":
                scol = _random_vibrant_color(runtime.rng)
            else:
                scol = c1
            # Offset start time slightly on initial fill so stars are asynchronous
            offset = runtime.rng.uniform(0.0, dur * 0.8) if not expired else 0.0
            runtime.starlight_stars[pick] = (t - offset, dur, scol)

        out = {n.id: rest for n in nodes}
        for nid, (st, sdur, scol) in runtime.starlight_stars.items():
            if nid in out:
                prog = max(0.0, min(1.0, (t - st) / max(0.05, sdur)))
                # Symmetric fade-in to 0.5 then fade-out to 1.0
                env = 1.0 - abs(2.0 * prog - 1.0)
                out[nid] = lerp_color(rest, scol, env)
        return out

    # 7. WAVE
    if eff == "wave":
        direction = p.get("direction", "Left-to-Right")
        speed = float(p.get("speed", 1.2))
        wavelength = max(0.2, float(p.get("wavelength", 1.0)))
        pmode = p.get("palette_mode", "Rainbow")
        stops = p.get("gradient_stops") or [
            (0.0, (0, 255, 100)),
            (0.5, (0, 160, 255)),
            (1.0, (170, 0, 255)),
        ]

        out = {}
        for n in nodes:
            if direction == "Right-to-Left":
                coord = 1.0 - n.nx
            elif direction == "Top-to-Bottom":
                coord = n.ny
            elif direction == "Bottom-to-Top":
                coord = 1.0 - n.ny
            elif direction in ("Radial Outward", "Outward"):
                coord = math.hypot(n.nx - 0.5, n.ny - 0.5) * 1.414
            elif direction in ("Radial Inward", "Inward"):
                coord = 1.0 - min(1.0, math.hypot(n.nx - 0.5, n.ny - 0.5) * 1.414)
            else:  # Left-to-Right
                coord = n.nx

            phase = (coord / wavelength - t * speed) % 1.0
            if pmode == "Custom Gradient":
                out[n.id] = sample_gradient(stops, phase, wrap=True)
            else:
                out[n.id] = sample_rainbow(phase)
        return out

    # 8. WHEEL
    if eff == "wheel":
        rpm = max(5.0, min(120.0, float(p.get("rpm", 30.0))))
        rps = rpm / 60.0
        direction = p.get("direction", "Clockwise")
        dir_sign = -1.0 if direction == "Clockwise" else 1.0
        pmode = p.get("palette_mode", "Rainbow")
        stops = p.get("gradient_stops") or [
            (0.0, (255, 0, 85)),
            (0.33, (0, 210, 255)),
            (0.66, (0, 255, 100)),
            (1.0, (255, 230, 0)),
        ]

        out = {}
        for n in nodes:
            dx = n.nx - 0.5
            dy = n.ny - 0.5
            theta = math.atan2(dy, dx)  # [-pi, pi]
            norm_angle = (theta / (2.0 * math.pi)) + 0.5  # [0, 1]
            phase = (norm_angle + dir_sign * t * rps) % 1.0
            if pmode in ("Custom Wheel", "Custom Gradient"):
                out[n.id] = sample_gradient(stops, phase, wrap=True)
            else:
                out[n.id] = sample_rainbow(phase)
        return out

    # 9. REACTIVE
    if eff == "reactive":
        fade_dur = max(0.1, float(p.get("fade_duration_s", 1.0)))
        cmode = p.get("color_mode", "Single")
        c1 = clamp_rgb(*p.get("color1", (255, 0, 85)))
        rest = clamp_rgb(*p.get("rest_color", (0, 0, 0)))

        out = {n.id: rest for n in nodes}
        # Currently held keys are at 100% brightness
        for nid, ev in list(runtime.active_keys.items()):
            col = ev.color if cmode == "Random" else c1
            if nid in out:
                out[nid] = col

        # Released keys interpolate back to rest over fade_dur
        for ev in runtime.press_events:
            if ev.node_id in runtime.active_keys:
                continue
            rel_t = ev.released_at if ev.released_at is not None else ev.pressed_at
            elapsed = t - rel_t
            if 0.0 <= elapsed <= fade_dur and ev.node_id in out:
                factor = 1.0 - (elapsed / fade_dur)
                col = ev.color if cmode == "Random" else c1
                out[ev.node_id] = lerp_color(rest, col, factor)
        return out

    # 10. RAIN
    if eff == "rain":
        step_s = max(0.05, min(0.25, float(p.get("step_ms", 110.0)) / 1000.0))
        density = p.get("density", "Medium")
        spawn_prob = {"Low": 0.18, "Medium": 0.38, "High": 0.68}.get(str(density), 0.38)
        theme = p.get("theme", "Classic Rain")
        c1 = clamp_rgb(*p.get("color1", (0, 190, 255)))

        max_row = max((n.row for n in nodes), default=5)
        all_cols = sorted({n.col for n in nodes}) or [0]
        tail_len = 3.0

        # Advance existing drops
        if runtime.last_eval_time == 0.0 or t < runtime.last_eval_time:
            runtime.last_eval_time = t
        steps_elapsed = (t - runtime.last_eval_time) / step_s
        if steps_elapsed >= 0.25:
            for d in runtime.rain_drops:
                d["row_pos"] += steps_elapsed
            runtime.rain_drops = [d for d in runtime.rain_drops if d["row_pos"] - tail_len <= max_row + 1]
            if runtime.rng.random() < spawn_prob:
                col_choice = runtime.rng.choice(all_cols)
                if theme == "Digital Matrix":
                    dcol = (0, 255, 70)
                elif theme == "Classic Rain":
                    dcol = (0, 200, 255) if runtime.rng.random() < 0.6 else (40, 110, 255)
                elif theme == "Random":
                    dcol = _random_vibrant_color(runtime.rng)
                else:
                    dcol = c1
                runtime.rain_drops.append({"col": col_choice, "row_pos": 0.0, "color": dcol})
            runtime.last_eval_time = t

        # Ensure at least one droplet exists immediately on start for deterministic tests & preview
        if not runtime.rain_drops:
            default_col = (0, 255, 70) if theme == "Digital Matrix" else (
                (0, 200, 255) if theme == "Classic Rain" else c1
            )
            runtime.rain_drops.append({"col": all_cols[len(all_cols) // 2], "row_pos": (t / step_s) % (max_row + 3), "color": default_col})

        out = {n.id: (0, 0, 0) for n in nodes}
        for d in runtime.rain_drops:
            head_r = d["row_pos"]
            dcol = d["color"]
            for n in nodes:
                if n.col == d["col"]:
                    dist_behind = head_r - n.row
                    if -0.3 <= dist_behind <= tail_len:
                        intensity = 1.0 if dist_behind <= 0.4 else max(0.0, 1.0 - (dist_behind / tail_len))
                        out[n.id] = add_colors(out[n.id], scale_color(dcol, intensity))
        return out

    # 11. SCANNER (Visor / Cylon Sweep)
    if eff == "scanner":
        speed = max(0.2, float(p.get("speed", 1.4)))
        tail_len = max(1, min(5, int(p.get("tail_length", 3))))
        bar_col = clamp_rgb(*p.get("color1", (255, 20, 40)))
        rest_col = clamp_rgb(*p.get("rest_color", (0, 0, 0)))
        axis = p.get("axis", "Horizontal")

        # Triangle wave bouncing 0.0 -> 1.0 -> 0.0
        raw_phase = (t * speed) % 2.0
        pos = raw_phase if raw_phase <= 1.0 else (2.0 - raw_phase)
        tail_norm = tail_len * 0.07

        out = {}
        for n in nodes:
            coord = n.nx if axis == "Horizontal" else n.ny
            dist = abs(coord - pos)
            if dist <= tail_norm:
                intensity = 1.0 - (dist / tail_norm)
                out[n.id] = lerp_color(rest_col, bar_col, intensity ** 1.3)
            else:
                out[n.id] = rest_col
        return out

    # 12. COLOR PULSE (Heartbeat)
    if eff == "color_pulse":
        bpm = max(40.0, min(160.0, float(p.get("bpm", 72.0))))
        beat_period = 60.0 / bpm
        beat_idx = int(math.floor(t / beat_period))
        phase = (t - beat_idx * beat_period) / beat_period  # [0, 1)

        # Lub-dub double pulse keyframe lookup table:
        # Pulse 1 (Lub) peaks at phase=0.12; Pulse 2 (Dub) peaks at phase=0.34; Pause 0.48..1.0
        if phase < 0.22:
            pulse = math.sin((phase / 0.22) * math.pi)
        elif 0.24 <= phase < 0.46:
            pulse = 0.82 * math.sin(((phase - 0.24) / 0.22) * math.pi)
        else:
            pulse = 0.0

        base_b = max(0.0, min(0.5, float(p.get("base_brightness", 0.08))))
        lum = min(1.0, base_b + (1.0 - base_b) * pulse)

        cmode = p.get("color_mode", "Single")
        if cmode == "Alternating Duo":
            col = p.get("color1", (255, 0, 60)) if (beat_idx % 2 == 0) else p.get("color2", (170, 0, 255))
        elif cmode == "Random":
            col = _random_vibrant_color(runtime.rng, index_seed=beat_idx + 10)
        else:
            col = p.get("color1", (255, 0, 60))

        scaled = scale_color(clamp_rgb(*col), lum)
        return {n.id: scaled for n in nodes}

    # 13. RIPPLE LINE (Linear Shockwave)
    if eff == "ripple_line":
        axis_mode = p.get("axis_mode", "Crosshair")  # Horizontal | Vertical | Crosshair
        speed_rc = max(2.0, float(p.get("speed_rows_s", 18.0)))
        line_col = clamp_rgb(*p.get("color1", (0, 230, 255)))
        rest_col = clamp_rgb(*p.get("rest_color", (0, 0, 0)))

        active_events = [ev for ev in runtime.press_events if 0.0 <= (t - ev.pressed_at) <= 2.5]
        if not active_events:
            demo_period = 2.0
            demo_t0 = math.floor(t / demo_period) * demo_period
            mid = nodes[len(nodes) // 2]
            active_events = [PressEvent(
                node_id=mid.id, row=mid.row, col=mid.col,
                x_mm=mid.x_mm, y_mm=mid.y_mm, pressed_at=demo_t0, color=line_col,
            )]

        out = {n.id: rest_col for n in nodes}
        for ev in active_events:
            age = max(0.0, t - ev.pressed_at)
            travel = age * speed_rc
            fade = max(0.0, 1.0 - age / 1.8)
            for n in nodes:
                hit = 0.0
                if axis_mode in ("Horizontal", "Crosshair") and n.row == ev.row:
                    d_col = abs(abs(n.col - ev.col) - travel)
                    if d_col <= 1.5:
                        hit = max(hit, (1.0 - d_col / 1.5) * fade)
                if axis_mode in ("Vertical", "Crosshair") and n.col == ev.col:
                    d_row = abs(abs(n.row - ev.row) - travel)
                    if d_row <= 1.5:
                        hit = max(hit, (1.0 - d_row / 1.5) * fade)
                if hit > 0.0:
                    out[n.id] = add_colors(out[n.id], scale_color(line_col, hit))
        return out

    # 14. GRADIENT FILL (Color Wash)
    if eff == "gradient_fill":
        direction = p.get("direction", "Left-to-Right")
        speed = max(0.2, float(p.get("speed", 1.0)))
        stops = p.get("gradient_stops") or [
            (0.0, (0, 255, 100)),
            (0.33, (0, 180, 255)),
            (0.66, (170, 0, 255)),
            (1.0, (255, 80, 0)),
        ]
        palette_colors = [clamp_rgb(*col) for _, col in stops] or [(0, 255, 100), (0, 180, 255)]

        if direction == "Bottom-to-Top":
            ordered = sorted(nodes, key=lambda n: (-n.row, n.col))
        elif direction == "Random Scatter":
            ordered = sorted(nodes, key=lambda n: _hash_noise_1d(hash(n.id) & 0xFFFF, 31337))
        else:  # Left-to-Right
            ordered = sorted(nodes, key=lambda n: (n.col, n.row))

        total_cycle = t * speed
        wipe_idx = int(math.floor(total_cycle))
        fill_frac = total_cycle - wipe_idx
        curr_col = palette_colors[wipe_idx % len(palette_colors)]
        prev_col = palette_colors[(wipe_idx - 1) % len(palette_colors)]

        cutoff = fill_frac * len(ordered)
        out = {}
        for i, n in enumerate(ordered):
            if i < int(cutoff):
                out[n.id] = curr_col
            elif i == int(cutoff):
                out[n.id] = lerp_color(prev_col, curr_col, cutoff - int(cutoff))
            else:
                out[n.id] = prev_col
        return out

    # 15. CHECKERBOARD (Alternating Grid)
    if eff == "checkerboard":
        interval_s = max(0.2, float(p.get("interval_s", 1.2)))
        transition = p.get("transition", "Smooth Crossfade")
        c1 = clamp_rgb(*p.get("color1", (0, 255, 100)))
        c2 = clamp_rgb(*p.get("color2", (140, 0, 255)))

        phase = (t / interval_s) % 2.0
        if transition == "Instant Toggle":
            blend = 0.0 if phase < 1.0 else 1.0
        else:
            blend = 0.5 * (1.0 - math.cos(math.pi * phase))

        col_even = lerp_color(c1, c2, blend)
        col_odd = lerp_color(c2, c1, blend)

        return {
            n.id: (col_even if ((n.row + n.col) % 2 == 0) else col_odd)
            for n in nodes
        }

    # 16. HEATMAP (Live Keypress Counter)
    if eff == "heatmap":
        sensitivity = max(1.0, float(p.get("sensitivity", 10)))
        cooling_rate = max(0.05, float(p.get("cooling_rate", 0.6)))
        cold_col = clamp_rgb(*p.get("cold_color", (0, 60, 255)))
        hot_col = clamp_rgb(*p.get("hot_color", (255, 20, 20)))

        stops: List[GradientStop] = [
            (0.0, cold_col),
            (0.35, (0, 230, 100)),
            (0.70, (255, 220, 0)),
            (1.0, hot_col),
        ]

        # Apply cooling decay over dt
        if dt > 0.0:
            for nid in list(runtime.heatmap_counts.keys()):
                new_val = runtime.heatmap_counts[nid] - cooling_rate * dt
                if new_val <= 0.0:
                    runtime.heatmap_counts.pop(nid, None)
                else:
                    runtime.heatmap_counts[nid] = new_val

        out = {}
        for n in nodes:
            heat_count = runtime.heatmap_counts.get(n.id, 0.0)
            ratio = max(0.0, min(1.0, heat_count / sensitivity))
            out[n.id] = sample_gradient(stops, ratio)
        return out

    # Fallback
    return {n.id: (0, 255, 0) for n in nodes}


# ---------------------------------------------------------------------------
# Multi-Layer Zone Compositor & Global Master Clock (Sections 3.2 & 3.3)
# ---------------------------------------------------------------------------
@dataclass
class LightingLayer:
    id: str
    name: str
    effect_id: str
    params: Dict[str, Any] = field(default_factory=dict)
    target_leds: Optional[Set[str]] = None  # None means whole device
    enabled: bool = True
    runtime: EffectRuntimeState = field(default_factory=EffectRuntimeState)

    def to_dict(self) -> Dict[str, Any]:
        serializable_params = {}
        for k, v in self.params.items():
            if isinstance(v, tuple):
                serializable_params[k] = list(v)
            elif k == "gradient_stops" and isinstance(v, list):
                serializable_params[k] = [[float(pos), list(col)] for pos, col in v]
            else:
                serializable_params[k] = v
        return {
            "id": self.id,
            "name": self.name,
            "effect_id": self.effect_id,
            "params": serializable_params,
            "target_leds": sorted(self.target_leds) if self.target_leds is not None else None,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LightingLayer":
        eff_id = str(data.get("effect_id", "spectrum_cycling"))
        params = get_default_effect_params(eff_id)
        raw_params = data.get("params", {})
        if isinstance(raw_params, dict):
            for k, v in raw_params.items():
                if k in ("color1", "color2", "rest_color", "cold_color", "hot_color") and isinstance(v, (list, tuple)) and len(v) == 3:
                    params[k] = clamp_rgb(v[0], v[1], v[2])
                elif k == "gradient_stops" and isinstance(v, list):
                    stops = []
                    for item in v:
                        if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[1], (list, tuple)) and len(item[1]) == 3:
                            stops.append((float(item[0]), clamp_rgb(*item[1])))
                    if len(stops) >= 2:
                        params[k] = stops
                else:
                    params[k] = v
        t_leds = data.get("target_leds")
        target_set = set(t_leds) if isinstance(t_leds, list) else None
        return cls(
            id=str(data.get("id", "layer-1")),
            name=str(data.get("name", "Base Layer")),
            effect_id=eff_id,
            params=params,
            target_leds=target_set,
            enabled=bool(data.get("enabled", True)),
        )


class LightingStudioController:
    """
    Manages the 60 FPS master animation clock, global controls (Master Brightness,
    Global Speed, Sync All Devices), device topologies, and per-zone effect layers.
    """
    def __init__(self):
        self.master_brightness: float = 1.0  # 0.0 (0%) to 1.0 (100%)
        self.global_speed: float = 1.0       # 0.5x to 3.0x
        self.sync_all_devices: bool = True
        self.whole_device_mode: Dict[str, bool] = {cat: True for cat in DEVICE_CATEGORIES}

        self.master_clock: float = 0.0
        self._last_wall_time: float = time.monotonic()

        self.topologies: Dict[str, List[LEDNode]] = {
            cat: build_device_topology(cat) for cat in DEVICE_CATEGORIES
        }
        self.device_layers: Dict[str, List[LightingLayer]] = {
            cat: [
                LightingLayer(
                    id="base",
                    name="Whole Device",
                    effect_id="wave",
                    params=get_default_effect_params("wave"),
                    target_leds=None,
                )
            ]
            for cat in DEVICE_CATEGORIES
        }
        self.user_swatches: List[RGBTuple] = list(DEFAULT_USER_SWATCHES)

    def step_clock(self, dt_wall: Optional[float] = None) -> Tuple[float, float]:
        """Advances the master clock by `dt_wall * global_speed` and returns `(master_clock, scaled_dt)`."""
        now = time.monotonic()
        if dt_wall is None:
            dt_wall = max(0.0, min(0.25, now - self._last_wall_time))
        self._last_wall_time = now
        scaled_dt = dt_wall * max(0.5, min(3.0, self.global_speed))
        self.master_clock += scaled_dt
        return self.master_clock, scaled_dt

    def get_active_layers(self, category: str) -> List[LightingLayer]:
        """Returns the layers to evaluate for `category` (respecting Sync All Devices)."""
        cat = category if category in self.device_layers else "keyboard"
        return self.device_layers[cat]

    def set_Effect_on_selection(
        self,
        category: str,
        effect_id: str,
        params: Optional[Dict[str, Any]] = None,
        selected_leds: Optional[Set[str]] = None,
        layer_name: Optional[str] = None,
    ) -> LightingLayer:
        """
        Assigns `effect_id` either to the whole device (if `whole_device_mode` or `selected_leds` is None)
        or as a targeted zone overlay layer on `selected_leds`.
        When `sync_all_devices` is True and applying to Whole Device, synchronizes across all categories.
        """
        cat = category if category in self.device_layers else "keyboard"
        eff_params = get_default_effect_params(effect_id)
        if params:
            eff_params.update(params)

        if self.whole_device_mode.get(cat, True) or not selected_leds:
            target_cats = DEVICE_CATEGORIES if self.sync_all_devices else (cat,)
            created_layer = None
            for tcat in target_cats:
                self.whole_device_mode[tcat] = True
                base_layer = LightingLayer(
                    id="base",
                    name="Whole Device",
                    effect_id=effect_id,
                    params=dict(eff_params),
                    target_leds=None,
                    runtime=EffectRuntimeState(),
                )
                self.device_layers[tcat] = [base_layer]
                if tcat == cat:
                    created_layer = base_layer
            return created_layer or self.device_layers[cat][0]

        # Zone / Custom Selection layer assignment
        layers = self.device_layers[cat]
        target_set = set(selected_leds)
        # Update existing layer if identical target set exists
        for layer in layers:
            if layer.target_leds == target_set:
                layer.effect_id = effect_id
                layer.params = dict(eff_params)
                layer.runtime = EffectRuntimeState()
                if layer_name:
                    layer.name = layer_name
                return layer

        new_layer = LightingLayer(
            id=f"zone-{len(layers) + 1}",
            name=layer_name or f"{EFFECT_SPECIFICATIONS.get(effect_id, {}).get('name', effect_id)} ({len(target_set)} LEDs)",
            effect_id=effect_id,
            params=dict(eff_params),
            target_leds=target_set,
            runtime=EffectRuntimeState(),
        )
        layers.append(new_layer)
        return new_layer

    def clear_zone_layers(self, category: Optional[str] = None) -> None:
        """Removes all zone overlay layers and restores clean Whole Device mode."""
        target_cats = DEVICE_CATEGORIES if (category is None or self.sync_all_devices) else (category,)
        for cat in target_cats:
            if cat not in self.device_layers:
                continue
            self.whole_device_mode[cat] = True
            base = self.device_layers[cat][0] if self.device_layers[cat] else LightingLayer(
                id="base",
                name="Whole Device",
                effect_id="wave",
                params=get_default_effect_params("wave"),
            )
            base.target_leds = None
            base.name = "Whole Device"
            base.runtime = EffectRuntimeState()
            self.device_layers[cat] = [base]

    def trigger_press(self, category: str, node_id: str, t: Optional[float] = None) -> None:
        """Records a key/button actuation event for reactive effects (Ripple, Reactive, Ripple Line, Heatmap)."""
        ts = self.master_clock if t is None else float(t)
        target_cats = DEVICE_CATEGORIES if self.sync_all_devices else (category,)
        for cat in target_cats:
            nodes = self.topologies.get(cat, [])
            node = next((n for n in nodes if n.id == node_id), None)
            if node is None and nodes:
                node = nodes[len(nodes) // 2]
            if node is None:
                continue
            for layer in self.device_layers.get(cat, []):
                rt = layer.runtime
                ev = PressEvent(
                    node_id=node.id,
                    row=node.row,
                    col=node.col,
                    x_mm=node.x_mm,
                    y_mm=node.y_mm,
                    pressed_at=ts,
                    color=_random_vibrant_color(rt.rng),
                )
                rt.press_events.append(ev)
                if len(rt.press_events) > 32:
                    rt.press_events = rt.press_events[-32:]
                rt.active_keys[node.id] = ev
                rt.heatmap_counts[node.id] = rt.heatmap_counts.get(node.id, 0.0) + 1.0

    def trigger_release(self, category: str, node_id: str, t: Optional[float] = None) -> None:
        """Marks a pressed key/button as released so Reactive begins its decay window."""
        ts = self.master_clock if t is None else float(t)
        target_cats = DEVICE_CATEGORIES if self.sync_all_devices else (category,)
        for cat in target_cats:
            for layer in self.device_layers.get(cat, []):
                ev = layer.runtime.active_keys.pop(node_id, None)
                if ev is not None:
                    ev.released_at = ts

    def reset_heatmap(self, category: Optional[str] = None) -> None:
        """Clears live keypress counters for Heatmap effect."""
        cats = DEVICE_CATEGORIES if category is None else (category,)
        for cat in cats:
            for layer in self.device_layers.get(cat, []):
                layer.runtime.heatmap_counts.clear()

    def render_device_frame(
        self,
        category: str,
        t: Optional[float] = None,
        dt: float = 1.0 / TARGET_FPS,
    ) -> Dict[str, RGBTuple]:
        """
        Composites all enabled layers for `category` at timestamp `t` (using shared `master_clock`
        when `t` is None) and scales final RGB values by `master_brightness`.
        """
        cat = category if category in self.topologies else "keyboard"
        nodes = self.topologies[cat]
        clock_t = self.master_clock if t is None else float(t)
        scaled_dt = dt * max(0.5, min(3.0, self.global_speed))

        frame: Dict[str, RGBTuple] = {n.id: (0, 0, 0) for n in nodes}
        layers = self.device_layers.get(cat, [])

        for layer in layers:
            if not layer.enabled:
                continue
            target_nodes = (
                nodes
                if layer.target_leds is None
                else [n for n in nodes if n.id in layer.target_leds]
            )
            if not target_nodes:
                continue
            layer_out = evaluate_effect(
                layer.effect_id,
                target_nodes,
                clock_t,
                scaled_dt,
                layer.params,
                layer.runtime,
            )
            for nid, col in layer_out.items():
                frame[nid] = col

        # Apply Master Brightness PWM scalar (Section 3.2)
        if self.master_brightness < 0.999:
            b = max(0.0, min(1.0, self.master_brightness))
            frame = {nid: scale_color(col, b) for nid, col in frame.items()}

        return frame


# ---------------------------------------------------------------------------
# Persistence for Lighting Studio Settings & User Swatches
# ---------------------------------------------------------------------------
def get_lighting_settings_path() -> Path:
    from strop_core.presets import get_strop_config_dir
    return get_strop_config_dir() / "lighting_settings.json"


def save_lighting_settings(controller: LightingStudioController, path: Optional[Path] = None) -> bool:
    """Persists lighting studio settings and user swatches atomically to JSON."""
    target = path or get_lighting_settings_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "master_brightness": round(float(controller.master_brightness), 4),
            "global_speed": round(float(controller.global_speed), 4),
            "sync_all_devices": bool(controller.sync_all_devices),
            "whole_device_mode": dict(controller.whole_device_mode),
            "user_swatches": [list(clamp_rgb(*c)) for c in controller.user_swatches[:8]],
            "device_layers": {
                cat: [layer.to_dict() for layer in layers]
                for cat, layers in controller.device_layers.items()
            },
        }
        tmp_path = target.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, target)
        return True
    except Exception:
        return False


def load_lighting_settings(controller: LightingStudioController, path: Optional[Path] = None) -> bool:
    """Loads persisted lighting studio settings and user swatches into `controller`."""
    target = path or get_lighting_settings_path()
    if not target.exists():
        return False
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False
        if "master_brightness" in data:
            controller.master_brightness = max(0.0, min(1.0, float(data["master_brightness"])))
        if "global_speed" in data:
            controller.global_speed = max(0.5, min(3.0, float(data["global_speed"])))
        if "sync_all_devices" in data:
            controller.sync_all_devices = bool(data["sync_all_devices"])
        if isinstance(data.get("whole_device_mode"), dict):
            for cat in DEVICE_CATEGORIES:
                if cat in data["whole_device_mode"]:
                    controller.whole_device_mode[cat] = bool(data["whole_device_mode"][cat])
        if isinstance(data.get("user_swatches"), list):
            swatches: List[RGBTuple] = []
            for item in data["user_swatches"][:8]:
                if isinstance(item, (list, tuple)) and len(item) == 3:
                    swatches.append(clamp_rgb(item[0], item[1], item[2]))
            while len(swatches) < 8:
                swatches.append(DEFAULT_USER_SWATCHES[len(swatches)])
            controller.user_swatches = swatches
        if isinstance(data.get("device_layers"), dict):
            for cat, raw_layers in data["device_layers"].items():
                if cat in DEVICE_CATEGORIES and isinstance(raw_layers, list) and raw_layers:
                    loaded = [LightingLayer.from_dict(item) for item in raw_layers if isinstance(item, dict)]
                    if loaded:
                        controller.device_layers[cat] = loaded
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# OpenRazer Hardware Bridge (Backward-compatible + Matrix Frame Streaming)
# ---------------------------------------------------------------------------
class RazerLightingEngine:
    """
    Communicates with the OpenRazer DBus daemon to set static colors, hardware brightness,
    or stream 60 FPS per-key RGB frames to `dev.fx.advanced.matrix`.
    Falls back gracefully if OpenRazer is not running or device does not support matrix fx.
    """
    def __init__(self):
        self._manager = None
        self._connected = False
        self._last_static_colors: Dict[str, RGBTuple] = {}
        self._worker_lock = threading.Lock()
        self._worker_event = threading.Event()
        self._pending_job: Optional[Dict[str, Any]] = None
        self._worker_thread: Optional[threading.Thread] = None
        self._init_openrazer()

    def _init_openrazer(self):
        try:
            import openrazer.client
            self._manager = openrazer.client.DeviceManager()
            self._connected = True
        except Exception:
            self._manager = None
            self._connected = False

    @property
    def is_available(self) -> bool:
        return self._connected and self._manager is not None

    def get_razer_device(self, device_name: str):
        """Finds the openrazer device matching the target name."""
        if not self.is_available:
            self._init_openrazer()
        if not self._manager:
            return None

        clean_target = device_name.lower().replace("razer", "").replace("_", " ").strip()
        for dev in self._manager.devices:
            dev_clean = dev.name.lower().replace("razer", "").replace("_", " ").strip()
            if clean_target in dev_clean or dev_clean in clean_target:
                return dev
        return None

    def apply_device_lighting(
        self,
        device_name: str,
        color: Tuple[int, int, int] = COLOR_STOCK_GREEN,
    ) -> bool:
        """
        Sets all LEDs on target Razer device to solid color.
        Supports static effect directly or fills advanced LED matrix.
        """
        dev = self.get_razer_device(device_name)
        if not dev or not hasattr(dev, "fx"):
            return False

        try:
            # 1. Try built-in static effect first
            if hasattr(dev.fx, "static"):
                dev.fx.static(*color)
                return True
            elif hasattr(dev.fx, "misc") and hasattr(dev.fx.misc, "set_static_effect"):
                dev.fx.misc.set_static_effect(*color)
                return True
        except Exception:
            pass

        # 2. Fall back to drawing full matrix
        if hasattr(dev.fx, "advanced"):
            try:
                adv = dev.fx.advanced
                rows = adv.rows
                cols = adv.cols
                matrix = adv.matrix
                for r in range(rows):
                    for c in range(cols):
                        matrix[r, c] = color
                adv.draw()
                return True
            except Exception as e:
                print(f"Failed to draw matrix lighting on {device_name}: {e}")

        return False

    def apply_all_connected_devices_lighting(
        self,
        color: Tuple[int, int, int] = COLOR_STOCK_GREEN,
    ) -> bool:
        """
        Applies solid color to every connected Razer device found by OpenRazer.
        """
        if not self.is_available:
            self._init_openrazer()
        if not self._manager or not self._manager.devices:
            return False

        success = True
        for dev in self._manager.devices:
            try:
                if hasattr(dev, "fx") and hasattr(dev.fx, "static"):
                    dev.fx.static(*color)
                elif hasattr(dev, "fx") and hasattr(dev.fx, "misc") and hasattr(dev.fx.misc, "set_static_effect"):
                    dev.fx.misc.set_static_effect(*color)
                elif hasattr(dev, "fx") and hasattr(dev.fx, "advanced"):
                    adv = dev.fx.advanced
                    for r in range(adv.rows):
                        for c in range(adv.cols):
                            adv.matrix[r, c] = color
                    adv.draw()
                else:
                    success = False
            except Exception as e:
                print(f"Failed to set lighting for {dev.name}: {e}")
                success = False
        return success

    @staticmethod
    def _infer_device_category(dev_name: str) -> str:
        low = (dev_name or "").lower()
        if any(k in low for k in ("tartarus", "orbweaver", "nostromo", "keypad")):
            return "keypad"
        if any(k in low for k in ("naga", "deathadder", "basilisk", "viper", "mamba", "orochi", "cobra", "abyssus", "lancehead", "mouse")):
            return "mouse"
        if any(k in low for k in ("wolverine", "raiju", "kishi", "controller")):
            return "controller"
        return "keyboard"

    @staticmethod
    def _write_node_to_matrix(adv, n: LEDNode, col: RGBTuple) -> None:
        rows, cols = adv.rows, adv.cols
        # 1. 1D Linear Keypad Matrix (e.g. Razer Tartarus Pro / V2: 1 x 21)
        if rows == 1 and cols >= 20:
            if n.id.startswith("grid-"):
                parts = n.id.split("-")
                if len(parts) == 3:
                    idx = int(parts[1]) * 5 + int(parts[2])
                    if 0 <= idx < cols:
                        adv.matrix[0, idx] = col
            elif n.id in ("scrollUp", "scrollDown") and cols > 19:
                adv.matrix[0, 19] = col
            elif n.id == "spacebar" and cols > 20:
                adv.matrix[0, 20] = col
            elif 0 <= n.col < cols:
                adv.matrix[0, n.col] = col
            return

        # 2. Standard 2D Keyboard / Keypad Matrix (e.g. BlackWidow V3: 6 x 22)
        if n.zone == "underglow" and n.row >= rows:
            return
        if n.zone == "underglow" and rows <= 6:
            # Skip virtual chassis underglow bars on 6-row key-only matrices so they never overwrite key switches
            return

        mapped_cells = OPENRAZER_KEYBOARD_6X22_MAP.get(n.id)
        if mapped_cells and rows >= 6 and cols >= 15:
            for mr, mc in mapped_cells:
                if 0 <= mr < rows and 0 <= mc < cols:
                    adv.matrix[mr, mc] = col
            return

        r = max(0, min(rows - 1, n.row))
        c_start = max(0, min(cols - 1, n.col))
        span = max(1, int(round(n.rw / 36.0)))
        for c in range(c_start, min(cols, c_start + span)):
            adv.matrix[r, c] = col

    def reset_hardware_lighting(
        self,
        device_name: Optional[str] = None,
        all_devices: bool = False,
    ) -> bool:
        """
        Clears any active lighting effect and zeroes the hardware matrix on target device(s)
        so previous profiles never combine with newly applied profiles.
        """
        if not self.is_available:
            self._init_openrazer()
        if not self._manager or not self._manager.devices:
            return False

        targets = (
            list(self._manager.devices)
            if (all_devices or not device_name)
            else [self.get_razer_device(device_name)]
        )
        targets = [d for d in targets if d is not None]
        if not targets:
            return False

        self._last_static_colors.clear()
        any_ok = False
        for dev in targets:
            try:
                if hasattr(dev, "fx") and hasattr(dev.fx, "none"):
                    try:
                        if not hasattr(dev.fx, "has") or dev.fx.has("none"):
                            dev.fx.none()
                            any_ok = True
                    except Exception:
                        pass
                adv = getattr(dev.fx, "advanced", None) if hasattr(dev, "fx") else None
                if adv is not None and getattr(adv, "rows", None) and getattr(adv, "cols", None):
                    if hasattr(adv.matrix, "reset"):
                        adv.matrix.reset()
                    else:
                        for r in range(adv.rows):
                            for c in range(adv.cols):
                                adv.matrix[r, c] = (0, 0, 0)
                    adv.draw()
                    any_ok = True
                elif hasattr(dev, "fx") and hasattr(dev.fx, "static"):
                    dev.fx.static(0, 0, 0)
                    any_ok = True
            except Exception:
                pass
        return any_ok

    def queue_frame_push(
        self,
        nodes: List[LEDNode],
        frame: Dict[str, RGBTuple],
        device_name: Optional[str] = None,
        all_devices: bool = False,
        controller: Optional[LightingStudioController] = None,
        reset_first: bool = False,
    ) -> None:
        """
        Enqueues the latest lighting frame (and optional hardware reset) onto a single
        serialized background worker thread so DBus calls never block the 60 FPS GTK UI
        and old profile frames are immediately dropped when switching profiles.
        """
        device_frames: Dict[str, Tuple[List[LEDNode], Dict[str, RGBTuple]]] = {}
        if controller is not None and all_devices:
            for cat in DEVICE_CATEGORIES:
                device_frames[cat] = (
                    controller.topologies[cat],
                    controller.render_device_frame(cat),
                )

        with self._worker_lock:
            # Preserve reset_first=True if an earlier unconsumed job requested a reset
            prev_reset = bool(self._pending_job and self._pending_job.get("reset_first"))
            self._pending_job = {
                "nodes": nodes,
                "frame": dict(frame),
                "device_name": device_name,
                "all_devices": all_devices,
                "device_frames": device_frames,
                "reset_first": reset_first or prev_reset,
            }
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._worker_thread = threading.Thread(
                    target=self._hardware_worker_loop,
                    name="strop-lighting-hw",
                    daemon=True,
                )
                self._worker_thread.start()
            self._worker_event.set()

    def _hardware_worker_loop(self) -> None:
        while True:
            self._worker_event.wait(timeout=1.0)
            with self._worker_lock:
                job = self._pending_job
                self._pending_job = None
                self._worker_event.clear()
            if job is None:
                continue
            try:
                if job.get("reset_first"):
                    self.reset_hardware_lighting(
                        device_name=job.get("device_name"),
                        all_devices=bool(job.get("all_devices")),
                    )
                self._push_frame_precomputed(job)
            except Exception:
                pass

    def _push_frame_precomputed(self, job: Dict[str, Any]) -> bool:
        if not self.is_available:
            self._init_openrazer()
        if not self._manager or not self._manager.devices:
            return False

        all_devices = bool(job.get("all_devices"))
        device_name = job.get("device_name")
        nodes = job["nodes"]
        frame = job["frame"]
        device_frames: Dict[str, Tuple[List[LEDNode], Dict[str, RGBTuple]]] = job.get("device_frames") or {}

        targets = (
            list(self._manager.devices)
            if (all_devices or not device_name)
            else [self.get_razer_device(device_name)]
        )
        targets = [d for d in targets if d is not None]
        if not targets:
            return False

        any_ok = False
        for dev in targets:
            try:
                dname = getattr(dev, "name", "")
                dev_cat = self._infer_device_category(dname)
                if all_devices and dev_cat in device_frames:
                    dev_nodes, dev_frame = device_frames[dev_cat]
                else:
                    dev_nodes, dev_frame = nodes, frame

                sample_color = (
                    dev_frame.get("palm_logo")
                    or dev_frame.get("scroll_wheel_top")
                    or next((col for col in dev_frame.values() if col != (0, 0, 0)), None)
                    or next(iter(dev_frame.values()), COLOR_STOCK_GREEN)
                )

                adv = getattr(dev.fx, "advanced", None) if hasattr(dev, "fx") else None
                if adv is not None and getattr(adv, "rows", None) and getattr(adv, "cols", None):
                    if hasattr(adv.matrix, "reset"):
                        adv.matrix.reset()
                    else:
                        for r in range(adv.rows):
                            for c in range(adv.cols):
                                adv.matrix[r, c] = (0, 0, 0)
                    for n in dev_nodes:
                        col = dev_frame.get(n.id, (0, 0, 0))
                        self._write_node_to_matrix(adv, n, col)
                    adv.draw()
                    any_ok = True
                elif hasattr(dev, "fx") and hasattr(dev.fx, "static"):
                    if self._last_static_colors.get(dname) != sample_color:
                        dev.fx.static(*sample_color)
                        self._last_static_colors[dname] = sample_color
                    any_ok = True
                elif hasattr(dev, "fx") and hasattr(dev.fx, "misc") and hasattr(dev.fx.misc, "set_static_effect"):
                    dev.fx.misc.set_static_effect(*sample_color)
                    any_ok = True
            except Exception:
                pass
        return any_ok

    def push_frame(
        self,
        nodes: List[LEDNode],
        frame: Dict[str, RGBTuple],
        device_name: Optional[str] = None,
        all_devices: bool = False,
        controller: Optional[LightingStudioController] = None,
    ) -> bool:
        """
        Streams a rendered RGB frame to OpenRazer hardware (clearing the matrix buffer
        before drawing each frame so previous profiles never combine).
        """
        if not self.is_available:
            self._init_openrazer()
        if not self._manager or not self._manager.devices:
            return False

        targets = (
            list(self._manager.devices)
            if (all_devices or not device_name)
            else [self.get_razer_device(device_name)]
        )
        targets = [d for d in targets if d is not None]
        if not targets:
            return False

        any_ok = False
        for dev in targets:
            try:
                dev_cat = self._infer_device_category(getattr(dev, "name", ""))
                if controller is not None and all_devices:
                    dev_nodes = controller.topologies.get(dev_cat, nodes)
                    dev_frame = controller.render_device_frame(dev_cat)
                else:
                    dev_nodes = nodes
                    dev_frame = frame

                # Pick representative active color for non-matrix static/zone devices (e.g. Naga Trinity)
                sample_color = (
                    dev_frame.get("palm_logo")
                    or dev_frame.get("scroll_wheel_top")
                    or next((col for col in dev_frame.values() if col != (0, 0, 0)), None)
                    or next(iter(dev_frame.values()), COLOR_STOCK_GREEN)
                )

                adv = getattr(dev.fx, "advanced", None) if hasattr(dev, "fx") else None
                if adv is not None and getattr(adv, "rows", None) and getattr(adv, "cols", None):
                    if hasattr(adv.matrix, "reset"):
                        adv.matrix.reset()
                    else:
                        for r in range(adv.rows):
                            for c in range(adv.cols):
                                adv.matrix[r, c] = (0, 0, 0)
                    for n in dev_nodes:
                        col = dev_frame.get(n.id, (0, 0, 0))
                        self._write_node_to_matrix(adv, n, col)
                    adv.draw()
                    any_ok = True
                elif hasattr(dev, "fx") and hasattr(dev.fx, "static"):
                    dev.fx.static(*sample_color)
                    any_ok = True
                elif hasattr(dev, "fx") and hasattr(dev.fx, "misc") and hasattr(dev.fx.misc, "set_static_effect"):
                    dev.fx.misc.set_static_effect(*sample_color)
                    any_ok = True
            except Exception:
                pass
        return any_ok


# Singleton engine instance
_engine: Optional[RazerLightingEngine] = None


def get_lighting_engine() -> RazerLightingEngine:
    global _engine
    if _engine is None:
        _engine = RazerLightingEngine()
    return _engine
