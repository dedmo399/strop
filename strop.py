#!/usr/bin/env python3
"""
Strop — Unified Razer Linux Peripheral Suite Hub
Native Linux GTK4 Dashboard for managing Razer keypads, keyboards, mice, and in-game HUDs.
Zero external dependencies - uses standard Python 3 and Ubuntu PyGObject (GTK4).
Supports all 230+ OpenRazer input devices.
"""

import sys
import os
import subprocess
from pathlib import Path

# Ensure strop_core can be imported regardless of execution working directory
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

from strop_core.device import scan_all_connected_devices, clean_device_display_name
from strop_core.presets import (
    get_presets_base_dir, get_active_profile, get_all_active_profiles,
    list_device_presets, check_daemon_status,
    run_profile_operation_async, check_profile_state_async
)

from strop_core.theme import apply_theme, show_about_dialog
from strop_core.catalog import get_device_catalog, list_devices_by_category, get_archetype_for_device

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gtk, Gdk, GLib, Gio, GdkPixbuf


class StropCatalogDialog(Gtk.Window):
    """Dialog allowing users to browse and launch studios for all 230+ OpenRazer models."""
    def __init__(self, parent):
        super().__init__(title="OpenRazer Hardware Catalog (230+ Devices)")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(700, 520)
        self.add_css_class("hub-window")

        self.all_devices = get_device_catalog()
        self.filtered_devices = list(self.all_devices)
        self._build_ui()

    def _build_ui(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(16)
        box.set_margin_end(16)
        self.set_child(box)

        # Header
        lbl_title = Gtk.Label()
        lbl_title.set_markup(f"<span size='medium' weight='bold' color='#f8fafc'>Supported OpenRazer Devices <span color='#22c55e'>({len(self.all_devices)} Total)</span></span>")
        lbl_title.set_xalign(0)
        box.append(lbl_title)

        # Filter bar
        filter_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search Razer models (e.g. Naga, Huntsman, Tartarus, Basilisk)...")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", self._on_search_changed)
        filter_bar.append(self.search_entry)

        self.cat_dropdown = Gtk.DropDown.new_from_strings(["All Categories", "Keypads", "Keyboards", "Mice", "Laptops"])
        self.cat_dropdown.connect("notify::selected", self._on_cat_changed)
        filter_bar.append(self.cat_dropdown)

        box.append(filter_bar)

        # Scrolled device list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_hexpand(True)
        scrolled.set_vexpand(True)
        box.append(scrolled)

        self.list_box = Gtk.ListBox()
        self.list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        scrolled.set_child(self.list_box)

        self._populate_list()

    def _populate_list(self):
        while True:
            row = self.list_box.get_row_at_index(0)
            if row is None:
                break
            self.list_box.remove(row)

        for dev in self.filtered_devices:
            row = Gtk.ListBoxRow()
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            card.add_css_class("assigned-row")
            card.set_margin_bottom(2)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            lbl_name = Gtk.Label()
            lbl_name.set_markup(f"<span weight='bold' color='#f8fafc'>{dev['name']}</span>")
            lbl_name.set_xalign(0)
            info_box.append(lbl_name)

            desc = dev.get("description", dev.get("archetype", "Standard Razer Device"))
            esc_desc = GLib.markup_escape_text(desc)
            lbl_meta = Gtk.Label()
            lbl_meta.set_markup(f"<span size='small' color='#94a3b8'>Category: <b>{dev['category'].title()}</b> | <b>{esc_desc}</b> | PID: <tt>{dev.get('pid', 'N/A')}</tt></span>")
            lbl_meta.set_xalign(0)
            info_box.append(lbl_meta)


            card.append(info_box)

            btn_launch = Gtk.Button(label="Open Studio")
            btn_launch.add_css_class("ghost-btn")
            btn_launch.set_valign(Gtk.Align.CENTER)
            btn_launch.connect("clicked", lambda w, dname=dev["name"]: self._launch_studio_and_close(dname))
            card.append(btn_launch)

            row.set_child(card)
            self.list_box.append(row)

    def _on_search_changed(self, entry):
        self._apply_filters()

    def _on_cat_changed(self, dropdown, param):
        self._apply_filters()

    def _apply_filters(self):
        query = self.search_entry.get_text().strip().lower()
        cat_idx = self.cat_dropdown.get_selected()
        cat_map = {0: None, 1: "keypad", 2: "keyboard", 3: "mouse", 4: "laptop"}
        selected_cat = cat_map.get(cat_idx)

        res = self.all_devices
        if selected_cat:
            res = [d for d in res if d["category"] == selected_cat]
        if query:
            res = [d for d in res if query in d["name"].lower() or query in d.get("description", "").lower() or query in d.get("archetype", "").lower() or query in str(d.get("pid", "")).lower()]

        self.filtered_devices = res
        self._populate_list()


    def _launch_studio_and_close(self, device_name: str):
        script_path = Path(__file__).parent / "strop_studio.py"
        try:
            subprocess.Popen([sys.executable, str(script_path), f"--device={device_name}"])
            self.close()
        except Exception as e:
            alert = Gtk.AlertDialog(message="Launch Failed", detail=str(e))
            alert.show(self)


class StropHubWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Strop — Razer Linux Suite")
        self.set_default_size(820, 640)
        self.add_css_class("hub-window")

        self.connected_devices = scan_all_connected_devices()
        self.selected_dev_name = ""
        self.available_presets_for_selected = []
        self.profile_operation_pending = False

        self._build_ui()

    def _build_ui(self):
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scrolled)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        main_box.set_margin_top(14)
        main_box.set_margin_bottom(14)
        main_box.set_margin_start(18)
        main_box.set_margin_end(18)
        scrolled.set_child(main_box)

        # 1. Header with Logo & Brand
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        header.set_valign(Gtk.Align.CENTER)

        icon_path = Path(__file__).parent / "assets" / "strop_icon.png"
        if icon_path.exists():
            try:
                texture = Gdk.Texture.new_from_filename(str(icon_path))
                logo_img = Gtk.Image.new_from_paintable(texture)
                logo_img.set_pixel_size(56)
                header.append(logo_img)
            except Exception:
                pass


        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title_box.set_hexpand(True)
        lbl_title = Gtk.Label()
        lbl_title.set_markup("<span size='large' weight='bold' color='#f8fafc'>STROP <span color='#22c55e'>SUITE</span></span>")
        lbl_title.set_xalign(0)
        title_box.append(lbl_title)

        lbl_sub = Gtk.Label(label="Precision Remap Studios & In-Game HUD Overlays for all 230+ OpenRazer Peripherals")
        lbl_sub.add_css_class("dim-text")
        lbl_sub.set_xalign(0)
        title_box.append(lbl_sub)
        header.append(title_box)

        btn_about = Gtk.Button(label="ℹ️ About Strop")
        btn_about.add_css_class("ghost-btn")
        btn_about.set_valign(Gtk.Align.CENTER)
        btn_about.set_tooltip_text("About Strop Suite & OpenRazer Integration")
        btn_about.connect("clicked", lambda w: show_about_dialog(self))
        header.append(btn_about)

        main_box.append(header)

        # 1b. Background Daemon Status Alert (shown if input-remapper is stopped or not installed)
        self.daemon_banner = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.daemon_banner.set_margin_top(2)
        self.daemon_banner.set_margin_bottom(2)
        main_box.append(self.daemon_banner)
        self._refresh_daemon_banner()

        # 2. Connected Hardware Banner with Live Active Profile Badges
        self.hardware_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.hardware_box.set_valign(Gtk.Align.CENTER)
        main_box.append(self.hardware_box)
        self._refresh_hardware_banner()


        # 3. Dedicated Active Profile Manager & Quick Apply Bar
        profile_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        profile_card.add_css_class("dock-card")

        p_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_p_title = Gtk.Label()
        lbl_p_title.set_markup("<span weight='bold' size='small' color='#86efac'>⚡ Profile &amp; Settings Manager</span>")
        lbl_p_title.set_xalign(0)
        lbl_p_title.set_hexpand(True)
        p_header.append(lbl_p_title)

        self.lbl_profile_status = Gtk.Label(label="")
        self.lbl_profile_status.add_css_class("dim-text")
        self.lbl_profile_status.set_xalign(1)
        p_header.append(self.lbl_profile_status)
        profile_card.append(p_header)

        p_controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        # Device selector dropdown
        dev_strings = [d.get("clean_name", d["name"]) for d in self.connected_devices] or ["(No Razer devices connected)"]
        self.hub_dev_dropdown = Gtk.DropDown.new_from_strings(dev_strings)
        self.hub_dev_dropdown.connect("notify::selected", self._on_hub_dev_selected)
        p_controls.append(self.hub_dev_dropdown)

        # Preset selector dropdown
        self.hub_preset_dropdown = Gtk.DropDown.new_from_strings(["(Select Device)"])
        self.hub_preset_dropdown.set_hexpand(True)
        p_controls.append(self.hub_preset_dropdown)

        self.btn_profile_apply = Gtk.Button(label="⚡ Apply Settings")
        self.btn_profile_apply.add_css_class("primary-btn")
        self.btn_profile_apply.set_tooltip_text("Apply the selected saved profile")
        self.btn_profile_apply.connect("clicked", self._on_hub_apply_clicked)
        p_controls.append(self.btn_profile_apply)

        self.btn_profile_stop = Gtk.Button(label="■ Stop")
        self.btn_profile_stop.add_css_class("ghost-btn")
        self.btn_profile_stop.set_tooltip_text("Stop injection for the selected device")
        self.btn_profile_stop.connect("clicked", self._on_hub_stop_clicked)
        p_controls.append(self.btn_profile_stop)

        profile_card.append(p_controls)
        main_box.append(profile_card)

        # Initial populate of presets for selected device
        if self.connected_devices:
            self._update_hub_preset_list(self.connected_devices[0]["name"])

        # 4. Apps Grid (6 Launch Cards in 3x2 grid)
        grid = Gtk.Grid()
        grid.set_row_spacing(10)
        grid.set_column_spacing(10)
        grid.set_hexpand(True)
        grid.set_vexpand(True)
        main_box.append(grid)

        # Card 1: Keypad Studio (Tartarus / Orbweaver)
        c1 = self._create_app_card(
            title="🎮 Keypad Studio",
            desc="Ergonomic 20-key matrix builder with live combo capture, macros, analog stick emulation, and input-remapper presets.",
            btn_label="Launch Keypad Studio",
            script="strop_keypad.py"
        )
        grid.attach(c1, 0, 0, 1, 1)

        # Card 2: Keyboard Studio (BlackWidow / Huntsman)
        c2 = self._create_app_card(
            title="⌨️ Keyboard Studio",
            desc="Full-size 108-key, TKL, 75%, and 60% keyboard studios with WASD analog joystick mapping and digital media roller.",
            btn_label="Launch Keyboard Studio",
            script="strop_keyboard.py"
        )
        grid.attach(c2, 1, 0, 1, 1)

        # Card 3: Mouse Studio (Naga / Basilisk / Viper / DeathAdder)
        c3 = self._create_app_card(
            title="🖱️ Mouse Studio",
            desc="Multi-plate mouse configurator for Naga 12-Grid MMO, Basilisk FPS clutch, Viper Ambi, and DeathAdder ergonomics.",
            btn_label="Launch Mouse Studio",
            script="strop_mouse.py"
        )
        grid.attach(c3, 2, 0, 1, 1)

        # Card 4: Dedicated Macro Studio
        c4 = self._create_app_card(
            title="📜 Macro Studio",
            desc="Visual macro sequence timeline builder, millisecond delay editor, turbo loops, and custom combo library.",
            btn_label="Launch Macro Studio",
            script="strop_macro.py"
        )
        grid.attach(c4, 0, 1, 1, 1)

        # Card 5: In-Game HUD Overlay
        c5 = self._create_app_card(
            title="🖥️ In-Game HUD Overlay",
            desc="Frameless, semi-transparent floating heads-up display showing active mappings & gamepad badges above full-screen games.",
            btn_label="Launch HUD Overlay",
            script="strop_hud.py"
        )
        grid.attach(c5, 1, 1, 1, 1)

        # Card 6: OpenRazer Catalog Browser (230+ Devices)
        c6 = self._create_catalog_card()
        grid.attach(c6, 2, 1, 1, 1)


    def _refresh_daemon_banner(self):
        while True:
            child = self.daemon_banner.get_first_child()
            if not child:
                break
            self.daemon_banner.remove(child)

        status, msg = check_daemon_status()
        if status == "running":
            self.daemon_banner.set_visible(False)
            return

        self.daemon_banner.set_visible(True)
        alert_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        alert_card.set_hexpand(True)

        if status == "not_installed":
            alert_card.add_css_class("alert-warning")
            lbl_icon = Gtk.Label(label="⚠️")
            lbl_text = Gtk.Label()
            lbl_text.set_markup("<b>Input-Remapper Missing:</b> Install <code>input-remapper</code> to apply macros and remaps to hardware.")
        else:
            alert_card.add_css_class("alert-warning")
            lbl_icon = Gtk.Label(label="⚡")
            lbl_text = Gtk.Label()
            lbl_text.set_markup("<b>Remapping Daemon Inactive:</b> Run <code>sudo systemctl start input-remapper</code> in terminal to activate hardware mapping.")

        lbl_text.set_xalign(0)
        lbl_text.set_hexpand(True)
        alert_card.append(lbl_icon)
        alert_card.append(lbl_text)

        btn_retry = Gtk.Button(label="Check Again")
        btn_retry.add_css_class("ghost-btn")
        btn_retry.connect("clicked", lambda w: self._refresh_daemon_banner())
        alert_card.append(btn_retry)

        self.daemon_banner.append(alert_card)

    def _refresh_hardware_banner(self):
        while True:
            child = self.hardware_box.get_first_child()
            if not child:
                break
            self.hardware_box.remove(child)

        lbl_dev_title = Gtk.Label()
        lbl_dev_title.set_markup("<span weight='bold' size='small' color='#94a3b8'>Hardware:</span>")
        self.hardware_box.append(lbl_dev_title)

        if self.connected_devices:
            for d in self.connected_devices:
                badge = Gtk.Button()
                dev_clean = d.get("clean_name", d["name"])
                active_prof = get_active_profile(d["name"])
                prof_str = f" [Last Strop: {active_prof}]" if active_prof else ""

                badge.set_child(Gtk.Label.new(f"🟢 {dev_clean}{prof_str}"))
                badge.add_css_class("badge-device")
                badge.set_tooltip_text(f"Hardware:\n{dev_clean}\nLast profile applied by Strop: {active_prof or 'None recorded'}\nBackend state is shown in the profile manager.\n\nScancode Capabilities Hash:\n{d['hash']}\n\nClick to launch studio!")
                badge.connect("clicked", lambda w, dev=d: self._launch_studio_for_device(dev["name"]))
                self.hardware_box.append(badge)
        else:
            no_dev = Gtk.Label()
            no_dev.set_markup("<span color='#94a3b8'>No Razer USB devices detected. Connect a device or browse the </span><span color='#86efac'>230+ Device Catalog</span><span color='#94a3b8'> below.</span>")
            self.hardware_box.append(no_dev)

        btn_rescan = Gtk.Button(label="⟳ Rescan")
        btn_rescan.add_css_class("ghost-btn")
        btn_rescan.connect("clicked", self._on_rescan_clicked)
        btn_rescan.set_halign(Gtk.Align.END)
        btn_rescan.set_hexpand(True)
        self.hardware_box.append(btn_rescan)


    def _on_hub_dev_selected(self, dropdown, param):
        idx = dropdown.get_selected()
        if idx < len(self.connected_devices):
            dev_name = self.connected_devices[idx]["name"]
            self._update_hub_preset_list(dev_name)

    def _update_hub_preset_list(self, device_name: str):
        self.selected_dev_name = device_name
        preset_names = list_device_presets(device_name)
        if not preset_names:
            preset_names = ["(No saved presets found)"]

        model = Gtk.StringList.new(preset_names)
        self.hub_preset_dropdown.set_model(model)
        self.available_presets_for_selected = preset_names


        # Select currently active profile if present
        active_prof = get_active_profile(device_name)
        if active_prof and active_prof in preset_names:
            self.hub_preset_dropdown.set_selected(preset_names.index(active_prof))

        self.lbl_profile_status.set_text("Checking backend injection state…")
        check_profile_state_async(
            device_name,
            lambda state, target=device_name: self._on_profile_state_checked(target, state),
            GLib.idle_add,
        )

    def _on_profile_state_checked(self, device_name: str, state: str):
        if device_name != self.selected_dev_name:
            return
        last_profile = get_active_profile(device_name)
        last_text = f" · Last Strop profile: {last_profile}" if last_profile else " · No Strop profile recorded"
        state_text = {
            "running": "Injection running",
            "starting": "Injection starting",
            "stopped": "Injection stopped",
            "failed": "Injection failed",
            "unknown": "Injection state unknown",
        }.get(state, "Injection state unknown")
        self.lbl_profile_status.set_text(state_text + last_text)

    def _set_profile_controls_busy(self, busy: bool):
        self.profile_operation_pending = busy
        self.btn_profile_apply.set_sensitive(not busy)
        self.btn_profile_stop.set_sensitive(not busy)

    def _on_profile_operation_finished(self, operation: str, device_name: str, preset_name: str, result):
        self._set_profile_controls_busy(False)
        if device_name == self.selected_dev_name:
            if result.status == "applied":
                self.lbl_profile_status.set_text(result.message)
            elif result.status == "stopped":
                self.lbl_profile_status.set_text(result.message)
            elif result.status == "unknown":
                self.lbl_profile_status.set_text("Injection state unknown · " + result.message)
            else:
                self.lbl_profile_status.set_text(f"{operation.title()} failed · " + result.message)
        if result.status in ("applied", "stopped"):
            self._refresh_hardware_banner()
        title = {
            "applied": "Profile Applied",
            "stopped": "Profile Stopped",
            "unknown": "Profile Outcome Unknown",
            "failed": f"Profile {operation.title()} Failed",
        }.get(result.status, "Profile Operation")
        Gtk.AlertDialog(message=title, detail=result.message).show(self)

    def _on_hub_apply_clicked(self, widget):
        if self.profile_operation_pending or not self.selected_dev_name or not self.available_presets_for_selected:
            return
        idx = self.hub_preset_dropdown.get_selected()
        if idx >= len(self.available_presets_for_selected):
            return
        chosen_preset = self.available_presets_for_selected[idx]
        if chosen_preset.startswith("("):
            return

        device_name = self.selected_dev_name
        self._set_profile_controls_busy(True)
        self.lbl_profile_status.set_text(f"Applying {chosen_preset}…")
        run_profile_operation_async(
            "apply", device_name,
            lambda result: self._on_profile_operation_finished("apply", device_name, chosen_preset, result),
            GLib.idle_add, preset_name=chosen_preset,
        )

    def _on_hub_stop_clicked(self, widget):
        if self.profile_operation_pending or not self.selected_dev_name:
            return
        device_name = self.selected_dev_name
        last_profile = get_active_profile(device_name) or ""
        self._set_profile_controls_busy(True)
        self.lbl_profile_status.set_text("Stopping injection…")
        run_profile_operation_async(
            "stop", device_name,
            lambda result: self._on_profile_operation_finished("stop", device_name, last_profile, result),
            GLib.idle_add,
        )

    def _create_app_card(self, title, desc, btn_label, script):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("hub-card")
        card.set_hexpand(True)
        card.set_vexpand(True)

        lbl_t = Gtk.Label()
        lbl_t.set_markup(f"<span weight='bold' size='medium' color='#f8fafc'>{title}</span>")
        lbl_t.set_xalign(0)
        card.append(lbl_t)

        lbl_d = Gtk.Label(label=desc)
        lbl_d.add_css_class("dim-text")
        lbl_d.set_wrap(True)
        lbl_d.set_xalign(0)
        lbl_d.set_vexpand(True)
        card.append(lbl_d)

        btn = Gtk.Button(label=btn_label)
        btn.add_css_class("primary-card-btn")
        btn.connect("clicked", lambda w: self._launch_script(script))
        card.append(btn)

        return card

    def _create_catalog_card(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("hub-card")
        card.set_hexpand(True)
        card.set_vexpand(True)

        lbl_t = Gtk.Label()
        lbl_t.set_markup("<span weight='bold' size='medium' color='#f8fafc'>📚 Hardware Catalog</span>")
        lbl_t.set_xalign(0)
        card.append(lbl_t)

        lbl_d = Gtk.Label(label="Instant search & 1-click studio launch for all 230+ OpenRazer-supported input devices.")
        lbl_d.add_css_class("dim-text")
        lbl_d.set_wrap(True)
        lbl_d.set_xalign(0)
        lbl_d.set_vexpand(True)
        card.append(lbl_d)

        btn = Gtk.Button(label="Browse 230+ Devices")
        btn.add_css_class("ghost-btn")
        btn.connect("clicked", lambda w: self._open_catalog_browser())
        card.append(btn)

        return card

    def _create_folder_card(self):
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("hub-card")
        card.set_hexpand(True)
        card.set_vexpand(True)

        lbl_t = Gtk.Label()
        lbl_t.set_markup("<span weight='bold' size='medium' color='#f8fafc'>📁 Preset Storage</span>")
        lbl_t.set_xalign(0)
        card.append(lbl_t)

        lbl_d = Gtk.Label(label="Manage JSON keymaps and macro presets in your system input-remapper directory.")
        lbl_d.add_css_class("dim-text")
        lbl_d.set_wrap(True)
        lbl_d.set_xalign(0)
        lbl_d.set_vexpand(True)
        card.append(lbl_d)

        btn = Gtk.Button(label="Open Presets Folder")
        btn.add_css_class("ghost-btn")
        btn.connect("clicked", lambda w: self._open_presets_folder())
        card.append(btn)

        return card

    def _open_catalog_browser(self):
        dlg = StropCatalogDialog(self)
        dlg.present()

    def _open_presets_folder(self):
        pdir = get_presets_base_dir()
        pdir.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.Popen(["xdg-open", str(pdir)])
        except Exception:
            pass

    def _launch_studio_for_device(self, device_name: str):
        script_path = Path(__file__).parent / "strop_studio.py"
        try:
            subprocess.Popen([sys.executable, str(script_path), f"--device={device_name}"])
        except Exception as e:
            alert = Gtk.AlertDialog(message="Launch Failed", detail=str(e))
            alert.show(self)

    def _launch_script(self, script_name: str):
        script_path = Path(__file__).parent / script_name
        try:
            subprocess.Popen([sys.executable, str(script_path)])
        except Exception as e:
            alert = Gtk.AlertDialog(message="Launch Failed", detail=str(e))
            alert.show(self)

    def _on_rescan_clicked(self, widget):
        self._refresh_daemon_banner()
        self.connected_devices = scan_all_connected_devices()
        self._refresh_hardware_banner()
        dev_strings = [d.get("clean_name", d["name"]) for d in self.connected_devices] or ["(No Razer devices connected)"]
        self.hub_dev_dropdown.set_model(Gtk.StringList.new(dev_strings))
        if self.connected_devices:
            self._update_hub_preset_list(self.connected_devices[0]["name"])



def on_startup(app):
    apply_theme()


def on_activate(app):
    win = StropHubWindow(app)
    win.present()


def main():
    app = Gtk.Application(
        application_id="com.razer.strop",
        flags=Gio.ApplicationFlags.NON_UNIQUE
    )


    app.connect("startup", on_startup)
    app.connect("activate", on_activate)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
