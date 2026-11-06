"""Hardware auto-detection and capabilities hashing for Razer peripherals.

The OpenRazer catalog supplies layout metadata; it does not imply that every
listed model has been detected or verified with Strop.
"""

from hashlib import md5
import json
from pathlib import Path
import re
from typing import List, Dict, Optional, Any
from strop_core.catalog import (
    get_device_by_name,
    get_archetype_for_device,
    is_multi_plate_mouse,
    MOUSE_NAGA_MMO,
    MOUSE_NAGA_HEX,
    MOUSE_BASILISK_FPS,
    MOUSE_FPS,
    MOUSE_AMBI,
)


from strop_core.logger import get_logger

logger = get_logger("strop.device")

# Side Plate Identifiers & Tab Metadata for Modular Razer Mice
SIDE_PLATE_FPS_2 = "fps_2"
SIDE_PLATE_HEX_7 = "hex_7"
SIDE_PLATE_MMO_12 = "mmo_12"
SIDE_PLATE_AMBI = "ambi"

SIDE_PLATE_METADATA: Dict[str, Dict[str, Any]] = {
    SIDE_PLATE_FPS_2: {
        "id": SIDE_PLATE_FPS_2,
        "label": "2-Button FPS / Ergonomic Plate",
        "short_label": "2-Button FPS Plate",
        "page": 0,
        "archetype": MOUSE_FPS,
    },
    SIDE_PLATE_HEX_7: {
        "id": SIDE_PLATE_HEX_7,
        "label": "7-Button MOBA / Action-RPG Hex Plate",
        "short_label": "7-Button Hex Plate",
        "page": 1,
        "archetype": MOUSE_NAGA_HEX,
    },
    SIDE_PLATE_MMO_12: {
        "id": SIDE_PLATE_MMO_12,
        "label": "12-Button MMO / Macro Grid Plate",
        "short_label": "12-Button MMO Plate",
        "page": 2,
        "archetype": MOUSE_NAGA_MMO,
    },
    SIDE_PLATE_AMBI: {
        "id": SIDE_PLATE_AMBI,
        "label": "Ambidextrous Right Side Buttons",
        "short_label": "Ambidextrous Side Buttons",
        "page": 3,
        "archetype": MOUSE_AMBI,
    },
}


def side_plate_for_archetype(archetype: Optional[str]) -> str:
    """Maps a mouse hardware archetype to its corresponding side plate identifier."""
    if archetype == MOUSE_NAGA_MMO:
        return SIDE_PLATE_MMO_12
    if archetype == MOUSE_NAGA_HEX:
        return SIDE_PLATE_HEX_7
    if archetype == MOUSE_AMBI:
        return SIDE_PLATE_AMBI
    return SIDE_PLATE_FPS_2


def detect_side_plate_from_preset_entries(entries: Optional[List[Dict[str, Any]]]) -> Optional[str]:
    """
    Infers the attached mouse side plate from input-remapper preset entries
    by inspecting mapped scancodes and button names.
    """
    if not isinstance(entries, list) or not entries:
        return None

    fps_score = 0
    hex_score = 0
    mmo_score = 0
    ambi_score = 0
    has_high_mmo_code = False

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        combo = entry.get("input_combination")
        if not isinstance(combo, list):
            continue
        name = str(entry.get("name") or "").strip().lower()
        codes = [
            item.get("code")
            for item in combo
            if isinstance(item, dict) and item.get("type", 1) == 1 and isinstance(item.get("code"), int)
        ]

        if "hex side button" in name or "naga_hex" in name or "naga hex" in name or name.startswith("hex "):
            hex_score += 2
        elif "naga side button" in name or name.startswith("naga_") or name.startswith("naga "):
            mmo_score += 2
        elif "right side" in name or name.startswith("ambi_"):
            ambi_score += 2
        elif "forward button" in name or "back button" in name or name.startswith("fps_"):
            fps_score += 2

        for code in codes:
            if 9 <= code <= 13:
                has_high_mmo_code = True
                mmo_score += 2
            elif 2 <= code <= 8:
                if "hex" in name:
                    hex_score += 1
                elif "naga" in name:
                    mmo_score += 1
                else:
                    hex_score += 1
            elif code in (275, 276):
                fps_score += 1
            elif code in (278, 281):
                ambi_score += 1

    if has_high_mmo_code and hex_score > 0 and "hex" not in " ".join(
        str(e.get("name") or "").lower() for e in entries if isinstance(e, dict)
    ):
        mmo_score += hex_score
        hex_score = 0

    scores = [
        (mmo_score, SIDE_PLATE_MMO_12),
        (hex_score, SIDE_PLATE_HEX_7),
        (fps_score, SIDE_PLATE_FPS_2),
        (ambi_score, SIDE_PLATE_AMBI),
    ]
    best_score, best_plate = max(scores, key=lambda item: item[0])
    return best_plate if best_score > 0 else None


