"""
Strop Core — Macro Templates, Storage, and Syntax Builders
Provides gaming & productivity macro definitions, builder utilities,
JSON storage management, and serializers compatible with input-remapper-2.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

from strop_core.logger import get_logger

logger = get_logger("strop.macros")


MACRO_TEMPLATES: List[Dict[str, Any]] = [
    # Gaming Combos & Combat
    {
        "id": "tpl_bullet_jump",
        "category": "Gaming",
        "title": "Warframe - Bullet Jump",
        "icon": "⚡",
        "macro": "modify(Control_L, wait(20).key_down(space).wait(100).key_up(space))",
        "label": "BulletJump",
        "desc": "Warframe Bullet Jump using native modify(): Holds Ctrl -> 20ms -> Space (100ms)",
        "mapping_type": "macro",
        "built_in": True
    },
    {
        "id": "tpl_bullet_jump_seq",
        "category": "Gaming",
        "title": "Warframe - Bullet Jump (Explicit)",
        "icon": "⚡",
        "macro": "key_down(Control_L).wait(20).key_down(space).wait(100).key_up(space).key_up(Control_L)",
        "label": "BulletJump",
        "desc": "Warframe Bullet Jump explicit key sequence: Ctrl down -> 20ms -> Space down -> 100ms -> Space up -> Ctrl up",
        "mapping_type": "macro",
        "built_in": True
    },
    {
        "id": "tpl_slide_attack",
        "category": "Gaming",
        "title": "Warframe - Slide Attack / Spin",
        "icon": "⚔️",
        "macro": "modify(Control_L, wait(50).key_down(e).wait(50).key_up(e))",
        "label": "SlideAttack",
        "desc": "Warframe Slide Melee Spin: Holds Ctrl -> 50ms -> E (50ms)",
        "mapping_type": "macro",
        "built_in": True
    },

    {
        "id": "tpl_slide_attack_repeat",
        "category": "Gaming",
        "title": "Warframe - Slide Attack (Loop x5)",
        "icon": "🔄",
        "macro": "repeat(5, key_down(Control_L).wait(50).key_down(e).wait(50).key_up(e).key_up(Control_L).wait(250))",
        "label": "SlideLoop",
        "desc": "Warframe continuous slide attack loop sequence",
        "mapping_type": "macro",
        "built_in": True
    },

    {
        "id": "tpl_ability_combo",
        "category": "Gaming",
        "title": "Quick Melee / Cast (E + Q)",
        "icon": "⚔️",
        "macro": "key(e).wait(40).key(q)",
        "label": "Ability Combo",
        "desc": "Fast sequence execution of melee and tactical ability",
        "mapping_type": "macro",
        "built_in": True
    },
    {
        "id": "tpl_dash",
        "category": "Gaming",
        "title": "Double-Tap Dash (W + W)",
        "icon": "⏩",
        "macro": "key(w).wait(30).key(w)",
        "label": "Dash",
        "desc": "Instant double tap forward dash / dodge",
        "mapping_type": "macro",
        "built_in": True
    },
    {
        "id": "tpl_reload_switch",
        "category": "Gaming",
        "title": "Quick Reload & Switch (R + 1)",
        "icon": "🔄",
        "macro": "key(r).wait(100).key(1)",
        "label": "Reload/Switch",
        "desc": "Reloads primary weapon and switches to weapon 1",
        "mapping_type": "macro",
        "built_in": True
    },


    # Productivity & Streaming
    {
        "id": "tpl_discord_mute",
        "category": "Productivity",
        "title": "Discord Mute Toggle",
        "icon": "🎙️",
        "macro": "Control_L + Shift_L + m",
        "label": "Discord Mute",
        "desc": "Standard hotkey combo to mute/unmute Discord microphone",
        "mapping_type": "key_macro",
        "built_in": True
    },
    {
        "id": "tpl_discord_deafen",
        "category": "Productivity",
        "title": "Discord Deafen Toggle",
        "icon": "🎧",
        "macro": "Control_L + Shift_L + d",
        "label": "Discord Deafen",
        "desc": "Standard hotkey combo to deafen/undeafen Discord audio",
        "mapping_type": "key_macro",
        "built_in": True
    },
    {
        "id": "tpl_obs_record",
        "category": "Productivity",
        "title": "OBS Record / Stream",
        "icon": "📹",
        "macro": "Control_L + Shift_L + F12",
        "label": "OBS Record",
        "desc": "Triggers global hotkey for OBS stream/recording capture",
        "mapping_type": "key_macro",
        "built_in": True
    },
    {
        "id": "tpl_term_paste",
        "category": "Productivity",
        "title": "Terminal Copy & Paste",
        "icon": "📋",
        "macro": "Control_L + Shift_L + v",
        "label": "Term Paste",
        "desc": "Linux terminal clipboard paste (Ctrl+Shift+V)",
        "mapping_type": "key_macro",
        "built_in": True
    },
    {
        "id": "tpl_screenshot",
        "category": "Productivity",
        "title": "Quick Screenshot Area",
        "icon": "📸",
        "macro": "Super_L + Shift_L + s",
        "label": "Screenshot",
        "desc": "Takes interactive regional screen capture",
        "mapping_type": "key_macro",
        "built_in": True
    },
]


def get_macros_file_path() -> Path:
    """Returns path to user custom macros storage (~/.config/strop/macros.json)."""
    p = Path.home() / ".config" / "strop" / "macros.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def get_user_macros() -> List[Dict[str, Any]]:
    """Reads custom user macros from ~/.config/strop/macros.json."""
    fpath = get_macros_file_path()
    if not fpath.exists() or fpath.stat().st_size == 0:
        return []
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                # Ensure all macros have valid input-remapper normalized strings
                for m in data:
                    if isinstance(m, dict) and "macro" in m:
                        m["macro"] = normalize_macro_to_input_remapper(m["macro"])
                return data
    except Exception as e:
        logger.warning(f"Failed to read custom macros: {e}")
    return []




def save_user_macros(macros: List[Dict[str, Any]]) -> bool:
    """Saves user custom macros list to ~/.config/strop/macros.json."""
    fpath = get_macros_file_path()
    try:
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(macros, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Failed to save custom macros: {e}")
        return False


def load_all_macros() -> List[Dict[str, Any]]:
    """Returns combined list of user custom macros and default templates."""
    user_macros = get_user_macros()
    seen_titles = set()
    combined = []

    # First add official built-in templates
    for tpl in MACRO_TEMPLATES:
        seen_titles.add(tpl.get("title", "").strip().lower())
        combined.append(dict(tpl))

    # Then add distinct user custom macros
    for m in user_macros:
        title_low = m.get("title", "").strip().lower()
        if title_low not in seen_titles:
            seen_titles.add(title_low)
            combined.append(dict(m))

    return combined



def save_or_update_macro(macro_dict: Dict[str, Any]) -> bool:
    """Saves a new macro or updates an existing one in user storage."""
    user_macros = get_user_macros()
    m_id = macro_dict.get("id")
    if not m_id:
        m_id = "macro_" + os.urandom(4).hex()
        macro_dict["id"] = m_id

    updated = False
    for i, m in enumerate(user_macros):
        if m.get("id") == m_id:
            user_macros[i] = macro_dict
            updated = True
            break
    if not updated:
        user_macros.append(macro_dict)

    return save_user_macros(user_macros)


def delete_custom_macro(macro_id: str) -> bool:
    """Deletes a custom macro by ID from user storage."""
    user_macros = get_user_macros()
    filtered = [m for m in user_macros if m.get("id") != macro_id]
    return save_user_macros(filtered)


def parse_dsl_sequence(seq_str: str) -> List[str]:
    """
    Parses a macro sequence in dotted DSL format (e.g. key_down(Control_L).wait(50).key(Up)...)
    or standard '+'-separated string into individual steps.
    """
    if not seq_str or not seq_str.strip():
        return []
    import re
    clean_str = seq_str.strip().replace("\n", " ")
    pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*([^)]*?)\s*\)')
    matches = list(pattern.finditer(clean_str))
    if not matches:
        # Fallback to '+'-separated string
        parts = [p.strip() for p in clean_str.split("+") if p.strip()]
        return parts

    tokens = []
    for m in matches:
        func = m.group(1).lower()
        arg = m.group(2).strip().strip('"\'')
        if func in ("wait", "sleep", "delay"):
            val = arg if ("ms" in arg or "s" in arg) else f"{arg}ms"
            tokens.append(val)
        elif func in ("key", "tap", "press"):
            tokens.append(arg)
        elif func in ("key_down", "hold", "down"):
            tokens.append(f"key_down({arg})" if not arg.startswith("key_down") else arg)
        elif func in ("key_up", "release", "up"):
            tokens.append(f"key_up({arg})" if not arg.startswith("key_up") else arg)
        elif func in ("mouse", "click"):
            tokens.append(f"mouse({arg})" if not arg.startswith("mouse") else arg)
        elif func == "wheel":
            tokens.append(f"wheel({arg})" if not arg.startswith("wheel") else arg)
        elif func == "run":
            tokens.append(f'run("{arg}")')
        else:
            tokens.append(f"{func}({arg})" if arg else func)

    return tokens


def normalize_macro_to_input_remapper(macro_str: str) -> str:
    """
    Converts custom chained macro strings or plus syntax with macros into valid input-remapper syntax.
    e.g. 'key_down(Control_L) + 25ms + key_down(space)...' -> 'key_down(Control_L).wait(25).key_down(space)...'
    """
    import re
    s = (macro_str or "").strip()
    if not s:
        return s

    # If it's a single key symbol without sequence or function calls (e.g. '4', '5', 'space', 'KEY_A'):
    if not any(c in s for c in ("+", ".", "(", ")")) and not s.lower().endswith("ms"):
        return s

    # If it's a simple key combination like 'Control_L + space' without function calls:
    if "+" in s and "(" not in s and ")" not in s and "ms" not in s:
        return s

    tokens = []
    # Split by '+' or '.'
    raw_tokens = [p.strip() for p in re.split(r'[\+\.]', s) if p.strip()]
    for tok in raw_tokens:
        tok_clean = tok.strip()
        m_ms = re.match(r'^(\d+)\s*ms$', tok_clean, re.IGNORECASE)
        m_wait = re.match(r'^wait\(\s*(\d+)(?:ms)?\s*\)$', tok_clean, re.IGNORECASE)
        m_func = re.match(r'^([a-zA-Z_]\w*)\s*\((.*)\)$', tok_clean)

        if m_ms:
            tokens.append(f"wait({m_ms.group(1)})")
        elif m_wait:
            tokens.append(f"wait({m_wait.group(1)})")
        elif m_func:
            fn, arg = m_func.group(1), m_func.group(2).strip()
            # If wait(25ms) strip ms
            if fn == "wait" and arg.lower().endswith("ms"):
                arg = arg[:-2].strip()
            tokens.append(f"{fn}({arg})")
        else:
            tokens.append(f"key({tok_clean})")

    return ".".join(tokens)



def build_macro_string(steps: List[str]) -> str:
    """Builds a formatted input-remapper macro string from a list of steps and delays."""
    tokens = []
    for s in steps:
        s_clean = s.strip()
        if not s_clean:
            continue
        if s_clean.lower().endswith("ms"):
            num = s_clean[:-2].strip()
            tokens.append(f"wait({num})")
        elif s_clean.startswith("wait(") and s_clean.endswith(")"):
            inner = s_clean[5:-1].strip()
            if inner.lower().endswith("ms"):
                inner = inner[:-2].strip()
            tokens.append(f"wait({inner})")
        elif "(" in s_clean and s_clean.endswith(")"):
            tokens.append(s_clean)
        else:
            tokens.append(f"key({s_clean})")

    return ".".join(tokens)


def parse_macro_steps(macro_str: str) -> List[str]:
    """Parses a macro string into individual components using DSL or '+' separators."""
    return parse_dsl_sequence(macro_str)


