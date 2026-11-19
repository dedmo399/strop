"""Tray model, refresh, operations, and application lifecycle regressions."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from strop_core.presets import ProfileOperationResult
from strop_core.tray import MenuItem, MenuModel, icon_pixmaps
from strop_core.tray_controller import TrayController
from strop_core.hud import HUDClient
from strop import StropApplication, StropHubWindow


def controller():
    control = TrayController.__new__(TrayController)
    control.app = Mock()
    control.devices = [{"name": "Razer Tartarus Pro", "archetype": "KEYPAD_TARTARUS"}]
    control.presets = {"Razer Tartarus Pro": ["game"]}
    control.states = {"Razer Tartarus Pro": "running"}
    control.last_profiles = {"Razer Tartarus Pro": "game"}
    control.results = {}
    control.diagnostics = []
    control.daemon_status = ("running", "Ready")
    control.busy = set()
    control.huds = {"Razer Tartarus Pro": Mock(visible=False)}
    control.closed = control.refreshing = control.refresh_pending = False
    control.generation = 0
    control.tray = Mock()
    control.timer = 0
    return control


def test_stable_menu_ids_and_stale_events():
    model = MenuModel()
    clicked = Mock()
    model.replace([MenuItem("device", "Keypad", children=[MenuItem("preset", "Game", clicked)])])
    old_id = model.ids["preset"]
    assert model.activate(old_id, "clicked")
    clicked.assert_called_once()
    model.replace([MenuItem("different", "Work", clicked)])
    assert model.ids["different"] != old_id
    assert not model.activate(old_id, "clicked")
    model.replace([MenuItem("preset", "Game", clicked, enabled=False)])
    assert model.ids["preset"] == old_id
    model.activate(old_id, "clicked")
    clicked.assert_called_once()
    assert model.layout(depth=0)[2] == []
    assert set(model.properties(old_id, ["label"])) == {"label"}


def test_icon_is_argb_and_has_expected_dimensions():
    width, height, pixels = icon_pixmaps()[0]
    assert (width, height) == (32, 32)
    assert len(pixels) == width * height * 4


def test_per_device_menu_and_profile_failure_busy_state():
    control = controller()
    with patch("strop_core.tray_controller.run_profile_operation_async") as operation, patch.object(control, "refresh"):
        assert control.operate("apply", "Razer Tartarus Pro", "game")
        assert not control.operate("stop", "Razer Tartarus Pro")
        children = next(item.children for item in control.menu_items() if item.key == "device:Razer Tartarus Pro")
        apply = next(item for item in children if item.label == "Apply Profile")
        assert not apply.children[0].enabled
        assert not next(item for item in children if item.label == "Stop Remapping").enabled
        callback = operation.call_args.args[2]
        callback(ProfileOperationResult("failed", "Device disconnected"))
    assert not control.busy
    assert control.results["Razer Tartarus Pro"] == "Device disconnected"
    control.huds["Razer Tartarus Pro"].refresh.assert_not_called()
    control.app.send_notification.assert_called_once()


def test_success_refreshes_hud_and_disconnected_device_cannot_apply():
    control = controller()
    with patch("strop_core.tray_controller.run_profile_operation_async") as operation, patch.object(control, "refresh"):
        control.operate("apply", "Razer Tartarus Pro", "game")
        operation.call_args.args[2](ProfileOperationResult("applied", "Applied"))
    control.huds["Razer Tartarus Pro"].refresh.assert_called_once()
    control.devices = []
    assert not control.operate("apply", "Razer Tartarus Pro", "game")
    assert any(item.label == "No connected devices" for item in control.menu_items())


def test_stale_refresh_is_discarded_and_refreshes_are_coalesced():
    control = controller()
    control.refreshing = True
    assert control.refresh()
    assert control.refresh_pending
    control.generation = 2
    with patch.object(control, "refresh") as refresh:
        control._refreshed(1, ([], {}, {}, {}, [], ("running", "Ready")))
    assert control.devices
    refresh.assert_called_once()
    assert not control.refresh_pending


def test_quit_closes_managed_huds_without_stopping_profiles():
    control = controller()
    with patch("strop_core.tray_controller.run_profile_operation_async") as operation:
        control.close()
    operation.assert_not_called()
    control.tray.close.assert_called_once()
    control.huds["Razer Tartarus Pro"].close.assert_called_once()


def test_hud_ownership_is_cleared_after_exit():
    client = HUDClient.__new__(HUDClient)
    client.running = client.visible = client.owned = True
    client.group = Mock()
    client.process = Mock()
    client.changed = Mock()
    client._vanished(None, "test")
    assert not client.owned and not client.running
    assert client.process is None


def test_hub_close_hides_with_tray_and_quits_without_it():
    app = SimpleNamespace(controller=SimpleNamespace(available=True), quit=Mock())
    window = SimpleNamespace(get_application=lambda: app, set_visible=Mock())
    assert StropHubWindow._on_close_requested(window, window)
    window.set_visible.assert_called_once_with(False)
    app.quit.assert_not_called()
    app.controller.available = False
    StropHubWindow._on_close_requested(window, window)
    app.quit.assert_called_once()


def test_activation_reuses_hub_and_lost_tray_restores_window():
    window = Mock()
    app = SimpleNamespace(window=None, activate=Mock())
    with patch("strop.StropHubWindow", return_value=window) as create:
        StropApplication._activate(app, app)
        StropApplication._activate(app, app)
    create.assert_called_once()
    assert window.present.call_count == 2
    StropApplication.tray_availability_changed(app, False)
    app.activate.assert_called_once()
    window.set_tray_available.assert_called_once_with(False)


def test_menu_model_property_update_and_layout_stability():
    model = MenuModel()
    layout_changed, props = model.replace([
        MenuItem("daemon", "Remapping daemon: checking", enabled=False),
        MenuItem("dev", "Mouse", children=[MenuItem("sub", "Sub")])
    ])
    assert layout_changed
    assert model.revision == 1
    assert props == []

    # Update only a property (label) on an existing item:
    layout_changed, props = model.replace([
        MenuItem("daemon", "Remapping daemon: running", enabled=False),
        MenuItem("dev", "Mouse", children=[MenuItem("sub", "Sub")])
    ])
    assert not layout_changed
    assert model.revision == 1
    daemon_id = model.ids["daemon"]
    assert any(item_id == daemon_id and changed.get("label").unpack() == "Remapping daemon: running"
               for item_id, changed in props)

    # Reorder or add a child to change layout:
    layout_changed, props = model.replace([
        MenuItem("daemon", "Remapping daemon: running", enabled=False),
        MenuItem("dev", "Mouse", children=[MenuItem("sub", "Sub"), MenuItem("sub2", "Sub2")])
    ])
    assert layout_changed
    assert model.revision == 2


def test_tray_controller_initializes_daemon_status_and_avoids_stuck_checking():
    app = Mock()
    app.get_dbus_connection.return_value = None
    with patch("strop_core.tray_controller.check_daemon_status", return_value=("running", "Ready")), \
         patch("strop_core.tray_controller.GLib.timeout_add_seconds", return_value=1), \
         patch.object(TrayController, "refresh"):
        ctrl = TrayController(app)
        assert ctrl.daemon_status == ("running", "Ready")
        items = {item.key: item for item in ctrl.menu_items()}
        assert items["daemon"].label == "Remapping daemon: running"


def test_tray_submenu_opened_does_not_block_layout_updates():
    from strop_core.tray import TrayService

    tray = TrayService.__new__(TrayService)
    tray.closed = False
    tray.menu = MenuModel()
    tray.menu_open = False
    tray.pending_layout_update = False
    tray.connection = Mock()

    tray.update([MenuItem("device_sub", "Device", children=[MenuItem("child", "Child")])])
    tray.connection.emit_signal.reset_mock()

    # Non-zero submenu 'opened' events must not suppress subsequent LayoutUpdated signals
    submenu_id = tray.menu.ids["device_sub"]
    assert submenu_id != 0
    tray._handle_event(submenu_id, "opened")
    assert not tray.menu_open

    tray.update([MenuItem("device_sub", "Device", children=[MenuItem("child2", "Child 2")])])
    emitted_signals = [call.args[3] for call in tray.connection.emit_signal.call_args_list]
    assert "LayoutUpdated" in emitted_signals

    # Root menu open (id == 0) still defers LayoutUpdated until closed
    tray.connection.emit_signal.reset_mock()
    tray._handle_event(0, "opened")
    assert tray.menu_open
    tray.update([MenuItem("device_sub", "Device", children=[MenuItem("child3", "Child 3")])])
    assert tray.pending_layout_update
    assert "LayoutUpdated" not in [call.args[3] for call in tray.connection.emit_signal.call_args_list]

    tray._handle_event(0, "closed")
    assert not tray.menu_open
    assert not tray.pending_layout_update
    assert "LayoutUpdated" in [call.args[3] for call in tray.connection.emit_signal.call_args_list]


def test_tray_dbusmenu_group_methods_for_kde():
    from gi.repository import GLib
    from strop_core.tray import TrayService

    clicked = Mock()
    tray = TrayService.__new__(TrayService)
    tray.closed = False
    tray.menu = MenuModel()
    tray.menu_open = False
    tray.pending_layout_update = False
    tray.refresh = Mock()
    tray.connection = Mock()
    tray.update([MenuItem("act", "Run Action", clicked)])
    act_id = tray.menu.ids["act"]

    inv_about = Mock()
    tray._menu_method(None, None, "/Menu", "com.canonical.dbusmenu", "AboutToShowGroup",
                      GLib.Variant("(ai)", ([0, 999],)), inv_about)
    tray.refresh.assert_called_once()
    updates, errors = inv_about.return_value.call_args.args[0].unpack()
    assert updates == []
    assert errors == [999]

    inv_event = Mock()
    tray._menu_method(None, None, "/Menu", "com.canonical.dbusmenu", "EventGroup",
                      GLib.Variant("(a(isvu))", ([(act_id, "clicked", GLib.Variant("s", ""), 0),
                                                   (999, "clicked", GLib.Variant("s", ""), 0)],)),
                      inv_event)
    clicked.assert_called_once()
    assert inv_event.return_value.call_args.args[0].unpack() == ([999],)
