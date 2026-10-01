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
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from strop_core.logger import get_logger

logger = get_logger("strop.presets")


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


def get_strop_config_dir() -> Path:
    """Returns the base strop config directory (~/.config/strop)."""
    p = Path.home() / ".config" / "strop"
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
    clean_target = device_name.lower().replace("razer", "").replace("_", " ").strip()
    matches = []
    for dname, pname in profiles.items():
        clean_d = dname.lower().replace("razer", "").replace("_", " ").strip()
        if clean_target and (clean_target in clean_d or clean_d in clean_target):
            matches.append(pname)
    return matches[0] if len(matches) == 1 else None


def set_active_profile(device_name: str, preset_name: str) -> bool:
    """Records the last confirmed Strop profile; returns whether it persisted."""
    profiles = get_all_active_profiles()
    matches = [
        name for name in profiles
        if name != device_name
        and name.lower().replace("razer", "").replace("_", " ").strip()
        == device_name.lower().replace("razer", "").replace("_", " ").strip()
    ]
    if len(matches) == 1:
        profiles.pop(matches[0], None)
    profiles[device_name] = preset_name
    try:
        _atomic_write_json(get_active_profiles_file(), profiles)
        return True
    except Exception as e:
        logger.warning(f"Failed to write active profile: {e}")
        return False


def clear_active_profile(device_name: str) -> bool:
    """Clears the last confirmed profile record; returns whether it persisted."""
    profiles = get_all_active_profiles()
    key = device_name if device_name in profiles else None
    if key is None:
        clean_target = device_name.lower().replace("razer", "").replace("_", " ").strip()
        matches = [
            name for name in profiles
            if name.lower().replace("razer", "").replace("_", " ").strip() == clean_target
        ]
        if len(matches) == 1:
            key = matches[0]
    if key is not None:
        del profiles[key]
        try:
            _atomic_write_json(get_active_profiles_file(), profiles)
            return True
        except Exception as e:
            logger.warning(f"Could not clear active profile: {e}")
            return False
    return True


def get_presets_base_dir() -> Path:
    """Returns the base input-remapper-2 presets directory (~/.config/input-remapper-2/presets)."""
    p1 = Path.home() / ".config" / "input-remapper-2" / "presets"
    p2 = Path.home() / ".config" / "input-remapper" / "presets"
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


def get_device_presets_dir(device_name: str) -> Path:
    """Returns the specific device preset subfolder, resolving existing directories or creating clean one."""
    base = get_presets_base_dir()
    clean_dev_input = sanitize_filename(device_name) or "Razer Device"
    # 1. Exact match
    pdir = base / clean_dev_input
    if pdir.exists():
        return pdir
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
    # 4. Default: Create clean path
    target = base / clean_name
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
    state: Dict[str, Dict[str, Any]],
    device_info: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Serializes runtime KeyState dictionary into pure input-remapper JSON entries.
    Handles scancode-to-hash resolution for multi-node devices (Tartarus switches, matrix, etc.).
    """
    dev_hash = device_info.get("hash", "")
    key_to_hash = device_info.get("key_to_hash", {})
    preset_data = []

    for kid, s in state.items():
        out_sym = (s.get("output") or "").strip()
        custom_name = (s.get("custom_name") or "").strip()
        if not out_sym and not custom_name:
            continue

        from strop_core.macros import normalize_macro_to_input_remapper
        out_sym = normalize_macro_to_input_remapper(out_sym)

        target_uinput = s.get("target") or "keyboard"
        if target_uinput == "analog" or s.get("mapping_type") == "analog":
            mapping_type = "analog"
        else:
            mapping_type = "key_macro"

        # Determine origin_hash for this key
        key_hash = s.get("origin_hash")
        if not key_hash and s.get("code") in key_to_hash:
            key_hash = key_to_hash[s["code"]]
        if not key_hash:
            key_hash = dev_hash

        if "combo" in s and s["combo"]:
            input_comb = [
                {
                    "type": 1,
                    "code": c_code,
                    "origin_hash": s.get("origin_hash") or key_to_hash.get(c_code, dev_hash)
                }
                for c_code in s["combo"]
            ]
        else:
            code_val = s.get("code") if s.get("code") is not None else 0
            input_comb = [{"type": 1 if s.get("code") is not None else 2, "code": code_val, "origin_hash": key_hash}]

        entry_dict: Dict[str, Any] = {
            "input_combination": input_comb,
            "target_uinput": target_uinput,
            "output_symbol": out_sym,
            "name": s["name"],
            "mapping_type": mapping_type
        }
        if custom_name:
            entry_dict["custom_name"] = custom_name

        preset_data.append(entry_dict)

    return preset_data


def save_device_preset(
    device_name: str,
    preset_name: str,
    state: Dict[str, Dict[str, Any]],
    device_info: Dict[str, Any],
) -> Optional[Path]:
    """Serializes and saves a preset file directly to disk. Returns saved file Path."""
    clean_pname = sanitize_filename(preset_name)
    if not clean_pname:
        logger.error("Preset name cannot be empty or invalid.")
        return None

    preset_data = serialize_preset_data(state, device_info)
    target_dir = get_device_presets_dir(device_name)
    save_file = target_dir / f"{clean_pname}.json"
    try:
        _atomic_write_json(save_file, preset_data)
        logger.info(f"Saved preset '{clean_pname}' to {save_file}")
        return save_file
    except Exception as e:
        logger.error(f"Failed to save preset '{clean_pname}': {e}")
        return None



def load_preset_file(path: Path) -> Optional[List[Dict[str, Any]]]:
    """Reads and parses an input-remapper JSON preset file."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list) and all(
                isinstance(entry, dict)
                and isinstance(entry.get("input_combination"), list)
                and isinstance(entry.get("output_symbol"), str)
                for entry in data
            ):
                return data
            logger.error(f"Preset {path} has an invalid structure")
    except Exception as e:
        logger.error(f"Failed to load preset {path}: {e}")
    return None


