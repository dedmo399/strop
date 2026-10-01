"""
Keypad hardware layout definitions (Tartarus Pro/V2/Chroma, Orbweaver, Nostromo).
Single source of truth shared by Keypad Studio and In-Game HUD Overlay.
"""

# 4x5 Key Grid (Keys 01-19)
KEYPAD_GRID = [
    [
        {"l": "01", "name": "Key 01 (1)", "c": 2, "aliases": ["key01", "key1", "1"]},
        {"l": "02", "name": "Key 02 (2)", "c": 3, "aliases": ["key02", "key2", "2"]},
        {"l": "03", "name": "Key 03 (3)", "c": 4, "aliases": ["key03", "key3", "3"]},
        {"l": "04", "name": "Key 04 (4)", "c": 5, "aliases": ["key04", "key4", "4"]},
        {"l": "05", "name": "Key 05 (5)", "c": 6, "aliases": ["key05", "key5", "5"]},
    ],
    [
        {"l": "06", "name": "Key 06 (Tab)", "c": 15, "aliases": ["key06", "key6", "tab"]},
        {"l": "07", "name": "Key 07 (Q)", "c": 16, "aliases": ["key07", "key7", "q"]},
        {"l": "08", "name": "Key 08 (W)", "c": 17, "aliases": ["key08", "key8", "w"]},
        {"l": "09", "name": "Key 09 (E)", "c": 18, "aliases": ["key09", "key9", "e"]},
        {"l": "10", "name": "Key 10 (R)", "c": 19, "aliases": ["key10", "r"]},
    ],
    [
        {"l": "11", "name": "Key 11 (Caps)", "c": 58, "aliases": ["key11", "caps", "capslock"]},
        {"l": "12", "name": "Key 12 (A)", "c": 30, "aliases": ["key12", "a"]},
        {"l": "13", "name": "Key 13 (S)", "c": 31, "aliases": ["key13", "s"]},
        {"l": "14", "name": "Key 14 (D)", "c": 32, "aliases": ["key14", "d"]},
        {"l": "15", "name": "Key 15 (F)", "c": 33, "aliases": ["key15", "f"]},
    ],
    [
        {"l": "16", "name": "Key 16 (Shift)", "c": 42, "aliases": ["key16", "shift", "shift_l"]},
        {"l": "17", "name": "Key 17 (Z)", "c": 44, "aliases": ["key17", "z"]},
        {"l": "18", "name": "Key 18 (X)", "c": 45, "aliases": ["key18", "x"]},
        {"l": "19", "name": "Key 19 (C)", "c": 46, "aliases": ["key19", "c"]},
    ],
]

# Key 20 (Spacebar)
SPACEBAR_DATA = {
    "id": "spacebar",
    "name": "Key 20 (Spacebar)",
    "l": "20",
    "c": 57,
    "aliases": ["key20", "space", "spacebar", "key 20", "20"],
    "verify": False,
    "note": ""
}

# Hyper-Response Thumb Button
THUMB_BTN_DATA = {
    "id": "thumb",
    "name": "Hyper-response Thumb Button",
    "l": "Thumb",
    "c": 56,
    "aliases": ["thumb", "dpad_button", "dpad button", "alt", "thumb button"],
    "verify": False,
    "note": "Ships mapped to Alt on most firmware revisions."
}

# 8-Way D-Pad
DPAD_DATA = {
    "n":  {"l": "↑", "name": "D-pad Up", "c": 103, "combo": [103], "aliases": ["dpad up", "dpad_up", "up"], "verify": False},
    "ne": {"l": "↗", "name": "D-pad Up-Right", "c": None, "combo": [103, 106], "aliases": ["dpad up right", "dpad_up_right"], "verify": True},
    "e":  {"l": "→", "name": "D-pad Right", "c": 106, "combo": [106], "aliases": ["dpad right", "dpad_right", "right"], "verify": False},
    "se": {"l": "↘", "name": "D-pad Down-Right", "c": None, "combo": [108, 106], "aliases": ["dpad down right", "dpad_down_right"], "verify": True},
    "s":  {"l": "↓", "name": "D-pad Down", "c": 108, "combo": [108], "aliases": ["dpad down", "dpad_down", "down"], "verify": False},
    "sw": {"l": "↙", "name": "D-pad Down-Left", "c": None, "combo": [108, 105], "aliases": ["dpad down left", "dpad_down_left"], "verify": True},
    "w":  {"l": "←", "name": "D-pad Left", "c": 105, "combo": [105], "aliases": ["dpad left", "dpad_left", "left"], "verify": False},
    "nw": {"l": "↖", "name": "D-pad Up-Left", "c": None, "combo": [103, 105], "aliases": ["dpad up left", "dpad_up_left"], "verify": True},
}

# Scroll Wheel
SCROLL_UP_DATA = {
    "id": "scrollUp",
    "name": "Scroll Wheel Up",
    "l": "Scr↑",
    "c": None,
    "aliases": ["scroll up", "scroll_up", "wheel up"],
    "verify": True,
    "note": "Driver-dependent scancode; verify in input-remapper-gtk."
}

SCROLL_DOWN_DATA = {
    "id": "scrollDown",
    "name": "Scroll Wheel Down",
    "l": "Scr↓",
    "c": None,
    "aliases": ["scroll down", "scroll_down", "wheel down"],
    "verify": True,
    "note": "Driver-dependent scancode; verify in input-remapper-gtk."
}
