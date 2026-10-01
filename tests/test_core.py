#!/usr/bin/env python3
"""
Unit tests for Strop Core:
- Catalog device classification and archetype resolution
- Macro parsing, timing extraction, and normalization
- Preset serialization and input-remapper compatibility
- Device name normalization and origin_hash computation
"""

import unittest
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from strop_core.catalog import (
    RAZER_DEVICE_CATALOG,
    get_device_by_name,
    get_device_by_pid,
    get_archetype_for_device,
    list_devices_by_category,
    KEYPAD_TARTARUS,
    KEYBOARD_FULL,
    KEYBOARD_TKL,
    KEYBOARD_60,
    MOUSE_NAGA_MMO,
    MOUSE_NAGA_HEX,
    MOUSE_BASILISK_FPS,
)
from strop_core.macros import (
    MACRO_TEMPLATES,
    normalize_macro_to_input_remapper,
    build_macro_string,
    parse_dsl_sequence,
)
from strop_core.presets import (
    serialize_preset_data,
)
from strop_core.device import (
    clean_device_display_name,
    calculate_origin_hash,
    is_razer_device,
)


class TestStropCatalog(unittest.TestCase):
    def test_catalog_not_empty(self):
        self.assertGreater(len(RAZER_DEVICE_CATALOG), 200, "Catalog should have over 200 Razer devices")

    def test_all_catalog_entries_valid(self):
        required_keys = {"name", "class", "pid", "pid_int", "category", "archetype"}
        valid_categories = {"keypad", "keyboard", "mouse", "laptop", "accessory"}

        for d in RAZER_DEVICE_CATALOG:
            missing = required_keys - set(d.keys())
            self.assertEqual(missing, set(), f"Device {d.get('name')} missing fields: {missing}")
            self.assertIn(d["category"], valid_categories, f"Unknown category: {d['category']} in {d['name']}")
            self.assertTrue(isinstance(d["pid_int"], int), f"PID must be int in {d['name']}")
            self.assertGreater(d["pid_int"], 0)

    def test_lookup_helpers(self):
        dev = get_device_by_name("Razer Tartarus Pro")
        self.assertIsNotNone(dev)
        self.assertEqual(dev["archetype"], KEYPAD_TARTARUS)
        self.assertIsNone(get_device_by_name("Razer"))

        # A short family query should resolve to its most specific catalog item,
        # not whichever related model happens to appear first in the catalog.
        family_match = get_device_by_name("Basilisk")
        candidates = [
            d for d in RAZER_DEVICE_CATALOG
            if "basilisk" in "".join(c.lower() for c in d["name"] if c.isalnum())
        ]
        if candidates:
            expected_length = max(len("".join(c.lower() for c in d["name"] if c.isalnum())) for d in candidates)
            self.assertIsNotNone(family_match)
            self.assertEqual(len("".join(c.lower() for c in family_match["name"] if c.isalnum())), expected_length)

        # Lookup by PID
        dev_by_pid = get_device_by_pid(dev["pid_int"])
        self.assertIsNotNone(dev_by_pid)
        self.assertEqual(dev_by_pid["name"], dev["name"])

    def test_archetype_heuristics(self):
        self.assertEqual(get_archetype_for_device("Unknown Tartarus Custom"), KEYPAD_TARTARUS)
        self.assertEqual(get_archetype_for_device("Razer Naga Pro"), MOUSE_NAGA_MMO)
        self.assertEqual(get_archetype_for_device("Razer Naga Hex V2"), MOUSE_NAGA_HEX)
        self.assertEqual(get_archetype_for_device("Razer Basilisk V3"), MOUSE_BASILISK_FPS)

        self.assertEqual(get_archetype_for_device("Razer Huntsman Mini"), KEYBOARD_60)
        self.assertEqual(get_archetype_for_device("Razer BlackWidow V3 TKL"), KEYBOARD_TKL)
        self.assertEqual(get_archetype_for_device("Razer BlackWidow V4 Pro"), KEYBOARD_FULL)

    def test_list_devices_by_category(self):
        keypads = list_devices_by_category("keypad")
        self.assertGreater(len(keypads), 0)
        for k in keypads:
            self.assertEqual(k["category"], "keypad")


