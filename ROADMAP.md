# 🗺️ Strop Roadmap

This document outlines the development roadmap, architectural principles, and active priorities for **Strop** — the native Linux peripheral configuration studio, RGB lighting suite, and HUD overlay for Razer hardware.

---

## 🏛️ Architectural Foundation: input-remapper & OpenRazer Commitment

Strop is designed from the ground up as a native GTK4 graphical studio and HUD layer that **always follows and depends on** two foundational Linux projects:

1. **[input-remapper](https://github.com/sezanzeb/input-remapper)**: The authoritative engine for Linux input event capture, scancode remapping, macro injection, and virtual `uinput` devices. Strop reads, writes, validates, and manages native `~/.config/input-remapper-2/` JSON preset configurations and uses the `input-remapper-daemon` D-Bus service for applying and monitoring profiles.
2. **[OpenRazer](https://openrazer.github.io/)**: The authoritative kernel-driver and daemon suite for Razer hardware communication, Chroma RGB lighting matrices, DPI stages, and polling-rate telemetry.

**Strop will not replace or compete with input-remapper or OpenRazer.** All roadmap features — including expanded controller mappings and Tartarus Pro key-depth workflows — are engineered to coordinate directly with and extend these upstream services without introducing conflicting standalone daemons or conflicting grabs.

---

## 📌 Roadmap Overview & Current Status

| Milestone | Target | Status | Focus Areas |
|:---|:---|:---|:---|
| **Strop 1.0** | v1.0.0 | **Completed** | Core remapping, input-remapper backend, preset validation, atomic writes, device HUD, Debian packaging. |
| **Strop 1.1** | v1.1.x | **Completed** | Single-instance Hub, GTK4/D-Bus tray applet, multi-device HUD management, D-pad combo preservation. |
| **Strop 1.2** | v1.2.0 | **Completed** | Chroma RGB Lighting Studio (16 effects, Cairo HSV/gradient engine), OpenRazer Mouse DPI/polling rate, D-Bus optimizations. |
| **Strop 2.0** | v2.0.0 | **Active Work** | Tartarus Pro key-depth analog reading, dual-stage actuation, proportional gamepad outputs, axis response curves. |
| **Future Enhancements** | 2.x+ | **Planned** | Expanded OpenRazer device telemetry, community macro presets, multi-device profile autoswitching. |

---

## 🎯 Active Priority: Strop 2.0

Strop 2.0 expands hardware input capabilities beyond digital remapping, unlocking the Tartarus Pro's analog optical switches and establishing correct virtual gamepad axis output within the `input-remapper` ecosystem.

The reference hardware and platform scope:
- **Devices**: Razer Tartarus Pro (`1532:0244`), Razer BlackWidow V3 (`1532:024e`), and Razer Naga Trinity (`1532:0067`).
- **Platform**: Ubuntu 26.04 LTS, GNOME on Wayland, Python 3.14, and GTK4.
- Full details in [docs/SUPPORT.md](docs/SUPPORT.md).

### Priority 1: Tartarus Pro Key-Depth & Analog Input

- [ ] **Protocol & Driver Research**:
  - Review [tartarus-linux](https://github.com/ZidoDasZibro/tartarus-linux) (GPL-3.0-or-later Rust implementation) and [open-tartarus-driver](https://github.com/ultramonaka/open-tartarus-driver) for HID mode-3 unlock and report `0x06` individual key depth readings. Retain required licensing notices for reused code.
- [ ] **Non-Blocking Depth Helper**:
  - Integrate or adapt a focused helper worker that streams key-depth measurements without blocking the GTK4 main loop.
  - Coordinate device interface access with `input-remapper` and OpenRazer to prevent command conflicts or duplicate event streams.
- [ ] **Live Depth Visualization & Calibration**:
  - Add real-time visual depth meters for each analog key in Keypad Studio.
  - Provide per-key actuation point calibration (minimum, resting deadzone, bottom-out).
- [ ] **Dual-Stage Actuation & Hysteresis**:
  - Implement separate press/release thresholds per key to prevent switch chatter.
  - Support dual-action actuation (e.g. shallow press = walk / tap; deep bottom-out = sprint / macro).
- [ ] **Lifecycle & Fault Tolerance**:
  - Gracefully handle disconnects, permission errors, and helper process crashes.
  - Ensure standard digital input remains fully operational through `input-remapper` upon helper exit or stop.
  - Preserve standard digital profiles and store depth/actuation settings separately in `~/.config/strop/`.

> **Milestone:** Strop displays reliable real-time depth values from the Tartarus Pro, provides configurable dual-stage triggers, and safely returns the device to standard operation when stopped.

---

### Priority 2: Controller Output & Proportional Axis Mapping

- [ ] **Gamepad Serialization Modernization**:
  - Replace unsupported legacy shorthand with valid virtual controller events matching `input-remapper`'s supported capabilities.
  - Support held gamepad buttons, bumpers, triggers, and D-pad cardinal/diagonal combinations.
- [ ] **Proportional Stick & Throttle Output**:
  - Feed Tartarus Pro key-depth readings into proportional analog stick directions (`ABS_X`, `ABS_Y`) and analog triggers (`ABS_Z`, `ABS_RZ`).
  - Implement configurable response curves (linear, exponential, s-curve) and deadzones.
- [ ] **Opposing Input & Neutralization Rules**:
  - Enforce consistent behavior for simultaneous opposing directions (e.g. simultaneous left + right, forward + backward) with neutral resolution.
  - Ensure immediate neutralization of all axes and release of virtual buttons on profile change, pause, stop, or application exit.
- [ ] **Studio Integration & Profile Persistence**:
  - Enable controller target controls in Keypad Studio as corresponding backend functionality is verified.
  - Guarantee round-trip serialization and preservation of controller mappings in native `input-remapper` preset files.

> **Milestone:** Digital keys reliably actuate gamepad buttons, and Tartarus analog keys provide proportional analog movement or throttle in games through input-remapper.

---

### Priority 3: Hardware Coordination & Calibration Settings

- [x] **Unified Lighting Studio**: Integrated Chroma RGB Studio with 16 presets, Cairo HSV color picker, and per-device zone previews (*shipped in v1.2.0*).
- [x] **Mouse Sensor Settings**: Independent X/Y DPI stages, polling rate selector, and per-device persistence (*shipped in v1.2.0*).
- [ ] **Tartarus Depth Coordination**:
  - Coordinate Tartarus Pro depth streaming with OpenRazer lighting updates to prevent USB endpoint contention.
  - Save per-device depth calibration profiles in `~/.config/strop/` alongside mouse settings.

---

## 📜 Completed Foundation (Strop 1.0 - 1.2)

### Strop 1.2.0
- **Chroma RGB Lighting Studio**: Standalone and embedded lighting studio with Cairo-rendered HSV color wheel, multi-stop gradient editor, 16 procedural effects, zone grouping, and master multi-device synchronization via OpenRazer.
- **OpenRazer Mouse Settings**: Hardware capability discovery, multi-stage DPI management with X/Y link/unlink, polling rate controls, and configuration persistence.
- **IPC & Performance Hardening**: Direct D-Bus queries via `pydbus`, 30-second key enumeration caching, and synchronized autoload configurations for `input-remapper`.

### Strop 1.1.0 & 1.1.1
- **System Tray Integration**: GTK4/D-Bus StatusNotifierItem tray applet with device studio launchers, profile selectors, daemon status indicators, and HUD toggles.
- **Single-Instance Hub**: Clean background minimizing with tray support and robust application lifecycle management.
- **Multi-Device In-Game HUD**: Independent HUD overlays per device with unmapped key fallbacks and quit-action flush synchronization.
- **Mapping Preservation**: Diagonal D-pad combo preservation and empty mapping safeguards.

### Strop 1.0.0
- **Core Remapping Workflow**: Input-remapper profile validation, atomic preset writes, and accurate status tracking.
- **Hardware Catalog**: Archetype heuristics and layouts for Tartarus Pro, BlackWidow V3, and Naga Trinity.
- **Macro Engine**: Hardened DSL sequence parser, built-in templates, and custom macro persistence.
- **Packaging & Delivery**: Debian packaging files, desktop entries, and multi-scale application icons.

---

## 🧪 Testing, Validation & Packaging Standards

All roadmap implementations must adhere to the following quality gates:

1. **Test Coverage**:
   - Protocol replay tests for analog depth reports (valid, malformed, out-of-order, incomplete).
   - Controller serialization, state transitions, opposing input resolution, and preset round trips.
   - Non-regression coverage for existing digital profiles and OpenRazer device simulations.
2. **Backend Integrity**:
   - Complete adherence to `input-remapper` JSON formats and daemon lifecycle.
   - Physical hardware must never be left in an unresponsive or grabbed state when Strop exits or crashes.
   - Clean neutralization of virtual controller axes upon any stop or error condition.
3. **Packaging & Upstream Alignment**:
   - Rely strictly on system packaging and package dependencies (`input-remapper`, `openrazer-meta` / `openrazer-daemon`).
   - Strict adherence to the platform support matrix documented in [docs/SUPPORT.md](docs/SUPPORT.md).
