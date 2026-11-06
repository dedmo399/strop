"""
OpenRazer Mouse DPI, Stages, and Polling Rate Controller for Strop Suite.
Discovers actual hardware sensor capabilities via OpenRazer D-Bus, applies
X/Y DPI, stage tables, and polling rates with read-back verification, and
persists per-device settings in ~/.config/strop/mouse_settings.json.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from strop_core.catalog import get_device_by_name
from strop_core.device import clean_device_display_name, device_model_name
from strop_core.logger import get_logger
from strop_core.presets import _atomic_write_json, get_strop_config_dir

logger = get_logger("strop.dpi")

MIN_DPI: int = 100
DEFAULT_MAX_DPI: int = 16000
DEFAULT_POLL_RATES: List[int] = [125, 500, 1000]
DEFAULT_DPI_STAGES: List[Tuple[int, int]] = [
    (800, 800),
    (1600, 1600),
    (3200, 3200),
    (3800, 3800),
    (6400, 6400),
]


@dataclass
class MouseSensorCapabilities:
    """Discovered hardware sensor capabilities for a Razer mouse."""
    available: bool = False
    device_name: str = ""
    serial: str = ""
    vid: Optional[int] = None
    pid: Optional[int] = None
    has_dpi: bool = False
    has_available_dpi: bool = False
    has_independent_xy: bool = False
    available_dpi: List[int] = field(default_factory=list)
    has_dpi_stages: bool = False
    min_dpi: int = MIN_DPI
    max_dpi: int = DEFAULT_MAX_DPI
    current_dpi: Tuple[int, int] = (3800, 3800)
    has_poll_rate: bool = False
    supported_poll_rates: List[int] = field(default_factory=lambda: list(DEFAULT_POLL_RATES))
    current_poll_rate: Optional[int] = None


@dataclass
class MouseSensorSettings:
    """User-configured DPI, stage presets, polling rate, and side plate for a mouse."""
    dpi_x: int = 3800
    dpi_y: int = 3800
    linked_xy: bool = True
    active_stage: int = 4
    stages: List[Tuple[int, int]] = field(default_factory=lambda: list(DEFAULT_DPI_STAGES))
    poll_rate: int = 1000
    side_plate: Optional[str] = None


@dataclass(frozen=True)
class SensorOperationResult:
    """Outcome of applying DPI or polling rate settings to hardware."""
    success: bool
    message: str
    dpi: Optional[Tuple[int, int]] = None
    poll_rate: Optional[int] = None


def clamp_dpi_value(
    dpi: int,
    min_dpi: int = MIN_DPI,
    max_dpi: int = DEFAULT_MAX_DPI,
    available_dpi: Optional[List[int]] = None,
) -> int:
    """Clamps a DPI integer to [min_dpi, max_dpi] or snaps to discrete available_dpi."""
    val = int(dpi)
    if available_dpi:
        valid = sorted(int(x) for x in available_dpi if int(x) > 0)
        if valid:
            return min(valid, key=lambda candidate: abs(candidate - val))
    low = max(1, int(min_dpi))
    high = max(low, int(max_dpi))
    return max(low, min(high, val))


def get_mouse_settings_file() -> Path:
    """Returns the path to ~/.config/strop/mouse_settings.json."""
    return get_strop_config_dir() / "mouse_settings.json"


def _read_all_mouse_settings() -> Dict[str, Any]:
    fpath = get_mouse_settings_file()
    if not fpath.exists():
        return {}
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.debug(f"Could not read mouse_settings.json: {e}")
    return {}


def load_mouse_settings(
    device_name: str,
    capabilities: Optional[MouseSensorCapabilities] = None,
) -> MouseSensorSettings:
    """
    Loads saved MouseSensorSettings for device_name, merging with live hardware
    capabilities when available.
    """
    clean_name = clean_device_display_name(device_name)
    all_data = _read_all_mouse_settings()

    entry = all_data.get(clean_name)
    if not isinstance(entry, dict):
        # Try normalized model match
        target_model = device_model_name(clean_name).casefold()
        for k, v in all_data.items():
            if isinstance(v, dict) and device_model_name(k).casefold() == target_model:
                entry = v
                break

    min_dpi = capabilities.min_dpi if capabilities else MIN_DPI
    max_dpi = capabilities.max_dpi if capabilities else DEFAULT_MAX_DPI
    avail_dpi = capabilities.available_dpi if capabilities else None
    supported_rates = (
        capabilities.supported_poll_rates
        if (capabilities and capabilities.supported_poll_rates)
        else DEFAULT_POLL_RATES
    )

    # Defaults from live hardware if available, else standard defaults
    default_x, default_y = (3800, 3800)
    if capabilities and capabilities.available and capabilities.has_dpi:
        live_x, live_y = capabilities.current_dpi
        default_x = clamp_dpi_value(live_x, min_dpi, max_dpi, avail_dpi)
        default_y = clamp_dpi_value(live_y if live_y > 0 else live_x, min_dpi, max_dpi, avail_dpi)

    default_poll = 1000
    if capabilities and capabilities.available and capabilities.current_poll_rate in supported_rates:
        default_poll = int(capabilities.current_poll_rate)
    elif supported_rates:
        default_poll = 1000 if 1000 in supported_rates else supported_rates[-1]

    stages: List[Tuple[int, int]] = [
        (
            clamp_dpi_value(sx, min_dpi, max_dpi, avail_dpi),
            clamp_dpi_value(sy, min_dpi, max_dpi, avail_dpi),
        )
        for sx, sy in DEFAULT_DPI_STAGES
    ]
    linked_xy = True
    dpi_x = default_x
    dpi_y = default_y
    poll_rate = default_poll
    active_stage = 4
    side_plate: Optional[str] = None

    if isinstance(entry, dict):
        if isinstance(entry.get("side_plate"), str) and entry["side_plate"].strip():
            side_plate = entry["side_plate"].strip()
        raw_stages = entry.get("stages")
        if isinstance(raw_stages, list) and len(raw_stages) > 0:
            parsed_stages: List[Tuple[int, int]] = []
            for item in raw_stages[:5]:
                if isinstance(item, (list, tuple)) and len(item) >= 2:
                    try:
                        sx = clamp_dpi_value(int(item[0]), min_dpi, max_dpi, avail_dpi)
                        sy = clamp_dpi_value(int(item[1]), min_dpi, max_dpi, avail_dpi)
                        parsed_stages.append((sx, sy))
                    except (ValueError, TypeError):
                        pass
                elif isinstance(item, int):
                    s_val = clamp_dpi_value(item, min_dpi, max_dpi, avail_dpi)
                    parsed_stages.append((s_val, s_val))
            while len(parsed_stages) < 5:
                fallback = DEFAULT_DPI_STAGES[len(parsed_stages)]
                parsed_stages.append((
                    clamp_dpi_value(fallback[0], min_dpi, max_dpi, avail_dpi),
                    clamp_dpi_value(fallback[1], min_dpi, max_dpi, avail_dpi),
                ))
            stages = parsed_stages

        # Use live hardware DPI when connected, otherwise saved DPI
        if not (capabilities and capabilities.available and capabilities.has_dpi):
            try:
                if "dpi_x" in entry:
                    dpi_x = clamp_dpi_value(int(entry["dpi_x"]), min_dpi, max_dpi, avail_dpi)
                if "dpi_y" in entry:
                    dpi_y = clamp_dpi_value(int(entry["dpi_y"]), min_dpi, max_dpi, avail_dpi)
                else:
                    dpi_y = dpi_x
            except (ValueError, TypeError):
                pass

        if isinstance(entry.get("linked_xy"), bool):
            linked_xy = entry["linked_xy"]
        else:
            linked_xy = (dpi_x == dpi_y)

        if capabilities and capabilities.available and capabilities.has_dpi and dpi_x != dpi_y:
            linked_xy = False
        if capabilities and not capabilities.has_independent_xy and capabilities.available:
            linked_xy = True
            dpi_y = dpi_x
        elif linked_xy:
            dpi_y = dpi_x

        try:
            saved_stage = int(entry.get("active_stage", 0))
            if 1 <= saved_stage <= len(stages):
                active_stage = saved_stage
        except (ValueError, TypeError):
            pass

        if not (capabilities and capabilities.available and capabilities.current_poll_rate):
            try:
                saved_poll = int(entry.get("poll_rate", default_poll))
                if saved_poll in supported_rates:
                    poll_rate = saved_poll
            except (ValueError, TypeError):
                pass

    # If current (dpi_x, dpi_y) matches a stage, align active_stage to it
    for idx, (sx, sy) in enumerate(stages, start=1):
        if sx == dpi_x and sy == dpi_y:
            active_stage = idx
            break

    return MouseSensorSettings(
        dpi_x=dpi_x,
        dpi_y=dpi_y,
        linked_xy=linked_xy,
        active_stage=active_stage,
        stages=stages,
        poll_rate=poll_rate,
        side_plate=side_plate,
    )


def save_mouse_settings(device_name: str, settings: MouseSensorSettings) -> bool:
    """Persists MouseSensorSettings for device_name to ~/.config/strop/mouse_settings.json."""
    clean_name = clean_device_display_name(device_name)
    all_data = _read_all_mouse_settings()
    prev = all_data.get(clean_name, {}) if isinstance(all_data.get(clean_name), dict) else {}
    saved_plate = settings.side_plate if settings.side_plate is not None else prev.get("side_plate")
    payload: Dict[str, Any] = {
        "dpi_x": int(settings.dpi_x),
        "dpi_y": int(settings.dpi_y),
        "linked_xy": bool(settings.linked_xy),
        "active_stage": int(settings.active_stage),
        "stages": [[int(sx), int(sy)] for sx, sy in settings.stages],
        "poll_rate": int(settings.poll_rate),
    }
    if isinstance(saved_plate, str) and saved_plate.strip():
        payload["side_plate"] = saved_plate.strip()
    all_data[clean_name] = payload
    try:
        _atomic_write_json(get_mouse_settings_file(), all_data)
        return True
    except Exception as e:
        logger.warning(f"Failed to save mouse settings for {clean_name}: {e}")
        return False


class RazerDPIEngine:
    """
    Communicates with the OpenRazer D-Bus daemon to query capabilities and set
    mouse DPI, DPI stages, and polling rate.
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
        except Exception as e:
            logger.debug(f"OpenRazer client unavailable: {e}")
            self._manager = None
            self._connected = False

    @property
    def is_available(self) -> bool:
        return self._connected and self._manager is not None

    def get_razer_mouse(self, device_name: str, pid: Optional[int] = None):
        """
        Finds the OpenRazer mouse matching device_name using stable identifiers first:
        1. USB (vid, pid) match (0x1532, pid)
        2. Exact normalized model name match
        3. Normalized substring match on mouse devices
        """
        if not self.is_available:
            self._init_openrazer()
        if not self._manager:
            return None

        try:
            devices = list(self._manager.devices)
        except Exception:
            return None

        target_pid = pid
        if target_pid is None and device_name:
            cat_entry = get_device_by_name(device_name)
            if cat_entry:
                target_pid = cat_entry.get("pid_int")

        # 1. Match by exact USB Product ID
        if target_pid is not None:
            for dev in devices:
                try:
                    dev_pid = int(getattr(dev, "_pid", -1))
                    dev_vid = int(getattr(dev, "_vid", 0x1532))
                    if dev_vid == 0x1532 and dev_pid == int(target_pid):
                        return dev
                except (ValueError, TypeError):
                    continue

        clean_target = device_model_name(device_name).casefold().replace("_", " ").strip()
        if not clean_target:
            return None

        # 2. Match by exact normalized model name
        for dev in devices:
            dev_clean = device_model_name(getattr(dev, "name", "")).casefold().replace("_", " ").strip()
            if dev_clean == clean_target:
                return dev

        # 3. Substring match restricted to mice / DPI-capable devices
        for dev in devices:
            is_mouse = getattr(dev, "type", "") == "mouse" or (hasattr(dev, "has") and dev.has("dpi"))
            if not is_mouse:
                continue
            dev_clean = device_model_name(getattr(dev, "name", "")).casefold().replace("_", " ").strip()
            if clean_target in dev_clean or dev_clean in clean_target:
                return dev

        return None

    def discover_capabilities(self, device_name: str, pid: Optional[int] = None) -> MouseSensorCapabilities:
        """Discovers actual DPI, stage, and polling rate capabilities from OpenRazer."""
        dev = self.get_razer_mouse(device_name, pid=pid)
        if dev is None:
            return MouseSensorCapabilities(
                available=False,
                device_name=clean_device_display_name(device_name),
            )

        has_fn = getattr(dev, "has", lambda _feature: False)
        has_dpi = bool(has_fn("dpi"))
        has_avail_dpi = bool(has_fn("available_dpi"))
        has_stages = bool(has_fn("dpi_stages"))
        has_poll = bool(has_fn("poll_rate"))
        has_supp_poll = bool(has_fn("supported_poll_rates"))

        avail_dpi_list: List[int] = []
        if has_avail_dpi:
            try:
                avail_dpi_list = [int(x) for x in dev.available_dpi]
            except Exception:
                avail_dpi_list = []

        max_dpi = DEFAULT_MAX_DPI
        if has_dpi:
            try:
                raw_max = int(dev.max_dpi)
                if raw_max > 0:
                    max_dpi = raw_max
            except Exception:
                if avail_dpi_list:
                    max_dpi = max(avail_dpi_list)

        min_dpi = min(avail_dpi_list) if avail_dpi_list else MIN_DPI

        current_dpi = (3800, 3800)
        if has_dpi or has_avail_dpi:
            try:
                raw_dpi = dev.dpi
                if isinstance(raw_dpi, (tuple, list)) and len(raw_dpi) >= 2:
                    dx = int(raw_dpi[0])
                    dy = int(raw_dpi[1]) if int(raw_dpi[1]) > 0 else dx
                    current_dpi = (dx, dy)
                elif isinstance(raw_dpi, (tuple, list)) and len(raw_dpi) == 1:
                    dx = int(raw_dpi[0])
                    current_dpi = (dx, dx)
            except Exception as e:
                logger.debug(f"Could not read current DPI from {getattr(dev, 'name', device_name)}: {e}")

        supported_rates = list(DEFAULT_POLL_RATES)
        if has_supp_poll:
            try:
                rates = [int(r) for r in dev.supported_poll_rates if int(r) > 0]
                if rates:
                    supported_rates = rates
            except Exception:
                pass

        current_poll: Optional[int] = None
        if has_poll:
            try:
                current_poll = int(dev.poll_rate)
                if current_poll > 0 and current_poll not in supported_rates:
                    supported_rates = sorted(set(supported_rates + [current_poll]))
            except Exception as e:
                logger.debug(f"Could not read poll_rate from {getattr(dev, 'name', device_name)}: {e}")

        vid = None
        resolved_pid = pid
        try:
            vid = int(getattr(dev, "_vid", 0x1532))
            resolved_pid = int(getattr(dev, "_pid", pid or 0)) or pid
        except (ValueError, TypeError):
            pass

        return MouseSensorCapabilities(
            available=True,
            device_name=clean_device_display_name(getattr(dev, "name", device_name)),
            serial=str(getattr(dev, "serial", "")),
            vid=vid,
            pid=resolved_pid,
            has_dpi=has_dpi,
            has_available_dpi=has_avail_dpi,
            has_independent_xy=bool(has_dpi and not has_avail_dpi),
            available_dpi=avail_dpi_list,
            has_dpi_stages=has_stages,
            min_dpi=min_dpi,
            max_dpi=max_dpi,
            current_dpi=current_dpi,
            has_poll_rate=has_poll,
            supported_poll_rates=supported_rates,
            current_poll_rate=current_poll,
        )

    def apply_dpi(
        self,
        device_name: str,
        dpi_x: int,
        dpi_y: Optional[int] = None,
        pid: Optional[int] = None,
    ) -> SensorOperationResult:
        """Applies X/Y DPI to the target OpenRazer mouse and verifies via read-back."""
        dev = self.get_razer_mouse(device_name, pid=pid)
        if dev is None:
            return SensorOperationResult(
                success=False,
                message=f"OpenRazer mouse '{device_name}' is not available.",
            )

        caps = self.discover_capabilities(device_name, pid=pid)
        if not caps.has_dpi:
            return SensorOperationResult(
                success=False,
                message=f"{caps.device_name} does not expose DPI control through OpenRazer.",
            )

        target_x = clamp_dpi_value(dpi_x, caps.min_dpi, caps.max_dpi, caps.available_dpi)
        raw_y = dpi_x if dpi_y is None else dpi_y
        target_y = clamp_dpi_value(raw_y, caps.min_dpi, caps.max_dpi, caps.available_dpi)

        try:
            if caps.has_available_dpi:
                dev.dpi = (int(target_x), 0)
                expected = (target_x, target_x)
            else:
                dev.dpi = (int(target_x), int(target_y))
                expected = (target_x, target_y)

            # Read-back verification
            try:
                read_dpi = dev.dpi
                actual_x = int(read_dpi[0])
                actual_y = int(read_dpi[1]) if len(read_dpi) > 1 and int(read_dpi[1]) > 0 else actual_x
                actual = (actual_x, actual_y)
            except Exception:
                actual = expected

            dpi_label = f"{actual[0]} DPI" if actual[0] == actual[1] else f"{actual[0]}×{actual[1]} DPI"
            return SensorOperationResult(
                success=True,
                message=f"Set {caps.device_name} to {dpi_label}",
                dpi=actual,
                poll_rate=caps.current_poll_rate,
            )
        except Exception as e:
            logger.warning(f"Failed to set DPI on {caps.device_name}: {e}")
            return SensorOperationResult(
                success=False,
                message=f"Failed to set DPI on {caps.device_name}: {e}",
            )

    def apply_dpi_stages(
        self,
        device_name: str,
        active_stage: int,
        stages: List[Tuple[int, int]],
        pid: Optional[int] = None,
    ) -> bool:
        """Syncs DPI stages to OpenRazer hardware if the device supports native dpi_stages."""
        dev = self.get_razer_mouse(device_name, pid=pid)
        if dev is None or not getattr(dev, "has", lambda _f: False)("dpi_stages"):
            return False

        caps = self.discover_capabilities(device_name, pid=pid)
        sanitized = [
            (
                clamp_dpi_value(sx, caps.min_dpi, caps.max_dpi, caps.available_dpi),
                clamp_dpi_value(sy, caps.min_dpi, caps.max_dpi, caps.available_dpi),
            )
            for sx, sy in stages
        ]
        if not sanitized:
            return False
        stage_idx = max(1, min(len(sanitized), int(active_stage)))
        try:
            dev.dpi_stages = (stage_idx, sanitized)
            return True
        except Exception as e:
            logger.debug(f"Could not sync native dpi_stages on {caps.device_name}: {e}")
            return False

    def apply_poll_rate(
        self,
        device_name: str,
        poll_rate: int,
        pid: Optional[int] = None,
    ) -> SensorOperationResult:
        """Applies polling rate (Hz) to the target OpenRazer mouse and verifies via read-back."""
        dev = self.get_razer_mouse(device_name, pid=pid)
        if dev is None:
            return SensorOperationResult(
                success=False,
                message=f"OpenRazer mouse '{device_name}' is not available.",
            )

        caps = self.discover_capabilities(device_name, pid=pid)
        if not caps.has_poll_rate:
            return SensorOperationResult(
                success=False,
                message=f"{caps.device_name} does not expose polling rate control through OpenRazer.",
            )

        rate = int(poll_rate)
        if caps.supported_poll_rates and rate not in caps.supported_poll_rates:
            return SensorOperationResult(
                success=False,
                message=f"Unsupported polling rate {rate} Hz (supported: {caps.supported_poll_rates}).",
            )

        try:
            dev.poll_rate = rate
            try:
                actual_rate = int(dev.poll_rate)
            except Exception:
                actual_rate = rate
            if actual_rate != rate:
                return SensorOperationResult(
                    success=False,
                    message=f"{caps.device_name} reported {actual_rate} Hz after requesting {rate} Hz.",
                    dpi=caps.current_dpi,
                    poll_rate=actual_rate,
                )
            return SensorOperationResult(
                success=True,
                message=f"Set {caps.device_name} polling rate to {actual_rate} Hz",
                dpi=caps.current_dpi,
                poll_rate=actual_rate,
            )
        except Exception as e:
            logger.warning(f"Failed to set poll_rate on {caps.device_name}: {e}")
            return SensorOperationResult(
                success=False,
                message=f"Failed to set polling rate on {caps.device_name}: {e}",
            )

    def apply_sensor_settings(
        self,
        device_name: str,
        settings: MouseSensorSettings,
        pid: Optional[int] = None,
    ) -> SensorOperationResult:
        """
        Applies both DPI (and stages if supported) and polling rate to the device,
        persisting settings to ~/.config/strop/mouse_settings.json.
        """
        dpi_y = settings.dpi_x if settings.linked_xy else settings.dpi_y
        settings.dpi_y = dpi_y
        saved = save_mouse_settings(device_name, settings)

        caps = self.discover_capabilities(device_name, pid=pid)
        if not caps.available:
            msg = (
                f"Saved sensor settings for {clean_device_display_name(device_name)} "
                "(OpenRazer device offline)."
                if saved else
                "Could not save or apply sensor settings (OpenRazer offline)."
            )
            return SensorOperationResult(
                success=False,
                message=msg,
                dpi=(settings.dpi_x, settings.dpi_y),
                poll_rate=settings.poll_rate,
            )

        messages: List[str] = []
        overall_ok = True
        applied_dpi = caps.current_dpi
        applied_poll = caps.current_poll_rate

        if caps.has_dpi:
            dpi_res = self.apply_dpi(device_name, settings.dpi_x, dpi_y, pid=pid)
            if dpi_res.success and dpi_res.dpi:
                applied_dpi = dpi_res.dpi
                settings.dpi_x, settings.dpi_y = applied_dpi
                dpi_str = (
                    f"{applied_dpi[0]} DPI"
                    if applied_dpi[0] == applied_dpi[1]
                    else f"{applied_dpi[0]}×{applied_dpi[1]} DPI"
                )
                messages.append(dpi_str)
            else:
                overall_ok = False
                messages.append(dpi_res.message)

        if caps.has_dpi_stages:
            self.apply_dpi_stages(device_name, settings.active_stage, settings.stages, pid=pid)

        if caps.has_poll_rate and settings.poll_rate:
            if caps.current_poll_rate != settings.poll_rate:
                poll_res = self.apply_poll_rate(device_name, settings.poll_rate, pid=pid)
                if poll_res.success and poll_res.poll_rate:
                    applied_poll = poll_res.poll_rate
                    messages.append(f"{applied_poll} Hz")
                else:
                    overall_ok = False
                    messages.append(poll_res.message)
            else:
                applied_poll = caps.current_poll_rate
                messages.append(f"{applied_poll} Hz")

        save_mouse_settings(device_name, settings)

        if overall_ok:
            summary = " · ".join(messages) if messages else "Sensor settings applied"
            return SensorOperationResult(
                success=True,
                message=f"{caps.device_name}: {summary}",
                dpi=applied_dpi,
                poll_rate=applied_poll,
            )
        return SensorOperationResult(
            success=False,
            message="; ".join(messages),
            dpi=applied_dpi,
            poll_rate=applied_poll,
        )


_dpi_engine: Optional[RazerDPIEngine] = None


def get_dpi_engine() -> RazerDPIEngine:
    """Returns the shared RazerDPIEngine singleton."""
    global _dpi_engine
    if _dpi_engine is None:
        _dpi_engine = RazerDPIEngine()
    return _dpi_engine
