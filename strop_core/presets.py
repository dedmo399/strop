"""
input-remapper-2 preset management, serialization, active profile tracking, and injection.
Pure functional helpers for loading, serializing, saving, and applying hardware presets.
"""

import os
import json
import subprocess
import shutil
import tempfile
import time
import threading
import copy
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from strop_core.logger import get_logger
from strop_core.gamepad import parse_gamepad_button_output
from strop_core.models import DeviceInfo, KeyState, PresetEntry

logger = get_logger("strop.presets")

try:  # dasbus is a hard package dependency, but degrade cleanly if absent.
    from dasbus.error import DBusError
except ImportError:  # pragma: no cover - exercised via tests with a patched import
    class DBusError(Exception):
        """Placeholder used when dasbus is not installed."""

_dbus_lock = threading.Lock()
_dbus_bus = None
_dbus_proxy = None


@dataclass(frozen=True)
class ProfileOperationResult:
    """Outcome of an apply/stop request, including uncertain backend states."""

    status: str
    message: str

    @property
    def success(self) -> bool:
        return self.status in ("applied", "stopped")


def _atomic_write_json(path: Path, data: Any) -> None:
    """Atomically replace a JSON file, preserving the prior file on write failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
        try:
            dir_fd = os.open(str(path.parent), os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def get_config_base() -> Path:
    """Returns the base configuration directory ($XDG_CONFIG_HOME or ~/.config)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg and xdg.strip():
        return Path(xdg.strip()).expanduser()
    return Path.home() / ".config"


def get_strop_config_dir() -> Path:
    """Returns the base strop config directory (~/.config/strop or $XDG_CONFIG_HOME/strop)."""
    p = get_config_base() / "strop"
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_active_profiles_file() -> Path:
    """Returns the path to active_profiles.json."""
    return get_strop_config_dir() / "active_profiles.json"


def get_all_active_profiles() -> Dict[str, str]:
    """Returns a dictionary mapping device names to their currently active preset names."""
    fpath = get_active_profiles_file()
    if not fpath.exists():
        return {}
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                # Read the existing device-name -> preset-name format. Ignore
                # malformed entries rather than propagating them to the UI.
                return {
                    str(device): preset
                    for device, preset in data.items()
                    if isinstance(device, str) and isinstance(preset, str)
                }
    except Exception as e:
        logger.debug(f"Could not read active profiles file: {e}")
    return {}


def get_active_profile(device_name: str) -> Optional[str]:
    """Returns Strop's last confirmed preset for a device, or None.

    This is a local history record. It does not prove that another application
    has not since changed or stopped the input-remapper injection.
    """
    profiles = get_all_active_profiles()
    # Check exact name
    if device_name in profiles:
        return profiles[device_name]
    # Fuzzy match
    normalize = lambda value: " ".join(value.casefold().replace("razer", "").replace("_", " ").split())
    clean_target = normalize(device_name)
    matches = [pname for dname, pname in profiles.items() if normalize(dname) == clean_target]
    return matches[0] if len(matches) == 1 else None


def _normalize_profile_device_name(value: str) -> str:
    return " ".join(value.casefold().replace("razer", "").replace("_", " ").split())


def set_active_profile(
    device_name: str,
    preset_name: str,
    autoload_key: Optional[str] = None,
) -> bool:
    """Records the last confirmed Strop profile; returns whether it persisted."""
    profiles = get_all_active_profiles()
    clean_target = _normalize_profile_device_name(device_name)
    matches = [
        name for name in profiles
        if name != device_name
        and _normalize_profile_device_name(name) == clean_target
    ]
    if len(matches) == 1:
        profiles.pop(matches[0], None)
    profiles[device_name] = preset_name
    try:
        _atomic_write_json(get_active_profiles_file(), profiles)
        _sync_input_remapper_autoload(device_name, preset_name, ir_key=autoload_key)
        return True
    except Exception as e:
        logger.warning(f"Failed to write active profile: {e}")
        return False