class TestStropMacros(unittest.TestCase):
    def test_macro_templates_structure(self):
        self.assertGreater(len(MACRO_TEMPLATES), 5)
        for tpl in MACRO_TEMPLATES:
            self.assertIn("title", tpl)
            self.assertIn("macro", tpl)
            self.assertIn("label", tpl)
            self.assertTrue(len(tpl["macro"]) > 0)

    def test_normalize_macro_timing_and_functions(self):
        # Plus with milliseconds
        raw = "key_down(Control_L) + 20ms + key_down(space) + 100ms + key_up(space) + key_up(Control_L)"
        norm = normalize_macro_to_input_remapper(raw)
        self.assertEqual(
            norm,
            "key_down(Control_L).wait(20).key_down(space).wait(100).key_up(space).key_up(Control_L)"
        )

    def test_normalize_single_symbols_unaltered(self):
        self.assertEqual(normalize_macro_to_input_remapper("4"), "4")
        self.assertEqual(normalize_macro_to_input_remapper("space"), "space")
        self.assertEqual(normalize_macro_to_input_remapper("disable"), "disable")

    def test_normalize_simple_combos_unaltered(self):
        self.assertEqual(normalize_macro_to_input_remapper("Control_L + c"), "Control_L + c")

    def test_parse_dsl_sequence(self):
        seq = "key_down(Control_L).wait(50).key(space).wait(100).key_up(Control_L)"
        tokens = parse_dsl_sequence(seq)
        self.assertEqual(tokens, ["key_down(Control_L)", "50ms", "space", "100ms", "key_up(Control_L)"])

    def test_build_macro_string(self):
        steps = ["key_down(Control_L)", "20ms", "key_down(space)", "100ms", "key_up(space)", "key_up(Control_L)"]
        built = build_macro_string(steps)
        self.assertEqual(
            built,
            "key_down(Control_L).wait(20).key_down(space).wait(100).key_up(space).key_up(Control_L)"
        )


class TestStropPresets(unittest.TestCase):
    def test_serialize_preset_data(self):
        state = {
            "fps_forward": {
                "code": 276,
                "output": "4",
                "name": "Forward",
                "target": "keyboard"
            },
            "fps_back": {
                "code": 275,
                "output": "modify(Control_L, wait(20).key(space))",
                "name": "Back",
                "custom_name": "BulletJump",
                "target": "keyboard"
            },
            "btn_middle": {
                "code": 274,
                "output": "disable",
                "name": "Middle Click",
                "target": "keyboard"
            }
        }
        dev_info = {
            "name": "Razer Naga Trinity",
            "hash": "851b995594cbeb43e755461039e83013",
            "key_to_hash": {
                274: "4a7e8e47ac053eac4fb9d67b78df2a8e",
                275: "4a7e8e47ac053eac4fb9d67b78df2a8e",
                276: "4a7e8e47ac053eac4fb9d67b78df2a8e"
            }
        }

        serialized = serialize_preset_data(state, dev_info)
        self.assertEqual(len(serialized), 3)

        by_code = {item["input_combination"][0]["code"]: item for item in serialized}

        # Check Forward
        fwd = by_code[276]
        self.assertEqual(fwd["output_symbol"], "4")
        self.assertEqual(fwd["mapping_type"], "key_macro")
        self.assertEqual(fwd["input_combination"][0]["origin_hash"], "4a7e8e47ac053eac4fb9d67b78df2a8e")

        # Check Back (Macro)
        back = by_code[275]
        self.assertEqual(back["output_symbol"], "modify(Control_L, wait(20).key(space))")
        self.assertEqual(back["mapping_type"], "key_macro")
        self.assertEqual(back["custom_name"], "BulletJump")

        # Check Middle (Disable)
        mid = by_code[274]
        self.assertEqual(mid["output_symbol"], "disable")
        self.assertEqual(mid["mapping_type"], "key_macro")

    def test_preset_valid_in_input_remapper_engine(self):
        import subprocess
        import sys
        import tempfile

        state = {
            "fps_forward": {"code": 276, "output": "4", "name": "Forward", "target": "keyboard"},
            "fps_back": {"code": 275, "output": "modify(Control_L, wait(20).key(space))", "name": "Back", "target": "keyboard"},
            "btn_middle": {"code": 274, "output": "disable", "name": "Middle Click", "target": "keyboard"}
        }
        dev_info = {
            "name": "Razer Naga Trinity",
            "hash": "851b995594cbeb43e755461039e83013",
            "key_to_hash": {274: "4a7e8e47ac053eac4fb9d67b78df2a8e", 275: "4a7e8e47ac053eac4fb9d67b78df2a8e", 276: "4a7e8e47ac053eac4fb9d67b78df2a8e"}
        }
        data = serialize_preset_data(state, dev_info)

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump(data, tf)
            tpath = Path(tf.name)

        validation_code = f"""
import sys, json
from pathlib import Path
try:
    from inputremapper.configs.preset import Preset
    from inputremapper.configs.keyboard_layout import keyboard_layout
except ImportError:
    sys.exit(42)

xmap_file = Path.home() / ".config" / "input-remapper-2" / "xmodmap.json"
if xmap_file.exists():
    try:
        with open(xmap_file, "r") as f:
            keyboard_layout.update(json.load(f))
    except Exception:
        pass

p = Preset(Path('{tpath}'))
p.load()
if not p.is_valid() or len(p) == 0:
    sys.exit(1)
sys.exit(0)
"""
        try:
            res = subprocess.run([sys.executable, "-c", validation_code], capture_output=True)
            if res.returncode == 42:
                self.skipTest("inputremapper package not installed on system")
            self.assertEqual(res.returncode, 0, f"Preset validation failed in input-remapper: {res.stderr.decode()}")
        finally:
            if tpath.exists():
                tpath.unlink()



