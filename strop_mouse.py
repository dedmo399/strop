#!/usr/bin/env python3
"""
Strop — Razer Mouse Remap Studio (Native Linux GTK4 GUI)
Modular mouse editor with generic layout archetypes for:
- Naga Series Interchangeable Side Plates (2-Button FPS, 7-Button Hex, and 12-Button MMO)
- Basilisk / DeathAdder / Viper / Cobra / Mamba FPS ergonomics
- Ambidextrous dual side button configurations
- Hardware DPI, 5-Stage Presets, and Polling Rate Control via OpenRazer
Powered by BaseStudioWindow.
"""

import sys
import os
from pathlib import Path
from typing import List, Optional, Tuple

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from strop_core.device import (
    SIDE_PLATE_AMBI,
    SIDE_PLATE_FPS_2,
    SIDE_PLATE_HEX_7,
    SIDE_PLATE_METADATA,
    SIDE_PLATE_MMO_12,
    apply_side_plate_to_device_info,
    detect_device,
    detect_mouse_side_plate,
    detect_side_plate_from_preset_entries,
    detect_side_plate_from_state,
    scan_all_connected_devices,
    side_plate_for_archetype,
)
from strop_core.dpi import (
    DEFAULT_DPI_STAGES,
    MouseSensorCapabilities,
    MouseSensorSettings,
    clamp_dpi_value,
    get_dpi_engine,
    load_mouse_settings,
    save_mouse_settings,
)
from strop_core.presets import load_preset_file
from strop_core.theme import apply_theme
from strop_core.studio_base import BaseStudioWindow
from strop_core.catalog import (
    get_archetype_for_device,
    is_multi_plate_mouse,
    MOUSE_NAGA_MMO,
    MOUSE_NAGA_HEX,
    MOUSE_BASILISK_FPS,
    MOUSE_FPS,
    MOUSE_AMBI,
)

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, GLib, Gio

from strop_core.layouts.mouse import (
    COMMON_MOUSE_BUTTONS, NAGA_12_GRID, NAGA_HEX_7_GRID, FPS_SIDE_BUTTONS, AMBI_RIGHT_BUTTONS
)


