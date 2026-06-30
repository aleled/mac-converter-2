# TODO / Feature Tracker

**Current Version:** 2.5.1 (Production Ready)
**Last Updated:** 2026-05-22

---

## Completed Milestones

### ✅ Milestone 1: Project Setup & Planning
- [x] Initialize git repository
- [x] Create documentation files
- [x] Define MAC address formats (10 total)
- [x] Set up Python environment

### ✅ Milestone 2: Core Functionality
- [x] Implement MAC address parsing/conversion
- [x] Support 10 MAC address formats
- [x] Add unit tests

### ✅ Milestone 3: Clipboard & Hotkey
- [x] Clipboard integration
- [x] Global hotkey (configurable, no admin required)
- [x] Hotkey parsing for pynput compatibility
- [x] Thread-safe hotkey listener

### ✅ Milestone 4: Auto-Cycling Converter
- [x] Auto-cycling format selection (0→1→2→...→9→0)
- [x] Instant format conversion on hotkey press
- [x] Automatic clipboard update with converted MAC
- [x] Remove legacy format selector dialog

### ✅ Milestone 5: Tray Notifications
- [x] Tray notifications for converted MAC addresses
- [x] Error notifications for invalid MAC addresses
- [x] Configurable notification duration (1-10 seconds)
- [x] Thread-safe notification display
- [x] Auto-dismiss after configured duration