class TestStropDeviceUtils(unittest.TestCase):
    def test_clean_device_display_name(self):
        self.assertEqual(clean_device_display_name("Razer Razer Tartarus Pro"), "Razer Tartarus Pro")
        self.assertEqual(clean_device_display_name("Razer Tartarus Pro"), "Razer Tartarus Pro")
        self.assertEqual(clean_device_display_name("Tartarus Pro"), "Razer Tartarus Pro")
        self.assertEqual(clean_device_display_name("Blade 15 (2022)"), "Blade 15 (2022)")

    def test_calculate_origin_hash(self):
        h = calculate_origin_hash("{1: [2, 3]}", "TestDevice")
        self.assertEqual(len(h), 32)
        self.assertTrue(h.isalnum())

    def test_is_razer_device(self):
        self.assertTrue(is_razer_device("Some Keyboard", vendor_id=0x1532))
        self.assertTrue(is_razer_device("Razer Tartarus Pro", vendor_id=None))
        self.assertTrue(is_razer_device("Razer BlackWidow V3", vendor_id=None))
        self.assertFalse(is_razer_device(None, vendor_id=None))
        self.assertFalse(is_razer_device("", vendor_id=None))


class TestStropGamepadParsing(unittest.TestCase):
    def test_left_stick_diagonal_parsing(self):
        from strop_core.gamepad import parse_gamepad_display_text, get_left_stick_mappings
        maps = get_left_stick_mappings()
        self.assertEqual(parse_gamepad_display_text(maps["n"]), "LS↑")
        self.assertEqual(parse_gamepad_display_text(maps["ne"]), "LS↗")
        self.assertEqual(parse_gamepad_display_text(maps["e"]), "LS→")
        self.assertEqual(parse_gamepad_display_text(maps["se"]), "LS↘")
        self.assertEqual(parse_gamepad_display_text(maps["s"]), "LS↓")
        self.assertEqual(parse_gamepad_display_text(maps["sw"]), "LS↙")
        self.assertEqual(parse_gamepad_display_text(maps["w"]), "LS←")
        self.assertEqual(parse_gamepad_display_text(maps["nw"]), "LS↖")

    def test_right_stick_diagonal_parsing(self):
        from strop_core.gamepad import parse_gamepad_display_text, get_right_stick_mappings
        maps = get_right_stick_mappings()
        self.assertEqual(parse_gamepad_display_text(maps["n"]), "RS↑")
        self.assertEqual(parse_gamepad_display_text(maps["ne"]), "RS↗")
        self.assertEqual(parse_gamepad_display_text(maps["se"]), "RS↘")
        self.assertEqual(parse_gamepad_display_text(maps["sw"]), "RS↙")
        self.assertEqual(parse_gamepad_display_text(maps["nw"]), "RS↖")


class TestStropMacroTokenizer(unittest.TestCase):
    def test_nested_macro_preserved(self):
        from strop_core.macros import normalize_macro_to_input_remapper, parse_dsl_sequence
        nested = "modify(Control_L, wait(20).key(space))"
        self.assertEqual(normalize_macro_to_input_remapper(nested), nested)
        dsl_tokens = parse_dsl_sequence(nested)
        self.assertEqual(dsl_tokens, [nested])

    def test_run_command_with_dots_preserved(self):
        from strop_core.macros import normalize_macro_to_input_remapper
        cmd = 'run("echo 1.2.3")'
        self.assertEqual(normalize_macro_to_input_remapper(cmd), cmd)


