# Strop support

Strop is a Linux application for configuring Razer peripherals through GTK,
input-remapper, and optional OpenRazer integration. The supported environment is
Ubuntu 26.04 with GNOME on Wayland. Other configurations may work but are outside
the current support scope.

## Requirements

| Component | Purpose |
| --- | --- |
| Python 3, PyGObject, and GTK 4 | Application interface |
| python-evdev | Input device discovery and capture |
| input-remapper | Profile remapping; current integration targets version 2.2.0 |
| OpenRazer (optional) | Supported lighting and hardware controls |
| Desktop StatusNotifier/AppIndicator host | Tray applet; Ubuntu AppIndicators supplies this on the supported GNOME desktop |

The Debian package declares the application dependencies and recommends
input-remapper and OpenRazer. See [README.md](../README.md) for installation.

## Hardware scope

| Device | USB ID |
| --- | --- |
| Razer Tartarus Pro | `1532:0244` |
| Razer BlackWidow V3 | `1532:024e` |
| Razer Naga Trinity | `1532:0067` |

The device catalog provides layout references for additional Razer models.
A catalog entry does not establish hardware support. Available controls depend
on the device, its driver, and the remapping backend.

## Services and permissions

Input-remapper must be installed and its daemon available to apply profiles.
Check it with `systemctl status input-remapper` and
`input-remapper-control --command hello`.

Run Strop as your desktop user. That user needs read access to the relevant
`/dev/input/event*` nodes. If discovery fails, check device permissions and udev
rules, reconnect the device, and rescan. If input-remapper detects a device that
Strop does not, check that python-evdev is installed.

OpenRazer is optional and must be running to use its supported hardware features.
Profile remapping uses input-remapper independently of OpenRazer.

## Known limitations

- The HUD uses X11/XWayland window controls. Positioning and always-on-top behavior
  depend on the compositor and may not work in fullscreen applications.
- The tray uses Gio/D-Bus, without loading GTK3 into the GTK4 application. If the
  desktop tray host is unavailable, Strop keeps the Hub accessible and closing it
  exits the application.
- Strop 1.1 does not expose digital-to-analog stick or trigger bindings. Expanded
  controller mappings and Tartarus key-depth access are planned for 2.0.
- Lighting and other hardware controls depend on what OpenRazer exposes for each
  device.

See [USER_GUIDE.md](USER_GUIDE.md) for profile management and troubleshooting,
[UPGRADING.md](UPGRADING.md) for backup and recovery, and
[the 2.0 roadmap](../ROADMAP_2.0.md) for planned capabilities.
