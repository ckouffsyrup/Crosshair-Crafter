# Crosshair Crafter v1.0.1

Official release build of Crosshair Crafter.

Crosshair Crafter is a lightweight Windows custom crosshair utility with generated crosshairs, custom PNG/JPG image crosshairs, live previewing, presets, favorites, sharing codes, and preset pack import/export.

## Highlights

- Clean modern UI
- Generated crosshair editor
- Custom PNG/JPG crosshair support
- Live preview before applying
- Transparent always-on-top overlay
- Preset saving/loading
- Favorite presets
- Crosshair sharing codes
- `.ccpack` preset pack import/export
- Built-in starter presets
- Safer config and preset loading

## How to run

1. Run `install_requirements.bat` once.
2. Run `run.bat` to start the app.

## How to build an EXE

Run:

```bat
build.bat
```

The built app will appear in the `dist` folder.

## Notes

Crosshair overlays usually work best in borderless/windowed mode. Some games or anti-cheat systems may block or dislike external overlays.

## Credits

Created by Carl.


## v1.0.1 Bug Patch

- Fixes the running Tkinter window using the default feather icon.
- Updates the build script to use PyInstaller clean builds.
- Keeps the same v1.0.0 features and UI.
