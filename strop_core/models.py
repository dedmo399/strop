"""
Strongly typed data structures and models for Strop.
"""

from typing import TypedDict, List, Optional, Any, Dict
from dataclasses import dataclass, field


class KeyState(TypedDict, total=False):
    """Represents the complete runtime state of a single physical key/button."""
    id: str
    name: str
    label: str
    default_label: str
    code: Optional[int]
    combo: Optional[List[int]]
    aliases: List[str]
    verify: bool
    note: str
    output: str
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


class PresetEntry(TypedDict, total=False):
    input_combination: List[PresetInputItem]
    target_uinput: str
    output_symbol: str
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
    num_keys: int
    all_hashes: Dict[str, str]
    key_to_hash: Dict[int, str]
