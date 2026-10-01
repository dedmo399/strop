"""
Smooth, non-blocking in-app notification toasts for GTK4.
Renders an unobtrusive floating banner that slides or appears inside the window container.
"""

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GLib


class StropToast(Gtk.Box):
    """Floating non-blocking status banner that automatically dismisses."""
    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("toast-banner")
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self.set_margin_bottom(16)
        self.set_visible(False)

        self.icon_lbl = Gtk.Label()
        self.icon_lbl.set_markup("<span size='medium'>⚡</span>")
        self.append(self.icon_lbl)

        self.msg_lbl = Gtk.Label()
        self.msg_lbl.set_markup("<span weight='bold' color='#f8fafc'>Notification</span>")
        self.append(self.msg_lbl)

        self.btn_dismiss = Gtk.Button(label="✕")
        self.btn_dismiss.add_css_class("ghost-btn")
        self.btn_dismiss.connect("clicked", lambda w: self.dismiss())
        self.append(self.btn_dismiss)

        self._timeout_id = None

    def show_message(self, message: str, icon: str = "⚡", timeout_ms: int = 2500):
        """Displays toast message with an icon and auto-dismisses."""
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

        self.icon_lbl.set_markup(f"<span size='medium'>{icon}</span>")
        self.msg_lbl.set_markup(f"<span weight='semibold' color='#f8fafc'>{GLib.markup_escape_text(message)}</span>")
        self.set_visible(True)

        if timeout_ms > 0:
            self._timeout_id = GLib.timeout_add(timeout_ms, self._on_timeout)

    def _on_timeout(self):
        self.dismiss()
        return False

    def dismiss(self):
        self.set_visible(False)
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None
