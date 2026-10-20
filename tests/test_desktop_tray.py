"""Opt-in check against the desktop's actual tray host; no hardware actions."""

import os
from unittest.mock import Mock

import pytest
from gi.repository import GLib

from strop_core.tray import TrayService, MenuItem, WATCHER

pytestmark = pytest.mark.skipif(os.environ.get("STROP_TEST_DESKTOP") != "1",
                                reason="requires the desktop's real StatusNotifier host")


def test_desktop_host_accepts_and_removes_tray_item():
    from test_tray_dbus import connection, call, until
    service_bus, peer = connection(), connection()
    tray = TrayService(service_bus, Mock(), Mock(), Mock())
    # Ubuntu's watcher separates the bus name and object path with '@'.
    identifier = service_bus.get_unique_name() + "@/StatusNotifierItem"

    def registered_items():
        return call(peer, WATCHER, "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties",
                    "Get", GLib.Variant("(ss)", (WATCHER, "RegisteredStatusNotifierItems")))[0]

    try:
        tray.update([MenuItem("hub", "Open Hub", Mock()), MenuItem("quit", "Quit Strop", Mock())])
        until(lambda: tray.available)
        until(lambda: identifier in registered_items())
    finally:
        tray.close()
        service_bus.close_sync(None)
    until(lambda: identifier not in registered_items())
    peer.close_sync(None)
