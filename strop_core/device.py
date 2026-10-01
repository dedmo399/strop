"""
Hardware auto-detection and capabilities hashing for Razer peripherals.
Supports all 230+ OpenRazer input devices.
"""

from hashlib import md5
import re
from typing import List, Dict, Optional, Any
from strop_core.catalog import get_device_by_name, get_archetype_for_device


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
    s = capabilities_str + name
    return md5(s.encode()).hexdigest().lower()


def is_razer_device(device_name: str, vendor_id: Optional[int] = None) -> bool:
    """Checks if a device is a Razer peripheral by vendor ID (0x1532) or name matching."""
    if vendor_id == 0x1532:
        return True
    name_low = device_name.lower()
    if "razer" in name_low or "tartarus" in name_low or "blackwidow" in name_low or "naga" in name_low or "orbweaver" in name_low or "nostromo" in name_low or "basilisk" in name_low or "deathadder" in name_low or "huntsman" in name_low or "viper" in name_low:
        return True
    return bool(get_device_by_name(device_name))


def scan_all_connected_devices() -> List[Dict[str, Any]]:
    """
    Scans all /dev/input/event* devices and returns unique connected Razer devices
    along with capability origin_hashes for all sub-interfaces.
    """
    found_map = {}
    try:
        import evdev
        for path in evdev.list_devices():
            try:
                d = evdev.InputDevice(path)
                vendor = getattr(d.info, "vendor", None) if hasattr(d, "info") else None
                if is_razer_device(d.name, vendor):
                    cap_str = str(d.capabilities(absinfo=False))
                    dhash = calculate_origin_hash(cap_str, d.name)
                    archetype = get_archetype_for_device(d.name)
                    clean_name = clean_device_display_name(d.name)
                    key_caps = d.capabilities().get(evdev.ecodes.EV_KEY, [])
                    num_keys = len(key_caps)

                    if clean_name not in found_map:
                        found_map[clean_name] = {
                            "name": clean_name,
                            "clean_name": clean_name,
                            "raw_name": d.name,
                            "hash": dhash,
                            "path": d.path,
                            "archetype": archetype,
                            "vendor": vendor,
                            "num_keys": num_keys,
                            "all_hashes": {},
                            "key_to_hash": {}
                        }

                    found_map[clean_name]["all_hashes"][path] = dhash


                    # Populate key_to_hash for every scancode supported by this sub-interface node

                    # Primary buttons / unique sub-interfaces (like mouse event node 4a7e8e47... with codes 272-276)
                    # or D-pad switches (3581cd25...) get recorded accurately
                    for kc in key_caps:
                        # Dedicated mouse buttons (272-281) or new nodes take precedence
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



            except Exception:
                pass
    except Exception:
        pass
    return list(found_map.values())


def detect_device(name_filter: str = "tartarus", default_name: str = "Razer Tartarus Pro") -> Dict[str, Any]:
    """
    Detects a specific connected Razer device based on name keyword filter or category archetype,
    collecting all sub-interface hashes and per-scancode hash associations.
    """
    clean_def = clean_device_display_name(default_name)
    target_archetype = get_archetype_for_device(default_name)
    all_devs = scan_all_connected_devices()
    
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
        "clean_name": clean_def,
        "raw_name": clean_def,
        "hash": "",
        "path": None,
        "archetype": target_archetype,
        "all_hashes": {},
        "key_to_hash": {}
    }



