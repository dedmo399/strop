#!/usr/bin/env python3
"""
Unit tests for Strop Core:
- Catalog device classification and archetype resolution
- Macro parsing, timing extraction, and normalization
- Preset serialization and input-remapper compatibility
- Device name normalization and origin_hash computation
"""

import unittest
import os
import json
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

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
    MOUSE_FPS,
    MOUSE_AMBI,
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
    device_model_name,
    scan_all_connected_devices,
    detect_device,
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

# The test must not depend on a desktop user's cached X11 keyboard layout.
keyboard_layout.update({{"4": 5, "control_l": 29, "space": 57}})

p = Preset(Path('{tpath}'))
p.load()
if not p.is_valid() or len(p) != 3:
    sys.exit(1)
sys.exit(0)
"""
        try:
            res = subprocess.run([sys.executable, "-c", validation_code], capture_output=True, timeout=10)
            if res.returncode == 42:
                if os.environ.get("STROP_REQUIRE_INPUT_REMAPPER") == "1":
                    self.fail("input-remapper is required for this test run but could not be imported")
                self.skipTest("inputremapper package not installed on system")
            self.assertEqual(res.returncode, 0, f"Preset validation failed in input-remapper: {res.stderr.decode()}")
        finally:
            if tpath.exists():
                tpath.unlink()



class TestStropDeviceUtils(unittest.TestCase):
    def test_model_only_labels(self):
        for raw, expected in (
            ("Razer Razer Tartarus Pro", "Tartarus Pro"),
            ("Razer BlackWidow V3", "BlackWidow V3"),
            ("Razer Naga Trinity", "Naga Trinity"),
            ("Tartarus Pro", "Tartarus Pro"),
            ("Blade 15 (2022)", "Blade 15 (2022)"),
        ):
            self.assertEqual(device_model_name(raw), expected)

    def test_discovery_excludes_forwarded_devices_and_preserves_physical_hashes(self):
        from unittest.mock import Mock

        nodes = {}
        for index, model in enumerate(("Naga Trinity", "BlackWidow V3", "Tartarus Pro")):
            for forwarded in (True, False):
                path = f"/dev/input/event{index * 2 + int(forwarded)}"
                raw = f"Razer Razer {model}"
                name = f"input-remapper {raw} forwarded" if forwarded else raw
                node = Mock(name=name)
                node.name = name
                node.path = path
                node.info = SimpleNamespace(vendor=0x1532)
                node.capabilities.return_value = {1: [30, 31]}
                nodes[path] = node
        evdev = SimpleNamespace(list_devices=lambda: list(nodes),
                                InputDevice=nodes.__getitem__, ecodes=SimpleNamespace(EV_KEY=1))
        with patch.dict("sys.modules", {"evdev": evdev}):
            devices = scan_all_connected_devices()
            selected = detect_device("naga", "Razer Naga Pro")
        self.assertEqual(len(devices), 3)
        self.assertEqual(selected["name"], "Razer Naga Trinity")
        for device, model in zip(devices, ("Naga Trinity", "BlackWidow V3", "Tartarus Pro")):
            self.assertEqual(device["name"], f"Razer {model}")
            self.assertEqual(device["clean_name"], model)
            expected_hash = calculate_origin_hash(str({1: [30, 31]}), f"Razer Razer {model}")
            self.assertEqual(device["hash"], expected_hash)
            self.assertEqual(device["all_hashes"], {device["path"]: expected_hash})
            self.assertEqual(device["key_to_hash"], {30: expected_hash, 31: expected_hash})
        for node in nodes.values():
            self.assertEqual(node.close.call_count, 2)

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
        self.assertFalse(is_razer_device("input-remapper Razer Razer Naga Trinity forwarded", vendor_id=0x1532))
        self.assertFalse(is_razer_device("input-remapper keyboard"))
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

    def test_gamepad_button_conversion_and_preset_serialization(self):
        from strop_core.gamepad import parse_gamepad_button_output, format_gamepad_button_output
        from strop_core.presets import serialize_preset_data
        self.assertEqual(parse_gamepad_button_output("gamepad(BTN_DPAD_UP)"), (1, 544))
        self.assertEqual(format_gamepad_button_output(1, 547), "gamepad(BTN_DPAD_RIGHT)")
        data = serialize_preset_data({"up": {"code": 17, "name": "Up", "output": "gamepad(BTN_DPAD_UP)", "target": "gamepad"}},
                                    {"name": "test pad", "hash": "abc", "key_to_hash": {17: "keyhash"}})
        mapping = data[0]
        self.assertEqual(mapping["output_type"], 1)
        self.assertEqual(mapping["output_code"], 544)


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

    def test_escaped_quote_and_malformed_delimiters(self):
        from strop_core.macros import _split_macro_tokens
        self.assertEqual(_split_macro_tokens('run("echo \\\"a.b\\\"").key(c)'), ['run("echo \\\"a.b\\\"")', 'key(c)'])
        for malformed in ('key(a', 'key(a))', 'run("unfinished)'):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                _split_macro_tokens(malformed)

    def test_built_in_macro_cannot_be_overwritten(self):
        from strop_core.macros import save_or_update_macro, load_all_macros, MACRO_TEMPLATES
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "macros.json"
            with patch("strop_core.macros.get_macros_file_path", return_value=path):
                result = save_or_update_macro({
                    "id": MACRO_TEMPLATES[0]["id"], "title": "Changed", "macro": "space",
                    "built_in": False,
                })
                self.assertFalse(result)
                self.assertEqual(load_all_macros()[0]["title"], MACRO_TEMPLATES[0]["title"])
                self.assertFalse(path.exists())


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

    def test_validate_preset_data_checks_nested_inputs_and_backend_fields(self):
        from strop_core.presets import validate_preset_data
        valid = [{
            "input_combination": [{"type": 1, "code": 30, "origin_hash": "abc"}],
            "target_uinput": "keyboard", "output_symbol": "a", "name": "A",
            "mapping_type": "key_macro", "custom_name": "Alpha",
        }]
        self.assertIsNone(validate_preset_data(valid))
        invalid = json.loads(json.dumps(valid))
        invalid[0]["input_combination"] = [{"type": True, "code": 30}]
        self.assertIn("integer type", validate_preset_data(invalid))
        invalid = json.loads(json.dumps(valid))
        invalid[0]["target_uinput"] = "analog"
        self.assertIn("unsupported target_uinput", validate_preset_data(invalid))

    def test_save_rejects_invalid_serialized_data_without_overwriting(self):
        from strop_core.presets import save_device_preset
        with tempfile.TemporaryDirectory() as temp_dir:
            preset_dir = Path(temp_dir)
            existing = preset_dir / "gaming.json"
            existing.write_text('[{"existing": true}]', encoding="utf-8")
            state = {"key": {"code": 30, "output": "a", "name": "A", "target": "unsupported"}}
            with patch("strop_core.presets.get_device_presets_dir", return_value=preset_dir):
                self.assertIsNone(save_device_preset("Razer Test", "gaming", state, {}))
            self.assertEqual(existing.read_text(encoding="utf-8"), '[{"existing": true}]')

    def test_save_preserves_valid_entries_strop_cannot_edit(self):
        from strop_core.presets import save_device_preset
        preserved = [{
            "input_combination": [{"type": 3, "code": 0, "analog_threshold": 50}],
            "target_uinput": "gamepad", "output_symbol": "a", "name": "Axis",
            "mapping_type": "key_macro", "backend_extension": {"keep": True},
        }]
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("strop_core.presets.get_device_presets_dir", return_value=Path(temp_dir)):
                saved = save_device_preset("Razer Test", "gaming", {}, {}, preserved_entries=preserved)
            self.assertIsNotNone(saved)
            self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), preserved)

    def test_profile_import_round_trips_combo_label_and_target(self):
        from types import SimpleNamespace
        from strop_core.studio_base import BaseStudioWindow
        from strop_core.presets import serialize_preset_data

        original = [{
            "input_combination": [
                {"type": 1, "code": 30, "origin_hash": "device-a"},
                {"type": 1, "code": 31, "origin_hash": "device-b"},
            ],
            "target_uinput": "mouse", "output_symbol": "b", "name": "A",
            "custom_name": "quick action", "mapping_type": "key_macro",
        }]

        class Entry:
            def set_text(self, _text):
                pass

        state = {"key_a": {
            "code": 30, "origin_hash": "device-a", "name": "A", "label": "A",
            "output": "", "target": "keyboard",
        }}
        fake_studio = SimpleNamespace(
            state=state, detected_device={"key_to_hash": {30: "device-a", 31: "device-b"}},
            selected_key_id=None, entry_preset_name=Entry(),
            _update_all_visuals=lambda: None,
        )
        fake_studio._match_preset_key = lambda code, name, origin_hash=None: BaseStudioWindow._match_preset_key(
            fake_studio, code, name, origin_hash
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "roundtrip.json"
            path.write_text(json.dumps(original), encoding="utf-8")
            matched, total = BaseStudioWindow._load_preset_file_data(fake_studio, str(path))

        self.assertEqual((matched, total), (1, 1))
        exported = serialize_preset_data(state, {"key_to_hash": {30: "device-a", 31: "device-b"}})
        self.assertEqual(exported, original)

    def test_profile_import_leaves_unrepresented_mapping_counted_as_unmapped(self):
        from types import SimpleNamespace
        from strop_core.studio_base import BaseStudioWindow

        data = [{
            "input_combination": [{"type": 3, "code": 0, "origin_hash": "device-a", "analog_threshold": 50}],
            "target_uinput": "gamepad", "output_symbol": "a", "name": "Axis",
            "mapping_type": "key_macro",
        }]
        state = {"axis": {"code": 0, "name": "Axis", "output": "old", "target": "keyboard"}}
        fake_studio = SimpleNamespace(
            state=state, detected_device={"key_to_hash": {}}, selected_key_id=None,
            entry_preset_name=SimpleNamespace(set_text=lambda _text: None),
            _update_all_visuals=lambda: None,
        )
        fake_studio._match_preset_key = lambda code, name, origin_hash=None: BaseStudioWindow._match_preset_key(
            fake_studio, code, name, origin_hash
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "unsupported.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            matched, total = BaseStudioWindow._load_preset_file_data(fake_studio, str(path))
        self.assertEqual((matched, total), (0, 1))
        self.assertEqual(state["axis"]["output"], "")
        self.assertEqual(fake_studio.unrepresented_preset_entries, data)

    def test_daemon_check_uses_supported_hello_command(self):
        from strop_core.presets import check_daemon_status
        with patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
             patch("strop_core.presets._is_dbus_daemon_active", return_value=False), \
             patch("strop_core.presets.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "hello", "")) as run:
            status, _ = check_daemon_status()
            self.assertEqual(status, "running")
            self.assertIn("hello", run.call_args.args[0])

    def test_daemon_check_uses_dbus_when_available(self):
        from strop_core.presets import check_daemon_status
        with patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
             patch("strop_core.presets._is_dbus_daemon_active", return_value=True), \
             patch("strop_core.presets.subprocess.run") as run:
            status, msg = check_daemon_status()
            self.assertEqual(status, "running")
            self.assertIn("active", msg)
            run.assert_not_called()

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

    def test_stop_profile_clears_record_when_backend_has_no_injector(self):
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
                 patch("strop_core.presets._wait_for_injector_state", return_value="UNKNOWN"):
                result = stop_profile(dev)
                self.assertEqual(result.status, "stopped")
                self.assertIsNone(get_active_profile(dev))

    def test_stop_profile_backend_errors_preserve_last_confirmed_profile(self):
        from strop_core.presets import stop_profile, get_active_profile
        dev = "Razer Test Device"
        for backend_state in ("FAILED", "NO_GRAB", "UPGRADE_EVDEV"):
            with self.subTest(state=backend_state), tempfile.TemporaryDirectory() as temp_dir:
                profiles_file = Path(temp_dir) / "active_profiles.json"
                profiles_file.write_text(json.dumps({dev: "gaming"}), encoding="utf-8")
                with patch("strop_core.presets.get_active_profiles_file", return_value=profiles_file), \
                     patch("strop_core.presets.shutil.which", return_value="/usr/bin/input-remapper-control"), \
                     patch("strop_core.presets._list_input_remapper_devices", return_value=[dev]), \
                     patch("strop_core.presets._resolve_input_remapper_device", return_value=dev), \
                     patch("strop_core.presets.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "", "")), \
                     patch("strop_core.presets._wait_for_injector_state", return_value=backend_state):
                    result = stop_profile(dev)
                    self.assertEqual(result.status, "failed")
                    self.assertIn(backend_state, result.message)
                    self.assertEqual(get_active_profile(dev), "gaming")


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


class TestReviewFixes(unittest.TestCase):
    def test_serialize_preset_skips_empty_output_with_custom_name(self):
        from strop_core.presets import serialize_preset_data, validate_preset_data

        state = {
            "k01": {
                "code": 30, "name": "Key 01", "label": "01",
                "output": "", "custom_name": "Leftover Label", "target": "keyboard",
            },
            "k02": {
                "code": 48, "name": "Key 02", "label": "02",
                "output": "b", "custom_name": "Jump", "target": "keyboard",
            },
        }
        serialized = serialize_preset_data(state, {"key_to_hash": {30: "h1", 48: "h1"}})
        self.assertEqual(len(serialized), 1)
        self.assertEqual(serialized[0]["output_symbol"], "b")
        self.assertIsNone(validate_preset_data(serialized))

    def test_diagonal_dpad_combo_round_trips_without_clobbering_cardinal_keys(self):
        from types import SimpleNamespace
        from strop_core.studio_base import BaseStudioWindow
        from strop_core.presets import serialize_preset_data

        state = {
            "dpad-n": {
                "id": "dpad-n", "code": 103, "name": "D-Pad Up", "label": "N",
                "output": "KEY_UP", "target": "keyboard",
            },
            "dpad-e": {
                "id": "dpad-e", "code": 106, "name": "D-Pad Right", "label": "E",
                "output": "KEY_RIGHT", "target": "keyboard",
            },
            "dpad-ne": {
                "id": "dpad-ne", "code": None, "combo": [103, 106], "name": "D-Pad Up-Right",
                "label": "NE", "output": "w + d", "target": "keyboard",
            },
        }
        fake_studio = SimpleNamespace(
            state=state,
            detected_device={"key_to_hash": {103: "hash-dpad", 106: "hash-dpad"}},
            selected_key_id=None,
            entry_preset_name=SimpleNamespace(set_text=lambda _t: None),
            _update_all_visuals=lambda: None,
        )
        fake_studio._match_preset_key = (
            lambda code, name, origin_hash=None, combination=None: BaseStudioWindow._match_preset_key(
                fake_studio, code, name, origin_hash, combination
            )
        )

        exported = serialize_preset_data(state, fake_studio.detected_device)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "dpad.json"
            path.write_text(json.dumps(exported), encoding="utf-8")
            matched, total = BaseStudioWindow._load_preset_file_data(fake_studio, str(path))

        self.assertEqual((matched, total), (3, 3))
        self.assertEqual(state["dpad-n"]["output"], "KEY_UP")
        self.assertEqual(state["dpad-e"]["output"], "KEY_RIGHT")
        self.assertEqual(state["dpad-ne"]["output"], "w + d")
        self.assertEqual(state["dpad-ne"]["combo"], [103, 106])

        # Reloading an empty preset must keep the intrinsic combo on dpad-ne intact
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_path = Path(temp_dir) / "empty.json"
            empty_path.write_text("[]", encoding="utf-8")
            BaseStudioWindow._load_preset_file_data(fake_studio, str(empty_path))
        self.assertEqual(state["dpad-ne"]["combo"], [103, 106])

    def test_keypad_batch_actions_clear_custom_name_and_preserve_scroll_target(self):
        from types import SimpleNamespace
        import strop_keypad

        win = SimpleNamespace(
            state={},
            archetype="tartarus",
            selected_key_id="grid-0-0",
            entry_output=SimpleNamespace(set_text=lambda _t: None),
            entry_custom_label=SimpleNamespace(set_text=lambda _t: None),
            _update_all_visuals=lambda: None,
        )

        strop_keypad.KeypadMainWindow._init_hardware_state(win)
        self.assertEqual(win.state["scrollUp"]["id"], "scrollUp")
        self.assertEqual(win.state["scrollDown"]["id"], "scrollDown")

        win.state["grid-0-0"]["custom_name"] = "Custom"
        win.state["scrollUp"]["target"] = "keyboard"
        win.state["scrollUp"]["custom_name"] = "WheelCustom"

        with patch.object(strop_keypad.Gtk, "AlertDialog", return_value=SimpleNamespace(show=lambda _s: None)):
            strop_keypad.KeypadMainWindow._on_set_all_to_default(win, None)
            self.assertEqual(win.state["grid-0-0"]["custom_name"], "")
            self.assertEqual(win.state["scrollUp"]["custom_name"], "")
            self.assertEqual(win.state["scrollUp"]["target"], "mouse")

            win.state["grid-0-0"]["custom_name"] = "CustomAgain"
            strop_keypad.KeypadMainWindow._on_set_all_to_disable(win, None)
            self.assertEqual(win.state["grid-0-0"]["custom_name"], "")
            self.assertEqual(win.state["grid-0-0"]["output"], "disable")

    def test_macro_studio_custom_step_handles_invalid_syntax_gracefully(self):
        from types import SimpleNamespace
        import strop_macro

        toasts = []
        win = SimpleNamespace(
            entry_custom_step=SimpleNamespace(
                get_text=lambda: "key(",
                set_text=lambda _t: None,
            ),
            current_steps=[],
            _render_timeline=lambda: None,
            toast=SimpleNamespace(show_message=lambda msg, icon="": toasts.append((msg, icon))),
        )
        strop_macro.StropMacroStudioWindow._on_add_custom_step(win)
        self.assertEqual(len(win.current_steps), 0)
        self.assertEqual(len(toasts), 1)
        self.assertIn("Invalid macro syntax", toasts[0][0])

    def test_lighting_engine_returns_false_when_no_devices_or_unsupported_fx(self):
        from types import SimpleNamespace
        import strop_core.studio_base as studio_base
        from strop_core.lighting import RazerLightingEngine
        from strop_core.studio_base import BaseStudioWindow

        engine = RazerLightingEngine()
        engine._available = True
        engine._manager = SimpleNamespace(devices=[])
        self.assertFalse(engine.apply_all_connected_devices_lighting((0, 255, 0)))

        engine._manager = SimpleNamespace(devices=[SimpleNamespace(name="NoFxDevice", fx=None)])
        self.assertFalse(engine.apply_all_connected_devices_lighting((0, 255, 0)))

        toasts = []
        fake_studio = SimpleNamespace(
            selected_color_name="Green",
            detected_device={"name": "Razer Test"},
            default_device_name="Razer Test",
            apply_color_all_devices=True,
            toast=SimpleNamespace(show_message=lambda msg, icon="": toasts.append((msg, icon))),
        )
        with patch.object(
            studio_base,
            "get_lighting_engine",
            return_value=SimpleNamespace(apply_all_connected_devices_lighting=lambda _rgb: False),
        ):
            BaseStudioWindow._apply_lighting_to_hardware(fake_studio)
        self.assertEqual(len(toasts), 1)
        self.assertEqual(toasts[0][1], "⚠️")

    def test_record_button_toggles_recording_css_class(self):
        from types import SimpleNamespace
        from strop_core.studio_base import BaseStudioWindow

        classes = {"record-btn"}
        btn = SimpleNamespace(
            set_label=lambda _l: None,
            add_css_class=lambda c: classes.add(c),
            remove_css_class=lambda c: classes.discard(c),
        )
        fake_studio = SimpleNamespace(
            is_recording_input=False,
            btn_record_input=btn,
            entry_output=SimpleNamespace(set_placeholder_text=lambda _t: None),
        )
        BaseStudioWindow._start_recording(fake_studio)
        self.assertTrue(fake_studio.is_recording_input)
        self.assertIn("record-btn", classes)
        self.assertIn("recording", classes)

        BaseStudioWindow._stop_recording(fake_studio)
        self.assertFalse(fake_studio.is_recording_input)
        self.assertIn("record-btn", classes)
        self.assertNotIn("recording", classes)

    def test_mouse_studio_initializes_ambidextrous_right_side_buttons(self):
        from types import SimpleNamespace
        import strop_mouse

        win = SimpleNamespace(state={})
        strop_mouse.RazerMouseStudioWindow._init_hardware_state(win)
        self.assertIn("ambi_right_front", win.state)
        self.assertIn("ambi_right_back", win.state)


class TestStropDPIAndSensor(unittest.TestCase):
    def _make_fake_mouse(
        self,
        name="Razer Naga Trinity",
        pid=0x0067,
        dpi=(3800, 3800),
        max_dpi=16000,
        poll_rate=1000,
        features=None,
        available_dpi=None,
    ):
        features = features if features is not None else {"dpi", "poll_rate"}

        class FakeMouse:
            def __init__(self):
                self.name = name
                self.type = "mouse"
                self.serial = "TESTSERIAL123"
                self._vid = 0x1532
                self._pid = pid
                self._dpi = dpi
                self.max_dpi = max_dpi
                self._poll_rate = poll_rate
                self.available_dpi = available_dpi or []
                self.supported_poll_rates = [125, 500, 1000]
                self.dpi_stages = (1, [(800, 800), (1600, 1600)])

            def has(self, feat):
                return feat in features

            @property
            def dpi(self):
                return self._dpi

            @dpi.setter
            def dpi(self, val):
                self._dpi = (int(val[0]), int(val[1]))

            @property
            def poll_rate(self):
                return self._poll_rate

            @poll_rate.setter
            def poll_rate(self, val):
                self._poll_rate = int(val)

        return FakeMouse()

    def test_discover_capabilities_and_stable_pid_matching(self):
        from strop_core.dpi import RazerDPIEngine

        naga = self._make_fake_mouse(name="Razer Naga Trinity", pid=0x0067, dpi=(3800, 3800))
        other = self._make_fake_mouse(name="Razer DeathAdder V2", pid=0x0084, dpi=(1600, 1600))
        engine = RazerDPIEngine()
        engine._connected = True
        engine._manager = SimpleNamespace(devices=[other, naga])

        # Match by exact PID even if name differs slightly
        matched = engine.get_razer_mouse("Custom Label", pid=0x0067)
        self.assertIs(matched, naga)

        caps = engine.discover_capabilities("Razer Naga Trinity", pid=0x0067)
        self.assertTrue(caps.available)
        self.assertEqual(caps.device_name, "Razer Naga Trinity")
        self.assertEqual(caps.pid, 0x0067)
        self.assertTrue(caps.has_dpi)
        self.assertTrue(caps.has_independent_xy)
        self.assertEqual(caps.max_dpi, 16000)
        self.assertEqual(caps.current_dpi, (3800, 3800))
        self.assertTrue(caps.has_poll_rate)
        self.assertEqual(caps.current_poll_rate, 1000)

    def test_apply_dpi_linked_independent_and_discrete_available_dpi(self):
        from strop_core.dpi import RazerDPIEngine

        naga = self._make_fake_mouse()
        engine = RazerDPIEngine()
        engine._connected = True
        engine._manager = SimpleNamespace(devices=[naga])

        # Linked X=Y DPI
        res = engine.apply_dpi("Razer Naga Trinity", 1600, 1600, pid=0x0067)
        self.assertTrue(res.success)
        self.assertEqual(res.dpi, (1600, 1600))
        self.assertEqual(naga.dpi, (1600, 1600))

        # Independent X/Y DPI + clamping above max_dpi
        res_xy = engine.apply_dpi("Razer Naga Trinity", 2400, 99999, pid=0x0067)
        self.assertTrue(res_xy.success)
        self.assertEqual(res_xy.dpi, (2400, 16000))
        self.assertEqual(naga.dpi, (2400, 16000))

        # Discrete available_dpi mouse (X-only, sends Y=0 to OpenRazer)
        discrete_mouse = self._make_fake_mouse(
            name="Razer Abyssus",
            pid=0x0042,
            dpi=(1800, 0),
            features={"dpi", "available_dpi"},
            available_dpi=[450, 1800, 3500],
        )
        engine._manager = SimpleNamespace(devices=[discrete_mouse])
        res_disc = engine.apply_dpi("Razer Abyssus", 1700, 1700, pid=0x0042)
        self.assertTrue(res_disc.success)
        self.assertEqual(discrete_mouse._dpi, (1800, 0))
        self.assertEqual(res_disc.dpi, (1800, 1800))

    def test_apply_poll_rate_and_error_reporting(self):
        from strop_core.dpi import RazerDPIEngine

        naga = self._make_fake_mouse()
        engine = RazerDPIEngine()
        engine._connected = True
        engine._manager = SimpleNamespace(devices=[naga])

        res_ok = engine.apply_poll_rate("Razer Naga Trinity", 500, pid=0x0067)
        self.assertTrue(res_ok.success)
        self.assertEqual(res_ok.poll_rate, 500)
        self.assertEqual(naga.poll_rate, 500)

        res_bad = engine.apply_poll_rate("Razer Naga Trinity", 333, pid=0x0067)
        self.assertFalse(res_bad.success)
        self.assertIn("Unsupported polling rate", res_bad.message)

    def test_mouse_settings_persistence_roundtrip(self):
        from strop_core.dpi import (
            MouseSensorCapabilities,
            MouseSensorSettings,
            load_mouse_settings,
            save_mouse_settings,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            settings_file = Path(temp_dir) / "mouse_settings.json"
            with patch("strop_core.dpi.get_mouse_settings_file", return_value=settings_file):
                custom = MouseSensorSettings(
                    dpi_x=1200,
                    dpi_y=1600,
                    linked_xy=False,
                    active_stage=2,
                    stages=[(400, 400), (1200, 1600), (2400, 2400), (3800, 3800), (6400, 6400)],
                    poll_rate=500,
                )
                self.assertTrue(save_mouse_settings("Razer Naga Trinity", custom))

                offline_caps = MouseSensorCapabilities(available=False, max_dpi=16000)
                loaded = load_mouse_settings("Razer Naga Trinity", offline_caps)
                self.assertEqual(loaded.dpi_x, 1200)
                self.assertEqual(loaded.dpi_y, 1600)
                self.assertFalse(loaded.linked_xy)
                self.assertEqual(loaded.active_stage, 2)
                self.assertEqual(loaded.stages[1], (1200, 1600))
                self.assertEqual(loaded.poll_rate, 500)

    def test_mouse_studio_stage_and_link_xy_handlers(self):
        import strop_mouse
        from strop_core.dpi import MouseSensorCapabilities, MouseSensorSettings, SensorOperationResult

        toasts = []
        applied_calls = []

        fake_engine = SimpleNamespace(
            discover_capabilities=lambda _name, pid=None: MouseSensorCapabilities(
                available=True,
                device_name="Razer Naga Trinity",
                has_dpi=True,
                has_independent_xy=True,
                min_dpi=100,
                max_dpi=16000,
                current_dpi=(1600, 1600),
                has_poll_rate=True,
                supported_poll_rates=[125, 500, 1000],
                current_poll_rate=1000,
            ),
            apply_sensor_settings=lambda name, settings, pid=None: (
                applied_calls.append((name, settings.dpi_x, settings.dpi_y, settings.poll_rate))
                or SensorOperationResult(True, "Applied 1600 DPI", dpi=(settings.dpi_x, settings.dpi_y), poll_rate=settings.poll_rate)
            ),
        )

        win = SimpleNamespace(
            _updating_dpi_controls=False,
            detected_device={"name": "Razer Naga Trinity", "product": 0x0067},
            default_device_name="Razer Naga Trinity",
            sensor_caps=fake_engine.discover_capabilities("Razer Naga Trinity"),
            sensor_settings=MouseSensorSettings(
                dpi_x=3800,
                dpi_y=3800,
                linked_xy=True,
                active_stage=4,
                stages=[(800, 800), (1600, 1600), (3200, 3200), (3800, 3800), (6400, 6400)],
                poll_rate=1000,
            ),
            stage_buttons=[],
            lbl_sensor_badge=None,
            toast=SimpleNamespace(show_message=lambda msg, icon="": toasts.append((msg, icon))),
        )
        # Bind helper methods from RazerMouseStudioWindow
        for method_name in (
            "_format_dpi_pair",
            "_refresh_stage_buttons",
            "_update_sensor_sensitivity_states",
            "_update_sensor_badge",
            "_sync_sensor_widgets_from_state",
            "_match_stage_for_current_dpi",
            "_on_dpi_stage_clicked",
            "_on_link_xy_toggled",
            "_apply_sensor_to_hardware",
        ):
            setattr(
                win,
                method_name,
                getattr(strop_mouse.RazerMouseStudioWindow, method_name).__get__(win, strop_mouse.RazerMouseStudioWindow),
            )

        with patch.object(strop_mouse, "get_dpi_engine", return_value=fake_engine):
            win._on_dpi_stage_clicked(None, 2)
            self.assertEqual(win.sensor_settings.active_stage, 2)
            self.assertEqual((win.sensor_settings.dpi_x, win.sensor_settings.dpi_y), (1600, 1600))
            self.assertEqual(len(applied_calls), 1)
            self.assertEqual(applied_calls[0], ("Razer Naga Trinity", 1600, 1600, 1000))

            # Unlock X=Y, change Y, then re-lock X=Y
            win.sensor_settings.dpi_x = 2000
            win.sensor_settings.dpi_y = 1200
            win.sensor_settings.linked_xy = False
            win._on_link_xy_toggled(SimpleNamespace(get_active=lambda: True))
            self.assertTrue(win.sensor_settings.linked_xy)
            self.assertEqual(win.sensor_settings.dpi_y, 2000)


class TestStropSidePlateDetection(unittest.TestCase):
    """Tests multi-plate mouse side plate detection and GUI focus on open and rescan."""

    def test_is_multi_plate_mouse_identifies_modular_naga_models(self):
        from strop_core.catalog import is_multi_plate_mouse

        self.assertTrue(is_multi_plate_mouse("Razer Naga Trinity"))
        self.assertTrue(is_multi_plate_mouse("Razer Naga Pro"))
        self.assertTrue(is_multi_plate_mouse("Razer Naga V2 Pro"))
        self.assertTrue(is_multi_plate_mouse("Unknown Device", pid=0x0067))
        self.assertTrue(is_multi_plate_mouse("Unknown Device", pid=0x0090))
        self.assertFalse(is_multi_plate_mouse("Razer DeathAdder V3"))
        self.assertFalse(is_multi_plate_mouse("Razer Basilisk V3"))
        self.assertFalse(is_multi_plate_mouse("Razer Tartarus Pro"))

    def test_detect_side_plate_from_preset_entries_and_state(self):
        from strop_core.device import (
            SIDE_PLATE_AMBI,
            SIDE_PLATE_FPS_2,
            SIDE_PLATE_HEX_7,
            SIDE_PLATE_MMO_12,
            detect_side_plate_from_preset_entries,
            detect_side_plate_from_state,
        )

        fps_entries = [
            {
                "input_combination": [{"type": 1, "code": 276, "origin_hash": "abc"}],
                "target_uinput": "keyboard",
                "output_symbol": "4",
                "name": "Forward Button (Front)",
                "mapping_type": "key_macro",
            },
            {
                "input_combination": [{"type": 1, "code": 275, "origin_hash": "abc"}],
                "target_uinput": "keyboard",
                "output_symbol": "5",
                "name": "Back Button (Rear)",
                "mapping_type": "key_macro",
            },
        ]
        self.assertEqual(detect_side_plate_from_preset_entries(fps_entries), SIDE_PLATE_FPS_2)

        hex_entries = [
            {
                "input_combination": [{"type": 1, "code": 2, "origin_hash": "abc"}],
                "target_uinput": "keyboard",
                "output_symbol": "1",
                "name": "Hex Side Button 1",
                "mapping_type": "key_macro",
            },
            {
                "input_combination": [{"type": 1, "code": 8, "origin_hash": "abc"}],
                "target_uinput": "keyboard",
                "output_symbol": "7",
                "name": "Hex Side Button 7",
                "mapping_type": "key_macro",
            },
        ]
        self.assertEqual(detect_side_plate_from_preset_entries(hex_entries), SIDE_PLATE_HEX_7)

        mmo_entries = [
            {
                "input_combination": [{"type": 1, "code": 2, "origin_hash": "abc"}],
                "target_uinput": "keyboard",
                "output_symbol": "1",
                "name": "Naga Side Button 1",
                "mapping_type": "key_macro",
            },
            {
                "input_combination": [{"type": 1, "code": 13, "origin_hash": "abc"}],
                "target_uinput": "keyboard",
                "output_symbol": "equal",
                "name": "Naga Side Button 12",
                "mapping_type": "key_macro",
            },
        ]
        self.assertEqual(detect_side_plate_from_preset_entries(mmo_entries), SIDE_PLATE_MMO_12)

        ambi_entries = [
            {
                "input_combination": [{"type": 1, "code": 278, "origin_hash": "abc"}],
                "target_uinput": "keyboard",
                "output_symbol": "r",
                "name": "Right Side Front Button",
                "mapping_type": "key_macro",
            }
        ]
        self.assertEqual(detect_side_plate_from_preset_entries(ambi_entries), SIDE_PLATE_AMBI)

        # State-based detection
        self.assertEqual(
            detect_side_plate_from_state({"fps_forward": {"output": "4"}, "naga_1": {"output": ""}}),
            SIDE_PLATE_FPS_2,
        )
        self.assertEqual(
            detect_side_plate_from_state({"naga_hex_3": {"output": "q"}}),
            SIDE_PLATE_HEX_7,
        )
        self.assertEqual(
            detect_side_plate_from_state({"naga_12": {"output": "f12"}}),
            SIDE_PLATE_MMO_12,
        )

    def test_scan_and_rescan_detect_attached_side_plate(self):
        import tempfile
        from unittest.mock import Mock
        from strop_core.device import (
            SIDE_PLATE_FPS_2,
            SIDE_PLATE_HEX_7,
            SIDE_PLATE_MMO_12,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_home = Path(tmpdir)
            strop_dir = tmp_home / ".config" / "strop"
            strop_dir.mkdir(parents=True, exist_ok=True)
            preset_dir = tmp_home / ".config" / "input-remapper-2" / "presets" / "Razer Razer Naga Trinity"
            preset_dir.mkdir(parents=True, exist_ok=True)

            # Initial scan: active profile 'fps_profile' uses 2-button FPS side plate (codes 275, 276)
            (strop_dir / "active_profiles.json").write_text(
                json.dumps({"Razer Naga Trinity": "fps_profile"}), encoding="utf-8"
            )
            (preset_dir / "fps_profile.json").write_text(
                json.dumps([
                    {
                        "input_combination": [{"type": 1, "code": 276, "origin_hash": "h1"}],
                        "target_uinput": "keyboard",
                        "output_symbol": "4",
                        "name": "Forward Button (Front)",
                        "mapping_type": "key_macro",
                    }
                ]),
                encoding="utf-8",
            )
            (preset_dir / "hex_profile.json").write_text(
                json.dumps([
                    {
                        "input_combination": [{"type": 1, "code": 5, "origin_hash": "h2"}],
                        "target_uinput": "keyboard",
                        "output_symbol": "e",
                        "name": "Hex Side Button 4",
                        "mapping_type": "key_macro",
                    }
                ]),
                encoding="utf-8",
            )
            (preset_dir / "mmo_profile.json").write_text(
                json.dumps([
                    {
                        "input_combination": [{"type": 1, "code": 12, "origin_hash": "h2"}],
                        "target_uinput": "keyboard",
                        "output_symbol": "minus",
                        "name": "Naga Side Button 11",
                        "mapping_type": "key_macro",
                    }
                ]),
                encoding="utf-8",
            )

            node = Mock(name="Razer Razer Naga Trinity")
            node.name = "Razer Razer Naga Trinity"
            node.path = "/dev/input/event5"
            node.info = SimpleNamespace(vendor=0x1532, product=0x0067)
            node.capabilities.return_value = {1: [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 272, 273, 274, 275, 276]}
            evdev = SimpleNamespace(
                list_devices=lambda: ["/dev/input/event5"],
                InputDevice=lambda _p: node,
                ecodes=SimpleNamespace(EV_KEY=1),
            )

            with patch.dict("sys.modules", {"evdev": evdev}), patch("pathlib.Path.home", return_value=tmp_home):
                dev1 = detect_device("naga", "Razer Naga Trinity")
                self.assertTrue(dev1["multi_plate"])
                self.assertEqual(dev1["side_plate"], SIDE_PLATE_FPS_2)
                self.assertEqual(dev1["side_plate_page"], 0)
                self.assertEqual(dev1["archetype"], MOUSE_FPS)

                # Rescan after switching to 7-button Hex profile
                (strop_dir / "active_profiles.json").write_text(
                    json.dumps({"Razer Naga Trinity": "hex_profile"}), encoding="utf-8"
                )
                dev2 = detect_device("naga", "Razer Naga Trinity")
                self.assertEqual(dev2["side_plate"], SIDE_PLATE_HEX_7)
                self.assertEqual(dev2["side_plate_page"], 1)
                self.assertEqual(dev2["archetype"], MOUSE_NAGA_HEX)

                # Rescan after switching to 12-button MMO profile
                (strop_dir / "active_profiles.json").write_text(
                    json.dumps({"Razer Naga Trinity": "mmo_profile"}), encoding="utf-8"
                )
                dev3 = detect_device("naga", "Razer Naga Trinity")
                self.assertEqual(dev3["side_plate"], SIDE_PLATE_MMO_12)
                self.assertEqual(dev3["side_plate_page"], 2)
                self.assertEqual(dev3["archetype"], MOUSE_NAGA_MMO)

    def test_mouse_studio_focuses_detected_side_plate_on_open_and_rescan(self):
        import strop_mouse
        from strop_core.device import (
            SIDE_PLATE_FPS_2,
            SIDE_PLATE_HEX_7,
            SIDE_PLATE_MMO_12,
        )

        current_page = [2]
        focused_calls = []

        fake_stack = SimpleNamespace(
            set_current_page=lambda idx: current_page.__setitem__(0, idx),
            get_current_page=lambda: current_page[0],
            grab_focus=lambda: focused_calls.append(("stack", current_page[0])),
        )
        fake_pages = {
            i: SimpleNamespace(grab_focus=lambda p=i: focused_calls.append(("page", p)))
            for i in range(4)
        }
        badge_markup = [""]
        fake_badge = SimpleNamespace(
            set_markup=lambda m: badge_markup.__setitem__(0, m),
            set_tooltip_text=lambda _t: None,
        )
        toasts = []

        win = SimpleNamespace(
            device_override="Razer Naga Trinity",
            default_device_name="Razer Naga Trinity",
            detected_device={
                "name": "Razer Naga Trinity",
                "product": 0x0067,
                "multi_plate": True,
                "side_plate": SIDE_PLATE_FPS_2,
                "side_plate_page": 0,
                "side_plate_label": "2-Button FPS / Ergonomic Plate",
                "archetype": MOUSE_FPS,
            },
            archetype=MOUSE_FPS,
            active_side_plate=SIDE_PLATE_FPS_2,
            _switching_side_plate_programmatically=False,
            state={},
            side_stack=fake_stack,
            side_plate_pages=fake_pages,
            lbl_side_plate_badge=fake_badge,
            toast=SimpleNamespace(show_message=lambda msg, icon="": toasts.append((msg, icon))),
        )

        for method_name in (
            "_plate_id_for_page",
            "_update_side_plate_badge",
            "_focus_detected_side_plate",
            "rescan_device_and_side_plate",
        ):
            setattr(
                win,
                method_name,
                getattr(strop_mouse.RazerMouseStudioWindow, method_name).__get__(
                    win, strop_mouse.RazerMouseStudioWindow
                ),
            )

        # 1. Focus on initial open -> focuses Page 0 (2-Button FPS Plate)
        plate = win._focus_detected_side_plate(focus_widget=True)
        self.assertEqual(plate, SIDE_PLATE_FPS_2)
        self.assertEqual(current_page[0], 0)
        self.assertIn(("page", 0), focused_calls)
        self.assertIn(("stack", 0), focused_calls)
        self.assertIn("2-Button FPS Plate", badge_markup[0])

        # 2. Rescan when 7-Button Hex plate is attached -> switches to Page 1 and focuses it
        focused_calls.clear()
        with patch.object(
            strop_mouse,
            "detect_device",
            return_value={
                "name": "Razer Naga Trinity",
                "product": 0x0067,
                "multi_plate": True,
                "side_plate": SIDE_PLATE_HEX_7,
                "side_plate_page": 1,
                "side_plate_label": "7-Button MOBA / Action-RPG Hex Plate",
                "archetype": MOUSE_NAGA_HEX,
            },
        ):
            rescanned_plate = win.rescan_device_and_side_plate(show_toast=True)
        self.assertEqual(rescanned_plate, SIDE_PLATE_HEX_7)
        self.assertEqual(current_page[0], 1)
        self.assertEqual(win.archetype, MOUSE_NAGA_HEX)
        self.assertIn(("page", 1), focused_calls)
        self.assertIn(("stack", 1), focused_calls)
        self.assertIn("7-Button Hex Plate", badge_markup[0])
        self.assertTrue(any("7-Button MOBA / Action-RPG Hex Plate" in msg for msg, _ in toasts))

        # 3. Rescan when 12-Button MMO plate is attached -> switches to Page 2 and focuses it
        focused_calls.clear()
        with patch.object(
            strop_mouse,
            "detect_device",
            return_value={
                "name": "Razer Naga Trinity",
                "product": 0x0067,
                "multi_plate": True,
                "side_plate": SIDE_PLATE_MMO_12,
                "side_plate_page": 2,
                "side_plate_label": "12-Button MMO / Macro Grid Plate",
                "archetype": MOUSE_NAGA_MMO,
            },
        ):
            rescanned_plate_mmo = win.rescan_device_and_side_plate(show_toast=True)
        self.assertEqual(rescanned_plate_mmo, SIDE_PLATE_MMO_12)
        self.assertEqual(current_page[0], 2)
        self.assertEqual(win.archetype, MOUSE_NAGA_MMO)
        self.assertIn(("page", 2), focused_calls)
        self.assertIn(("stack", 2), focused_calls)


class TestStropLightingStudio(unittest.TestCase):
    """Tests the 60 FPS Lighting Studio engine, all 16 effects, color/gradient math, zones, and catalog removal."""

    def test_color_and_gradient_utilities(self):
        from strop_core.lighting import (
            clamp_rgb,
            rgb_to_hex,
            hex_to_rgb,
            rgb_to_hsv,
            hsv_to_rgb,
            sample_gradient,
            add_colors,
            scale_color,
        )

        # Clamping & Hex roundtrip
        self.assertEqual(clamp_rgb(-15, 128.4, 999), (0, 128, 255))
        self.assertEqual(rgb_to_hex((255, 0, 85)), "#FF0055")
        self.assertEqual(hex_to_rgb("#FF0055"), (255, 0, 85))
        self.assertEqual(hex_to_rgb("0f8"), (0, 255, 136))
        self.assertIsNone(hex_to_rgb("not-a-hex"))

        # HSV <-> RGB roundtrip
        for sample in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255), (0, 0, 0), (255, 120, 40)]:
            h, s, v = rgb_to_hsv(*sample)
            reconstructed = hsv_to_rgb(h, s, v)
            for c1, c2 in zip(sample, reconstructed):
                self.assertAlmostEqual(c1, c2, delta=2)

        # Additive & brightness scaling
        self.assertEqual(add_colors((200, 40, 10), (100, 50, 250)), (255, 90, 255))
        self.assertEqual(scale_color((200, 100, 50), 0.5), (100, 50, 25))

        # Multi-stop gradient (2 to 6 stops)
        stops = [
            (0.0, (255, 0, 0)),
            (0.5, (0, 255, 0)),
            (1.0, (0, 0, 255)),
        ]
        self.assertEqual(sample_gradient(stops, 0.0), (255, 0, 0))
        self.assertEqual(sample_gradient(stops, 0.5), (0, 255, 0))
        self.assertEqual(sample_gradient(stops, 1.0), (0, 0, 255))
        mid = sample_gradient(stops, 0.25)
        self.assertTrue(120 <= mid[0] <= 135 and 120 <= mid[1] <= 135 and mid[2] == 0)

    def test_device_topologies_and_preset_clusters_and_marquee(self):
        from strop_core.lighting import (
            DEVICE_CATEGORIES,
            build_device_topology,
            get_preset_clusters,
            select_nodes_in_rect,
        )

        for cat in DEVICE_CATEGORIES:
            nodes = build_device_topology(cat)
            self.assertGreater(len(nodes), 10, f"Topology for {cat} should have LEDs")
            clusters = get_preset_clusters(cat, nodes)
            self.assertGreaterEqual(len(clusters), 3)
            for cname, cset in clusters.items():
                self.assertGreater(len(cset), 0, f"Preset cluster {cname} on {cat} should not be empty")

        # Specific required clusters per Section 3.3
        kb_clusters = get_preset_clusters("keyboard")
        for req in ("All Keys", "WASD + Arrow Keys", "Number Row (1–0)", "Numpad", "Function Row (F1–F12)", "Perimeter Underglow"):
            self.assertIn(req, kb_clusters)
        self.assertTrue({"w", "a", "s", "d", "up", "down", "left", "right"}.issubset(kb_clusters["WASD + Arrow Keys"]))

        mouse_clusters = get_preset_clusters("mouse")
        for req in ("Scroll Wheel", "Palm/Body Logo", "Left/Right Accent Rails"):
            self.assertIn(req, mouse_clusters)

        ctrl_clusters = get_preset_clusters("controller")
        for req in ("Left/Right Thumbstick Halos", "Action Face Buttons", "Top/Bottom Lightbar"):
            self.assertIn(req, ctrl_clusters)

        # Marquee box hit-testing
        kb_nodes = build_device_topology("keyboard")
        all_hit = select_nodes_in_rect(kb_nodes, -10.0, -10.0, 5000.0, 5000.0)
        self.assertEqual(len(all_hit), len(kb_nodes))
        none_hit = select_nodes_in_rect(kb_nodes, -500.0, -500.0, -100.0, -100.0)
        self.assertEqual(len(none_hit), 0)

    def test_all_16_lighting_effects_evaluate_cleanly(self):
        from strop_core.lighting import (
            EFFECT_SPECIFICATIONS,
            EffectRuntimeState,
            PressEvent,
            build_device_topology,
            evaluate_effect,
            get_default_effect_params,
        )

        expected_16 = {
            "breathing", "fire", "ripple", "spectrum_cycling",
            "starlight", "static", "wave", "wheel",
            "reactive", "rain",
            "scanner", "color_pulse", "ripple_line", "gradient_fill",
            "checkerboard", "heatmap",
        }
        self.assertEqual(set(EFFECT_SPECIFICATIONS.keys()), expected_16)

        kb_nodes = build_device_topology("keyboard")
        for eff_id in expected_16:
            rt = EffectRuntimeState()
            # Seed a press event and heatmap count for input-driven effects
            target_node = kb_nodes[10]
            rt.press_events.append(PressEvent(
                node_id=target_node.id,
                row=target_node.row,
                col=target_node.col,
                x_mm=target_node.x_mm,
                y_mm=target_node.y_mm,
                pressed_at=0.1,
                color=(255, 0, 128),
            ))
            rt.active_keys[target_node.id] = rt.press_events[0]
            rt.heatmap_counts[target_node.id] = 6.0

            params = get_default_effect_params(eff_id)
            for t in (0.0, 0.25, 1.1, 4.05):
                frame = evaluate_effect(eff_id, kb_nodes, t, 1.0 / 60.0, params, rt)
                self.assertEqual(len(frame), len(kb_nodes), f"Effect {eff_id} at t={t} did not return all nodes")
                for col in frame.values():
                    self.assertEqual(len(col), 3)
                    self.assertTrue(all(0 <= ch <= 255 for ch in col))

        # Verify Breathing 200ms dark hold at end of cycle
        b_rt = EffectRuntimeState()
        b_params = {"speed_s": 4.0, "color_mode": "Single", "color1": (0, 255, 0)}
        peak_frame = evaluate_effect("breathing", kb_nodes[:2], 2.0, 0.016, b_params, b_rt)
        hold_frame = evaluate_effect("breathing", kb_nodes[:2], 4.1, 0.016, b_params, b_rt)
        self.assertEqual(peak_frame[kb_nodes[0].id], (0, 255, 0))
        self.assertEqual(hold_frame[kb_nodes[0].id], (0, 0, 0))

    def test_compositor_layers_sync_global_controls_and_persistence(self):
        from strop_core.lighting import (
            LightingStudioController,
            load_lighting_settings,
            save_lighting_settings,
        )

        ctrl = LightingStudioController()
        ctrl.sync_all_devices = True
        ctrl.set_Effect_on_selection("keyboard", "static", params={"color1": (0, 100, 255)})

        # Because sync_all_devices is True, mouse and controller also get static (0, 100, 255)
        self.assertEqual(ctrl.device_layers["mouse"][0].effect_id, "static")
        self.assertEqual(ctrl.device_layers["controller"][0].params["color1"], (0, 100, 255))

        # Add a custom WASD overlay layer (Static Red over Static Blue background)
        ctrl.whole_device_mode["keyboard"] = False
        ctrl.set_Effect_on_selection(
            "keyboard",
            "static",
            params={"color1": (255, 0, 0)},
            selected_leds={"w", "a", "s", "d"},
            layer_name="WASD Red",
        )
        frame_full = ctrl.render_device_frame("keyboard", t=1.0)
        self.assertEqual(frame_full["w"], (255, 0, 0))
        self.assertEqual(frame_full["esc"], (0, 100, 255))

        # Master Brightness scaling at 50%
        ctrl.master_brightness = 0.5
        frame_half = ctrl.render_device_frame("keyboard", t=1.0)
        self.assertEqual(frame_half["w"], (128, 0, 0))
        self.assertEqual(frame_half["esc"], (0, 50, 128))

        # Global speed clock advancement
        ctrl.global_speed = 2.5
        t_after, scaled_dt = ctrl.step_clock(dt_wall=0.1)
        self.assertAlmostEqual(scaled_dt, 0.25, places=4)
        self.assertAlmostEqual(t_after, 0.25, places=4)

        # Persistence roundtrip
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg_path = Path(tmpdir) / "lighting_settings.json"
            ctrl.user_swatches[0] = (12, 34, 56)
            self.assertTrue(save_lighting_settings(ctrl, path=cfg_path))

            loaded_ctrl = LightingStudioController()
            self.assertTrue(load_lighting_settings(loaded_ctrl, path=cfg_path))
            self.assertAlmostEqual(loaded_ctrl.master_brightness, 0.5, places=3)
            self.assertAlmostEqual(loaded_ctrl.global_speed, 2.5, places=3)
            self.assertEqual(loaded_ctrl.user_swatches[0], (12, 34, 56))
            self.assertEqual(len(loaded_ctrl.device_layers["keyboard"]), 2)
            self.assertEqual(loaded_ctrl.device_layers["keyboard"][1].target_leds, {"w", "a", "s", "d"})

    def test_hardware_catalog_removed_from_hub(self):
        import strop
        import strop_studio

        self.assertFalse(hasattr(strop, "StropCatalogDialog"))
        self.assertFalse(hasattr(strop.StropHubWindow, "_create_catalog_card"))
        self.assertFalse(hasattr(strop.StropHubWindow, "_open_catalog_browser"))

    def test_profile_switching_clears_previous_layers_and_resets_hardware_matrix(self):
        from strop_core.lighting import (
            LightingStudioController,
            RazerLightingEngine,
            build_device_topology,
        )

        ctrl = LightingStudioController()
        ctrl.whole_device_mode["keyboard"] = False
        ctrl.set_Effect_on_selection(
            "keyboard",
            "scanner",
            selected_leds={"w", "a", "s", "d"},
            layer_name="WASD Scanner",
        )
        self.assertEqual(len(ctrl.device_layers["keyboard"]), 2)

        # Switching back to Whole Device / selecting a new whole-device profile clears all old zone layers
        ctrl.clear_zone_layers("keyboard")
        ctrl.set_Effect_on_selection("keyboard", "rain", selected_leds=None)
        self.assertEqual(len(ctrl.device_layers["keyboard"]), 1)
        self.assertEqual(ctrl.device_layers["keyboard"][0].effect_id, "rain")
        self.assertIsNone(ctrl.device_layers["keyboard"][0].target_leds)

        # Verify 1x21 linear keypad matrix mapping (Tartarus Pro) and 6x22 keyboard matrix reset
        calls = []

        class FakeMatrix:
            def __init__(self, rows, cols):
                self.rows = rows
                self.cols = cols
                self.cells = {}

            def reset(self):
                calls.append("reset")
                self.cells.clear()

            def __setitem__(self, key, val):
                self.cells[key] = val

        class FakeAdv:
            def __init__(self, rows, cols):
                self.rows = rows
                self.cols = cols
                self.matrix = FakeMatrix(rows, cols)

            def draw(self):
                calls.append("draw")

        # 1x21 Keypad (Razer Tartarus Pro)
        adv_kp = FakeAdv(1, 21)
        kp_nodes = build_device_topology("keypad")
        for n in kp_nodes:
            RazerLightingEngine._write_node_to_matrix(adv_kp, n, (0, 255, 0))
        # All 21 linear columns (0..20) should be populated (keys 01-19 -> 0..18, scroll -> 19, spacebar -> 20)
        for col_idx in range(21):
            self.assertEqual(adv_kp.matrix.cells.get((0, col_idx)), (0, 255, 0))

        # 6x22 Keyboard (Razer BlackWidow V3) — underglow must not overwrite key switches
        # and all QWERTY row keys (including tab, w, r, y, i, p) must populate their hardware cells
        from strop_core.lighting import OPENRAZER_KEYBOARD_6X22_MAP

        adv_kb = FakeAdv(6, 22)
        kb_nodes = build_device_topology("keyboard")
        for n in kb_nodes:
            col = (255, 0, 0) if n.zone == "underglow" else (0, 255, 0)
            RazerLightingEngine._write_node_to_matrix(adv_kb, n, col)
        self.assertNotIn((255, 0, 0), adv_kb.matrix.cells.values())
        for key_id in ("tab", "q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "lbrk", "rbrk", "bslash"):
            for mr, mc in OPENRAZER_KEYBOARD_6X22_MAP[key_id]:
                self.assertEqual(
                    adv_kb.matrix.cells.get((mr, mc)),
                    (0, 255, 0),
                    f"Key '{key_id}' cell ({mr}, {mc}) was not lit",
                )


if __name__ == "__main__":
    unittest.main()
