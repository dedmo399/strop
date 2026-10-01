"""
Strop Core — Base Studio Window
Universal GTK4 base class for hardware studios (Keypad, Keyboard, Mouse).
Provides:
- Polychromatic dark theme styling and CSS context
- Standardized top header bar with live device origin_hash badge & active profile status
- Responsive 3-column bottom studio dock (Key Inspector, Special Actions / Gamepad Palette, Presets & Remap list)
- Universal live keypress recording engine with modifier composition
- Multi-tier preset matching, loading, direct saving, application, and markdown cheat-sheet generation
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio

from strop_core.device import clean_device_display_name
from strop_core.presets import (
    get_device_presets_dir, get_active_profile, apply_profile,
    save_device_preset, load_preset_file
)
from strop_core.theme import apply_theme, show_about_dialog
from strop_core.toast import StropToast
from strop_core.logger import get_logger
from strop_core.gamepad import (
    GAMEPAD_BUTTON_PRESETS, parse_gamepad_display_text
)
from strop_core.lighting import get_lighting_engine, COLOR_PALETTE
from strop_core.macros import load_all_macros, MACRO_TEMPLATES



logger = get_logger("strop.studio")




QUICK_SNIPPETS = [
    ("disable", "disable", "Completely mute key"),
    ("space", "space", "Spacebar key"),
    ("Shift_L", "Shift_L", "Left Shift modifier"),
    ("Control_L", "Control_L", "Left Control modifier"),
    ("Alt_L", "Alt_L", "Left Alt modifier"),
    ("Tab", "Tab", "Tab key"),
    ("Return", "Return", "Enter / Return key"),
    ("Escape", "Escape", "Escape key"),
    ("mouse(1)", "mouse(1)", "Left Click"),
    ("mouse(2)", "mouse(2)", "Middle Click"),
    ("mouse(3)", "mouse(3)", "Right Click"),
    ("wheel(up)", "wheel(up)", "Scroll Up"),
    ("wheel(down)", "wheel(down)", "Scroll Down"),
    ("run(...)", 'run("notify-send \'Action\'")', "Execute command"),
]



class BaseStudioWindow(Gtk.ApplicationWindow):
    """
    Universal GTK4 Application Window for all Strop Hardware Studios.
    Subclasses implement `_init_device()`, `_init_hardware_state()`, and `_build_hardware_canvas()`.
    """
    def __init__(self, app, title: str, default_width: int = 1080, default_height: int = 700):
        super().__init__(application=app, title=title)
        self.set_default_size(default_width, default_height)
        self.add_css_class("main-window")

        # Hardware & State definitions
        self.detected_device: Dict[str, Any] = {}
        self.default_device_name = "Razer Input Device"
        self.default_preset_name = "my-profile"
        self.state: Dict[str, Dict[str, Any]] = {}
        self.button_widgets: Dict[str, Dict[str, Any]] = {}
        self.selected_key_id: Optional[str] = None
        self.is_recording_input: bool = False

        # Lighting & Color Picker State
        self.selected_color_name: str = "Green"
        self.apply_color_all_devices: bool = True
        self.swatch_buttons: Dict[str, Gtk.Button] = {}

        # Hook for subclass device detection
        self._init_device()

        # Hook for subclass hardware state dictionary population
        self._init_hardware_state()

        # Build Main UI Layout

        self._build_base_ui()

        # Setup Input Recording Controller
        self._setup_input_controller()

        # Auto-load active profile if exists
        self._auto_load_active_profile()

        # Initial Render
        self._update_all_visuals()

    def _init_device(self):
        """Subclasses should override to detect specific connected hardware."""
        pass

    def _init_hardware_state(self):
        """Subclasses should populate `self.state` with key definitions."""
        pass

    def _build_hardware_canvas(self) -> Gtk.Widget:
        """Subclasses must implement and return the visual hardware diagram widget."""
        raise NotImplementedError("Subclasses must implement _build_hardware_canvas()")

    def _get_studio_title_markup(self) -> str:
        """Returns the studio title markup for the header bar."""
        return "<span size='medium' weight='bold' color='#f8fafc'>STROP <span color='#22c55e'>Studio</span></span>"

    def _build_base_ui(self):
        overlay = Gtk.Overlay()
        self.set_child(overlay)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(8)
        main_box.set_margin_bottom(8)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        overlay.set_child(main_box)

        # 1. Header Bar
        header_box = self._build_header_bar()
        main_box.append(header_box)

        # 2. Hardware Canvas
        canvas_widget = self._build_hardware_canvas()
        canvas_widget.set_vexpand(True)
        main_box.append(canvas_widget)

        # 3. Bottom Studio Dock (3 columns)
        dock_widget = self._build_studio_dock()
        main_box.append(dock_widget)

        # 4. Floating In-App Toast Notification Banner
        self.toast = StropToast()
        overlay.add_overlay(self.toast)


    def _build_header_bar(self) -> Gtk.Box:
        header_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)

        lbl_title = Gtk.Label()
        lbl_title.set_markup(self._get_studio_title_markup())
        lbl_title.set_xalign(0)
        header_box.append(lbl_title)

        badges_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        badges_box.set_hexpand(True)
        badges_box.set_halign(Gtk.Align.END)

        dev_name = self.detected_device.get("name", self.default_device_name)
        dev_hash = self.detected_device.get("hash", "")
        if dev_name:
            dev_badge = Gtk.Label()
            dev_badge.set_markup(f"🟢 <b>{GLib.markup_escape_text(dev_name)}</b>")
            dev_badge.add_css_class("badge-device")
            if dev_hash:
                dev_badge.set_tooltip_text(f"Auto-generated origin_hash:\n{dev_hash}")
            badges_box.append(dev_badge)


        self.count_badge = Gtk.Label(label="0 keys remapped")
        self.count_badge.add_css_class("badge-stock")
        badges_box.append(self.count_badge)

        btn_hud = Gtk.Button(label="🖥 HUD Overlay")
        btn_hud.add_css_class("ghost-btn")
        btn_hud.set_tooltip_text("Launch floating on-screen HUD overlay")
        btn_hud.connect("clicked", self._launch_hud_overlay)
        badges_box.append(btn_hud)

        btn_about = Gtk.Button(label="ℹ️ About")
        btn_about.add_css_class("ghost-btn")
        btn_about.set_tooltip_text("About Strop Suite")
        btn_about.connect("clicked", lambda w: show_about_dialog(self))
        badges_box.append(btn_about)

        btn_reset_all = Gtk.Button(label="Reset All")
        btn_reset_all.add_css_class("danger-btn")
        btn_reset_all.connect("clicked", self._on_reset_all)
        badges_box.append(btn_reset_all)

        header_box.append(badges_box)
        return header_box

    def _build_studio_dock(self) -> Gtk.Box:
        dock_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        dock_box.set_size_request(-1, 230)

        # Col 1: Key Inspector
        col1 = self._build_key_inspector_dock()
        col1.set_hexpand(False)
        col1.set_size_request(270, -1)
        dock_box.append(col1)

        # Col 2: Special Actions & Gamepad Palette
        col2 = self._build_special_actions_dock()
        col2.set_hexpand(True)
        dock_box.append(col2)

        # Col 3: Presets & Active Remap List
        col3 = self._build_presets_dock()
        col3.set_hexpand(False)
        col3.set_size_request(280, -1)
        dock_box.append(col3)

        return dock_box

    def _build_key_inspector_dock(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("card")

        lbl_head = Gtk.Label()
        lbl_head.set_markup("<span weight='bold' size='small' color='#f8fafc'>Key Inspector</span>")
        lbl_head.set_xalign(0)
        card.append(lbl_head)

        self.editor_empty_lbl = Gtk.Label(label="Select any key on the canvas\nto inspect & configure.")
        self.editor_empty_lbl.add_css_class("dim-label")
        self.editor_empty_lbl.set_vexpand(True)
        card.append(self.editor_empty_lbl)

        self.editor_form_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.editor_form_box.set_visible(False)
        self.editor_form_box.set_vexpand(True)

        meta_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.ed_key_name = Gtk.Label()
        self.ed_key_name.set_xalign(0)
        self.ed_key_name.set_hexpand(True)
        meta_row.append(self.ed_key_name)

        self.ed_key_code = Gtk.Label()
        self.ed_key_code.add_css_class("code-label")
        meta_row.append(self.ed_key_code)
        self.editor_form_box.append(meta_row)

        out_lbl = Gtk.Label(label="Key / Macro Output:")
        out_lbl.set_xalign(0)
        out_lbl.add_css_class("dim-label")
        self.editor_form_box.append(out_lbl)

        self.entry_output = Gtk.Entry()
        self.entry_output.set_placeholder_text("e.g. 4, 5, space, mouse(1), key_down(Control_L)")
        self.entry_output.connect("changed", self._on_output_changed)
        self.editor_form_box.append(self.entry_output)

        self.btn_record_input = Gtk.Button(label="🔴 Record Physical Keystroke")
        self.btn_record_input.add_css_class("record-btn")
        self.btn_record_input.set_tooltip_text("Press physical key or combo to capture")
        self.btn_record_input.connect("clicked", self._on_record_clicked)
        self.editor_form_box.append(self.btn_record_input)

        name_lbl = Gtk.Label(label="Display Label (Optional):")
        name_lbl.set_xalign(0)
        name_lbl.add_css_class("dim-label")
        self.editor_form_box.append(name_lbl)

        self.entry_custom_label = Gtk.Entry()
        self.entry_custom_label.set_placeholder_text("e.g. Run, Ult, Weapon 4, BulletJump")
        self.entry_custom_label.connect("changed", self._on_custom_label_changed)
        self.editor_form_box.append(self.entry_custom_label)

        target_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        lbl_target = Gtk.Label(label="Target UInput:")
        lbl_target.add_css_class("dim-label")
        target_row.append(lbl_target)

        target_models = Gtk.StringList.new(["keyboard", "mouse", "keyboard + mouse", "gamepad"])
        self.dropdown_target = Gtk.DropDown.new(target_models, None)
        self.dropdown_target.set_hexpand(True)
        self.dropdown_target.connect("notify::selected", self._on_target_changed)
        target_row.append(self.dropdown_target)
        self.editor_form_box.append(target_row)

        btn_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_clear = Gtk.Button(label="Clear Mapping")
        btn_clear.add_css_class("ghost-btn")
        btn_clear.set_hexpand(True)
        btn_clear.connect("clicked", self._on_clear_current_key)
        btn_row.append(btn_clear)
        self.editor_form_box.append(btn_row)

        card.append(self.editor_form_box)
        return card

    def _build_special_actions_dock(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("card")

        lbl_head = Gtk.Label()
        lbl_head.set_markup("<span weight='bold' size='small' color='#f8fafc'>Special Actions &amp; Gamepad Palette</span>")
        lbl_head.set_xalign(0)
        card.append(lbl_head)

        notebook = Gtk.Notebook()
        notebook.set_vexpand(True)

        # Tab 1: Subclass Custom Actions (Hardware-specific tabs e.g. Actions, Hardware, Emulation)
        custom_pages = self._build_custom_special_actions_pages()
        if custom_pages:
            for page_title, page_widget in custom_pages:
                notebook.append_page(page_widget, Gtk.Label(label=page_title))
        else:
            custom_page = self._build_custom_special_actions_page()
            if custom_page:
                notebook.append_page(custom_page, Gtk.Label(label="Hardware"))


        # Tab 2: Universal Gamepad Button Palette
        gp_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        gp_box.set_margin_top(3)

        gp_flow = Gtk.FlowBox()
        gp_flow.set_valign(Gtk.Align.START)
        gp_flow.set_max_children_per_line(4)
        gp_flow.set_selection_mode(Gtk.SelectionMode.NONE)

        for gp_item in GAMEPAD_BUTTON_PRESETS:
            label = gp_item["label"]
            sym = gp_item["symbol"]
            desc = gp_item.get("desc", label)
            b = Gtk.Button(label=label)
            b.add_css_class("quick-tag")
            b.set_tooltip_text(f"Assign {desc} ({sym}) to selected key")
            b.connect("clicked", self._on_gamepad_btn_clicked, sym)
            gp_flow.append(b)

        gp_box.append(gp_flow)

        gp_scrolled = Gtk.ScrolledWindow()
        gp_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        gp_scrolled.set_child(gp_box)
        notebook.append_page(gp_scrolled, Gtk.Label(label="🎮 Gamepad"))

        # Tab 3: Quick Snippets
        snip_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        snip_box.set_margin_top(4)

        snip_flow = Gtk.FlowBox()
        snip_flow.set_valign(Gtk.Align.START)
        snip_flow.set_max_children_per_line(4)
        snip_flow.set_selection_mode(Gtk.SelectionMode.NONE)

        for label, insert_val, tip in QUICK_SNIPPETS:
            btn = Gtk.Button(label=label)
            btn.add_css_class("quick-tag")
            btn.set_tooltip_text(tip)
            btn.connect("clicked", self._on_quick_func_clicked, insert_val)
            snip_flow.append(btn)
        snip_box.append(snip_flow)
        notebook.append_page(snip_box, Gtk.Label(label="✂ Snippets"))

        # Tab 4: Macros (Library & Custom Macro Assignment)
        macro_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        macro_box.set_margin_top(4)
        macro_box.set_margin_start(4)
        macro_box.set_margin_end(4)

        # Macro Launcher & Header Bar
        m_top_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_tpl = Gtk.Label()
        lbl_tpl.set_markup("<span size='small' weight='bold' color='#86efac'>📜 Macro Library</span>")
        lbl_tpl.set_xalign(0)
        lbl_tpl.set_hexpand(True)
        m_top_bar.append(lbl_tpl)

        btn_open_macro_studio = Gtk.Button(label="🛠️ Open Macro Studio")
        btn_open_macro_studio.add_css_class("ghost-btn")
        btn_open_macro_studio.set_tooltip_text("Open dedicated Macro Studio to create, edit, and record macros")
        btn_open_macro_studio.connect("clicked", self._launch_macro_studio)
        m_top_bar.append(btn_open_macro_studio)

        btn_refresh_macros = Gtk.Button(label="⟳")
        btn_refresh_macros.add_css_class("ghost-btn")
        btn_refresh_macros.set_tooltip_text("Reload macros from storage")
        btn_refresh_macros.connect("clicked", lambda w: self._refresh_macros_list())
        m_top_bar.append(btn_refresh_macros)

        macro_box.append(m_top_bar)

        macro_scrolled = Gtk.ScrolledWindow()
        macro_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        macro_scrolled.set_vexpand(True)

        self.macro_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        macro_scrolled.set_child(self.macro_list_box)
        macro_box.append(macro_scrolled)

        self._populate_macros_list()

        notebook.append_page(macro_box, Gtk.Label(label="📜 Macros"))


        # Tab 5: Lighting (8 Basic Colors + Black)
        lighting_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        lighting_box.set_margin_top(6)
        lighting_box.set_margin_start(4)
        lighting_box.set_margin_end(4)

        color_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        color_row.set_halign(Gtk.Align.CENTER)

        self.swatch_buttons = {}
        for cname, cinfo in COLOR_PALETTE.items():
            btn = Gtk.Button()
            btn.add_css_class("color-swatch")
            if cname == self.selected_color_name:
                btn.add_css_class("active")
            btn.set_tooltip_text(f"{cinfo['icon']} {cname} — {cinfo['tip']}")

            # Custom inline CSS background for the swatch button
            css_provider = Gtk.CssProvider()
            border_color = "#475569" if cname == "Black" else cinfo["hex"]
            css_provider.load_from_data(f"""
                button {{
                    background-color: {cinfo['hex']};
                    border-color: {border_color};
                }}
            """.encode("utf-8"))
            btn.get_style_context().add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            btn.connect("clicked", self._on_color_swatch_clicked, cname)
            self.swatch_buttons[cname] = btn
            color_row.append(btn)

        lighting_box.append(color_row)

        # Lighting Options Bar: Target Scope Toggle & Manual Apply Button
        ctrl_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        ctrl_bar.set_halign(Gtk.Align.CENTER)

        self.chk_all_devices = Gtk.CheckButton(label="Apply to all connected devices")
        self.chk_all_devices.set_active(True)  # Default: All devices
        self.chk_all_devices.set_tooltip_text("If checked, changes lighting across all Razer keypads, keyboards, and mice.")
        self.chk_all_devices.connect("toggled", self._on_all_devices_toggled)
        ctrl_bar.append(self.chk_all_devices)

        btn_apply_rgb = Gtk.Button(label="💡 Apply Lighting")
        btn_apply_rgb.add_css_class("primary-btn")
        btn_apply_rgb.set_tooltip_text("Send selected RGB color to physical hardware immediately")
        btn_apply_rgb.connect("clicked", self._on_apply_lighting_clicked)
        ctrl_bar.append(btn_apply_rgb)

        lighting_box.append(ctrl_bar)

        notebook.append_page(lighting_box, Gtk.Label(label="💡 Lighting"))

        card.append(notebook)

        return card



    def _build_custom_special_actions_pages(self) -> Optional[List[Tuple[str, Gtk.Widget]]]:
        """Subclasses can override to return a list of (tab_name, page_widget) tuples."""
        return None

    def _build_custom_special_actions_page(self) -> Optional[Gtk.Widget]:
        """Subclasses can override to add a single device-specific hardware actions page."""
        return None


    def _build_presets_dock(self) -> Gtk.Box:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        card.add_css_class("card")

        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_p_title = Gtk.Label()
        lbl_p_title.set_markup("<span weight='bold' size='small' color='#f8fafc'>Active Profile:</span>")
        status_row.append(lbl_p_title)

        self.lbl_active_profile_status = Gtk.Label()
        self.lbl_active_profile_status.set_markup("<span color='#94a3b8' size='small'><i>none</i></span>")
        self.lbl_active_profile_status.set_hexpand(True)
        self.lbl_active_profile_status.set_xalign(0)
        status_row.append(self.lbl_active_profile_status)
        card.append(status_row)

        self.entry_preset_name = Gtk.Entry()
        self.entry_preset_name.set_placeholder_text("Preset name (e.g. gaming)")
        self.entry_preset_name.set_text(self.default_preset_name)
        card.append(self.entry_preset_name)

        p_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        btn_load_json = Gtk.Button(label="📂 Load")
        btn_load_json.add_css_class("ghost-btn")
        btn_load_json.set_tooltip_text("Open an input-remapper JSON preset")
        btn_load_json.connect("clicked", self._load_json_preset)
        p_row.append(btn_load_json)

        btn_export_json = Gtk.Button(label="💾 Save")
        btn_export_json.add_css_class("ghost-btn")
        btn_export_json.set_tooltip_text("Save keymap to preset JSON file")
        btn_export_json.connect("clicked", self._export_json_preset)
        p_row.append(btn_export_json)

        btn_apply_json = Gtk.Button(label="⚡ Apply")
        btn_apply_json.add_css_class("primary-btn")
        btn_apply_json.set_tooltip_text("Apply & activate this profile on hardware via input-remapper")
        btn_apply_json.connect("clicked", self._apply_current_preset)
        p_row.append(btn_apply_json)
        card.append(p_row)

        self.lbl_remap_count = Gtk.Label()
        self.lbl_remap_count.set_markup("<span weight='bold' size='small' color='#f8fafc'>Active Remaps (0)</span>")
        self.lbl_remap_count.set_xalign(0)
        card.append(self.lbl_remap_count)

        scrolled_list = Gtk.ScrolledWindow()
        scrolled_list.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled_list.set_vexpand(True)

        self.remap_list_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        scrolled_list.set_child(self.remap_list_box)
        card.append(scrolled_list)

        extra_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        btn_export_md = Gtk.Button(label="Export Cheat Sheet (.md)")
        btn_export_md.add_css_class("ghost-btn")
        btn_export_md.set_hexpand(True)
        btn_export_md.connect("clicked", self._export_cheatsheet_md)
        extra_row.append(btn_export_md)
        card.append(extra_row)

        return card

    # ------------------------------------------------------------------
    # Universal Input Controller & Key Recorder
    # ------------------------------------------------------------------
    def _setup_input_controller(self):
        controller = Gtk.EventControllerKey.new()
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

    def _on_record_clicked(self, widget):
        if self.is_recording_input:
            self._stop_recording(cancelled=True)
        else:
            self._start_recording()

    def _start_recording(self):
        self.is_recording_input = True
        self.btn_record_input.set_label("⏹ Press Key Combo...")
        self.btn_record_input.remove_css_class("record-btn")
        self.btn_record_input.add_css_class("recording-pulse")
        self.entry_output.set_placeholder_text("Listening for physical keystroke...")

    def _stop_recording(self, cancelled=False):
        self.is_recording_input = False
        self.btn_record_input.set_label("🔴 Record Input")
        self.btn_record_input.remove_css_class("recording-pulse")
        self.btn_record_input.add_css_class("record-btn")
        self.entry_output.set_placeholder_text("e.g. KEY_A, mouse(1), disable")

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if not self.is_recording_input:
            return False

        key_name = Gdk.keyval_name(keyval)
        if not key_name:
            return False

        # Modifiers alone (e.g. user taps Control_L, Shift_L, Alt_L, etc.)
        MOD_MAP = {
            Gdk.KEY_Control_L: "Control_L",
            Gdk.KEY_Control_R: "Control_R",
            Gdk.KEY_Shift_L: "Shift_L",
            Gdk.KEY_Shift_R: "Shift_R",
            Gdk.KEY_Alt_L: "Alt_L",
            Gdk.KEY_Alt_R: "Alt_R",
            Gdk.KEY_Super_L: "Super_L",
            Gdk.KEY_Super_R: "Super_R",
            Gdk.KEY_Meta_L: "Alt_L",
            Gdk.KEY_Meta_R: "Alt_R",
        }

        # Normalize special key names to standard input-remapper symbols
        if keyval == Gdk.KEY_space:
            key_name = "space"
        elif keyval in MOD_MAP:
            key_name = MOD_MAP[keyval]

        # If a non-modifier key is pressed while holding modifier keys
        modifiers = []
        if keyval not in MOD_MAP:
            if state & Gdk.ModifierType.CONTROL_MASK:
                modifiers.append("Control_L")
            if state & Gdk.ModifierType.ALT_MASK:
                modifiers.append("Alt_L")
            if state & Gdk.ModifierType.SHIFT_MASK:
                modifiers.append("Shift_L")
            if state & Gdk.ModifierType.SUPER_MASK:
                modifiers.append("Super_L")

        if modifiers:
            combo_str = " + ".join(modifiers + [key_name])
        else:
            combo_str = key_name

        if self.selected_key_id:
            self.entry_output.set_text(combo_str)
            self.state[self.selected_key_id]["output"] = combo_str
            self._update_all_visuals()

        self._stop_recording()
        return True


    # ------------------------------------------------------------------
    # Universal Event Handlers
    # ------------------------------------------------------------------
    def _on_key_clicked(self, widget, key_id):
        if self.is_recording_input:
            self._stop_recording(cancelled=True)
        self.selected_key_id = key_id
        self._update_all_visuals()

    def _on_quick_func_clicked(self, widget, insert_val):
        if not self.selected_key_id:
            return
        if self.is_recording_input:
            self._stop_recording(cancelled=True)
        self.entry_output.set_text(insert_val)
        self.state[self.selected_key_id]["output"] = insert_val
        self._update_all_visuals()

    def _on_gamepad_btn_clicked(self, widget, symbol_str):
        if not self.selected_key_id:
            return
        if self.is_recording_input:
            self._stop_recording(cancelled=True)
        self.entry_output.set_text(symbol_str)
        self.state[self.selected_key_id]["output"] = symbol_str
        self.state[self.selected_key_id]["target"] = "gamepad"
        self._update_all_visuals()

    def _on_custom_label_changed(self, widget):
        if not self.selected_key_id:
            return
        new_label = self.entry_custom_label.get_text()
        self.state[self.selected_key_id]["custom_name"] = new_label
        self._update_all_visuals(refresh_editor_entry=False)

    # ------------------------------------------------------------------
    # Macro Builder & Template Handlers
    # ------------------------------------------------------------------
    def _on_assign_macro_template(self, widget, tpl: Dict[str, Any]):
        if not self.selected_key_id:
            if hasattr(self, "toast"):
                self.toast.show_message("Select a key on the hardware canvas first!", icon="⚠️")
            return
        if self.is_recording_input:
            self._stop_recording(cancelled=True)

        macro_code = tpl["macro"]
        macro_label = tpl.get("label", tpl["title"])
        mapping_type = tpl.get("mapping_type", "macro")

        self.entry_output.set_text(macro_code)
        self.entry_custom_label.set_text(macro_label)
        self.state[self.selected_key_id]["output"] = macro_code
        self.state[self.selected_key_id]["custom_name"] = macro_label
        self.state[self.selected_key_id]["mapping_type"] = mapping_type
        self.state[self.selected_key_id]["target"] = "keyboard"
        self._update_all_visuals()

        if hasattr(self, "toast"):
            self.toast.show_message(f"Assigned macro '{tpl['title']}' to {self.state[self.selected_key_id]['name']}", icon=tpl.get("icon", "📜"))

    def _populate_macros_list(self):

        while True:
            child = self.macro_list_box.get_first_child()
            if not child:
                break
            self.macro_list_box.remove(child)

        all_macros = load_all_macros()
        if not all_macros:
            empty_lbl = Gtk.Label(label="No macros available.\nClick 'Open Macro Studio' to create one.")
            empty_lbl.add_css_class("dim-label")
            empty_lbl.set_vexpand(True)
            self.macro_list_box.append(empty_lbl)
            return

        for tpl in all_macros:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            row.add_css_class("remap-row")
            tip_desc = tpl.get("desc", tpl.get("title", ""))
            row.set_tooltip_text(f"{tpl['title']}: {tip_desc}")

            lbl_text = Gtk.Label()
            esc_title = GLib.markup_escape_text(tpl["title"])
            esc_cat = GLib.markup_escape_text(tpl.get("category", "General"))
            esc_badge = GLib.markup_escape_text(tpl.get("label", tpl["title"]))
            tag_badge = " <span size='6500' color='#22c55e'>[Built-In]</span>" if tpl.get("built_in") else " <span size='6500' color='#94a3b8'>[Custom]</span>"
            lbl_text.set_markup(f"<span size='small' weight='bold' color='#f8fafc'>{esc_title}</span>{tag_badge}\n<span size='7500' color='#94a3b8'>Category: <b>{esc_cat}</b> | Badge: <tt>{esc_badge}</tt></span>")
            lbl_text.set_xalign(0)
            lbl_text.set_hexpand(True)
            row.append(lbl_text)

            btn_assign = Gtk.Button(label="Assign")
            btn_assign.add_css_class("primary-btn")
            btn_assign.connect("clicked", self._on_assign_macro_template, tpl)
            row.append(btn_assign)

            self.macro_list_box.append(row)


    def _refresh_macros_list(self):
        self._populate_macros_list()
        if hasattr(self, "toast"):
            self.toast.show_message("Macro list reloaded", icon="⟳")

    def _launch_macro_studio(self, widget):
        import subprocess
        macro_script = Path(__file__).resolve().parent.parent / "strop_macro.py"
        try:
            subprocess.Popen([sys.executable, str(macro_script)])
        except Exception as e:
            alert = Gtk.AlertDialog(
                message="Could not launch Macro Studio",
                detail=str(e)
            )
            alert.show(self)



    # ------------------------------------------------------------------
    # Lighting & Color Picker Handlers
    # ------------------------------------------------------------------
    def _on_color_swatch_clicked(self, widget, color_name: str):
        self.selected_color_name = color_name
        for cname, btn in self.swatch_buttons.items():
            if cname == color_name:
                btn.add_css_class("active")
            else:
                btn.remove_css_class("active")
        self._apply_lighting_to_hardware()

    def _on_all_devices_toggled(self, widget):
        self.apply_color_all_devices = widget.get_active()

    def _on_apply_lighting_clicked(self, widget):
        self._apply_lighting_to_hardware()

    def _apply_lighting_to_hardware(self):
        cinfo = COLOR_PALETTE.get(self.selected_color_name, COLOR_PALETTE["Green"])
        rgb = cinfo["rgb"]
        dev_name = self.detected_device.get("name", self.default_device_name)
        lighting = get_lighting_engine()

        try:
            if self.apply_color_all_devices:
                lighting.apply_all_connected_devices_lighting(rgb)
                target_desc = "all connected Razer devices"
            else:
                lighting.apply_device_lighting(dev_name, rgb)
                target_desc = dev_name

            if hasattr(self, "toast"):
                self.toast.show_message(f"Set {self.selected_color_name} lighting on {target_desc}", icon=cinfo.get("icon", "💡"))
        except Exception as e:
            logger.error(f"Failed to apply lighting: {e}")

    def _on_output_changed(self, widget):
        if not self.selected_key_id:
            return
        new_text = self.entry_output.get_text()
        self.state[self.selected_key_id]["output"] = new_text
        self._update_all_visuals(refresh_editor_entry=False)

    def _on_target_changed(self, dropdown, param):
        if not self.selected_key_id:
            return
        selected_item = dropdown.get_selected_item()
        target = selected_item.get_string() if selected_item else "keyboard"
        self.state[self.selected_key_id]["target"] = target

    def _on_clear_current_key(self, widget):
        if not self.selected_key_id:
            return
        if self.is_recording_input:
            self._stop_recording(cancelled=True)
        self.state[self.selected_key_id]["output"] = ""
        self.state[self.selected_key_id]["custom_name"] = ""
        self.entry_output.set_text("")
        self.entry_custom_label.set_text("")
        self._update_all_visuals()

    def _on_reset_all(self, widget):
        alert = Gtk.AlertDialog(
            message="Reset all key assignments?",
            detail="This will clear all customized bindings and labels back to factory stock."
        )
        alert.set_buttons(["Cancel", "Reset All"])
        alert.set_default_button(0)
        alert.set_cancel_button(0)

        def on_alert_response(dialog, result):
            try:
                choice = dialog.choose_finish(result)
                if choice == 1:
                    for s in self.state.values():
                        s["output"] = ""
                        s["custom_name"] = ""
                    if self.selected_key_id:
                        self.entry_output.set_text("")
                        self.entry_custom_label.set_text("")
                    self._update_all_visuals()
            except Exception:
                pass

        alert.choose(self, None, on_alert_response)

    def _on_delete_remap_item(self, widget, kid):
        self.state[kid]["output"] = ""
        self.state[kid]["custom_name"] = ""
        if self.selected_key_id == kid:
            self.entry_output.set_text("")
            self.entry_custom_label.set_text("")
        self._update_all_visuals()


    def _launch_hud_overlay(self, widget):
        import subprocess
        overlay_script = Path(__file__).resolve().parent.parent / "strop_hud.py"
        try:
            subprocess.Popen([sys.executable, str(overlay_script)])
        except Exception as e:
            alert = Gtk.AlertDialog(
                message="Could not launch HUD Overlay",
                detail=str(e)
            )
            alert.show(self)

    # ------------------------------------------------------------------
    # Visual Synchronization
    # ------------------------------------------------------------------
    def _format_display_text(self, output_str: str) -> str:
        trimmed = (output_str or "").strip()
        if not trimmed:
            return ""
        gp_text = parse_gamepad_display_text(trimmed)
        if gp_text:
            return gp_text
        if trimmed.lower() == "disable":
            return "disable"
        if any(c in trimmed for c in ("+", "(", ")", ",", '"', "'", ";", ".")):
            return "macro"
        if "macro" in trimmed.lower() or "\n" in trimmed:
            return "macro"
        return trimmed

    def _update_all_visuals(self, refresh_editor_entry=True):
        # 1. Update Hardware Buttons
        for kid, s in self.state.items():
            if kid not in self.button_widgets:
                continue
            w_info = self.button_widgets[kid]
            btn = w_info.get("btn") or w_info.get("box")
            lbl = w_info.get("lbl")
            raw_label = w_info.get("raw_label", "")

            if self.selected_key_id == kid:
                btn.add_css_class("selected")
            else:
                btn.remove_css_class("selected")

            has_output = bool(s.get("output") and s["output"].strip())
            custom_name = s.get("custom_name", "").strip()
            if has_output or custom_name:
                btn.add_css_class("assigned")
                disp_text = custom_name if custom_name else self._format_display_text(s.get("output", ""))
                if lbl:
                    lbl.set_markup(f"<span weight='bold' size='small'>{raw_label}</span>\n<span size='7500' weight='semibold' color='#86efac'>→ {GLib.markup_escape_text(disp_text)}</span>")
            else:
                btn.remove_css_class("assigned")
                if lbl:
                    lbl.set_markup(f"<span weight='bold' size='small'>{raw_label}</span>")

        # 2. Update Editor Form
        if not self.selected_key_id:
            self.editor_empty_lbl.set_visible(True)
            self.editor_form_box.set_visible(False)
        else:
            self.editor_empty_lbl.set_visible(False)
            self.editor_form_box.set_visible(True)
            s = self.state[self.selected_key_id]
            self.ed_key_name.set_markup(f"<span size='small' weight='bold' color='#86efac'>{GLib.markup_escape_text(s['name'])}</span>")

            code_desc = f"evdev {s['code']}" if s.get("code") is not None else "driver dependent"
            self.ed_key_code.set_text(code_desc)

            if refresh_editor_entry:
                self.entry_output.set_text(s.get("output", ""))
                self.entry_custom_label.set_text(s.get("custom_name", ""))

            idx = 0
            if s.get("target") == "mouse":
                idx = 1
            elif s.get("target") == "keyboard + mouse":
                idx = 2
            elif s.get("target") == "gamepad":
                idx = 3
            self.dropdown_target.set_selected(idx)

        # 3. Update Remaps List & Badges
        assigned_items = [
            (kid, s) for kid, s in self.state.items()
            if (s.get("output") and s["output"].strip()) or (s.get("custom_name") and s["custom_name"].strip())
        ]
        count = len(assigned_items)

        self.count_badge.set_text(f"{count} remapped")
        if count > 0:
            self.count_badge.remove_css_class("badge-stock")
            self.count_badge.add_css_class("badge-assigned")
        else:
            self.count_badge.remove_css_class("badge-assigned")
            self.count_badge.add_css_class("badge-stock")

        self.lbl_remap_count.set_markup(f"<span weight='bold' size='small' color='#f8fafc'>Active Remaps ({count})</span>")

        while True:
            child = self.remap_list_box.get_first_child()
            if not child:
                break
            self.remap_list_box.remove(child)

        if not assigned_items:
            empty_lbl = Gtk.Label(label="No keys remapped.\nAll inputs using hardware defaults.")
            empty_lbl.add_css_class("dim-label")
            empty_lbl.set_vexpand(True)
            self.remap_list_box.append(empty_lbl)
        else:
            for kid, s in assigned_items:
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row.add_css_class("remap-row")
                c_name = s.get("custom_name", "").strip()
                out_sym = s.get("output", "").strip()
                tip_text = f"{s['name']}: {c_name} ({out_sym})" if c_name else f"{s['name']}: {out_sym}"
                row.set_tooltip_text(tip_text)

                disp_text = c_name if c_name else self._format_display_text(out_sym)

                lbl_from = Gtk.Label()
                lbl_from.set_markup(f"<span size='small' weight='semibold' color='#94a3b8'>{GLib.markup_escape_text(s['name'])}</span>")
                row.append(lbl_from)

                lbl_arrow = Gtk.Label()
                lbl_arrow.set_markup(f"<span size='small' color='#86efac'>→ <b>{GLib.markup_escape_text(disp_text)}</b></span>")
                lbl_arrow.set_hexpand(True)
                lbl_arrow.set_xalign(0)
                row.append(lbl_arrow)

                btn_del = Gtk.Button(label="✕")
                btn_del.add_css_class("danger-btn")
                btn_del.connect("clicked", self._on_delete_remap_item, kid)
                row.append(btn_del)

                self.remap_list_box.append(row)

    # ------------------------------------------------------------------
    # Preset Matching, Loading, Direct Saving, and Applying
    # ------------------------------------------------------------------
    def _match_preset_key(self, code: Optional[int], name: str) -> Optional[str]:
        """Robustly matches an input-remapper JSON mapping to a state key."""
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

    def _load_preset_file_data(self, load_path: str) -> Tuple[int, int]:
        with open(load_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("File is not a valid input-remapper JSON list.")

        for s in self.state.values():
            s["output"] = ""
            s["target"] = "keyboard"

        matched_count = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            input_comb = item.get("input_combination", [])
            if not input_comb or not isinstance(input_comb, list):
                continue
            first_input = input_comb[0]
            code = first_input.get("code")
            output_sym = item.get("output_symbol", "")
            target = item.get("target_uinput", "keyboard")
            name = item.get("name", "")
            custom_name = item.get("custom_name", "")

            matched_key = self._match_preset_key(code, name)
            if matched_key:
                self.state[matched_key]["output"] = output_sym
                self.state[matched_key]["target"] = target
                self.state[matched_key]["custom_name"] = custom_name
                matched_count += 1


        preset_name = Path(load_path).stem
        self.entry_preset_name.set_text(preset_name)
        if self.selected_key_id:
            self.entry_output.set_text(self.state[self.selected_key_id].get("output", ""))

        self._update_all_visuals()
        return matched_count, len(data)

    def _auto_load_active_profile(self):
        dev_name = self.detected_device.get("name", self.default_device_name)
        active_p = get_active_profile(dev_name)
        if not active_p:
            return

        self.lbl_active_profile_status.set_markup(f"<span color='#86efac' weight='bold'>⚡ {active_p}</span>")
        dev_dir = get_device_presets_dir(dev_name)
        presets = list(dev_dir.glob("*.json"))
        for pfile in presets:
            if pfile.stem == active_p:
                try:
                    self._load_preset_file_data(str(pfile))
                except Exception:
                    pass
                break

    def _save_preset_direct(self, preset_name: str) -> Optional[Path]:
        dev_name = self.detected_device.get("name", self.default_device_name)
        return save_device_preset(dev_name, preset_name, self.state, self.detected_device)

    def _apply_current_preset(self, widget):
        pname = self.entry_preset_name.get_text().strip() or self.default_preset_name
        dev_name = self.detected_device.get("name", self.default_device_name)

        # Save preset directly to disk first
        self._save_preset_direct(pname)

        success, msg = apply_profile(dev_name, pname)
        if success:
            self.lbl_active_profile_status.set_markup(f"<span color='#86efac' weight='bold'>⚡ {pname}</span>")
        else:
            self.lbl_active_profile_status.set_markup(f"<span color='#f87171' weight='bold'>⚠️ Failed</span>")

        # Apply physical OpenRazer lighting using the user's selected color
        try:
            cinfo = COLOR_PALETTE.get(self.selected_color_name, COLOR_PALETTE["Green"])
            rgb = cinfo["rgb"]
            lighting = get_lighting_engine()
            if self.apply_color_all_devices:
                lighting.apply_all_connected_devices_lighting(rgb)
            else:
                lighting.apply_device_lighting(dev_name, rgb)
        except Exception:
            pass

        # Non-blocking smooth in-app toast notification with daemon feedback
        if hasattr(self, "toast"):
            icon = "⚡" if success else "⚠️"
            self.toast.show_message(msg, icon=icon)
        self._update_all_visuals()







    def _load_json_preset(self, widget):
        dev_name = self.detected_device.get("name", self.default_device_name)
        dev_dir = get_device_presets_dir(dev_name)

        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Load input-remapper Preset (.json)")
        file_dialog.set_initial_folder(Gio.File.new_for_path(str(dev_dir)))

        json_filter = Gtk.FileFilter()
        json_filter.set_name("JSON Presets (*.json)")
        json_filter.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(json_filter)
        file_dialog.set_filters(filters)

        def on_open_response(dialog, result):
            try:
                gfile = dialog.open_finish(result)
                if not gfile:
                    return
                load_path = gfile.get_path()
                matched, total = self._load_preset_file_data(load_path)
                alert = Gtk.AlertDialog(
                    message="Preset Loaded Successfully!",
                    detail=f"Loaded: {Path(load_path).name}\n{matched}/{total} input(s) mapped."
                )
                alert.show(self)
            except Exception as e:
                alert = Gtk.AlertDialog(message="Load Error", detail=str(e))
                alert.show(self)

        file_dialog.open(self, None, on_open_response)

    def _export_json_preset(self, widget):
        pname = self.entry_preset_name.get_text().strip() or self.default_preset_name
        dev_name = self.detected_device.get("name", self.default_device_name)
        save_file = self._save_preset_direct(pname)
        if save_file:
            alert = Gtk.AlertDialog(message="Preset Saved", detail=f"Saved to: {save_file}")
            alert.show(self)
        else:
            alert = Gtk.AlertDialog(message="Save Error", detail="Failed to write preset file.")
            alert.show(self)

    def _export_cheatsheet_md(self, widget):
        preset_name = self.entry_preset_name.get_text().strip() or self.default_preset_name
        dev_name = self.detected_device.get("name", self.default_device_name)
        md = f"# {dev_name} Remap — {preset_name}\n\n"
        md += "| Physical Input | Stock Function | Remapped To | Target |\n"
        md += "| :--- | :--- | :--- | :--- |\n"

        for kid, s in self.state.items():
            stock = f"evdev {s['code']}" if s.get("code") is not None else "device-dependent"
            mapped = f"**{s['output']}**" if s.get("output") and s["output"].strip() else "_unchanged_"
            target = s.get("target", "-") if s.get("output") and s["output"].strip() else "-"
            md += f"| {s['name']} | {stock} | {mapped} | {target} |\n"

        file_dialog = Gtk.FileDialog()
        file_dialog.set_title("Save Markdown Cheat Sheet")
        file_dialog.set_initial_name(f"{preset_name.replace(' ', '-')}-cheatsheet.md")

        def on_md_save_response(dialog, result):
            try:
                gfile = dialog.save_finish(result)
                if not gfile:
                    return
                save_path = gfile.get_path()
                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(md)

                alert = Gtk.AlertDialog(
                    message="Cheat sheet exported!",
                    detail=f"Saved cheat sheet to:\n{save_path}"
                )
                alert.show(self)
            except Exception as e:
                alert = Gtk.AlertDialog(message="Export Error", detail=str(e))
                alert.show(self)

        file_dialog.save(self, None, on_md_save_response)