def detect_side_plate_from_state(state: Dict[str, Dict[str, Any]]) -> Optional[str]:
    """
    Infers the active side plate from a RazerMouseStudioWindow runtime state dict
    based on which side-plate buttons have non-empty outputs assigned.
    """
    if not isinstance(state, dict) or not state:
        return None

    counts = {
        SIDE_PLATE_FPS_2: 0,
        SIDE_PLATE_HEX_7: 0,
        SIDE_PLATE_MMO_12: 0,
        SIDE_PLATE_AMBI: 0,
    }
    for kid, entry in state.items():
        if not isinstance(entry, dict):
            continue
        out = str(entry.get("output") or "").strip()
        if not out:
            continue
        if kid in ("fps_forward", "fps_back"):
            counts[SIDE_PLATE_FPS_2] += 1
        elif kid.startswith("naga_hex_"):
            counts[SIDE_PLATE_HEX_7] += 1
        elif kid.startswith("naga_"):
            counts[SIDE_PLATE_MMO_12] += 1
        elif kid.startswith("ambi_"):
            counts[SIDE_PLATE_AMBI] += 1

    best_plate, best_count = max(counts.items(), key=lambda kv: kv[1])
    return best_plate if best_count > 0 else None


def _read_sysfs_side_plate(pid: Optional[int] = None) -> Optional[str]:
    """
    Checks /sys/bus/hid/drivers/razermouse/*/ for any driver-exposed side panel
    attribute on modular Razer mice. Non-blocking sysfs file read only.
    """
    sysfs_base = Path("/sys/bus/hid/drivers/razermouse")
    if not sysfs_base.is_dir():
        return None
    attr_names = ("side_panel", "side_plate", "panel_id", "attached_side_panel")
    try:
        for dev_dir in sysfs_base.iterdir():
            if not dev_dir.is_dir():
                continue
            if pid is not None and f":{pid:04X}." not in dev_dir.name.upper():
                continue
            for attr in attr_names:
                attr_file = dev_dir / attr
                if attr_file.is_file():
                    raw = attr_file.read_text(encoding="utf-8", errors="ignore").strip().lower()
                    if raw in ("2", "fps", "fps_2", "0x01", "1"):
                        return SIDE_PLATE_FPS_2
                    if raw in ("6", "7", "hex", "hex_7", "0x02"):
                        return SIDE_PLATE_HEX_7
                    if raw in ("12", "mmo", "mmo_12", "0x03", "3"):
                        return SIDE_PLATE_MMO_12
    except Exception:
        pass
    return None


def _find_existing_device_presets_dir(device_name: str) -> Optional[Path]:
    """Finds an existing input-remapper preset directory for device_name without creating folders."""
    from strop_core.presets import get_config_base
    base_dirs = [get_config_base()]
    home_base = Path.home() / ".config"
    if home_base not in base_dirs:
        base_dirs.append(home_base)
    candidates = []
    for base in base_dirs:
        candidates.append(base / "input-remapper-2" / "presets")
        candidates.append(base / "input-remapper" / "presets")
    clean_name = clean_device_display_name(device_name)
    model_norm = device_model_name(clean_name).lower().replace("_", " ").strip()
    for base in candidates:
        if not base.is_dir():
            continue
        for exact in (device_name, clean_name, f"Razer {clean_name}"):
            if exact and (base / exact).is_dir():
                return base / exact
        try:
            for sub in base.iterdir():
                if sub.is_dir():
                    sub_norm = device_model_name(sub.name).lower().replace("_", " ").strip()
                    if model_norm and (model_norm == sub_norm or model_norm in sub_norm or sub_norm in model_norm):
                        return sub
        except OSError:
            pass
    return None