def _sync_input_remapper_autoload(
    device_name: str,
    preset_name: Optional[str],
    ir_key: Optional[str] = None,
) -> None:
    """Keep ~/.config/input-remapper-2/config.json autoload mapping synchronized."""
    try:
        ir_cfg_path = _profile_config_dir() / "config.json"
        if not ir_cfg_path.is_file():
            return
        with open(ir_cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return
        autoload = data.get("autoload")
        if autoload is None:
            if not preset_name:
                return
            autoload = {}
            data["autoload"] = autoload
        if not isinstance(autoload, dict):
            return

        target_norm = _normalize_profile_device_name(device_name)
        matching_keys = [
            k for k in list(autoload.keys())
            if isinstance(k, str) and _normalize_profile_device_name(k) == target_norm
        ]

        if preset_name:
            target_key = ir_key or (matching_keys[0] if len(matching_keys) == 1 else device_name)
            if autoload.get(target_key) == preset_name:
                return
            autoload[target_key] = preset_name
        else:
            keys_to_remove = set(matching_keys)
            if ir_key:
                keys_to_remove.add(ir_key)
            keys_to_remove.add(device_name)
            removed = False
            for k in keys_to_remove:
                if k in autoload:
                    autoload.pop(k, None)
                    removed = True
            if not removed:
                return

        _atomic_write_json(ir_cfg_path, data)
    except Exception as e:
        logger.warning(f"Failed to sync autoload to input-remapper config: {e}")


def clear_active_profile(device_name: str, autoload_key: Optional[str] = None) -> bool:
    """Clears the last confirmed profile record; returns whether it persisted."""
    profiles = get_all_active_profiles()
    key = device_name if device_name in profiles else None
    if key is None:
        clean_target = _normalize_profile_device_name(device_name)
        matches = [
            name for name in profiles
            if _normalize_profile_device_name(name) == clean_target
        ]
        if len(matches) == 1:
            key = matches[0]
    if key is not None:
        del profiles[key]
        try:
            _atomic_write_json(get_active_profiles_file(), profiles)
        except Exception as e:
            logger.warning(f"Could not clear active profile: {e}")
            return False
    _sync_input_remapper_autoload(device_name, None, ir_key=autoload_key)
    return True


def get_presets_base_dir() -> Path:
    """Returns the base input-remapper-2 presets directory ($XDG_CONFIG_HOME or ~/.config)."""
    base = get_config_base()
    p1 = base / "input-remapper-2" / "presets"
    p2 = base / "input-remapper" / "presets"
    if p1.exists():
        return p1
    if p2.exists():
        return p2
    p1.mkdir(parents=True, exist_ok=True)
    return p1


def sanitize_filename(name: str) -> str:
    """Sanitizes names to prevent path traversal or invalid characters."""
    if not name:
        return ""
    clean = Path(name).name.replace(".json", "").strip()
    clean = clean.replace("/", "").replace("\\", "").replace("\0", "").strip(" .")
    return clean


def get_device_presets_dir(
    device_name: str,
    preferred_dir_name: Optional[str] = None,
) -> Path:
    """Returns the specific device preset subfolder, resolving existing directories or creating clean one."""
    base = get_presets_base_dir()
    clean_dev_input = sanitize_filename(device_name) or "Razer Device"
    # 1. Exact match
    pdir = base / clean_dev_input
    if pdir.exists():
        return pdir
    if preferred_dir_name:
        clean_pref = sanitize_filename(preferred_dir_name)
        if clean_pref and (base / clean_pref).exists():
            return base / clean_pref
    # 2. Match clean name
    from strop_core.device import clean_device_display_name
    clean_name = sanitize_filename(clean_device_display_name(device_name)) or clean_dev_input
    pdir_clean = base / clean_name
    if pdir_clean.exists():
        return pdir_clean
    # 3. Fuzzy search existing directories
    clean_target = clean_dev_input.lower().replace("razer", "").replace("_", " ").strip()
    if base.exists():
        for sub in base.iterdir():
            if sub.is_dir():
                clean_sub = sub.name.lower().replace("razer", "").replace("_", " ").strip()
                if clean_target and (clean_target in clean_sub or clean_sub in clean_target):
                    return sub
    # 4. Default: Create preferred or clean path
    default_dir_name = sanitize_filename(preferred_dir_name) if preferred_dir_name else ""
    target = base / (default_dir_name or clean_name)
    target.mkdir(parents=True, exist_ok=True)
    return target


def list_device_presets(device_name: str) -> List[str]:
    """Returns a sorted list of preset names (without .json) for a device."""
    pdir = get_device_presets_dir(device_name)
    if not pdir.exists():
        return []
    presets = []
    for f in pdir.glob("*.json"):
        presets.append(f.stem)
    return sorted(presets, key=lambda s: s.lower())


def serialize_preset_data(
    state: Dict[str, KeyState],
    device_info: DeviceInfo,
) -> List[PresetEntry]:
    """
    Serializes runtime KeyState dictionary into pure input-remapper JSON entries.
    Handles scancode-to-hash resolution for multi-node devices (Tartarus switches, matrix, etc.).
    """
    dev_hash = device_info.get("hash", "")
    key_to_hash = device_info.get("key_to_hash", {})
    rel_to_hash = device_info.get("rel_to_hash", {})
    preset_data: List[PresetEntry] = []

    for kid, s in state.items():
        out_sym = (s.get("output") or "").strip()
        custom_name = (s.get("custom_name") or "").strip()
        output_event = parse_gamepad_button_output(out_sym)
        output_type = s.get("output_type")
        output_code = s.get("output_code")
        if output_event:
            output_type, output_code = output_event
            out_sym = ""
        if not out_sym and (output_type is None or output_code is None):
            continue

        from strop_core.macros import normalize_macro_to_input_remapper
        out_sym = normalize_macro_to_input_remapper(out_sym)

        target_uinput = s.get("target") or "keyboard"
        mapping_type = "analog" if s.get("mapping_type") == "analog" else "key_macro"

        # Determine origin_hash and input_combination for this key/event
        input_type = int(s.get("input_type", 1))
        if "combo" in s and s["combo"]:
            input_comb = [
                {
                    "type": 1,
                    "code": c_code,
                    "origin_hash": (
                        key_to_hash.get(c_code)
                        or (s.get("origin_hash") if c_code == s.get("code") else None)
                        or dev_hash
                    ),
                }
                for c_code in s["combo"]
            ]
        elif s.get("code") is None:
            logger.warning(f"Skipping preset mapping for {kid!r}: missing evdev code.")
            continue
        elif input_type == 2:
            code_val = int(s["code"])
            key_hash = s.get("origin_hash") or rel_to_hash.get(code_val) or dev_hash
            rel_item: Dict[str, Any] = {"type": 2, "code": code_val, "origin_hash": key_hash}
            if s.get("analog_threshold") is not None:
                rel_item["analog_threshold"] = int(s["analog_threshold"])
            input_comb = [rel_item]
        else:
            code_val = int(s["code"])
            key_hash = s.get("origin_hash") or key_to_hash.get(code_val) or dev_hash
            input_comb = [{"type": 1, "code": code_val, "origin_hash": key_hash}]

        entry_dict: PresetEntry = {
            "input_combination": input_comb,
            "target_uinput": target_uinput,
            "output_symbol": out_sym,
            "name": s["name"],
            "mapping_type": mapping_type
        }
        if output_type is not None and output_code is not None:
            entry_dict["output_type"] = output_type
            entry_dict["output_code"] = output_code
        if custom_name:
            entry_dict["custom_name"] = custom_name

        preset_data.append(entry_dict)

    return preset_data


def validate_preset_data(data: Any) -> Optional[str]:
    """Return a useful error for malformed or backend-incompatible preset JSON."""
    if not isinstance(data, list):
        return "Preset must be a JSON list."

    # These are input-remapper's KnownUinput and MappingType values. Keep the
    # check independent of its GUI imports so headless validation cannot load
    # GTK 3 into Strop's GTK 4 process.
    valid_targets = {"keyboard", "mouse", "gamepad", "keyboard + mouse"}
    valid_mapping_types = {"key_macro", "analog"}

    for index, entry in enumerate(data):
        prefix = f"Mapping {index + 1}"
        if not isinstance(entry, dict):
            return f"{prefix} must be an object."
        combination = entry.get("input_combination")
        if not isinstance(combination, list) or not combination:
            return f"{prefix} must have a non-empty input_combination list."
        for input_index, input_item in enumerate(combination):
            input_prefix = f"{prefix}, input {input_index + 1}"
            if not isinstance(input_item, dict):
                return f"{input_prefix} must be an object."
            for field in ("type", "code"):
                value = input_item.get(field)
                if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                    return f"{input_prefix} must have a non-negative integer {field}."
            origin_hash = input_item.get("origin_hash")
            if origin_hash is not None and not isinstance(origin_hash, str):
                return f"{input_prefix} origin_hash must be text or null."
            threshold = input_item.get("analog_threshold")
            if threshold is not None and (not isinstance(threshold, int) or isinstance(threshold, bool)):
                return f"{input_prefix} analog_threshold must be an integer or null."

        target = entry.get("target_uinput")
        if not isinstance(target, str) or target not in valid_targets:
            return f"{prefix} has an unsupported target_uinput."
        output = entry.get("output_symbol")
        output_type = entry.get("output_type")
        output_code = entry.get("output_code")
        if output is not None and not isinstance(output, str):
            return f"{prefix} output_symbol must be text or null."
        if output_type is not None and (not isinstance(output_type, int) or isinstance(output_type, bool)):
            return f"{prefix} output_type must be an integer."
        if output_code is not None and (not isinstance(output_code, int) or isinstance(output_code, bool)):
            return f"{prefix} output_code must be an integer."
        if not (isinstance(output, str) and output.strip()) and (output_type is None or output_code is None):
            return f"{prefix} must define an output_symbol or both output_type and output_code."
        if isinstance(output, str) and "gamepad(" in output and not parse_gamepad_button_output(output):
            return f"{prefix} uses an unsupported gamepad macro; this backend supports gamepad buttons, not digital-to-axis or combined-button macro outputs."
        mapping_type = entry.get("mapping_type")
        if mapping_type is not None and (
            not isinstance(mapping_type, str) or mapping_type not in valid_mapping_types
        ):
            return f"{prefix} has an unsupported mapping_type."
        for field in ("name", "custom_name"):
            value = entry.get(field)
            if value is not None and not isinstance(value, str):
                return f"{prefix} {field} must be text or null."
    return None


def save_device_preset(
    device_name: str,
    preset_name: str,
    state: Dict[str, KeyState],
    device_info: DeviceInfo,
    preserved_entries: Optional[List[PresetEntry]] = None,
) -> Optional[Path]:
    """Serializes and saves a preset file directly to disk. Returns saved file Path."""
    clean_pname = sanitize_filename(preset_name)
    if not clean_pname:
        logger.error("Preset name cannot be empty or invalid.")
        return None

    try:
        preset_data = serialize_preset_data(state, device_info)
        if preserved_entries:
            preset_data.extend(copy.deepcopy(preserved_entries))
    except Exception as e:
        logger.error(f"Could not serialize preset '{clean_pname}': {e}")
        return None
    validation_error = validate_preset_data(preset_data)
    if validation_error:
        logger.error(f"Could not save preset '{clean_pname}': {validation_error}")
        return None
    raw_name = device_info.get("raw_name") if isinstance(device_info, dict) else None
    if raw_name:
        try:
            target_dir = get_device_presets_dir(device_name, preferred_dir_name=raw_name)
        except TypeError:
            target_dir = get_device_presets_dir(device_name)
    else:
        target_dir = get_device_presets_dir(device_name)
    save_file = target_dir / f"{clean_pname}.json"
    try:
        _atomic_write_json(save_file, preset_data)
        logger.info(f"Saved preset '{clean_pname}' to {save_file}")
        return save_file
    except Exception as e:
        logger.error(f"Failed to save preset '{clean_pname}': {e}")
        return None



def load_preset_file(path: Path) -> Optional[List[PresetEntry]]:
    """Reads and parses an input-remapper JSON preset file."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            validation_error = validate_preset_data(data)
            if validation_error is None:
                return data
            logger.error(f"Preset {path} is invalid: {validation_error}")
    except Exception as e:
        logger.error(f"Failed to load preset {path}: {e}")
    return None


def _profile_config_dir() -> Path:
    return get_presets_base_dir().parent


_device_keys_lock = threading.Lock()
_DEVICE_KEYS_CACHE: Tuple[float, List[str]] = (0.0, [])


def invalidate_device_keys_cache() -> None:
    """Clears the cached input-remapper device enumeration."""
    global _DEVICE_KEYS_CACHE
    with _device_keys_lock:
        _DEVICE_KEYS_CACHE = (0.0, [])


def _list_input_remapper_devices(ctrl_bin: str, force_refresh: bool = False) -> List[str]:
    global _DEVICE_KEYS_CACHE
    now = time.monotonic()
    with _device_keys_lock:
        last_time, cached_keys = _DEVICE_KEYS_CACHE
        if not force_refresh and cached_keys and (now - last_time < 30.0):
            return list(cached_keys)

    result = subprocess.run(
        [ctrl_bin, "--list-devices"], capture_output=True, text=True, timeout=3.0,
        env=dict(os.environ, PYTHONWARNINGS="ignore"),
    )
    if result.returncode != 0:
        with _device_keys_lock:
            _, latest_cached = _DEVICE_KEYS_CACHE
            if latest_cached:
                return list(latest_cached)
        detail = (result.stderr or result.stdout or "Unable to enumerate input-remapper devices").strip()
        raise RuntimeError(detail[-500:])
    keys = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    with _device_keys_lock:
        _DEVICE_KEYS_CACHE = (time.monotonic(), keys)
    return list(keys)


def _resolve_input_remapper_device(device_name: str, group_keys: List[str]) -> Optional[str]:
    """Resolve a Strop device name to one exact input-remapper group key."""
    candidates = [device_name]
    if not device_name.startswith("Razer Razer"):
        candidates.append(f"Razer Razer {device_name.replace('Razer ', '')}")
    if not device_name.startswith("Razer "):
        candidates.append(f"Razer {device_name}")

    for candidate in candidates:
        exact = [key for key in group_keys if key.casefold() == candidate.casefold()]
        if len(exact) == 1:
            return exact[0]

    normalize = lambda value: "".join(char.casefold() for char in value if char.isalnum())
    candidate_keys = {normalize(candidate) for candidate in candidates}
    matches = [key for key in group_keys if normalize(key) in candidate_keys]
    return matches[0] if len(matches) == 1 else None


def _get_system_bus():
    """Return a cached dasbus system bus connection (thread-safe)."""
    global _dbus_bus
    with _dbus_lock:
        if _dbus_bus is None:
            from dasbus.connection import SystemMessageBus
            _dbus_bus = SystemMessageBus()
        return _dbus_bus


def _reset_dbus_cache() -> None:
    """Drop cached bus/proxy so the next call reconnects (e.g. after DBusError)."""
    global _dbus_bus, _dbus_proxy
    with _dbus_lock:
        old_bus = _dbus_bus
        _dbus_bus = None
        _dbus_proxy = None
    if old_bus is not None and hasattr(old_bus, "disconnect"):
        try:
            old_bus.disconnect()
        except Exception:
            pass


def _get_input_remapper_proxy():
    """Return a cached dasbus proxy for input-remapper's Control service."""
    global _dbus_proxy
    bus = _get_system_bus()
    with _dbus_lock:
        if _dbus_proxy is None:
            from dasbus.identifier import DBusServiceIdentifier
            service = DBusServiceIdentifier(
                namespace=("inputremapper", "Control"),
                message_bus=bus,
            )
            _dbus_proxy = service.get_proxy()
        return _dbus_proxy


def _get_input_remapper_state(group_key: str) -> str:
    """Read injector state from input-remapper's D-Bus API."""
    try:
        daemon = _get_input_remapper_proxy()
        raw_state = daemon.get_state(group_key, timeout=2000)
    except DBusError:
        _reset_dbus_cache()
        raise
    state = getattr(raw_state, "value", raw_state)
    return str(state).upper().rsplit(".", 1)[-1]


def _wait_for_injector_state(group_key: str, expected: set, timeout: float = 4.0) -> Optional[str]:
    """Poll D-Bus state briefly after a command; call only from a worker thread."""
    deadline = time.monotonic() + timeout
    last_state = None
    while time.monotonic() < deadline:
        try:
            last_state = _get_input_remapper_state(group_key)
        except Exception as exc:
            logger.warning(f"Could not query input-remapper state: {exc}")
            return None
        if last_state in expected:
            return last_state
        if last_state in {"FAILED", "NO_GRAB", "UPGRADE_EVDEV"}:
            return last_state
        time.sleep(0.1)
    return last_state


def get_injection_state(device_name: str) -> str:
    """Return running, stopped, or unknown using input-remapper's D-Bus state."""
    # Fast path: query D-Bus directly for candidate group names to avoid subprocess overhead
    clean = device_name.replace("Razer ", "")
    candidates = [
        device_name,
        f"Razer {device_name}" if not device_name.startswith("Razer ") else device_name,
        f"Razer Razer {clean}",
    ]
    seen = set()
    unique_candidates = [c for c in candidates if not (c in seen or seen.add(c))]

    try:
        daemon = _get_input_remapper_proxy()
        for cand in unique_candidates:
            try:
                raw_state = daemon.get_state(cand, timeout=1000)
            except DBusError as exc:
                logger.debug(f"input-remapper D-Bus state query failed for {cand!r}: {exc}")
                _reset_dbus_cache()
                break
            state = getattr(raw_state, "value", raw_state)
            state_str = str(state).upper().rsplit(".", 1)[-1]
            if state_str == "RUNNING":
                return "running"
            if state_str == "STARTING":
                return "starting"
            if state_str in {"FAILED", "NO_GRAB", "UPGRADE_EVDEV"}:
                return "failed"
            if state_str == "STOPPED":
                return "stopped"
    except Exception as exc:
        logger.debug(f"input-remapper D-Bus unavailable ({type(exc).__name__}): {exc}")

    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return "unknown"
    try:
        keys = _list_input_remapper_devices(ctrl_bin)
        group_key = _resolve_input_remapper_device(device_name, keys)
        if not group_key:
            return "unknown"
        state = _get_input_remapper_state(group_key)
        if state == "STARTING":
            return "starting"
        if state == "RUNNING":
            return "running"
        if state in {"FAILED", "NO_GRAB", "UPGRADE_EVDEV"}:
            return "failed"
        if state in {"STOPPED", "UNKNOWN"}:
            return "stopped"
    except Exception as exc:
        logger.debug(f"Could not query injector state for {device_name}: {exc}")
    return "unknown"


def run_profile_operation_async(
    operation: str,
    device_name: str,
    callback,
    schedule_on_main,
    preset_name: Optional[str] = None,
) -> threading.Thread:
    """Run apply/stop outside GTK's thread and deliver the result on its main loop."""
    def worker():
        try:
            if operation == "apply" and preset_name:
                result = apply_profile(device_name, preset_name)
            elif operation == "stop":
                result = stop_profile(device_name)
            else:
                result = ProfileOperationResult("failed", "Invalid profile operation.")
        except Exception as exc:
            logger.exception(f"Profile operation failed unexpectedly: {exc}")
            result = ProfileOperationResult("failed", str(exc))

        def deliver():
            callback(result)
            return False

        schedule_on_main(deliver)

    worker_thread = threading.Thread(target=worker, name="strop-profile-operation", daemon=True)
    worker_thread.start()
    return worker_thread


def check_profile_state_async(device_name: str, callback, schedule_on_main) -> threading.Thread:
    """Query backend injection state off-thread and deliver running/stopped/unknown."""
    def worker():
        state = get_injection_state(device_name)

        def deliver():
            callback(state)
            return False

        schedule_on_main(deliver)

    worker_thread = threading.Thread(target=worker, name="strop-profile-state", daemon=True)
    worker_thread.start()
    return worker_thread


def apply_profile(device_name: str, preset_name: str) -> ProfileOperationResult:
    """Apply a valid saved preset and verify that its injector reaches RUNNING."""
    clean_preset = sanitize_filename(preset_name)
    if not clean_preset:
        return ProfileOperationResult("failed", "Preset name cannot be empty or invalid.")

    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return ProfileOperationResult("failed", "input-remapper-control is not installed.")

    preset_path = get_device_presets_dir(device_name) / f"{clean_preset}.json"
    if load_preset_file(preset_path) is None:
        return ProfileOperationResult("failed", f"Preset file is missing or invalid: {preset_path.name}")

    try:
        group_keys = _list_input_remapper_devices(ctrl_bin)
        group_key = _resolve_input_remapper_device(device_name, group_keys)
        if not group_key:
            try:
                group_keys = _list_input_remapper_devices(ctrl_bin, force_refresh=True)
            except TypeError:
                group_keys = _list_input_remapper_devices(ctrl_bin)
            group_key = _resolve_input_remapper_device(device_name, group_keys)
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not enumerate input-remapper devices: {exc}")
    if not group_key:
        return ProfileOperationResult(
            "failed",
            f"No unique input-remapper device matched {device_name}; check that it is connected and visible to input-remapper.",
        )

    config_dir = _profile_config_dir()
    if not (config_dir / "config.json").is_file():
        return ProfileOperationResult("failed", f"input-remapper configuration is missing from {config_dir}.")

    cmd = [
        ctrl_bin, "--config-dir", str(config_dir), "--command", "start",
        "--device", group_key, "--preset", clean_preset,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3.0,
            env=dict(os.environ, PYTHONWARNINGS="ignore"),
        )
    except subprocess.TimeoutExpired:
        return ProfileOperationResult(
            "unknown",
            "Apply timed out; the backend may have started the injection, but Strop could not confirm it. Check the input-remapper daemon and device connection, then refresh the profile state.",
        )
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not run input-remapper-control: {exc}")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Backend rejected the apply request").strip()
        return ProfileOperationResult("failed", detail[-500:])

    state = _wait_for_injector_state(group_key, {"RUNNING"})
    if state != "RUNNING":
        if state in {"FAILED", "NO_GRAB", "UPGRADE_EVDEV", "STOPPED", "UNKNOWN"}:
            return ProfileOperationResult("failed", f"input-remapper did not start the injection (state: {state}).")
        return ProfileOperationResult(
            "unknown",
            "Apply was accepted, but Strop could not confirm that the injection is running. Check the input-remapper daemon and device connection, then refresh the profile state.",
        )

    if not set_active_profile(device_name, clean_preset, autoload_key=group_key):
        return ProfileOperationResult("applied", f"Injection is running with {clean_preset}, but Strop could not save its last-confirmed profile record.")
    return ProfileOperationResult("applied", f"input-remapper reports an injection running for {device_name}; Strop last applied {clean_preset}.")


