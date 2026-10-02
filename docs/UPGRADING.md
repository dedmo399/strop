# Backup, upgrade, and recovery

This guide covers Strop 0.9.1 to later 0.9.x/1.0 packages. It has not yet been exercised as a clean-system upgrade; verify it on the Steam PC before declaring upgrade support.

## Back up profiles and settings

Strop keeps its macro library and last-confirmed profile labels in `~/.config/strop/`. Input-remapper stores the actual user presets in `~/.config/input-remapper-2/presets/` on current installations; older installations may use `~/.config/input-remapper/presets/`.

Close Strop editors, then copy any existing data directories into a timestamped backup:

```bash
backup="$HOME/strop-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
for path in .config/strop .config/input-remapper-2/presets .config/input-remapper/presets; do
    if [ -e "$HOME/$path" ]; then
        mkdir -p "$backup/$(dirname "$path")"
        cp -a "$HOME/$path" "$backup/$path"
    fi
done
tar -C "$backup" -czf "$backup.tar.gz" .
echo "Backup saved to $backup.tar.gz"
```

Keep the archive somewhere outside the PC if it is your recovery copy. Strop's `active_profiles.json` records the last profile Strop confirmed; it does not represent the live injection state. The input-remapper preset files are the important mapping data.

## Upgrade

1. Use Strop/input-remapper to stop active profiles before upgrading, then close Strop windows.
2. Install the downloaded package with `sudo apt install ./strop_VERSION_all.deb`.
3. Launch Strop and input-remapper, confirm the devices and saved presets appear, and apply a profile only after reviewing its mappings.

Package installation does not intentionally remove user configuration. Do not run the Strop application with `sudo`.

## Restore

Close Strop and input-remapper, then extract the backup into the same user's home directory:

```bash
tar -C "$HOME" -xzf "$HOME/strop-backup-YYYYMMDD-HHMMSS.tar.gz"
```

This overlays the saved directories. It does not delete newer files that were added after the backup. For an exact rollback, first move the current Strop directory and whichever input-remapper preset directory you use aside, then extract the archive. Restore files as your desktop user; avoid `sudo` so ownership remains correct.
