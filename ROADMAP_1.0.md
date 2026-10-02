# Strop 1.0 Release Roadmap

This roadmap defines the work needed to make Strop 1.0 reliable to install, use, and support. The 1.0 goal is a stable end-to-end workflow for supported hardware, with clear limits and verified behavior.

## Release principles

- A user can discover a supported device, edit a profile, save it, apply it, and confirm its state.
- Strop reports failures and uncertain outcomes accurately.
- The documented hardware and platform support matches what has been tested.
- Existing profiles and user macro data survive upgrades and can be recovered.

## Priority 1: Stabilize profile lifecycle

- [ ] Confirm save, apply, stop, and active-profile status match the input-remapper backend result.
- [x] Validate preset data before saving or applying it.
- [x] Write profile and state files atomically to avoid corruption from interrupted writes.
- [x] Preserve the last confirmed state when apply or stop fails; show uncertain state after timeouts.
- [x] Handle missing input-remapper, daemon failures, permission problems, device disconnects, and stale state with actionable messages.
- [x] Verify imported presets round-trip through Strop without losing mappings, labels, or target information for mappings Strop can edit; preserve other valid mappings on save.

## Priority 2: Define supported hardware and platforms

- [x] Publish the sole 1.0 hardware target matrix and distinguish device detection from end-to-end verification.
- [x] Mark catalog-only devices separately from devices verified end to end.
- [x] List the supported Linux distribution, desktop session, and input-remapper/OpenRazer versions.
- [x] Document required packages, device permissions, service setup, and known X11/Wayland limitations.
- [x] Make device discovery explain permission and driver errors instead of presenting them as an empty device list.

### 1.0 support target: Steam PC

Strop 1.0 will officially support only the Steam PC configuration below. Other Linux distributions, desktop sessions, remapping backends, and devices remain unsupported unless they are added after verification. This is the observed support target, not a claim that every mapping path has passed end-to-end testing.

| Area | Observed configuration |
| --- | --- |
| OS / architecture | Ubuntu 26.04.1 LTS (Resolute), amd64 |
| Kernel | 7.0.0-34-generic |
| Desktop | GNOME 50.1 on Wayland; GTK 4.22.4 |
| Python | 3.14.4 |
| Remapping backend | input-remapper 2.2.0; daemon active and reachable |
| Host hardware | ASUS ROG STRIX B550-F GAMING WIFI II; AMD Ryzen 7 5800X3D; 64 GiB RAM; PowerColor Radeon RX 9070 XT |

The input-remapper daemon currently enumerates these attached devices. They are the initial 1.0 hardware support scope; each still needs Strop workflow and mapping verification:

| Device | USB ID | Observed status |
| --- | --- | --- |
| Razer Tartarus Pro (RZ07-0311) | `1532:0244` | Enumerated; Strop mapping verification pending |
| Razer BlackWidow V3 | `1532:024e` | Enumerated; Strop mapping verification pending |
| Razer Naga Trinity | `1532:0067` | Enumerated; Strop mapping verification pending |

OpenRazer 3.12.4 is installed and its per-user daemon is active; its system service is inactive. Treat Strop's OpenRazer-dependent functionality as unverified until the relevant hardware paths are exercised in Strop. No gamepad was attached in this inventory, so gamepad support is outside the 1.0 hardware matrix unless subsequently tested.

## Priority 3: Verify mapping correctness

- [x] Add regression coverage for representative keyboard/mouse preset serialization, gamepad button event serialization, stick display directions, and macro tokenization.
- [ ] Verify mappings on the supported physical keyboard, mouse, and keypad. Gamepad hardware is not in the 1.0 support matrix.
- [ ] Verify analog stick cardinal and diagonal directions, right-stick mappings, triggers, and D-pad actions on supported hardware. Current input-remapper 2.2.0 does not accept the digital-to-axis or compound-button macro outputs Strop previously generated; the UI now disables unsupported stick binds and emits single D-pad buttons only.
- [x] Add parser checks for balanced nested syntax and escaped quoted arguments; validate saved macros with the installed input-remapper parser when available.
- [ ] Verify preset import/export compatibility through round trips on the supported devices and backend.
- [x] Restrict HUD preset loading and active-profile labels to the selected device, and clear stale mapping state for empty presets.
- [x] Protect built-in macro templates and atomically validate user macro-library writes.
- [ ] Confirm mapping behavior and HUD updates during end-to-end use on `steam`.

## Priority 4: Make installation and upgrades repeatable

- [ ] Build and install the Debian package in a clean supported environment.
- [x] Add local Debian package build/inspection checks and validate the source desktop entry. A clean install/uninstall and launcher runtime check is still pending.
- [ ] Test upgrades from 0.9.1 and confirm user presets and macros remain intact.
- [x] Document backup and recovery for profiles and macro data; exercise restore on the support PC before release.
- [x] Align README installation instructions, desktop entry, package contents, and package data permissions. Clean install/uninstall behavior remains pending.
- [ ] Finalize and verify maintainer contact and package metadata before publishing the package.

## Priority 5: Add release checks and documentation

- [ ] Run the core test suite in CI for the supported Python and dependency versions. The workflow now targets Ubuntu 26.04; it still needs a hosted run and validation against the Steam PC's exact runtime versions.
- [x] Add Python compilation, desktop-entry, package-build, and package-content checks to CI.
- [ ] Publish the 1.0 changelog and upgrade notes with release results; development drafts are in `CHANGELOG.md` and `docs/UPGRADING.md`.
- [x] Add installation, first-run, device permissions, profile management, and troubleshooting documentation.
- [x] State the intended hardware matrix and known limitations in the README.

## Release verification checklist

Before tagging 1.0:

1. Install Strop from the documented package or source instructions in a clean environment.
2. Connect representative devices from the published support matrix and confirm discovery and mapping behavior.
3. Create, save, apply, stop, export, and re-import profiles; verify each reported result against the backend.
4. Exercise missing-daemon, permission-denied, timeout, and disconnect cases and confirm clear recovery guidance.
5. Upgrade from 0.9.1 and confirm user data is preserved.
6. Run automated tests and packaging checks; record the results with the release notes.
7. Confirm version strings, package metadata, documentation, and release tag agree on `1.0.0`.

## Suggested scope boundary

The standalone `stropd` daemon remains a separate roadmap item unless it becomes a required part of Strop's 1.0 product definition. Macro Studio focuses on manual composition and validated input-remapper macros. The 1.0 release should focus on a dependable workflow using the chosen, documented remapping backend.

## Current starting point

The 0.9.2 branch contains profile-state, device discovery, macro parsing, gamepad display, HUD targeting, and preset handling improvements. The Steam PC and three Razer devices above are the sole 1.0 support target. Support and setup are documented in `docs/SUPPORT.md` and `docs/USER_GUIDE.md`. Physical mapping, profile lifecycle, clean installation, upgrade, and hosted-CI verification remain open.
