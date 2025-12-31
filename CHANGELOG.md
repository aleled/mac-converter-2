# Git user info for project commits:
# Name: Alejandro Lichtenfeld
# Email: 4leled@gmail.com
# (Set globally in git config as of 2025-06-04)

# Changelog

## [2.2.0] - 2025-12-31
### Added
- Auto-cycling MAC format converter: each hotkey press cycles to the next format (0→1→2→...→9→0)
- Tray notifications for converted MAC addresses (configurable duration, default 3 seconds)
- Error notifications for invalid MAC addresses in clipboard
- Configurable global hotkey via Settings dialog (default alt+shift+m)
- Configurable notification duration (1-10 seconds) via Settings dialog
- Threading.Timer-based notification auto-dismiss for precise duration control

### Changed
- Removed FormatSelector dialog entirely - replaced with instant auto-cycling and notifications
- Settings structure: replaced 'default_format' and 'timer' with 'last_format_index', 'hotkey', 'notification_duration'
- Hotkey implementation: switched from hardcoded Alt+Shift+M to settings-configurable hotkey
- Fixed author name from "A. Lederman" to "Alejandro Lichtenfeld"
- Version updated to 2.2.0

### Removed
- FormatSelector QDialog class (315+ lines of code)
- dialog_request_queue and dialog_open global state
- bring_to_foreground() and safe_bring_to_foreground() functions (focus management no longer needed)
- show_format_selector_from_queue() function
- Admin privilege check and keyboard package dependency
- Legacy dialog-based format selection UI/UX

### Fixed
- Author name correction in settings and about text
- Notification system now respects user-configured duration settings

## [Unreleased - Previous Session]
- Major debug session for selector dialog: added detailed debug output for navigation, selection, and cell state.
- Improved highlight: selected cell now has green background, orange text, and bold font for maximum visibility.
- Navigation logic confirmed: only columns 1 and 2 are selectable, up/down/left/right keys work as intended.
- Reduced dialog spam in console by throttling repeated messages.
- Added cell state printout for further troubleshooting.
- All changes committed and session state saved for seamless continuation.

## [2.1.0] - 2025-06-07
### Added
- Persistent user preferences: autostart, default format, timer, about/credits/license info (settings stored in %APPDATA%/mac-converter-2/settings.json)
- Settings dialog accessible from tray menu (change preferences: autostart, default format, timer, etc.)
- About dialog with app info, author, credits, and MIT license

### Changed
- App always loads/saves settings from %APPDATA%/mac-converter-2/settings.json
- App uses default format and timer from settings
- Autostart logic: add/remove from Windows startup based on user preference
- Robust error handling for settings file
- Switched from keyboard (admin required) to pynput for global hotkey registration (no admin required).
- The app no longer requires administrator rights for any feature. This is now a permanent design constraint for all future development.

### Fixed
- Info box always shows correct MAC address from clipboard
- Minor UI/UX polish and English phrasing finalized

## [2.0.0] - 2025-06-06
### Added
- Robust global hotkey (Alt+Shift+M) using the keyboard package (suppressed, admin required on Windows).
- Info box always shows the correct MAC address from the clipboard.
- Modern, visually clear, and user-friendly format selector dialog.
- Clean tray quit and error-free shutdown.

### Changed
- Removed all legacy/unused QTableWidget code and debug output.
- Updated all documentation and comments for clarity and accuracy.

### Fixed
- No more 'M' characters in terminal after exit.
- Info box never shows '(none)' if a MAC is present.

## [2025-06-04] Major documentation and maintenance update:
- All functions and classes now have detailed docstrings (clipboard_hotkey.py, mac_formats.py, test_mac_formats.py)
- Documented persistent Windows focus bug and all attempted workarounds in TODO.md
- Moved unused/old files (clipboard_hotkey_new.py, clipboard_hotkey_fixed.py, clipboard_hotkey_broken.py) to old/
- Updated README.md, TODO.md, DEVELOPMENT_LOG.md with current state, known issues, and progress
- Removed native table selection/focus border, leaving only custom highlight
- No changes to selector logic or highlight per user request
- All debug output reviewed; only essential debug remains
- All changes pushed to git

---

Each milestone and version will be logged here.