### ✅ Milestone 6: UI/UX Enhancements
- [x] Dark theme for all dialogs (#2b2b2b background)
- [x] Format popup with icon header (48x48)
- [x] Settings dialog with grouped sections
- [x] About dialog with app icon (96x96)
- [x] Professional styling and color scheme
- [x] Clickable GitHub link in About dialog

### ✅ Milestone 7: User Preferences
- [x] Persistent settings in %APPDATA%\mac-converter-2\settings.json
- [x] Settings dialog accessible from tray menu
- [x] Configurable global hotkey
- [x] Configurable notification duration
- [x] Autostart (Start with Windows) option
- [x] Robust error handling for settings file

### ✅ Milestone 8: Windows Installer
- [x] PyInstaller executable build (mac-converter.spec)
- [x] Inno Setup installer script (installer.iss)
- [x] Professional wizard-style installation
- [x] Optional desktop shortcut
- [x] Optional Windows startup entry
- [x] Clean uninstaller with settings cleanup
- [x] Embedded app icon in executable
- [x] No admin rights required for installation

### ✅ Milestone 9: Documentation & QA
- [x] Update README.md with v2.2.0 features
- [x] Update CHANGELOG.md with release notes
- [x] Update DEVELOPMENT_LOG.md with session notes
- [x] Manual testing and verification
- [x] Clean up temporary files and debug output
- [x] Add .gitignore entries for build artifacts
- [x] GitHub repository sync

---

### ✅ Milestone 10: OUI Vendor Lookup (v2.3.0)
- [x] IEEE OUI database integration (~38,900 vendor entries)
- [x] Background download with auto-update when stale
- [x] Vendor lookup via Enter key in format popup
- [x] Vendor popup with countdown timer and copy-to-clipboard
- [x] Manual OUI update with real-time percentage progress bar
- [x] Searchable OUI database viewer (read-only table)
- [x] OUI settings: enable/disable, auto-update, interval, timeout
- [x] Database stats in About dialog
- [x] New standalone module `oui_lookup.py`
- [x] Fixed app exit on dialog close (setQuitOnLastWindowClosed)
- [x] Fixed dark theme in scrollable Settings dialog
- [x] Updated installer to v2.3.0

### ✅ Milestone 11: Security & Bug Audit + Bug Fixes (v2.4.0)
- [x] Full read-only audit of all source/build/doc files (37 findings: 5 HIGH, 12 MEDIUM, 20 LOW) — see `docs/AUDIT-2026-05-14.md`
- [x] pytest regression suite scaffolded (`tests/`, `pytest.ini`, `requirements-dev.txt`, `conftest.py`); 24 tests green
- [x] Atomic settings writes (`os.replace`) under module-level `_settings_lock` (closes F7, F16, F23, F28)
- [x] Settings load validation + corrupt-file rename to `settings.json.corrupt-<unix-ts>` (closes F8, F15, F24)
- [x] OUI download hardening — atomic replace, HTML/captive-portal rejection, zero-entry guard, response context manager, cancel-event parameter (closes F2, F3, F4, F5)
- [x] MAC regex tightened to reject mixed `:`/`-` separators (closes F1)
- [x] All `pyperclip` call sites wrapped in `try/except PyperclipException` (closes F6, F20, F21)
- [x] Hotkey input validated on Settings dialog Save with inline error label (closes F14)
- [x] Functional autostart via Startup-folder shortcut managed by the app (closes F13 + F31)
- [x] Single-instance Win32 named mutex prevents double-launch (closes F25)
- [x] FormatSelectorPopup Enter key replaced with Qt-scoped `QShortcut` — global pynput keyboard hook removed (closes F19)
- [x] OUI worker cooperative shutdown (cancel event + join), re-entrance guard, error message sanitization (closes F11, F12, F18, F26)
- [x] PyInstaller spec ships a real multi-size `.ico`, explicit hidden imports, UPX disabled (closes F32, F33, F34); `keyboard` dropped from `requirements.txt` (closes F35)
- [x] Cleanup batch — 17 bare `except:` narrowed, `exit_event` removed, QTimer cleanup on quit, listener join, OUI auto-update deferred one Qt tick, `env_load.ps1` ANSI escape fixed (closes F9, F10, F17, F22, F27, F29, F30, F36)
- [x] README format table renamed formats 9-10 to "Hyphen-6char (Cisco-style)" (closes F37)
- [x] Version bumped to 2.4.0 across all surfaces; CHANGELOG `[2.4.0]` section added with all 37 F-IDs listed

### ✅ Milestone 12: GitHub Pages Download Portal (v2.4.0)
- [x] Single-page static portal at `docs/index.html` + `docs/styles.css` + `docs/icon-v1.png`
- [x] Dark-theme styling matching the app palette
- [x] Auto-fetches latest release via the GitHub API with graceful fallback to "Coming soon"
- [x] Operator instructions at `docs/README.md`
- [x] Pages enabled in repo Settings → Pages, serving from `/docs`
- [x] `.nojekyll` added so Pages serves the folder as static files (Jekyll was choking on the audit markdown)
- [x] Live at **https://aleled.github.io/mac-converter-2/**

### ✅ Milestone 13: Post-release UX patches (v2.4.1 + v2.4.2)
- [x] v2.4.1: first attempt at fixing the Enter-to-vendor focus regression — added `activateWindow()`, `setFocus()`, and `SetForegroundWindow` after `.show()`. Insufficient on its own.
- [x] v2.4.2: full fix — `Qt.StrongFocus` policy on `FormatSelectorPopup`, `AttachThreadInput` trick to satisfy Windows' foreground-steal rules, `Qt.ApplicationShortcut` context for the `QShortcut`, plus a `keyPressEvent` override on the popup as belt-and-suspenders
- [x] v2.4.2: tray notification when Enter is pressed before the OUI database has loaded ("OUI database is still loading, try again in a moment") so the case is no longer silent
- [x] v2.4.2 release built and published with both `.exe` artifacts; portal auto-detected within 30s

### ✅ Milestone 14: Comprehensive documentation pass (v2.4.2)
- [x] `ARCHITECTURE.md` — module-by-module code walkthrough, threading model, data flow, key design decisions with rationale, "where to look when something breaks"
- [x] `TROUBLESHOOTING.md` — user-facing diagnostic guide for hotkey conflicts, OUI download failures, antivirus, autostart, corrupt settings, etc.
- [x] `BUILDING.md` — detailed build instructions (PyInstaller + Inno Setup), one-time setup, release process, build troubleshooting
- [x] README significantly expanded — per-feature deep documentation, settings reference table, "How it works in 60 seconds", file locations table, documentation map
- [x] TODO + DEVELOPMENT_LOG updated with v2.4.1, v2.4.2, and Milestone 14 entries

### ✅ Milestone 15: Corporate-network TLS support + manual OUI import (v2.4.3)
- [x] Added `truststore` package — Python `urllib` now uses Windows' certificate store, fixing `CERTIFICATE_VERIFY_FAILED` failures on corporate networks with TLS-intercepting proxies (Zscaler, Palo Alto, FortiGate, Cisco Umbrella, etc.)
- [x] `truststore.inject_into_ssl()` called at `oui_lookup` module load — same approach pip uses
- [x] New "Import from file…" button in Settings → OUI section — fallback for locked-down environments where even `truststore` isn't enough; validates the file, atomically replaces the live database, reloads
- [x] Updated `requirements.txt` and `mac-converter.spec` (`truststore` added as hidden import for the PyInstaller exe)
- [x] CHANGELOG `[2.4.3]` section added

### ✅ Milestone 16: Startup Update Check (v2.5.0)
- [x] New `update_check.py` module — pure logic, no Qt dependency, mirrors the `oui_lookup.py` pattern
- [x] `APP_VERSION` consolidated as single source of truth (replaces three previously-hardcoded version strings across `clipboard_hotkey.py` and `oui_lookup.py`)
- [x] GitHub Releases API integration; TLS via the truststore injection from `oui_lookup.py` (the new module inherits it for free)
- [x] Modal QMessageBox prompt with Upgrade / Skip buttons; Upgrade opens the portal in the default browser and exits the app so the installer can replace the running exe
- [x] Defensive error handling — all failure paths return `None` silently, no popups for offline / rate-limited / network-broken cases
- [x] 10 new pytest regression tests (`_parse_version` + `check_for_update` happy/error paths)
- [x] Module-level `_update_timer` cleaned up in `on_quit` (matches F27 pattern)
- [x] CHANGELOG `[2.5.0]` section, README, ARCHITECTURE, TROUBLESHOOTING, DEVELOPMENT_LOG updates

### ✅ Milestone 17: Format expansion + autostart double-launch fix (v2.5.1)
- [x] New space-separated MAC detection (`aa bb cc dd ee ff`) — input only, not in conversion cycle
- [x] New 4-4-4 dash format (`AABB-CCDD-EEFF` and lowercase) — detection + 2 new conversion outputs; cycle expanded from 10 to 12 formats
- [x] Format cycle modulo wraps via `len(MAC_FORMATS)` instead of hardcoded `% 10`
- [x] `last_format_index` validation range expanded from `[0, 9]` to `[0, 11]`
- [x] Fix double-launch on Windows startup — pre-v2.4.0 installer left `MAC Address Converter.lnk` (full app name); v2.4.0+ in-app autostart used `MAC-Converter.lnk` (different filename, same target); both fired at boot
- [x] Runtime sweep: `_cleanup_legacy_autostart_shortcuts()` runs at `main()` startup and from `set_autostart_enabled(True)`; idempotent
- [x] Installer sweep: `[InstallDelete]` directive in `installer.iss` removes `MAC Address Converter.lnk` during install
- [x] 5 new pytest tests (4 parametrize cases for the new detection inputs and 12-format output, 1 for the expanded `last_format_index` range, 3 for the autostart cleanup helper)
- [x] CHANGELOG `[2.5.1]` section, README format table updated to 12 formats, ARCHITECTURE §6.7 expanded with the legacy-shortcut narrative, TROUBLESHOOTING entry, DEVELOPMENT_LOG entry

---

## Current Release (v2.5.1)

**Status:** Production Ready ✅

### Features Included
- ✅ Auto-cycling MAC format converter (10 formats) with strict separator validation
- ✅ Configurable, validated global hotkey (no admin required)
- ✅ Tray notifications with duration control and clipboard-error fallback
- ✅ Dark theme UI with professional styling
- ✅ Settings dialog (hotkey, duration, autostart, OUI options) with inline validation
- ✅ About dialog with app info, GitHub link, and OUI database stats
- ✅ OUI vendor lookup with IEEE database (~38,900 vendors) — Qt-scoped Enter key, no global keyboard hook
- ✅ Manual OUI update with percentage progress bar, cooperative shutdown, content-sniff hardening
- ✅ Searchable OUI database viewer
- ✅ Persistent atomic settings storage with corrupt-file recovery
- ✅ Functional "Start with Windows" autostart (Startup-folder shortcut)
- ✅ Single-instance enforcement
- ✅ Windows installer package
- ✅ Standalone executable with real multi-size `.ico` icon
- ✅ 24 pytest regression tests covering pure-logic surfaces
- ✅ Public download portal at https://aleled.github.io/mac-converter-2/
- ✅ Comprehensive security & bug audit completed (`docs/AUDIT-2026-05-14.md`)

### Build Artifacts
- Standalone executable: `dist/MAC-Converter.exe` (~51 MB, real `.ico` icon embedded)
- Windows installer: `installer-output/MAC-Converter-Setup-v2.5.1.exe` (~54 MB, 12 conversion formats, legacy-shortcut cleanup, startup update check)
- Source code: clean, audited, tested, fully documented (ARCHITECTURE.md, TROUBLESHOOTING.md, BUILDING.md, etc.)

---

## Future Enhancements (v2.6.0+)

### Potential Features
- [ ] Tray history of recent conversions
- [ ] Batch MAC address conversion
- [ ] Additional MAC format variations
- [ ] Custom user-defined formats
- [ ] Hotkey history/logs
- [ ] Settings import/export
- [ ] Multi-language support
- [ ] Linux/macOS full support
- [ ] Update checker
- [ ] Performance metrics/statistics

### Nice-to-Have Improvements
- [ ] Keyboard shortcuts guide in About
- [ ] Drag-and-drop MAC file import
- [ ] System tray menu with recent formats
- [ ] Dark/Light theme toggle
- [ ] Custom notification sounds
- [ ] Auto-update functionality

### Technical Debt / Refactoring
- [ ] Add unit tests for UI dialogs
- [ ] Integration tests for full workflow
- [ ] Code coverage analysis
- [ ] Performance profiling
- [ ] Memory usage optimization

---

## Known Limitations

- **Windows Only**: Primary platform is Windows 10/11
- **No Batch Processing**: One MAC address at a time
- **No History**: Previous conversions not stored
- **No Update Mechanism**: Manual updates via GitHub
- **OUI Database**: Requires internet for initial download (~3.5 MB from IEEE)

---

## Design Constraints (Permanent)

- ✅ **No Admin Rights**: App must never require administrator privileges
- ✅ **No Configuration Wizards**: Works out of the box with sensible defaults
- ✅ **Minimal Dependencies**: Lightweight, fast startup
- ✅ **Dark Theme Only**: Professional appearance
- ✅ **System Tray Focus**: Not a window application

---

## Recent Changes (Session: 2026-05-15 — v2.4.2 release + comprehensive documentation pass)

### What Was Done (continued from 2026-05-14 session)
- ✅ Diagnosed and fixed the Enter-to-vendor-lookup regression: shipped v2.4.1 (first focus-grab attempt) and v2.4.2 (full fix with `Qt.StrongFocus` + `AttachThreadInput` + `Qt.ApplicationShortcut` + `keyPressEvent`)
- ✅ Added tray notification when OUI database isn't loaded yet (no more silent Enter)
- ✅ Created `ARCHITECTURE.md` — full module-by-module code walkthrough with design rationale and "where to look when something breaks"
- ✅ Created `TROUBLESHOOTING.md` — user-facing diagnostic guide
- ✅ Created `BUILDING.md` — detailed build instructions
- ✅ Significantly expanded `README.md` — per-feature deep documentation, settings reference table, file locations, documentation map
- ✅ Updated TODO + DEVELOPMENT_LOG with Milestones 13 and 14
- ✅ Pages portal `.nojekyll` fix (first build was erroring because Jekyll choked on the audit markdown)

## Earlier in this engagement (Session: 2026-05-14 — v2.4.0 audit, fixes, portal)

### What Was Done
- ✅ Conducted full security & bug audit of the repository (37 findings: 5 HIGH, 12 MEDIUM, 20 LOW); report at `docs/AUDIT-2026-05-14.md`
- ✅ Implemented all 37 fixes across 15 commit groups (atomic settings, OUI hardening, regex tightening, clipboard wrapping, hotkey validation, autostart, single-instance, Qt-scoped Enter key, OUI worker shutdown, PyInstaller hygiene, cleanup batch, doc fixes, version bump)
- ✅ Scaffolded pytest regression suite (24 tests, all green) — `tests/`, `pytest.ini`, `requirements-dev.txt`, `conftest.py`
- ✅ Generated multi-size `icon-v1.ico` from PNG via Pillow
- ✅ Removed duplicate `PyQt5` and dead `keyboard` dependencies from `requirements.txt`
- ✅ Removed installer's `[Tasks] startup` and `{userstartup}\…` entries; app now owns autostart via Startup-folder shortcut
- ✅ Built v2.4.0 installer (`installer-output/MAC-Converter-Setup-v2.4.0.exe`) and standalone executable (`dist/MAC-Converter.exe`)
- ✅ Published v2.4.0 GitHub Release with both artifacts
- ✅ Created GitHub Pages download portal at `docs/` — single-page, dark-theme, auto-fetches latest release
- ✅ Enabled GitHub Pages serving from `/docs` — live at https://aleled.github.io/mac-converter-2/
- ✅ Updated README, TODO, DEVELOPMENT_LOG, CHANGELOG with v2.4.0 content
- ✅ Added SECURITY.md and CONTRIBUTING.md
- ✅ Configured GitHub repo description, homepage URL, and topics

### Earlier Sessions (Session: 2026-02-17)
- ✅ Implemented OUI vendor lookup feature (IEEE database, ~38,900 vendors)
- ✅ Created `oui_lookup.py` standalone module
- ✅ Added vendor popup with countdown, copy-to-clipboard, auto-close
- ✅ Added manual OUI update with real-time percentage progress bar
- ✅ Added searchable OUI database viewer (38,900+ entries)
- ✅ Enhanced Settings dialog with OUI section (scroll area, dark theme fix)
- ✅ Enhanced About dialog with OUI database statistics
- ✅ Fixed app exit bug when closing dialogs (setQuitOnLastWindowClosed)
- ✅ Built v2.3.0 executable and installer
- ✅ Cleaned up old files and updated all documentation

### Current Project State
- All milestones through v2.4.0 completed (including post-release audit and remediation)
- Production-ready release published and reachable via the download portal
- Code is clean, audited, documented, and tested (24/24 regression tests green)

---

## How to Build

### Prerequisites
- Python 3.8+
- PyInstaller (for executable)
- Inno Setup v6+ (for installer, Windows only)

### Build Executable
```bash
pyinstaller mac-converter.spec
# Output: dist/MAC-Converter.exe
```

### Build Installer
```bash
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
# Output: installer-output/MAC-Converter-Setup-v2.4.0.exe
```

---

## Development Guidelines

### When Adding Features
1. Update this TODO.md with new feature items
2. Create feature branch from `dev`
3. Update CHANGELOG.md with changes
4. Update README.md if user-facing
5. Test thoroughly before committing
6. Merge to `dev` branch
7. Push to GitHub

### Code Quality Standards
- No admin rights required for any feature
- Use pynput for hotkey registration
- Store settings in %APPDATA%\mac-converter-2\
- Use dark theme for all UI elements
- Maintain thread-safe operations
- Include error handling and validation
- Clean up debug output before release

---

**Last Updated:** 2026-05-22
**Maintained By:** Alejandro Lichtenfeld
**Repository:** https://github.com/aleled/mac-converter-2
**Download portal:** https://aleled.github.io/mac-converter-2/
