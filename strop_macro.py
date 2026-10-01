#!/usr/bin/env python3
"""
Strop — Dedicated Macro Studio & Sequence Wizard
Visual macro editor, wizard sequence parser, timeline builder, and template library.
Supports whole sequence expressions (e.g. key_down(Control_L).wait(50).key(Up)...),
saving and organizing custom macros in ~/.config/strop/macros.json.
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure strop_core can be imported
script_dir = Path(__file__).resolve().parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib, Gio

from strop_core.theme import apply_theme
from strop_core.toast import StropToast
from strop_core.macros import (
    load_all_macros, save_or_update_macro, delete_custom_macro,
    build_macro_string, parse_macro_steps, parse_dsl_sequence, get_user_macros
)


class MacroWizardDialog(Gtk.Window):
    """Interactive Wizard Modal for creating/importing macros from sequence expressions."""
    def __init__(self, parent):
        super().__init__(title="New Macro Wizard")
        self.set_transient_for(parent)
        self.set_modal(True)
        self.set_default_size(580, 480)
        self.parent_win = parent

        content_area = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(16)
        content_area.set_margin_end(16)
        self.set_child(content_area)

        # Header Title
        lbl_head = Gtk.Label()
        lbl_head.set_markup("<span size='medium' weight='bold' color='#f8fafc'>🪄 Macro Creation Wizard</span>")
        lbl_head.set_xalign(0)
        content_area.append(lbl_head)


        lbl_desc = Gtk.Label(label="Create a macro using metadata fields or paste a full sequence expression.")
        lbl_desc.add_css_class("dim-text")
        lbl_desc.set_xalign(0)
        content_area.append(lbl_desc)

        # Form Properties Box
        form_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        form_card.add_css_class("dock-card")

        grid = Gtk.Grid()
        grid.set_column_spacing(8)
        grid.set_row_spacing(6)

        # 1. Macro Title
        lbl_t = Gtk.Label(label="Title:")
        lbl_t.set_xalign(0)
        lbl_t.add_css_class("dim-label")
        grid.attach(lbl_t, 0, 0, 1, 1)

        self.wiz_title = Gtk.Entry()
        self.wiz_title.set_placeholder_text("e.g. Slide Jump, Fast Grenade, Discord Mute")
        self.wiz_title.set_hexpand(True)
        grid.attach(self.wiz_title, 1, 0, 1, 1)

        # 2. Badge Label
        lbl_b = Gtk.Label(label="Badge:")
        lbl_b.set_xalign(0)
        lbl_b.add_css_class("dim-label")
        grid.attach(lbl_b, 2, 0, 1, 1)

        self.wiz_badge = Gtk.Entry()
        self.wiz_badge.set_placeholder_text("e.g. SlideJump")
        self.wiz_badge.set_size_request(110, -1)
        grid.attach(self.wiz_badge, 3, 0, 1, 1)

        # 3. Category
        lbl_c = Gtk.Label(label="Category:")
        lbl_c.set_xalign(0)
        lbl_c.add_css_class("dim-label")
        grid.attach(lbl_c, 0, 1, 1, 1)

        self.wiz_cat = Gtk.Entry()
        self.wiz_cat.set_text("Gaming")
        grid.attach(self.wiz_cat, 1, 1, 3, 1)

        form_card.append(grid)
        content_area.append(form_card)

        # Sequence Expression Section
        seq_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        lbl_seq = Gtk.Label()
        lbl_seq.set_markup("<span weight='bold' size='small' color='#86efac'>Macro Sequence Expression:</span>")
        lbl_seq.set_xalign(0)

        seq_box.append(lbl_seq)

        lbl_hint = Gtk.Label(label="Accepts dotted syntax or '+' format, e.g.:\nkey_down(Control_L).wait(50).key(Up).wait(40).key_up(Control_L)\nor: Control_L + 50ms + space")
        lbl_hint.add_css_class("dim-text")
        lbl_hint.set_wrap(True)
        lbl_hint.set_xalign(0)
        seq_box.append(lbl_hint)

        self.seq_textview = Gtk.TextView()
        self.seq_textview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.seq_textview.add_css_class("code-box")
        self.seq_textview.set_size_request(-1, 90)
        self.seq_buffer = self.seq_textview.get_buffer()
        self.seq_buffer.set_text("key_down(Control_L).wait(50).key(Up).wait(40).key_up(Control_L)")

        seq_scrolled = Gtk.ScrolledWindow()
        seq_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        seq_scrolled.set_vexpand(True)
        seq_scrolled.set_child(self.seq_textview)
        seq_box.append(seq_scrolled)

        content_area.append(seq_box)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        btn_box.set_halign(Gtk.Align.END)
        btn_box.set_margin_top(8)

        btn_cancel = Gtk.Button(label="Cancel")
        btn_cancel.add_css_class("ghost-btn")
        btn_cancel.connect("clicked", lambda w: self.close())
        btn_box.append(btn_cancel)

        btn_create = Gtk.Button(label="🪄 Create Macro")
        btn_create.add_css_class("primary-btn")
        btn_create.connect("clicked", self._on_create_clicked)
        btn_box.append(btn_create)

        content_area.append(btn_box)

    def _on_create_clicked(self, widget):
        title = self.wiz_title.get_text().strip()
        if not title:
            title = "Custom Macro"

        start_iter = self.seq_buffer.get_start_iter()
        end_iter = self.seq_buffer.get_end_iter()
        seq_text = self.seq_buffer.get_text(start_iter, end_iter, False).strip()

        steps = parse_dsl_sequence(seq_text)
        if not steps:
            steps = ["space", "50ms", "mouse(1)"]

        compiled = build_macro_string(steps)
        macro_dict = {
            "id": f"macro_{os.urandom(4).hex()}",
            "title": title,
            "label": self.wiz_badge.get_text().strip() or title[:10],
            "category": self.wiz_cat.get_text().strip() or "Custom",
            "macro": compiled,
            "desc": f"Wizard-generated macro with {len(steps)} step(s)",
            "mapping_type": "macro",
            "built_in": False
        }

        save_or_update_macro(macro_dict)
        self.parent_win._load_macros_and_select_id(macro_dict["id"])
        self.parent_win.toast.show_message(f"Created macro '{title}' via Wizard!", icon="🪄")
        self.close()



class StropMacroStudioWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="Strop — Macro Studio")
        self.set_default_size(980, 660)
        self.set_size_request(850, 550)

        # Macro state
        self.macros: List[Dict[str, Any]] = []
        self.selected_macro_id: Optional[str] = None
        self.current_steps: List[str] = []
        self.is_recording = False

        self._build_ui()
        self._load_macros_and_select_first()

    def _build_ui(self):
        overlay = Gtk.Overlay()
        self.set_child(overlay)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        main_box.set_margin_top(12)
        main_box.set_margin_bottom(12)
        main_box.set_margin_start(16)
        main_box.set_margin_end(16)
        overlay.set_child(main_box)

        # In-App Floating Toast Notification Banner
        self.toast = StropToast()
        overlay.add_overlay(self.toast)

        # -------------------------------------------------------------
        # 1. Header Bar
        # -------------------------------------------------------------
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_valign(Gtk.Align.CENTER)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        lbl_title = Gtk.Label()
        lbl_title.set_markup("<span size='large' weight='bold' color='#f8fafc'>STROP <span color='#22c55e'>Macro Studio</span></span>")
        lbl_title.set_xalign(0)
        title_box.append(lbl_title)

        lbl_sub = Gtk.Label(label="Visual Sequence Timeline, Sequence Expression Wizard, & input-remapper-2 Macro Builder")
        lbl_sub.add_css_class("dim-text")
        lbl_sub.set_xalign(0)
        title_box.append(lbl_sub)
        header.append(title_box)

        # Header action buttons
        header_actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header_actions.set_halign(Gtk.Align.END)
        header_actions.set_hexpand(True)

        btn_wiz = Gtk.Button(label="🪄 New Macro Wizard")
        btn_wiz.add_css_class("primary-btn")
        btn_wiz.set_tooltip_text("Open Wizard to generate macro from sequence expressions or steps")
        btn_wiz.connect("clicked", lambda w: self._open_macro_wizard())
        header_actions.append(btn_wiz)

        header.append(header_actions)
        main_box.append(header)

        # -------------------------------------------------------------
        # 2. Main Content Split: Left (Library) | Right (Timeline & Builder)
        # -------------------------------------------------------------
        content_paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        content_paned.set_position(320)
        content_paned.set_vexpand(True)
        main_box.append(content_paned)

        # Left Column: Macro Library
        left_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        left_card.add_css_class("card")
        left_card.set_size_request(300, -1)

        lib_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_lib = Gtk.Label()
        lbl_lib.set_markup("<span weight='bold' size='small' color='#f8fafc'>Macro Library</span>")
        lbl_lib.set_xalign(0)
        lbl_lib.set_hexpand(True)
        lib_header.append(lbl_lib)

        self.lbl_macro_count = Gtk.Label(label="0 macros")
        self.lbl_macro_count.add_css_class("dim-text")
        lib_header.append(self.lbl_macro_count)
        left_card.append(lib_header)

        # Search Bar
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Search macros...")
        self.search_entry.connect("search-changed", self._on_search_changed)
        left_card.append(self.search_entry)

        # Scrolled Macro List
        lib_scrolled = Gtk.ScrolledWindow()
        lib_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        lib_scrolled.set_vexpand(True)

        self.library_list_box = Gtk.ListBox()
        self.library_list_box.add_css_class("dock-card")
        self.library_list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.library_list_box.connect("row-selected", self._on_macro_row_selected)
        lib_scrolled.set_child(self.library_list_box)
        left_card.append(lib_scrolled)

        content_paned.set_start_child(left_card)

        # Right Column: Macro Editor & Timeline Builder
        right_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        right_card.add_css_class("card")
        right_card.set_hexpand(True)

        # Properties Row: Name, Label, Icon, Category
        prop_grid = Gtk.Grid()
        prop_grid.set_column_spacing(8)
        prop_grid.set_row_spacing(6)

        lbl_mname = Gtk.Label(label="Macro Title:")
        lbl_mname.set_xalign(0)
        lbl_mname.add_css_class("dim-label")
        prop_grid.attach(lbl_mname, 0, 0, 1, 1)

        self.entry_title = Gtk.Entry()
        self.entry_title.set_placeholder_text("e.g. Turbo Click, Dodge Roll")
        self.entry_title.set_hexpand(True)
        prop_grid.attach(self.entry_title, 1, 0, 1, 1)

        lbl_mlabel = Gtk.Label(label="Badge Label:")
        lbl_mlabel.set_xalign(0)
        lbl_mlabel.add_css_class("dim-label")
        prop_grid.attach(lbl_mlabel, 2, 0, 1, 1)

        self.entry_badge = Gtk.Entry()
        self.entry_badge.set_placeholder_text("e.g. Turbo, SlideJump")
        self.entry_badge.set_size_request(120, -1)
        prop_grid.attach(self.entry_badge, 3, 0, 1, 1)

        lbl_mcat = Gtk.Label(label="Category:")
        lbl_mcat.set_xalign(0)
        lbl_mcat.add_css_class("dim-label")
        prop_grid.attach(lbl_mcat, 0, 1, 1, 1)

        self.entry_category = Gtk.Entry()
        self.entry_category.set_text("Custom")
        prop_grid.attach(self.entry_category, 1, 1, 3, 1)

        right_card.append(prop_grid)


        # -------------------------------------------------------------
        # Action Step Insertion Bar
        # -------------------------------------------------------------
        add_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        add_bar.set_margin_top(4)

        lbl_add = Gtk.Label()
        lbl_add.set_markup("<span size='small' weight='bold' color='#86efac'>+ Insert Step:</span>")
        add_bar.append(lbl_add)

        # Preset step pills
        for d_lbl, d_val in [("+25ms", "25ms"), ("+50ms", "50ms"), ("+100ms", "100ms"), ("+250ms", "250ms")]:
            btn_d = Gtk.Button(label=d_lbl)
            btn_d.add_css_class("quick-tag")
            btn_d.set_tooltip_text(f"Insert {d_val} pause")
            btn_d.connect("clicked", lambda w, v=d_val: self._add_step(v))
            add_bar.append(btn_d)

        for act_lbl, act_val in [("+Left Click", "mouse(1)"), ("+Right Click", "mouse(3)"), ("+Space", "space"), ("+Ctrl", "Control_L"), ("+Shift", "Shift_L")]:
            btn_a = Gtk.Button(label=act_lbl)
            btn_a.add_css_class("quick-tag")
            btn_a.set_tooltip_text(f"Insert {act_lbl}")
            btn_a.connect("clicked", lambda w, v=act_val: self._add_step(v))
            add_bar.append(btn_a)

        right_card.append(add_bar)

        # Sequence Expression / Custom Input Bar
        custom_input_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.entry_custom_step = Gtk.Entry()
        self.entry_custom_step.set_placeholder_text("Type step or full sequence (e.g. key_down(Control_L).wait(50).key(Up)... or 'Tab + 50ms + e')")
        self.entry_custom_step.set_hexpand(True)
        self.entry_custom_step.connect("activate", lambda e: self._on_add_custom_step())
        custom_input_bar.append(self.entry_custom_step)

        btn_add_custom = Gtk.Button(label="Parse & Insert")
        btn_add_custom.add_css_class("ghost-btn")
        btn_add_custom.set_tooltip_text("Parses sequence or step and appends to the timeline")
        btn_add_custom.connect("clicked", lambda w: self._on_add_custom_step())
        custom_input_bar.append(btn_add_custom)
        right_card.append(custom_input_bar)

        # -------------------------------------------------------------
        # Vertical Timeline Step Box
        # -------------------------------------------------------------
        lbl_tl = Gtk.Label()
        lbl_tl.set_markup("<span weight='bold' size='small' color='#f8fafc'>Sequence Timeline</span>")
        lbl_tl.set_xalign(0)
        right_card.append(lbl_tl)

        tl_scrolled = Gtk.ScrolledWindow()
        tl_scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        tl_scrolled.set_vexpand(True)

        self.timeline_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        tl_scrolled.set_child(self.timeline_box)
        right_card.append(tl_scrolled)

        # Raw Output Preview Bar
        preview_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        lbl_prev_title = Gtk.Label(label="Compiled Syntax:")
        lbl_prev_title.add_css_class("dim-label")
        preview_box.append(lbl_prev_title)

        self.lbl_compiled_syntax = Gtk.Label()
        self.lbl_compiled_syntax.set_markup("<span color='#86efac'><tt><i>(empty)</i></tt></span>")
        self.lbl_compiled_syntax.set_hexpand(True)
        self.lbl_compiled_syntax.set_xalign(0)
        preview_box.append(self.lbl_compiled_syntax)
        right_card.append(preview_box)

        # Bottom Actions: Save, Delete, Duplicate
        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        
        self.btn_delete = Gtk.Button(label="🗑 Delete Macro")
        self.btn_delete.add_css_class("danger-btn")
        self.btn_delete.connect("clicked", self._on_delete_clicked)
        bottom_bar.append(self.btn_delete)

        btn_clear_steps = Gtk.Button(label="Clear Steps")
        btn_clear_steps.add_css_class("ghost-btn")
        btn_clear_steps.connect("clicked", lambda w: self._clear_all_steps())
        bottom_bar.append(btn_clear_steps)

        btn_save = Gtk.Button(label="💾 Save Macro")
        btn_save.add_css_class("primary-btn")
        btn_save.set_hexpand(True)
        btn_save.set_halign(Gtk.Align.END)
        btn_save.connect("clicked", self._on_save_clicked)
        bottom_bar.append(btn_save)

        right_card.append(bottom_bar)
        content_paned.set_end_child(right_card)

    def _open_macro_wizard(self):
        dlg = MacroWizardDialog(self)
        dlg.present()

    def _load_macros_and_select_first(self):
        self.macros = load_all_macros()
        self._refresh_library_list()
        if self.macros:
            first_row = self.library_list_box.get_row_at_index(0)
            if first_row:
                self.library_list_box.select_row(first_row)

    def _load_macros_and_select_id(self, target_id: str):
        self.macros = load_all_macros()
        self._refresh_library_list()
        for idx, m in enumerate(self.macros):
            if m.get("id") == target_id:
                row = self.library_list_box.get_row_at_index(idx)
                if row:
                    self.library_list_box.select_row(row)
                break

    def _refresh_library_list(self, filter_text=""):
        while True:
            child = self.library_list_box.get_first_child()
            if not child:
                break
            self.library_list_box.remove(child)

        count = 0
        search_term = (filter_text or "").strip().lower()
        for idx, m in enumerate(self.macros):
            title = m.get("title", "Untitled Macro")
            macro_str = m.get("macro", "")
            cat = m.get("category", "General")
            if search_term and search_term not in title.lower() and search_term not in macro_str.lower() and search_term not in cat.lower():
                continue

            row = Gtk.ListBoxRow()
            card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            card.add_css_class("remap-row")
            card.set_margin_top(2)
            card.set_margin_bottom(2)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            info_box.set_hexpand(True)

            lbl_title = Gtk.Label()
            esc_t = GLib.markup_escape_text(title)
            is_built_in = m.get("built_in", False)
            badge_str = " <span size='6500' color='#22c55e'>[Built-In]</span>" if is_built_in else " <span size='6500' color='#94a3b8'>[Custom]</span>"
            lbl_title.set_markup(f"<span weight='bold' size='small' color='#f8fafc'>{esc_t}</span>{badge_str}")
            lbl_title.set_xalign(0)
            info_box.append(lbl_title)

            lbl_sub = Gtk.Label()
            esc_cat = GLib.markup_escape_text(cat)
            esc_label = GLib.markup_escape_text(m.get("label", title))
            lbl_sub.set_markup(f"<span size='7500' color='#94a3b8'>Category: <b>{esc_cat}</b> | Badge: <tt>{esc_label}</tt></span>")
            lbl_sub.set_xalign(0)
            info_box.append(lbl_sub)

            card.append(info_box)
            row.set_child(card)
            row._macro_data = m
            self.library_list_box.append(row)
            count += 1

        self.lbl_macro_count.set_text(f"{count} macros")

    def _on_search_changed(self, entry):
        self._refresh_library_list(entry.get_text())

    def _on_macro_row_selected(self, listbox, row):
        if not row or not hasattr(row, "_macro_data"):
            return
        m = row._macro_data
        self.selected_macro_id = m.get("id")
        self.entry_title.set_text(m.get("title", ""))
        self.entry_badge.set_text(m.get("label", m.get("title", "")))
        self.entry_category.set_text(m.get("category", "Custom"))

        self.current_steps = parse_macro_steps(m.get("macro", ""))
        self._render_timeline()

        # Disable delete for built-in templates
        is_builtin = m.get("built_in", False)
        self.btn_delete.set_sensitive(not is_builtin)


    def _add_step(self, step_val: str):
        self.current_steps.append(step_val)
        self._render_timeline()

    def _on_add_custom_step(self):
        val = self.entry_custom_step.get_text().strip()
        if not val:
            return
        # Parse potential multi-step expression or single step
        parsed = parse_dsl_sequence(val)
        if parsed:
            self.current_steps.extend(parsed)
            self._render_timeline()
            self.entry_custom_step.set_text("")
            self.toast.show_message(f"Parsed and inserted {len(parsed)} step(s)!", icon="⚡")

    def _remove_step(self, idx: int):
        if 0 <= idx < len(self.current_steps):
            self.current_steps.pop(idx)
            self._render_timeline()

    def _move_step(self, idx: int, delta: int):
        new_idx = idx + delta
        if 0 <= new_idx < len(self.current_steps):
            self.current_steps[idx], self.current_steps[new_idx] = self.current_steps[new_idx], self.current_steps[idx]
            self._render_timeline()

    def _clear_all_steps(self):
        self.current_steps = []
        self._render_timeline()

    def _render_timeline(self):
        while True:
            child = self.timeline_box.get_first_child()
            if not child:
                break
            self.timeline_box.remove(child)

        if not self.current_steps:
            empty = Gtk.Label(label="No steps in timeline. Use the wizard or insertion bar above.")
            empty.add_css_class("dim-label")
            empty.set_vexpand(True)
            self.timeline_box.append(empty)
        else:
            for idx, step in enumerate(self.current_steps):
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
                row.add_css_class("remap-row")

                lbl_idx = Gtk.Label()
                lbl_idx.set_markup(f"<span size='small' color='#94a3b8'>#{idx + 1}</span>")
                row.append(lbl_idx)

                # Icon/Badge distinguishing delays vs keystrokes
                is_delay = "ms" in step or ("s" in step and step.replace("ms", "").replace("s", "").isdigit())
                is_mouse = "mouse" in step or "wheel" in step
                is_hold = "key_down" in step or "hold" in step
                is_release = "key_up" in step or "release" in step
                badge_type = "⏱️ Delay" if is_delay else ("🖱️ Click" if is_mouse else ("⬇️ Hold" if is_hold else ("⬆️ Release" if is_release else "⌨️ Key")))
                
                lbl_type = Gtk.Label()
                lbl_type.set_markup(f"<span size='small' weight='bold' color='#f8fafc'>{badge_type}</span>")
                row.append(lbl_type)

                lbl_val = Gtk.Label()
                esc_val = GLib.markup_escape_text(step)
                color = "#fcd34d" if is_delay else ("#93c5fd" if is_mouse else ("#f87171" if is_hold else ("#60a5fa" if is_release else "#86efac")))
                lbl_val.set_markup(f"<span size='small' weight='bold' color='{color}'><tt>{esc_val}</tt></span>")
                lbl_val.set_xalign(0)
                lbl_val.set_hexpand(True)
                row.append(lbl_val)

                # Up / Down Controls
                btn_up = Gtk.Button(label="▲")
                btn_up.add_css_class("ghost-btn")
                btn_up.set_sensitive(idx > 0)
                btn_up.connect("clicked", lambda w, i=idx: self._move_step(i, -1))
                row.append(btn_up)

                btn_down = Gtk.Button(label="▼")
                btn_down.add_css_class("ghost-btn")
                btn_down.set_sensitive(idx < len(self.current_steps) - 1)
                btn_down.connect("clicked", lambda w, i=idx: self._move_step(i, 1))
                row.append(btn_down)

                btn_del = Gtk.Button(label="✕")
                btn_del.add_css_class("danger-btn")
                btn_del.connect("clicked", lambda w, i=idx: self._remove_step(i))
                row.append(btn_del)

                self.timeline_box.append(row)

        compiled = build_macro_string(self.current_steps)
        if compiled:
            self.lbl_compiled_syntax.set_markup(f"<span color='#86efac'><tt>{GLib.markup_escape_text(compiled)}</tt></span>")
        else:
            self.lbl_compiled_syntax.set_markup("<span color='#94a3b8'><tt><i>(empty)</i></tt></span>")

    def _on_save_clicked(self, widget):
        title = self.entry_title.get_text().strip()
        if not title:
            self.toast.show_message("Please provide a macro title!", icon="⚠️")
            return

        compiled = build_macro_string(self.current_steps)
        if not compiled:
            self.toast.show_message("Macro timeline cannot be empty!", icon="⚠️")
            return

        macro_data = {
            "id": self.selected_macro_id or f"macro_{os.urandom(4).hex()}",
            "title": title,
            "label": self.entry_badge.get_text().strip() or title,
            "category": self.entry_category.get_text().strip() or "Custom",
            "macro": compiled,
            "desc": f"Custom macro with {len(self.current_steps)} step(s)",
            "mapping_type": "macro",
            "built_in": False
        }


        success = save_or_update_macro(macro_data)
        if success:
            self.selected_macro_id = macro_data["id"]
            self.macros = load_all_macros()
            self._refresh_library_list(self.search_entry.get_text())
            self.btn_delete.set_sensitive(True)
            self.toast.show_message(f"Saved macro '{title}' to storage!", icon="💾")
        else:
            self.toast.show_message("Failed to save macro to disk.", icon="❌")

    def _on_delete_clicked(self, widget):
        if not self.selected_macro_id:
            return

        alert = Gtk.AlertDialog(
            message="Delete this macro?",
            detail="This will permanently remove this custom macro from your library."
        )
        alert.set_buttons(["Cancel", "Delete"])
        alert.set_default_button(0)
        alert.set_cancel_button(0)

        def on_response(dialog, result):
            try:
                choice = dialog.choose_finish(result)
                if choice == 1:
                    delete_custom_macro(self.selected_macro_id)
                    self.macros = load_all_macros()
                    self._load_macros_and_select_first()
                    self.toast.show_message("Deleted macro from library", icon="🗑")
            except Exception:
                pass

        alert.choose(self, None, on_response)


def on_startup(app):
    apply_theme()


def on_activate(app):
    win = StropMacroStudioWindow(app)
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
