"""
OpenRazer Hardware RGB Matrix Controller for Strop Suite.
Allows highlighting remapped keys in bright red (or custom RGB) and unmapped keys
in default stock Razer green directly on physical Razer devices.
"""

import sys
from typing import Dict, Any, List, Optional, Tuple

# Standard 8 Basic Colors + Black RGB Presets
COLOR_PALETTE = {
    "Green":  {"rgb": (0, 255, 0),   "hex": "#22c55e", "icon": "🟢", "tip": "Official Razer Green (0, 255, 0)"},
    "Red":    {"rgb": (255, 0, 0),   "hex": "#ef4444", "icon": "🔴", "tip": "Bright Red (255, 0, 0)"},
    "Blue":   {"rgb": (0, 100, 255), "hex": "#3b82f6", "icon": "🔵", "tip": "Bright Blue (0, 100, 255)"},
    "Yellow": {"rgb": (255, 230, 0), "hex": "#eab308", "icon": "🟡", "tip": "Vibrant Yellow (255, 230, 0)"},
    "Orange": {"rgb": (255, 120, 0), "hex": "#f97316", "icon": "🟠", "tip": "Bright Orange (255, 120, 0)"},
    "Purple": {"rgb": (170, 0, 255), "hex": "#a855f7", "icon": "🟣", "tip": "Electric Purple (170, 0, 255)"},
    "Brown":  {"rgb": (140, 70, 20), "hex": "#854d0e", "icon": "🟤", "tip": "Warm Brown (140, 70, 20)"},
    "White":  {"rgb": (255, 255, 255), "hex": "#ffffff", "icon": "⚪", "tip": "Crisp White (255, 255, 255)"},
    "Black":  {"rgb": (0, 0, 0),     "hex": "#000000", "icon": "⚫", "tip": "LEDs Off / Black (0, 0, 0)"},
}

COLOR_STOCK_GREEN = COLOR_PALETTE["Green"]["rgb"]
COLOR_REMAPPED_RED = COLOR_PALETTE["Red"]["rgb"]
COLOR_OFF = COLOR_PALETTE["Black"]["rgb"]



class RazerLightingEngine:
    """
    Communicates with the OpenRazer DBus daemon to set per-key custom matrix colors.
    Falls back gracefully if OpenRazer is not running or device does not support matrix fx.
    """
    def __init__(self):
        self._manager = None
        self._connected = False
        self._init_openrazer()

    def _init_openrazer(self):
        try:
            import openrazer.client
            self._manager = openrazer.client.DeviceManager()
            self._connected = True
        except Exception:
            self._manager = None
            self._connected = False

    @property
    def is_available(self) -> bool:
        return self._connected and self._manager is not None

    def get_razer_device(self, device_name: str):
        """Finds the openrazer device matching the target name."""
        if not self.is_available:
            self._init_openrazer()
        if not self._manager:
            return None

        clean_target = device_name.lower().replace("razer", "").replace("_", " ").strip()
        for dev in self._manager.devices:
            dev_clean = dev.name.lower().replace("razer", "").replace("_", " ").strip()
            if clean_target in dev_clean or dev_clean in clean_target:
                return dev
        return None

    def apply_device_lighting(
        self,
        device_name: str,
        color: Tuple[int, int, int] = COLOR_STOCK_GREEN,
    ) -> bool:
        """
        Sets all LEDs on target Razer device to solid bright green (0, 255, 0).
        Supports static effect directly or fills advanced LED matrix.
        """
        dev = self.get_razer_device(device_name)
        if not dev or not hasattr(dev, "fx"):
            return False

        try:
            # 1. Try built-in static effect first
            if hasattr(dev.fx, "static"):
                dev.fx.static(*color)
                return True
            elif hasattr(dev.fx, "misc") and hasattr(dev.fx.misc, "set_static_effect"):
                dev.fx.misc.set_static_effect(*color)
                return True
        except Exception:
            pass

        # 2. Fall back to drawing full matrix in bright green
        if hasattr(dev.fx, "advanced"):
            try:
                adv = dev.fx.advanced
                rows = adv.rows
                cols = adv.cols
                matrix = adv.matrix
                for r in range(rows):
                    for c in range(cols):
                        matrix[r, c] = color
                adv.draw()
                return True
            except Exception as e:
                print(f"Failed to draw matrix lighting on {device_name}: {e}")

        return False

    def apply_all_connected_devices_lighting(
        self,
        color: Tuple[int, int, int] = COLOR_STOCK_GREEN,
    ) -> bool:
        """
        Applies solid bright green to every connected Razer device found by OpenRazer.
        """
        if not self.is_available:
            self._init_openrazer()
        if not self._manager:
            return False

        success = True
        for dev in self._manager.devices:
            try:
                if hasattr(dev, "fx") and hasattr(dev.fx, "static"):
                    dev.fx.static(*color)
                elif hasattr(dev, "fx") and hasattr(dev.fx, "advanced"):
                    adv = dev.fx.advanced
                    for r in range(adv.rows):
                        for c in range(adv.cols):
                            adv.matrix[r, c] = color
                    adv.draw()
            except Exception as e:
                print(f"Failed to set lighting for {dev.name}: {e}")
                success = False
        return success



# Singleton engine instance
_engine: Optional[RazerLightingEngine] = None

def get_lighting_engine() -> RazerLightingEngine:
    global _engine
    if _engine is None:
        _engine = RazerLightingEngine()
    return _engine
