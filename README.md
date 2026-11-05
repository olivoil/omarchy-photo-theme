# Personal Theme

Your personal photos as Omarchy wallpapers, with optional matching colors.

![Personal Theme's native Omarchy photo carousel, showing landscape wallpapers](preview.png)

An Omarchy Quattro plugin with a native photo picker, Appearance menu, optional bar button, and one background service. It supports a local folder or read-only Google Drive syncing. Photos can come from Apple Photos, Google Photos, Immich, or anywhere else: export them into your chosen source folder.

## Features

- A **Personal Theme** entry in Omarchy's theme picker, with a preview.
- **Appearance → Personal Theme**: choose a photo, next photo, pause/resume, sync, status, and settings.
- Omarchy's standard background picker. Confirming a selection applies the image and then its colors.
- Rotation every 15, 30, 60, 120, or 240 minutes, only while Personal Theme is selected.
- Persistent pause, including after selecting another photo or restarting the shell.
- Matching dark colors, matching light colors, or wallpaper only.
- **Color Mode → Auto · Match Photo / Dark / Light / Wallpaper Only** in the main plugin menu. Auto uses Matugen's smart mode to choose dark or light from each photo's overall perceptual brightness. It is a visual heuristic, not a prediction of personal aesthetic preference. It only re-evaluates when the photo or color settings change.
- Right-click the bar icon to toggle dark/light for the same photo. From Auto, this sets a manual override based on the displayed mode; choose Auto again to follow future photos.
- Local folders and optional Google Drive downloads, checked every 15 minutes.
- HEIC/HEIF conversion. Supported images up to 100 MiB; up to 10,000 photos per local source.
- Disabling the plugin stops scheduling and workers. No systemd units or permanent theme hooks are needed.

## Install

Dependencies: Omarchy 4.x, Python 3.11+, ImageMagick, Matugen 4.2+ (for adaptive colors including Auto), rclone (for Google Drive), and Zenity (for choosing a folder).

```bash
omarchy plugin add https://github.com/olivoil/omarchy-personal-theme --enable
```

Update with `omarchy plugin update io.github.olivoil.personal-theme`. A local checkout can also be installed with `omarchy plugin add /absolute/path/to/checkout --enable --yes`.

Open **Appearance → Personal Theme → Settings**. Use **Install Dependencies** if needed, then choose **Use Local Folder** or **Connect Google Drive Folder**. The latter asks for a folder link and opens Google authorization if a connection is not already available. Google Drive access is read-only. rclone's shared OAuth client may require replacement with your own client ID; see [rclone's Drive documentation](https://rclone.org/drive/#making-your-own-client-id).

Select **Personal Theme** from the theme picker, or choose a photo from its menu. On a new installation, the neutral theme preview is replaced after photos have been imported. Network syncing is enabled only after choosing Drive; a local source never contacts a photo service.

## Commands

The executable is `bin/personal-theme` inside the installed plugin directory, normally `~/.config/omarchy/plugins/io.github.olivoil.personal-theme/bin/personal-theme`.

```bash
personal-theme pick
personal-theme next
personal-theme set "/path/to/a/photo/in/the/managed/collection.jpg"
personal-theme pause
personal-theme resume
personal-theme status
personal-theme request-sync
personal-theme configure interval 60
personal-theme configure appearance dark   # light, smart, or fixed also supported
personal-theme configure appearance smart  # choose dark/light from each photo
personal-theme toggle-mode                 # dark ↔ light, same photo
```

These short commands assume you added the plugin's `bin` directory to PATH, or created a launcher in `~/.local/bin`. The migrated local trial includes that launcher and forwards the old `omarchy-personal-wallpaper --pick/--pause/--resume` commands for compatibility. The menu always uses its absolute executable path. `resume` resets the countdown; it does not change the photo immediately. The source directory is separate from the managed background collection, so original files are never edited. Removing a source photo removes only its generated wallpaper copy; the currently displayed copy stays until it is no longer in use.

## Migration and data

First activation imports the prototype's Drive folder, existing rclone remote, pause preference, cached photos, and palette, when present. It does not copy OAuth credentials into this repository or the plugin. Configuration is under `~/.config/omarchy-personal-theme`, worker state under `~/.local/state/omarchy-personal-theme`, and downloaded images under `~/.cache/omarchy-personal-theme`.

Before migrating a live prototype, disable its `omarchy-matugen.path`, `omarchy-bg-rotate.timer`, `omarchy-personal-wallpaper.timer`, and `omarchy-drive-wallpapers.timer`, and archive its `personal-wallpaper-rotation` theme hook. This prevents two owners of the same wallpaper. The local trial migration has done this separately from plugin installation; the plugin installer does not run privileged scripts or remove an unrelated installation automatically.

Disable through Omarchy's plugin menu. Removing the plugin preserves your photos, generated theme, and settings. Menu entries are withdrawn on disable; unrelated menu entries are preserved, with the original JSONC backed up before migration. The generated theme remains static when the plugin is disabled.

## Development

```bash
python -m unittest discover -s tests -v
omarchy plugin validate .
```

Tests use temporary directories and mock only desktop commands. They cover picker selection and cancellation, theme guards, persistent pause, transitions, migration, safe JSONC parsing, source publishing, and stale lifecycle callbacks. Live validation additionally exercises native picker IPC, generated colors, switching themes, and disabling/re-enabling the plugin.

## Credits and license

MIT. The palette template and integration approach build on [Robin Bohrer's omarchy-auto-theme](https://github.com/AccursedGalaxy/omarchy-auto-theme); its MIT notice is retained in `LICENSE.omarchy-auto-theme`. Matugen is an external GPLv2 dependency, not vendored. rclone and ImageMagick are external dependencies. Personal photos and credentials are never part of this repository.
