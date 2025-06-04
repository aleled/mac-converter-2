# TODO / Feature Tracker

## Milestone 1: Project Setup & Planning
- [x] Initialize git repository
- [x] Create documentation files
- [x] Define MAC address formats (8 total)
- [x] Set up Python environment

## Milestone 2: Core Functionality
- [x] Implement MAC address parsing/conversion
- [x] Add unit tests

## Milestone 3: Clipboard & Hotkey
- [x] Clipboard integration
- [x] Global hotkey (configurable, conflict-checked)

## Milestone 4: UI/UX Foundation
- [x] Tray icon and menu
- [x] Format selection popup

## Milestone 5: Preferences & Autostart
- [x] User preferences
- [x] Autostart (optional)
- [ ] Implement persistent settings (hotkey, timeout, default MAC format) with both a config file (standardized location, e.g. %APPDATA%/mac-converter-2/settings.json) and a settings dialog accessible from the tray menu. Settings must persist between app executions. When packaging as an installer, ensure settings are stored in a user-writable, standard location.

## Milestone 6: Packaging & Installer
- [x] Compile to .exe (PyInstaller)
- [ ] Full Windows installer (Start Menu shortcut, autostart, per-user/system-wide install) [Planned, not started]
- [ ] Add uninstall/autostart options

## Milestone 7: Documentation & QA
- [x] Update docs, logs, changelogs
- [x] Manual/automated testing
- [ ] Add screenshots/GIFs and troubleshooting section to README.md [Planned, not started]
- [ ] Add notification (popup or sound) when a MAC address is converted (user-configurable in settings). [Planned, not started]
- [ ] Regularly update and track milestone progress in this file and in the changelog during development. Ensure all completed, in-progress, and planned tasks are clearly marked and up to date.

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

- [ ] Regularly update and track milestone progress in this file and in the changelog during development. Ensure all completed, in-progress, and planned tasks are clearly marked and up to date.

Add new tasks below as needed.
