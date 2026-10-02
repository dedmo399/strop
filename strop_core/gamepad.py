"""
Linux Gamepad & Analog Joystick Emulation for the Strop Suite.
Provides standard Xbox 360 / Linux Gamepad event codes, axis mapping generators,
and input-remapper-2 gamepad target serializers.
"""

from typing import Dict, List, Any, Optional
import re

EV_KEY = 1

GAMEPAD_BUTTON_CODES = {
    "BTN_SOUTH": 304, "BTN_EAST": 305, "BTN_NORTH": 307, "BTN_WEST": 308,
    "BTN_TL": 310, "BTN_TR": 311, "BTN_SELECT": 314, "BTN_START": 315,
    "BTN_MODE": 316, "BTN_THUMBL": 317, "BTN_THUMBR": 318,
    "BTN_DPAD_UP": 544, "BTN_DPAD_DOWN": 545,
    "BTN_DPAD_LEFT": 546, "BTN_DPAD_RIGHT": 547,
}

# Standard Linux Gamepad Event Codes (evdev/uinput)
# Axes
ABS_X = "ABS_X"          # Left Stick X (Left: -32767, Right: +32767)
ABS_Y = "ABS_Y"          # Left Stick Y (Up: -32767, Down: +32767)
ABS_Z = "ABS_Z"          # Left Trigger (LT: 0 to 255)
ABS_RX = "ABS_RX"        # Right Stick X (Left: -32767, Right: +32767)
ABS_RY = "ABS_RY"        # Right Stick Y (Up: -32767, Down: +32767)
ABS_RZ = "ABS_RZ"        # Right Trigger (RT: 0 to 255)
ABS_HAT0X = "ABS_HAT0X"  # D-Pad X (-1, 0, 1)
ABS_HAT0Y = "ABS_HAT0Y"  # D-Pad Y (-1, 0, 1)

# Buttons
BTN_SOUTH = "BTN_SOUTH"  # A / Cross
BTN_EAST = "BTN_EAST"    # B / Circle
BTN_NORTH = "BTN_NORTH"  # X / Square
BTN_WEST = "BTN_WEST"    # Y / Triangle
BTN_TL = "BTN_TL"        # Left Bumper (LB)
BTN_TR = "BTN_TR"        # Right Bumper (RB)
BTN_SELECT = "BTN_SELECT"# Select / Back / View
BTN_START = "BTN_START"  # Start / Menu
BTN_MODE = "BTN_MODE"    # Guide / Xbox Button
BTN_THUMBL = "BTN_THUMBL"# Left Stick Click (L3)
BTN_THUMBR = "BTN_THUMBR"# Right Stick Click (R3)
BTN_DPAD_UP = "BTN_DPAD_UP"
BTN_DPAD_DOWN = "BTN_DPAD_DOWN"
BTN_DPAD_LEFT = "BTN_DPAD_LEFT"
BTN_DPAD_RIGHT = "BTN_DPAD_RIGHT"

# Common Gamepad Button Definitions for UI
GAMEPAD_BUTTON_PRESETS = [
    {"label": "A (South)", "symbol": "BTN_SOUTH", "code": 304, "desc": "A / Cross Button"},
    {"label": "B (East)", "symbol": "BTN_EAST", "code": 305, "desc": "B / Circle Button"},
    {"label": "X (North)", "symbol": "BTN_NORTH", "code": 307, "desc": "X / Square Button"},
    {"label": "Y (West)", "symbol": "BTN_WEST", "code": 308, "desc": "Y / Triangle Button"},
    {"label": "LB (Bumper)", "symbol": "BTN_TL", "code": 310, "desc": "Left Bumper (LB)"},
    {"label": "RB (Bumper)", "symbol": "BTN_TR", "code": 311, "desc": "Right Bumper (RB)"},
    {"label": "LT (Trigger)", "symbol": "ABS_Z", "code": 2, "desc": "Left Analog Trigger (LT)"},
    {"label": "RT (Trigger)", "symbol": "ABS_RZ", "code": 5, "desc": "Right Analog Trigger (RT)"},
    {"label": "L3 (Left Click)", "symbol": "BTN_THUMBL", "code": 317, "desc": "Left Stick Click (L3)"},
    {"label": "R3 (Right Click)", "symbol": "BTN_THUMBR", "code": 318, "desc": "Right Stick Click (R3)"},
    {"label": "Start / Menu", "symbol": "BTN_START", "code": 315, "desc": "Start / Menu Button"},
    {"label": "Select / Back", "symbol": "BTN_SELECT", "code": 314, "desc": "Select / View / Back Button"},
]


