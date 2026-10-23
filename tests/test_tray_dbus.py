"""Private-session protocol tests. Run with dbus-run-session and STROP_TEST_DBUS=1."""

import os
import subprocess
import sys
import time
from unittest.mock import Mock

import pytest
from gi.repository import Gio, GLib

from strop_core.hud import HUDClient, hud_application_id
from strop_core.tray import TrayService, MenuItem, WATCHER

pytestmark = pytest.mark.skipif(os.environ.get("STROP_TEST_DBUS") != "1",
                                reason="requires an isolated dbus-run-session")


def until(condition):
    deadline = time.monotonic() + 4
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if condition():
            return
        time.sleep(0.005)
    assert condition(), "D-Bus operation timed out"


def connection():
    return Gio.DBusConnection.new_for_address_sync(
        os.environ["DBUS_SESSION_BUS_ADDRESS"],
        Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
        None, None,
    )


def name_request(bus, method, name):
    params = GLib.Variant("(su)", (name, 0)) if method == "RequestName" else GLib.Variant("(s)", (name,))
    return bus.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                         method, params, None, Gio.DBusCallFlags.NONE, 2000, None)


def call(bus, dest, path, interface, method, params=None):
    results, errors = [], []

    def finished(connection, result):
        try:
            results.append(connection.call_finish(result))
        except GLib.Error as error:
            errors.append(error)

    bus.call(dest, path, interface, method, params, None, Gio.DBusCallFlags.NONE, 2000, None, finished)
    until(lambda: results or errors)
    if errors:
        raise errors[0]
    return results[0].unpack()


@pytest.fixture
def host():
    bus = connection()
    registrations = []
    xml = f"""<node><interface name="{WATCHER}">
    <method name="RegisterStatusNotifierItem"><arg type="s" direction="in"/></method>
    <property name="IsStatusNotifierHostRegistered" type="b" access="read"/>
    </interface></node>"""

    def register(connection, sender, path, interface, method, params, invocation):
        registrations.append((sender, params.unpack()[0]))
        invocation.return_value(None)

    reg = bus.register_object("/StatusNotifierWatcher", Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0],
                              register, lambda *args: GLib.Variant("b", True), None)
    name_request(bus, "RequestName", WATCHER)
    yield bus, registrations
    name_request(bus, "ReleaseName", WATCHER)
    bus.unregister_object(reg)
    bus.close_sync(None)


def test_tray_exports_menu_actions_and_recovers_host(host):
    bus, registrations = host
    service_bus, peer = connection(), connection()
    activated, refreshed, available, clicked = Mock(), Mock(), [], Mock()
    tray = TrayService(service_bus, activated, refreshed, available.append)
    try:
        tray.update([MenuItem("device", "Keypad", children=[MenuItem("profile", "Game", clicked)])])
        until(lambda: tray.available)
        assert registrations == [(service_bus.get_unique_name(), "/StatusNotifierItem")]
        dest = service_bus.get_unique_name()
        properties = call(peer, dest, "/StatusNotifierItem", "org.freedesktop.DBus.Properties",
                          "GetAll", GLib.Variant("(s)", ("org.kde.StatusNotifierItem",)))[0]
        assert properties["Menu"] == "/Menu"
        assert properties["IconPixmap"][0][:2] == (32, 32)
        revision, layout = call(peer, dest, "/Menu", "com.canonical.dbusmenu", "GetLayout",
                                GLib.Variant("(iias)", (0, -1, [])))
        assert revision == 1
        assert layout[2][0][1]["label"] == "Keypad"
        profile_id = tray.menu.ids["profile"]
        call(peer, dest, "/Menu", "com.canonical.dbusmenu", "Event",
             GLib.Variant("(isvu)", (profile_id, "clicked", GLib.Variant("s", ""), 0)))
        clicked.assert_called_once()
        call(peer, dest, "/Menu", "com.canonical.dbusmenu", "AboutToShow", GLib.Variant("(i)", (0,)))
        refreshed.assert_called_once()
        call(peer, dest, "/StatusNotifierItem", "org.kde.StatusNotifierItem", "Activate",
             GLib.Variant("(ii)", (0, 0)))
        activated.assert_called_once()
        tray.update([])
        errors = call(peer, dest, "/Menu", "com.canonical.dbusmenu", "EventGroup",
                      GLib.Variant("(a(isvu))", ([(profile_id, "clicked", GLib.Variant("s", ""), 0)],)))
        assert errors == ([profile_id],)
        name_request(bus, "ReleaseName", WATCHER)
        until(lambda: not tray.available)
        name_request(bus, "RequestName", WATCHER)
        until(lambda: tray.available)
        assert available == [True, False, True]
        assert len(registrations) == 2
    finally:
        tray.close()
        peer.close_sync(None)
        service_bus.close_sync(None)


