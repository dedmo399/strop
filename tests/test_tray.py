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
