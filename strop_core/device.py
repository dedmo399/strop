"""Hardware auto-detection and capabilities hashing for Razer peripherals.

The OpenRazer catalog supplies layout metadata; it does not imply that every
listed model has been detected or verified with Strop.
"""

from hashlib import md5
import re
from typing import List, Dict, Optional, Any
from strop_core.catalog import get_device_by_name, get_archetype_for_device


from strop_core.logger import get_logger

logger = get_logger("strop.device")


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


def is_razer_device(device_name: Optional[str], vendor_id: Optional[int] = None) -> bool:
    """Checks if a device is a Razer peripheral by vendor ID (0x1532) or name matching."""
    # uinput outputs can copy the physical device's name and vendor ID.
    # They must never become remapping sources or supply origin hashes.
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
            dev_name = d.name or ""
            if is_razer_device(dev_name, vendor):
                cap_str = str(d.capabilities(absinfo=False))
                dhash = calculate_origin_hash(cap_str, dev_name)
                archetype = get_archetype_for_device(dev_name)
                clean_name = clean_device_display_name(dev_name)
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

    devices = list(found_map.values())
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
    return {
        "name": clean_def,
        "clean_name": device_model_name(clean_def),
        "raw_name": clean_def,
        "hash": "",
        "path": None,
        "archetype": target_archetype,
        "all_hashes": {},
        "key_to_hash": {},
        "detected": False,
        "scan_diagnostics": diagnostics,
    }

