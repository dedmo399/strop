"""GTK4-compatible StatusNotifierItem and DBusMenu, using Gio only."""

from dataclasses import dataclass, field
from pathlib import Path
import logging

import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gio, GLib, GdkPixbuf

LOG = logging.getLogger(__name__)
WATCHER = "org.kde.StatusNotifierWatcher"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/Menu"

# Wire definitions kept here so installation needs no external interface files.
ITEM_XML = """<node><interface name="org.kde.StatusNotifierItem">
<property name="Category" type="s" access="read"/>
<property name="Id" type="s" access="read"/>
<property name="Title" type="s" access="read"/>
<property name="Status" type="s" access="read"/>
<property name="WindowId" type="i" access="read"/>
<property name="IconName" type="s" access="read"/>
<property name="IconThemePath" type="s" access="read"/>
<property name="IconPixmap" type="a(iiay)" access="read"/>
<property name="OverlayIconName" type="s" access="read"/>
<property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
<property name="AttentionIconName" type="s" access="read"/>
<property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
<property name="AttentionMovieName" type="s" access="read"/>
<property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
<property name="Menu" type="o" access="read"/>
<property name="ItemIsMenu" type="b" access="read"/>
<method name="Activate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="SecondaryActivate"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="ContextMenu"><arg type="i" direction="in"/><arg type="i" direction="in"/></method>
<method name="Scroll"><arg type="i" direction="in"/><arg type="s" direction="in"/></method>
<signal name="NewIcon"/><signal name="NewTitle"/>
<signal name="NewStatus"><arg type="s"/></signal>
</interface></node>"""

MENU_XML = """<node><interface name="com.canonical.dbusmenu">
<property name="Version" type="u" access="read"/>
<property name="TextDirection" type="s" access="read"/>
<property name="Status" type="s" access="read"/>
<property name="IconThemePath" type="as" access="read"/>
<method name="GetLayout"><arg type="i" direction="in"/><arg type="i" direction="in"/>
<arg type="as" direction="in"/><arg type="u" direction="out"/><arg type="(ia{sv}av)" direction="out"/></method>
<method name="GetGroupProperties"><arg type="ai" direction="in"/><arg type="as" direction="in"/>
<arg type="a(ia{sv})" direction="out"/></method>
<method name="GetProperty"><arg type="i" direction="in"/><arg type="s" direction="in"/><arg type="v" direction="out"/></method>
<method name="Event"><arg type="i" direction="in"/><arg type="s" direction="in"/>
<arg type="v" direction="in"/><arg type="u" direction="in"/></method>
<method name="EventGroup"><arg type="a(isvu)" direction="in"/><arg type="ai" direction="out"/></method>
<method name="AboutToShow"><arg type="i" direction="in"/><arg type="b" direction="out"/></method>
<method name="AboutToShowGroup"><arg type="ai" direction="in"/>
<arg type="ai" direction="out"/><arg type="ai" direction="out"/></method>
<signal name="LayoutUpdated"><arg type="u"/><arg type="i"/></signal>
<signal name="ItemsPropertiesUpdated"><arg type="a(ia{sv})"/><arg type="a(ias)"/></signal>
</interface></node>"""


@dataclass
class MenuItem:
    key: str
    label: str = ""
    callback: object = None
    enabled: bool = True
    children: list = field(default_factory=list)


