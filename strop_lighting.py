#!/usr/bin/env python3
"""
Strop — Unified RGB Lighting & Chroma Effects Studio (Native GTK4 GUI)
Implements a 60 FPS internal render loop with 16 lighting presets, interactive
Cairo HSV color ring + SV square, multi-stop gradient editor, global master
synchronization, and 2D vector zone mapping across Keyboards, Keypads, Mice, and Controllers.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, Gio, GLib, Gtk

from strop_core.catalog import get_archetype_for_device
from strop_core.device import detect_device, device_model_name, scan_all_connected_devices
from strop_core.lighting import (
    DEVICE_CATEGORIES,
    EFFECT_SPECIFICATIONS,
    EffectRuntimeState,
    FRAME_INTERVAL_MS,
    GradientStop,
    LightingLayer,
    LightingStudioController,
    RGBTuple,
    get_default_effect_params,
    get_lighting_engine,
    get_preset_clusters,
    load_lighting_settings,
    rgb_to_hex,
    save_lighting_settings,
)
from strop_core.lighting_widgets import ColorSelectorPanel, DeviceLightingCanvas
from strop_core.theme import apply_theme, show_about_dialog
from strop_core.toast import StropToast


def _category_for_device_name(device_name: str) -> str:
    low = (device_name or "").lower()
    if "controller" in low or "wolverine" in low or "raiju" in low or "kishi" in low:
        return "controller"
    arch = get_archetype_for_device(device_name)
    if arch.startswith("KEYPAD_"):
        return "keypad"
    if arch.startswith("MOUSE_"):
        return "mouse"
    return "keyboard"


class LightingStudioWindow(Gtk.ApplicationWindow):
    """Main GTK4 Window for the Strop Lighting Studio."""
    def __init__(self, app: Gtk.Application, device_override: Optional[str] = None):
        super().__init__(application=app, title="Strop — Lighting Studio")
        self.set_default_size(1160, 780)
        self.add_css_class("main-window")

        self.controller = LightingStudioController()
        load_lighting_settings(self.controller)
        self.hw_engine = get_lighting_engine()

        self.connected_devices = scan_all_connected_devices()
        if device_override:
            self.active_device_name = device_override
            self.active_category = _category_for_device_name(device_override)
        elif self.connected_devices:
            self.active_device_name = self.connected_devices[0]["name"]
            self.active_category = _category_for_device_name(self.active_device_name)
        else:
            self.active_device_name = "Razer BlackWidow V3"
            self.active_category = "keyboard"

        self.active_layer_index: int = 0
        self.active_color_slot: str = "color1"  # "color1" | "color2" | "rest_color" | "cold_color" | "hot_color"
        self._updating_controls: bool = False
        self._tick_source_id: int = 0
        self._hw_frame_divider: int = 0
        self.live_hw_preview: bool = True

        self._build_ui()
        self._setup_keyboard_trigger_controller()
        self._switch_category(self.active_category)

        self._tick_source_id = GLib.timeout_add(FRAME_INTERVAL_MS, self._on_frame_tick)
        self.connect("close-request", self._on_close_request)

    def _on_close_request(self, window: Gtk.Window) -> bool:
        if self._tick_source_id:
            GLib.source_remove(self._tick_source_id)
            self._tick_source_id = 0
        save_lighting_settings(self.controller)
        return False

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        overlay = Gtk.Overlay()
        self.set_child(overlay)

        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        root_box.set_margin_top(8)
        root_box.set_margin_bottom(8)
        root_box.set_margin_start(12)
        root_box.set_margin_end(12)
        overlay.set_child(root_box)

        # 1. Global Top Toolbar (Section 3.2)
        root_box.append(self._build_global_toolbar())

        # 2. Zone Assignment & Hardware Mapping Bar (Section 3.3)
        root_box.append(self._build_zone_toolbar())

        # 3. Interactive 2D Device SVG/Vector Canvas
        canvas_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        canvas_card.add_css_class("chassis")
        canvas_card.set_vexpand(True)

        self.canvas = DeviceLightingCanvas(
            on_selection_changed=self._on_canvas_selection_changed,
            on_node_pressed=self._on_canvas_node_pressed,
            on_node_released=self._on_canvas_node_released,
        )
        canvas_card.append(self.canvas)
        root_box.append(canvas_card)

        # 4. Bottom 3-Column Dock (Effect Presets & Layers | Effect Parameters | Color & Gradient Selector)
        root_box.append(self._build_bottom_dock())

        # 5. Toast notification overlay
        self.toast = StropToast()
        overlay.add_overlay(self.toast)

    def _build_global_toolbar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bar.add_css_class("dock-card")

        # Brand Title
        lbl_title = Gtk.Label()
        lbl_title.set_markup("<span size='medium' weight='bold' color='#f8fafc'>STROP <span color='#22c55e'>Lighting Studio</span></span>")
        lbl_title.set_xalign(0)
        bar.append(lbl_title)

        # Device Topology Switcher (Keyboard, Keypad, Mouse, Controller)
        topo_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.cat_buttons: Dict[str, Gtk.Button] = {}
        cat_labels = [
            ("keyboard", "⌨️ Keyboard"),
            ("keypad", "🎮 Keypad"),
            ("mouse", "🖱️ Mouse"),
            ("controller", "🕹️ Controller"),
        ]
        for cat_id, label in cat_labels:
            btn = Gtk.Button(label=label)
            btn.add_css_class("dpi-stage-btn")
            btn.connect("clicked", lambda b, cid=cat_id: self._switch_category(cid))
            topo_box.append(btn)
            self.cat_buttons[cat_id] = btn
        bar.append(topo_box)

        # Master Brightness Slider (0% - 100%)
        b_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_b = Gtk.Label(label="🔆 Brightness")
        lbl_b.add_css_class("dim-text")
        b_box.append(lbl_b)

        self.scale_brightness = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.0, 100.0, 1.0)
        self.scale_brightness.set_value(self.controller.master_brightness * 100.0)
        self.scale_brightness.set_draw_value(False)
        self.scale_brightness.set_size_request(100, -1)
        self.scale_brightness.connect("value-changed", self._on_brightness_changed)
        b_box.append(self.scale_brightness)

        self.lbl_brightness_val = Gtk.Label(label=f"{int(round(self.controller.master_brightness * 100))}%")
        self.lbl_brightness_val.set_width_chars(4)
        self.lbl_brightness_val.add_css_class("code-label")
        b_box.append(self.lbl_brightness_val)
        bar.append(b_box)

        # Global Speed Slider (0.5x - 3.0x)
        s_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_s = Gtk.Label(label="⏱️ Speed")
        lbl_s.add_css_class("dim-text")
        s_box.append(lbl_s)

        self.scale_speed = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0.5, 3.0, 0.1)
        self.scale_speed.set_value(self.controller.global_speed)
        self.scale_speed.set_draw_value(False)
        self.scale_speed.set_size_request(95, -1)
        self.scale_speed.connect("value-changed", self._on_global_speed_changed)
        s_box.append(self.scale_speed)

        self.lbl_speed_val = Gtk.Label(label=f"{self.controller.global_speed:.1f}x")
        self.lbl_speed_val.set_width_chars(4)
        self.lbl_speed_val.add_css_class("code-label")
        s_box.append(self.lbl_speed_val)
        bar.append(s_box)

        # Sync All Devices Toggle
        self.chk_sync_all = Gtk.CheckButton(label="🔗 Sync All Devices")
        self.chk_sync_all.set_active(self.controller.sync_all_devices)
        self.chk_sync_all.set_tooltip_text(
            "Share a single phase-locked master clock and apply effect changes across all devices simultaneously"
        )
        self.chk_sync_all.connect("toggled", self._on_sync_all_toggled)
        bar.append(self.chk_sync_all)

        # Right-aligned Action Buttons
        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        actions.set_hexpand(True)
        actions.set_halign(Gtk.Align.END)

        btn_save = Gtk.Button(label="💾 Save")
        btn_save.add_css_class("ghost-btn")
        btn_save.set_tooltip_text("Save lighting profile and custom swatches")
        btn_save.connect("clicked", self._on_save_clicked)
        actions.append(btn_save)

        btn_apply_hw = Gtk.Button(label="⚡ Apply to Hardware")
        btn_apply_hw.add_css_class("primary-btn")
        btn_apply_hw.set_tooltip_text("Push lighting frame to connected OpenRazer hardware")
        btn_apply_hw.connect("clicked", self._on_apply_hardware_clicked)
        actions.append(btn_apply_hw)

        btn_about = Gtk.Button(label="ℹ️")
        btn_about.add_css_class("ghost-btn")
        btn_about.connect("clicked", lambda w: show_about_dialog(self))
        actions.append(btn_about)

        bar.append(actions)
        return bar

    def _build_zone_toolbar(self) -> Gtk.Box:
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        bar.add_css_class("card")

        # Whole Device Mode One-Click Toggle
        self.btn_whole_device = Gtk.ToggleButton(label="🌐 Whole Device")
        self.btn_whole_device.add_css_class("dpi-stage-btn")
        self.btn_whole_device.set_active(True)
        self.btn_whole_device.set_tooltip_text("Route a single effect layer to every LED on the active peripheral")
        self.btn_whole_device.connect("toggled", self._on_whole_device_toggled)
        bar.append(self.btn_whole_device)

        lbl_clusters = Gtk.Label(label="Preset Zones:")
        lbl_clusters.add_css_class("dim-text")
        bar.append(lbl_clusters)

        # Dynamic Preset Cluster Buttons container
        self.cluster_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.cluster_btn_box.set_hexpand(True)
        bar.append(self.cluster_btn_box)

        # Selection / Trigger Tool Mode + Layer Assignment
        tools_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)

        self.btn_mode_select = Gtk.ToggleButton(label="⬚ Marquee / Click Select")
        self.btn_mode_select.add_css_class("ghost-btn")
        self.btn_mode_select.set_active(True)
        self.btn_mode_select.set_tooltip_text("Click LEDs or drag a marquee box to select custom zones")
        self.btn_mode_select.connect("toggled", self._on_mode_select_toggled)
        tools_box.append(self.btn_mode_select)

        self.btn_mode_trigger = Gtk.ToggleButton(label="⚡ Test Input Trigger")
        self.btn_mode_trigger.add_css_class("ghost-btn")
        self.btn_mode_trigger.set_tooltip_text("Click keys on canvas to fire live Ripple, Reactive, Ripple Line, or Heatmap events")
        self.btn_mode_trigger.connect("toggled", self._on_mode_trigger_toggled)
        tools_box.append(self.btn_mode_trigger)

        self.btn_assign_zone = Gtk.Button(label="➕ Assign Layer to Selection")
        self.btn_assign_zone.add_css_class("func-btn")
        self.btn_assign_zone.set_tooltip_text("Assign current effect as an independent overlay on the selected LEDs")
        self.btn_assign_zone.connect("clicked", self._on_assign_selection_layer)
        tools_box.append(self.btn_assign_zone)

        btn_clear_sel = Gtk.Button(label="🧹 Reset Layers")
        btn_clear_sel.add_css_class("ghost-btn")
        btn_clear_sel.set_tooltip_text("Clear all zone overlays and reset to a single Whole Device effect")
        btn_clear_sel.connect("clicked", self._on_reset_layers_clicked)
        tools_box.append(btn_clear_sel)

        bar.append(tools_box)
        return bar

    def _build_bottom_dock(self) -> Gtk.Box:
        dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        dock.set_size_request(-1, 310)

        # Column 1: 16 Lighting Presets & Active Zone Layers
        col1 = self._build_effects_and_layers_column()
        col1.set_size_request(300, -1)
        dock.append(col1)

        # Column 2: Dynamic Effect Parameter Controls
        col2 = self._build_effect_params_column()
        col2.set_hexpand(True)
        dock.append(col2)

        # Column 3: Unified Color Selector & Gradient Editor
        self.color_selector = ColorSelectorPanel(
            user_swatches=self.controller.user_swatches,
            on_color_changed=self._on_selector_color_changed,
            on_gradient_changed=self._on_selector_gradient_changed,
            on_user_swatches_changed=self._on_user_swatches_updated,
        )
        self.color_selector.set_size_request(360, -1)
        dock.append(self.color_selector)

        return dock

    def _build_effects_and_layers_column(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("card")

        lbl_head = Gtk.Label()
        lbl_head.set_markup("<span weight='bold' size='small' color='#f8fafc'>✨ Lighting Effects (16 Presets)</span>")
        lbl_head.set_xalign(0)
        card.append(lbl_head)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        eff_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.effect_buttons: Dict[str, Gtk.Button] = {}

        groups = ["Core Presets", "Common Additions", "Grid & Pulse FX"]
        for grp in groups:
            grp_lbl = Gtk.Label()
            grp_lbl.set_markup(f"<span size='x-small' weight='bold' color='#86efac'>{GLib.markup_escape_text(grp.upper())}</span>")
            grp_lbl.set_xalign(0)
            grp_lbl.set_margin_top(4)
            eff_list_box.append(grp_lbl)

            grid = Gtk.Grid()
            grid.set_row_spacing(3)
            grid.set_column_spacing(4)
            specs = [s for s in EFFECT_SPECIFICATIONS.values() if s["group"] == grp]
            for idx, spec in enumerate(specs):
                eid = spec["id"]
                btn = Gtk.Button(label=f"{spec['icon']} {spec['name']}")
                btn.add_css_class("dpi-stage-btn")
                btn.set_hexpand(True)
                btn.set_tooltip_text(spec["description"])
                btn.connect("clicked", lambda b, effect_id=eid: self._on_effect_selected(effect_id))
                grid.attach(btn, idx % 2, idx // 2, 1, 1)
                self.effect_buttons[eid] = btn
            eff_list_box.append(grid)

        scrolled.set_child(eff_list_box)
        card.append(scrolled)

        # Active Zone Layers List
        lbl_layers = Gtk.Label()
        lbl_layers.set_markup("<span weight='bold' size='x-small' color='#94a3b8'>ACTIVE ZONE LAYERS</span>")
        lbl_layers.set_xalign(0)
        card.append(lbl_layers)

        self.layers_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        card.append(self.layers_box)

        return card

    def _build_effect_params_column(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("card")

        self.lbl_effect_title = Gtk.Label()
        self.lbl_effect_title.set_markup("<span weight='bold' size='medium' color='#f8fafc'>Effect Settings</span>")
        self.lbl_effect_title.set_xalign(0)
        card.append(self.lbl_effect_title)

        self.lbl_effect_desc = Gtk.Label()
        self.lbl_effect_desc.add_css_class("dim-text")
        self.lbl_effect_desc.set_wrap(True)
        self.lbl_effect_desc.set_xalign(0)
        card.append(self.lbl_effect_desc)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)

        self.params_container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        scrolled.set_child(self.params_container)
        card.append(scrolled)

        return card

    # ------------------------------------------------------------------
    # Dynamic Effect Parameter Builder (All 16 Effects)
    # ------------------------------------------------------------------
    def _current_layer(self) -> LightingLayer:
        layers = self.controller.get_active_layers(self.active_category)
        if not layers:
            layer = LightingLayer(id="base", name="Whole Device", effect_id="static", params=get_default_effect_params("static"))
            self.controller.device_layers[self.active_category] = [layer]
            return layer
        self.active_layer_index = max(0, min(self.active_layer_index, len(layers) - 1))
        return layers[self.active_layer_index]

    def _rebuild_effect_params_ui(self) -> None:
        while True:
            child = self.params_container.get_first_child()
            if not child:
                break
            self.params_container.remove(child)

        layer = self._current_layer()
        eff_id = layer.effect_id
        spec = EFFECT_SPECIFICATIONS.get(eff_id, EFFECT_SPECIFICATIONS["static"])
        params = layer.params

        self.lbl_effect_title.set_markup(
            f"<span weight='bold' size='medium' color='#f8fafc'>{spec['icon']} {GLib.markup_escape_text(spec['name'])}</span>"
        )
        self.lbl_effect_desc.set_text(spec["description"])

        # Highlight active effect button
        for eid, btn in self.effect_buttons.items():
            if eid == eff_id:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

        # 1. BREATHING
        if eff_id == "breathing":
            self._add_slider_param(
                "Cycle Duration (s)", "speed_s", 1.5, 8.0, 0.1,
                presets=[("Fast (1.5s)", 1.5), ("Medium (4.0s)", 4.0), ("Slow (8.0s)", 8.0)],
            )
            self._add_dropdown_param("Color Mode", "color_mode", ["Single", "Two Alternating", "Random"])
            self._add_color_slot_selector([("Primary Color", "color1"), ("Secondary Color", "color2")])

        # 2. FIRE
        elif eff_id == "fire":
            self._add_slider_param("Flicker Refresh Rate (Hz)", "flicker_hz", 10.0, 60.0, 1.0)
            self._add_dropdown_param("Color Theme", "theme", ["Classic Flame", "Blue Gas", "Custom Duo-Tone"])
            self._add_color_slot_selector([("Ignition Base Color", "color1"), ("Upper Flame Tip", "color2")])

        # 3. RIPPLE
        elif eff_id == "ripple":
            self._add_slider_param("Expansion Speed (mm/s)", "speed_mm_s", 50.0, 500.0, 10.0)
            self._add_slider_param("Spread Width (key-units)", "spread_units", 1.0, 4.0, 0.25)
            self._add_dropdown_param("Color Mode", "color_mode", ["Single", "Random", "Rainbow"])
            self._add_color_slot_selector([("Ring Color", "color1"), ("Background Color", "rest_color")])
            self._add_trigger_test_button("⚡ Trigger Ripple Pulse")

        # 4. SPECTRUM CYCLING
        elif eff_id == "spectrum_cycling":
            self._add_slider_param(
                "360° Revolution Duration (s)", "duration_s", 2.0, 60.0, 1.0,
                presets=[("Fast (2s)", 2.0), ("Medium (10s)", 10.0), ("Slow (60s)", 60.0)],
            )

        # 5. STARLIGHT
        elif eff_id == "starlight":
            self._add_dropdown_param("Twinkle Density", "density", ["Low", "Medium", "High"])
            self._add_slider_param("Star Fade Duration (s)", "duration_s", 0.3, 3.0, 0.1)
            self._add_dropdown_param("Color Selection", "color_mode", ["Monochrome", "Two-Tone", "Random"])
            self._add_color_slot_selector([("Star Color 1", "color1"), ("Star Color 2", "color2"), ("Base Sky", "rest_color")])

        # 6. STATIC
        elif eff_id == "static":
            self._add_color_slot_selector([("Solid LED Color", "color1")])
            note = Gtk.Label(
                label="Static mode has zero animation overhead and acts as the default fallback for onboard hardware memory."
            )
            note.add_css_class("dim-text")
            note.set_wrap(True)
            note.set_xalign(0)
            self.params_container.append(note)

        # 7. WAVE
        elif eff_id == "wave":
            self._add_dropdown_param(
                "Direction", "direction",
                ["Left-to-Right", "Right-to-Left", "Top-to-Bottom", "Bottom-to-Top", "Radial Outward", "Radial Inward"],
            )
            self._add_slider_param("Wave Velocity (Hz)", "speed", 0.2, 4.0, 0.1)
            self._add_slider_param("Wavelength Scale", "wavelength", 0.4, 2.5, 0.1)
            self._add_dropdown_param("Palette", "palette_mode", ["Rainbow", "Custom Gradient"])

        # 8. WHEEL
        elif eff_id == "wheel":
            self._add_slider_param("Rotation Speed (RPM)", "rpm", 5.0, 120.0, 1.0)
            self._add_dropdown_param("Direction", "direction", ["Clockwise", "Counter-clockwise"])
            self._add_dropdown_param("Color Palette", "palette_mode", ["Rainbow", "Custom Wheel"])

        # 9. REACTIVE
        elif eff_id == "reactive":
            self._add_dropdown_param("Active Color Mode", "color_mode", ["Single", "Random"])
            self._add_slider_param(
                "Fade-Out Decay (s)", "fade_duration_s", 0.2, 3.0, 0.1,
                presets=[("Short (0.2s)", 0.2), ("Medium (1.0s)", 1.0), ("Long (3.0s)", 3.0)],
            )
            self._add_color_slot_selector([("Active Press Color", "color1"), ("Background / Rest Color", "rest_color")])
            self._add_trigger_test_button("⚡ Trigger Reactive Keypress")

        # 10. RAIN
        elif eff_id == "rain":
            self._add_slider_param(
                "Drop Fall Interval (ms/row)", "step_ms", 50.0, 250.0, 5.0,
                presets=[("Downpour (50ms)", 50.0), ("Steady (120ms)", 120.0), ("Drizzle (250ms)", 250.0)],
            )
            self._add_dropdown_param("Droplet Density", "density", ["Low", "Medium", "High"])
            self._add_dropdown_param("Color Theme", "theme", ["Classic Rain", "Digital Matrix", "Single Solid", "Random"])
            self._add_color_slot_selector([("Droplet Color", "color1")])

        # 11. SCANNER
        elif eff_id == "scanner":
            self._add_slider_param("Sweep Speed", "speed", 0.3, 3.5, 0.1)
            self._add_slider_param("Comet Tail Length (LEDs)", "tail_length", 1.0, 5.0, 1.0)
            self._add_dropdown_param("Sweep Axis", "axis", ["Horizontal", "Vertical"])
            self._add_color_slot_selector([("Scanner Bar Color", "color1"), ("Background Rest Color", "rest_color")])

        # 12. COLOR PULSE (HEARTBEAT)
        elif eff_id == "color_pulse":
            self._add_slider_param("Tempo (BPM)", "bpm", 40.0, 160.0, 2.0)
            self._add_dropdown_param("Color Mode", "color_mode", ["Single", "Alternating Duo", "Random"])
            self._add_slider_param("Base Resting Brightness", "base_brightness", 0.0, 0.40, 0.02)
            self._add_color_slot_selector([("Pulse Color A", "color1"), ("Pulse Color B", "color2")])

        # 13. RIPPLE LINE
        elif eff_id == "ripple_line":
            self._add_dropdown_param("Axis Mode", "axis_mode", ["Horizontal", "Vertical", "Crosshair"])
            self._add_slider_param("Travel Speed (rows/s)", "speed_rows_s", 4.0, 36.0, 1.0)
            self._add_color_slot_selector([("Shockwave Line Color", "color1"), ("Background Color", "rest_color")])
            self._add_trigger_test_button("⚡ Fire Linear Shockwave")

        # 14. GRADIENT FILL
        elif eff_id == "gradient_fill":
            self._add_dropdown_param("Fill Direction", "direction", ["Left-to-Right", "Bottom-to-Top", "Random Scatter"])
            self._add_slider_param("Fill Speed", "speed", 0.3, 3.0, 0.1)

        # 15. CHECKERBOARD
        elif eff_id == "checkerboard":
            self._add_slider_param("Swap Interval (s)", "interval_s", 0.2, 5.0, 0.1)
            self._add_dropdown_param("Transition Style", "transition", ["Instant Toggle", "Smooth Crossfade"])
            self._add_color_slot_selector([("Grid Group A Color", "color1"), ("Grid Group B Color", "color2")])

        # 16. HEATMAP
        elif eff_id == "heatmap":
            self._add_slider_param("Heat Sensitivity (presses to Red)", "sensitivity", 1.0, 30.0, 1.0)
            self._add_slider_param("Cooling Decay Rate (/s)", "cooling_rate", 0.1, 4.0, 0.1)
            self._add_color_slot_selector([("Cold Rest Stop", "cold_color"), ("Peak Hot Stop", "hot_color")])

            btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            btn_sim = Gtk.Button(label="🔥 Simulate Keypress Burst")
            btn_sim.add_css_class("func-btn")
            btn_sim.connect("clicked", lambda b: self._simulate_keypress_burst())
            btn_row.append(btn_sim)

            btn_rst = Gtk.Button(label="🔄 Reset Heatmap")
            btn_rst.add_css_class("ghost-btn")
            btn_rst.connect("clicked", lambda b: self.controller.reset_heatmap(self.active_category))
            btn_row.append(btn_rst)
            self.params_container.append(btn_row)

        # Sync Color Selector Panel with active layer's color & gradient stops
        if self.active_color_slot not in params:
            self.active_color_slot = "cold_color" if "cold_color" in params else "color1"
        active_col = params.get(self.active_color_slot, (0, 255, 0))
        self.color_selector.set_color(active_col, emit=False)
        if "gradient_stops" in params:
            self.color_selector.gradient_editor.set_stops(params["gradient_stops"], emit=False)

    def _add_slider_param(
        self,
        label_text: str,
        param_key: str,
        min_v: float,
        max_v: float,
        step_v: float,
        presets: Optional[List[tuple]] = None,
    ) -> None:
        layer = self._current_layer()
        cur_val = float(layer.params.get(param_key, min_v))

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        top = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label=label_text)
        lbl.add_css_class("dim-text")
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        top.append(lbl)

        val_lbl = Gtk.Label(label=f"{cur_val:.1f}" if step_v < 1.0 else f"{int(round(cur_val))}")
        val_lbl.add_css_class("code-label")
        top.append(val_lbl)
        box.append(top)

        scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, min_v, max_v, step_v)
        scale.set_value(cur_val)
        scale.set_draw_value(False)

        def on_changed(s):
            v = s.get_value()
            if step_v >= 1.0 and param_key in ("tail_length", "sensitivity"):
                v = int(round(v))
                val_lbl.set_text(str(v))
            else:
                val_lbl.set_text(f"{v:.2f}" if step_v < 0.1 else f"{v:.1f}")
            self._set_effect_param(param_key, v)

        scale.connect("value-changed", on_changed)
        box.append(scale)

        if presets:
            p_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
            for p_title, p_val in presets:
                p_btn = Gtk.Button(label=p_title)
                p_btn.add_css_class("ghost-btn")
                p_btn.connect("clicked", lambda b, pv=p_val, sc=scale: sc.set_value(pv))
                p_row.append(p_btn)
            box.append(p_row)

        self.params_container.append(box)

    def _add_dropdown_param(self, label_text: str, param_key: str, options: List[str]) -> None:
        layer = self._current_layer()
        cur_val = str(layer.params.get(param_key, options[0]))
        idx = options.index(cur_val) if cur_val in options else 0

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl = Gtk.Label(label=label_text)
        lbl.add_css_class("dim-text")
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        row.append(lbl)

        dd = Gtk.DropDown.new_from_strings(options)
        dd.set_selected(idx)
        dd.connect(
            "notify::selected",
            lambda d, p, opts=options, pk=param_key: self._set_effect_param(pk, opts[d.get_selected()]),
        )
        row.append(dd)
        self.params_container.append(row)

    def _add_color_slot_selector(self, slots: List[tuple]) -> None:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label(label="Edit Color Slot:")
        lbl.add_css_class("dim-text")
        row.append(lbl)

        layer = self._current_layer()
        if self.active_color_slot not in {k for _, k in slots}:
            self.active_color_slot = slots[0][1]

        slot_btns: Dict[str, Gtk.Button] = {}
        for title, key in slots:
            col = layer.params.get(key, (0, 255, 0))
            btn = Gtk.Button(label=f"{title} ({rgb_to_hex(col)})")
            btn.add_css_class("dpi-stage-btn")
            if key == self.active_color_slot:
                btn.add_css_class("active")

            def on_slot_clicked(b, slot_key=key):
                self.active_color_slot = slot_key
                for sk, sb in slot_btns.items():
                    if sk == slot_key:
                        sb.add_css_class("active")
                    else:
                        sb.remove_css_class("active")
                c = self._current_layer().params.get(slot_key, (0, 255, 0))
                self.color_selector.set_color(c, emit=False)

            btn.connect("clicked", on_slot_clicked)
            row.append(btn)
            slot_btns[key] = btn

        self.params_container.append(row)

    def _add_trigger_test_button(self, label: str) -> None:
        btn = Gtk.Button(label=label)
        btn.add_css_class("func-btn")
        btn.connect("clicked", lambda b: self._simulate_keypress_burst(count=1))
        self.params_container.append(btn)

    def _simulate_keypress_burst(self, count: int = 4) -> None:
        nodes = self.controller.topologies.get(self.active_category, [])
        if not nodes:
            return
        import random
        for _ in range(count):
            pick = random.choice(nodes)
            self.controller.trigger_press(self.active_category, pick.id)
            self.controller.trigger_release(self.active_category, pick.id)

    # ------------------------------------------------------------------
    # State & Event Handlers
    # ------------------------------------------------------------------
    def _switch_category(self, category: str) -> None:
        if category not in DEVICE_CATEGORIES:
            return
        self.active_category = category
        for cid, btn in self.cat_buttons.items():
            if cid == category:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")

        nodes = self.controller.topologies[category]
        self.canvas.set_topology(category, nodes)

        self._updating_controls = True
        try:
            self.btn_whole_device.set_active(self.controller.whole_device_mode.get(category, True))
        finally:
            self._updating_controls = False

        self._rebuild_preset_cluster_buttons()
        self._rebuild_layers_list_ui()
        self._rebuild_effect_params_ui()

    def _rebuild_preset_cluster_buttons(self) -> None:
        while True:
            child = self.cluster_btn_box.get_first_child()
            if not child:
                break
            self.cluster_btn_box.remove(child)

        clusters = get_preset_clusters(self.active_category, self.controller.topologies[self.active_category])
        for cluster_name, led_ids in clusters.items():
            btn = Gtk.Button(label=cluster_name)
            btn.add_css_class("quick-tag")
            btn.connect("clicked", lambda b, ids=led_ids, cname=cluster_name: self._on_cluster_preset_clicked(cname, ids))
            self.cluster_btn_box.append(btn)

    def _on_cluster_preset_clicked(self, cluster_name: str, led_ids: Set[str]) -> None:
        self.canvas.set_selected_ids(set(led_ids), emit=True)
        self.toast.show_message(
            f"Selected {cluster_name} ({len(led_ids)} LEDs) — click '➕ Assign Layer to Selection' to add a zone overlay",
            icon="🎯",
        )

    def _on_reset_layers_clicked(self, btn: Gtk.Button) -> None:
        self.controller.clear_zone_layers(self.active_category)
        self.active_layer_index = 0
        self._updating_controls = True
        try:
            self.btn_whole_device.set_active(True)
        finally:
            self._updating_controls = False
        self.canvas.set_selected_ids(set(), emit=False)
        save_lighting_settings(self.controller)
        self._rebuild_layers_list_ui()
        self._rebuild_effect_params_ui()
        frame = self.controller.render_device_frame(self.active_category)
        self.hw_engine.queue_frame_push(
            self.controller.topologies[self.active_category],
            frame,
            device_name=self.active_device_name,
            all_devices=self.controller.sync_all_devices,
            controller=self.controller,
            reset_first=True,
        )
        self.toast.show_message("Cleared all zone overlays and reset hardware matrix", icon="🧹")

    def _rebuild_layers_list_ui(self) -> None:
        while True:
            child = self.layers_box.get_first_child()
            if not child:
                break
            self.layers_box.remove(child)

        layers = self.controller.get_active_layers(self.active_category)
        self.active_layer_index = max(0, min(self.active_layer_index, len(layers) - 1))

        for idx, layer in enumerate(layers):
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.add_css_class("remap-row")

            spec = EFFECT_SPECIFICATIONS.get(layer.effect_id, EFFECT_SPECIFICATIONS["static"])
            btn_sel = Gtk.Button(label=f"{spec['icon']} {layer.name}: {spec['name']}")
            btn_sel.add_css_class("dpi-stage-btn")
            if idx == self.active_layer_index:
                btn_sel.add_css_class("active")
            btn_sel.set_hexpand(True)
            btn_sel.connect("clicked", lambda b, i=idx: self._select_layer(i))
            row.append(btn_sel)

            if idx > 0:
                btn_del = Gtk.Button(label="✕")
                btn_del.add_css_class("danger-btn")
                btn_del.set_tooltip_text("Remove zone overlay layer")
                btn_del.connect("clicked", lambda b, i=idx: self._delete_layer(i))
                row.append(btn_del)

            self.layers_box.append(row)

    def _select_layer(self, index: int) -> None:
        layers = self.controller.get_active_layers(self.active_category)
        if 0 <= index < len(layers):
            self.active_layer_index = index
            target = layers[index].target_leds
            self.canvas.set_selected_ids(set(target) if target else set(), emit=False)
            self._rebuild_layers_list_ui()
            self._rebuild_effect_params_ui()

    def _delete_layer(self, index: int) -> None:
        layers = self.controller.get_active_layers(self.active_category)
        if index > 0 and index < len(layers):
            layers.pop(index)
            self.active_layer_index = max(0, self.active_layer_index - 1)
            self._rebuild_layers_list_ui()
            self._rebuild_effect_params_ui()

    def _on_effect_selected(self, effect_id: str) -> None:
        # When on the base Whole Device layer (or in Whole Device mode), replace all layers cleanly
        # so previous effects/zone layers never linger or combine with the new profile.
        if self.active_layer_index == 0 or self.controller.whole_device_mode.get(self.active_category, True):
            self.controller.whole_device_mode[self.active_category] = True
            self._updating_controls = True
            try:
                self.btn_whole_device.set_active(True)
            finally:
                self._updating_controls = False
            self.canvas.set_selected_ids(set(), emit=False)
            self.controller.set_Effect_on_selection(
                self.active_category,
                effect_id,
                selected_leds=None,
            )
            self.active_layer_index = 0
        else:
            layer = self._current_layer()
            layer.effect_id = effect_id
            layer.params = get_default_effect_params(effect_id)
            layer.runtime = EffectRuntimeState()
            if layer.target_leds is not None:
                eff_name = EFFECT_SPECIFICATIONS.get(effect_id, {}).get("name", effect_id)
                layer.name = f"{eff_name} ({len(layer.target_leds)} LEDs)"

        save_lighting_settings(self.controller)
        self._rebuild_layers_list_ui()
        self._rebuild_effect_params_ui()
        frame = self.controller.render_device_frame(self.active_category)
        self.hw_engine.queue_frame_push(
            self.controller.topologies[self.active_category],
            frame,
            device_name=self.active_device_name,
            all_devices=self.controller.sync_all_devices,
            controller=self.controller,
            reset_first=True,
        )

    def _set_effect_param(self, key: str, value: Any) -> None:
        layer = self._current_layer()
        layer.params[key] = value
        if self.controller.sync_all_devices and layer.target_leds is None:
            for cat in DEVICE_CATEGORIES:
                if cat != self.active_category and self.controller.device_layers.get(cat):
                    self.controller.device_layers[cat][0].params[key] = value

    def _on_selector_color_changed(self, rgb: RGBTuple) -> None:
        layer = self._current_layer()
        if self.active_color_slot in layer.params:
            self._set_effect_param(self.active_color_slot, rgb)
        else:
            self._set_effect_param("color1", rgb)

    def _on_selector_gradient_changed(self, stops: List[GradientStop]) -> None:
        self._set_effect_param("gradient_stops", stops)

    def _on_user_swatches_updated(self, swatches: List[RGBTuple]) -> None:
        self.controller.user_swatches = list(swatches)
        save_lighting_settings(self.controller)
        self.toast.show_message("Saved custom color swatch", icon="🎨")

    def _on_brightness_changed(self, scale: Gtk.Scale) -> None:
        val = scale.get_value()
        self.controller.master_brightness = max(0.0, min(1.0, val / 100.0))
        self.lbl_brightness_val.set_text(f"{int(round(val))}%")

    def _on_global_speed_changed(self, scale: Gtk.Scale) -> None:
        val = scale.get_value()
        self.controller.global_speed = max(0.5, min(3.0, val))
        self.lbl_speed_val.set_text(f"{val:.1f}x")

    def _on_sync_all_toggled(self, chk: Gtk.CheckButton) -> None:
        self.controller.sync_all_devices = chk.get_active()
        if self.controller.sync_all_devices:
            # Synchronize active whole-device effect to all devices immediately
            base = self.controller.device_layers[self.active_category][0]
            for cat in DEVICE_CATEGORIES:
                if cat != self.active_category:
                    self.controller.device_layers[cat] = [
                        LightingLayer(
                            id="base",
                            name="Whole Device",
                            effect_id=base.effect_id,
                            params=dict(base.params),
                            target_leds=None,
                        )
                    ]
            self.toast.show_message("Sync All Devices enabled — master clock & effect phase-locked", icon="🔗")

    def _on_whole_device_toggled(self, btn: Gtk.ToggleButton) -> None:
        if self._updating_controls:
            return
        active = btn.get_active()
        self.controller.whole_device_mode[self.active_category] = active
        if active:
            self.controller.clear_zone_layers(self.active_category)
            self.active_layer_index = 0
            self.canvas.set_selected_ids(set(), emit=False)
            save_lighting_settings(self.controller)
            self._rebuild_layers_list_ui()
            self._rebuild_effect_params_ui()
            frame = self.controller.render_device_frame(self.active_category)
            self.hw_engine.queue_frame_push(
                self.controller.topologies[self.active_category],
                frame,
                device_name=self.active_device_name,
                all_devices=self.controller.sync_all_devices,
                controller=self.controller,
                reset_first=True,
            )

    def _on_mode_select_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self.btn_mode_trigger.set_active(False)
            self.canvas.interaction_mode = "select"
        elif not self.btn_mode_trigger.get_active():
            btn.set_active(True)

    def _on_mode_trigger_toggled(self, btn: Gtk.ToggleButton) -> None:
        if btn.get_active():
            self.btn_mode_select.set_active(False)
            self.canvas.interaction_mode = "trigger"
        elif not self.btn_mode_select.get_active():
            btn.set_active(True)

    def _on_assign_selection_layer(self, btn: Gtk.Button) -> None:
        sel = set(self.canvas.selected_ids)
        if not sel:
            self.toast.show_message("Select one or more LEDs or a Preset Zone first", icon="⚠️")
            return
        self.controller.whole_device_mode[self.active_category] = False
        self._updating_controls = True
        try:
            self.btn_whole_device.set_active(False)
        finally:
            self._updating_controls = False

        cur = self._current_layer()
        new_layer = self.controller.set_Effect_on_selection(
            self.active_category,
            cur.effect_id,
            params=dict(cur.params),
            selected_leds=sel,
        )
        layers = self.controller.get_active_layers(self.active_category)
        if new_layer in layers:
            self.active_layer_index = layers.index(new_layer)
        self._rebuild_layers_list_ui()
        self._rebuild_effect_params_ui()
        self.toast.show_message(f"Assigned layer '{new_layer.name}'", icon="✨")

    def _on_canvas_selection_changed(self, selected_ids: Set[str]) -> None:
        # Keep selection highlighted on canvas; only switch out of Whole Device mode
        # when the user explicitly clicks '➕ Assign Layer to Selection'.
        pass

    def _on_canvas_node_pressed(self, node_id: str) -> None:
        self.controller.trigger_press(self.active_category, node_id)

    def _on_canvas_node_released(self, node_id: str) -> None:
        self.controller.trigger_release(self.active_category, node_id)

    def _setup_keyboard_trigger_controller(self) -> None:
        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_physical_key_pressed)
        key_ctrl.connect("key-released", self._on_physical_key_released)
        self.add_controller(key_ctrl)

    def _match_keycode_to_node(self, keyval: int, keycode: int) -> Optional[str]:
        evdev_code = keycode - 8
        nodes = self.controller.topologies.get(self.active_category, [])
        for n in nodes:
            if n.scancode is not None and n.scancode == evdev_code:
                return n.id
        key_name = (Gdk.keyval_name(keyval) or "").lower()
        for n in nodes:
            if n.id.lower() == key_name or n.label.lower() == key_name:
                return n.id
        return None

    def _on_physical_key_pressed(self, controller, keyval: int, keycode: int, state) -> bool:
        nid = self._match_keycode_to_node(keyval, keycode)
        if nid:
            self.controller.trigger_press(self.active_category, nid)
        return False

    def _on_physical_key_released(self, controller, keyval: int, keycode: int, state) -> None:
        nid = self._match_keycode_to_node(keyval, keycode)
        if nid:
            self.controller.trigger_release(self.active_category, nid)

    def _on_save_clicked(self, btn: Gtk.Button) -> None:
        if save_lighting_settings(self.controller):
            self.toast.show_message("Saved lighting configuration and custom swatches", icon="💾")
        else:
            self.toast.show_message("Could not save lighting configuration", icon="⚠️")

    def _on_apply_hardware_clicked(self, btn: Gtk.Button) -> None:
        save_lighting_settings(self.controller)
        self.live_hw_preview = True
        frame = self.controller.render_device_frame(self.active_category)
        nodes = self.controller.topologies[self.active_category]
        if self.hw_engine.is_available:
            self.hw_engine.queue_frame_push(
                nodes,
                frame,
                device_name=self.active_device_name,
                all_devices=self.controller.sync_all_devices,
                controller=self.controller,
                reset_first=True,
            )
            self.toast.show_message("Cleared previous lighting and applied new profile to hardware", icon="💡")
        else:
            self.toast.show_message("Saved lighting profile (OpenRazer hardware not detected — running in studio preview)", icon="💡")

    # ------------------------------------------------------------------
    # 60 FPS Standardized Internal Render Loop
    # ------------------------------------------------------------------
    def _on_frame_tick(self) -> bool:
        clock_t, scaled_dt = self.controller.step_clock()
        frame = self.controller.render_device_frame(self.active_category, t=clock_t, dt=scaled_dt)
        self.canvas.set_frame(frame)

        # If live hardware streaming is active and OpenRazer is connected, enqueue on background worker
        if self.live_hw_preview and self.hw_engine.is_available:
            self._hw_frame_divider = (self._hw_frame_divider + 1) % 3
            if self._hw_frame_divider == 0:
                self.hw_engine.queue_frame_push(
                    self.controller.topologies[self.active_category],
                    frame,
                    device_name=self.active_device_name,
                    all_devices=self.controller.sync_all_devices,
                    controller=self.controller,
                    reset_first=False,
                )
        return True


class LightingStudioApp(Gtk.Application):
    def __init__(self, device_override: Optional[str] = None):
        super().__init__(application_id="com.razer.strop.lighting", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.device_override = device_override
        self.window: Optional[LightingStudioWindow] = None
        self.connect("startup", lambda app: apply_theme())
        self.connect("activate", self._on_activate)

    def _on_activate(self, app: Gtk.Application) -> None:
        if self.window is None:
            self.window = LightingStudioWindow(self, device_override=self.device_override)
        elif self.device_override:
            self.window.active_device_name = self.device_override
            self.window._switch_category(_category_for_device_name(self.device_override))
        self.window.present()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Strop RGB Lighting & Chroma Effects Studio")
    parser.add_argument("--device", "-d", type=str, default=None, help="Target Razer device name")
    args, unknown = parser.parse_known_args(argv)

    app = LightingStudioApp(device_override=args.device)
    return app.run([sys.argv[0]] + unknown)


if __name__ == "__main__":
    sys.exit(main())