class TestStropPresetSecurityAndState(unittest.TestCase):
    def test_sanitize_filename(self):
        from strop_core.presets import sanitize_filename
        self.assertEqual(sanitize_filename("../../etc/passwd"), "passwd")
        self.assertEqual(sanitize_filename("my-profile.json"), "my-profile")
        self.assertEqual(sanitize_filename("valid_name"), "valid_name")

    def test_atomic_json_write_preserves_old_file_on_replace_failure(self):
        from strop_core.presets import _atomic_write_json
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state.json"
            path.write_text('{"old": true}', encoding="utf-8")
            with patch("strop_core.presets.os.replace", side_effect=OSError("injected failure")):
                with self.assertRaises(OSError):
                    _atomic_write_json(path, {"new": True})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"old": True})
            self.assertEqual(list(Path(temp_dir).glob("*.tmp")), [])

    def test_load_preset_file_rejects_malformed_entries(self):
        from strop_core.presets import load_preset_file
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text(json.dumps([{"output_symbol": "a"}]), encoding="utf-8")
            self.assertIsNone(load_preset_file(path))

    def test_daemon_check_uses_supported_hello_command(self):
        from strop_core.presets import check_daemon_status
        with patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
             patch("strop_core.presets.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "hello", "")) as run:
            status, _ = check_daemon_status()
            self.assertEqual(status, "running")
            self.assertIn("hello", run.call_args.args[0])

    def test_apply_profile_missing_executable_does_not_record_active_profile(self):
        from strop_core.presets import apply_profile, get_active_profile
        dev = "TestRazerDevice99"
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "active_profiles.json"
            with patch("strop_core.presets.get_active_profiles_file", return_value=profiles_file), \
                 patch("strop_core.presets.shutil.which", return_value=None):
                result = apply_profile(dev, "gaming")
                self.assertEqual(result.status, "failed")
                self.assertIn("not installed", result.message)
                self.assertIsNone(get_active_profile(dev))

    def test_apply_profile_command_failure_does_not_record_active_profile(self):
        from strop_core.presets import apply_profile, get_active_profile
        dev = "Razer Test Device"
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "active_profiles.json"
            preset_dir = Path(temp_dir) / "presets"
            preset_dir.mkdir()
            (preset_dir / "gaming.json").write_text("[]", encoding="utf-8")
            (Path(temp_dir) / "config.json").write_text("{}", encoding="utf-8")
            with patch("strop_core.presets.get_active_profiles_file", return_value=profiles_file), \
                 patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
                 patch("strop_core.presets.get_device_presets_dir", return_value=preset_dir), \
                 patch("strop_core.presets._profile_config_dir", return_value=Path(temp_dir)), \
                 patch("strop_core.presets._list_input_remapper_devices", return_value=[dev]), \
                 patch("strop_core.presets._resolve_input_remapper_device", return_value=dev), \
                 patch("strop_core.presets.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "apply failed")):
                result = apply_profile(dev, "gaming")
                self.assertEqual(result.status, "failed")
                self.assertIn("apply failed", result.message)
                self.assertIsNone(get_active_profile(dev))

    def test_apply_profile_timeout_reports_unconfirmed_state(self):
        from strop_core.presets import apply_profile, get_active_profile
        dev = "Razer Test Device"
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "active_profiles.json"
            preset_dir = Path(temp_dir) / "presets"
            preset_dir.mkdir()
            (preset_dir / "gaming.json").write_text("[]", encoding="utf-8")
            (Path(temp_dir) / "config.json").write_text("{}", encoding="utf-8")
            timeout = subprocess.TimeoutExpired("input-remapper-control", 3.0)
            with patch("strop_core.presets.get_active_profiles_file", return_value=profiles_file), \
                 patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
                 patch("strop_core.presets.get_device_presets_dir", return_value=preset_dir), \
                 patch("strop_core.presets._profile_config_dir", return_value=Path(temp_dir)), \
                 patch("strop_core.presets._list_input_remapper_devices", return_value=[dev]), \
                 patch("strop_core.presets._resolve_input_remapper_device", return_value=dev), \
                 patch("strop_core.presets.subprocess.run", side_effect=timeout):
                result = apply_profile(dev, "gaming")
                self.assertEqual(result.status, "unknown")
                self.assertIn("may have started", result.message)
                self.assertIsNone(get_active_profile(dev))

    def test_apply_profile_requires_a_valid_saved_preset(self):
        from strop_core.presets import apply_profile
        with tempfile.TemporaryDirectory() as temp_dir:
            preset_dir = Path(temp_dir) / "presets"
            preset_dir.mkdir()
            with patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
                 patch("strop_core.presets.get_device_presets_dir", return_value=preset_dir):
                result = apply_profile("Razer Test Device", "missing")
                self.assertEqual(result.status, "failed")
                self.assertIn("missing or invalid", result.message)

    def test_apply_profile_confirms_running_state_before_recording(self):
        from strop_core.presets import apply_profile, get_active_profile
        dev = "Razer Test Device"
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "active_profiles.json"
            preset_dir = Path(temp_dir) / "presets"
            preset_dir.mkdir()
            (preset_dir / "gaming.json").write_text("[]", encoding="utf-8")
            (Path(temp_dir) / "config.json").write_text("{}", encoding="utf-8")
            with patch("strop_core.presets.get_active_profiles_file", return_value=profiles_file), \
                 patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
                 patch("strop_core.presets.get_device_presets_dir", return_value=preset_dir), \
                 patch("strop_core.presets._profile_config_dir", return_value=Path(temp_dir)), \
                 patch("strop_core.presets._list_input_remapper_devices", return_value=[dev]), \
                 patch("strop_core.presets._resolve_input_remapper_device", return_value=dev), \
                 patch("strop_core.presets.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
                 patch("strop_core.presets._wait_for_injector_state", return_value="RUNNING"):
                result = apply_profile(dev, "gaming")
                self.assertEqual(result.status, "applied")
                self.assertEqual(get_active_profile(dev), "gaming")

    def test_stop_profile_failure_keeps_last_recorded_profile(self):
        from strop_core.presets import stop_profile, get_active_profile
        dev = "Razer Test Device"
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "active_profiles.json"
            profiles_file.write_text(json.dumps({dev: "gaming"}), encoding="utf-8")
            with patch("strop_core.presets.get_active_profiles_file", return_value=profiles_file), \
                 patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
                 patch("strop_core.presets._list_input_remapper_devices", return_value=[dev]), \
                 patch("strop_core.presets._resolve_input_remapper_device", return_value=dev), \
                 patch("strop_core.presets.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "", "stop failed")):
                result = stop_profile(dev)
                self.assertEqual(result.status, "failed")
                self.assertEqual(get_active_profile(dev), "gaming")

    def test_stop_profile_clears_record_only_after_confirmed_stopped_state(self):
        from strop_core.presets import stop_profile, get_active_profile
        dev = "Razer Test Device"
        with tempfile.TemporaryDirectory() as temp_dir:
            profiles_file = Path(temp_dir) / "active_profiles.json"
            profiles_file.write_text(json.dumps({dev: "gaming"}), encoding="utf-8")
            with patch("strop_core.presets.get_active_profiles_file", return_value=profiles_file), \
                 patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
                 patch("strop_core.presets._list_input_remapper_devices", return_value=[dev]), \
                 patch("strop_core.presets._resolve_input_remapper_device", return_value=dev), \
                 patch("strop_core.presets.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
                 patch("strop_core.presets._wait_for_injector_state", return_value="STOPPED"):
                result = stop_profile(dev)
                self.assertEqual(result.status, "stopped")
                self.assertIsNone(get_active_profile(dev))


class TestStropThemeAndAbout(unittest.TestCase):
    def test_show_about_dialog_callable(self):
        from strop_core.theme import show_about_dialog
        self.assertTrue(callable(show_about_dialog))

    def test_show_about_dialog_headless_safe(self):
        from strop_core.theme import show_about_dialog
        import gi
        gi.require_version('Gtk', '4.0')
        gi.require_version('Gdk', '4.0')
        from gi.repository import Gtk, Gdk

        dlg = show_about_dialog()
        if Gdk.Display.get_default() is None:
            self.assertIsNone(dlg, "In headless environment with no display, show_about_dialog should return None safely")
        else:
            self.assertIsNotNone(dlg)
            self.assertEqual(dlg.get_program_name(), "Strop")


if __name__ == "__main__":
    unittest.main()
