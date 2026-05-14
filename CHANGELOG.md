# Git user info for project commits:
# Name: Alejandro Lichtenfeld
# Email: 4leled@gmail.com
# (Set globally in git config as of 2025-06-04)

# Changelog

## [2.4.0] - 2026-05-14
### Added
- pytest regression suite (`tests/`) covering pure-logic fixes in `mac_formats.py`, `oui_lookup.py`, and settings I/O. Dev deps in `requirements-dev.txt`.
- Inline error label for invalid hotkey input in Settings dialog.
- Tray-notification fallback when clipboard is locked instead of silent listener-thread death.
- Single-instance check: a second app launch shows "MAC Converter is already running" and exits cleanly.
- `set_autostart_enabled()` / `is_autostart_enabled()` helpers manage a Startup-folder shortcut (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk`).
- `_validate_settings(d)` coerces/clamps every known setting key, falling back to defaults per-key on bad input.
- `_atomic_write_json(path, data)` helper and module-level `_settings_lock` serialize all `save_settings` writes.
- OUI download hardening: `cancel_event` parameter for cooperative shutdown, Content-Type and magic-byte sniff that rejects HTML responses.

### Changed
- Settings I/O is now atomic (`os.replace`) and serialized through `_settings_lock`. Corrupt `settings.json` is renamed to `settings.json.corrupt-<unix-ts>` instead of being silently overwritten with defaults.
- OUI download rejects HTML / non-CSV responses (e.g. captive portals) and zero-entry CSVs before they can overwrite the live database.
- Format popup Enter key handling switched from a system-wide pynput keyboard listener to a Qt-scoped `QShortcut` — no more global keystroke capture in other apps.
- PyInstaller spec ships a real `.ico` (7 sizes) for the Windows exe icon and disables UPX to reduce antivirus false positives.
- `requirements.txt` no longer lists the unused `keyboard` package or the duplicate `PyQt5` line.
- Installer's `[Tasks] startup` and `{userstartup}\…` entries removed; autostart is owned by the app via the Startup-folder shortcut (single source of truth).
- `env_load.ps1` error message uses native PowerShell `-ForegroundColor` instead of literal ANSI escapes.
- OUI auto-update at startup deferred one Qt event-loop tick via `QTimer.singleShot(0, …)`.

### Fixed
- F1: `MAC_REGEX` no longer accepts mixed `:`/`-` separators in the same MAC.
- F2: atomic `os.replace` in OUI download preserves the prior `oui.csv` on rename failure.
- F3: HTML / non-CSV response detection (Content-Type sniff + first-chunk magic bytes).
- F4: HTTPS response opened in a `with` block so the socket closes on exception.
- F5: zero-entry CSV parse is now a load failure, not a silent success.
- F6: `pyperclip.paste()` / `.copy()` in the hotkey handler are wrapped — locked clipboard no longer crashes the listener thread.
- F7, F16, F23, F28: atomic `save_settings` with module-level lock; three writer threads no longer race.
- F8, F15, F24: `_validate_settings` coerces/clamps all known keys; corrupt JSON triggers rename-and-fallback.
- F9: dead `exit_event` synchronization primitive removed.
- F10, F17, F22: 17 bare `except:` clauses narrowed to `except Exception:`.
- F11: OUI download worker honors a cancel event; closing the dialog mid-download cleanly tears down the worker and drains the progress queue.
- F12: error messages no longer leak the full `oui.csv` path containing the user's username.
- F13: "Start with Windows" checkbox actually creates/removes a Startup-folder shortcut now (was previously cosmetic).
- F14: invalid hotkey input is rejected on Save with an inline error label.
- F18: a second click on "Update OUI database" is refused while a download is in progress.
- F19: FormatSelectorPopup Enter key uses `QShortcut` (Qt-scoped) instead of a global pynput listener.
- F20, F21: `pyperclip.copy()` in FormatSelectorPopup and VendorPopup wrapped.
- F25: single-instance mutex prevents double-launch.
- F26: OUI worker cooperative shutdown reduces the daemon-kill corruption window.
- F27, F29: QTimers stop and pynput listener joins on app quit.
- F30: OUI auto-update at startup deferred one Qt tick.
- F31: installer no longer adds its own Startup-folder shortcut; the app owns autostart.
- F32: PyInstaller icon is now a real multi-size `.ico`.
- F33: `pystray._win32` and pywin32 modules are explicitly hidden imports.
- F34: UPX disabled.
- F35: unused `keyboard` package removed from `requirements.txt`.
- F36: `env_load.ps1` ANSI escape garbage replaced with native PowerShell color.
- F37: README format table renamed formats 9-10 from "Windows format alternate" to "Hyphen-6char (Cisco-style)".

## [2.3.0] - 2026-02-17
### Added
- OUI vendor lookup: press Enter in format popup to identify MAC address manufacturer
- IEEE OUI database integration (~38,900 vendor entries from standards-oui.ieee.org)
- Vendor popup with countdown timer, copy-to-clipboard button, and auto-close
- Background OUI database download with auto-update when stale (configurable interval)
- Manual OUI database update with real-time percentage progress bar (MB downloaded / total)
- OUI database viewer: searchable, read-only table of all 38,900+ OUI entries
- OUI settings section: enable/disable, auto-update toggle, update interval, vendor popup timeout
- Database info in About dialog: entry count, unique vendors, file size, download timestamp, location
- New module `oui_lookup.py`: standalone thread-safe OUI database with download, parse, and lookup

### Changed
- Format popup now shows "Press Enter for vendor lookup" hint when OUI database is loaded
- Settings dialog wrapped in scroll area to accommodate new OUI section
- About dialog expanded with OUI database statistics section
- Version updated to 2.3.0

### Fixed
- Settings/About dialogs no longer cause app to exit when closed (setQuitOnLastWindowClosed)
- Dark theme now properly applies inside scroll areas in Settings dialog
- QGroupBox content no longer clips at borders (padding-top fix)

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
