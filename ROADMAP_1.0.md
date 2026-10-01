# Strop 1.0 Release Roadmap

This roadmap defines the work needed to make Strop 1.0 reliable to install, use, and support. The 1.0 goal is a stable end-to-end workflow for supported hardware, with clear limits and verified behavior.

## Release principles

- A user can discover a supported device, edit a profile, save it, apply it, and confirm its state.
- Strop reports failures and uncertain outcomes accurately.
- The documented hardware and platform support matches what has been tested.
- Existing profiles and user macro data survive upgrades and can be recovered.

## Priority 1: Stabilize profile lifecycle

- [ ] Confirm save, apply, stop, and active-profile status match the input-remapper backend result.
- [ ] Validate preset data before saving or applying it.
- [ ] Write profile and state files atomically to avoid corruption from interrupted writes.
- [ ] Preserve the last confirmed state when apply or stop fails; show uncertain state after timeouts.
- [ ] Handle missing input-remapper, daemon failures, permission problems, device disconnects, and stale state with actionable messages.
- [ ] Verify imported presets round-trip through Strop without losing mappings, labels, or target information.

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
| Desktop | GNOME 50.1 on Wayland; GTK 3.24.52 |
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

- [ ] Cover representative keyboard, mouse, keypad, macro, and gamepad mappings with regression tests.
- [ ] Verify analog stick cardinal and diagonal directions, right-stick mappings, triggers, and D-pad actions.
- [ ] Verify macro parsing for nested calls, delays, quoted arguments, and supported input-remapper syntax.
- [ ] Verify preset import/export compatibility with each supported backend version.
- [ ] Confirm the HUD reflects the selected device and the profile state Strop can confirm.
- [ ] Protect built-in actions and user data from accidental deletion or malformed input.

## Priority 4: Make installation and upgrades repeatable

- [ ] Build and install the Debian package in a clean supported environment.
- [ ] Verify desktop launchers, icons, permissions, package dependencies, and uninstall behavior.
- [ ] Test upgrades from 0.9.1 and confirm user presets and macros remain intact.
- [ ] Provide a backup and recovery path for profiles and macro data.
- [ ] Ensure package metadata and installation instructions match the generated artifacts.

## Priority 5: Add release checks and documentation

- [ ] Run the core test suite in CI for supported Python and dependency versions.
- [ ] Add import/startup and package-build checks to catch missing files and broken entry points.
- [ ] Publish a 1.0 changelog and upgrade notes.
- [ ] Complete installation, first-run, device permissions, profile management, and troubleshooting guides.
- [ ] State the tested hardware matrix and known limitations in the README.

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

The standalone `stropd` daemon and AI macro generation remain separate roadmap items unless either becomes a required part of Strop's 1.0 product definition. The 1.0 release should focus on a dependable workflow using the chosen, documented remapping backend.

## Current starting point

The 0.9.2 branch contains profile-state, device discovery, macro parsing, gamepad display, HUD targeting, and preset handling improvements. The Steam PC and three Razer devices above are the sole 1.0 support target. Priority 2 support scope and diagnostic guidance are recorded in `docs/SUPPORT.md`; end-to-end mapping and profile lifecycle verification remain for Priorities 1 and 3.
