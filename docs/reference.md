# Photo Theme reference

## Requirements

- Omarchy 4.x and Python 3.11 or newer.
- ImageMagick for photo previews and HEIC/HEIF conversion.
- Zenity for the folder chooser.
- Matugen 4.2 or newer for matching colors, including Auto mode.
- rclone for Google Drive. It isn't needed for a local folder.

Install the tools yourself before using the plugin:

```bash
omarchy pkg add matugen imagemagick zenity
```

For Google Drive, also run `omarchy pkg add rclone`. The plugin never installs, updates, or removes packages.

Google Drive setup opens Google's authorization page if a connection isn't already available. Access is read-only. If rclone's shared Google login client stops working, follow its [instructions for creating your own client ID](https://rclone.org/drive/#making-your-own-client-id).

## Terminal commands

The executable lives at:

```text
~/.config/omarchy/plugins/io.github.olivoil.photo-theme/bin/photo-theme
```

To use the short command in your current terminal session:

```bash
alias photo-theme="$HOME/.config/omarchy/plugins/io.github.olivoil.photo-theme/bin/photo-theme"
```

Then you can run:

```bash
photo-theme pick
photo-theme next
photo-theme pause
photo-theme resume
photo-theme status
photo-theme request-sync
photo-theme toggle-mode
```

Set the rotation interval in minutes:

```bash
photo-theme configure interval 60
```

Supported intervals are 15, 30, 60, 120, and 240 minutes. Resuming rotation starts a new countdown; it doesn't change the photo immediately.

Choose a color mode:

```bash
photo-theme configure appearance smart  # Auto · Match Photo
photo-theme configure appearance dark
photo-theme configure appearance light
photo-theme configure appearance fixed  # Wallpaper Only
```

Auto uses Matugen's estimate of the photo's overall brightness. It makes a new choice when the photo or color settings change. `toggle-mode` switches the displayed mode to its opposite and leaves Auto.

To select a particular photo, use a path from the plugin's managed wallpaper collection:

```bash
photo-theme set "$HOME/.config/omarchy/backgrounds/photo-theme/example.jpg"
```

Selecting a photo doesn't resume paused rotation.

## Files and photo handling

Photo Theme keeps its settings and working files in these locations:

| Location | Contents |
| --- | --- |
| `~/.config/omarchy-photo-theme` | Settings |
| `~/.local/state/omarchy-photo-theme` | Rotation, sync status, and menu backup |
| `~/.cache/omarchy-photo-theme` | Downloaded photos |
| `~/.config/omarchy/backgrounds/photo-theme` | Wallpaper copies |
| `~/.config/omarchy/themes/photo-theme` | Generated palette and preview |

The source folder is separate from the wallpaper copies. Original files are never edited. Removing a source photo removes its wallpaper copy, except for the photo currently on screen, which stays available while it's in use.

Images can be up to 100 MiB each. Local folders can contain up to 10,000 photos and 30,000 total entries, with subfolders scanned up to 32 levels deep.

Disabling the plugin stops its service and removes its menu entries. The generated theme stays as it was. Removing the plugin preserves the theme, photos, and settings. There are no separate systemd units or permanent theme hooks to manage.

## Upgrading from Personal Theme

First disable the old plugin:

```bash
omarchy plugin disable io.github.olivoil.personal-theme
```

Then install Photo Theme using the [README's install command](../README.md#get-started). It imports your settings, cached photos, pause preference, and Drive connection. Once you've checked that everything works, remove Personal Theme through Omarchy's plugin menu.

The previous repository URL redirects to the new one. Existing local launchers from the early trial also forward the old commands to Photo Theme.

### Earlier script-based prototype

Before installing the plugin, disable these old background jobs:

```bash
systemctl --user disable --now omarchy-matugen.path omarchy-bg-rotate.timer omarchy-personal-wallpaper.timer omarchy-drive-wallpapers.timer
```

Also archive the `personal-wallpaper-rotation` hook under `~/.config/omarchy/hooks/theme-set.d/`. This prevents the prototype and the plugin from changing wallpapers at the same time.

First activation imports the prototype's Drive source, cached photos, pause preference, and palette when available. Your rclone credentials stay in rclone's configuration.

## Development

From a checkout, run:

```bash
python -m unittest discover -s tests -v
omarchy plugin validate .
```

Tests use temporary folders and mock desktop commands. They cover photo selection, cancellation, pause behavior, theme switching, migration, menu updates, and photo conversion. For UI changes, also check the native picker, palette updates, and plugin disable/enable in a running Omarchy session.
