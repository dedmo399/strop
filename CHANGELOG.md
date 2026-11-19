# Changelog

## 1.3.2

- Added KDE Plasma (Wayland & X11) desktop integration:
  - Added `strop_core/desktop.py` with KDE/GNOME and Wayland/X11 session detection and KWin D-Bus scripting (`org.kde.kwin.Scripting`) keep-above/placement support for the HUD overlay on KDE Wayland (falling back cleanly to X11/XWayland `pin_window_on_top`).
  - Forced `gtk-application-prefer-dark-theme = True` and added explicit `headerbar`, `popover`, and `dropdown` CSS rules in `strop_core/theme.py` so Strop's dark slate palette renders consistently under Breeze-GTK.
  - Added test coverage for KDE desktop detection, KWin D-Bus pinning, dark-theme settings, and `DBusMenu` group methods (`AboutToShowGroup`, `EventGroup`) used by Plasma's StatusNotifier host.

## 1.3.1

- Added Arch Linux and CachyOS packaging support (`packaging/arch/PKGBUILD`, `packaging/arch/.SRCINFO`, `build_arch.sh` with native `makepkg` and Docker/Podman container build support, plus CI Arch package verification).
- Fixed HUD overlay top toolbar controls (transparency, profile selector, apply/stop, refresh, collapse, close) by replacing the container-wide `Gtk.GestureDrag` grab with `Gtk.WindowHandle`, and shortened the HUD status badge to compact `Active: <profile>` / `Stopped` labels.
- Hardened X11 window pinning (`ctypes` signatures, resource cleanup, strict title matching), `EV_REL` scroll-wheel mapping and round-trip isolation, non-Razer vendor filtering, modifier/combo recording, macro built-in save IDs, preset autoload sync, OpenRazer reconnect handling, and studio window lifecycle cleanup.

## 1.3.0

- Migrated the input-remapper D-Bus client from `pydbus` to `dasbus` (`DBusServiceIdentifier` proxy, millisecond timeouts, `DBusError` handling) with a cached, thread-safe system bus connection that resets after D-Bus errors.
- Hardened D-Bus fallback handling so Strop degrades cleanly to the `input-remapper-control` CLI if `dasbus` is unavailable.
- Added `python3-dasbus` to Debian package dependencies and CI workflows.

## 1.2.2

- Refined hardware catalog metadata (`strop_core/catalog.py`) and updated the architectural roadmap (`ROADMAP.md`) for the 1.3/1.4 and 2.0 cycles.
- Added the GitHub Pages studio showcase (`site/`) and dynamic asset staging in `.github/workflows/pages.yml`, eliminating duplicate repository binaries and keeping the source release tarball compact (~2.2 MB).
- Consolidated project metadata and test configuration in `pyproject.toml`, added `.gitattributes` and `.mailmap`, removed redundant root `.sh` wrapper scripts, and single-sourced `VERSION` and `strop.desktop` in `build_deb.sh`.
- Hardened `.github/workflows/ci.yml` with explicit read permissions, concurrency cancellation, dynamic version extraction, and `input-remapper >= 2.2.0` compatibility checks.

## 1.2.1

- Fixed hardware discovery to inspect device `phys` attributes and exclude input-remapper 2.2.1+ virtual forwarded devices (`phys="input-remapper/*"`), preventing duplicate device detection and origin-hash collisions when profiles are actively injected.
- Added full support for `$XDG_CONFIG_HOME` across Strop configuration paths, active profiles, custom macros, mouse sensor settings, lighting profiles, and input-remapper preset directories.
- Expanded automated test coverage for legacy and 2.2.1+ virtual device filtering and dynamic XDG base configuration path resolution.

## 1.2.0

- Added Unified RGB Lighting & Chroma Effects Studio (`strop_lighting.py`, `/usr/bin/strop-lighting`, `lighting.sh`, `strop_core/lighting.py`, `strop_core/lighting_widgets.py`) with a 60 FPS render engine, 16 lighting presets, interactive Cairo HSV color wheel + SV square, multi-stop gradient editor, global master synchronization, and 2D vector zone mapping across Keyboards, Keypads, Mice, and Controllers.
- Added OpenRazer Mouse DPI, stage table, and polling rate controller (`strop_core/dpi.py`) with hardware capability discovery, read-back verification, per-device persistence in `~/.config/strop/mouse_settings.json`, and integrated controls in Mouse Studio (`strop_mouse.py`).
- Optimized input-remapper daemon and injection status checks via direct D-Bus queries (`pydbus`) and added a 30-second cache for device key enumeration to eliminate subprocess overhead and daemon log spam.
- Synchronized `~/.config/input-remapper-2/config.json` autoload mappings automatically when applying or clearing active profiles.
- Improved tray menu stability by tracking menu open/closed state to defer layout updates while open, emitting `ItemsPropertiesUpdated` when layout structure is unchanged, restricting `AboutToShow` refresh to the root menu, and initializing daemon status synchronously.
- Expanded hardware discovery, catalog metadata, and studio launchers across the Hub, Tray, and `strop_studio.py` (`--lighting`).

## 1.1.1

- Added the `/usr/bin/strop-studio` CLI wrapper to the Debian package.
- Fixed diagonal D-Pad combination preset loading so intrinsic combo keys round-trip without clobbering cardinal D-Pad bindings.
- Prevented cleared keys with leftover custom labels from serializing invalid empty `output_symbol` entries, and cleared custom labels during batch keypad resets.
- Handled invalid macro syntax gracefully with toast warnings in Macro Studio.
- Added ambidextrous right-side mouse buttons to Mouse Studio and verified OpenRazer lighting status before reporting success.
- Restored active recording button styling and cleaned up duplicate HUD CSS rules and launcher scripts.

## 1.1.0

- Flushed managed HUD shutdown requests before releasing their D-Bus connection, fixing an intermittent quit-action delivery failure.
- Added a GTK4-compatible tray applet with device studio launchers, profile apply/stop controls, backend status, and HUD visibility controls.
- Made the Hub single-instance; closing it keeps Strop in the tray when desktop tray support is available. Quit closes managed HUDs without stopping remapping or closing studios.
- Added one HUD instance per device with show, hide, refresh, and quit actions.
- Displayed factory default keys below physical HUD labels when no custom setting exists, including unmapped keys in partial profiles.
- Cleared stale HUD bindings when presets disappear or fail to load.
- Excluded input-remapper virtual outputs from hardware discovery and studio selection, preserving physical-device mapping hashes.
- Simplified hardware, selector, tray, and studio labels to model names while retaining existing profile identities.

## 1.0.0

- Stabilized profile save, apply, and stop outcomes, with atomic preset and state writes.
- Improved device discovery diagnostics and documented the platform support target.
- Hardened macro parsing and custom macro storage; built-in templates are protected.
- Corrected supported gamepad-button output serialization and disabled unsupported digital-to-analog bindings.
- Restricted HUD profile and preset display to the selected device and added mapping regression coverage.
- Added installation, permissions, profile management, troubleshooting, backup, and recovery documentation.
- Added automated source, desktop-entry, test, and Debian packaging checks.

The supported platform is Ubuntu 26.04 LTS, GNOME on Wayland, Python 3.14, and GTK4, with input-remapper 2.2.0.
The hardware scope is the Razer Tartarus Pro, BlackWidow V3, and Naga Trinity.
See [docs/SUPPORT.md](docs/SUPPORT.md) for runtime details and known limitations,
and [docs/UPGRADING.md](docs/UPGRADING.md) for backup and upgrade instructions.
