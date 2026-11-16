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
| **Strop 1.2** | v1.2.x | **Completed** | Chroma RGB Lighting Studio (16 effects, Cairo HSV/gradient engine), OpenRazer Mouse DPI, D-Bus optimizations, input-remapper 2.2.1+ virtual device filter, and `$XDG_CONFIG_HOME` support. |
| **Strop 1.3 / 1.4** | v1.3.0 → v1.4.0 | **Active Development** | **Phase 3: Infrastructure, HUD & Cross-Distro Packaging.** Migrate D-Bus communication to `dasbus`, clean up and improve the in-game HUD overlay, package Strop for major Linux/GNOME distros (Fedora/RPM, Arch/PKGBUILD, Debian/Ubuntu), add containerized cross-distro test matrices for varying `input-remapper`/`openrazer` versions, integrate headless hardware emulation (`razer-emulator`) in CI, and stabilize into the v1.4.0 release. |
| **Strop 2.0** | v2.0.0 | **Accelerated** | **Phase 2: Roadmap Acceleration.** Tartarus Pro key-depth analog reading (`open-tartarus-driver`, `tartarus-linux`), Huntsman analog input (`razer-analog`), dual-stage actuation, proportional gamepad outputs, and SOCD / Snap Tap neutralization (`doubletap`). |
| **Strop 2.1+** | v2.1.0+ | **Planned** | **Phase 4: Telemetry & Advanced Hardware Controls.** Wireless battery telemetry & UPower integration (`basilisk-battery`, GNOME async tray), HyperScroll tension & profile backups (`RazerTux`), 8K HyperPolling (`evhz`), and multi-layer RGB compositing (`uchroma`). |

---

## 🛠️ New Development Cycle: Strop 1.3 → 1.4 (Phase 3: Infrastructure & Packaging Modernization)

Following upstream `input-remapper`'s migration to `dasbus` ([PR #1201](https://github.com/sezanzeb/input-remapper/pull/1201), [PR #1212](https://github.com/sezanzeb/input-remapper/pull/1212)), Strop begins an active modernization development cycle in version **1.3**. Because Linux distributions (Fedora, Debian, Ubuntu) are dropping unmaintained `pydbus`, Strop will replace its D-Bus client layer to maintain long-term packaging viability. Once verified and stable, this cycle will culminate in the **Strop 1.4.0** stable release.

### Modernization Objectives:
- [ ] **Migrate D-Bus Client from `pydbus` to `dasbus`**:
  - Refactor daemon query mechanisms in `strop_core/presets.py` to use `dasbus.connection.SystemMessageBus` and proxy lookups (`DBusServiceIdentifier(namespace=("inputremapper", "Control"))`).
  - Update D-Bus timeout conventions to milliseconds matching input-remapper PR #1212.
  - Standardize error handling around `dasbus.error.DBusError`.
- [ ] **Dependency & Packaging Modernization**:
  - Add `python3-dasbus` to Debian package dependencies (`build_deb.sh`) and CI test environments (`.github/workflows/ci.yml`).
  - Formally deprecate and remove `pydbus` imports across `strop_core` and `tests/`.
- [ ] **In-Game HUD Cleanup & Visual/UX Improvements**:
  - Audit and refactor `strop_hud.py` and `strop_core/hud.py` to clean up overlay layout rendering, key-cell proportions, typography, and CSS styling across Keypad, Keyboard, and Mouse views.
  - Improve GNOME Wayland / X11 overlay ergonomics, including window placement persistence, scale/opacity tuning, click-through behavior, and live profile reload responsiveness.
- [ ] **Multi-Distro Linux / GNOME Packaging**:
  - Add native packaging definitions for major GNOME/Linux distributions alongside `build_deb.sh`:
    - **Fedora / openSUSE**: RPM `.spec` file and COPR build automation.
    - **Arch Linux**: `PKGBUILD` and `.SRCINFO` for AUR / `makepkg`.
    - **Debian / Ubuntu**: Unified `.deb` package with FreeDesktop AppStream metadata (`com.razer.strop.metainfo.xml`).
- [ ] **Cross-Distro Compatibility & Version-Matrix Testing**:
  - Add a containerized test harness (Podman / Docker and CI matrix jobs across Ubuntu LTS/current, Fedora, Debian, and Arch) to validate Strop against differing distro-packaged versions of `input-remapper` (2.0.x, 2.1.x, 2.2.x+), `openrazer`, Python (3.11–3.14), and GTK4.
  - Add runtime version/capability detection and graceful compatibility shims for upstream differences in `input-remapper` preset schemas, D-Bus methods, and virtual device naming (`phys` / `input-remapper` suffix conventions).
