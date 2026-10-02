#!/usr/bin/env python3
"""
Strop — Razer Tartarus Pro On-Screen Heads-Up Display (HUD) Overlay
Polychromatic Dark Slate & Emerald Color Scheme.
Lightweight, frameless, transparent floating overlay designed to stay on top of games.
Zero external dependencies - uses standard Python 3 and Ubuntu PyGObject (GTK4).

Features:
- Exact 1:1 physical layout (5 keypad rows, Scroll Up/Down, Thumb above, D-pad middle, 20 below)
- Polychromatic dark slate & neon emerald color palette
- Launches automatically in the upper-left corner
- Pinned always-on-top (stays above full-screen and windowed games)
- Draggable mini header so you can reposition it anywhere
- Live input-remapper preset switcher & auto-refresh
- Opacity cycle toggle (88%, 70%, 50%, 100%)
- Minimalist collapse / expand toggle
"""

import sys
import os
import json
from pathlib import Path

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from strop_core.x11 import pin_window_on_top
from strop_core.device import detect_device
from strop_core.presets import (
    get_device_presets_dir, list_device_presets,
    get_active_profile, load_preset_file,
    run_profile_operation_async, check_profile_state_async
)
from strop_core.gamepad import parse_gamepad_display_text, format_gamepad_button_output







# Prefer X11/XWayland for reliable always-on-top overlay stacking over games
if "GDK_BACKEND" not in os.environ:
    os.environ["GDK_BACKEND"] = "x11,wayland"

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio

from strop_core.layouts.keypad import (
    KEYPAD_GRID, SPACEBAR_DATA, THUMB_BTN_DATA, DPAD_DATA,
    SCROLL_UP_DATA, SCROLL_DOWN_DATA
)

GRID_DATA = KEYPAD_GRID


# ----------------------------------------------------------------------
# Polychromatic Dark Slate & Emerald CSS Theme
# ----------------------------------------------------------------------

CSS_STYLE = b"""
* {
    font-family: "Ubuntu", "Inter", "Cantarell", "DejaVu Sans", "Liberation Sans", "Noto Sans", sans-serif;
}

window.hud-window {
    background-color: rgba(18, 22, 29, 0.92);
    color: #e2e8f0;
    border-radius: 10px;
    border: 1px solid rgba(34, 197, 94, 0.45);
    box-shadow: 0 6px 24px rgba(0, 0, 0, 0.65);
}

.hud-container {
    padding: 6px 8px;
}

/* Minimalist Polychromatic Inline Header */
.hud-header {
    padding-bottom: 4px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 4px;
}

.drag-handle {
    color: #22c55e;
    font-weight: bold;
    font-size: 10.5px;
}

.hud-btn {
    background: rgba(26, 32, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    font-size: 9.5px;
    font-weight: 600;
    border-radius: 4px;
    padding: 1px 5px;
    min-height: 20px;
}

.hud-btn:hover {
    border-color: #22c55e;
    color: #86efac;
    background: rgba(32, 42, 54, 0.95);
}

dropdown button {
    background: rgba(26, 32, 42, 0.85);
    border: 1px solid rgba(34, 197, 94, 0.35);
    border-radius: 4px;
    color: #f8fafc;
    font-size: 10px;
    font-weight: 600;
    padding: 1px 6px;
    min-height: 20px;
}

/* Keypad Keys: Polychromatic Slate Tiles */
.key-cap {
    background: rgba(28, 34, 44, 0.90);
    border: 1px solid rgba(54, 66, 82, 0.85);
    border-radius: 4px;
    color: #94a3b8;
    padding: 1px 2px;
    min-width: 36px;
    min-height: 28px;
}

/* Remapped Keycap: Polychromatic Emerald Glow */
.key-cap.assigned {
    background: rgba(21, 38, 29, 0.95);
    border: 1px solid #22c55e;
    color: #86efac;
}

/* D-Pad Buttons */
.dpad-cap {
    background: rgba(28, 34, 44, 0.90);
    border: 1px solid rgba(54, 66, 82, 0.85);
    border-radius: 4px;
    color: #94a3b8;
    padding: 0;
    min-width: 24px;
    min-height: 24px;
}

.dpad-cap.assigned {
    background: rgba(21, 38, 29, 0.95);
    border: 1px solid #22c55e;
    color: #86efac;
}

.dpad-center-cap {
    background: rgba(16, 20, 26, 0.9);
    border: 1px solid rgba(40, 50, 64, 0.8);
    border-radius: 50%;
    color: #64748b;
    font-size: 6.5px;
    font-weight: 700;
}
"""