def _read_autoload_preset_name(device_name: str, raw_name: Optional[str] = None) -> Optional[str]:
    """Reads the autoloaded preset name for device_name from input-remapper config.json if present."""
    from strop_core.presets import get_config_base
    base_dirs = [get_config_base()]
    home_base = Path.home() / ".config"
    if home_base not in base_dirs:
        base_dirs.append(home_base)
    clean_name = clean_device_display_name(device_name)
    model_norm = device_model_name(clean_name).lower().replace("_", " ").strip()
    for base in base_dirs:
        for cfg_rel in ("input-remapper-2/config.json", "input-remapper/config.json"):
            cfg_path = base / cfg_rel
            if not cfg_path.is_file():
                continue
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                autoload = data.get("autoload", {}) if isinstance(data, dict) else {}
                if not isinstance(autoload, dict):
                    continue
                for key in (raw_name, device_name, clean_name, f"Razer {clean_name}"):
                    if key and isinstance(autoload.get(key), str) and autoload[key].strip():
                        return autoload[key].strip()
                for k, v in autoload.items():
                    if isinstance(k, str) and isinstance(v, str) and v.strip():
                        if device_model_name(k).lower().replace("_", " ").strip() == model_norm:
                            return v.strip()
            except Exception:
                pass
    return None


