"""Shared HUD labels and per-device launch/control helpers."""

import hashlib
import logging
import subprocess
import sys
from pathlib import Path

from strop_core.device import clean_device_display_name
from strop_core.gamepad import parse_gamepad_display_text

LOG = logging.getLogger(__name__)


def hud_application_id(device_name):
    name = clean_device_display_name(device_name or "Razer Tartarus Pro")
    return "com.razer.strop.hud.d" + hashlib.sha256(name.encode()).hexdigest()[:24]


def launch_hud(device_name=None):
    script = Path(__file__).resolve().parent.parent / "strop_hud.py"
    command = [sys.executable, str(script)]
    if device_name:
        command.extend(["--device", device_name])
    return subprocess.Popen(command)


def format_output(output):
    text = (output or "").strip()
    gamepad = parse_gamepad_display_text(text)
    if gamepad:
        return gamepad
    if text.lower() == "disable":
        return "off"
    if "macro" in text.lower() or any(c in text for c in "+(),\"';.\n"):
        return "macro"
    return text


def binding_label(state):
    """Return display text and whether this is a custom setting."""
    custom = (state.get("custom_name") or "").strip()
    output = (state.get("output") or "").strip()
    if custom or output:
        return custom or format_output(output), True
    return state.get("default_label", ""), False


class HUDClient:
    """Observe a HUD's exported visibility action; never launch it to query it."""

    def __init__(self, device_name, changed):
        from gi.repository import Gio
        self.device_name = device_name
        self.application_id = hud_application_id(device_name)
        self.path = "/" + self.application_id.replace(".", "/")
        self.changed = changed
        self.group = None
        self.connection = None
        self.running = False
        self.visible = False
        self.owned = False
        self.process = None
        self.watch = Gio.bus_watch_name(
            Gio.BusType.SESSION, self.application_id, Gio.BusNameWatcherFlags.NONE,
            self._appeared, self._vanished,
        )

    def _appeared(self, connection, name, owner):
        from gi.repository import Gio
        self.running = True
        self.connection = connection
        self.group = Gio.DBusActionGroup.get(connection, name, self.path)
        self.group.connect("action-added", self._state_changed)
        self.group.connect("action-state-changed", self._state_changed)
        self.group.list_actions()  # Begin asynchronous action discovery.
        self.changed()

    def _state_changed(self, group, action, *args):
        if action == "visible":
            state = group.get_action_state("visible")
            self.visible = bool(state and state.unpack())
            self.changed()

    def _vanished(self, connection, name):
        if self.running:
            self.owned = False
            self.process = None
        self.group = None
        self.connection = None
        self.running = self.visible = False
        self.changed()

    def toggle(self):
        if self.visible and self.group:
            self.group.activate_action("hide", None)
        else:
            # Even before action discovery, application activation presents it.
            if not self.running:
                if self.process and self.process.poll() is None:
                    return
                self.process = launch_hud(self.device_name)
                self.owned = True
            else:
                launch_hud(self.device_name)

    def refresh(self):
        if self.group:
            self.group.activate_action("refresh", None)

    def close(self):
        from gi.repository import Gio, GLib
        if self.owned:
            if self.group:
                self.group.activate_action("quit", None)
                # Remote activation is asynchronous. Deliver quit before dropping
                # the proxy/connection or letting the owning application exit.
                if self.connection:
                    try:
                        self.connection.flush_sync(None)
                    except GLib.Error:
                        LOG.exception("Could not flush HUD shutdown action")
            elif self.process and self.process.poll() is None:
                self.process.terminate()
        Gio.bus_unwatch_name(self.watch)
        self.group = None
        self.connection = None
