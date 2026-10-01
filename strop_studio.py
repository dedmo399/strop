#!/usr/bin/env python3
"""
Strop — Universal Parameterized Hardware Studio
Dynamically dispatches and renders studio interfaces for all 230+ OpenRazer input devices.
Supports:
- Keypads: Tartarus Pro, Tartarus V2, Orbweaver, Nostromo
- Keyboards: Full ANSI, TKL Tournament, 75%, 65%, 60% Mini, and Blade Laptops
- Mice: Naga MMO 12-Grid, Naga Hex, Basilisk FPS Clutch, Viper Ambi, DeathAdder
"""

import sys
import os
import argparse
from pathlib import Path

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from strop_core.catalog import (
    get_device_catalog, get_device_by_name, get_archetype_for_device,
    KEYPAD_TARTARUS, KEYPAD_ORBWEAVER, KEYPAD_NOSTROMO,
    KEYBOARD_FULL, KEYBOARD_TKL, KEYBOARD_75, KEYBOARD_65, KEYBOARD_60, KEYBOARD_BLADE,
    MOUSE_NAGA_MMO, MOUSE_NAGA_HEX, MOUSE_BASILISK_FPS, MOUSE_FPS, MOUSE_AMBI
)
from strop_core.device import detect_device


def launch_for_device(device_name: str):
    dev_info = get_device_by_name(device_name)
    archetype = get_archetype_for_device(device_name)
    
    # Pass --device to target studio entrypoint
    sys.argv = [sys.argv[0], f"--device={device_name}"]

    # 1. Keypads
    if archetype in [KEYPAD_TARTARUS, KEYPAD_ORBWEAVER, KEYPAD_NOSTROMO]:
        from strop_keypad import main as keypad_main
        return keypad_main()

    # 2. Mice
    elif archetype in [MOUSE_NAGA_MMO, MOUSE_NAGA_HEX, MOUSE_BASILISK_FPS, MOUSE_FPS, MOUSE_AMBI]:
        from strop_mouse import main as mouse_main
        return mouse_main()

    # 3. Keyboards (Full, TKL, 75%, 60%, Blade)
    else:
        from strop_keyboard import main as keyboard_main
        return keyboard_main()



def main():
    parser = argparse.ArgumentParser(description="Strop Universal Razer Studio Launcher")
    parser.add_argument("--device", "-d", type=str, help="Device name to launch (e.g. 'Razer Naga Pro', 'Razer Huntsman Mini')")
    parser.add_argument("--list", "-l", action="store_true", help="List all 230+ supported OpenRazer input devices")
    args, unknown = parser.parse_known_args()

    if args.list:
        catalog = get_device_catalog()
        print(f"🗡️ STROP — Supported OpenRazer Input Devices ({len(catalog)} total):\n")
        current_cat = None
        for d in catalog:
            cat = d["category"].upper()
            if cat != current_cat:
                print(f"\n=== {cat}S ===")
                current_cat = cat
            print(f"  • {d['name']:<40} [PID: {d['pid']:<6}] ({d['archetype']})")
        return 0

    target = args.device or "Razer Tartarus Pro"
    return launch_for_device(target)


if __name__ == "__main__":
    sys.exit(main())
