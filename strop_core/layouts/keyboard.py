"""
Keyboard hardware layout definitions (Full ANSI 108-Key, TKL, 75%, 65%, 60% Mini, Blade Laptops).
Standardized 1u keyboard scaling unit calculations.
"""

# Physical 1u Base Dimensions in Pixels
U_WIDTH = 38
U_HEIGHT = 36


def u_to_px(u_val: float, base_px: int = U_WIDTH) -> int:
    """Converts a standard key unit (e.g. 1.25u, 2.25u, 6.25u) into pixel width."""
    return int(round(u_val * base_px))


# Main Alphanumeric Block (Row 0 to Row 5)
MAIN_KEYS = [
    # Row 0: Function row
    [
        {"id": "esc", "l": "Esc", "name": "Escape", "c": 1, "w": 1.0, "gap": 1.0},
        {"id": "f1", "l": "F1", "name": "F1", "c": 59, "w": 1.0},
        {"id": "f2", "l": "F2", "name": "F2", "c": 60, "w": 1.0},
        {"id": "f3", "l": "F3", "name": "F3", "c": 61, "w": 1.0},
        {"id": "f4", "l": "F4", "name": "F4", "c": 62, "w": 1.0, "gap": 0.5},
        {"id": "f5", "l": "F5", "name": "F5", "c": 63, "w": 1.0},
        {"id": "f6", "l": "F6", "name": "F6", "c": 64, "w": 1.0},
        {"id": "f7", "l": "F7", "name": "F7", "c": 65, "w": 1.0},
        {"id": "f8", "l": "F8", "name": "F8", "c": 66, "w": 1.0, "gap": 0.5},
        {"id": "f9", "l": "F9", "name": "F9", "c": 67, "w": 1.0},
        {"id": "f10", "l": "F10", "name": "F10", "c": 68, "w": 1.0},
        {"id": "f11", "l": "F11", "name": "F11", "c": 87, "w": 1.0},
        {"id": "f12", "l": "F12", "name": "F12", "c": 88, "w": 1.0},
    ],
    # Row 1: Number row
    [
        {"id": "grave", "l": "`", "name": "Grave / Tilde", "c": 41, "w": 1.0},
        {"id": "k1", "l": "1", "name": "1", "c": 2, "w": 1.0},
        {"id": "k2", "l": "2", "name": "2", "c": 3, "w": 1.0},
        {"id": "k3", "l": "3", "name": "3", "c": 4, "w": 1.0},
        {"id": "k4", "l": "4", "name": "4", "c": 5, "w": 1.0},
        {"id": "k5", "l": "5", "name": "5", "c": 6, "w": 1.0},
        {"id": "k6", "l": "6", "name": "6", "c": 7, "w": 1.0},
        {"id": "k7", "l": "7", "name": "7", "c": 8, "w": 1.0},
        {"id": "k8", "l": "8", "name": "8", "c": 9, "w": 1.0},
        {"id": "k9", "l": "9", "name": "9", "c": 10, "w": 1.0},
        {"id": "k0", "l": "0", "name": "0", "c": 11, "w": 1.0},
        {"id": "minus", "l": "-", "name": "Minus", "c": 12, "w": 1.0},
        {"id": "equal", "l": "=", "name": "Equal", "c": 13, "w": 1.0},
        {"id": "bsp", "l": "Bksp", "name": "Backspace", "c": 14, "w": 2.0},
    ],
    # Row 2: Tab / QWERTY row
    [
        {"id": "tab", "l": "Tab", "name": "Tab", "c": 15, "w": 1.5},
        {"id": "q", "l": "Q", "name": "Q", "c": 16, "w": 1.0},
        {"id": "w", "l": "W", "name": "W", "c": 17, "w": 1.0},
        {"id": "e", "l": "E", "name": "E", "c": 18, "w": 1.0},
        {"id": "r", "l": "R", "name": "R", "c": 19, "w": 1.0},
        {"id": "t", "l": "T", "name": "T", "c": 20, "w": 1.0},
        {"id": "y", "l": "Y", "name": "Y", "c": 21, "w": 1.0},
        {"id": "u", "l": "U", "name": "U", "c": 22, "w": 1.0},
        {"id": "i", "l": "I", "name": "I", "c": 23, "w": 1.0},
        {"id": "o", "l": "O", "name": "O", "c": 24, "w": 1.0},
        {"id": "p", "l": "P", "name": "P", "c": 25, "w": 1.0},
        {"id": "lbrk", "l": "[", "name": "Left Bracket", "c": 26, "w": 1.0},
        {"id": "rbrk", "l": "]", "name": "Right Bracket", "c": 27, "w": 1.0},
        {"id": "bslash", "l": "\\", "name": "Backslash", "c": 43, "w": 1.5},
    ],
    # Row 3: Caps / Home row
    [
        {"id": "caps", "l": "Caps", "name": "Caps Lock", "c": 58, "w": 1.75},
        {"id": "a", "l": "A", "name": "A", "c": 30, "w": 1.0},
        {"id": "s", "l": "S", "name": "S", "c": 31, "w": 1.0},
        {"id": "d", "l": "D", "name": "D", "c": 32, "w": 1.0},
        {"id": "f", "l": "F", "name": "F", "c": 33, "w": 1.0},
        {"id": "g", "l": "G", "name": "G", "c": 34, "w": 1.0},
        {"id": "h", "l": "H", "name": "H", "c": 35, "w": 1.0},
        {"id": "j", "l": "J", "name": "J", "c": 36, "w": 1.0},
        {"id": "k", "l": "K", "name": "K", "c": 37, "w": 1.0},
        {"id": "l", "l": "L", "name": "L", "c": 38, "w": 1.0},
        {"id": "semi", "l": ";", "name": "Semicolon", "c": 39, "w": 1.0},
        {"id": "quote", "l": "'", "name": "Apostrophe", "c": 40, "w": 1.0},
        {"id": "enter", "l": "Enter", "name": "Enter", "c": 28, "w": 2.25},
    ],
    # Row 4: Shift row
    [
        {"id": "lshift", "l": "Shift", "name": "Left Shift", "c": 42, "w": 2.25},
        {"id": "z", "l": "Z", "name": "Z", "c": 44, "w": 1.0},
        {"id": "x", "l": "X", "name": "X", "c": 45, "w": 1.0},
        {"id": "c", "l": "C", "name": "C", "c": 46, "w": 1.0},
        {"id": "v", "l": "V", "name": "V", "c": 47, "w": 1.0},
        {"id": "b", "l": "B", "name": "B", "c": 48, "w": 1.0},
        {"id": "n", "l": "N", "name": "N", "c": 49, "w": 1.0},
        {"id": "m", "l": "M", "name": "M", "c": 50, "w": 1.0},
        {"id": "comma", "l": ",", "name": "Comma", "c": 51, "w": 1.0},
        {"id": "dot", "l": ".", "name": "Period", "c": 52, "w": 1.0},
        {"id": "slash", "l": "/", "name": "Slash", "c": 53, "w": 1.0},
        {"id": "rshift", "l": "Shift", "name": "Right Shift", "c": 54, "w": 2.75},
    ],
    # Row 5: Bottom Modifier row
    [
        {"id": "lctrl", "l": "Ctrl", "name": "Left Ctrl", "c": 29, "w": 1.25},
        {"id": "lwin", "l": "Super", "name": "Left Super / Win", "c": 125, "w": 1.25},
        {"id": "lalt", "l": "Alt", "name": "Left Alt", "c": 56, "w": 1.25},
        {"id": "space", "l": "Space", "name": "Spacebar", "c": 57, "w": 6.25},
        {"id": "ralt", "l": "Alt", "name": "Right Alt", "c": 100, "w": 1.25},
        {"id": "fn", "l": "Fn", "name": "Razer Fn Key", "c": 464, "w": 1.25, "aliases": ["fn"]},
        {"id": "menu", "l": "Menu", "name": "Menu / Compose", "c": 127, "w": 1.25},
        {"id": "rctrl", "l": "Ctrl", "name": "Right Ctrl", "c": 97, "w": 1.25},
    ],
]