class KeypadHUDOverlay(Gtk.ApplicationWindow):
    def __init__(self, app, device_override=None):
        super().__init__(application=app, title="Strop — Keypad HUD Overlay")
        self.add_css_class("hud-window")
        
        # Completely remove system titlebar for clean, unobtrusive glass overlay
        self.set_decorated(False)
        self.set_default_size(320, 210)
        self.set_resizable(False)

        # State storage
        self.state = {}
        self.button_widgets = {}
        self.available_presets = []
        self.current_preset_name = ""
        self.profile_operation_pending = False
        self.opacity_levels = [0.88, 0.70, 0.50, 1.0]
        self.opacity_idx = 0
        self.is_collapsed = False
        if device_override:
            if isinstance(device_override, dict):
                self.detected_device = device_override
            else:
                self.detected_device = detect_device(device_override, default_name=device_override)
        else:
            self.detected_device = detect_device("tartarus", default_name="Razer Tartarus Pro")

        # Initialize State Definitions
        self._init_state()

        # Build HUD UI
        self._build_ui()

        # Scan and load presets from input-remapper directory
        self._scan_and_load_presets()


        # Schedule always-on-top & upper-left pin right after display mapping
        GLib.timeout_add(150, self._apply_on_top_and_position)

    def _apply_on_top_and_position(self):
        pin_window_on_top("Strop — Keypad HUD Overlay", x=12, y=12)
        return False  # Run once



    def _init_state(self):
        for r, row in enumerate(GRID_DATA):
            for c, item in enumerate(row):
                kid = f"grid-{r}-{c}"
                self.state[kid] = {
                    "name": item["name"],
                    "label": item["l"],
                    "code": item["c"],
                    "aliases": item.get("aliases", []),
                    "output": ""
                }

        self.state["spacebar"] = {
            "name": SPACEBAR_DATA["name"],
            "label": SPACEBAR_DATA["l"],
            "code": SPACEBAR_DATA["c"],
            "aliases": SPACEBAR_DATA.get("aliases", []),
            "output": ""
        }

        self.state["thumb"] = {
            "name": THUMB_BTN_DATA["name"],
            "label": THUMB_BTN_DATA["l"],
            "code": THUMB_BTN_DATA["c"],
            "aliases": THUMB_BTN_DATA.get("aliases", []),
            "output": ""
        }

        for dir_key, item in DPAD_DATA.items():
            kid = f"dpad-{dir_key}"
            self.state[kid] = {
                "name": item["name"],
                "label": item["l"],
                "code": item["c"],
                "aliases": item.get("aliases", []),
                "output": ""
            }

        self.state["scrollUp"] = {
            "name": SCROLL_UP_DATA["name"],
            "label": SCROLL_UP_DATA["l"],
            "code": SCROLL_UP_DATA["c"],
            "aliases": SCROLL_UP_DATA.get("aliases", []),
            "output": ""
        }

        self.state["scrollDown"] = {
            "name": SCROLL_DOWN_DATA["name"],
            "label": SCROLL_DOWN_DATA["l"],
            "code": SCROLL_DOWN_DATA["c"],
            "aliases": SCROLL_DOWN_DATA.get("aliases", []),
            "output": ""
        }

    def _build_ui(self):
        self.main_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.main_container.add_css_class("hud-container")
        self.set_child(self.main_container)

        # -------------------------------------------------------------
        # 1. Minimalist Integrated Header (No System Titlebar)
        # -------------------------------------------------------------
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        header.add_css_class("hud-header")
        header.set_cursor_from_name("grab")

        lbl_drag = Gtk.Label(label="⋮⋮ HUD")
        lbl_drag.add_css_class("drag-handle")
        lbl_drag.set_cursor_from_name("grab")
        header.append(lbl_drag)

        # Preset Dropdown Switcher
        self.preset_dropdown = Gtk.DropDown.new_from_strings(["No Presets Found"])
        self.preset_dropdown_handler_id = self.preset_dropdown.connect("notify::selected-item", self._on_preset_selected)
        self.preset_dropdown.set_hexpand(True)
        header.append(self.preset_dropdown)

        self.lbl_profile_status = Gtk.Label(label="Injection state unknown")
        self.lbl_profile_status.add_css_class("dim-text")
        header.append(self.lbl_profile_status)

        self.btn_profile_apply = Gtk.Button(label="⚡")
        self.btn_profile_apply.add_css_class("hud-btn")
        self.btn_profile_apply.set_tooltip_text("Apply the selected profile")
        self.btn_profile_apply.connect("clicked", self._on_apply_clicked)
        header.append(self.btn_profile_apply)

        self.btn_profile_stop = Gtk.Button(label="■")
        self.btn_profile_stop.add_css_class("hud-btn")
        self.btn_profile_stop.set_tooltip_text("Stop injection for this device")
        self.btn_profile_stop.connect("clicked", self._on_stop_clicked)
        header.append(self.btn_profile_stop)


        # Opacity Cycle Button
        self.btn_opacity = Gtk.Button(label="88%")
        self.btn_opacity.add_css_class("hud-btn")
        self.btn_opacity.set_tooltip_text("Cycle Transparency")
        self.btn_opacity.connect("clicked", self._cycle_opacity)
        header.append(self.btn_opacity)

        # Refresh Presets Button
        btn_refresh = Gtk.Button(label="⟳")
        btn_refresh.add_css_class("hud-btn")
        btn_refresh.set_tooltip_text("Reload Presets")
        btn_refresh.connect("clicked", lambda w: self._scan_and_load_presets())
        header.append(btn_refresh)

        # Collapse / Expand Button
        self.btn_collapse = Gtk.Button(label="▲")
        self.btn_collapse.add_css_class("hud-btn")
        self.btn_collapse.set_tooltip_text("Collapse/Expand Grid")
        self.btn_collapse.connect("clicked", self._toggle_collapse)
        header.append(self.btn_collapse)

        # Minimal Close Button
        btn_close = Gtk.Button(label="✕")
        btn_close.add_css_class("hud-btn")
        btn_close.set_tooltip_text("Close HUD")
        btn_close.connect("clicked", lambda w: self.close())
        header.append(btn_close)

        # Enable dragging the window via the ultra-slim toolbar
        self.drag_gesture = Gtk.GestureDrag.new()
        self.drag_gesture.connect("drag-begin", self._on_toolbar_drag_begin)
        header.add_controller(self.drag_gesture)

        self.main_container.append(header)

        # -------------------------------------------------------------
        # 2. Compact Visual Keypad Grid (Mirroring Physical Layout)
        # -------------------------------------------------------------
        self.body_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.body_box.set_halign(Gtk.Align.CENTER)
        self.main_container.append(self.body_box)

        # Left Column: Keypad Grid (Keys 01-19, Scroll Up in row 3 col 4, Scroll Down in row 4 col 4)
        grid = Gtk.Grid()
        grid.set_row_spacing(2)
        grid.set_column_spacing(2)

        for r, row in enumerate(GRID_DATA):
            for c, item in enumerate(row):
                kid = f"grid-{r}-{c}"
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                box.add_css_class("key-cap")

                lbl = Gtk.Label()
                lbl.set_markup(f"<span weight='bold' size='8500'>{item['l']}</span>")
                lbl.set_justify(Gtk.Justification.CENTER)
                box.append(lbl)

                self.button_widgets[kid] = {"box": box, "lbl": lbl, "raw_label": item["l"]}
                grid.attach(box, c, r, 1, 1)

        # Scroll Up in Row 3, Column 4 (under Key 15, to the right of Key 19)
        sup_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sup_box.add_css_class("key-cap")
        sup_lbl = Gtk.Label()
        sup_lbl.set_markup("<span weight='bold' size='7500'>Scr↑</span>")
        sup_box.append(sup_lbl)
        self.button_widgets["scrollUp"] = {"box": sup_box, "lbl": sup_lbl, "raw_label": "Scr↑"}
        grid.attach(sup_box, 4, 3, 1, 1)

        # Scroll Down in Row 4, Column 4 (under Scroll Up)
        sdn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sdn_box.add_css_class("key-cap")
        sdn_lbl = Gtk.Label()
        sdn_lbl.set_markup("<span weight='bold' size='7500'>Scr↓</span>")
        sdn_box.append(sdn_lbl)
        self.button_widgets["scrollDown"] = {"box": sdn_box, "lbl": sdn_lbl, "raw_label": "Scr↓"}
        grid.attach(sdn_box, 4, 4, 1, 1)

        self.body_box.append(grid)

        # Right Column: Thumb Module (Thumb Button Top -> 8-Way D-pad Middle -> Key 20 Spacebar Bottom)
        thumb_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        thumb_col.set_halign(Gtk.Align.CENTER)

        # 1. Thumb Button (Top above D-pad)
        thumb_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        thumb_box.add_css_class("key-cap")
        thumb_box.set_size_request(82, 18)
        thumb_lbl = Gtk.Label()
        thumb_lbl.set_markup("<span weight='bold' size='7500'>Thumb</span>")
        thumb_box.append(thumb_lbl)
        self.button_widgets["thumb"] = {"box": thumb_box, "lbl": thumb_lbl, "raw_label": "Thumb"}
        thumb_col.append(thumb_box)

        # 2. 8-Way D-Pad (Middle)
        dpad_grid = Gtk.Grid()
        dpad_grid.set_row_spacing(2)
        dpad_grid.set_column_spacing(2)
        dpad_grid.set_halign(Gtk.Align.CENTER)

        dpad_positions = {
            "nw": (0, 0), "n": (1, 0), "ne": (2, 0),
            "w":  (0, 1),              "e":  (2, 1),
            "sw": (0, 2), "s": (1, 2), "se": (2, 2)
        }

        for dir_key, (col, row) in dpad_positions.items():
            kid = f"dpad-{dir_key}"
            dinfo = DPAD_DATA[dir_key]
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            box.add_css_class("dpad-cap")

            lbl = Gtk.Label()
            lbl.set_markup(f"<span weight='bold' size='8000'>{dinfo['l']}</span>")
            box.append(lbl)
            self.button_widgets[kid] = {"box": box, "lbl": lbl, "raw_label": dinfo["l"]}
            dpad_grid.attach(box, col, row, 1, 1)

        center_lbl = Gtk.Label(label="8W")
        center_lbl.add_css_class("dpad-center-cap")
        center_lbl.set_size_request(24, 24)
        dpad_grid.attach(center_lbl, 1, 1, 1, 1)

        thumb_col.append(dpad_grid)

        # 3. Key 20 Spacebar (Bottom under D-pad)
        space_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        space_box.add_css_class("key-cap")
        space_box.set_size_request(82, 18)
        space_lbl = Gtk.Label()
        space_lbl.set_markup("<span weight='bold' size='8500'>20</span>")
        space_box.append(space_lbl)
        self.button_widgets["spacebar"] = {"box": space_box, "lbl": space_lbl, "raw_label": "20"}
        thumb_col.append(space_box)

        self.body_box.append(thumb_col)

    def _cycle_opacity(self, widget):
        self.opacity_idx = (self.opacity_idx + 1) % len(self.opacity_levels)
        opacity = self.opacity_levels[self.opacity_idx]
        self.set_opacity(opacity)
        self.btn_opacity.set_label(f"{int(opacity * 100)}%")

    def _toggle_collapse(self, widget):
        self.is_collapsed = not self.is_collapsed
        self.body_box.set_visible(not self.is_collapsed)
        self.btn_collapse.set_label("▼" if self.is_collapsed else "▲")

    def _on_toolbar_drag_begin(self, gesture, start_x, start_y):
        surface = self.get_surface()
        if surface and isinstance(surface, Gdk.Toplevel):
            device = gesture.get_device()
            surface.begin_move(device, 1, int(start_x), int(start_y), Gdk.CURRENT_TIME)

    def _format_display_text(self, output_str):
        trimmed = (output_str or "").strip()
        if not trimmed:
            return ""
        gp_text = parse_gamepad_display_text(trimmed)
        if gp_text:
            return gp_text
        if trimmed.lower() == "disable":
            return "off"
        if any(c in trimmed for c in ("+", "(", ")", ",", '"', "'", ";", ".")):
            return "macro"
        if "macro" in trimmed.lower() or "\n" in trimmed:
            return "macro"
        return trimmed


    def _match_preset_key(self, code, name, combination=None):
        if combination and len(combination) > 1:
            preset_codes = sorted(item.get("code") for item in combination)
            for direction, data in DPAD_DATA.items():
                if sorted(data.get("combo", [])) == preset_codes:
                    return f"dpad-{direction}"
        if code is not None:
            for kid, s in self.state.items():
                if s.get("code") == code:
                    return kid
        if name:
            clean_name = str(name).strip().lower().replace("_", " ").replace("-", " ")
            for kid, s in self.state.items():
                if s.get("name", "").lower() == clean_name or s.get("label", "").lower() == clean_name:
                    return kid
                for a in s.get("aliases", []):
                    if a.lower() == clean_name:
                        return kid
        return None

    def _scan_and_load_presets(self):
        dev_name = self.detected_device.get("name", "Razer Tartarus Pro") if hasattr(self, "detected_device") and self.detected_device else "Razer Tartarus Pro"
        self.lbl_profile_status.set_text("Checking injection…")
        check_profile_state_async(
            dev_name,
            lambda state, target=dev_name: self._on_profile_state_checked(target, state),
            GLib.idle_add,
        )
        preset_names = list_device_presets(dev_name)
        if not preset_names:
            self.available_presets = []
            return

        self.available_presets = preset_names

        # Temporarily disconnect / block signal during programmatic model updates
        if hasattr(self, "preset_dropdown_handler_id") and self.preset_dropdown_handler_id:
            self.preset_dropdown.handler_block(self.preset_dropdown_handler_id)

        new_model = Gtk.StringList.new(preset_names)
        self.preset_dropdown.set_model(new_model)

        active_prof = get_active_profile(dev_name)
        active_idx = 0
        if active_prof and active_prof in preset_names:
            active_idx = preset_names.index(active_prof)

        self.preset_dropdown.set_selected(active_idx)

        if hasattr(self, "preset_dropdown_handler_id") and self.preset_dropdown_handler_id:
            self.preset_dropdown.handler_unblock(self.preset_dropdown_handler_id)

        self.current_preset_name = preset_names[active_idx]
        self._load_preset_file(preset_names[active_idx])
        if active_prof:
            self.lbl_profile_status.set_text(f"Last Strop profile: {active_prof} · state checking")

    def _on_preset_selected(self, dropdown, param):
        selected_idx = dropdown.get_selected()
        if selected_idx < len(self.available_presets):
            preset_name = self.available_presets[selected_idx]
            dev_name = self.detected_device.get("name", "Razer Tartarus Pro") if hasattr(self, "detected_device") and self.detected_device else "Razer Tartarus Pro"
            self.current_preset_name = preset_name
            self._load_preset_file(preset_name)
            self.lbl_profile_status.set_text(f"Selected: {preset_name} · not applied")

    def _on_profile_state_checked(self, device_name: str, state: str):
        current_device = self.detected_device.get("name", "Razer Tartarus Pro")
        if device_name != current_device:
            return
        last_profile = get_active_profile(device_name)
        state_text = {
            "running": "Injection running", "starting": "Injection starting",
            "stopped": "Injection stopped", "failed": "Injection failed",
        }.get(state, "Injection state unknown")
        if last_profile:
            state_text += f" · Last Strop: {last_profile}"
        self.lbl_profile_status.set_text(state_text)

    def _set_profile_controls_busy(self, busy: bool):
        self.profile_operation_pending = busy
        self.btn_profile_apply.set_sensitive(not busy)
        self.btn_profile_stop.set_sensitive(not busy)

    def _on_apply_clicked(self, widget):
        if self.profile_operation_pending or not self.current_preset_name:
            return
        device_name = self.detected_device.get("name", "Razer Tartarus Pro")
        preset_name = self.current_preset_name
        self._set_profile_controls_busy(True)
        self.lbl_profile_status.set_text(f"Applying {preset_name}…")
        run_profile_operation_async(
            "apply", device_name,
            lambda result: self._on_profile_operation_finished("apply", device_name, preset_name, result),
            GLib.idle_add, preset_name=preset_name,
        )

    def _on_stop_clicked(self, widget):
        if self.profile_operation_pending:
            return
        device_name = self.detected_device.get("name", "Razer Tartarus Pro")
        self._set_profile_controls_busy(True)
        self.lbl_profile_status.set_text("Stopping injection…")
        run_profile_operation_async(
            "stop", device_name,
            lambda result: self._on_profile_operation_finished("stop", device_name, "", result),
            GLib.idle_add,
        )

    def _on_profile_operation_finished(self, operation: str, device_name: str, preset_name: str, result):
        self._set_profile_controls_busy(False)
        self.lbl_profile_status.set_text(result.message)
        if not result.success:
            print(f"[HUD] {operation.title()} profile: {result.message}")


    def _load_preset_file(self, preset_spec):
        try:
            dev_name = self.detected_device.get("name", "Razer Tartarus Pro") if hasattr(self, "detected_device") and self.detected_device else "Razer Tartarus Pro"
            if isinstance(preset_spec, (str, Path)):
                p = Path(preset_spec)
                if not p.exists() or not p.is_file():
                    # Resolve from device preset directory
                    dev_dir = get_device_presets_dir(dev_name)
                    p = dev_dir / f"{str(preset_spec).replace('.json', '')}.json"
                if not p.exists():
                    return
            else:
                return


            data = load_preset_file(p)
            if data is None:
                self.lbl_profile_status.set_text(f"Could not read preset: {p.name}")
                return

            for s in self.state.values():
                s["output"] = ""
                s["custom_name"] = ""

            for item in data:
                if not isinstance(item, dict):
                    continue
                input_comb = item["input_combination"]
                code = input_comb[0]["code"]
                out_sym = item.get("output_symbol", "")
                name = item.get("name", "")
                custom_name = item.get("custom_name") or ""
                if not out_sym:
                    out_sym = format_gamepad_button_output(item.get("output_type"), item.get("output_code")) or ""

                matched_key = self._match_preset_key(code, name, input_comb)
                if matched_key:
                    self.state[matched_key]["output"] = out_sym
                    self.state[matched_key]["custom_name"] = custom_name

            self._update_all_visuals()

        except Exception as e:
            print(f"Error loading overlay preset {preset_spec}: {e}")


    def _update_all_visuals(self):
        for kid, s in self.state.items():
            if kid not in self.button_widgets:
                continue
            w_info = self.button_widgets[kid]
            box = w_info["box"]
            lbl = w_info["lbl"]
            raw_label = w_info["raw_label"]

            has_output = bool(s["output"] and s["output"].strip())
            custom_name = s.get("custom_name", "").strip()
            if has_output or custom_name:
                box.add_css_class("assigned")
                disp = custom_name if custom_name else self._format_display_text(s["output"])
                lbl.set_markup(f"<span weight='bold' size='8000'>{raw_label}</span>\n<span size='6500' weight='bold' color='#86efac'>{GLib.markup_escape_text(disp)}</span>")
            else:
                box.remove_css_class("assigned")
                lbl.set_markup(f"<span weight='bold' size='8000'>{raw_label}</span>")



from strop_core.theme import apply_theme
def on_startup(app):
    apply_theme(CSS_STYLE)


def on_activate(app):
    dev_name = getattr(app, "_device_override", None)
    win = KeypadHUDOverlay(app, device_override=dev_name)
    win.present()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Strop Keypad HUD Overlay")
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
