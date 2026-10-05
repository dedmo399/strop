# Strop 1.0 release scope

Strop 1.0 provides a stable profile workflow using input-remapper, with documented
hardware support and known backend limitations. The 1.0 roadmap is closed.
The remaining verification and publication prerequisites were removed at the
maintainer's request; they are not represented as completed tests.

## Included in 1.0

- Profile validation, atomic writes, and accurate save/apply/stop status.
- Actionable device, permission, daemon, and disconnect diagnostics.
- Preset round trips that preserve mappings, labels, and output targets.
- Hardened macro parsing and protected built-in macro templates.
- HUD profile and mapping display restricted to the selected device.
- Debian packaging and automated source, test, desktop-entry, and package checks.
- Installation, first-run, troubleshooting, backup, and recovery documentation.

## Support scope

The Steam PC running Ubuntu 26.04.1 LTS, a `7.0.0-*-generic` kernel, GNOME 50.1
on Wayland, Python 3.14.4, GTK 4.22.4, and input-remapper 2.2.0 is the sole
supported configuration. The Razer Tartarus Pro, BlackWidow V3, and Naga Trinity
are the supported devices. Full details are in [docs/SUPPORT.md](docs/SUPPORT.md).

Physical profile mappings, preset round trips, HUD updates, fresh installation,
uninstall behavior, and upgrade data preservation were verified on this setup.
An isolated backup restoration drill also recovered all configuration files
byte-for-byte. This does not establish testing of restored profiles in the app.

## Known limitations

Digital-to-analog stick and trigger bindings are unavailable with the supported
backend. D-pad-to-gamepad outputs and optional lighting remain unverified.
These are documented limitations rather than additional 1.0 release requirements.
Other hardware and desktop configurations remain outside the support matrix.

The active development plan is [ROADMAP_2.0.md](ROADMAP_2.0.md).
The native `stropd` daemon remains an architectural reference in
[ROADMAP_NATIVE_DAEMON.md](ROADMAP_NATIVE_DAEMON.md).
Release changes are recorded in [CHANGELOG.md](CHANGELOG.md).
