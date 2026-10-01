"""
Global GTK4 CSS Theme Engine & Style Providers for the Strop Suite.
Polychromatic Dark Slate & Emerald Theme.
"""

from typing import Optional
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
from gi.repository import Gtk, Gdk, GLib



BASE_CSS = b"""
* {
    font-family: "Ubuntu", "Inter", "Cantarell", "DejaVu Sans", "Liberation Sans", "Noto Sans", sans-serif;
}

window.hub-window,
window.main-window {
    background-color: #12161d;
    color: #e2e8f0;
}

label {
    color: #e2e8f0;
}

.dim-label,
.dim-text {
    color: #94a3b8;
    font-size: 11.5px;
}

/* Polychromatic Cards */
.hub-card {
    background: linear-gradient(160deg, #1b2330, #141a24);
    border: 1px solid #283444;
    border-radius: 12px;
    padding: 16px;
}

.hub-card:hover {
    border-color: #22c55e;
    background: linear-gradient(160deg, #202b3a, #161e2a);
    box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4);
}

.dock-card,
.card {
    background-color: #161c26;
    border: 1px solid #283444;
    border-radius: 12px;
    padding: 12px;
}

.badge-assigned {
    background: #14281e;
    color: #86efac;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 10px;
    border: 1px solid #22c55e;
}

.badge-stock {
    background: #161c26;
    color: #94a3b8;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 10px;
    border: 1px solid #283444;
}

.remap-row {
    background-color: #141a24;
    border: 1px solid #243040;
    border-radius: 6px;
    padding: 4px 8px;
    margin-bottom: 3px;
}

.quick-tag {
    background: #132219;
    border: 1px solid #1f3b2b;
    border-radius: 5px;
    color: #86efac;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 6px;
}

.quick-tag:hover {
    border-color: #22c55e;
    background: #1a3325;
    color: #bbf7d0;
}

.mouse-plate-card {
    background: linear-gradient(160deg, #1b2330, #141a24);
    border: 1px solid #283444;
    border-radius: 14px;
    padding: 14px 16px;
}

.chassis {
    background: linear-gradient(160deg, #1d2533, #131822);
    border: 1px solid #2c394b;
    border-radius: 16px;
    padding: 14px 20px;
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.05);
}

/* Keypad & Keyboard Keycaps: Polychromatic Dark Slate Tiles */
.key-btn,
.mouse-btn {
    background: #1f2735;
    border: 1px solid #334257;
    border-radius: 6px;
    color: #f8fafc;
    font-size: 11px;
    font-weight: 700;
    padding: 2px 4px;
    min-width: 28px;
    min-height: 28px;
}


.key-btn:hover,
.mouse-btn:hover {
    border-color: #22c55e;
    background: #273345;
    color: #ffffff;
}

/* Remapped Keys: Deep Emerald Tint + Radiant Mint Glow */
.key-btn.assigned,
.mouse-btn.assigned {
    background: #14281e;
    border-color: #22c55e;
    color: #86efac;
    box-shadow: 0 0 4px rgba(34, 197, 94, 0.25);
}

.key-btn.selected,
.mouse-btn.selected {
    border-color: #22c55e;
    border-width: 2px;
    box-shadow: 0 0 8px rgba(34, 197, 94, 0.45);
}

/* DPAD Buttons */
.dpad-btn {
    background: #1f2735;
    border: 1px solid #334257;
    border-radius: 6px;
    color: #f8fafc;
    font-size: 13px;
    font-weight: 700;
    min-width: 36px;
    min-height: 36px;
    padding: 0;
}

.dpad-btn:hover {
    border-color: #22c55e;
    background: #273345;
}

.dpad-btn.assigned {
    background: #14281e;
    border-color: #22c55e;
    color: #86efac;
    box-shadow: 0 0 4px rgba(34, 197, 94, 0.25);
}

.dpad-btn.selected {
    border-color: #22c55e;
    border-width: 2px;
    box-shadow: 0 0 8px rgba(34, 197, 94, 0.45);
}

/* Quick Function Pills */
.func-btn {
    background: #132219;
    border: 1px solid #1f3b2b;
    border-radius: 5px;
    color: #86efac;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 6px;
}

.func-btn:hover {
    border-color: #22c55e;
    background: #1a3325;
    color: #bbf7d0;
}

/* Primary Action Buttons */
.primary-card-btn,
.primary-btn {
    background: #14532d;
    color: #ffffff;
    font-weight: 700;
    font-size: 11.5px;
    border-radius: 6px;
    border: 1px solid #16a34a;
    padding: 7px 12px;
}

.primary-card-btn:hover,
.primary-btn:hover {
    background: #166534;
    border-color: #22c55e;
    color: #ffffff;
    box-shadow: 0 0 6px rgba(34, 197, 94, 0.3);
}

.record-btn {
    background: #132219;
    border: 1px solid #22c55e;
    color: #86efac;
    font-weight: 700;
    font-size: 11px;
    border-radius: 6px;
    padding: 6px 10px;
}

.record-btn:hover {
    background: #1a3325;
    color: #bbf7d0;
}

.record-btn.recording {
    background: #7f1d1d;
    border-color: #ef4444;
    color: #fecaca;
}

.ghost-btn {
    background: #18202b;
    border: 1px solid #2b384a;
    border-radius: 6px;
    color: #e2e8f0;
    font-size: 11px;
    font-weight: 600;
    padding: 6px 10px;
}

.ghost-btn:hover {
    border-color: #22c55e;
    color: #86efac;
    background: #1e2837;
}

.danger-btn {
    background: #1a1e26;
    color: #ef4444;
    border: 1px solid #3d2328;
    font-size: 11px;
    font-weight: 600;
    border-radius: 6px;
    padding: 5px 8px;
}

.danger-btn:hover {
    border-color: #ef4444;
    background: #2e171b;
}

.badge-device {
    background: #132219;
    color: #86efac;
    font-size: 12.5px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 8px;
    border: 1px solid #22c55e;
}


.assigned-row {
    background-color: #141a24;
    border: 1px solid #243040;
    border-radius: 6px;
    padding: 4px 8px;
    margin-bottom: 3px;
}

/* Flat Form Controls */
entry, dropdown button {
    background-color: #161c26;
    border: 1px solid #2b384a;
    border-radius: 6px;
    color: #f8fafc;
    padding: 4px 8px;
    font-size: 11.5px;
}

entry:focus {
    border-color: #22c55e;
    box-shadow: 0 0 4px rgba(34, 197, 94, 0.35);
}

/* Clean Notebook Tabs */
notebook tab {
    background-color: #141a24;
    color: #94a3b8;
    border: 1px solid transparent;
    border-radius: 6px 6px 0 0;
    padding: 4px 10px;
    font-weight: 600;
    font-size: 11px;
}

notebook tab:checked {
    background-color: #1b2330;
    color: #22c55e;
    border: 1px solid #283444;
    border-bottom: 1px solid #1b2330;
}

/* HUD Overlay Window Styling */
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

/* Status & Notification Alert Cards */
.alert-warning {
    background: linear-gradient(160deg, #2b1d14, #1c1511);
    border: 1px solid #f97316;
    border-radius: 10px;
    padding: 10px 14px;
}

.alert-info {
    background: linear-gradient(160deg, #13222a, #101920);
    border: 1px solid #38bdf8;
    border-radius: 10px;
    padding: 10px 14px;
}

/* In-App Non-Blocking Toast Banner */

.toast-banner {
    background: rgba(20, 30, 24, 0.96);
    border: 1px solid #22c55e;
    border-radius: 8px;
    padding: 8px 16px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5), 0 0 10px rgba(34, 197, 94, 0.35);
}

/* Lighting Color Picker Swatches */
.color-swatch {
    min-width: 26px;
    min-height: 26px;
    padding: 0;
    border-radius: 6px;
    border: 2px solid #2d3748;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
}

.color-swatch:hover {
    border-color: #f8fafc;
    box-shadow: 0 0 8px rgba(255, 255, 255, 0.5);
}

.color-swatch.active {
    border-color: #ffffff;
    border-width: 2px;
    box-shadow: 0 0 10px rgba(255, 255, 255, 0.85);
}
"""





