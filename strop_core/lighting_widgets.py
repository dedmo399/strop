"""
Custom GTK4 + Cairo Widgets for the Strop Lighting Studio.

Provides:
- `HSVColorWheelWidget`: Outer 360° Hue ring + inner Saturation/Value (SV) square with drag selection
- `GradientEditorWidget`: Horizontal gradient bar with 2 to 6 draggable color stops
- `ColorSelectorPanel`: Unified Color Selector (Hue/SV wheel, #Hex field, clamped 0-255 R/G/B fields,
  8 factory swatches + 8 persistent user swatches, and gradient stop editor)
- `DeviceLightingCanvas`: Interactive 2D vector graphic for Keyboard, Keypad, Mouse, and Controller
  with 60 FPS live RGB glow rendering, click/marquee zone selection, and live keypress trigger mode
"""

from __future__ import annotations

import math
from typing import Callable, Dict, List, Optional, Set, Tuple

import cairo
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gdk, GLib, Gtk

from strop_core.lighting import (
    FACTORY_SWATCHES,
    GradientStop,
    LEDNode,
    RGBTuple,
    clamp_channel,
    clamp_rgb,
    hex_to_rgb,
    hsv_to_rgb,
    rgb_to_hex,
    rgb_to_hsv,
    sample_gradient,
    select_nodes_in_rect,
)


def _rounded_rect(cr: cairo.Context, x: float, y: float, w: float, h: float, r: float) -> None:
    r = max(0.0, min(r, w * 0.5, h * 0.5))
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
    cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3.0 * math.pi / 2.0)
    cr.close_path()