# Navigation & Edit Cluster (6 Rows aligned with Main 60% Matrix)
NAV_KEYS = [
    # Row 0: System
    [
        {"id": "prtsc", "l": "PrtSc", "name": "Print Screen", "c": 99},
        {"id": "scrlk", "l": "ScrLk", "name": "Scroll Lock", "c": 70},
        {"id": "pause", "l": "Pause", "name": "Pause / Break", "c": 119},
    ],
    # Row 1: Insert, Home, Page Up
    [
        {"id": "ins", "l": "Ins", "name": "Insert", "c": 110},
        {"id": "home", "l": "Home", "name": "Home", "c": 102},
        {"id": "pgup", "l": "PgUp", "name": "Page Up", "c": 104},
    ],
    # Row 2: Delete, End, Page Down
    [
        {"id": "del", "l": "Del", "name": "Delete", "c": 111},
        {"id": "end", "l": "End", "name": "End", "c": 107},
        {"id": "pgdn", "l": "PgDn", "name": "Page Down", "c": 109},
    ],
    # Row 3: Spacer row between nav cluster and arrow cluster
    [],
    # Row 4: Arrow Up (centered above Down)
    [
        {"id": "up", "l": "▲", "name": "Up Arrow", "c": 103, "col": 1},
    ],
    # Row 5: Arrow Left, Down, Right
    [
        {"id": "left", "l": "◀", "name": "Left Arrow", "c": 105, "col": 0},
        {"id": "down", "l": "▼", "name": "Down Arrow", "c": 108, "col": 1},
        {"id": "right", "l": "▶", "name": "Right Arrow", "c": 106, "col": 2},
    ],
]