def stop_profile(device_name: str) -> ProfileOperationResult:
    """Stop an injection and clear its local record only after backend confirmation."""
    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return ProfileOperationResult("failed", "input-remapper-control is not installed; Strop could not confirm the profile stopped.")

    try:
        group_keys = _list_input_remapper_devices(ctrl_bin)
        group_key = _resolve_input_remapper_device(device_name, group_keys)
        if not group_key:
            try:
                group_keys = _list_input_remapper_devices(ctrl_bin, force_refresh=True)
            except TypeError:
                group_keys = _list_input_remapper_devices(ctrl_bin)
            group_key = _resolve_input_remapper_device(device_name, group_keys)
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not enumerate input-remapper devices: {exc}")
    if not group_key:
        return ProfileOperationResult(
            "failed",
            f"No unique input-remapper device matched {device_name}; check that it is connected and visible to input-remapper.",
        )

    try:
        result = subprocess.run(
            [ctrl_bin, "--command", "stop", "--device", group_key],
            capture_output=True, text=True, timeout=3.0,
            env=dict(os.environ, PYTHONWARNINGS="ignore"),
        )
    except subprocess.TimeoutExpired:
        return ProfileOperationResult(
            "unknown",
            "Stop timed out; Strop could not confirm whether the injection stopped. Check the input-remapper daemon and device connection, then refresh the profile state.",
        )
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not run input-remapper-control: {exc}")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Backend rejected the stop request").strip()
        return ProfileOperationResult("failed", detail[-500:])

    state = _wait_for_injector_state(group_key, {"STOPPED", "UNKNOWN"})
    if state in {"FAILED", "NO_GRAB", "UPGRADE_EVDEV"}:
        return ProfileOperationResult(
            "failed",
            f"input-remapper could not confirm a clean stop (state: {state}); the last confirmed profile is retained.",
        )
    if state not in {"STOPPED", "UNKNOWN"}:
        return ProfileOperationResult(
            "unknown",
            "Stop was accepted, but Strop could not confirm that injection ended. Check the input-remapper daemon and device connection, then refresh the profile state.",
        )

    if not clear_active_profile(device_name, autoload_key=group_key):
        return ProfileOperationResult("stopped", "Injection stopped, but Strop could not clear its last-confirmed profile record.")
    return ProfileOperationResult("stopped", f"input-remapper reports no injection running for {device_name}.")