def apply_theme(extra_css: bytes = b"") -> None:
    """Applies the unified Polychromatic GTK4 stylesheet and ensures the Strop application icon is bound."""
    # Set prgname matching the desktop file ID for GNOME Shell and Wayland compositors
    GLib.set_prgname("com.razer.strop")
    GLib.set_application_name("Strop")


    provider = Gtk.CssProvider()
    full_css = BASE_CSS + b"\n" + extra_css if extra_css else BASE_CSS
    provider.load_from_data(full_css)
    display = Gdk.Display.get_default()
    if display:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        # Register local assets directory into GTK4 icon theme search path as fallback
        try:
            from pathlib import Path
            local_assets = Path(__file__).parent.parent / "assets"
            if local_assets.exists():
                icon_theme = Gtk.IconTheme.get_for_display(display)
                icon_theme.add_search_path(str(local_assets))
        except Exception:
            pass


def show_about_dialog(parent_window: Optional[Gtk.Window] = None) -> Optional[Gtk.AboutDialog]:
    """Presents the standard GTK4 About dialog for Strop."""
    from strop_core import __version__
    if Gdk.Display.get_default() is None:
        try:
            Gtk.init_check()
        except Exception:
            pass
        if Gdk.Display.get_default() is None:
            return None

    about = Gtk.AboutDialog()
    if parent_window:
        about.set_transient_for(parent_window)
        about.set_modal(True)

    about.set_program_name("Strop")
    about.set_version(__version__)
    about.set_comments("Putting the sharpest edge on your Razer gaming hardware on Linux.\nUnified GTK4 remap studios, in-game HUDs, and macro composer. Catalog entries are layout references; see the support matrix for officially supported devices.")
    about.set_website("https://github.com/strop-linux/strop")
    about.set_website_label("GitHub Repository")
    about.set_authors(["Strop Linux Contributors <https://github.com/strop-linux/strop>"])
    about.set_copyright("Copyright © 2026 Strop Linux Contributors\nLicensed under the GNU General Public License v3.0 (GPLv3).")
    about.set_license_type(Gtk.License.GPL_3_0)
    about.set_logo_icon_name("strop")

    # Try loading custom logo texture from local assets if available
    try:
        from pathlib import Path
        icon_path = Path(__file__).parent.parent / "assets" / "strop_icon.png"
        if icon_path.exists():
            about.set_logo(Gdk.Texture.new_from_filename(str(icon_path)))
    except Exception:
        pass

    about.present()
    return about

