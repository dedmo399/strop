# Strop license notice

SPDX-License-Identifier: GPL-3.0-or-later

Unless a file or directory contains a different notice, Strop's original source code and the generated image assets in `assets/` are licensed under the GNU General Public License, version 3 or (at your option) any later version. The full GPL version 3 text is in [`LICENSE`](LICENSE).

Third-party software and any third-party material incorporated into Strop remain under their own licenses and notices.

## Upstream runtime integrations

Strop interacts at runtime with separate system packages that are distributed under their own open-source licenses:

- **[input-remapper](https://github.com/sezanzeb/input-remapper)** — Licensed under the GNU General Public License v3.0 (`GPL-3.0`). Used as the system remapping and macro injection backend.
- **[OpenRazer](https://github.com/openrazer/openrazer)** ([openrazer.github.io](https://openrazer.github.io/)) — Licensed under the GNU General Public License v2.0 (`GPL-2.0`). Used via D-Bus/Python bindings as the optional hardware driver and daemon for RGB lighting, DPI, and polling rate controls.