class RazerMouseStudioWindow(BaseStudioWindow):
    """Refactored Universal Mouse Studio Window with OpenRazer DPI & Sensor Control."""
    def __init__(self, app, device_override=None):
        self.device_override = device_override
        self._updating_dpi_controls = False
        self._switching_side_plate_programmatically = False
        self.stage_buttons: List[Gtk.Button] = []
        self.lbl_sensor_badge: Optional[Gtk.Label] = None
        self.lbl_side_plate_badge: Optional[Gtk.Label] = None
        self.side_stack: Optional[Gtk.Notebook] = None
        self.side_plate_pages = {}
        self.active_side_plate: str = SIDE_PLATE_FPS_2
        super().__init__(app, title="Strop — Mouse Studio", default_width=1020, default_height=680)
        # Ensure GUI focuses on the detected / active side plate when opened
        self._focus_detected_side_plate(focus_widget=True)

    def _init_device(self):
        if self.device_override:
            if isinstance(self.device_override, dict):
                self.detected_device = apply_side_plate_to_device_info(dict(self.device_override))
            else:
                self.detected_device = detect_device(self.device_override, default_name=self.device_override)
        else:
            self.detected_device = self._auto_detect_mouse()

        self.default_device_name = self.detected_device.get("name", "Razer Naga Pro")
        self.default_preset_name = "my-mouse-preset"
        self.archetype = self.detected_device.get("archetype") or get_archetype_for_device(self.default_device_name)
        self.active_side_plate = (
            self.detected_device.get("side_plate")
            or side_plate_for_archetype(self.archetype)
        )
        self._init_sensor_state()

    def _init_sensor_state(self):
        self._updating_dpi_controls = False
        self.stage_buttons = []
        self.lbl_sensor_badge = None
        pid = self.detected_device.get("product")
        engine = get_dpi_engine()
        self.sensor_caps: MouseSensorCapabilities = engine.discover_capabilities(
            self.default_device_name, pid=pid
        )
        self.sensor_settings: MouseSensorSettings = load_mouse_settings(
            self.default_device_name, self.sensor_caps
        )

    def _auto_detect_mouse(self):
        all_devs = scan_all_connected_devices()
        mice = [
            d for d in all_devs
            if str(d.get("archetype") or "").startswith("MOUSE_") or d.get("multi_plate")
        ]
        for m in mice:
            if m.get("multi_plate"):
                return m
        if mice:
            return mice[0]
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
        for item in AMBI_RIGHT_BUTTONS:
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

        # Top Section Header with Live Sensor Status Badge
        top_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_top = Gtk.Label()
        lbl_top.set_markup("<span weight='bold' size='small' color='#94a3b8'>Primary Mouse Controls &amp; Scroll Wheel</span>")
        lbl_top.set_xalign(0)
        lbl_top.set_hexpand(True)
        top_header.append(lbl_top)

        self.lbl_sensor_badge = Gtk.Label()
        self.lbl_sensor_badge.add_css_class("badge-sensor")
        self._update_sensor_badge()
        top_header.append(self.lbl_sensor_badge)

        canvas.append(top_header)

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

        # Modular Side Plates Header + Active Side Plate Indicator & Rescan Button
        side_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        side_header.set_margin_top(8)

        lbl_side = Gtk.Label()
        lbl_side.set_markup("<span weight='bold' size='small' color='#94a3b8'>Interchangeable Side Plates &amp; Thumb Clusters</span>")
        lbl_side.set_xalign(0)
        lbl_side.set_hexpand(True)
        side_header.append(lbl_side)

        self.lbl_side_plate_badge = Gtk.Label()
        self.lbl_side_plate_badge.add_css_class("badge-device")
        side_header.append(self.lbl_side_plate_badge)

        self.btn_rescan_plate = Gtk.Button(label="⟳ Rescan Plate")
        self.btn_rescan_plate.add_css_class("ghost-btn")
        self.btn_rescan_plate.set_tooltip_text("Rescan connected mouse and focus the currently attached side plate")
        self.btn_rescan_plate.connect("clicked", self._on_rescan_plate_clicked)
        side_header.append(self.btn_rescan_plate)

        canvas.append(side_header)

        side_stack = Gtk.Notebook()
        side_stack.set_vexpand(False)
        self.side_stack = side_stack

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

        # Plate 4: Ambidextrous Right-Side Buttons
        ambi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ambi_box.set_margin_top(8)
        ambi_box.set_halign(Gtk.Align.CENTER)

        for item in AMBI_RIGHT_BUTTONS:
            btn = self._create_mouse_button_widget(item, width=130, height=48)
            ambi_box.append(btn)
        side_stack.append_page(ambi_box, Gtk.Label(label="Ambidextrous Right Side Buttons"))

        self.side_plate_pages = {
            0: fps_box,
            1: hex_box,
            2: naga_box,
            3: ambi_box,
        }
        side_stack.connect("switch-page", self._on_side_plate_tab_switched)

        # Auto-switch tab based on detected side plate / archetype
        self._focus_detected_side_plate(self.active_side_plate, focus_widget=False)

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

    # ------------------------------------------------------------------
    # Side Plate Detection, Focus & Rescan
    # ------------------------------------------------------------------
    def _plate_id_for_page(self, page_num: int) -> str:
        for pid, meta in SIDE_PLATE_METADATA.items():
            if meta.get("page") == page_num:
                return pid
        return SIDE_PLATE_FPS_2

    def _update_side_plate_badge(self):
        if self.lbl_side_plate_badge is None:
            return
        meta = SIDE_PLATE_METADATA.get(self.active_side_plate, SIDE_PLATE_METADATA[SIDE_PLATE_FPS_2])
        multi = bool(
            self.detected_device.get("multi_plate")
            or is_multi_plate_mouse(
                self.detected_device.get("name", self.default_device_name),
                pid=self.detected_device.get("product"),
            )
        )
        prefix = "Attached Plate:" if multi else "Side Layout:"
        short_lbl = meta.get("short_label", meta["label"])
        self.lbl_side_plate_badge.set_markup(
            f"🧩 <b>{GLib.markup_escape_text(prefix)}</b> {GLib.markup_escape_text(short_lbl)}"
        )
        self.lbl_side_plate_badge.set_tooltip_text(
            f"Active Side Plate: {meta['label']}\n"
            f"Device: {self.detected_device.get('name', self.default_device_name)}\n"
            f"Archetype: {meta['archetype']}"
        )

    def _focus_detected_side_plate(self, plate_id: Optional[str] = None, focus_widget: bool = True) -> str:
        resolved_plate = plate_id if (plate_id and plate_id in SIDE_PLATE_METADATA) else None
        if not resolved_plate:
            resolved_plate = detect_side_plate_from_state(getattr(self, "state", {}))
        if not resolved_plate:
            resolved_plate = self.detected_device.get("side_plate")
        if not resolved_plate or resolved_plate not in SIDE_PLATE_METADATA:
            resolved_plate = side_plate_for_archetype(getattr(self, "archetype", None))

        meta = SIDE_PLATE_METADATA.get(resolved_plate, SIDE_PLATE_METADATA[SIDE_PLATE_FPS_2])
        self.active_side_plate = meta["id"]
        self.detected_device["side_plate"] = meta["id"]
        self.detected_device["side_plate_label"] = meta["label"]
        self.detected_device["side_plate_page"] = meta["page"]
        if self.detected_device.get("multi_plate") or is_multi_plate_mouse(
            self.detected_device.get("name", getattr(self, "default_device_name", "")),
            pid=self.detected_device.get("product"),
        ):
            self.archetype = meta["archetype"]
            self.detected_device["archetype"] = meta["archetype"]

        if getattr(self, "side_stack", None) is not None:
            self._switching_side_plate_programmatically = True
            try:
                self.side_stack.set_current_page(meta["page"])
            finally:
                self._switching_side_plate_programmatically = False

            if focus_widget:
                page_widget = getattr(self, "side_plate_pages", {}).get(meta["page"])
                if page_widget is not None and hasattr(page_widget, "grab_focus"):
                    page_widget.grab_focus()
                if hasattr(self.side_stack, "grab_focus"):
                    self.side_stack.grab_focus()

        self._update_side_plate_badge()
        return meta["id"]

    def _on_side_plate_tab_switched(self, _notebook, _page, page_num: int):
        if getattr(self, "_switching_side_plate_programmatically", False):
            return
        plate_id = self._plate_id_for_page(int(page_num))
        meta = SIDE_PLATE_METADATA.get(plate_id, SIDE_PLATE_METADATA[SIDE_PLATE_FPS_2])
        self.active_side_plate = meta["id"]
        self.detected_device["side_plate"] = meta["id"]
        self.detected_device["side_plate_label"] = meta["label"]
        self.detected_device["side_plate_page"] = meta["page"]
        if self.detected_device.get("multi_plate"):
            self.archetype = meta["archetype"]
            self.detected_device["archetype"] = meta["archetype"]
        self._update_side_plate_badge()

    def _on_rescan_plate_clicked(self, _widget):
        self.rescan_device_and_side_plate(show_toast=True)

    def rescan_device_and_side_plate(self, show_toast: bool = True) -> str:
        """Rescans connected mouse hardware and focuses the detected side plate in the GUI."""
        if isinstance(self.device_override, str) and self.device_override.strip():
            rescanned = detect_device(self.device_override, default_name=self.device_override)
        elif isinstance(self.device_override, dict):
            target_name = self.device_override.get("name") or self.default_device_name
            rescanned = detect_device(target_name, default_name=target_name)
        else:
            rescanned = self._auto_detect_mouse()

        self.detected_device = rescanned
        self.default_device_name = rescanned.get("name", self.default_device_name)
        self.archetype = rescanned.get("archetype") or get_archetype_for_device(self.default_device_name)

        detected_plate = (
            rescanned.get("side_plate")
            or detect_side_plate_from_state(getattr(self, "state", {}))
            or side_plate_for_archetype(self.archetype)
        )
        focused_plate = self._focus_detected_side_plate(detected_plate, focus_widget=True)
        meta = SIDE_PLATE_METADATA.get(focused_plate, SIDE_PLATE_METADATA[SIDE_PLATE_FPS_2])
        if show_toast and hasattr(self, "toast"):
            self.toast.show_message(
                f"Focused {meta['label']} on {self.default_device_name}",
                icon="🧩",
            )
        return focused_plate

    def _match_preset_key(self, code, name, origin_hash=None, combination=None):
        matched = super()._match_preset_key(code, name, origin_hash, combination)
        if matched is not None:
            return matched
        if code is not None and 2 <= code <= 8:
            # Disambiguate scancodes 2..8 between 7-Button Hex plate and 12-Button MMO plate
            if getattr(self, "active_side_plate", None) == SIDE_PLATE_HEX_7 or getattr(self, "archetype", None) == MOUSE_NAGA_HEX:
                candidate = f"naga_hex_{code - 1}"
            else:
                candidate = f"naga_{code - 1}"
            if candidate in self.state:
                return candidate
        return None

    def _load_preset_file_data(self, load_path: str) -> Tuple[int, int]:
        preset_entries = load_preset_file(Path(load_path))
        plate_from_preset = detect_side_plate_from_preset_entries(preset_entries)
        if plate_from_preset and plate_from_preset in SIDE_PLATE_METADATA:
            meta = SIDE_PLATE_METADATA[plate_from_preset]
            self.active_side_plate = meta["id"]
            if self.detected_device.get("multi_plate") or is_multi_plate_mouse(
                self.detected_device.get("name", self.default_device_name),
                pid=self.detected_device.get("product"),
            ):
                self.archetype = meta["archetype"]
        matched_count, total_count = super()._load_preset_file_data(load_path)
        target_plate = (
            plate_from_preset
            or detect_side_plate_from_state(self.state)
            or self.detected_device.get("side_plate")
        )
        self._focus_detected_side_plate(target_plate, focus_widget=True)
        return matched_count, total_count

    # ------------------------------------------------------------------
    # Hardware DPI, Stages & Polling Rate Controls
    # ------------------------------------------------------------------
    def _build_custom_special_actions_pages(self) -> List[Tuple[str, Gtk.Widget]]:
        return [("🎯 DPI & Sensor", self._build_dpi_sensor_page())]

    def _build_dpi_sensor_page(self) -> Gtk.Widget:
        if not hasattr(self, "sensor_caps") or not hasattr(self, "sensor_settings"):
            self._init_sensor_state()

        dpi_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        dpi_box.set_margin_top(6)
        dpi_box.set_margin_start(4)
        dpi_box.set_margin_end(4)

        # Row 1: 5 Customizable DPI Stage Buttons + Save / Reset Stage
        stages_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_stages = Gtk.Label()
        lbl_stages.set_markup("<span size='small' weight='bold' color='#86efac'>Stages:</span>")
        lbl_stages.set_xalign(0)
        stages_row.append(lbl_stages)

        self.stage_buttons = []
        for idx in range(1, 6):
            btn = Gtk.Button()
            btn.add_css_class("dpi-stage-btn")
            btn.set_hexpand(True)
            btn.connect("clicked", self._on_dpi_stage_clicked, idx)
            self.stage_buttons.append(btn)
            stages_row.append(btn)

        btn_save_stage = Gtk.Button(label="💾 Save Stage")
        btn_save_stage.add_css_class("ghost-btn")
        btn_save_stage.set_tooltip_text("Save current X/Y DPI values into the selected stage slot")
        btn_save_stage.connect("clicked", self._on_save_stage_clicked)
        stages_row.append(btn_save_stage)

        btn_reset_stages = Gtk.Button(label="↺")
        btn_reset_stages.add_css_class("ghost-btn")
        btn_reset_stages.set_tooltip_text("Reset all 5 DPI stages to factory defaults")
        btn_reset_stages.connect("clicked", self._on_reset_stages_clicked)
        stages_row.append(btn_reset_stages)

        dpi_box.append(stages_row)

        # Row 2: Fine-Grained X / Y DPI Slider & SpinButtons
        xy_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        min_dpi = self.sensor_caps.min_dpi
        max_dpi = self.sensor_caps.max_dpi

        self.dpi_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_dpi, max_dpi, 50)
        self.dpi_scale.set_draw_value(False)
        self.dpi_scale.set_hexpand(True)
        self.dpi_scale.set_value(self.sensor_settings.dpi_x)
        self.dpi_scale.set_tooltip_text(f"Adjust DPI ({min_dpi} – {max_dpi})")
        self.dpi_scale.connect("value-changed", self._on_dpi_scale_changed)
        xy_row.append(self.dpi_scale)

        lbl_x = Gtk.Label(label="X:")
        lbl_x.add_css_class("dim-label")
        xy_row.append(lbl_x)

        self.spin_dpi_x = Gtk.SpinButton.new_with_range(min_dpi, max_dpi, 50)
        self.spin_dpi_x.set_value(self.sensor_settings.dpi_x)
        self.spin_dpi_x.set_tooltip_text("Horizontal (X) DPI sensitivity")
        self.spin_dpi_x.connect("value-changed", self._on_spin_dpi_x_changed)
        xy_row.append(self.spin_dpi_x)

        lbl_y = Gtk.Label(label="Y:")
        lbl_y.add_css_class("dim-label")
        xy_row.append(lbl_y)

        self.spin_dpi_y = Gtk.SpinButton.new_with_range(min_dpi, max_dpi, 50)
        self.spin_dpi_y.set_value(self.sensor_settings.dpi_y)
        self.spin_dpi_y.set_tooltip_text("Vertical (Y) DPI sensitivity")
        self.spin_dpi_y.connect("value-changed", self._on_spin_dpi_y_changed)
        xy_row.append(self.spin_dpi_y)

        self.chk_link_xy = Gtk.CheckButton(label="Lock X=Y")
        self.chk_link_xy.set_active(self.sensor_settings.linked_xy)
        self.chk_link_xy.set_tooltip_text("Keep horizontal (X) and vertical (Y) DPI identical")
        self.chk_link_xy.connect("toggled", self._on_link_xy_toggled)
        xy_row.append(self.chk_link_xy)

        dpi_box.append(xy_row)

        # Row 3: Polling Rate Selector, Status Label, Read Hardware, and Apply Button
        ctrl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        lbl_poll = Gtk.Label(label="Polling:")
        lbl_poll.add_css_class("dim-label")
        ctrl_row.append(lbl_poll)

        self.poll_rates_list = list(self.sensor_caps.supported_poll_rates or [125, 500, 1000])
        poll_labels = [f"{r} Hz" for r in self.poll_rates_list]
        self.dropdown_poll_rate = Gtk.DropDown.new_from_strings(poll_labels)
        if self.sensor_settings.poll_rate in self.poll_rates_list:
            self.dropdown_poll_rate.set_selected(self.poll_rates_list.index(self.sensor_settings.poll_rate))
        self.dropdown_poll_rate.set_tooltip_text("USB Polling Rate (Hz)")
        self.dropdown_poll_rate.connect("notify::selected", self._on_poll_rate_selected)
        ctrl_row.append(self.dropdown_poll_rate)

        self.lbl_sensor_status = Gtk.Label()
        self.lbl_sensor_status.add_css_class("dim-label")
        self.lbl_sensor_status.set_xalign(0)
        self.lbl_sensor_status.set_hexpand(True)
        ctrl_row.append(self.lbl_sensor_status)

        btn_read_hw = Gtk.Button(label="⟳ Read")
        btn_read_hw.add_css_class("ghost-btn")
        btn_read_hw.set_tooltip_text("Read current DPI and polling rate from physical mouse via OpenRazer")
        btn_read_hw.connect("clicked", self._on_read_hardware_clicked)
        ctrl_row.append(btn_read_hw)

        self.btn_apply_sensor = Gtk.Button(label="⚡ Apply DPI")
        self.btn_apply_sensor.add_css_class("primary-btn")
        self.btn_apply_sensor.set_tooltip_text("Apply DPI and polling rate to hardware immediately and save settings")
        self.btn_apply_sensor.connect("clicked", self._on_apply_sensor_clicked)
        ctrl_row.append(self.btn_apply_sensor)

        dpi_box.append(ctrl_row)

        self._refresh_stage_buttons()
        self._update_sensor_sensitivity_states()
        self._update_sensor_badge()
        return dpi_box

    def _format_dpi_pair(self, dpi_x: int, dpi_y: int) -> str:
        return f"{dpi_x}" if dpi_x == dpi_y else f"{dpi_x}×{dpi_y}"

    def _refresh_stage_buttons(self):
        if not getattr(self, "stage_buttons", None):
            return
        stages = self.sensor_settings.stages
        for idx, btn in enumerate(self.stage_buttons, start=1):
            if idx - 1 < len(stages):
                sx, sy = stages[idx - 1]
            else:
                sx, sy = (800 * idx, 800 * idx)
            btn.set_label(f"S{idx}: {self._format_dpi_pair(sx, sy)}")
            btn.set_tooltip_text(f"Stage {idx}: {sx}×{sy} DPI (click to activate)")
            if idx == self.sensor_settings.active_stage and sx == self.sensor_settings.dpi_x and sy == self.sensor_settings.dpi_y:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

    def _update_sensor_sensitivity_states(self):
        can_indep_xy = (not self.sensor_caps.available) or self.sensor_caps.has_independent_xy
        if hasattr(self, "chk_link_xy"):
            self.chk_link_xy.set_sensitive(can_indep_xy)
        if hasattr(self, "spin_dpi_y"):
            self.spin_dpi_y.set_sensitive(can_indep_xy and not self.sensor_settings.linked_xy)
        if hasattr(self, "dropdown_poll_rate"):
            self.dropdown_poll_rate.set_sensitive(
                (not self.sensor_caps.available) or self.sensor_caps.has_poll_rate
            )
        if hasattr(self, "lbl_sensor_status"):
            if self.sensor_caps.available and self.sensor_caps.has_dpi:
                self.lbl_sensor_status.set_text(
                    f"Max {self.sensor_caps.max_dpi} DPI · OpenRazer active"
                )
            else:
                self.lbl_sensor_status.set_text(
                    f"Max {self.sensor_caps.max_dpi} DPI · Saved locally (OpenRazer offline)"
                )

    def _update_sensor_badge(self):
        dpi_str = self._format_dpi_pair(self.sensor_settings.dpi_x, self.sensor_settings.dpi_y)
        poll_str = f"{self.sensor_settings.poll_rate} Hz"
        if self.lbl_sensor_badge is not None:
            status_tag = "" if (self.sensor_caps.available and self.sensor_caps.has_dpi) else " (saved)"
            self.lbl_sensor_badge.set_markup(
                f"🎯 <b>{GLib.markup_escape_text(dpi_str)} DPI</b> · {GLib.markup_escape_text(poll_str)}{status_tag}"
            )
            tip = (
                f"Active Sensor Settings:\n"
                f"• DPI: {self.sensor_settings.dpi_x} × {self.sensor_settings.dpi_y}\n"
                f"• Stage: {self.sensor_settings.active_stage} of {len(self.sensor_settings.stages)}\n"
                f"• Polling Rate: {self.sensor_settings.poll_rate} Hz\n"
                f"• Backend: {'OpenRazer Live' if self.sensor_caps.available else 'Saved locally (OpenRazer offline)'}"
            )
            self.lbl_sensor_badge.set_tooltip_text(tip)

    def _sync_sensor_widgets_from_state(self):
        self._updating_dpi_controls = True
        try:
            if hasattr(self, "dpi_scale"):
                self.dpi_scale.set_range(self.sensor_caps.min_dpi, self.sensor_caps.max_dpi)
                self.dpi_scale.set_value(self.sensor_settings.dpi_x)
            if hasattr(self, "spin_dpi_x"):
                self.spin_dpi_x.set_range(self.sensor_caps.min_dpi, self.sensor_caps.max_dpi)
                self.spin_dpi_x.set_value(self.sensor_settings.dpi_x)
            if hasattr(self, "spin_dpi_y"):
                self.spin_dpi_y.set_range(self.sensor_caps.min_dpi, self.sensor_caps.max_dpi)
                self.spin_dpi_y.set_value(self.sensor_settings.dpi_y)
            if hasattr(self, "chk_link_xy"):
                self.chk_link_xy.set_active(self.sensor_settings.linked_xy)
            if hasattr(self, "dropdown_poll_rate") and hasattr(self, "poll_rates_list"):
                if self.sensor_settings.poll_rate in self.poll_rates_list:
                    self.dropdown_poll_rate.set_selected(
                        self.poll_rates_list.index(self.sensor_settings.poll_rate)
                    )
        finally:
            self._updating_dpi_controls = False

        self._refresh_stage_buttons()
        self._update_sensor_sensitivity_states()
        self._update_sensor_badge()

    def _match_stage_for_current_dpi(self):
        for idx, (sx, sy) in enumerate(self.sensor_settings.stages, start=1):
            if sx == self.sensor_settings.dpi_x and sy == self.sensor_settings.dpi_y:
                self.sensor_settings.active_stage = idx
                break

    def _on_dpi_scale_changed(self, scale):
        if self._updating_dpi_controls:
            return
        raw_val = int(round(scale.get_value() / 50.0) * 50)
        val = clamp_dpi_value(
            raw_val,
            self.sensor_caps.min_dpi,
            self.sensor_caps.max_dpi,
            self.sensor_caps.available_dpi,
        )
        self.sensor_settings.dpi_x = val
        if self.sensor_settings.linked_xy:
            self.sensor_settings.dpi_y = val
        self._match_stage_for_current_dpi()
        self._sync_sensor_widgets_from_state()

    def _on_spin_dpi_x_changed(self, spin):
        if self._updating_dpi_controls:
            return
        val = clamp_dpi_value(
            spin.get_value_as_int(),
            self.sensor_caps.min_dpi,
            self.sensor_caps.max_dpi,
            self.sensor_caps.available_dpi,
        )
        self.sensor_settings.dpi_x = val
        if self.sensor_settings.linked_xy:
            self.sensor_settings.dpi_y = val
        self._match_stage_for_current_dpi()
        self._sync_sensor_widgets_from_state()

    def _on_spin_dpi_y_changed(self, spin):
        if self._updating_dpi_controls:
            return
        val = clamp_dpi_value(
            spin.get_value_as_int(),
            self.sensor_caps.min_dpi,
            self.sensor_caps.max_dpi,
            self.sensor_caps.available_dpi,
        )
        self.sensor_settings.dpi_y = val
        if self.sensor_settings.linked_xy:
            self.sensor_settings.dpi_x = val
        self._match_stage_for_current_dpi()
        self._sync_sensor_widgets_from_state()

    def _on_link_xy_toggled(self, check_btn):
        if self._updating_dpi_controls:
            return
        linked = bool(check_btn.get_active())
        self.sensor_settings.linked_xy = linked
        if linked:
            self.sensor_settings.dpi_y = self.sensor_settings.dpi_x
        self._match_stage_for_current_dpi()
        self._sync_sensor_widgets_from_state()

    def _on_poll_rate_selected(self, dropdown, _param):
        if self._updating_dpi_controls:
            return
        idx = int(dropdown.get_selected())
        if 0 <= idx < len(self.poll_rates_list):
            self.sensor_settings.poll_rate = self.poll_rates_list[idx]
            self._update_sensor_badge()

    def _on_dpi_stage_clicked(self, _widget, stage_idx: int):
        stages = self.sensor_settings.stages
        if not (1 <= stage_idx <= len(stages)):
            return
        sx, sy = stages[stage_idx - 1]
        self.sensor_settings.active_stage = stage_idx
        self.sensor_settings.dpi_x = sx
        if sx != sy and self.sensor_caps.has_independent_xy:
            self.sensor_settings.linked_xy = False
            self.sensor_settings.dpi_y = sy
        else:
            self.sensor_settings.dpi_y = sx if self.sensor_settings.linked_xy else sy
        self._sync_sensor_widgets_from_state()
        self._apply_sensor_to_hardware()

    def _on_save_stage_clicked(self, _widget):
        idx = max(1, min(len(self.sensor_settings.stages), int(self.sensor_settings.active_stage)))
        dx = int(self.sensor_settings.dpi_x)
        dy = dx if self.sensor_settings.linked_xy else int(self.sensor_settings.dpi_y)
        self.sensor_settings.stages[idx - 1] = (dx, dy)
        dev_name = self.detected_device.get("name", self.default_device_name)
        save_mouse_settings(dev_name, self.sensor_settings)
        if self.sensor_caps.available and self.sensor_caps.has_dpi_stages:
            get_dpi_engine().apply_dpi_stages(
                dev_name, idx, self.sensor_settings.stages, pid=self.detected_device.get("product")
            )
        self._refresh_stage_buttons()
        if hasattr(self, "toast"):
            self.toast.show_message(
                f"Saved Stage {idx} as {self._format_dpi_pair(dx, dy)} DPI", icon="💾"
            )

    def _on_reset_stages_clicked(self, _widget):
        self.sensor_settings.stages = [
            (
                clamp_dpi_value(sx, self.sensor_caps.min_dpi, self.sensor_caps.max_dpi, self.sensor_caps.available_dpi),
                clamp_dpi_value(sy, self.sensor_caps.min_dpi, self.sensor_caps.max_dpi, self.sensor_caps.available_dpi),
            )
            for sx, sy in DEFAULT_DPI_STAGES
        ]
        self._match_stage_for_current_dpi()
        dev_name = self.detected_device.get("name", self.default_device_name)
        save_mouse_settings(dev_name, self.sensor_settings)
        self._refresh_stage_buttons()
        if hasattr(self, "toast"):
            self.toast.show_message("Reset DPI stages to factory defaults", icon="↺")

    def _on_read_hardware_clicked(self, _widget):
        self.rescan_device_and_side_plate(show_toast=False)
        dev_name = self.detected_device.get("name", self.default_device_name)
        pid = self.detected_device.get("product")
        self.sensor_caps = get_dpi_engine().discover_capabilities(dev_name, pid=pid)
        plate_meta = SIDE_PLATE_METADATA.get(self.active_side_plate, SIDE_PLATE_METADATA[SIDE_PLATE_FPS_2])
        if self.sensor_caps.available and self.sensor_caps.has_dpi:
            dx, dy = self.sensor_caps.current_dpi
            self.sensor_settings.dpi_x = dx
            self.sensor_settings.dpi_y = dy
            self.sensor_settings.linked_xy = (dx == dy)
            if self.sensor_caps.current_poll_rate:
                self.sensor_settings.poll_rate = self.sensor_caps.current_poll_rate
            self._match_stage_for_current_dpi()
            self._sync_sensor_widgets_from_state()
            if hasattr(self, "toast"):
                self.toast.show_message(
                    f"Read from {self.sensor_caps.device_name}: "
                    f"{self._format_dpi_pair(dx, dy)} DPI · {self.sensor_settings.poll_rate} Hz · {plate_meta['short_label']}",
                    icon="🎯",
                )
        else:
            self._sync_sensor_widgets_from_state()
            if hasattr(self, "toast"):
                self.toast.show_message(
                    f"Focused {plate_meta['short_label']} · displaying saved sensor settings.",
                    icon="🧩",
                )

    def _on_apply_sensor_clicked(self, _widget):
        self._apply_sensor_to_hardware()

    def _apply_sensor_to_hardware(self, show_toast: bool = True):
        dev_name = self.detected_device.get("name", self.default_device_name)
        pid = self.detected_device.get("product")
        res = get_dpi_engine().apply_sensor_settings(dev_name, self.sensor_settings, pid=pid)
        self.sensor_caps = get_dpi_engine().discover_capabilities(dev_name, pid=pid)
        self._sync_sensor_widgets_from_state()
        if show_toast and hasattr(self, "toast"):
            self.toast.show_message(res.message, icon="🎯" if res.success else "⚠️")
        return res

    def _apply_current_preset(self, widget):
        plate_from_state = detect_side_plate_from_state(self.state)
        if plate_from_state:
            self._focus_detected_side_plate(plate_from_state, focus_widget=False)
        self.sensor_settings.side_plate = self.active_side_plate
        self._apply_sensor_to_hardware(show_toast=False)
        super()._apply_current_preset(widget)


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
