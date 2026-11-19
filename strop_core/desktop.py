"""
Desktop environment and compositor helpers for Strop (KDE Plasma, GNOME, Wayland, X11).
"""

import json
import os
import tempfile
from typing import Callable, Mapping, Optional

from strop_core.logger import get_logger
from strop_core.x11 import pin_window_on_top

logger = get_logger("strop.desktop")


def is_kde(environ: Optional[Mapping[str, str]] = None) -> bool:
    """Returns True when running inside a KDE / Plasma desktop session."""
    env = os.environ if environ is None else environ
    if env.get("KDE_FULL_SESSION", "").strip().lower() == "true":
        return True
    desktop = env.get("XDG_CURRENT_DESKTOP", "").lower()
    session = env.get("DESKTOP_SESSION", "").lower()
    return "kde" in desktop or "plasma" in desktop or "plasma" in session


def session_type(environ: Optional[Mapping[str, str]] = None) -> str:
    """Returns 'wayland', 'x11', or 'unknown' for the active graphical session."""
    env = os.environ if environ is None else environ
    stype = env.get("XDG_SESSION_TYPE", "").strip().lower()
    if stype in ("wayland", "x11"):
        return stype
    if env.get("WAYLAND_DISPLAY"):
        return "wayland"
    if env.get("DISPLAY"):
        return "x11"
    return "unknown"


def is_kde_wayland(environ: Optional[Mapping[str, str]] = None) -> bool:
    """Returns True when running inside KDE Plasma on a Wayland session."""
    return is_kde(environ) and session_type(environ) == "wayland"


def pin_kwin_window_on_top(
    target_title: str = "Strop HUD Overlay",
    x: int = 12,
    y: int = 12,
    connection=None,
) -> bool:
    """
    Uses KWin's D-Bus Scripting API (org.kde.kwin.Scripting) on KDE Plasma
    to mark the matching HUD window keepAbove, onAllDesktops, skipTaskbar,
    and position it at (x, y). Degrades cleanly when KWin is unavailable.
    """
    if not target_title:
        return False

    tmp_path = None
    try:
        from gi.repository import Gio, GLib

        bus = connection if connection is not None else Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if bus is None:
            return False

        title_json = json.dumps(target_title)
        script_body = f"""
var targetTitle = {title_json};
var clients = workspace.windowList ? workspace.windowList() : workspace.clientList();
for (var i = 0; i < clients.length; i++) {{
    var w = clients[i];
    if (w && w.caption && w.caption.indexOf(targetTitle) !== -1) {{
        w.keepAbove = true;
        w.onAllDesktops = true;
        w.skipTaskbar = true;
        w.skipPager = true;
        if (w.frameGeometry !== undefined) {{
            var g = w.frameGeometry;
            w.frameGeometry = {{ x: {int(x)}, y: {int(y)}, width: g.width, height: g.height }};
        }}
        break;
    }}
}}
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".js", prefix="strop_kwin_", delete=False, encoding="utf-8"
        ) as tf:
            tf.write(script_body)
            tmp_path = tf.name

        plugin_name = f"strop_hud_pin_{os.getpid()}"
        load_res = bus.call_sync(
            "org.kde.KWin",
            "/Scripting",
            "org.kde.kwin.Scripting",
            "loadScript",
            GLib.Variant("(ss)", (tmp_path, plugin_name)),
            GLib.VariantType("(i)"),
            Gio.DBusCallFlags.NONE,
            1500,
            None,
        )
        script_id = int(load_res.unpack()[0])
        if script_id < 0:
            return False

        script_path = f"/Scripting/Script{script_id}"
        try:
            bus.call_sync(
                "org.kde.KWin",
                script_path,
                "org.kde.kwin.Script",
                "run",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                1500,
                None,
            )
        finally:
            try:
                bus.call_sync(
                    "org.kde.KWin",
                    "/Scripting",
                    "org.kde.kwin.Scripting",
                    "unloadScript",
                    GLib.Variant("(s)", (plugin_name,)),
                    GLib.VariantType("(b)"),
                    Gio.DBusCallFlags.NONE,
                    1500,
                    None,
                )
            except Exception:
                pass
        return True
    except Exception as exc:
        logger.debug(f"KWin scripting pin skipped: {exc}")
        return False
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def pin_hud_window_on_top(
    target_title: str = "Strop HUD Overlay",
    x: int = 12,
    y: int = 12,
    x11_pin_fn: Optional[Callable[[str, int, int], bool]] = None,
) -> bool:
    """
    Pins and positions the HUD window on top across X11, XWayland, and KDE KWin Wayland.
    """
    x11_fn = x11_pin_fn or pin_window_on_top
    if is_kde_wayland():
        if pin_kwin_window_on_top(target_title, x, y):
            return True
    return bool(x11_fn(target_title, x, y))