- [ ] **D-Bus Test Suite Realignment & Headless Hardware Emulation**:
  - Update `tests/test_tray_dbus.py` and `tests/test_core.py` D-Bus mocks to align with `dasbus` proxy structures and event loop integration.
  - Implement CI test fixtures modeled after [meeuw/razer-emulator](https://github.com/meeuw/razer-emulator) (utilizing Linux `dummy_hcd` / `libcomposite`) to run automated OpenRazer and input-remapper end-to-end integration tests without physical Razer peripherals.
- [ ] **Stabilization & Release Gate (v1.4.0)**:
  - Validate daemon status polling, profile application, stop requests, and HUD synchronization under real GNOME desktop sessions across target distributions.
  - When all regression checks and live hardware validations pass cleanly, tag and release as **Strop 1.4.0**.

---

## 🎯 Active Priority: Strop 2.0 (Phase 2: Roadmap Acceleration)

Strop 2.0 expands hardware input capabilities beyond digital remapping, unlocking the Tartarus Pro's analog optical switches and establishing correct virtual gamepad axis output within the `input-remapper` ecosystem.

Recent upstream bug fixes in input-remapper 2.2.0 and 2.2.1 have **accelerated Phase 2 implementation** by removing several backend hurdles:
- **Upstream Trigger Release Fix ([PR #1274](https://github.com/sezanzeb/input-remapper/pull/1274))**: Triggers are now correctly treated as released (0) rather than negative joystick deflection, unblocking digital-to-trigger mapping and proportional trigger output (`ABS_Z`, `ABS_RZ`).
- **D-Pad & Joystick Unmapped Direction Preservation ([PR #1274](https://github.com/sezanzeb/input-remapper/pull/1274))**: Unmapped directions are now forwarded rather than swallowed when a combo is mapped, simplifying Tartarus stick and thumbpad handling.
- **Improved Analog Deadzones ([PR #1274](https://github.com/sezanzeb/input-remapper/pull/1274))**: Raised default `analog_threshold` to 30, eliminating noisy scancode collisions during stick recording.
- **Toggle Macro Support ([PR #1183](https://github.com/sezanzeb/input-remapper/pull/1183))**: Native backend support for looping/toggle macros ready for integration in Macro Studio.

The reference hardware and platform scope:
- **Devices**: Razer Tartarus Pro (`1532:0244`), Razer BlackWidow V3 (`1532:024e`), and Razer Naga Trinity (`1532:0067`).
- **Platform**: Ubuntu 26.04 LTS, GNOME on Wayland, Python 3.14, and GTK4.
- Full details in [docs/SUPPORT.md](docs/SUPPORT.md).

### Priority 1: Tartarus Pro & Optical Key-Depth Analog Input

- [ ] **Protocol & Driver Research**:
  - Review [tartarus-linux](https://github.com/ZidoDasZibro/tartarus-linux) (GPL-3.0-or-later Rust implementation), [open-tartarus-driver](https://github.com/ultramonaka/open-tartarus-driver), and [OpenTartarus](https://github.com/moparmaniac412/OpenTartarus) for HID mode-3 unlock and report `0x06` individual key depth readings (`0x00`–`0xFF`). Retain required licensing notices for reused code.
  - Review [meeuw/razer-analog](https://github.com/meeuw/razer-analog) for decoding optical analog key travel and virtual axis translations for Razer Huntsman Analog keyboards (Mini Analog, V2 Analog).
- [ ] **Non-Blocking Depth Helper**:
  - Integrate or adapt a focused helper worker that streams key-depth measurements without blocking the GTK4 main loop.
  - Coordinate device interface access with `input-remapper` and OpenRazer to prevent command conflicts or duplicate event streams.
- [ ] **Live Depth Visualization & Calibration**:
  - Add real-time visual depth meters for each analog key in Keypad Studio and Keyboard Studio.
  - Provide per-key actuation point calibration (minimum, resting deadzone, bottom-out).
- [ ] **Dual-Stage Actuation & Hysteresis**:
  - Implement separate press/release thresholds per key to prevent switch chatter.
  - Support dual-action actuation (e.g. shallow press = walk / tap; deep bottom-out = sprint / macro).
- [ ] **Lifecycle & Fault Tolerance**:
  - Gracefully handle disconnects, permission errors, and helper process crashes.
  - Ensure standard digital input remains fully operational through `input-remapper` upon helper exit or stop.
  - Preserve standard digital profiles and store depth/actuation settings separately in `~/.config/strop/`.

> **Milestone:** Strop displays reliable real-time depth values from the Tartarus Pro and Huntsman Analog devices, provides configurable dual-stage triggers, and safely returns devices to standard operation when stopped.

---

### Priority 2: Controller Output & Proportional Axis Mapping

- [ ] **Gamepad Serialization Modernization**:
  - Replace unsupported legacy shorthand with valid virtual controller events matching `input-remapper`'s supported capabilities.
  - Support held gamepad buttons, bumpers, triggers, and D-pad cardinal/diagonal combinations.
- [ ] **Proportional Stick & Throttle Output**:
  - Feed Tartarus Pro key-depth readings into proportional analog stick directions (`ABS_X`, `ABS_Y`) and analog triggers (`ABS_Z`, `ABS_RZ`).
  - Implement configurable response curves (linear, exponential, s-curve) and deadzones.
- [ ] **Opposing Input & SOCD / Snap Tap Resolution**:
  - Implement a configurable Simultaneous Opposing Cardinal Direction (SOCD) cleaner inspired by [zakack/doubletap](https://github.com/zakack/doubletap) directly in the input pipeline.
  - Support modes: Neutral Cancellation (Left + Right = None), Last-Input-Prioritized (Razer "Snap Tap" behavior for rapid A/D counter-strafing), and First-Input-Prioritized.
  - Ensure immediate neutralization of all axes and release of virtual buttons on profile change, pause, stop, or application exit.
- [ ] **Studio Integration & Profile Persistence**:
  - Enable controller target controls in Keypad Studio as corresponding backend functionality is verified.
  - Guarantee round-trip serialization and preservation of controller mappings in native `input-remapper` preset files.

> **Milestone:** Digital keys reliably actuate gamepad buttons, Tartarus analog keys provide proportional analog movement or throttle in games through input-remapper, and SOCD/Snap Tap clean opposing cardinal directions.

---

### Priority 3: Hardware Coordination & Calibration Settings

- [x] **Unified Lighting Studio**: Integrated Chroma RGB Studio with 16 presets, Cairo HSV color picker, and per-device zone previews (*shipped in v1.2.0*).
- [x] **Mouse Sensor Settings**: Independent X/Y DPI stages, polling rate selector, and per-device persistence (*shipped in v1.2.0*).
- [ ] **Tartarus Depth Coordination**:
  - Coordinate Tartarus Pro depth streaming with OpenRazer lighting updates to prevent USB endpoint contention.
  - Save per-device depth calibration profiles in `~/.config/strop/` alongside mouse settings.

---

## 🔮 Future Development Cycle: Strop 2.1+ (Phase 4: Telemetry & Advanced Hardware Controls)

Following the stabilization of analog depth and virtual controller mappings in Strop 2.0, the **Strop 2.1+** release cycle expands hardware telemetry, battery power management, advanced mouse controls, and multi-layer RGB compositing by integrating proven techniques from the broader Linux peripheral community:

### 1. Wireless Battery Monitoring & Native Desktop Telemetry
- [ ] **Asynchronous Battery & Charging Polling**:
  - Implement non-blocking background polling for wireless mice and dongles inspired by [bl3xand/Razer-Battery-Indicator](https://github.com/bl3xand/Razer-Battery-Indicator-Gnome-Extension) and [HoroTW/RazerBatteryTray](https://github.com/HoroTW/RazerBatteryTray), ensuring sleeping wireless peripherals never block the GTK4 main loop.
- [ ] **Linux UPower D-Bus Integration**:
  - Adapt 2.4GHz receiver power telemetry techniques from [arkady-emelyanov/basilisk-battery](https://github.com/arkady-emelyanov/basilisk-battery) to bridge battery levels directly into standard Linux desktop power managers (GNOME/UPower) without requiring external daemons.
- [ ] **Tray & HUD Battery Badges**:
  - Display live battery percentages, charging animations, and configurable low-battery desktop notifications in the Strop GTK4 StatusNotifier tray applet, Hub, and in-game HUD overlays.

### 2. Advanced Mouse Controls & HyperPolling
- [ ] **HyperScroll Tension & Resistance Tuning**:
  - Integrate scroll wheel mode switching (free-spin vs. tactile) and electronic resistance control for supported mice (Naga V2 Pro, Basilisk V3 Pro) utilizing control bytes researched by [anoraknophobia/RazerTux](https://github.com/anoraknophobia/RazerTux).
- [ ] **Onboard Profile Backup & Recovery**:
  - Add import, export, and backup tools for mouse hardware memory profiles using reverse-engineered formats documented in `RazerTux`.
- [ ] **High Polling Rate (2K / 4K / 8KHz) & Latency Verification**:
  - Expand `strop_core/dpi.py` supported polling rate table beyond 1000Hz for Razer HyperPolling Wireless Dongles and wired 8K mice (Viper 8KHz, DeathAdder V3 Pro).
  - Implement an integrated real-time polling rate verification widget in Mouse Studio using low-overhead `evdev` timestamp delta tracking inspired by [evhz](https://gitlab.com/iankelling/evhz).

### 3. Multi-Layer Chroma RGB Compositing
- [ ] **Multi-Layer Lighting Engine**:
  - Evolve Strop's Cairo lighting engine to support layered effect composition inspired by [hyperb1iss/uchroma](https://github.com/hyperbliss/uchroma) (e.g. stacking dynamic reactive keypress ripples or starlight on top of base breathing/gradient layers).
- [ ] **Community Effect Presets**:
  - Expand built-in procedural lighting effects with community routines from [codanaut/openrazer-effects](https://github.com/codanaut/openrazer-effects) and direct USB-HID controls from [open-razerkit](https://github.com/HamzaYslmn/open-razerkit).

---

## 📚 Community Reference Projects & Upstream Prior Art

Strop acknowledges and draws technical guidance from the following open-source projects across the Linux peripheral and reverse-engineering ecosystem:

| Project | Primary Capability | Intended Strop Touchpoint | Upstream License |
|:---|:---|:---|:---|
| **[meeuw/razer-emulator](https://github.com/meeuw/razer-emulator)** | Software USB emulation via `dummy_hcd` & `libcomposite` | Headless CI test fixtures for `.github/workflows/ci.yml` (v1.4) | GPL-3.0-or-later |
| **[ultramonaka/open-tartarus-driver](https://github.com/ultramonaka/open-tartarus-driver)** | Tartarus Pro HID Mode 3 unlock & 0x06 depth report streaming | Keypad Studio real-time depth helper & dual-stage actuation (v2.0) | MIT |
| **[moparmaniac412/OpenTartarus](https://github.com/moparmaniac412/OpenTartarus)** | Tartarus Pro Linux tray, analog stick mapping, and RGB controls | Analog key depth visualization and profile coordination (v2.0) | GPL-3.0-or-later |
| **[meeuw/razer-analog](https://github.com/meeuw/razer-analog)** | Huntsman Mini/V2 optical analog switch capture & `uinput` mapping | Keyboard Studio continuous optical depth & joystick axes (v2.0) | GPL-3.0-or-later |
| **[zakack/doubletap](https://github.com/zakack/doubletap)** | Low-latency Linux `evdev` SOCD cleaner / Snap Tap engine | Opposing input neutralization & Snap Tap mode in Macro Studio (v2.0) | GPL-3.0-or-later |
| **[arkady-emelyanov/basilisk-battery](https://github.com/arkady-emelyanov/basilisk-battery)** | 2.4GHz receiver battery reporting to Linux `UPower` D-Bus | Native UPower desktop power integration & Hub telemetry (v2.1+) | MIT |
| **[bl3xand/Razer-Battery-Indicator](https://github.com/bl3xand/Razer-Battery-Indicator-Gnome-Extension)** | Non-blocking async wireless battery polling for GNOME | Tray applet & HUD live wireless battery indicator badges (v2.1+) | GPL-3.0-or-later |
| **[anoraknophobia/RazerTux](https://github.com/anoraknophobia/RazerTux)** | Naga V2 Pro HyperScroll tension, stages, and onboard backup | Mouse Studio electronic scroll wheel tuning & memory backups (v2.1+) | GPL-3.0-or-later |
| **[evhz](https://gitlab.com/iankelling/evhz)** | Real-time USB polling rate measurement tool | Mouse Studio live polling rate verification widget (v2.1+) | GPL-3.0-or-later |
| **[hyperb1iss/uchroma](https://github.com/hyperbliss/uchroma)** | Asyncio Chroma driver with multi-layer RGB framebuffer engine | Lighting Studio multi-layer effect compositing architecture (v2.1+) | GPL-3.0-or-later |
| **[codanaut/openrazer-effects](https://github.com/codanaut/openrazer-effects)** | Community Python Chroma effect scripts and patterns | Procedural animation catalog expansion (v2.1+) | MIT |


---

## 📜 Completed Foundation (Strop 1.0 - 1.2)

### Strop 1.2.1
- **Upstream Forwarded Device Filtering**: Updated hardware scanning to inspect device `phys` attributes and exclude input-remapper 2.2.1+ virtual devices (`phys="input-remapper/*"`), preventing duplicate device detection and origin-hash collisions.
- **Dynamic `$XDG_CONFIG_HOME` Support**: Standardized base path resolution across Strop configs, active profiles, macro storage, mouse DPI settings, lighting profiles, and input-remapper-2 presets directories.

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
