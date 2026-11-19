"""
Strongly typed data structures and models for Strop.
"""

from typing import TypedDict, List, Optional, Dict


class KeyState(TypedDict, total=False):
    """Represents the complete runtime state of a single physical key/button."""
    id: str
    name: str
    label: str
    default_label: str
    code: Optional[int]
    input_type: int
    analog_threshold: Optional[int]
    combo: Optional[List[int]]
    aliases: List[str]
    verify: bool
    note: str
    output: str
    output_type: Optional[int]
    output_code: Optional[int]
    mapping_type: str
    custom_name: str
    target: str
    origin_hash: Optional[str]
    row: Optional[int]
    col: Optional[int]
    w: Optional[float]
    gap: Optional[float]


class PresetInputItem(TypedDict, total=False):
    type: int
    code: int
    origin_hash: str
    analog_threshold: Optional[int]


class PresetEntry(TypedDict, total=False):
    input_combination: List[PresetInputItem]
    target_uinput: str
    output_symbol: str
    output_type: Optional[int]
    output_code: Optional[int]
    name: str
    custom_name: Optional[str]
    mapping_type: str


class DeviceInfo(TypedDict, total=False):
    name: str
    clean_name: str
    raw_name: str
    hash: str
    path: str
    archetype: str
    vendor: Optional[int]
    product: Optional[int]
    num_keys: int
    all_hashes: Dict[str, str]
    key_to_hash: Dict[int, str]
    rel_to_hash: Dict[int, str]
    detected: bool
    scan_diagnostics: List[str]
    multi_plate: bool
    side_plate: Optional[str]
    side_plate_label: Optional[str]
    side_plate_page: Optional[int]
