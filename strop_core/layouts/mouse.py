"""
Mouse hardware layout definitions (Naga 12-Grid MMO, Basilisk FPS Clutch, Viper Ambi).
"""

COMMON_MOUSE_BUTTONS = [
    {"id": "btn_left", "l": "Left Click", "name": "Primary Left Click", "c": 272, "aliases": ["btn_left", "left click", "btn 1", "left_click", "btn_mouse_left"]},
    {"id": "btn_right", "l": "Right Click", "name": "Secondary Right Click", "c": 273, "aliases": ["btn_right", "right click", "btn 2", "right_click", "btn_mouse_right"]},
    {"id": "btn_middle", "l": "Wheel Click", "name": "Middle Mouse Click", "c": 274, "aliases": ["btn_middle", "middle click", "btn 3", "middle_click", "btn_mouse_middle"]},
    {"id": "wheel_up", "l": "Wheel Up", "name": "Scroll Wheel Up", "c": None, "aliases": ["wheel up", "wheel_up", "rel_wheel:1", "wheel_up_macro", "rel_wheel"]},
    {"id": "wheel_down", "l": "Wheel Down", "name": "Scroll Wheel Down", "c": None, "aliases": ["wheel down", "wheel_down", "rel_wheel:-1", "wheel_down_macro"]},
    {"id": "tilt_left", "l": "Tilt Left", "name": "Scroll Wheel Tilt Left", "c": 279, "aliases": ["tilt left", "tilt_left", "btn_tilt_left", "wheel_left"]},
    {"id": "tilt_right", "l": "Tilt Right", "name": "Scroll Wheel Tilt Right", "c": 280, "aliases": ["tilt right", "tilt_right", "btn_tilt_right", "wheel_right"]},
    {"id": "dpi_up", "l": "DPI +", "name": "DPI Stage Up Button", "c": 148, "aliases": ["dpi up", "dpi+", "dpi_up", "dpi_stage_up"]},
    {"id": "dpi_down", "l": "DPI -", "name": "DPI Stage Down Button", "c": 149, "aliases": ["dpi down", "dpi-", "dpi_down", "dpi_stage_down"]},
]

NAGA_12_GRID = [
    [
        {"id": "naga_1", "l": "01", "name": "Naga Side Button 1", "c": 2, "aliases": ["1", "naga 1", "side 1", "naga_1"]},
        {"id": "naga_2", "l": "02", "name": "Naga Side Button 2", "c": 3, "aliases": ["2", "naga 2", "side 2", "naga_2"]},
        {"id": "naga_3", "l": "03", "name": "Naga Side Button 3", "c": 4, "aliases": ["3", "naga 3", "side 3", "naga_3"]},
    ],
    [
        {"id": "naga_4", "l": "04", "name": "Naga Side Button 4", "c": 5, "aliases": ["4", "naga 4", "side 4", "naga_4"]},
        {"id": "naga_5", "l": "05", "name": "Naga Side Button 5", "c": 6, "aliases": ["5", "naga 5", "side 5", "naga_5"]},
        {"id": "naga_6", "l": "06", "name": "Naga Side Button 6", "c": 7, "aliases": ["6", "naga 6", "side 6", "naga_6"]},
    ],
    [
        {"id": "naga_7", "l": "07", "name": "Naga Side Button 7", "c": 8, "aliases": ["7", "naga 7", "side 7", "naga_7"]},
        {"id": "naga_8", "l": "08", "name": "Naga Side Button 8", "c": 9, "aliases": ["8", "naga 8", "side 8", "naga_8"]},
        {"id": "naga_9", "l": "09", "name": "Naga Side Button 9", "c": 10, "aliases": ["9", "naga 9", "side 9", "naga_9"]},
    ],
    [
        {"id": "naga_10", "l": "10", "name": "Naga Side Button 10", "c": 11, "aliases": ["10", "naga 10", "side 10", "naga_10", "0"]},
        {"id": "naga_11", "l": "11", "name": "Naga Side Button 11", "c": 12, "aliases": ["11", "naga 11", "side 11", "naga_11", "-"]},
        {"id": "naga_12", "l": "12", "name": "Naga Side Button 12", "c": 13, "aliases": ["12", "naga 12", "side 12", "naga_12", "="]},
    ]
]

NAGA_HEX_7_GRID = [
    {"id": "naga_hex_1", "l": "01", "name": "Hex Side Button 1", "c": 2, "aliases": ["hex 1", "naga hex 1", "hex_1"]},
    {"id": "naga_hex_2", "l": "02", "name": "Hex Side Button 2", "c": 3, "aliases": ["hex 2", "naga hex 2", "hex_2"]},
    {"id": "naga_hex_3", "l": "03", "name": "Hex Side Button 3", "c": 4, "aliases": ["hex 3", "naga hex 3", "hex_3"]},
    {"id": "naga_hex_4", "l": "04", "name": "Hex Side Button 4", "c": 5, "aliases": ["hex 4", "naga hex 4", "hex_4"]},
    {"id": "naga_hex_5", "l": "05", "name": "Hex Side Button 5", "c": 6, "aliases": ["hex 5", "naga hex 5", "hex_5"]},
    {"id": "naga_hex_6", "l": "06", "name": "Hex Side Button 6", "c": 7, "aliases": ["hex 6", "naga hex 6", "hex_6"]},
    {"id": "naga_hex_7", "l": "07", "name": "Hex Side Button 7", "c": 8, "aliases": ["hex 7", "naga hex 7", "hex_7"]},
]

FPS_SIDE_BUTTONS = [
    {"id": "fps_forward", "l": "Forward (Front)", "name": "Forward Button (Front)", "c": 276, "aliases": ["btn_forward", "forward", "front", "btn_extra", "m5", "m4"]},
    {"id": "fps_back", "l": "Back (Rear)", "name": "Back Button (Rear)", "c": 275, "aliases": ["btn_back", "back", "rear", "btn_side", "m4", "m5"]},
]









AMBI_RIGHT_BUTTONS = [
    {"id": "ambi_right_front", "l": "Right Front (M7)", "name": "Right Side Front Button", "c": 278, "aliases": ["right_front", "m7", "btn_side_right_1"]},
    {"id": "ambi_right_back", "l": "Right Back (M8)", "name": "Right Side Back Button", "c": 281, "aliases": ["right_back", "m8", "btn_side_right_2"]},
]
