#!/usr/bin/env python3
"""
Strop — Razer Keypad Remap Studio (Native Ubuntu GTK4 GUI)
Compact Studio Layout supporting Tartarus Pro/V2/Chroma, Orbweaver, and Nostromo.
Powered by BaseStudioWindow.
"""

import sys
import os
from pathlib import Path

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from strop_core.device import detect_device
from strop_core.theme import apply_theme
from strop_core.studio_base import BaseStudioWindow
from strop_core.catalog import get_archetype_for_device
from strop_core.gamepad import (
    get_left_stick_mappings, get_right_stick_mappings, get_dpad_button_mappings
)


import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gio


from strop_core.layouts.keypad import (
    KEYPAD_GRID, SPACEBAR_DATA, THUMB_BTN_DATA, DPAD_DATA,
    SCROLL_UP_DATA, SCROLL_DOWN_DATA
)

GRID_DATA = KEYPAD_GRID



class KeypadMainWindow(BaseStudioWindow):
    """Refactored Keypad Studio Window."""
    def __init__(self, app, device_override=None):
        self.device_override = device_override
        super().__init__(app, title="Strop — Keypad Studio", default_width=980, default_height=660)

    def _init_device(self):
        if self.device_override:
            if isinstance(self.device_override, dict):
                self.detected_device = self.device_override
            else:
                self.detected_device = detect_device(self.device_override, default_name=self.device_override)
        else:
            self.detected_device = detect_device("tartarus", default_name="Razer Tartarus Pro")


        self.default_device_name = self.detected_device.get("name", "Razer Tartarus Pro")
        self.default_preset_name = "my-keypad-preset"
        self.archetype = self.detected_device.get("archetype") or get_archetype_for_device(self.default_device_name)


    def _init_hardware_state(self):
        # 4x5 Grid Keys (Keys 01-19)
        for r, row in enumerate(GRID_DATA):
            for c, item in enumerate(row):
                kid = f"grid-{r}-{c}"
                self.state[kid] = {
                    "name": item["name"],
                    "label": item["l"],
                    "code": item["c"],
                    "aliases": item.get("aliases", []),
                    "verify": False,
                    "note": "",
                    "output": "",
                    "target": "keyboard"
                }

        # Scroll Wheel Up & Down
        for sdata in [SCROLL_UP_DATA, SCROLL_DOWN_DATA]:
            self.state[sdata["id"]] = {
                "name": sdata["name"],
                "label": sdata["l"],
                "code": sdata["c"],
                "aliases": sdata.get("aliases", []),
                "verify": sdata["verify"],
                "note": sdata["note"],
                "output": "",
                "target": "mouse"
            }

        # Thumb Button
        self.state[THUMB_BTN_DATA["id"]] = {
            "name": THUMB_BTN_DATA["name"],
            "label": THUMB_BTN_DATA["l"],
            "code": THUMB_BTN_DATA["c"],
            "aliases": THUMB_BTN_DATA.get("aliases", []),
            "verify": THUMB_BTN_DATA["verify"],
            "note": THUMB_BTN_DATA["note"],
            "output": "",
            "target": "keyboard"
        }

        # 8-Way D-Pad
        for dir_key, dinfo in DPAD_DATA.items():
            kid = f"dpad-{dir_key}"
            self.state[kid] = {
                "name": dinfo["name"],
                "label": dinfo["l"],
                "code": dinfo["c"],
                "combo": dinfo.get("combo", [dinfo["c"]] if dinfo["c"] else []),
                "aliases": dinfo.get("aliases", []),
                "verify": dinfo["verify"],
                "note": "",
                "output": "",
                "target": "keyboard"
            }


        # Spacebar (Key 20)
        self.state[SPACEBAR_DATA["id"]] = {
            "name": SPACEBAR_DATA["name"],
            "label": SPACEBAR_DATA["l"],
            "code": SPACEBAR_DATA["c"],
            "aliases": SPACEBAR_DATA.get("aliases", []),
            "verify": SPACEBAR_DATA["verify"],
            "note": SPACEBAR_DATA["note"],
            "output": "",
            "target": "keyboard"
        }

    def _get_studio_title_markup(self) -> str:
        return "<span size='medium' weight='bold' color='#f8fafc'>STROP <span color='#22c55e'>Keypad Studio</span></span>"

    def _build_hardware_canvas(self) -> Gtk.Widget:
        chassis = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        chassis.add_css_class("chassis")
        chassis.set_halign(Gtk.Align.CENTER)

        # Main Layout: 4x5 Keypad (Left) + Thumb cluster (Right)
        layout_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        layout_row.set_halign(Gtk.Align.CENTER)
        chassis.append(layout_row)

        # Left Column: Keypad Grid (Keys 01-19, Scroll Up in row 3 col 4, Scroll Down in row 4 col 4)
        grid = Gtk.Grid()
        grid.set_row_spacing(5)
        grid.set_column_spacing(5)

        for r, row in enumerate(GRID_DATA):
            for c, item in enumerate(row):
                kid = f"grid-{r}-{c}"
                btn = Gtk.Button()
                btn.add_css_class("key-btn")
                btn.connect("clicked", self._on_key_clicked, kid)

                lbl = Gtk.Label()
                lbl.set_markup(f"<span weight='bold' size='medium'>{item['l']}</span>")
                lbl.set_justify(Gtk.Justification.CENTER)
                btn.set_child(lbl)

                self.button_widgets[kid] = {"btn": btn, "lbl": lbl, "raw_label": item["l"]}
                grid.attach(btn, c, r, 1, 1)

        # Scroll Up in Row 3, Column 4 (next to Key 19)
        scroll_up_btn = Gtk.Button()
        scroll_up_btn.add_css_class("key-btn")
        scroll_up_btn.connect("clicked", self._on_key_clicked, "scrollUp")
        sup_lbl = Gtk.Label()
        sup_lbl.set_markup("<span weight='bold' size='small'>Scr↑</span>")
        scroll_up_btn.set_child(sup_lbl)
        self.button_widgets["scrollUp"] = {"btn": scroll_up_btn, "lbl": sup_lbl, "raw_label": "Scr↑"}
        grid.attach(scroll_up_btn, 4, 3, 1, 1)

        # Scroll Down in Row 4, Column 4 (under Scroll Up)
        scroll_dn_btn = Gtk.Button()
        scroll_dn_btn.add_css_class("key-btn")
        scroll_dn_btn.connect("clicked", self._on_key_clicked, "scrollDown")
        sdn_lbl = Gtk.Label()
        sdn_lbl.set_markup("<span weight='bold' size='small'>Scr↓</span>")
        scroll_dn_btn.set_child(sdn_lbl)
        self.button_widgets["scrollDown"] = {"btn": scroll_dn_btn, "lbl": sdn_lbl, "raw_label": "Scr↓"}
        grid.attach(scroll_dn_btn, 4, 4, 1, 1)


        layout_row.append(grid)

        # Right Column: Thumb Module (Thumb Button -> 8-Way D-pad -> Spacebar)
        thumb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        thumb_box.set_halign(Gtk.Align.CENTER)

        # 1. Thumb Button
        thumb_btn = Gtk.Button()
        thumb_btn.add_css_class("key-btn")
        thumb_btn.set_size_request(130, 28)
        thumb_btn.connect("clicked", self._on_key_clicked, "thumb")
        thumb_lbl = Gtk.Label()
        thumb_lbl.set_markup("<span weight='bold' size='small'>Thumb</span>")
        thumb_btn.set_child(thumb_lbl)
        self.button_widgets["thumb"] = {"btn": thumb_btn, "lbl": thumb_lbl, "raw_label": "Thumb"}
        thumb_box.append(thumb_btn)

        # 2. 8-Way D-Pad
        dpad_grid = Gtk.Grid()
        dpad_grid.set_row_spacing(3)
        dpad_grid.set_column_spacing(3)
        dpad_grid.set_halign(Gtk.Align.CENTER)

        dpad_positions = {
            "nw": (0, 0), "n": (1, 0), "ne": (2, 0),
            "w":  (0, 1),              "e":  (2, 1),
            "sw": (0, 2), "s": (1, 2), "se": (2, 2)
        }

        for dir_key, (col, row) in dpad_positions.items():
            kid = f"dpad-{dir_key}"
            dinfo = DPAD_DATA[dir_key]
            btn = Gtk.Button()
            btn.add_css_class("dpad-btn")
            btn.connect("clicked", self._on_key_clicked, kid)

            lbl = Gtk.Label()
            lbl.set_markup(f"<span weight='bold'>{dinfo['l']}</span>")
            btn.set_child(lbl)

            self.button_widgets[kid] = {"btn": btn, "lbl": lbl, "raw_label": dinfo["l"]}
            dpad_grid.attach(btn, col, row, 1, 1)

        thumb_box.append(dpad_grid)

        # 3. Spacebar (Key 20)
        space_btn = Gtk.Button()
        space_btn.add_css_class("key-btn")
        space_btn.set_size_request(130, 36)
        space_btn.connect("clicked", self._on_key_clicked, "spacebar")
        space_lbl = Gtk.Label()
        space_lbl.set_markup("<span weight='bold' size='medium'>20 (Space)</span>")
        space_btn.set_child(space_lbl)
        self.button_widgets["spacebar"] = {"btn": space_btn, "lbl": space_lbl, "raw_label": "20 (Space)"}
        thumb_box.append(space_btn)

        layout_row.append(thumb_box)
        return chassis

    def _build_custom_special_actions_pages(self):
        """Builds custom tabs for Keypad Studio: ⚡ Actions and 🕹 Emulation."""
        # -------------------------------------------------------------
        # Tab 1: ⚡ Actions (Set Defaults, Disable All, WASD Thumbpad)
        # -------------------------------------------------------------
        actions_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        actions_box.set_margin_top(6)
        actions_box.set_margin_start(4)
        actions_box.set_margin_end(4)

        lbl_act = Gtk.Label()
        lbl_act.set_markup("<span size='small' weight='bold' color='#86efac'>Batch Keypad Actions:</span>")
        lbl_act.set_xalign(0)
        actions_box.append(lbl_act)

        btn_grid = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        btn_default = Gtk.Button(label="↺ Set All to Default")
        btn_default.add_css_class("quick-tag")
        btn_default.set_tooltip_text("Clear all remappings and restore every key to its stock factory behavior")
        btn_default.connect("clicked", self._on_set_all_to_default)
        btn_grid.append(btn_default)

        btn_disable = Gtk.Button(label="⊘ Disable All Keys")
        btn_disable.add_css_class("quick-tag")
        btn_disable.set_tooltip_text("Set every physical key and D-pad direction to 'disable' (mute input)")
        btn_disable.connect("clicked", self._on_set_all_to_disable)
        btn_grid.append(btn_disable)

        btn_wasd = Gtk.Button(label="⌨ D-Pad ➔ WASD")
        btn_wasd.add_css_class("quick-tag")
        btn_wasd.set_tooltip_text("Map the D-Pad to keyboard WASD movement (Up=W, Down=S, Left=A, Right=D with full diagonal movement)")
        btn_wasd.connect("clicked", self._bind_thumbpad_to_wasd)
        btn_grid.append(btn_wasd)

        actions_box.append(btn_grid)

        # -------------------------------------------------------------
        # Tab 2: 🕹 Emulation (Analog Sticks & Gamepad D-Pad)
        # -------------------------------------------------------------
        emu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        emu_box.set_margin_top(6)
        emu_box.set_margin_start(4)
        emu_box.set_margin_end(4)

        lbl_emu = Gtk.Label()
        lbl_emu.set_markup("<span size='small' weight='bold' color='#86efac'>D-Pad Gamepad Emulation:</span>")
        lbl_emu.set_xalign(0)
        emu_box.append(lbl_emu)

        emu_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        btn_ls = Gtk.Button(label="🕹 Left Stick (LS)")
        btn_ls.add_css_class("quick-tag")
        btn_ls.set_tooltip_text("Map all 8 D-pad directions to Left Analog Stick (ABS_X, ABS_Y) with diagonal blending")
        btn_ls.connect("clicked", self._bind_dpad_to_left_stick)
        emu_row.append(btn_ls)

        btn_rs = Gtk.Button(label="🕹 Right Stick (RS)")
        btn_rs.add_css_class("quick-tag")
        btn_rs.set_tooltip_text("Map all 8 D-pad directions to Right Analog Stick (ABS_RX, ABS_RY)")
        btn_rs.connect("clicked", self._bind_dpad_to_right_stick)
        emu_row.append(btn_rs)

        btn_hat = Gtk.Button(label="🎮 Gamepad D-Pad (Hat)")
        btn_hat.add_css_class("quick-tag")
        btn_hat.set_tooltip_text("Map 8 directions to Gamepad D-Pad buttons (BTN_DPAD_UP, etc.)")
        btn_hat.connect("clicked", self._bind_dpad_to_gamepad_hat)
        emu_row.append(btn_hat)

        emu_box.append(emu_row)

        return [
            ("⚡ Actions", actions_box),
            ("🕹 Emulation", emu_box),
        ]

    def _on_set_all_to_default(self, widget):
        """Restores every key mapping back to factory stock (empty output)."""
        for s in self.state.values():
            s["output"] = ""
            s["target"] = "mouse" if s.get("id", "").startswith("scroll") else "keyboard"
        if self.selected_key_id:
            self.entry_output.set_text("")
        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="Restored All Keys to Default",
            detail="Every key has been reset to its default unmapped stock behavior."
        )
        alert.show(self)

    def _on_set_all_to_disable(self, widget):
        """Sets every key mapping to 'disable'."""
        for s in self.state.values():
            s["output"] = "disable"
            s["target"] = "keyboard"
        if self.selected_key_id:
            self.entry_output.set_text("disable")
        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="All Keys Disabled",
            detail="Every key, scroll direction, and D-pad input is now set to 'disable'."
        )
        alert.show(self)

    def _bind_thumbpad_to_wasd(self, widget):
        """Maps 8-way D-Pad to keyboard WASD movement."""
        # Map 4 primary switches: Up(W), Down(S), Left(A), Right(D)
        # When pressing diagonal directions on the physical D-pad thumbstick, both adjacent switches
        # actuate together (e.g. Up+Right emits W+D simultaneously in Linux evdev for fluid 8-way movement).
        wasd_map = {
            "n": "w",
            "e": "d",
            "s": "s",
            "w": "a",
            "ne": "",
            "se": "",
            "sw": "",
            "nw": "",
        }
        for dir_key, key_sym in wasd_map.items():
            kid = f"dpad-{dir_key}"
            if kid in self.state:
                self.state[kid]["output"] = key_sym
                self.state[kid]["target"] = "keyboard"

        if self.selected_key_id and self.selected_key_id.startswith("dpad-"):
            self.entry_output.set_text(self.state[self.selected_key_id]["output"])

        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="D-Pad Mapped to WASD",
            detail="D-Pad mapped to standard keyboard WASD movement:\n• Up = W\n• Down = S\n• Left = A\n• Right = D\n\nPhysical diagonal presses will actuate W+D, S+D, S+A, and W+A seamlessly."
        )
        alert.show(self)


    def _bind_dpad_to_left_stick(self, widget):
        ls_maps = get_left_stick_mappings()
        for dir_key, sym in ls_maps.items():
            kid = f"dpad-{dir_key}"
            if kid in self.state:
                self.state[kid]["output"] = sym
                self.state[kid]["target"] = "gamepad"
        if self.selected_key_id and self.selected_key_id.startswith("dpad-"):
            self.entry_output.set_text(self.state[self.selected_key_id]["output"])
        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="Mapped to Left Analog Stick (LS)",
            detail="All 8 D-pad directions mapped to Xbox 360 Left Analog Stick (ABS_X, ABS_Y) with smooth diagonal blending!"
        )
        alert.show(self)

    def _bind_dpad_to_right_stick(self, widget):
        rs_maps = get_right_stick_mappings()
        for dir_key, sym in rs_maps.items():
            kid = f"dpad-{dir_key}"
            if kid in self.state:
                self.state[kid]["output"] = sym
                self.state[kid]["target"] = "gamepad"
        if self.selected_key_id and self.selected_key_id.startswith("dpad-"):
            self.entry_output.set_text(self.state[self.selected_key_id]["output"])
        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="Mapped to Right Analog Stick (RS)",
            detail="All 8 D-pad directions mapped to Xbox 360 Right Analog Stick (ABS_RX, ABS_RY)!"
        )
        alert.show(self)

    def _bind_dpad_to_gamepad_hat(self, widget):
        dpad_maps = get_dpad_button_mappings()
        for dir_key, sym in dpad_maps.items():
            kid = f"dpad-{dir_key}"
            if kid in self.state:
                self.state[kid]["output"] = sym
                self.state[kid]["target"] = "gamepad"
        if self.selected_key_id and self.selected_key_id.startswith("dpad-"):
            self.entry_output.set_text(self.state[self.selected_key_id]["output"])
        self._update_all_visuals()
        alert = Gtk.AlertDialog(
            message="Mapped to Gamepad D-Pad Buttons",
            detail="All 8 D-pad directions mapped to standard gamepad D-pad buttons (BTN_DPAD_*)!"
        )
        alert.show(self)



def on_startup(app):
    apply_theme()


def on_activate(app):
    dev_name = getattr(app, "_device_override", None)
    win = KeypadMainWindow(app, device_override=dev_name)
    win.present()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Strop Keypad Remap Studio")
    parser.add_argument("--device", "-d", type=str, default=None, help="Target Razer Keypad model")
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