def _profile_config_dir() -> Path:
    return get_presets_base_dir().parent


def _list_input_remapper_devices(ctrl_bin: str) -> List[str]:
    result = subprocess.run(
        [ctrl_bin, "--list-devices"], capture_output=True, text=True, timeout=3.0,
        env=dict(os.environ, PYTHONWARNINGS="ignore"),
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Unable to enumerate input-remapper devices").strip()
        raise RuntimeError(detail[-500:])
    return [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]


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


def _get_input_remapper_state(group_key: str) -> str:
    """Read injector state from input-remapper's D-Bus API."""
    from pydbus import SystemBus

    daemon = SystemBus().get("inputremapper.Control")
    raw_state = daemon.get_state(group_key, timeout=2)
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
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not enumerate input-remapper devices: {exc}")
    group_key = _resolve_input_remapper_device(device_name, group_keys)
    if not group_key:
        return ProfileOperationResult("failed", f"No unambiguous input-remapper device matched {device_name}.")

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
        return ProfileOperationResult("unknown", "Apply timed out; the backend may have started the injection, but Strop could not confirm it.")
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not run input-remapper-control: {exc}")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Backend rejected the apply request").strip()
        return ProfileOperationResult("failed", detail[-500:])

    state = _wait_for_injector_state(group_key, {"RUNNING"})
    if state != "RUNNING":
        if state in {"FAILED", "NO_GRAB", "UPGRADE_EVDEV", "STOPPED", "UNKNOWN"}:
            return ProfileOperationResult("failed", f"input-remapper did not start the injection (state: {state}).")
        return ProfileOperationResult("unknown", "Apply was accepted, but Strop could not confirm that the injection is running.")

    if not set_active_profile(device_name, clean_preset):
        return ProfileOperationResult("applied", f"Injection is running with {clean_preset}, but Strop could not save its last-confirmed profile record.")
    return ProfileOperationResult("applied", f"input-remapper reports an injection running for {device_name}; Strop last applied {clean_preset}.")


def stop_profile(device_name: str) -> ProfileOperationResult:
    """Stop an injection and clear its local record only after backend confirmation."""
    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return ProfileOperationResult("failed", "input-remapper-control is not installed; Strop could not confirm the profile stopped.")

    try:
        group_keys = _list_input_remapper_devices(ctrl_bin)
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not enumerate input-remapper devices: {exc}")
    group_key = _resolve_input_remapper_device(device_name, group_keys)
    if not group_key:
        return ProfileOperationResult("failed", f"No unambiguous input-remapper device matched {device_name}.")

    try:
        result = subprocess.run(
            [ctrl_bin, "--command", "stop", "--device", group_key],
            capture_output=True, text=True, timeout=3.0,
            env=dict(os.environ, PYTHONWARNINGS="ignore"),
        )
    except subprocess.TimeoutExpired:
        return ProfileOperationResult("unknown", "Stop timed out; Strop could not confirm whether the injection stopped.")
    except Exception as exc:
        return ProfileOperationResult("failed", f"Could not run input-remapper-control: {exc}")

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "Backend rejected the stop request").strip()
        return ProfileOperationResult("failed", detail[-500:])

    state = _wait_for_injector_state(group_key, {"STOPPED", "UNKNOWN", "FAILED", "NO_GRAB", "UPGRADE_EVDEV"})
    if state not in {"STOPPED", "UNKNOWN", "FAILED", "NO_GRAB", "UPGRADE_EVDEV"}:
        return ProfileOperationResult("unknown", "Stop was accepted, but Strop could not confirm that injection ended.")

    if not clear_active_profile(device_name):
        return ProfileOperationResult("stopped", "Injection stopped, but Strop could not clear its last-confirmed profile record.")
    return ProfileOperationResult("stopped", f"input-remapper reports no injection running for {device_name}.")

def check_daemon_status() -> Tuple[str, str]:
    """
    Checks if input-remapper is installed and its system daemon is currently running.
    Returns: (status: 'running' | 'stopped' | 'not_installed', message: str)
    """
    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return "not_installed", "input-remapper is not installed. Install via your package manager."

    try:
        sub_env = dict(os.environ, PYTHONWARNINGS="ignore")
        res = subprocess.run([ctrl_bin, "--command", "hello"], capture_output=True, text=True, timeout=0.8, env=sub_env)
        if res.returncode != 0:
            return "stopped", "input-remapper daemon is not running. Start with: sudo systemctl start input-remapper"
        return "running", "input-remapper daemon is active."
    except Exception as e:
        return "unknown", f"Daemon status check error: {e}"