def format_gamepad_output_symbol(action: str, value: Optional[int] = None) -> str:
    """Formats an input-remapper gamepad action symbol."""
    if value is not None:
        return f"gamepad({action}, {value})"
    return f"gamepad({action})"


def parse_gamepad_button_output(symbol: str) -> Optional[tuple[int, int]]:
    """Translate Strop's button shorthand to input-remapper event fields."""
    match = re.fullmatch(
        r"\s*(?:gamepad\(\s*(BTN_[A-Z0-9_]+)\s*\)|(BTN_[A-Z0-9_]+))\s*",
        symbol or "",
    )
    if not match:
        return None
    code = GAMEPAD_BUTTON_CODES.get(match.group(1) or match.group(2))
    return (EV_KEY, code) if code is not None else None


def format_gamepad_button_output(output_type: Optional[int], output_code: Optional[int]) -> Optional[str]:
    """Translate an input-remapper gamepad key event into Strop's display form."""
    if output_type != EV_KEY or output_code is None:
        return None
    for name, code in GAMEPAD_BUTTON_CODES.items():
        if code == output_code:
            return format_gamepad_output_symbol(name)
    return None


def get_left_stick_mappings() -> Dict[str, str]:
    """
    Returns 8-way directional mapping for Left Analog Stick (LS Movement).
    Diagonal values are mathematically normalized to ~0.7071 * 32767 = 23170.
    """
    return {
        "n":  "gamepad(ABS_Y, -32767)",
        "ne": "gamepad(ABS_X, 23170) + gamepad(ABS_Y, -23170)",
        "e":  "gamepad(ABS_X, 32767)",
        "se": "gamepad(ABS_X, 23170) + gamepad(ABS_Y, 23170)",
        "s":  "gamepad(ABS_Y, 32767)",
        "sw": "gamepad(ABS_X, -23170) + gamepad(ABS_Y, 23170)",
        "w":  "gamepad(ABS_X, -32767)",
        "nw": "gamepad(ABS_X, -23170) + gamepad(ABS_Y, -23170)",
    }


def get_right_stick_mappings() -> Dict[str, str]:
    """
    Returns 8-way directional mapping for Right Analog Stick (RS Camera / Aim).
    """
    return {
        "n":  "gamepad(ABS_RY, -32767)",
        "ne": "gamepad(ABS_RX, 23170) + gamepad(ABS_RY, -23170)",
        "e":  "gamepad(ABS_RX, 32767)",
        "se": "gamepad(ABS_RX, 23170) + gamepad(ABS_RY, 23170)",
        "s":  "gamepad(ABS_RY, 32767)",
        "sw": "gamepad(ABS_RX, -23170) + gamepad(ABS_RY, 23170)",
        "w":  "gamepad(ABS_RX, -32767)",
        "nw": "gamepad(ABS_RX, -23170) + gamepad(ABS_RY, -23170)",
    }


def get_dpad_button_mappings() -> Dict[str, str]:
    """
    Returns standard Gamepad D-pad button mappings.
    """
    return {
        "n":  "gamepad(BTN_DPAD_UP)",
        "e":  "gamepad(BTN_DPAD_RIGHT)",
        "s":  "gamepad(BTN_DPAD_DOWN)",
        "w":  "gamepad(BTN_DPAD_LEFT)",
        "ne": "gamepad(BTN_DPAD_UP) + gamepad(BTN_DPAD_RIGHT)",
        "se": "gamepad(BTN_DPAD_DOWN) + gamepad(BTN_DPAD_RIGHT)",
        "sw": "gamepad(BTN_DPAD_DOWN) + gamepad(BTN_DPAD_LEFT)",
        "nw": "gamepad(BTN_DPAD_UP) + gamepad(BTN_DPAD_LEFT)",
    }