# ---------------------------------------------------------------------------
# 1. Outer 360° Hue Ring + Inner Saturation/Value (SV) Square
# ---------------------------------------------------------------------------
class HSVColorWheelWidget(Gtk.DrawingArea):
    """
    Combines an outer 360-degree Hue ring with an inner Saturation/Value (SV) square
    for intuitive drag selection (Section 3.1).
    """
    def __init__(self, on_color_changed: Optional[Callable[[RGBTuple], None]] = None):
        super().__init__()
        self.set_content_width(164)
        self.set_content_height(164)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.CENTER)

        self.hue: float = 120.0  # [0, 360)
        self.sat: float = 1.0    # [0, 1]
        self.val: float = 1.0    # [0, 1]
        self.on_color_changed = on_color_changed
        self._drag_mode: Optional[str] = None  # "ring" | "square"
        self._drag_start_xy: Tuple[float, float] = (0.0, 0.0)

        self.set_draw_func(self._on_draw)

        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_pressed)
        self.add_controller(click)

        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def set_rgb(self, rgb: RGBTuple, emit: bool = False) -> None:
        h, s, v = rgb_to_hsv(*rgb)
        # Preserve hue angle if saturation or value drops to 0
        if s > 1e-3:
            self.hue = h
        self.sat = s
        self.val = v
        self.queue_draw()
        if emit and self.on_color_changed:
            self.on_color_changed(self.get_rgb())

    def get_rgb(self) -> RGBTuple:
        return hsv_to_rgb(self.hue, self.sat, self.val)

    def _geometry(self, width: int, height: int) -> Tuple[float, float, float, float, float]:
        cx = width * 0.5
        cy = height * 0.5
        outer_r = min(width, height) * 0.46
        ring_thickness = max(13.0, outer_r * 0.22)
        inner_r = outer_r - ring_thickness
        sq_half = (inner_r - 5.0) * math.cos(math.pi / 4.0)
        return cx, cy, outer_r, inner_r, sq_half

    def _on_draw(self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        cx, cy, outer_r, inner_r, sq_half = self._geometry(width, height)
        mid_r = (outer_r + inner_r) * 0.5
        ring_w = outer_r - inner_r

        # 1. Draw 360° Hue Ring in 72 angular segments
        segments = 72
        step_rad = (2.0 * math.pi) / segments
        cr.set_line_width(ring_w)
        for i in range(segments):
            a0 = i * step_rad
            a1 = (i + 1.05) * step_rad
            deg = (i / segments) * 360.0
            r, g, b = hsv_to_rgb(deg, 1.0, 1.0)
            cr.set_source_rgb(r / 255.0, g / 255.0, b / 255.0)
            cr.new_sub_path()
            cr.arc(cx, cy, mid_r, a0, a1)
            cr.stroke()

        # Subtle ring borders
        cr.set_line_width(1.0)
        cr.set_source_rgba(0.05, 0.08, 0.12, 0.9)
        cr.arc(cx, cy, outer_r, 0.0, 2.0 * math.pi)
        cr.stroke()
        cr.arc(cx, cy, inner_r, 0.0, 2.0 * math.pi)
        cr.stroke()

        # 2. Draw Inner Saturation/Value (SV) Square
        sx = cx - sq_half
        sy = cy - sq_half
        sw = sq_half * 2.0
        sh = sq_half * 2.0

        # Base pure hue fill
        hr, hg, hb = hsv_to_rgb(self.hue, 1.0, 1.0)
        cr.rectangle(sx, sy, sw, sh)
        cr.set_source_rgb(hr / 255.0, hg / 255.0, hb / 255.0)
        cr.fill()

        # Horizontal white -> transparent gradient (Saturation: left=0, right=1)
        sat_pat = cairo.LinearGradient(sx, sy, sx + sw, sy)
        sat_pat.add_color_stop_rgba(0.0, 1.0, 1.0, 1.0, 1.0)
        sat_pat.add_color_stop_rgba(1.0, 1.0, 1.0, 1.0, 0.0)
        cr.rectangle(sx, sy, sw, sh)
        cr.set_source(sat_pat)
        cr.fill()

        # Vertical transparent -> black gradient (Value: top=1, bottom=0)
        val_pat = cairo.LinearGradient(sx, sy, sx, sy + sh)
        val_pat.add_color_stop_rgba(0.0, 0.0, 0.0, 0.0, 0.0)
        val_pat.add_color_stop_rgba(1.0, 0.0, 0.0, 0.0, 1.0)
        cr.rectangle(sx, sy, sw, sh)
        cr.set_source(val_pat)
        cr.fill()

        cr.set_line_width(1.2)
        cr.set_source_rgba(0.2, 0.26, 0.34, 1.0)
        cr.rectangle(sx, sy, sw, sh)
        cr.stroke()

        # 3. Hue Ring Indicator Reticle
        hue_rad = math.radians(self.hue)
        hx = cx + math.cos(hue_rad) * mid_r
        hy = cy + math.sin(hue_rad) * mid_r
        cr.set_line_width(2.2)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.arc(hx, hy, ring_w * 0.42, 0.0, 2.0 * math.pi)
        cr.stroke()
        cr.set_line_width(1.0)
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.arc(hx, hy, ring_w * 0.42 + 1.2, 0.0, 2.0 * math.pi)
        cr.stroke()

        # 4. SV Square Indicator Reticle
        px = sx + self.sat * sw
        py = sy + (1.0 - self.val) * sh
        cr.set_line_width(2.0)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.arc(px, py, 5.0, 0.0, 2.0 * math.pi)
        cr.stroke()
        cr.set_line_width(1.0)
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.arc(px, py, 6.2, 0.0, 2.0 * math.pi)
        cr.stroke()

    def _classify_and_update(self, x: float, y: float, lock_mode: bool = False) -> None:
        w = self.get_width() or 164
        h = self.get_height() or 164
        cx, cy, outer_r, inner_r, sq_half = self._geometry(w, h)
        dx = x - cx
        dy = y - cy
        dist = math.hypot(dx, dy)

        if not lock_mode or self._drag_mode is None:
            if inner_r - 3.0 <= dist <= outer_r + 6.0:
                self._drag_mode = "ring"
            elif abs(dx) <= sq_half + 4.0 and abs(dy) <= sq_half + 4.0:
                self._drag_mode = "square"
            else:
                return

        if self._drag_mode == "ring":
            angle = math.degrees(math.atan2(dy, dx)) % 360.0
            self.hue = angle
        elif self._drag_mode == "square":
            sx = cx - sq_half
            sy = cy - sq_half
            sw = sq_half * 2.0
            sh = sq_half * 2.0
            self.sat = max(0.0, min(1.0, (x - sx) / max(1.0, sw)))
            self.val = max(0.0, min(1.0, 1.0 - (y - sy) / max(1.0, sh)))

        self.queue_draw()
        if self.on_color_changed:
            self.on_color_changed(self.get_rgb())

    def _on_pressed(self, gesture, n_press: int, x: float, y: float) -> None:
        self._drag_mode = None
        self._classify_and_update(x, y, lock_mode=False)

    def _on_drag_begin(self, gesture, start_x: float, start_y: float) -> None:
        self._drag_start_xy = (start_x, start_y)
        self._drag_mode = None
        self._classify_and_update(start_x, start_y, lock_mode=False)

    def _on_drag_update(self, gesture, offset_x: float, offset_y: float) -> None:
        x = self._drag_start_xy[0] + offset_x
        y = self._drag_start_xy[1] + offset_y
        self._classify_and_update(x, y, lock_mode=True)

    def _on_drag_end(self, gesture, offset_x: float, offset_y: float) -> None:
        self._drag_mode = None


# ---------------------------------------------------------------------------
# 2. Horizontal Multi-Stop Gradient Editor (2 to 6 Draggable Stops)
# ---------------------------------------------------------------------------
class GradientEditorWidget(Gtk.Box):
    """
    Displays a horizontal gradient bar supporting 2 to 6 draggable color stops (Section 3.1).
    """
    def __init__(
        self,
        on_stops_changed: Optional[Callable[[List[GradientStop]], None]] = None,
        on_stop_selected: Optional[Callable[[RGBTuple], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.stops: List[GradientStop] = [
            (0.0, (0, 255, 100)),
            (0.5, (0, 160, 255)),
            (1.0, (170, 0, 255)),
        ]
        self.selected_idx: int = 0
        self.on_stops_changed = on_stops_changed
        self.on_stop_selected = on_stop_selected
        self._drag_start_x: float = 0.0

        head_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl = Gtk.Label()
        lbl.set_markup("<span size='small' weight='bold' color='#94a3b8'>Gradient Stops (2–6)</span>")
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        head_row.append(lbl)

        self.btn_add_stop = Gtk.Button(label="+ Stop")
        self.btn_add_stop.add_css_class("ghost-btn")
        self.btn_add_stop.set_tooltip_text("Add color stop (max 6)")
        self.btn_add_stop.connect("clicked", self._on_add_stop)
        head_row.append(self.btn_add_stop)

        self.btn_del_stop = Gtk.Button(label="− Stop")
        self.btn_del_stop.add_css_class("ghost-btn")
        self.btn_del_stop.set_tooltip_text("Remove selected color stop (min 2)")
        self.btn_del_stop.connect("clicked", self._on_remove_stop)
        head_row.append(self.btn_del_stop)

        self.append(head_row)

        self.canvas = Gtk.DrawingArea()
        self.canvas.set_content_height(34)
        self.canvas.set_hexpand(True)
        self.canvas.set_draw_func(self._on_draw)
        self.append(self.canvas)

        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_pressed)
        self.canvas.add_controller(click)

        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        self.canvas.add_controller(drag)

        self._update_button_sensitivity()

    def set_stops(self, stops: List[GradientStop], emit: bool = False) -> None:
        if len(stops) >= 2:
            self.stops = [(max(0.0, min(1.0, float(pos))), clamp_rgb(*col)) for pos, col in stops[:6]]
            self.selected_idx = min(self.selected_idx, len(self.stops) - 1)
            self._update_button_sensitivity()
            self.canvas.queue_draw()
            if emit and self.on_stops_changed:
                self.on_stops_changed(self.get_stops())

    def get_stops(self) -> List[GradientStop]:
        return sorted(self.stops, key=lambda item: item[0])

    def update_selected_stop_color(self, rgb: RGBTuple, emit: bool = True) -> None:
        if 0 <= self.selected_idx < len(self.stops):
            pos, _ = self.stops[self.selected_idx]
            self.stops[self.selected_idx] = (pos, clamp_rgb(*rgb))
            self.canvas.queue_draw()
            if emit and self.on_stops_changed:
                self.on_stops_changed(self.get_stops())

    def _update_button_sensitivity(self) -> None:
        self.btn_add_stop.set_sensitive(len(self.stops) < 6)
        self.btn_del_stop.set_sensitive(len(self.stops) > 2)

    def _on_add_stop(self, btn) -> None:
        if len(self.stops) >= 6:
            return
        ordered = self.get_stops()
        # Insert stop at largest gap
        best_gap = -1.0
        insert_pos = 0.5
        for i in range(len(ordered) - 1):
            gap = ordered[i + 1][0] - ordered[i][0]
            if gap > best_gap:
                best_gap = gap
                insert_pos = (ordered[i][0] + ordered[i + 1][0]) * 0.5
        new_col = sample_gradient(ordered, insert_pos)
        self.stops.append((insert_pos, new_col))
        self.selected_idx = len(self.stops) - 1
        self._update_button_sensitivity()
        self.canvas.queue_draw()
        if self.on_stops_changed:
            self.on_stops_changed(self.get_stops())

    def _on_remove_stop(self, btn) -> None:
        if len(self.stops) <= 2:
            return
        if 0 <= self.selected_idx < len(self.stops):
            self.stops.pop(self.selected_idx)
            self.selected_idx = max(0, min(self.selected_idx, len(self.stops) - 1))
            self._update_button_sensitivity()
            self.canvas.queue_draw()
            if self.on_stops_changed:
                self.on_stops_changed(self.get_stops())

    def _on_draw(self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        pad_x = 10.0
        bar_w = max(20.0, width - pad_x * 2.0)
        bar_y = 4.0
        bar_h = 16.0

        pat = cairo.LinearGradient(pad_x, bar_y, pad_x + bar_w, bar_y)
        for pos, (r, g, b) in self.get_stops():
            pat.add_color_stop_rgb(pos, r / 255.0, g / 255.0, b / 255.0)

        _rounded_rect(cr, pad_x, bar_y, bar_w, bar_h, 5.0)
        cr.set_source(pat)
        cr.fill_preserve()
        cr.set_line_width(1.0)
        cr.set_source_rgba(0.25, 0.33, 0.44, 1.0)
        cr.stroke()

        # Draw stop handles
        for idx, (pos, (r, g, b)) in enumerate(self.stops):
            hx = pad_x + pos * bar_w
            hy = bar_y + bar_h + 7.0
            radius = 6.5 if idx == self.selected_idx else 5.0
            cr.arc(hx, hy, radius, 0.0, 2.0 * math.pi)
            cr.set_source_rgb(r / 255.0, g / 255.0, b / 255.0)
            cr.fill_preserve()
            if idx == self.selected_idx:
                cr.set_line_width(2.2)
                cr.set_source_rgb(0.13, 0.77, 0.37)  # Emerald highlight
            else:
                cr.set_line_width(1.2)
                cr.set_source_rgb(0.9, 0.94, 0.98)
            cr.stroke()

    def _find_nearest_stop(self, x: float) -> int:
        w = self.canvas.get_width() or 200
        pad_x = 10.0
        bar_w = max(20.0, w - pad_x * 2.0)
        best_i = 0
        best_d = 1e9
        for i, (pos, _) in enumerate(self.stops):
            hx = pad_x + pos * bar_w
            d = abs(x - hx)
            if d < best_d:
                best_d = d
                best_i = i
        return best_i

    def _on_pressed(self, gesture, n_press: int, x: float, y: float) -> None:
        self.selected_idx = self._find_nearest_stop(x)
        self.canvas.queue_draw()
        if self.on_stop_selected and 0 <= self.selected_idx < len(self.stops):
            self.on_stop_selected(self.stops[self.selected_idx][1])

    def _on_drag_begin(self, gesture, start_x: float, start_y: float) -> None:
        self._drag_start_x = start_x
        self.selected_idx = self._find_nearest_stop(start_x)
        self.canvas.queue_draw()

    def _on_drag_update(self, gesture, offset_x: float, offset_y: float) -> None:
        if not (0 <= self.selected_idx < len(self.stops)):
            return
        w = self.canvas.get_width() or 200
        pad_x = 10.0
        bar_w = max(20.0, w - pad_x * 2.0)
        x = self._drag_start_x + offset_x
        new_pos = max(0.0, min(1.0, (x - pad_x) / bar_w))
        _, col = self.stops[self.selected_idx]
        self.stops[self.selected_idx] = (new_pos, col)
        self.canvas.queue_draw()
        if self.on_stops_changed:
            self.on_stops_changed(self.get_stops())


# ---------------------------------------------------------------------------
# 3. Unified Color Selector Architecture (Section 3.1)
# ---------------------------------------------------------------------------
class ColorSelectorPanel(Gtk.Box):
    """
    Unified Color Selector component displayed whenever an effect supports custom color
    or gradient inputs:
    - Outer 360° Hue ring + inner SV square
    - Direct 6-char Hex entry (#FF0055) + 3 RGB decimal fields clamped 0..255
    - 8 Factory vibrant swatches + 8 User-saveable swatch slots
    - Horizontal 2-to-6 stop Gradient Editor
    """
    def __init__(
        self,
        user_swatches: List[RGBTuple],
        on_color_changed: Optional[Callable[[RGBTuple], None]] = None,
        on_gradient_changed: Optional[Callable[[List[GradientStop]], None]] = None,
        on_user_swatches_changed: Optional[Callable[[List[RGBTuple]], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.add_css_class("card")

        self.current_rgb: RGBTuple = (0, 255, 0)
        self.user_swatches: List[RGBTuple] = list(user_swatches[:8])
        while len(self.user_swatches) < 8:
            self.user_swatches.append((34, 197, 94))
        self.selected_user_slot: int = 0
        self.on_color_changed = on_color_changed
        self.on_gradient_changed = on_gradient_changed
        self.on_user_swatches_changed = on_user_swatches_changed
        self._updating_widgets: bool = False

        # Title + Active Color Target Selector (Primary vs Secondary)
        head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_title = Gtk.Label()
        lbl_title.set_markup("<span weight='bold' size='small' color='#f8fafc'>🎨 Color &amp; Gradient Selector</span>")
        lbl_title.set_xalign(0)
        lbl_title.set_hexpand(True)
        head.append(lbl_title)
        self.append(head)

        # Top Split: Color Wheel (Left) + Hex & RGB Numeric Fields (Right)
        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.wheel = HSVColorWheelWidget(on_color_changed=self._on_wheel_changed)
        top_row.append(self.wheel)

        inputs_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        inputs_col.set_valign(Gtk.Align.CENTER)
        inputs_col.set_hexpand(True)

        # Live Color Preview Pill + Hex Entry
        hex_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl_hex = Gtk.Label(label="Hex")
        lbl_hex.add_css_class("dim-text")
        hex_row.append(lbl_hex)

        self.entry_hex = Gtk.Entry()
        self.entry_hex.set_max_length(7)
        self.entry_hex.set_width_chars(8)
        self.entry_hex.set_text("#00FF00")
        self.entry_hex.connect("activate", self._on_hex_committed)
        focus_ctrl = Gtk.EventControllerFocus.new()
        focus_ctrl.connect("leave", lambda ctrl: self._on_hex_committed(self.entry_hex))
        self.entry_hex.add_controller(focus_ctrl)
        hex_row.append(self.entry_hex)
        inputs_col.append(hex_row)

        # R, G, B Clamped 0-255 SpinButtons
        self.spin_r = self._create_rgb_row(inputs_col, "R", 0)
        self.spin_g = self._create_rgb_row(inputs_col, "G", 255)
        self.spin_b = self._create_rgb_row(inputs_col, "B", 0)

        top_row.append(inputs_col)
        self.append(top_row)

        # Quick Swatches: 8 Factory + 8 User-Saveable
        lbl_factory = Gtk.Label()
        lbl_factory.set_markup("<span size='small' color='#94a3b8'>Factory Swatches</span>")
        lbl_factory.set_xalign(0)
        self.append(lbl_factory)

        factory_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        for rgb in FACTORY_SWATCHES:
            btn = self._make_swatch_button(rgb, f"Factory {rgb_to_hex(rgb)}")
            btn.connect("clicked", lambda b, c=rgb: self.set_color(c, emit=True))
            factory_row.append(btn)
        self.append(factory_row)

        user_head = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        lbl_user = Gtk.Label()
        lbl_user.set_markup("<span size='small' color='#94a3b8'>User Swatches (Persistent)</span>")
        lbl_user.set_xalign(0)
        lbl_user.set_hexpand(True)
        user_head.append(lbl_user)

        btn_save_swatch = Gtk.Button(label="💾 Save to Slot")
        btn_save_swatch.add_css_class("ghost-btn")
        btn_save_swatch.set_tooltip_text("Save current color into the active user swatch slot")
        btn_save_swatch.connect("clicked", self._on_save_user_swatch)
        user_head.append(btn_save_swatch)
        self.append(user_head)

        self.user_swatch_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.user_swatch_btns: List[Gtk.Button] = []
        self._rebuild_user_swatches()
        self.append(self.user_swatch_row)

        # Gradient Editor (2 to 6 stops)
        self.gradient_editor = GradientEditorWidget(
            on_stops_changed=self._on_gradient_stops_changed,
            on_stop_selected=lambda col: self.set_color(col, emit=False),
        )
        self.append(self.gradient_editor)

    def _create_rgb_row(self, parent: Gtk.Box, channel_label: str, initial: int) -> Gtk.SpinButton:
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        lbl = Gtk.Label(label=f"{channel_label}:")
        lbl.set_width_chars(2)
        lbl.add_css_class("dim-text")
        row.append(lbl)

        adj = Gtk.Adjustment(value=initial, lower=0, upper=255, step_increment=1, page_increment=10, page_size=0)
        spin = Gtk.SpinButton(adjustment=adj, climb_rate=1, digits=0)
        spin.set_numeric(True)
        spin.connect("value-changed", self._on_rgb_spin_changed)
        row.append(spin)
        parent.append(row)
        return spin

    def _make_swatch_button(self, rgb: RGBTuple, tooltip: str) -> Gtk.Button:
        btn = Gtk.Button()
        btn.add_css_class("color-swatch")
        btn.set_tooltip_text(tooltip)
        area = Gtk.DrawingArea()
        area.set_content_width(22)
        area.set_content_height(20)
        area.set_draw_func(lambda a, cr, w, h, c=rgb: self._draw_swatch(cr, w, h, c))
        btn.set_child(area)
        return btn

    @staticmethod
    def _draw_swatch(cr: cairo.Context, w: int, h: int, rgb: RGBTuple) -> None:
        _rounded_rect(cr, 1.0, 1.0, w - 2.0, h - 2.0, 4.0)
        cr.set_source_rgb(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)
        cr.fill()

    def _rebuild_user_swatches(self) -> None:
        while True:
            child = self.user_swatch_row.get_first_child()
            if not child:
                break
            self.user_swatch_row.remove(child)
        self.user_swatch_btns.clear()

        for idx, rgb in enumerate(self.user_swatches[:8]):
            btn = self._make_swatch_button(rgb, f"User Slot {idx + 1}: {rgb_to_hex(rgb)}")
            if idx == self.selected_user_slot:
                btn.add_css_class("active")
            btn.connect("clicked", self._on_user_swatch_clicked, idx)
            self.user_swatch_row.append(btn)
            self.user_swatch_btns.append(btn)

    def _on_user_swatch_clicked(self, btn: Gtk.Button, idx: int) -> None:
        self.selected_user_slot = idx
        for i, b in enumerate(self.user_swatch_btns):
            if i == idx:
                b.add_css_class("active")
            else:
                b.remove_css_class("active")
        self.set_color(self.user_swatches[idx], emit=True)

    def _on_save_user_swatch(self, btn: Gtk.Button) -> None:
        self.user_swatches[self.selected_user_slot] = self.current_rgb
        self._rebuild_user_swatches()
        if self.on_user_swatches_changed:
            self.on_user_swatches_changed(list(self.user_swatches))

    def set_color(self, rgb: RGBTuple, emit: bool = False) -> None:
        self.current_rgb = clamp_rgb(*rgb)
        self._updating_widgets = True
        try:
            self.wheel.set_rgb(self.current_rgb, emit=False)
            self.entry_hex.set_text(rgb_to_hex(self.current_rgb))
            self.spin_r.set_value(self.current_rgb[0])
            self.spin_g.set_value(self.current_rgb[1])
            self.spin_b.set_value(self.current_rgb[2])
        finally:
            self._updating_widgets = False

        if emit:
            self.gradient_editor.update_selected_stop_color(self.current_rgb, emit=False)
            if self.on_color_changed:
                self.on_color_changed(self.current_rgb)

    def _on_wheel_changed(self, rgb: RGBTuple) -> None:
        if self._updating_widgets:
            return
        self.current_rgb = clamp_rgb(*rgb)
        self._updating_widgets = True
        try:
            self.entry_hex.set_text(rgb_to_hex(self.current_rgb))
            self.spin_r.set_value(self.current_rgb[0])
            self.spin_g.set_value(self.current_rgb[1])
            self.spin_b.set_value(self.current_rgb[2])
        finally:
            self._updating_widgets = False
        self.gradient_editor.update_selected_stop_color(self.current_rgb, emit=True)
        if self.on_color_changed:
            self.on_color_changed(self.current_rgb)

    def _on_hex_committed(self, entry: Gtk.Entry) -> None:
        if self._updating_widgets:
            return
        parsed = hex_to_rgb(entry.get_text())
        if parsed is not None:
            self.set_color(parsed, emit=True)
        else:
            entry.set_text(rgb_to_hex(self.current_rgb))

    def _on_rgb_spin_changed(self, spin: Gtk.SpinButton) -> None:
        if self._updating_widgets:
            return
        r = clamp_channel(self.spin_r.get_value())
        g = clamp_channel(self.spin_g.get_value())
        b = clamp_channel(self.spin_b.get_value())
        self.set_color((r, g, b), emit=True)

    def _on_gradient_stops_changed(self, stops: List[GradientStop]) -> None:
        if self.on_gradient_changed:
            self.on_gradient_changed(stops)


# ---------------------------------------------------------------------------
# 4. Interactive 2D Device SVG/Vector Canvas with Marquee & Trigger Modes
# ---------------------------------------------------------------------------
class DeviceLightingCanvas(Gtk.DrawingArea):
    """
    Renders an interactive 2D graphic of the active peripheral (Keyboard, Keypad,
    Mouse, or Controller) at 60 FPS, supporting:
    - Single-click LED selection and marquee drag-box zone selection
    - Live keypress/click input trigger mode for Ripple, Reactive, Ripple Line, and Heatmap
    """
    def __init__(
        self,
        on_selection_changed: Optional[Callable[[Set[str]], None]] = None,
        on_node_pressed: Optional[Callable[[str], None]] = None,
        on_node_released: Optional[Callable[[str], None]] = None,
    ):
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_content_width(860)
        self.set_content_height(265)

        self.category: str = "keyboard"
        self.nodes: List[LEDNode] = []
        self.frame_colors: Dict[str, RGBTuple] = {}
        self.selected_ids: Set[str] = set()
        self.interaction_mode: str = "select"  # "select" | "trigger"

        self.on_selection_changed = on_selection_changed
        self.on_node_pressed = on_node_pressed
        self.on_node_released = on_node_released

        self._marquee_rect: Optional[Tuple[float, float, float, float]] = None
        self._drag_start_device: Tuple[float, float] = (0.0, 0.0)
        self._active_trigger_node: Optional[str] = None
        self._scale: float = 1.0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0

        self.set_draw_func(self._on_draw)

        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_pressed)
        click.connect("released", self._on_released)
        self.add_controller(click)

        drag = Gtk.GestureDrag.new()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    def set_topology(self, category: str, nodes: List[LEDNode]) -> None:
        self.category = category
        self.nodes = list(nodes)
        self.selected_ids.clear()
        self.queue_draw()

    def set_frame(self, frame: Dict[str, RGBTuple]) -> None:
        self.frame_colors = frame
        self.queue_draw()

    def set_selected_ids(self, ids: Set[str], emit: bool = False) -> None:
        self.selected_ids = set(ids)
        self.queue_draw()
        if emit and self.on_selection_changed:
            self.on_selection_changed(set(self.selected_ids))

    def _compute_transform(self, width: int, height: int) -> Tuple[float, float, float, float, float]:
        if not self.nodes:
            return 1.0, 0.0, 0.0, 100.0, 100.0
        max_x = max(n.rx + n.rw for n in self.nodes) + 14.0
        max_y = max(n.ry + n.rh for n in self.nodes) + 14.0
        scale = min((width - 16.0) / max(1.0, max_x), (height - 16.0) / max(1.0, max_y), 1.35)
        scale = max(0.4, scale)
        ox = (width - max_x * scale) * 0.5
        oy = (height - max_y * scale) * 0.5
        return scale, ox, oy, max_x, max_y

    def _widget_to_device(self, wx: float, wy: float) -> Tuple[float, float]:
        s = max(0.1, self._scale)
        return ((wx - self._offset_x) / s, (wy - self._offset_y) / s)

    def _hit_test(self, dx: float, dy: float) -> Optional[LEDNode]:
        for n in reversed(self.nodes):
            if n.rx <= dx <= (n.rx + n.rw) and n.ry <= dy <= (n.ry + n.rh):
                return n
        return None

    def _draw_chassis_silhouette(self, cr: cairo.Context, max_x: float, max_y: float) -> None:
        if self.category == "mouse":
            cx = 260.0
            _rounded_rect(cr, cx - 110.0, 14.0, 220.0, 228.0, 82.0)
            cr.set_source_rgb(0.09, 0.12, 0.16)
            cr.fill_preserve()
            cr.set_line_width(2.0)
            cr.set_source_rgb(0.20, 0.27, 0.36)
            cr.stroke()
        elif self.category == "controller":
            cx = 300.0
            _rounded_rect(cr, cx - 210.0, 10.0, 420.0, 232.0, 64.0)
            cr.set_source_rgb(0.09, 0.12, 0.16)
            cr.fill_preserve()
            cr.set_line_width(2.0)
            cr.set_source_rgb(0.20, 0.27, 0.36)
            cr.stroke()
        else:
            _rounded_rect(cr, 2.0, 2.0, max_x - 4.0, max_y - 4.0, 14.0)
            cr.set_source_rgb(0.09, 0.12, 0.16)
            cr.fill_preserve()
            cr.set_line_width(1.6)
            cr.set_source_rgb(0.18, 0.24, 0.33)
            cr.stroke()

    def _on_draw(self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int) -> None:
        scale, ox, oy, max_x, max_y = self._compute_transform(width, height)
        self._scale = scale
        self._offset_x = ox
        self._offset_y = oy

        cr.save()
        cr.translate(ox, oy)
        cr.scale(scale, scale)

        self._draw_chassis_silhouette(cr, max_x, max_y)

        # Render each LED node
        for n in self.nodes:
            r, g, b = self.frame_colors.get(n.id, (0, 255, 0))
            rf, gf, bf = r / 255.0, g / 255.0, b / 255.0
            lum = max(rf, gf, bf)
            is_sel = n.id in self.selected_ids

            cx = n.rx + n.rw * 0.5
            cy = n.ry + n.rh * 0.5

            # Soft outer LED bloom when lit
            if lum > 0.08:
                glow_r = max(n.rw, n.rh) * 0.72
                glow = cairo.RadialGradient(cx, cy, 2.0, cx, cy, glow_r)
                glow.add_color_stop_rgba(0.0, rf, gf, bf, 0.42 * lum)
                glow.add_color_stop_rgba(1.0, rf, gf, bf, 0.0)
                cr.set_source(glow)
                cr.arc(cx, cy, glow_r, 0.0, 2.0 * math.pi)
                cr.fill()

            # Node geometry path
            if n.shape == "circle":
                rad = min(n.rw, n.rh) * 0.5
                cr.arc(cx, cy, rad, 0.0, 2.0 * math.pi)
            elif n.shape == "pill":
                _rounded_rect(cr, n.rx, n.ry, n.rw, n.rh, min(n.rw, n.rh) * 0.45)
            elif n.shape == "bar":
                _rounded_rect(cr, n.rx, n.ry, n.rw, n.rh, 3.0)
            else:
                _rounded_rect(cr, n.rx, n.ry, n.rw, n.rh, 5.0)

            # Interior fill (blend dark cap with vivid backlight)
            fill_r = 0.11 + rf * 0.78
            fill_g = 0.14 + gf * 0.78
            fill_b = 0.19 + bf * 0.78
            cr.set_source_rgb(fill_r, fill_g, fill_b)
            cr.fill_preserve()

            # Keycap / Zone border
            if is_sel:
                cr.set_line_width(2.4)
                cr.set_source_rgb(1.0, 1.0, 1.0)
            elif lum > 0.05:
                cr.set_line_width(1.3)
                cr.set_source_rgba(rf, gf, bf, 0.95)
            else:
                cr.set_line_width(1.0)
                cr.set_source_rgba(0.24, 0.31, 0.42, 0.9)
            cr.stroke()

            # Label text (skip tiny underglow bars)
            if n.shape != "bar" and n.rw >= 20.0 and n.rh >= 18.0:
                cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
                cr.set_font_size(9.5 if len(n.label) <= 3 else 8.0)
                ext = cr.text_extents(n.label)
                tx = cx - (ext.width * 0.5 + ext.x_bearing)
                ty = cy - (ext.height * 0.5 + ext.y_bearing)
                # Contrast-aware text color
                if (rf * 0.299 + gf * 0.587 + bf * 0.114) > 0.62:
                    cr.set_source_rgb(0.05, 0.07, 0.10)
                else:
                    cr.set_source_rgb(0.96, 0.98, 1.0)
                cr.move_to(tx, ty)
                cr.show_text(n.label)

        # Marquee Selection Box
        if self._marquee_rect is not None:
            x1, y1, x2, y2 = self._marquee_rect
            mx, my = min(x1, x2), min(y1, y2)
            mw, mh = abs(x2 - x1), abs(y2 - y1)
            cr.rectangle(mx, my, mw, mh)
            cr.set_source_rgba(0.13, 0.77, 0.37, 0.18)
            cr.fill_preserve()
            cr.set_line_width(1.5)
            cr.set_dash([5.0, 3.0])
            cr.set_source_rgba(0.13, 0.77, 0.37, 0.95)
            cr.stroke()
            cr.set_dash([])

        cr.restore()

    def _on_pressed(self, gesture, n_press: int, x: float, y: float) -> None:
        dx, dy = self._widget_to_device(x, y)
        hit = self._hit_test(dx, dy)
        if self.interaction_mode == "trigger":
            if hit is not None:
                self._active_trigger_node = hit.id
                if self.on_node_pressed:
                    self.on_node_pressed(hit.id)
            return

        # Selection mode: single click toggles the clicked LED
        if hit is not None:
            if hit.id in self.selected_ids:
                self.selected_ids.remove(hit.id)
            else:
                self.selected_ids.add(hit.id)
            self.queue_draw()
            if self.on_selection_changed:
                self.on_selection_changed(set(self.selected_ids))

    def _on_released(self, gesture, n_press: int, x: float, y: float) -> None:
        if self._active_trigger_node is not None:
            nid = self._active_trigger_node
            self._active_trigger_node = None
            if self.on_node_released:
                self.on_node_released(nid)

    def _on_drag_begin(self, gesture, start_x: float, start_y: float) -> None:
        if self.interaction_mode != "select":
            return
        self._drag_start_device = self._widget_to_device(start_x, start_y)
        self._marquee_rect = None

    def _on_drag_update(self, gesture, offset_x: float, offset_y: float) -> None:
        if self.interaction_mode != "select":
            return
        if math.hypot(offset_x, offset_y) < 6.0:
            return
        sx, sy = self._drag_start_device
        ex, ey = sx + offset_x / max(0.1, self._scale), sy + offset_y / max(0.1, self._scale)
        self._marquee_rect = (sx, sy, ex, ey)
        self.selected_ids = select_nodes_in_rect(self.nodes, sx, sy, ex, ey)
        self.queue_draw()
        if self.on_selection_changed:
            self.on_selection_changed(set(self.selected_ids))

    def _on_drag_end(self, gesture, offset_x: float, offset_y: float) -> None:
        if self._marquee_rect is not None:
            self._marquee_rect = None
            self.queue_draw()
