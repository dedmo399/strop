"""HUD regressions without requiring a desktop or real hardware."""

import json
from types import MethodType, SimpleNamespace
from unittest.mock import patch

from strop_core.hud import binding_label, hud_application_id
from strop_core.layouts.keypad import KEYPAD_GRID
from strop_hud import KeypadHUDOverlay


class Widget:
    def __init__(self):
        self.text = ""
        self.classes = set()
        self.sensitive = True
        self.selected = 0

    def set_text(self, text):
        self.text = text

    set_markup = set_text

    def add_css_class(self, name):
        self.classes.add(name)

    def remove_css_class(self, name):
        self.classes.discard(name)

    def set_sensitive(self, value):
        self.sensitive = value

    def set_model(self, model):
        self.model = model

    def set_selected(self, index):
        self.selected = index

    def get_selected(self):
        return self.selected

    def handler_block(self, handler):
        pass

    handler_unblock = handler_block


def overlay():
    hud = SimpleNamespace(
        state={}, button_widgets={}, detected_device={"name": "Razer Tartarus Pro"},
        lbl_profile_status=Widget(), preset_dropdown=Widget(), btn_profile_apply=Widget(),
        btn_profile_stop=Widget(), available_presets=[], current_preset_name="", preset_error="",
        profile_operation_pending=False, preset_dropdown_handler_id=1,
    )
    for name in ("_init_state", "_reset_bindings", "_update_all_visuals", "_load_preset_file",
                 "_match_preset_key", "_scan_and_load_presets", "_on_profile_state_checked",
                 "_on_preset_selected"):
        setattr(hud, name, MethodType(getattr(KeypadHUDOverlay, name), hud))
    hud._init_state()
    for key, state in hud.state.items():
        hud.button_widgets[key] = {"box": Widget(), "lbl": Widget(), "raw_label": state["label"]}
    return hud


def write_preset(path, output="k", custom=None):
    entries = [] if output is None else [{
        "input_combination": [{"type": 1, "code": 16}], "target_uinput": "keyboard",
        "output_symbol": output, "custom_name": custom,
    }]
    path.write_text(json.dumps(entries))


def test_default_label_precedence_and_formats():
    state = {"default_label": "Q", "output": "", "custom_name": " "}
    assert binding_label(state) == ("Q", False)
    state["output"] = "disable"
    assert binding_label(state) == ("off", True)
    state["custom_name"] = "Ability"
    assert binding_label(state) == ("Ability", True)
    state["custom_name"] = ""
    state["output"] = "k(a).w(20)"
    assert binding_label(state) == ("macro", True)
    state["output"] = "gamepad(BTN_SOUTH)"
    assert binding_label(state) == ("(A)", True)


def test_factory_defaults_and_neutral_rendering():
    hud = overlay()
    hud._update_all_visuals()
    assert [key["default_label"] for key in KEYPAD_GRID[1]] == ["Tab", "Q", "W", "E", "R"]
    assert hud.state["spacebar"]["default_label"] == "Space"
    assert hud.state["thumb"]["default_label"] == "Alt"
    for key, widgets in hud.button_widgets.items():
        assert "assigned" not in widgets["box"].classes
        assert hud.state[key]["default_label"] in widgets["lbl"].text
    assert hud.button_widgets["dpad-n"]["lbl"].text.count("↑") == 1


def test_partial_empty_failed_and_missing_presets_clear_stale_labels(tmp_path):
    hud = overlay()
    path = tmp_path / "profile.json"
    write_preset(path, custom="<Ability & boost>")
    hud._load_preset_file(path)
    key = hud.button_widgets["grid-1-1"]
    assert "&lt;Ability &amp; boost&gt;" in key["lbl"].text
    assert "assigned" in key["box"].classes
    assert "Tab" in hud.button_widgets["grid-1-0"]["lbl"].text
    write_preset(path, output=None)
    hud._load_preset_file(path)
    assert "assigned" not in key["box"].classes
    assert ">Q</span>" in key["lbl"].text
    write_preset(path)
    hud._load_preset_file(path)
    path.write_text("invalid json")
    hud._load_preset_file(path)
    assert hud.preset_error
    assert hud.state["grid-1-1"]["output"] == ""
    with patch("strop_hud.get_device_presets_dir", return_value=tmp_path):
        hud._load_preset_file("removed")
    assert "removed.json" in hud.preset_error


def test_empty_scan_resets_profile_and_keeps_stop_available():
    hud = overlay()
    hud.state["grid-1-1"]["output"] = "k"
    hud.current_preset_name = "old"
    with patch("strop_hud.check_profile_state_async"), patch("strop_hud.list_device_presets", return_value=[]):
        hud._scan_and_load_presets()
    assert hud.current_preset_name == ""
    assert hud.state["grid-1-1"]["output"] == ""
    assert not hud.btn_profile_apply.sensitive
    assert hud.btn_profile_stop.sensitive


def test_backend_check_does_not_hide_load_error():
    hud = overlay()
    hud.preset_error = "Could not read preset: broken.json"
    with patch("strop_hud.get_active_profile", return_value="broken"):
        hud._on_profile_state_checked("Razer Tartarus Pro", "stopped")
    assert hud.preset_error in hud.lbl_profile_status.text


def test_device_ids_are_stable_distinct_and_normalized():
    assert hud_application_id("Razer Tartarus Pro") == hud_application_id("Razer Razer Tartarus Pro")
    assert hud_application_id("Razer Tartarus Pro") != hud_application_id("Razer Orbweaver")
