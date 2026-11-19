"""Opt-in real GTK smoke check on a private bus with mocked hardware/backend."""

import os
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("STROP_TEST_GUI") != "1",
                                reason="requires a desktop display and private D-Bus session")


def test_real_hub_and_hud_lifecycle(tmp_path):
    from test_tray_dbus import until
    from gi.repository import Gtk
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
        # Header uses Gtk.WindowHandle (no capturing GestureDrag on the header box)
        assert isinstance(hud.window.main_container.get_first_child(), Gtk.WindowHandle)
        assert not hasattr(hud.window, "drag_gesture")
        hud.window.btn_opacity.emit("clicked")
        hud.window.btn_collapse.emit("clicked")
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


def test_real_studio_windows_smoke_lifecycle(tmp_path):
    import gi
    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk
    from test_tray_dbus import until
    from strop_core.dpi import MouseSensorSettings
    from strop_keypad import KeypadMainWindow
    from strop_keyboard import KeyboardMainWindow
    from strop_mouse import RazerMouseStudioWindow
    from strop_macro import StropMacroStudioWindow
    from strop_lighting import LightingStudioWindow

    app = Gtk.Application(application_id="io.github.strop.GuiSmokeTest")
    assert app.register(None)

    mock_keypad_dev = {"name": "Razer Tartarus Pro", "raw_name": "Razer Tartarus Pro", "detected": False, "key_to_hash": {}, "rel_to_hash": {}, "scan_diagnostics": []}
    mock_kb_dev = {"name": "Razer BlackWidow V3", "raw_name": "Razer BlackWidow V3", "detected": False, "key_to_hash": {}, "rel_to_hash": {}, "scan_diagnostics": []}
    mock_mouse_dev = {"name": "Razer Naga Pro", "raw_name": "Razer Naga Pro", "detected": False, "key_to_hash": {}, "rel_to_hash": {}, "scan_diagnostics": []}

    def _has_hud_button(win):
        def walk(widget):
            if widget is None:
                return False
            if isinstance(widget, Gtk.Button) and widget.get_label() == "🖥 HUD Overlay":
                return True
            child = widget.get_first_child()
            while child is not None:
                if walk(child):
                    return True
                child = child.get_next_sibling()
            return False

        return walk(win.get_child()) or walk(win.get_titlebar())

    with patch("strop_keypad.detect_device", return_value=mock_keypad_dev), \
         patch("strop_keyboard.detect_device", return_value=mock_kb_dev), \
         patch("strop_mouse.detect_device", return_value=mock_mouse_dev), \
         patch("strop_mouse.scan_all_connected_devices", return_value=[]), \
         patch("strop_lighting.scan_all_connected_devices", return_value=[]), \
         patch("strop_core.studio_base.check_profile_state_async"), \
         patch("strop_core.studio_base.get_device_presets_dir", return_value=tmp_path), \
         patch("strop_core.studio_base.get_active_profile", return_value=None), \
         patch("strop_core.studio_base.load_all_macros", return_value=[]), \
         patch("strop_core.dpi.RazerDPIEngine._init_openrazer"), \
         patch("strop_core.lighting.RazerLightingEngine._init_openrazer"), \
         patch("strop_mouse.load_mouse_settings", return_value=MouseSensorSettings()), \
         patch("strop_mouse.save_mouse_settings", return_value=True), \
         patch("strop_lighting.load_lighting_settings", return_value=False), \
         patch("strop_lighting.save_lighting_settings", return_value=True), \
         patch("strop_macro.load_all_macros", return_value=[]):

        kp = KeypadMainWindow(app, device_override="Razer Tartarus Pro")
        kp.present()
        until(lambda: kp.get_mapped())
        assert _has_hud_button(kp)
        kp.destroy()

        kb = KeyboardMainWindow(app, device_override="Razer BlackWidow V3")
        kb.present()
        until(lambda: kb.get_mapped())
        assert not _has_hud_button(kb)
        kb.destroy()

        ms = RazerMouseStudioWindow(app, device_override="Razer Naga Pro")
        ms.present()
        until(lambda: ms.get_mapped())
        assert not _has_hud_button(ms)
        ms.destroy()

        mc = StropMacroStudioWindow(app)
        mc.present()
        until(lambda: mc.get_mapped())
        mc.destroy()

        lt = LightingStudioWindow(app, device_override="Razer BlackWidow V3")
        lt.present()
        until(lambda: lt.get_mapped())
        lt.destroy()

    app.release()
    app.quit()
