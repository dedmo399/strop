#!/usr/bin/env python3
"""
Strop — Razer Keyboard Remap Studio (Native Ubuntu GTK4 GUI)
Compact Studio Layout supporting full-size, TKL, 75%, 65%, 60% Mini, and Blade laptops.
Powered by BaseStudioWindow.
"""

import sys
import os
from pathlib import Path

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from strop_core.device import detect_device, clean_device_display_name
from strop_core.theme import apply_theme
from strop_core.studio_base import BaseStudioWindow
from strop_core.gamepad import get_left_stick_mappings, get_right_stick_mappings


import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, GLib, Gio


# ----------------------------------------------------------------------
# Accurate Hardware Key Layout Data (ANSI Full Size + Media Controls)
# ----------------------------------------------------------------------

from strop_core.catalog import (
    KEYBOARD_FULL, KEYBOARD_TKL, KEYBOARD_75, KEYBOARD_65, KEYBOARD_60, KEYBOARD_BLADE,
    get_archetype_for_device
)
from strop_core.layouts.keyboard import (
    MAIN_KEYS, NAV_KEYS, NUMPAD_KEYS as NUMPAD_GRID, u_to_px, U_WIDTH, U_HEIGHT
)



class KeyboardMainWindow(BaseStudioWindow):
    """Refactored Universal Keyboard Studio Window."""
    def __init__(self, app, device_override=None):
        self.device_override = device_override
        super().__init__(app, title="Strop — Keyboard Studio", default_width=1080, default_height=720)

    def _init_device(self):
        if self.device_override:
            if isinstance(self.device_override, dict):
                self.detected_device = self.device_override
            else:
                self.detected_device = detect_device(self.device_override, default_name=self.device_override)
        else:
            self.detected_device = detect_device("blackwidow", default_name="Razer BlackWidow V3")


        self.default_device_name = self.detected_device.get("name", "Razer BlackWidow V3")
        self.default_preset_name = "my-keyboard-preset"
        dev_name = self.detected_device["name"] if self.detected_device else self.default_device_name
        self.archetype = self.detected_device.get("archetype") or get_archetype_for_device(dev_name)



    def _init_hardware_state(self):
        # 1. Main 60% Matrix
        for row in MAIN_KEYS:
            for k in row:
                self.state[k["id"]] = {
                    "name": k["name"],
                    "label": k["l"],
                    "code": k["c"],
                    "aliases": k.get("aliases", []),
                    "output": "",
                    "target": "keyboard"
                }

        # 2. Navigation & Arrow Cluster
        for row in NAV_KEYS:
            for k in row:
                self.state[k["id"]] = {
                    "name": k["name"],
                    "label": k["l"],
                    "code": k["c"],
                    "aliases": k.get("aliases", []),
                    "output": "",
                    "target": "keyboard"
                }

        # 3. Numpad & Media Keys
        for row in NUMPAD_GRID:
            for k in row:
                self.state[k["id"]] = {
                    "name": k["name"],
                    "label": k["l"],
                    "code": k["c"],
                    "aliases": k.get("aliases", []),
                    "output": "",
                    "target": "keyboard"
                }


    def _get_studio_title_markup(self) -> str:
        return "<span size='medium' weight='bold' color='#f8fafc'>STROP <span color='#22c55e'>Keyboard Studio</span></span>"

    def _build_hardware_canvas(self) -> Gtk.Widget:
        chassis = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        chassis.add_css_class("chassis")
        chassis.set_halign(Gtk.Align.CENTER)

        kb_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        kb_row.set_halign(Gtk.Align.CENTER)
        chassis.append(kb_row)

        # 1. Main 60% Matrix (Left)
        main_grid = Gtk.Grid()
        main_grid.set_row_spacing(3)
        main_grid.set_column_spacing(3)

        for r, row in enumerate(MAIN_KEYS):
            current_col = 0
            for k in row:
                btn = Gtk.Button()
                btn.add_css_class("key-btn")

                unit_w = u_to_px(k.get("w", 1.0))
                btn.set_size_request(unit_w, U_HEIGHT)
                btn.connect("clicked", self._on_key_clicked, k["id"])


                lbl = Gtk.Label()
                lbl.set_markup(f"<span weight='bold' size='8500'>{GLib.markup_escape_text(k['l'])}</span>")
                lbl.set_justify(Gtk.Justification.CENTER)
                btn.set_child(lbl)

                self.button_widgets[k["id"]] = {"btn": btn, "lbl": lbl, "raw_label": k["l"]}

                span_cols = max(1, int(round(k.get("w", 1.0) * 4)))
                main_grid.attach(btn, current_col, r, span_cols, 1)
                current_col += span_cols

                if k.get("gap"):
                    current_col += int(k["gap"] * 4)

        kb_row.append(main_grid)

        # 2. Navigation & Arrows Cluster (Middle: shown on FULL, TKL, 75%, 65%)
        if self.archetype not in (KEYBOARD_60,):
            nav_grid = Gtk.Grid()
            nav_grid.set_row_spacing(3)
            nav_grid.set_column_spacing(3)

            for r, row in enumerate(NAV_KEYS):
                for k in row:
                    btn = Gtk.Button()
                    btn.add_css_class("key-btn")
                    btn.set_size_request(U_WIDTH, U_HEIGHT)
                    btn.connect("clicked", self._on_key_clicked, k["id"])

                    lbl = Gtk.Label()
                    lbl.set_markup(f"<span weight='bold' size='7500'>{GLib.markup_escape_text(k['l'])}</span>")
                    lbl.set_justify(Gtk.Justification.CENTER)
                    btn.set_child(lbl)

                    self.button_widgets[k["id"]] = {"btn": btn, "lbl": lbl, "raw_label": k["l"]}
                    c_idx = k.get("col", row.index(k))
                    nav_grid.attach(btn, c_idx, r, 1, 1)

            kb_row.append(nav_grid)

        # 3. Numpad & Media Roller Cluster (Right: shown on FULL keyboards)
        if self.archetype == KEYBOARD_FULL:
            np_grid = Gtk.Grid()
            np_grid.set_row_spacing(3)
            np_grid.set_column_spacing(3)

            for r, row in enumerate(NUMPAD_GRID):
                for k in row:
                    btn = Gtk.Button()
                    btn.add_css_class("key-btn")

                    w_units = k.get("w", 1.0)
                    h_units = k.get("h", 1)

                    unit_w = u_to_px(w_units)
                    unit_h = U_HEIGHT if h_units == 1 else (U_HEIGHT * 2 + 3)
                    btn.set_size_request(unit_w, unit_h)
                    btn.connect("clicked", self._on_key_clicked, k["id"])

                    lbl = Gtk.Label()
                    lbl.set_markup(f"<span weight='bold' size='8000'>{GLib.markup_escape_text(k['l'])}</span>")
                    lbl.set_justify(Gtk.Justification.CENTER)
                    btn.set_child(lbl)

                    self.button_widgets[k["id"]] = {"btn": btn, "lbl": lbl, "raw_label": k["l"]}

                    col_idx = k.get("col", row.index(k))
                    w_span = int(round(w_units))
                    np_grid.attach(btn, col_idx, r, w_span, h_units)

            kb_row.append(np_grid)

        return chassis



    def _build_custom_special_actions_page(self) -> Gtk.Widget:
        """Keyboard-specific WASD analog stick mapping presets."""
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        page_box.set_margin_top(4)

        lbl = Gtk.Label()
        lbl.set_markup("<span size='small' weight='bold' color='#86efac'>WASD / Arrow Gamepad Emulation:</span>")
        lbl.set_xalign(0)
        page_box.append(lbl)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        btn_wasd_ls = Gtk.Button(label="🕹 Map WASD -> Left Stick (LS)")
        btn_wasd_ls.add_css_class("quick-tag")
        btn_wasd_ls.set_tooltip_text("Maps W, A, S, D keys to 360 Left Analog Stick")
        btn_wasd_ls.connect("clicked", self._bind_wasd_left_stick)
        row.append(btn_wasd_ls)

        btn_arrows_dpad = Gtk.Button(label="🎮 Map Arrows -> Gamepad D-Pad")
        btn_arrows_dpad.add_css_class("quick-tag")
        btn_arrows_dpad.set_tooltip_text("Maps Arrow keys to Gamepad D-Pad buttons")
        btn_arrows_dpad.connect("clicked", self._bind_arrows_dpad)
        row.append(btn_arrows_dpad)

        page_box.append(row)
        return page_box

    def _bind_wasd_left_stick(self, widget):
        wasd_maps = {
            "w": "gamepad(ABS_Y, -32767)",
            "s": "gamepad(ABS_Y, 32767)",
            "a": "gamepad(ABS_X, -32767)",
            "d": "gamepad(ABS_X, 32767)"
        }
        for k_id, sym in wasd_maps.items():
            if k_id in self.state:
                self.state[k_id]["output"] = sym
                self.state[k_id]["target"] = "gamepad"
        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="WASD Mapped to Left Analog Stick",
            detail="Keys W, A, S, D are now configured for Left Stick (LS) movement in game controllers."
        )
        alert.show(self)

    def _bind_arrows_dpad(self, widget):
        arrow_maps = {
            "up": "gamepad(BTN_DPAD_UP)",
            "down": "gamepad(BTN_DPAD_DOWN)",
            "left": "gamepad(BTN_DPAD_LEFT)",
            "right": "gamepad(BTN_DPAD_RIGHT)"
        }
        for k_id, sym in arrow_maps.items():
            if k_id in self.state:
                self.state[k_id]["output"] = sym
                self.state[k_id]["target"] = "gamepad"
        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="Arrow Keys Mapped to D-Pad",
            detail="Arrow keys mapped to Gamepad D-Pad buttons (BTN_DPAD_UP/DOWN/LEFT/RIGHT)."
        )
        alert.show(self)


def on_startup(app):
    apply_theme()


def on_activate(app):
    dev_name = getattr(app, "_device_override", None)
    win = KeyboardMainWindow(app, device_override=dev_name)
    win.present()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Strop Keyboard Remap Studio")
    parser.add_argument("--device", "-d", type=str, default=None, help="Target Razer Keyboard model")
    args, unknown = parser.parse_known_args()

    app = Gtk.Application(
        application_id="com.razer.strop",
        flags=Gio.ApplicationFlags.NON_UNIQUE
    )


    app._device_override = args.device
    app.connect("startup", on_startup)
    app.connect("activate", on_activate)
    return app.run([sys.argv[0]] + unknown)


if __name__ == "__main__":
    sys.exit(main())

