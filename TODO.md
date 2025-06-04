# TODO / Feature Tracker

## Milestone 1: Project Setup & Planning
- [ ] Initialize git repository
- [ ] Create documentation files
- [ ] Define MAC address formats (8 total)
- [ ] Set up Python environment

## Milestone 2: Core Functionality
- [ ] Implement MAC address parsing/conversion
- [ ] Add unit tests

## Milestone 3: Clipboard & Hotkey
- [ ] Clipboard integration
- [ ] Global hotkey (configurable, conflict-checked)

## Milestone 4: UI/UX Foundation
- [ ] Tray icon and menu
- [ ] Format selection popup

## Milestone 5: Preferences & Autostart
- [ ] User preferences
- [ ] Autostart (optional)

## Milestone 6: Packaging & Installer
- [ ] Compile to .exe (PyInstaller)
- [ ] Create Windows installer
- [ ] Add uninstall/autostart options

## Milestone 7: Documentation & QA
- [ ] Update docs, logs, changelogs
- [ ] Manual/automated testing

## Milestone 8: Linux Support (Future)
- [ ] Add Linux support for all features

---

## Desired/Expected Application Behavior

- When the app executes, it resides in memory and waits for the global hotkey.
- When the hotkey is pressed, it reads the last entry from the clipboard.
- If the clipboard content is not a valid MAC address, it copies "not a valid mac :-)" to the clipboard and keeps waiting for the next hotkey press.
- If the clipboard content is a valid MAC address, it shows the user a window selector dialog.
- When the selector window is displayed:
  - The window is brought to the front and focused over any other window.
  - A timer (default 6 seconds) starts ticking.
  - If the user presses any key, the timer stops permanently.
  - If the timer reaches 0, the window hides and the clipboard remains unchanged.
  - The user can use the arrow keys (up, down, left, right), ESC, and ENTER to navigate, select, or hide the window.
  - The user can also click on a cell with the mouse to select a value.
  - Once a value is selected (by keyboard or mouse), or ESC/timeout occurs, the window hides (minimized back to the tray bar) and the app keeps running in the background, waiting for the next hotkey.
  - Only if the user selects quit from the traybar menu does the application exit.

## Known Issues
- Windows: Dialog focus/foreground bug persists despite all known workarounds (dummy window, SetForegroundWindow, etc.). See code and comments for details. No further workaround planned.

## Roadmap / TODO (as of 2025-06-04)
- Implement persistent settings (hotkey, timeout, default MAC format) with both a config file (standardized location, e.g. %APPDATA%/mac-converter-2/settings.json) and a settings dialog accessible from the tray menu. Settings must persist between app executions. When packaging as an installer, ensure settings are stored in a user-writable, standard location.
- Add notification (popup or sound) when a MAC address is converted (user-configurable in settings). [Planned, not started]
- Full Windows installer (Start Menu shortcut, autostart, per-user/system-wide install) [Planned, not started]
- Add screenshots/GIFs and troubleshooting section to README.md [Planned, not started]
- Revisit release planning and cross-platform support at a later stage.

Add new tasks below as needed.
