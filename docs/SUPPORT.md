# Strop 1.0 support matrix

Strop 1.0 has one official platform target: the `steam` PC configuration below. Other operating systems, distributions, desktop sessions, input-remapper/OpenRazer versions, and devices are outside the 1.0 support commitment unless this document is updated after verification.

## Platform target

| Component | Supported target observed on `steam` |
| --- | --- |
| Distribution | Ubuntu 26.04.1 LTS (Resolute Raccoon), amd64 |
| Kernel | Linux 7.0.0-34-generic |
| Desktop session | GNOME 50.1, Wayland |
| GTK | GTK 4.22.4; PyGObject 3.56.2 |
| Python | Python 3.14.4 |
| Input discovery | python3-evdev 1.9.3 |
| Mapping backend | input-remapper 2.2.0; daemon responds to its control CLI |
| Optional lighting integration | OpenRazer 3.12.4; per-user daemon active |
| Host | ASUS ROG STRIX B550-F GAMING WIFI II, AMD Ryzen 7 5800X3D, 64 GiB RAM, PowerColor Radeon RX 9070 XT |

The software stack and devices below were observed on this PC. Device discovery by Linux and input-remapper is not the same as end-to-end verification of every Strop editor, mapping, lighting, or HUD path. Use the status column to track that distinction.

## Hardware scope

| Device | USB ID | Observed status |
| --- | --- | --- |
| Razer Tartarus Pro (RZ07-0311) | `1532:0244` | Enumerated by input-remapper and visible as Linux input devices; Strop end-to-end verification pending |
| Razer BlackWidow V3 | `1532:024e` | Enumerated by input-remapper and visible as Linux input devices; Strop end-to-end verification pending |
| Razer Naga Trinity | `1532:0067` | Enumerated by input-remapper and visible as Linux input devices; Strop end-to-end verification pending |

No gamepad was attached during inventory. Gamepads and all devices not listed above are outside the 1.0 support commitment until tested and added here.

## Catalog versus support

Strop contains 230+ catalog entries and generic layout archetypes for Razer models. These entries provide layout/reference data for the editors. They do not establish USB discovery, correct physical key positions, mapping behavior, lighting compatibility, or official device support. Only the three devices in the hardware table are in the initial support scope, and their end-to-end verification remains pending.

## Runtime requirements and setup

The Debian package declares Python, PyGObject, GTK 4, and python-evdev as dependencies. GTK 4 provides the GDK 4 typelib used by the app. The package recommends input-remapper plus OpenRazer. For the supported setup:

1. Install Strop using its Debian package on Ubuntu 26.04.1 LTS.
2. Install and enable input-remapper 2.2.0. Check it with `systemctl status input-remapper` and `input-remapper-control --command hello`.
3. Keep the desktop session user able to read the relevant `/dev/input/event*` nodes. On the inventoried PC, Strop's user could open the detected Razer input nodes without running the app as root.
4. Install and run OpenRazer only for lighting features; profile remapping uses input-remapper. On the inventoried PC, OpenRazer 3.12.4's per-user daemon was active.

If device discovery reports a permission error, check the logged-in user's udev permissions and ACLs on `/dev/input/event*`. Do not run Strop with `sudo`; that can create root-owned configuration files and bypass the intended desktop-session D-Bus access. Reconnect the device and rescan after correcting device access. If input-remapper lists a device but Strop does not, verify that `python3-evdev` is installed and that the desktop user can read the device's event node.

## Display-session limitations

GNOME Wayland is the only supported desktop session for 1.0. The regular GTK 4 editors use the active GTK display backend. The HUD uses X11/XWayland window controls to request positioning and always-on-top behavior; that request can be ignored by the compositor, especially for native Wayland windows or exclusive-fullscreen applications. HUD stacking behavior still requires end-to-end verification on the support target. A pure X11 session is not in the official 1.0 matrix.

## Verification status

The `steam` PC and three devices are the sole target for Priority 3 mapping and Priority 1 profile lifecycle verification. Update this document with concrete results for discovery, save/apply/stop, representative mappings, imported preset round-trips, optional lighting, and HUD behavior before calling the matrix end-to-end tested.
