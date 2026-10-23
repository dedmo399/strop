# 🗡️ Strop — Razer Linux Peripheral Suite

<div align="center">
  <img src="assets/strop_icon.png" width="160" alt="Strop Logo" />
  <h3>Putting the sharpest edge on your Razer gaming hardware on Linux.</h3>
  <p>Native GTK4 Remap Studios • In-Game Heads-Up Displays • Unified Device Hub • input-remapper Integration • 230+ Catalog Layouts</p>
</div>

![Strop Hub, Keypad Studio, Macro Studio, and keypad HUD with a Warframe profile](docs/screenshots/strop-suite.png)

---

## AI disclosure and disclaimer

Strop was created with substantial assistance from generative AI, including AI-generated code and documentation. AI assistance is part of the project's development process and may also be used for future changes. This project should not be understood as entirely human-written software.

AI-generated work can contain bugs, incorrect assumptions, and inaccurate descriptions of hardware or software behavior. The use of AI does not establish that the code has received an independent review, security audit, or comprehensive hardware testing. Device catalog entries and feature descriptions are not proof of compatibility; consult the [support matrix](docs/SUPPORT.md) for the project's stated support scope and limitations.

The maintainer remains responsible for what is accepted and released. Please evaluate Strop against your own needs, back up your remapping profiles before making changes, and report problems through the [issue tracker](https://github.com/dedmo399/strop/issues). The warranty disclaimer in the [project license](LICENSE) applies.

---

## Source repository

The primary source for Strop is [dedmo399/strop on GitHub](https://github.com/dedmo399/strop). The `main` branch is the canonical development branch.

Clone the repository over HTTPS:

```bash
git clone https://github.com/dedmo399/strop.git
cd strop
```

For an existing checkout, get the latest committed source with `git pull --ff-only` on `main`. To propose a change, follow [CONTRIBUTING.md](CONTRIBUTING.md). Generated `.deb` and `.tar.gz` packages stay out of source control; build them with `./build_deb.sh`.

---

## 🧰 Platform and support

The **only official 1.1 support target** is the Steam PC running Ubuntu 26.04.1 LTS, GNOME 50.1 on Wayland, Python 3.14.4, GTK 4.22.4, and input-remapper 2.2.0. The hardware scope remains the Razer Tartarus Pro, BlackWidow V3, and Naga Trinity listed in the [support matrix](docs/SUPPORT.md).

Strop's catalog contains 230+ device entries and generic layout archetypes. Catalog presence is reference data; it does not mean a device has been tested or is officially supported. Other distributions, sessions, backend versions, and devices are outside the 1.1 support commitment.

Strop uses **Python 3**, **PyGObject**, **GTK 4**, and **python-evdev**. Hardware remapping requires **input-remapper**; OpenRazer is optional for supported lighting integration. The Debian package declares these runtime dependencies. Follow the [support and setup notes](docs/SUPPORT.md) for device permissions and session limitations.

- **Macro Studio & Composer**: Built-in gaming combos such as Bullet Jump and Ability Combos, plus productivity shortcuts with custom millisecond delays.
- Polychromatic dark slate & emerald theme design language.


---

## 🚀 Suite Applications

### 1. **Strop Hub & Tray Applet** (`./strop.py` or `./strop.sh`)
The central dashboard scans connected Razer input devices and launches the studios. Its 230+ entry catalog provides layout references; those devices are not thereby verified or supported.

Strop 1.1 starts a tray applet alongside the Hub. Use its device menus to open studios, apply saved profiles, stop remapping, and show or hide keypad HUDs. Device and profile status refreshes every five seconds. Reopening Strop presents the existing Hub.

Closing the Hub keeps Strop running when desktop tray support is available. **Quit Strop** closes the Hub, tray, and HUDs started through the Hub or tray; studios and applied remapping profiles keep running. If tray support is unavailable, closing the Hub exits Strop. Login autostart is not enabled.

### 2. **Strop Keypad Studio** (`./strop_keypad.py` or `./keypad.sh`)
- **Keypad Matrix**: Physical 1:1 layout (Keys 01–19, Scroll Up, Scroll Down, 8-Way D-pad, Thumb Button, Spacebar) for Tartarus Pro, Tartarus V2, Orbweaver, and Nostromo.
- **Gamepad button outputs**: Bind keypad keys to supported single gamepad buttons. Analog stick and trigger binding from digital keys is unavailable with the supported input-remapper backend.
- **Auto-Detection on Execution**: Scans USB devices and calculates hardware capabilities `origin_hash`.
- **Live Key Recording / Input Capture (`[ 🔴 Capture Input ]`)**: Record physical key combinations directly.
- **Preset Importer & Exporter**: Direct integration with `input-remapper-2`.

### 3. **Strop Keyboard Studio** (`./strop_keyboard.py` or `./keyboard.sh`)
- **Full-Size Mechanical Keyboard Diagram (108 Keys)**: Complete ANSI 60% matrix, navigation/editing cluster, arrow keys, numpad, and digital multi-function media roller.
- **Layout archetypes**: Full-size, Tenkeyless (TKL), 75%, 65%, 60% Mini, and Blade laptop layouts. These are catalog/layout references; see the support matrix for verified device scope.
- **Gamepad button outputs**: Assign supported single gamepad buttons to keyboard keys. Digital-to-analog stick and trigger mappings are unavailable with the supported input-remapper backend.
- **Full Studio Dock**: Key inspector, input recorder, gamepad palette, and input-remapper-2 preset management.

### 4. **Strop Mouse Studio** (`./strop_mouse.py` or `./mouse.sh`)
- **Multi-Plate Modular Support**:
  - **Naga MMO 12-Button Mechanical Side Grid** (Naga Trinity / Pro / V2 / Chroma / Epic / X).
  - **Naga Hex & Radial Side Plate** (Naga Trinity Hex, Naga Hex V2).
  - **FPS & Ergonomic Side Plate** with Multi-Function DPI Clutch & Tilt-Wheel (Basilisk V3 / Pro, DeathAdder V2 / V3, Viper, Cobra, Mamba, Orochi, Abyssus).
  - **Ambidextrous Dual Side Buttons** (Viper, Ouroboros, Taipan, Lancehead).
  - **Gamepad Action Palette**: Assign supported single controller-button outputs. Analog triggers are not supported from digital inputs by the current backend.

### 5. **Strop Macro Studio** (`./strop_macro.py`)
- **Visual Sequence Timeline**: Visual vertical step builder to insert keypresses, mouse clicks, and custom millisecond delay pauses.
- **Custom Macro Library**: Organize, search, and save custom macros directly in `~/.config/strop/macros.json`.
- **Integrated Hardware Assignment**: Any macro built in Macro Studio is instantly available for 1-click assignment across all keypads, keyboards, and mice.

### 6. **Strop Universal Parameterized Studio** (`./strop_studio.py`)
- Launch studio for any device by name:
  ```bash
  ./strop_studio.py --device="Razer Naga Pro"
  ./strop_studio.py --device="Razer Huntsman Mini"
  ./strop_studio.py --device="Razer Tartarus Pro"
  ./strop_studio.py --list
  ```

### 7. **Strop In-Game HUD Overlay** (`./strop_hud.py` or `./hud.sh`)
- **Frameless Glassmorphism Floating Window**: Semi-translucent overlay that requests always-on-top positioning through X11/XWayland. Fullscreen visibility and positioning depend on the compositor and game; see [known limitations](docs/SUPPORT.md#known-limitations).
- **Physical Layout Mirror**: 5-row keypad layout, aligned scroll wheel, thumb button, and D-pad.
- **Default Key Labels**: Shows each factory binding below its physical key number when there is no custom label or binding. Unmapped keys in partial profiles show their defaults too.
- **Per-Device Windows**: Repeated launches present the same HUD for that device. Tray hiding preserves its current position, opacity, and collapsed state.
- **Gamepad Badge Recognition**: Displays clean analog stick and controller badges (`LS↑`, `LS↓`, `(A)`, `(B)`, `LT`, `RT`, etc.).
- **Live Preset Switcher**: Switch active profiles directly in-game.

---

## 🎮 Quick Launch Commands

```bash
# Unified Hub Dashboard & 230+ Device Catalog
./strop.py

# Dedicated Macro Studio
./strop_macro.py

# Generic Keypad Studio (Tartarus / Orbweaver / Nostromo)
./strop_keypad.py

# Generic Keyboard Studio (BlackWidow / Huntsman / DeathStalker / Blade)
./strop_keyboard.py

# Generic Mouse Studio (Naga MMO / Basilisk FPS / Viper Ambi)
./strop_mouse.py

# In-Game HUD Overlay
./strop_hud.py

# Universal Studio CLI
./strop_studio.py --device="<Device Name>"
```

---

## 📦 Installation & Packaging

The official 1.1 target is Ubuntu 26.04.1 LTS on the Steam PC. Other distributions are not in the support matrix.

### Install Debian Package (.deb)
Download `strop_1.1.0_all.deb`, `strop_1.1.0.tar.gz`, and `SHA256SUMS` from the [Strop 1.1.0 release](https://github.com/dedmo399/strop/releases/tag/v1.1.0) into the same directory. Verify both downloads before installing:

```bash
sha256sum --check SHA256SUMS
```

Both files should report `OK`. Checksums detect corrupted or changed downloads; they are not an independent signature of the release. If verification fails, download the files again before proceeding.

Install the verified Debian package with `apt`:
```bash
sudo apt install ./strop_1.1.0_all.deb
```

To build fresh `.deb` and `.tar.gz` release artifacts at any time:
```bash
./build_deb.sh
```

Source checkout launchers use the `./strop*.py` commands above. To add an installed package to the application menu, install the `.deb`; it provides a system desktop entry and icons.

See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for first-run and profile steps. [docs/SUPPORT.md](docs/SUPPORT.md) lists the platform matrix, device scope, package requirements, permission guidance, and Wayland/XWayland limitations. [docs/UPGRADING.md](docs/UPGRADING.md) explains backup, upgrade, and recovery steps. [CHANGELOG.md](CHANGELOG.md) describes the 1.1 release. Catalog models not listed in the support matrix are not part of official 1.1 support.

The active [Strop 2.0 roadmap](ROADMAP_2.0.md) prioritizes Tartarus Pro key-depth access, correct controller-output mappings, and unified hardware settings.

---

## Help and contributions

For setup and troubleshooting, read the [user guide](docs/USER_GUIDE.md) and [support matrix](docs/SUPPORT.md). Report ordinary bugs through the [issue tracker](https://github.com/dedmo399/strop/issues/new/choose), using the bug-report template. See [CONTRIBUTING.md](CONTRIBUTING.md) for development and testing guidance, and [SECURITY.md](SECURITY.md) for handling suspected vulnerabilities.

---

## 📜 Version & License

- **Version**: `1.1.0`
- **License**: [GNU General Public License v3.0 or later](LICENSES.md) (`GPL-3.0-or-later`); full license text: [LICENSE](LICENSE).

Maintained by Strop Contributors. Source and issue tracking: [dedmo399/strop](https://github.com/dedmo399/strop).
