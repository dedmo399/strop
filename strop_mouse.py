#!/usr/bin/env python3
"""
Strop — Razer Mouse Remap Studio (Native Linux GTK4 GUI)
Modular mouse editor with generic layout archetypes for:
- Naga Series Interchangeable Side Plates (2-Button FPS, 7-Button Hex, and 12-Button MMO)
- Basilisk / DeathAdder / Viper / Cobra / Mamba FPS ergonomics
- Ambidextrous dual side button configurations
Powered by BaseStudioWindow.
"""


import sys
import os
from pathlib import Path

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from strop_core.device import scan_all_connected_devices, detect_device
from strop_core.theme import apply_theme
from strop_core.studio_base import BaseStudioWindow
from strop_core.catalog import get_archetype_for_device, MOUSE_NAGA_MMO, MOUSE_NAGA_HEX


import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, GLib, Gio


from strop_core.layouts.mouse import (
    COMMON_MOUSE_BUTTONS, NAGA_12_GRID, NAGA_HEX_7_GRID, FPS_SIDE_BUTTONS
)





class RazerMouseStudioWindow(BaseStudioWindow):
    """Refactored Universal Mouse Studio Window."""
    def __init__(self, app, device_override=None):
        self.device_override = device_override
        super().__init__(app, title="Strop — Mouse Studio", default_width=1020, default_height=680)

    def _init_device(self):
        if self.device_override:
            if isinstance(self.device_override, dict):
                self.detected_device = self.device_override
            else:
                self.detected_device = detect_device(self.device_override, default_name=self.device_override)
        else:
            self.detected_device = self._auto_detect_mouse()


        self.default_device_name = self.detected_device.get("name", "Razer Naga Pro")
        self.default_preset_name = "my-mouse-preset"
        self.archetype = self.detected_device.get("archetype") or get_archetype_for_device(self.default_device_name)


    def _auto_detect_mouse(self):
        return detect_device("naga", default_name="Razer Naga Pro")


    def _init_hardware_state(self):
        for item in COMMON_MOUSE_BUTTONS:
            self.state[item["id"]] = {
                "id": item["id"], "name": item["name"], "label": item["l"],
                "code": item["c"], "aliases": item.get("aliases", []),
                "output": "", "target": "mouse"
            }
        for row in NAGA_12_GRID:
            for item in row:
                self.state[item["id"]] = {
                    "id": item["id"], "name": item["name"], "label": item["l"],
                    "code": item["c"], "aliases": item.get("aliases", []),
                    "output": "", "target": "keyboard"
                }
        for item in NAGA_HEX_7_GRID:
            self.state[item["id"]] = {
                "id": item["id"], "name": item["name"], "label": item["l"],
                "code": item["c"], "aliases": item.get("aliases", []),
                "output": "", "target": "keyboard"
            }
        for item in FPS_SIDE_BUTTONS:
            self.state[item["id"]] = {
                "id": item["id"], "name": item["name"], "label": item["l"],
                "code": item["c"], "aliases": item.get("aliases", []),
                "output": "", "target": "keyboard"
            }


    def _get_studio_title_markup(self) -> str:
        return "<span size='medium' weight='bold' color='#f8fafc'>STROP <span color='#22c55e'>Mouse Studio</span></span>"

    def _build_hardware_canvas(self) -> Gtk.Widget:
        canvas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        canvas.add_css_class("card")

        # Top Section: Common Top / Wheel / DPI Controls
        lbl_top = Gtk.Label()
        lbl_top.set_markup("<span weight='bold' size='small' color='#94a3b8'>Primary Mouse Controls &amp; Scroll Wheel</span>")
        lbl_top.set_xalign(0)
        canvas.append(lbl_top)

        top_grid = Gtk.Grid()
        top_grid.set_column_spacing(8)
        top_grid.set_row_spacing(8)
        top_grid.set_hexpand(True)

        for idx, item in enumerate(COMMON_MOUSE_BUTTONS):
            col = idx % 5
            row = idx // 5
            btn = self._create_mouse_button_widget(item)
            top_grid.attach(btn, col, row, 1, 1)

        canvas.append(top_grid)

        # Modular Side Plates
        lbl_side = Gtk.Label()
        lbl_side.set_markup("<span weight='bold' size='small' color='#94a3b8'>Interchangeable Side Plates &amp; Thumb Clusters</span>")
        lbl_side.set_xalign(0)
        lbl_side.set_margin_top(8)
        canvas.append(lbl_side)

        side_stack = Gtk.Notebook()
        side_stack.set_vexpand(False)

        # Plate 1: 2-Button FPS / Standard Ergonomic Plate
        fps_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        fps_box.set_margin_top(8)
        fps_box.set_halign(Gtk.Align.CENTER)

        for item in FPS_SIDE_BUTTONS:
            btn = self._create_mouse_button_widget(item, width=130, height=48)
            fps_box.append(btn)
        side_stack.append_page(fps_box, Gtk.Label(label="2-Button FPS / Ergonomic Plate"))

        # Plate 2: 7-Button MOBA / Action-RPG Hex Wheel Plate
        hex_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        hex_box.set_margin_top(8)
        hex_box.set_halign(Gtk.Align.CENTER)

        for item in NAGA_HEX_7_GRID:
            btn = self._create_mouse_button_widget(item, width=54, height=44)
            hex_box.append(btn)
        side_stack.append_page(hex_box, Gtk.Label(label="7-Button MOBA / Action-RPG Hex Plate"))

        # Plate 3: 12-Button MMO / Macro Grid Plate
        naga_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        naga_box.set_margin_top(6)
        naga_grid = Gtk.Grid()
        naga_grid.set_column_spacing(6)
        naga_grid.set_row_spacing(6)
        naga_grid.set_halign(Gtk.Align.CENTER)

        for r_idx, row in enumerate(NAGA_12_GRID):
            for c_idx, item in enumerate(row):
                btn = self._create_mouse_button_widget(item, width=64, height=42)
                naga_grid.attach(btn, c_idx, r_idx, 1, 1)
        naga_box.append(naga_grid)
        side_stack.append_page(naga_box, Gtk.Label(label="12-Button MMO / Macro Grid Plate"))

        # Auto-switch tab based on detected archetype
        if self.archetype == MOUSE_NAGA_MMO:
            side_stack.set_current_page(2)
        elif self.archetype == MOUSE_NAGA_HEX:
            side_stack.set_current_page(1)
        else:
            side_stack.set_current_page(0)

        canvas.append(side_stack)
        return canvas



    def _create_mouse_button_widget(self, item, width=100, height=40):
        btn = Gtk.Button()
        btn.add_css_class("key-btn")
        btn.set_size_request(width, height)
        btn.set_hexpand(True)

        lbl = Gtk.Label()
        lbl.set_markup(f"<span weight='bold' size='8500'>{GLib.markup_escape_text(item['l'])}</span>")
        btn.set_child(lbl)
        btn.connect("clicked", self._on_key_clicked, item["id"])

        self.button_widgets[item["id"]] = {
            "btn": btn, "lbl": lbl, "raw_label": item["l"]
        }
        return btn


def on_startup(app):
    apply_theme()


def on_activate(app):
    dev_name = getattr(app, "_device_override", None)
    win = RazerMouseStudioWindow(app, device_override=dev_name)
    win.present()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Strop Mouse Remap Studio")
    parser.add_argument("--device", "-d", type=str, default=None, help="Target Razer Mouse model")
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