class MenuModel:
    """Stable IDs prevent an event for an old row activating a different row."""

    def __init__(self):
        self.ids = {"root": 0}
        self.items = {0: MenuItem("root")}
        self.revision = 0

    def replace(self, children):
        items = {}

        def visit(item):
            if item.key not in self.ids:
                self.ids[item.key] = len(self.ids)
            items[self.ids[item.key]] = item
            for child in item.children:
                visit(child)

        visit(MenuItem("root", children=children))
        self.items = items
        self.revision += 1

    def properties(self, item_id, names=()):
        item = self.items[item_id]
        props = {"label": GLib.Variant("s", item.label),
                 "enabled": GLib.Variant("b", item.enabled),
                 "visible": GLib.Variant("b", True)}
        if item.children or item_id == 0:
            props["children-display"] = GLib.Variant("s", "submenu")
        return {key: value for key, value in props.items() if not names or key in names}

    def layout(self, item_id=0, depth=-1, names=()):
        item = self.items[item_id]
        children = []
        if depth != 0:
            children = [GLib.Variant("(ia{sv}av)", self.layout(self.ids[child.key], depth - 1, names))
                        for child in item.children]
        return item_id, self.properties(item_id, names), children

    def activate(self, item_id, event):
        item = self.items.get(item_id)
        if item is None:
            return False
        if event == "clicked" and item.enabled and item.callback:
            item.callback()
        return True


def icon_pixmaps():
    path = Path(__file__).resolve().parent.parent / "assets/icons/strop_32x32.png"
    try:
        image = GdkPixbuf.Pixbuf.new_from_file(str(path))
        pixels = image.get_pixels()
        channels, stride = image.get_n_channels(), image.get_rowstride()
        data = bytearray()
        for y in range(image.get_height()):
            for x in range(image.get_width()):
                pos = y * stride + x * channels
                r, g, b = pixels[pos:pos + 3]
                data.extend((pixels[pos + 3] if channels == 4 else 255, r, g, b))
        return [(image.get_width(), image.get_height(), bytes(data))]
    except Exception:
        LOG.exception("Could not load tray icon")
        return []