def _read_active_preset_side_plate(device_name: str, raw_name: Optional[str] = None) -> Optional[str]:
    """Checks active Strop profile or input-remapper autoload preset to detect the attached side plate."""
    try:
        from strop_core.presets import get_active_profile, load_preset_file
    except Exception:
        return None

    pdir = _find_existing_device_presets_dir(device_name)
    if pdir is None and raw_name:
        pdir = _find_existing_device_presets_dir(raw_name)
    if pdir is None or not pdir.is_dir():
        return None

    preset_candidates: List[Path] = []
    active_prof = get_active_profile(device_name) or (get_active_profile(raw_name) if raw_name else None)
    if active_prof:
        cand = pdir / f"{active_prof}.json"
        if cand.is_file():
            preset_candidates.append(cand)

    autoload_prof = _read_autoload_preset_name(device_name, raw_name=raw_name)
    if autoload_prof:
        cand = pdir / f"{autoload_prof}.json"
        if cand.is_file() and cand not in preset_candidates:
            preset_candidates.append(cand)

    try:
        json_files = sorted(pdir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        for jf in json_files:
            if jf not in preset_candidates:
                preset_candidates.append(jf)
    except OSError:
        pass

    for pfile in preset_candidates:
        try:
            entries = load_preset_file(pfile)
            detected = detect_side_plate_from_preset_entries(entries)
            if detected:
                return detected
        except Exception:
            pass
    return None


def _read_saved_side_plate_setting(device_name: str) -> Optional[str]:
    """Reads any persisted side_plate preference from mouse_settings.json."""
    from strop_core.presets import get_strop_config_dir
    fpath = get_strop_config_dir() / "mouse_settings.json"
    if not fpath.is_file():
        home_fpath = Path.home() / ".config" / "strop" / "mouse_settings.json"
        if home_fpath.is_file():
            fpath = home_fpath
        else:
            return None
    try:
        data = json.loads(fpath.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        clean_name = clean_device_display_name(device_name)
        entry = data.get(clean_name)
        if not isinstance(entry, dict):
            target_model = device_model_name(clean_name).casefold()
            for k, v in data.items():
                if isinstance(v, dict) and device_model_name(k).casefold() == target_model:
                    entry = v
                    break
        if isinstance(entry, dict):
            plate = entry.get("side_plate")
            if isinstance(plate, str) and plate in SIDE_PLATE_METADATA:
                return plate
    except Exception:
        pass
    return None


def detect_mouse_side_plate(device_info: Dict[str, Any]) -> Optional[str]:
    """
    Detects the currently attached side plate for a connected or target mouse.
    Returns one of SIDE_PLATE_FPS_2, SIDE_PLATE_HEX_7, SIDE_PLATE_MMO_12, SIDE_PLATE_AMBI,
    or None if the device is not a mouse.
    """
    if not isinstance(device_info, dict):
        return None
    dev_name = str(device_info.get("name") or "")
    raw_name = str(device_info.get("raw_name") or dev_name)
    pid = device_info.get("product")
    archetype = str(device_info.get("archetype") or get_archetype_for_device(dev_name))
    multi_plate = is_multi_plate_mouse(dev_name, pid=pid) or is_multi_plate_mouse(raw_name, pid=pid)

    if not archetype.startswith("MOUSE_") and not multi_plate:
        return None

    name_low = f"{dev_name} {raw_name}".lower()

    if multi_plate:
        # 1. Check explicit variant qualifier in name (e.g. "Razer Naga Trinity Hex" or "FPS")
        if "hex" in name_low or "7-button" in name_low or "7 button" in name_low or "6-button" in name_low:
            return SIDE_PLATE_HEX_7
        if "fps" in name_low or "2-button" in name_low or "2 button" in name_low:
            return SIDE_PLATE_FPS_2

        # 2. Check kernel sysfs side panel attribute if exposed by driver
        sysfs_plate = _read_sysfs_side_plate(pid=pid)
        if sysfs_plate in SIDE_PLATE_METADATA:
            return sysfs_plate

        # 3. Check evdev capability scancodes if device only exposes side buttons without 1..12 grid
        key_to_hash = device_info.get("key_to_hash")
        if isinstance(key_to_hash, dict) and key_to_hash:
            has_fps_btns = (275 in key_to_hash) or (276 in key_to_hash)
            has_grid_btns = any(kc in key_to_hash for kc in range(2, 14))
            if has_fps_btns and not has_grid_btns:
                return SIDE_PLATE_FPS_2

        # 4. Check active Strop profile / input-remapper autoload preset mappings
        preset_plate = _read_active_preset_side_plate(dev_name, raw_name=raw_name)
        if preset_plate in SIDE_PLATE_METADATA:
            return preset_plate

        # 5. Check saved side_plate in mouse_settings.json
        saved_plate = _read_saved_side_plate_setting(dev_name)
        if saved_plate in SIDE_PLATE_METADATA:
            return saved_plate

    # Default based on catalog archetype
    return side_plate_for_archetype(archetype)


def apply_side_plate_to_device_info(device_info: Dict[str, Any]) -> Dict[str, Any]:
    """Populates side_plate, side_plate_label, side_plate_page, multi_plate, and updates archetype."""
    if not isinstance(device_info, dict):
        return device_info
    dev_name = str(device_info.get("name") or "")
    raw_name = str(device_info.get("raw_name") or dev_name)
    pid = device_info.get("product")
    multi_plate = is_multi_plate_mouse(dev_name, pid=pid) or is_multi_plate_mouse(raw_name, pid=pid)
    device_info["multi_plate"] = multi_plate

    plate_id = detect_mouse_side_plate(device_info)
    if plate_id and plate_id in SIDE_PLATE_METADATA:
        meta = SIDE_PLATE_METADATA[plate_id]
        device_info["side_plate"] = meta["id"]
        device_info["side_plate_label"] = meta["label"]
        device_info["side_plate_page"] = meta["page"]
        if multi_plate:
            device_info["archetype"] = meta["archetype"]
    else:
        device_info["side_plate"] = None
        device_info["side_plate_label"] = None
        device_info["side_plate_page"] = None
    return device_info


def clean_device_display_name(raw_name: str) -> str:
    """
    Cleans up duplicate vendor prefix (e.g. 'Razer Razer Tartarus Pro' -> 'Razer Tartarus Pro').
    """
    if not raw_name:
        return "Razer Device"
    cleaned = raw_name.strip()
    # Replace repeated 'Razer Razer' or 'razer razer' with a single 'Razer'
    cleaned = re.sub(r'^(?:razer\s*)+', 'Razer ', cleaned, flags=re.IGNORECASE).strip()
    if not cleaned.lower().startswith("razer") and not cleaned.lower().startswith("blade"):
        cleaned = f"Razer {cleaned}"
    return cleaned.strip()


def calculate_origin_hash(capabilities_str: str, name: str) -> str:
    """Computes the exact origin_hash used by input-remapper-2."""
    s = capabilities_str + (name or "")
    return md5(s.encode()).hexdigest().lower()


def device_model_name(raw_name: str) -> str:
    """Model-only UI label; never use this as a backend or preset identity."""
    return re.sub(r'^(?:razer\s+)+', '', (raw_name or '').strip(),
                  flags=re.IGNORECASE).strip() or "Device"


def is_razer_device(device_name: Optional[str], vendor_id: Optional[int] = None, phys: Optional[str] = None) -> bool:
    """Checks if a device is a Razer peripheral by vendor ID (0x1532) or name matching."""
    # uinput outputs can copy the physical device's name and vendor ID (input-remapper 2.2.1+).
    # They must never become remapping sources or supply origin hashes.
    if isinstance(phys, str) and ("input-remapper" in phys.lower() or phys.strip().lower().startswith("input-remapper")):
        return False
    if isinstance(device_name, str) and device_name.strip().lower().startswith("input-remapper"):
        return False
    if vendor_id == 0x1532:
        return True
    if not device_name or not isinstance(device_name, str):
        return False
    name_low = device_name.lower()
    if "razer" in name_low or "tartarus" in name_low or "blackwidow" in name_low or "naga" in name_low or "orbweaver" in name_low or "nostromo" in name_low or "basilisk" in name_low or "deathadder" in name_low or "huntsman" in name_low or "viper" in name_low:
        return True
    return bool(get_device_by_name(device_name))


def scan_all_connected_devices(diagnostics: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """
    Scans all /dev/input/event* devices and returns unique connected Razer devices
    along with capability origin_hashes for all sub-interfaces.
    Properly handles device permissions and releases file descriptors.
    """
    found_map = {}
    diagnostics = diagnostics if diagnostics is not None else []
    try:
        import evdev
    except ImportError as e:
        message = "Hardware discovery needs python3-evdev. Install it with: sudo apt install python3-evdev."
        diagnostics.append(message)
        logger.warning(f"{message} ({e})")
        return []

    try:
        device_paths = evdev.list_devices()
    except PermissionError as e:
        message = (
            "Strop cannot list /dev/input devices. Check the logged-in user's device ACLs and udev rules; "
            "the desktop user needs read access. Do not run Strop as root."
        )
        diagnostics.append(message)
        logger.error(f"{message} ({e})")
        return []
    except Exception as e:
        message = f"Strop could not enumerate /dev/input devices: {e}"
        diagnostics.append(message)
        logger.warning(message)
        return []

    denied_nodes = 0
    for path in device_paths:
        d = None
        try:
            d = evdev.InputDevice(path)
            vendor = getattr(d.info, "vendor", None) if hasattr(d, "info") else None
            product = getattr(d.info, "product", None) if hasattr(d, "info") else None
            dev_name = d.name or ""
            dev_phys = getattr(d, "phys", None) or ""
            if is_razer_device(dev_name, vendor, phys=dev_phys):
                cap_str = str(d.capabilities(absinfo=False))
                dhash = calculate_origin_hash(cap_str, dev_name)
                archetype = get_archetype_for_device(dev_name)
                clean_name = clean_device_display_name(dev_name)
                if product is None:
                    cat_entry = get_device_by_name(clean_name)
                    product = cat_entry["pid_int"] if cat_entry else None
                key_caps = d.capabilities().get(evdev.ecodes.EV_KEY, [])
                num_keys = len(key_caps)

                if clean_name not in found_map:
                    found_map[clean_name] = {
                        "name": clean_name,
                        "clean_name": device_model_name(clean_name),
                        "raw_name": dev_name,
                        "hash": dhash,
                        "path": d.path,
                        "archetype": archetype,
                        "vendor": vendor,
                        "product": product,
                        "num_keys": num_keys,
                        "all_hashes": {},
                        "key_to_hash": {},
                        "detected": True,
                    }

                found_map[clean_name]["all_hashes"][path] = dhash

                # Populate key_to_hash for every scancode supported by this sub-interface node
                for kc in key_caps:
                    if kc not in found_map[clean_name]["key_to_hash"] or (272 <= kc <= 285):
                        found_map[clean_name]["key_to_hash"][kc] = dhash

                # Set primary default hash to the main matrix / largest interface
                if num_keys > found_map[clean_name].get("num_keys", 0):
                    found_map[clean_name]["hash"] = dhash
                    found_map[clean_name]["path"] = d.path
                    found_map[clean_name]["num_keys"] = num_keys

                # Dedicated Tartarus D-pad switch node (3581cd...)
                if dhash.startswith("3581cd"):
                    for switch_code in (56, 103, 105, 106, 108):
                        found_map[clean_name]["key_to_hash"][switch_code] = dhash

        except PermissionError as e:
            denied_nodes += 1
            logger.warning(f"Permission denied reading device node {path}: {e}")
        except Exception as e:
            logger.warning(f"Could not read device node {path}: {e}")
        finally:
            if d is not None:
                try:
                    d.close()
                except Exception:
                    pass

    devices = [apply_side_plate_to_device_info(dev) for dev in found_map.values()]
    if denied_nodes:
        diagnostics.append(
            f"Strop could not read {denied_nodes} input device node(s). Check /dev/input ACLs and udev rules "
            "for the logged-in user; do not run Strop as root."
        )
    if not devices:
        if not device_paths:
            diagnostics.append(
                "No Linux input event devices were found. Reconnect the device and check that its kernel input/HID driver loaded."
            )
        elif denied_nodes:
            diagnostics.append(
                "No Razer devices were readable. Check USB connection, kernel input/HID drivers, and whether "
                "input-remapper-control --list-devices can enumerate the device."
            )
        else:
            diagnostics.append(
                "No supported Razer input device was detected. Check the USB connection and Linux input/HID driver. "
                "The catalog contains layout references; catalog entries are not verified device support."
            )
    return devices


def detect_device(name_filter: str = "tartarus", default_name: str = "Razer Tartarus Pro") -> Dict[str, Any]:
    """
    Detects a specific connected Razer device based on name keyword filter or category archetype,
    collecting all sub-interface hashes and per-scancode hash associations.
    """
    clean_def = clean_device_display_name(default_name)
    target_archetype = get_archetype_for_device(default_name)
    diagnostics: List[str] = []
    all_devs = scan_all_connected_devices(diagnostics)
    
    # 1. Look for direct match on name_filter
    filter_low = name_filter.lower().strip()
    for d in all_devs:
        raw_low = d.get("raw_name", "").lower()
        name_low = d.get("name", "").lower()
        if filter_low in raw_low or filter_low in name_low:
            return d
            
    # 2. Look for match on archetype category (e.g. KEYBOARD_* or KEYPAD_* or MOUSE_*)
    target_prefix = target_archetype.split("_")[0] if target_archetype else ""
    if target_prefix:
        for d in all_devs:
            d_arch = d.get("archetype", "")
            if d_arch and d_arch.startswith(target_prefix):
                return d

    # 3. Fallback to default metadata
    cat_entry = get_device_by_name(clean_def)
    fallback = {
        "name": clean_def,
        "clean_name": device_model_name(clean_def),
        "raw_name": clean_def,
        "hash": "",
        "path": None,
        "archetype": target_archetype,
        "product": cat_entry["pid_int"] if cat_entry else None,
        "all_hashes": {},
        "key_to_hash": {},
        "detected": False,
        "scan_diagnostics": diagnostics,
    }
    return apply_side_plate_to_device_info(fallback)