def parse_gamepad_display_text(symbol: str) -> Optional[str]:
    """Translates raw gamepad symbol into concise readable HUD/UI text."""
    trimmed = symbol.strip()
    if not ("gamepad(" in trimmed or "ABS_" in trimmed or "BTN_" in trimmed):
        return None

    # Left Stick
    m_x = re.search(r'ABS_X\s*,\s*(-?\d+)', trimmed)
    m_y = re.search(r'ABS_Y\s*,\s*(-?\d+)', trimmed)
    if m_x and m_y:
        val_x = int(m_x.group(1))
        val_y = int(m_y.group(1))
        if val_x < 0 and val_y < 0:
            return "LS↖"
        elif val_x > 0 and val_y < 0:
            return "LS↗"
        elif val_x < 0 and val_y > 0:
            return "LS↙"
        elif val_x > 0 and val_y > 0:
            return "LS↘"
        return "LS"
    elif m_y:
        val_y = int(m_y.group(1))
        return "LS↑" if val_y < 0 else "LS↓"
    elif m_x:
        val_x = int(m_x.group(1))
        return "LS←" if val_x < 0 else "LS→"

    # Right Stick
    m_rx = re.search(r'ABS_RX\s*,\s*(-?\d+)', trimmed)
    m_ry = re.search(r'ABS_RY\s*,\s*(-?\d+)', trimmed)
    if m_rx and m_ry:
        val_rx = int(m_rx.group(1))
        val_ry = int(m_ry.group(1))
        if val_rx < 0 and val_ry < 0:
            return "RS↖"
        elif val_rx > 0 and val_ry < 0:
            return "RS↗"
        elif val_rx < 0 and val_ry > 0:
            return "RS↙"
        elif val_rx > 0 and val_ry > 0:
            return "RS↘"
        return "RS"
    elif m_ry:
        val_ry = int(m_ry.group(1))
        return "RS↑" if val_ry < 0 else "RS↓"
    elif m_rx:
        val_rx = int(m_rx.group(1))
        return "RS←" if val_rx < 0 else "RS→"

    # A diagonal D-pad mapping contains two button events.
    dpad = {
        name for name in ("BTN_DPAD_UP", "BTN_DPAD_DOWN", "BTN_DPAD_LEFT", "BTN_DPAD_RIGHT")
        if re.search(rf"\b{name}\b", trimmed)
    }
    vertical = "up" if "BTN_DPAD_UP" in dpad else "down" if "BTN_DPAD_DOWN" in dpad else None
    horizontal = "right" if "BTN_DPAD_RIGHT" in dpad else "left" if "BTN_DPAD_LEFT" in dpad else None
    if vertical and horizontal:
        return "D" + {("up", "right"): "↗", ("down", "right"): "↘", ("down", "left"): "↙", ("up", "left"): "↖"}[(vertical, horizontal)]
    if vertical:
        return "D↑" if vertical == "up" else "D↓"
    if horizontal:
        return "D→" if horizontal == "right" else "D←"

    # Triggers & Buttons
    if "ABS_Z" in trimmed:
        return "LT"
    if "ABS_RZ" in trimmed:
        return "RT"
    if "BTN_SOUTH" in trimmed or "BTN_A" in trimmed:
        return "(A)"
    if "BTN_EAST" in trimmed or "BTN_B" in trimmed:
        return "(B)"
    if "BTN_NORTH" in trimmed or "BTN_X" in trimmed:
        return "(X)"
    if "BTN_WEST" in trimmed or "BTN_Y" in trimmed:
        return "(Y)"
    if "BTN_TL" in trimmed:
        return "LB"
    if "BTN_TR" in trimmed:
        return "RB"
    if "BTN_THUMBL" in trimmed:
        return "L3"
    if "BTN_THUMBR" in trimmed:
        return "R3"
    if "BTN_START" in trimmed:
        return "START"
    if "BTN_SELECT" in trimmed:
        return "SELECT"
    return "PAD"