class TrayService:
    def __init__(self, connection, activate, refresh, availability):
        self.connection = connection
        self.activate = activate
        self.refresh = refresh
        self.availability = availability
        self.available = False
        self.closed = False
        self.epoch = 0
        self.menu = MenuModel()
        self.pixmaps = icon_pixmaps()
        self.registrations = []
        for path, xml, method, prop in ((ITEM_PATH, ITEM_XML, self._item_method, self._item_property),
                                       (MENU_PATH, MENU_XML, self._menu_method, self._menu_property)):
            info = Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]
            self.registrations.append(connection.register_object(path, info, method, prop, None))
        self.subscription = connection.signal_subscribe(
            WATCHER, "org.freedesktop.DBus.Properties", "PropertiesChanged",
            "/StatusNotifierWatcher", WATCHER, Gio.DBusSignalFlags.NONE, self._host_changed,
        )
        self.watch = Gio.bus_watch_name_on_connection(
            connection, WATCHER, Gio.BusNameWatcherFlags.NONE, self._appeared, self._vanished,
        )

    def _set_available(self, value):
        if value != self.available:
            self.available = value
            self.availability(value)

    def _appeared(self, connection, name, owner):
        self.epoch += 1
        epoch = self.epoch
        connection.call(WATCHER, "/StatusNotifierWatcher", WATCHER,
                        "RegisterStatusNotifierItem", GLib.Variant("(s)", (ITEM_PATH,)),
                        None, Gio.DBusCallFlags.NONE, 3000, None, self._registered, epoch)

    def _registered(self, connection, result, epoch):
        if self.closed or epoch != self.epoch:
            return
        try:
            connection.call_finish(result)
            connection.call(WATCHER, "/StatusNotifierWatcher", "org.freedesktop.DBus.Properties",
                            "Get", GLib.Variant("(ss)", (WATCHER, "IsStatusNotifierHostRegistered")),
                            None, Gio.DBusCallFlags.NONE, 3000, None, self._host_checked, epoch)
        except GLib.Error:
            LOG.exception("Tray registration failed")
            self._set_available(False)

    def _host_checked(self, connection, result, epoch):
        if self.closed or epoch != self.epoch:
            return
        try:
            self._set_available(bool(connection.call_finish(result).unpack()[0]))
        except GLib.Error:
            LOG.exception("Tray host query failed")
            self._set_available(False)

    def _host_changed(self, connection, sender, path, interface, signal, params):
        changed = params.unpack()[1]
        if "IsStatusNotifierHostRegistered" in changed:
            self._set_available(bool(changed["IsStatusNotifierHostRegistered"]))

    def _vanished(self, connection, name):
        self.epoch += 1
        self._set_available(False)

    def update(self, items):
        if self.closed:
            return
        self.menu.replace(items)
        self.connection.emit_signal(None, MENU_PATH, "com.canonical.dbusmenu", "LayoutUpdated",
                                    GLib.Variant("(ui)", (self.menu.revision, 0)))

    def _item_property(self, connection, sender, path, interface, name):
        strings = {"Category": "ApplicationStatus", "Id": "strop", "Title": "Strop",
                   "Status": "Active", "IconName": "strop", "IconThemePath": "",
                   "OverlayIconName": "", "AttentionIconName": "", "AttentionMovieName": ""}
        if name in strings:
            return GLib.Variant("s", strings[name])
        if name.endswith("Pixmap"):
            return GLib.Variant("a(iiay)", self.pixmaps if name == "IconPixmap" else [])
        if name == "Menu":
            return GLib.Variant("o", MENU_PATH)
        if name == "ItemIsMenu":
            return GLib.Variant("b", True)
        if name == "WindowId":
            return GLib.Variant("i", 0)
        if name == "ToolTip":
            return GLib.Variant("(sa(iiay)ss)", ("strop", [], "Strop", "Peripheral studio and HUD"))

    def _item_method(self, connection, sender, path, interface, method, params, invocation):
        if method in ("Activate", "SecondaryActivate"):
            self.activate()
        invocation.return_value(None)

    def _menu_property(self, connection, sender, path, interface, name):
        return {"Version": GLib.Variant("u", 3), "TextDirection": GLib.Variant("s", "ltr"),
                "Status": GLib.Variant("s", "normal"), "IconThemePath": GLib.Variant("as", [])}.get(name)

    def _menu_method(self, connection, sender, path, interface, method, params, invocation):
        args = params.unpack()
        try:
            if method == "GetLayout":
                result = GLib.Variant("(u(ia{sv}av))", (self.menu.revision, self.menu.layout(*args)))
            elif method == "GetGroupProperties":
                ids, names = args
                result = GLib.Variant("(a(ia{sv}))", ([(i, self.menu.properties(i, names))
                                                     for i in ids if i in self.menu.items],))
            elif method == "GetProperty":
                props = self.menu.properties(args[0])
                result = GLib.Variant("(v)", (props[args[1]],))
            elif method == "Event":
                if not self.menu.activate(args[0], args[1]):
                    raise KeyError(args[0])
                result = None
            elif method == "EventGroup":
                errors = [event[0] for event in args[0] if not self.menu.activate(event[0], event[1])]
                result = GLib.Variant("(ai)", (errors,))
            elif method == "AboutToShow":
                if args[0] not in self.menu.items:
                    raise KeyError(args[0])
                self.refresh()
                result = GLib.Variant("(b)", (False,))
            elif method == "AboutToShowGroup":
                self.refresh()
                result = GLib.Variant("(aiai)", ([], [i for i in args[0] if i not in self.menu.items]))
            else:
                invocation.return_dbus_error("com.canonical.dbusmenu.Error.UnknownMethod", method)
                return
            invocation.return_value(result)
        except (KeyError, ValueError) as error:
            invocation.return_dbus_error("com.canonical.dbusmenu.Error.InvalidItem", str(error))
        except Exception:
            LOG.exception("Tray menu action failed")
            invocation.return_dbus_error("com.canonical.dbusmenu.Error.Failed", "Menu action failed")

    def close(self):
        self.closed = True
        self.epoch += 1
        Gio.bus_unwatch_name(self.watch)
        self.connection.signal_unsubscribe(self.subscription)
        for registration in self.registrations:
            self.connection.unregister_object(registration)
