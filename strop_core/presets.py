"""
input-remapper-2 preset management, serialization, active profile tracking, and injection.
Pure functional helpers for loading, serializing, saving, and applying hardware presets.
"""

import os
import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from strop_core.logger import get_logger

logger = get_logger("strop.presets")


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
                return data
    except Exception as e:
        logger.debug(f"Could not read active profiles file: {e}")
    return {}


def get_active_profile(device_name: str) -> Optional[str]:
    """Returns the currently active preset name for a given device, or None."""
    profiles = get_all_active_profiles()
    # Check exact name
    if device_name in profiles:
        return profiles[device_name]
    # Fuzzy match
    clean_target = device_name.lower().replace("razer", "").replace("_", " ").strip()
    for dname, pname in profiles.items():
        clean_d = dname.lower().replace("razer", "").replace("_", " ").strip()
        if clean_target and (clean_target in clean_d or clean_d in clean_target):
            return pname
    return None


def set_active_profile(device_name: str, preset_name: str) -> None:
    """Records the active profile for a device into ~/.config/strop/active_profiles.json."""
    profiles = get_all_active_profiles()
    profiles[device_name] = preset_name
    fpath = get_active_profiles_file()
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to write active profile: {e}")


def clear_active_profile(device_name: str) -> None:
    """Clears the active profile record for a device."""
    profiles = get_all_active_profiles()
    if device_name in profiles:
        del profiles[device_name]
        try:
            with open(get_active_profiles_file(), "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not clear active profile: {e}")


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
        with open(save_file, "w", encoding="utf-8") as f:
            json.dump(preset_data, f, indent=2)
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
            if isinstance(data, list):
                return data
    except Exception as e:
        logger.error(f"Failed to load preset {path}: {e}")
    return None


def apply_profile(device_name: str, preset_name: str) -> Tuple[bool, str]:
    """
    Applies a preset to the hardware via input-remapper-control and records it as active upon confirmation.
    Returns (success: bool, message: str) without blocking the UI main loop.
    """
    clean_preset = sanitize_filename(preset_name)
    if not clean_preset:
        return False, "Preset name cannot be empty or invalid."

    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return False, "input-remapper-control is not installed. Install input-remapper to apply profiles to hardware."

    # Locate config directory
    config_dir = None
    if (Path.home() / ".config" / "input-remapper-2").exists():
        config_dir = str(Path.home() / ".config" / "input-remapper-2")
    elif (Path.home() / ".config" / "input-remapper").exists():
        config_dir = str(Path.home() / ".config" / "input-remapper")

    # Find best matching device name candidate for input-remapper daemon
    dev_candidates = [device_name]
    if not device_name.startswith("Razer Razer"):
        dev_candidates.append(f"Razer Razer {device_name.replace('Razer ', '')}")
    if not device_name.startswith("Razer "):
        dev_candidates.append(f"Razer {device_name}")

    last_err = ""
    sub_env = dict(os.environ, PYTHONWARNINGS="ignore")

    for dev_cand in dev_candidates:
        cmd = [ctrl_bin]
        if config_dir:
            cmd.extend(["--config-dir", config_dir])
        cmd.extend(["--command", "start", "--device", dev_cand, "--preset", clean_preset])

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=0.8, env=sub_env)
            if res.returncode == 0:
                # Only record as active once confirmed by daemon
                set_active_profile(device_name, clean_preset)
                logger.info(f"Profile '{clean_preset}' successfully started on {dev_cand}")
                return True, f"Profile '{clean_preset}' successfully activated on {device_name}!"
            
            raw_output = res.stderr or res.stdout or ""
            clean_lines = [
                line.strip() for line in raw_output.splitlines()
                if line.strip() and not any(w in line for w in ("UserWarning", "DeprecationWarning", "Pydantic", "pydantic", "UserWarning:"))
            ]
            last_err = " ".join(clean_lines).strip()
        except subprocess.TimeoutExpired:
            last_err = (
                "input-remapper-control timed out; the daemon may have applied the profile, "
                "but Strop could not confirm it."
            )
        except Exception as e:
            last_err = str(e)

    err_msg = f": {last_err[:120]}" if last_err else "."
    return False, f"Could not start profile on {device_name}{err_msg}"



def stop_profile(device_name: str) -> Tuple[bool, str]:
    """Stops the active preset for a given device."""
    ctrl_bin = shutil.which("input-remapper-control")
    if not ctrl_bin:
        return False, "input-remapper-control is not installed; Strop could not confirm that the profile stopped."

    dev_candidates = [device_name]
    if not device_name.startswith("Razer Razer"):
        dev_candidates.append(f"Razer Razer {device_name.replace('Razer ', '')}")

    sub_env = dict(os.environ, PYTHONWARNINGS="ignore")
    stopped = False
    for dev_cand in dev_candidates:
        try:
            res = subprocess.run([ctrl_bin, "--command", "stop", "--device", dev_cand], capture_output=True, timeout=0.6, env=sub_env)
            if res.returncode == 0:
                stopped = True
                break
        except Exception as e:
            logger.debug(f"Error stopping profile on {dev_cand}: {e}")

    if stopped:
        clear_active_profile(device_name)
        return True, f"Profile stopped for {device_name}."
    else:
        return False, f"Could not stop profile on {device_name} (daemon or device not responding)."
 

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
        res = subprocess.run([ctrl_bin, "--command", "status"], capture_output=True, text=True, timeout=0.8, env=sub_env)
        out = (res.stdout or "") + (res.stderr or "")
        if "Host is down" in out or "Could not connect" in out or "not running" in out or res.returncode != 0:
            return "stopped", "input-remapper daemon is not running. Start with: sudo systemctl start input-remapper"
        return "running", "input-remapper daemon is active."
    except Exception as e:
        return "unknown", f"Daemon status check error: {e}"