# Dedicated Media Controls (BlackWidow V3 Roller + Multi-Function Media Button)
MEDIA_KEYS = [
    {"id": "mute", "l": "Mute", "name": "Volume Mute (Roller Click)", "c": 113, "aliases": ["mute", "key_mute"]},
    {"id": "voldn", "l": "Vol-", "name": "Volume Down (Roller Down)", "c": 114, "aliases": ["volumedown", "voldn"]},
    {"id": "volup", "l": "Vol+", "name": "Volume Up (Roller Up)", "c": 115, "aliases": ["volumeup", "volup"]},
    {"id": "play", "l": "⏯", "name": "Media Play / Pause Button", "c": 164, "aliases": ["playpause", "media_playpause"]},
]

# Numpad Cluster (6 Rows aligned with Main 60% Matrix and Navigation Cluster)
NUMPAD_KEYS = [
    # Row 0: Dedicated Media Row / BlackWidow V3 Roller
    MEDIA_KEYS,
    # Row 1: NumLock, /, *, -
    [
        {"id": "numlk", "l": "Num", "name": "Num Lock", "c": 69},
        {"id": "kp_slash", "l": "/", "name": "Numpad Slash", "c": 98},
        {"id": "kp_star", "l": "*", "name": "Numpad Asterisk", "c": 55},
        {"id": "kp_minus", "l": "-", "name": "Numpad Minus", "c": 74},
    ],
    # Row 2: 7, 8, 9, + (2-row vertical key)
    [
        {"id": "kp_7", "l": "7", "name": "Numpad 7", "c": 71, "col": 0},
        {"id": "kp_8", "l": "8", "name": "Numpad 8", "c": 72, "col": 1},
        {"id": "kp_9", "l": "9", "name": "Numpad 9", "c": 73, "col": 2},
        {"id": "kp_plus", "l": "+", "name": "Numpad Plus", "c": 78, "col": 3, "h": 2},
    ],
    # Row 3: 4, 5, 6
    [
        {"id": "kp_4", "l": "4", "name": "Numpad 4", "c": 75, "col": 0},
        {"id": "kp_5", "l": "5", "name": "Numpad 5", "c": 76, "col": 1},
        {"id": "kp_6", "l": "6", "name": "Numpad 6", "c": 77, "col": 2},
    ],
    # Row 4: 1, 2, 3, Enter (2-row vertical key)
    [
        {"id": "kp_1", "l": "1", "name": "Numpad 1", "c": 79, "col": 0},
        {"id": "kp_2", "l": "2", "name": "Numpad 2", "c": 80, "col": 1},
        {"id": "kp_3", "l": "3", "name": "Numpad 3", "c": 81, "col": 2},
        {"id": "kp_enter", "l": "Ent", "name": "Numpad Enter", "c": 96, "col": 3, "h": 2},
    ],
    # Row 5: 0 (2-unit wide), .
    [
        {"id": "kp_0", "l": "0", "name": "Numpad 0", "c": 82, "col": 0, "w": 2.0},
        {"id": "kp_dot", "l": ".", "name": "Numpad Period", "c": 83, "col": 2},
    ],
]

