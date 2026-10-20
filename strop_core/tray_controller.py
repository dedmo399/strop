"""Background device/profile refresh and tray actions shared with the Hub."""

import logging
import subprocess
import sys
import threading
from pathlib import Path

from gi.repository import Gio, GLib

from strop_core.device import scan_all_connected_devices
from strop_core.presets import (
    list_device_presets, get_active_profile, get_injection_state, check_daemon_status,
    run_profile_operation_async,
)
from strop_core.hud import HUDClient
from strop_core.tray import MenuItem, TrayService

LOG = logging.getLogger(__name__)


class TrayController:
    def __init__(self, app):
        self.app = app
        self.devices = []
        self.presets = {}
        self.states = {}
        self.last_profiles = {}
        self.results = {}
        self.diagnostics = []
        self.daemon_status = ("checking", "Checking remapping daemon…")
        self.busy = set()
        self.huds = {}
        self.closed = False
        self.refreshing = False
        self.refresh_pending = False
        self.generation = 0
        self.tray = None
        self.timer = 0
        connection = app.get_dbus_connection()
        if connection:
            try:
                self.tray = TrayService(connection, app.activate, self.refresh, self._availability)
            except Exception:
                LOG.exception("Tray setup failed")
        self._rebuild()
        self.timer = GLib.timeout_add_seconds(5, self.refresh)
        self.refresh()

    @property
    def available(self):
        return bool(self.tray and self.tray.available)

    def _availability(self, available):
        if not self.closed:
            self.app.tray_availability_changed(available)

    def refresh(self):
        if self.closed:
            return False
        if self.refreshing:
            self.refresh_pending = True
            return True
        self.refreshing = True
        generation = self.generation

        def worker():
            try:
                diagnostics = []
                devices = scan_all_connected_devices(diagnostics)
                daemon_status = check_daemon_status()
                presets, states, profiles = {}, {}, {}
                for device in devices:
                    name = device["name"]
                    presets[name] = list_device_presets(name)
                    states[name] = get_injection_state(name)
                    profiles[name] = get_active_profile(name)
                snapshot = (devices, presets, states, profiles, diagnostics, daemon_status)
            except Exception:
                LOG.exception("Tray refresh failed")
                snapshot = None
            GLib.idle_add(self._refreshed, generation, snapshot)

        threading.Thread(target=worker, name="strop-tray-refresh", daemon=True).start()
        return True

    def _refreshed(self, generation, snapshot):
        self.refreshing = False
        if self.closed:
            return False
        if generation == self.generation and snapshot is not None:
            (self.devices, self.presets, self.states, self.last_profiles,
             self.diagnostics, self.daemon_status) = snapshot
            for device in self.devices:
                name = device["name"]
                if self._is_keypad(device) and name not in self.huds:
                    self.huds[name] = HUDClient(name, self._rebuild)
            self._rebuild()
        if self.refresh_pending or generation != self.generation:
            self.refresh_pending = False
            self.refresh()
        return False

    @staticmethod
    def _is_keypad(device):
        return device.get("archetype", "").startswith("KEYPAD_")

    def launch(self, script, device=None):
        command = [sys.executable, str(Path(__file__).resolve().parent.parent / script)]
        if device:
            command.extend(["--device", device])
        try:
            subprocess.Popen(command)
        except OSError as error:
            self.notify("Could not launch Strop window", str(error))

    def notify(self, title, message):
        notification = Gio.Notification.new(title)
        notification.set_body(message)
        notification.set_icon(Gio.ThemedIcon.new("strop"))
        notification.set_default_action("app.open-hub")
        self.app.send_notification("profile-operation", notification)

    def show_hud(self, name):
        if name not in self.huds:
            self.huds[name] = HUDClient(name, self._rebuild)
        try:
            self.huds[name].toggle()
        except OSError as error:
            self.notify("Could not launch HUD", str(error))

    def operate(self, operation, name, preset=None, callback=None):
        if self.closed or name in self.busy:
            return False
        if name not in {device["name"] for device in self.devices}:
            return False
        if operation == "apply" and preset not in self.presets.get(name, []):
            return False
        self.busy.add(name)
        self.generation += 1
        self.results[name] = f"Applying {preset}…" if operation == "apply" else "Stopping remapping…"
        self._rebuild()

        def finished(result):
            if self.closed:
                return
            self.busy.discard(name)
            self.generation += 1
            self.results[name] = result.message
            if result.status == "applied" and name in self.huds:
                self.huds[name].refresh()
            self.notify("Profile " + result.status, result.message)
            self._rebuild()
            if callback:
                callback(result)
            self.refresh()

        run_profile_operation_async(operation, name, finished, GLib.idle_add, preset_name=preset)
        return True

    def menu_items(self):
        items = [MenuItem("hub", "Open Hub", self.app.activate),
                 MenuItem("macros", "Macro Studio", lambda: self.launch("strop_macro.py")),
                 MenuItem("refresh", "Refresh Devices", self.refresh),
                 MenuItem("daemon", "Remapping daemon: " + self.daemon_status[0], enabled=False)]
        for device in self.devices:
            name = device["name"]
            prefix = "device:" + name
            children = [MenuItem(prefix + ":studio", "Open Studio",
                                 lambda target=name: self.launch("strop_studio.py", target))]
            if self._is_keypad(device):
                hud = self.huds.get(name)
                label = "Hide HUD" if hud and hud.visible else "Show HUD"
                children.append(MenuItem(prefix + ":hud", label, lambda target=name: self.show_hud(target)))
            state = self.states.get(name, "unknown")
            children.extend([
                MenuItem(prefix + ":status", "Injection: " + state, enabled=False),
                MenuItem(prefix + ":last", "Last Strop profile: " + (self.last_profiles.get(name) or "None"), enabled=False),
            ])
            profiles = [MenuItem(prefix + ":preset:" + preset, preset,
                                 lambda target=name, profile=preset: self.operate("apply", target, profile),
                                 enabled=name not in self.busy)
                        for preset in self.presets.get(name, [])]
            if profiles:
                children.append(MenuItem(prefix + ":profiles", "Apply Profile", children=profiles))
            else:
                children.append(MenuItem(prefix + ":empty", "No saved profiles", enabled=False))
            children.append(MenuItem(prefix + ":stop", "Stop Remapping",
                                     lambda target=name: self.operate("stop", target), enabled=name not in self.busy))
            if name in self.results:
                children.append(MenuItem(prefix + ":result", self.results[name], enabled=False))
            items.append(MenuItem(prefix, device.get("clean_name", name), children=children))
        if not self.devices:
            items.append(MenuItem("empty", "No connected devices", enabled=False))
        for index, message in enumerate(self.diagnostics):
            items.append(MenuItem(f"diagnostic:{index}", message, enabled=False))
        items.append(MenuItem("quit", "Quit Strop", self.app.quit))
        return items

    def _rebuild(self):
        if self.closed:
            return
        if self.tray:
            self.tray.update(self.menu_items())
        self.app.tray_state_changed(self)

    def close(self):
        self.closed = True
        if self.timer:
            GLib.source_remove(self.timer)
        for hud in self.huds.values():
            hud.close()
        connection = self.app.get_dbus_connection()
        if connection:
            try:
                connection.flush_sync(None)
            except GLib.Error:
                LOG.exception("Could not flush HUD shutdown actions")
        if self.tray:
            self.tray.close()