def _is_dbus_daemon_active() -> bool:
    try:
        bus = _get_system_bus()
        dbus_proxy = bus.get_proxy("org.freedesktop.DBus", "/org/freedesktop/DBus")
        return "inputremapper.Control" in dbus_proxy.ListNames(timeout=1000)
    except DBusError:
        _reset_dbus_cache()
        return False
    except Exception:
        return False


def check_daemon_status() -> Tuple[str, str]:
    """
    Checks if input-remapper is installed and its system daemon is currently running.
    Returns: (status: 'running' | 'stopped' | 'not_installed', message: str)
    """
    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return "not_installed", "input-remapper is not installed. Install via your package manager."

    # Direct D-Bus check avoiding subprocess spawn and daemon log spam
    if _is_dbus_daemon_active():
        return "running", "input-remapper daemon is active."

    try:
        sub_env = dict(os.environ, PYTHONWARNINGS="ignore")
        res = subprocess.run([ctrl_bin, "--command", "hello"], capture_output=True, text=True, timeout=0.8, env=sub_env)
        if res.returncode != 0:
            return "stopped", "input-remapper daemon is not running. Start with: sudo systemctl start input-remapper"
        return "running", "input-remapper daemon is active."
    except Exception as e:
        return "unknown", f"Daemon status check error: {e}"
