# 🗺️ Strop Roadmap: Standalone Native Daemon Architecture (`stropd`)

The active release plan is [ROADMAP_2.0.md](ROADMAP_2.0.md). This document is a
reference for a possible full daemon; implementing it is not required for 2.0.

## 🎯 Goal
Eliminate dependency on external services (such as `input-remapper-daemon` / `input-remapper-gtk`) while preserving **100% full compatibility** with existing `~/.config/input-remapper-2/` JSON preset configurations and macro syntax.

---

## 🏗️ Architectural Overview

```
                               ┌──────────────────────────────────────────────┐
                               │       Strop Native Daemon (stropd)           │
                               │                                              │
┌───────────────────────┐      │  1. JSON Preset Parser                       │      ┌──────────────────────────┐
│  Hardware Endpoints   │      │     (Reads ~/.config/input-remapper-2/...)   │      │   Virtual uinput Nodes   │
│  /dev/input/event2    ├─────►│                                              ├─────►│  • /dev/uinput (Kbd)     │
│  /dev/input/event3    │ EVIOC│  2. libevdev Event Grabber (EVIOCGRAB)       │      │  • /dev/uinput (Mouse)   │
│  (Tartarus/Keyboard)  │ GRAB │                                              │      │  • /dev/uinput (Gamepad) │
└───────────────────────┘      │  3. Remap & Macro Engine                     │      └────────────┬─────────────┘
                               │     (Key/Mouse/Gamepad/Custom Macros)        │                   │
                               │                                              │                   │
                               │  4. IPC Server (Unix Socket / D-Bus / CLI)   │                   ▼
                               │     (stropd apply / stop / status)           │          Game / Desktop OS
                               └──────────────────────▲───────────────────────┘
                                                      │
                                                      │ IPC (Apply Preset)
                                                      │
                                           ┌──────────┴──────────┐
                                           │   Strop Studio UI   │
                                           │   & HUD Overlay     │
                                           └─────────────────────┘
```

---

## 📦 Core Pillars for Implementation

### 1. Hardware Event Interception (`EVIOCGRAB`)
- **Exclusive Device Grab**: Open active `/dev/input/event*` devices using `evdev.InputDevice(path).grab()`.
- **Pass-through**: Forward untouched scancodes directly to virtual nodes to preserve natural typing when keys are unmapped.
- **Multi-Node Support**: Group composite devices (e.g. Tartarus Pro's matrix, D-Pad, and scroll wheel nodes) under a single unified hardware abstraction.

### 2. Virtual `uinput` Device Pool
- **Virtual Keyboard**: Creates `/dev/uinput` keyboard for standard `KEY_*` emissions.
- **Virtual Mouse**: Creates pointer with `BTN_LEFT`, `BTN_RIGHT`, `REL_X`, `REL_Y`, and `REL_WHEEL`.
- **Virtual Gamepad**: Creates Microsoft X-Box 360 / Generic gamepad controller with `BTN_SOUTH`, `BTN_EAST`, `ABS_X`, `ABS_Y`, etc.

### 3. Native JSON Preset & Macro Engine
- Parse `input_combination`, `output_symbol`, `target_uinput`, and `mapping_type` fields 1:1.
- Support key macros, hold-key combos (`w + d`), disable flags, gamepad axes, and mouse actions.
- Respect `origin_hash` per scancode for exact hardware node discrimination.

### 4. User-Space Daemon & IPC Control
- Runs as a systemd user service (`systemctl --user start stropd`).
- Controlled via Unix Domain Socket (`/run/user/1000/strop.sock`) or CLI:
  ```bash
  stropd load "Razer Tartarus Pro" "gaming-wasd.json"
  stropd apply "Razer Tartarus Pro"
  stropd stop "Razer Tartarus Pro"
  stropd status
  ```
