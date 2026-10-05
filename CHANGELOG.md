# Changelog

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
