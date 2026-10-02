# Strop first-run and profile guide

Use this guide with the supported PC and devices listed in [SUPPORT.md](SUPPORT.md). Device discovery alone does not mean a mapping has been verified.

## Before launching

- Install Strop and the documented runtime dependencies.
- Ensure input-remapper 2.2.0 is installed and its service is running. Check with `systemctl status input-remapper` and `input-remapper-control --command hello`.
- Launch Strop as your logged-in desktop user. Do not use `sudo` for the application.

## Create and apply a profile

1. Launch Strop from the application menu or run `strop` after installing the package. In a source checkout, run `./strop.py` from the project directory.
2. Confirm the intended device appears in the hub. Use **Rescan** if needed. Review any discovery diagnostic before opening a studio.
3. Open that device's studio, select an input on the layout, and edit its output and target. Only supported single gamepad-button outputs are available for gamepad mapping; digital-to-analog stick and trigger bindings are not supported by the 1.0 backend.
4. Enter a preset name. In the Presets section, use **Save** to write the preset, or **Apply** to save it and request input-remapper to start it.
5. Confirm the result in Strop's status message. An unknown/timeout result means Strop cannot confirm whether the backend changed state; inspect input-remapper before retrying.
6. Use **Stop** to ask the backend to stop injection for the selected device. Confirm the reported result.

The hub also offers **Apply Settings** and **Stop** for the selected device/profile. A label such as “Last Strop profile” is Strop's last confirmed operation, not live proof that the profile remains active if another tool changes injection state.

## Import and export presets

- Use **Load** to import an input-remapper JSON preset. Strop reports how many mappings it can edit. Valid mappings outside Strop's editor model are preserved when the preset is saved.
- Use **Save** to write the current editor state to the selected device's input-remapper preset directory.
- Keep a separate backup before replacing a profile. See [UPGRADING.md](UPGRADING.md) for backup and restore instructions.

## Macros

Macro Studio saves custom macros under `~/.config/strop/macros.json`. Built-in templates are read-only. Macro syntax must be accepted by the installed input-remapper parser when that parser is available.

## Common problems

| Symptom | Check |
| --- | --- |
| No device appears | Rescan; check the USB connection, Linux input driver, `/dev/input/event*` access, and `python3-evdev`. See [SUPPORT.md](SUPPORT.md). |
| Apply or stop fails | Check `systemctl status input-remapper` and `input-remapper-control --command hello`; reconnect the device if it disconnected. |
| Preset loads partially | Review the count and original JSON. Some valid backend mappings are not represented by Strop's editor; those entries are preserved when saving. |
| HUD does not stay above a game | GNOME Wayland/XWayland and exclusive fullscreen can limit compositor window placement. HUD stacking still needs end-to-end verification on the support PC. |

