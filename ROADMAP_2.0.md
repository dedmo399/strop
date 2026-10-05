# Strop 2.0 Roadmap

Strop 2.0 will expand hardware capabilities in this order: Tartarus Pro key-depth
access, correct controller-output mappings, and unified hardware settings.
Strop 1.0 remains the released baseline; this document is the active roadmap.

The initial hardware scope remains the Razer Tartarus Pro (`1532:0244`),
BlackWidow V3 (`1532:024e`), and Naga Trinity (`1532:0067`) on the Steam PC.
New capabilities are planned work, not claims of existing support.

## Priority 1: Tartarus Pro depth access

- [ ] Review [tartarus-linux](https://github.com/ZidoDasZibro/tartarus-linux) as the primary Linux implementation reference: HID mode-3 unlock, report `0x06`, individual key depths, interface selection, evdev grabs, and uinput output.
- [ ] Compare its protocol handling with [open-tartarus-driver](https://github.com/ultramonaka/open-tartarus-driver), the Windows implementation that inspired it. Retain required license notices for any reused code.
- [ ] Evaluate integrating or adapting the Linux helper before building a new one. Check Ubuntu compatibility, device ownership, permissions, dependencies, configuration, service lifecycle, and shutdown behavior.
- [ ] Integrate or build a focused Linux helper that reads individual key depths without blocking the GTK interface.
- [ ] Add a live depth display for each analog key and calibration controls.
- [ ] Add separate press/release thresholds to prevent chatter, followed by shallow/deep actions.
- [ ] Coordinate device ownership with input-remapper and OpenRazer to prevent duplicate input and conflicting device commands.
- [ ] Handle permission failures, disconnects, helper failures, and shutdown; release device access and restore ordinary operation where the protocol permits.
- [ ] Preserve existing digital profiles and store depth settings separately.

**Milestone:** Strop displays reliable depth values from the Tartarus Pro and
returns the device to ordinary operation when stopped.

After the depth prototype, choose whether to feed normalized analog input into
input-remapper or let the helper own those outputs. Base the decision on observed
protocol behavior, backend capability, release handling, and compatibility with
existing profiles. A complete replacement daemon is not a prerequisite.

## Priority 2: Correct controller-output mappings

- [ ] Replace unsupported `gamepad(...)` serialization with input-remapper's actual event and macro formats where supported.
- [ ] Implement held controller buttons, left/right stick directions, triggers, and D-pad diagonals.
- [ ] Define consistent behavior for simultaneous directions, opposing inputs, and release back to neutral.
- [ ] Connect Tartarus key depth to proportional stick and trigger outputs, including calibration and response controls.
- [ ] Evaluate tartarus-linux's existing stick/trigger output, response curves, deadzones, dual-depth actions, and layers for reuse. Verify axis ranges, opposing inputs, and release behavior before adopting its implementation.
- [ ] Use a focused native output component where input-remapper cannot provide the required behavior.
- [ ] Release held buttons and neutralize axes on stop, profile change, disconnect, or helper failure.
- [ ] Enable each currently disabled controller control once its implementation works, and preserve mappings through save/load round trips.

**Milestone:** Digital mappings produce predictable controller output, and
Tartarus analog keys provide proportional movement or throttle.

Input-remapper 2.2.0 can emit raw gamepad-axis events through macros; its direct
button-to-axis handler is unimplemented. Rejected Strop shorthand does not prove
that the backend cannot generate an output. Select the implementation for each
mapping from backend capabilities rather than assuming all analog output needs
a replacement daemon.

## Priority 3: Unified hardware settings

- [ ] Extend the existing OpenRazer integration into a shared hardware settings panel.
- [ ] Discover each device's actual capabilities before presenting controls.
- [ ] Provide supported lighting effects and brightness controls.
- [ ] Provide Naga DPI and polling-rate settings where exposed by the device and driver.
- [ ] Match devices using stable identifiers rather than partial names.
- [ ] Save settings per device and accurately report failed or uncertain changes.
- [ ] Coordinate lighting and hardware commands with the Tartarus depth helper.

**Milestone:** The Hub exposes supported hardware settings for all three devices
alongside their mapping profiles.

## Validation and user interaction

- [ ] Automate protocol replay tests for valid, malformed, incomplete, and unexpected depth reports.
- [ ] Automate controller serialization, output-state transitions, opposing inputs, neutralization, and profile round trips.
- [ ] Test hardware capability detection and error handling with simulated OpenRazer devices.
- [ ] Extend packaging and CI checks for any new helper, dependencies, permissions, and service integration.

Keep interaction minimal. Request a short key-depth exercise and observation of
controller behavior only where software cannot establish the physical result.
Record those results as evidence for the new capabilities; the removed 1.0
release prerequisites remain closed.

## Architecture boundary

### Driver references

- [tartarus-linux](https://github.com/ZidoDasZibro/tartarus-linux): Rust Linux implementation for the same Tartarus Pro USB ID. Its README reports testing on Nobara/Fedora 44, so Ubuntu support must be established rather than assumed. It is licensed GPL-3.0-or-later and documents analog reading, native controller output, and systemd user-service integration.
- [open-tartarus-driver](https://github.com/ultramonaka/open-tartarus-driver): Windows implementation and complementary protocol research reference.

Study both projects before choosing the depth helper and output architecture.
Evaluate the Linux driver's OpenRazer coexistence and replace any standalone web
interface with Strop's GTK controls when integrating it. Review upstream setup
scripts and adapt permissions and packaging to Strop rather than installing them
unchanged.

Retain input-remapper for existing workflows wherever it meets the requirements,
and use OpenRazer for supported hardware settings. Expand native components only
where the depth prototype or controller work demonstrates a need.

[ROADMAP_NATIVE_DAEMON.md](ROADMAP_NATIVE_DAEMON.md) remains an architectural
reference for a possible full daemon, not an additional 2.0 release requirement.
[ROADMAP_1.0.md](ROADMAP_1.0.md) records the closed 1.0 scope.
