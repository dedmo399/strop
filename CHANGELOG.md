# Changelog

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
- Improved device discovery diagnostics and documented the Steam PC support target.
- Hardened macro parsing and custom macro storage; built-in templates are protected.
- Corrected supported gamepad-button output serialization and disabled unsupported digital-to-analog bindings.
- Restricted HUD profile and preset display to the selected device and added mapping regression coverage.
- Added installation, permissions, profile management, troubleshooting, backup, and recovery documentation.
- Added automated source, desktop-entry, test, and Debian packaging checks.

The supported platform is Ubuntu 26.04.1 LTS on the Steam PC, using a
`7.0.0-*-generic` kernel, GNOME 50.1 on Wayland, and input-remapper 2.2.0.
The hardware scope is the Razer Tartarus Pro, BlackWidow V3, and Naga Trinity.
See [docs/SUPPORT.md](docs/SUPPORT.md) for runtime details and known limitations,
and [docs/UPGRADING.md](docs/UPGRADING.md) for backup and upgrade instructions.
