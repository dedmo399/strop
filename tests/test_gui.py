"""Opt-in real GTK smoke check on a private bus with mocked hardware/backend."""

import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("STROP_TEST_GUI") != "1",
                                reason="requires a desktop display and private D-Bus session")


def test_real_hub_and_hud_lifecycle(tmp_path):
    from test_tray_dbus import until
    from strop import StropApplication
    from strop_hud import HUDApplication
    from strop_core.hud import HUDClient

    with patch("strop_core.tray_controller.scan_all_connected_devices", return_value=[]), \
         patch("strop_core.tray_controller.check_daemon_status", return_value=("running", "Ready")), \
         patch("strop.get_active_profile", return_value=None), \
         patch("strop_hud.detect_device", return_value={"name": "Razer Tartarus Pro"}), \
         patch("strop_hud.list_device_presets", return_value=[]), \
         patch("strop_hud.get_active_profile", return_value=None), \
         patch("strop_hud.check_profile_state_async"), \
         patch("strop_hud.pin_window_on_top"):
        hub = StropApplication()
        assert hub.register(None)
        hub.activate()
        until(lambda: hub.window.get_mapped())
        first_window = hub.window
        hub.activate()
        assert hub.window is first_window
        # Exercise real selectors as asynchronous discovery arrives and disappears.
        control = hub.controller
        control.devices = [{"name": "Razer Tartarus Pro", "archetype": "KEYPAD_TARTARUS", "hash": "test"}]
        control.presets = {"Razer Tartarus Pro": ["game"]}
        control.states = {"Razer Tartarus Pro": "stopped"}
        control._rebuild()
        assert first_window.selected_dev_name == "Razer Tartarus Pro"
        assert first_window.btn_profile_apply.get_sensitive()
        control.devices = []
        control._rebuild()
        assert not first_window.btn_profile_apply.get_sensitive()
        assert not first_window.btn_profile_stop.get_sensitive()

        hud = HUDApplication("Razer Tartarus Pro")
        assert hud.register(None)
        hud.activate()
        until(lambda: hud.window.get_mapped())
        for key, expected in (("grid-1-0", "Tab"), ("grid-1-1", "Q"), ("spacebar", "Space"), ("thumb", "Alt")):
            assert expected in hud.window.button_widgets[key]["lbl"].get_text()
        hud.window._cycle_opacity(None)
        hud.window._toggle_collapse(None)
        opacity, collapsed = hud.window.get_opacity(), hud.window.is_collapsed
        client = HUDClient("Razer Tartarus Pro", lambda: None)
        until(lambda: client.visible)
        client.toggle()
        until(lambda: not client.visible)
        hud.activate_action("show", None)
        until(lambda: client.visible)
        assert hud.window.get_opacity() == opacity
        assert hud.window.is_collapsed == collapsed
        assert hud.visible_action.get_state().unpack()
        hud.window.state["grid-1-1"]["output"] = "k"
        client.refresh()
        until(lambda: hud.window.state["grid-1-1"]["output"] == "")
        client.close()
        hud.window.destroy()
        hud.release()
        hud.quit()
        hub.controller.close()
        hub.window.destroy()
        hub.release()
        hub.quit()
