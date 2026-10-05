# Strop 1.0 support matrix

Strop 1.0 has one official platform target: the `steam` PC configuration below. Other operating systems, distributions, desktop sessions, input-remapper/OpenRazer versions, and devices are outside the 1.0 support commitment unless this document is updated after verification.

## Platform target

| Component | Supported target observed on `steam` |
| --- | --- |
| Distribution | Ubuntu 26.04.1 LTS (Resolute Raccoon), amd64 |
| Kernel | Linux 7.0.0-*-generic (any numbered build) |
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
| Razer Tartarus Pro (RZ07-0311) | `1532:0244` | Enumerated; user verified profiles, physical mappings, and preset round trips |
| Razer BlackWidow V3 | `1532:024e` | Enumerated; user verified profiles, physical mappings, and preset round trips |
| Razer Naga Trinity | `1532:0067` | Enumerated; user verified profiles, physical mappings, and preset round trips |

No gamepad was attached during inventory. Gamepads and all devices not listed above are outside the 1.0 support commitment until tested and added here.

## Catalog versus support

Strop contains 230+ catalog entries and generic layout archetypes for Razer models. These entries provide layout/reference data for the editors. They do not establish USB discovery, correct physical key positions, mapping behavior, lighting compatibility, or official device support. Only the three devices in the hardware table are in the initial support scope. Their user verification results are recorded below; optional lighting remains unverified.

## Runtime requirements and setup

The Debian package declares Python, PyGObject, GTK 4, and python-evdev as dependencies. GTK 4 provides the GDK 4 typelib used by the app. The package recommends input-remapper plus OpenRazer. For the supported setup:

1. Install Strop using its Debian package on Ubuntu 26.04.1 LTS.
2. Install and enable input-remapper 2.2.0. Check it with `systemctl status input-remapper` and `input-remapper-control --command hello`.
3. Keep the desktop session user able to read the relevant `/dev/input/event*` nodes. On the inventoried PC, Strop's user could open the detected Razer input nodes without running the app as root.
4. Install and run OpenRazer only for lighting features; profile remapping uses input-remapper. On the inventoried PC, OpenRazer 3.12.4's per-user daemon was active.

If device discovery reports a permission error, check the logged-in user's udev permissions and ACLs on `/dev/input/event*`. Do not run Strop with `sudo`; that can create root-owned configuration files and bypass the intended desktop-session D-Bus access. Reconnect the device and rescan after correcting device access. If input-remapper lists a device but Strop does not, verify that `python3-evdev` is installed and that the desktop user can read the device's event node.

## Display-session limitations

GNOME Wayland is the only supported desktop session for 1.0. The regular GTK 4 editors use the active GTK display backend. The HUD uses X11/XWayland window controls to request positioning and always-on-top behavior; that request can be ignored by the compositor, especially for native Wayland windows or exclusive-fullscreen applications. Fullscreen HUD stacking remains unverified. A pure X11 session is not in the official 1.0 matrix.

## Verification status

On 2026-10-04, the user confirmed that saving, applying, and stopping profiles on `steam` work and that Strop's displayed status agrees with actual behavior.

On the same date, the user confirmed that BlackWidow V3 remapped keys and macros produce the expected input, while unmapped keys continue to work normally. The user also confirmed that Naga Trinity remapped buttons and macros produce the expected input, while unmapped buttons and pointer movement work normally. Tartarus Pro remapped keys and macros also produce the expected input, while unmapped keys, the scroll wheel, thumb button, and D-pad work normally.

Tartarus D-pad-to-gamepad cardinal button outputs remain unverified. Physical mapping verification is not an additional 1.0 release requirement; unverified outputs do not expand the support matrix.

On the same date, the user confirmed preset round trips work on the BlackWidow V3, Naga Trinity, and Tartarus Pro: saving, loading, saving again, and reapplying preserves mappings, labels, and output targets. The user also confirmed that the HUD shows the selected device, profile, and mappings and updates correctly when switching profiles during use on `steam`.

On 2026-10-05, the user confirmed a fresh installation of the latest Debian package on the supported setup with no previous Strop package installed, including working menu launcher and icons.

On the same date, the user confirmed uninstall removes Strop's launchers and menu entry while preserving saved presets and macros.

An automated isolated restoration drill recovered all 12 current configuration files byte-for-byte on 2026-10-05. Loading and applying the recovered profiles in Strop was not exercised. Further recovery verification is not a 1.0 release prerequisite.

The `steam` PC and three devices are the sole target for Priority 3 mapping and Priority 1 profile lifecycle verification. D-pad-to-gamepad outputs, optional lighting, and fullscreen HUD stacking remain unverified.

### Upgrade data preservation

During pre-1.0 package testing on 2026-10-04, an upgrade on `steam` changed only Strop. All 16 backed-up configuration files remained present and byte-for-byte unchanged. Package verification reported no discrepancies, the desktop entry passed validation, all six installed launch commands were present, and input-remapper answered its `hello` command.

These historical checks establish upgrade data preservation for that tested build. They do not claim that the final 1.0 package was installed during those earlier tests. Strop 1.0 keeps the same user-data locations and backup procedure.