def test_hud_visibility_refresh_and_owned_quit_actions():
    bus = connection()
    name = hud_application_id("Razer Tartarus Pro")
    path = "/" + name.replace(".", "/")
    actions = Gio.SimpleActionGroup()
    visible = Gio.SimpleAction.new_stateful("visible", None, GLib.Variant("b", True))
    actions.add_action(visible)
    calls = []
    for action_name in ("show", "hide", "refresh", "quit"):
        action = Gio.SimpleAction.new(action_name, None)

        def activate(action, parameter):
            calls.append(action.get_name())
            if action.get_name() in ("show", "hide"):
                visible.set_state(GLib.Variant("b", action.get_name() == "show"))

        action.connect("activate", activate)
        actions.add_action(action)
    export = bus.export_action_group(path, actions)
    name_request(bus, "RequestName", name)
    client = HUDClient("Razer Tartarus Pro", Mock())
    try:
        until(lambda: client.visible)
        client.toggle()
        until(lambda: not client.visible)
        assert calls == ["hide"]
        client.refresh()
        until(lambda: "refresh" in calls)
        client.owned = True
        client.close()
        until(lambda: "quit" in calls)
    finally:
        name_request(bus, "ReleaseName", name)
        bus.unexport_action_group(export)
        bus.close_sync(None)


@pytest.mark.parametrize("attempt", range(3))
def test_owned_hud_receives_quit_when_client_exits_immediately(attempt):
    """Exercise shutdown without a sender main loop left to deliver queued calls."""
    bus = connection()
    name = hud_application_id(f"Razer Tartarus Pro shutdown {attempt}")
    path = "/" + name.replace(".", "/")
    actions = Gio.SimpleActionGroup()
    received = []
    quit_action = Gio.SimpleAction.new("quit", None)
    quit_action.connect("activate", lambda *args: received.append("quit"))
    actions.add_action(quit_action)
    export = bus.export_action_group(path, actions)
    name_request(bus, "RequestName", name)
    script = """
import os, sys, time
from gi.repository import GLib
from strop_core.hud import HUDClient
client = HUDClient(sys.argv[1], lambda: None)
context = GLib.MainContext.default()
deadline = time.monotonic() + 4
while not (client.group and client.group.has_action('quit')):
    while context.pending():
        context.iteration(False)
    if time.monotonic() > deadline:
        os._exit(2)
    time.sleep(0.005)
client.owned = True
client.close()
os._exit(0)
"""
    sender = None
    try:
        sender = subprocess.Popen([sys.executable, "-c", script,
                                   f"Razer Tartarus Pro shutdown {attempt}"])
        until(lambda: sender.poll() is not None)
        assert sender.returncode == 0
        until(lambda: received == ["quit"])
    finally:
        if sender is not None and sender.poll() is None:
            sender.terminate()
            sender.wait(timeout=2)
        name_request(bus, "ReleaseName", name)
        bus.unexport_action_group(export)
        bus.close_sync(None)
