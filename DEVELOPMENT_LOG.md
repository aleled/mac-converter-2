# Git user info for project commits:
# Name: Alejandro Lichtenfeld
# Email: 4leled@gmail.com
# (Set globally in git config as of 2025-06-04)

# Development Log

## 2025-06-03
- Project initialized
- Documentation and planning files created
- Git repository setup planned

---

## 2025-06-03 (Windows/PowerShell Session)
- Verified and fixed virtual environment activation for PowerShell (`env_load.ps1`).
- Ensured all dependencies are installed and requirements are up to date.
- Set up and verified git remote and branch tracking with GitHub.
- Refactored `clipboard_hotkey.py` for robust hotkey detection on Windows (Alt+Shift+M now works reliably).
- Improved exit handling (Ctrl+C now cleanly exits the app).
- Debug output added for hotkey troubleshooting.

**Instructions for next session (Windows/PowerShell):**
1. **Pull the latest project and notes:**
   ```powershell
   git pull
   ```
2. **Activate the virtual environment:**
   ```powershell
   . .\env_load.ps1
   ```
3. **Install dependencies (if needed):**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Run the app:**
   ```powershell
   python clipboard_hotkey.py
   ```
5. **Check `DEVELOPMENT_LOG.md` and `TODO.md` for progress and next steps.**

**Next steps for future sessions:**
- (Optional) Restore or improve tray icon functionality for Windows.
- (Optional) Replace console format selection with a GUI popup for better UX.
- Continue feature development as per `TODO.md`.
- Remove or reduce debug output if no longer needed.

---

## 2025-06-04 (Windows/PowerShell Session) - PyQt GUI Implementation
- Successfully implemented PyQt5-based format selector GUI as per roadmap requirements:
  - Three-column table: [Format Style] [Upper Case] [Lower Case]
  - Navigation with arrow keys (UP/DOWN/LEFT/RIGHT)
  - ENTER to select, ESC to cancel
  - Clear instructions displayed to user
  - Auto-selects default format (colon-separated uppercase) after 6 seconds timeout
  - Window stays on top and is centered on screen
- Updated `clipboard_hotkey.py` to use PyQt5 GUI instead of console input
- Added PyQt5 to requirements.txt
- Tray icon uses custom icon-v1.png successfully
- Application tested and working correctly

**Current Status:**
- Core MAC address conversion: ✅ Complete
- Global hotkey (Alt+Shift+M): ✅ Complete  
- Clipboard integration: ✅ Complete
- Tray icon with custom logo: ✅ Complete
- PyQt GUI format selector: ✅ Complete

**Next Steps for Future Sessions:**
- Remove debug output if no longer needed
- Add user preferences (hotkey customization, default format)
- Implement autostart functionality
- Create Windows installer with PyInstaller
- Continue feature development as per TODO.md milestones

---

## 2025-06-04 (Windows/PowerShell Session)
- Updated `clipboard_hotkey.py` to use `icon-v1.png` as the tray icon/logo on all platforms (including Windows).
- Tray icon now loads the PNG; falls back to old icon if loading fails.
- Tray icon is now always started, not just on Linux/Mac.
- Ready for further UI/UX improvements (e.g., GUI format selection popup).

---

## 2025-06-04
- [Documentation and maintenance update](CHANGELOG.md):
  - Expanded docstrings for all code and tests
  - Documented Windows focus bug and workarounds
  - Moved old/unused files to old/
  - Updated all documentation files
  - See CHANGELOG.md for details

---

## [2025-06-05]
- Debugged and improved MAC format selector dialog: ensured only columns 1/2 are selectable, highlight is visible, and navigation is robust.
- Added detailed debug output for all navigation and selection actions, including cell state printout.
- Reduced dialog spam in console for easier debugging.
- All changes committed and session state saved for seamless continuation in next session.

---

## 2025-06-06
- Finalized UI/UX: modern, robust, and visually clear format selector dialog.
- Hotkey (Alt+Shift+M) is robust, suppressed, and requires admin on Windows.
- Info box always shows the correct MAC address from the clipboard.
- Removed all legacy/unused code and debug output.
- Documentation and comments updated for clarity.
- Tray quit is clean and error-free.
- v2.0 stable milestone reached.

## Next Steps
- Optional polish, packaging, and user feedback.

---

## 2025-06-07
- Added persistent user preferences: autostart, default format, timer, about/credits/license info (settings stored in %APPDATA%/mac-converter-2/settings.json)
- Added settings dialog accessible from tray menu (change preferences: autostart, default format, timer, etc.)
- Added About dialog with app info, author, credits, and MIT license
- App always loads/saves settings from %APPDATA%/mac-converter-2/settings.json
- App uses default format and timer from settings
- Implemented autostart logic: add/remove from Windows startup based on user preference
- Added robust error handling for settings file
- Info box always shows correct MAC address from clipboard
- Minor UI/UX polish and finalized English phrasing

---

## 2025-06-07: UI/UX and Window Management Guidelines Added

- Added general guidelines for window independence, hotkey behavior, and tray menu window exclusivity to documentation.
- See README.md and TODO.md for details.

---

## 2025-06-07: Version Bump

- Created new branch feature/v2.1.0 for continued development.
- Updated version references to 2.1.0 in documentation.

---

## 2025-06-07 (Windows/PowerShell Session) - Hotkey Admin Rights Removed
- Replaced keyboard package (required admin) with pynput for global hotkey registration.
- App no longer requires administrator rights for hotkey functionality.
- Updated all documentation and code to reflect this permanent design constraint: **the app must never require admin rights to run or register hotkeys**.

---

## 2025-06-07: UI/UX Baseline Established

- Dialog layout, color palette, and controls are now documented in README.md.
- All headers/cells left-aligned, consistent widths, modern dark theme.
- Controls and info/instructions always visible.
- See README.md for ASCII diagram and color/UX notes.
- Maintain this as the baseline for all future UI/UX changes.

---

---

## 2025-12-31: v2.2.0 Production Release with Windows Installer

### Session Summary
- Created professional Windows installer for MAC Converter v2.2.0 using PyInstaller and Inno Setup
- Updated installer script version from 2.1.0 to 2.2.0
- Built standalone executable: `dist/MAC-Converter.exe` (55 MB)
- Generated installer: `installer-output/MAC-Converter-Setup-v2.2.0.exe` (58 MB)

### Installer Features
- Professional Inno Setup wizard-style installation
- Default install location: `C:\Program Files\MAC-Converter`
- Optional desktop shortcut (unchecked by default)
- Optional Windows startup entry (unchecked by default)
- Includes README.md and LICENSE.txt
- Uninstaller with option to remove user settings from `%APPDATA%\mac-converter-2`
- No admin rights required for installation or runtime
- Automatic app launch after installation (optional)

### Build Process
1. Updated `installer.iss` version from 2.1.0 to 2.2.0
2. Built executable with PyInstaller using `mac-converter.spec`
   - Entry point: `clipboard_hotkey.py`
   - Includes: `icon-v1.png`, `pynput` hidden imports
   - Output: 55 MB standalone executable
3. Built installer with Inno Setup (v6.5.4)
   - Compressed all files (executable, icon, docs)
   - Created digital signature metadata
   - Final installer: 58 MB

### Application Readiness Verification
- ✅ Auto-cycling MAC format converter (0→1→2→...→9→0)
- ✅ Configurable global hotkey (default alt+shift+m)
- ✅ Tray notifications with configurable duration
- ✅ Settings dialog with dark theme and grouped options
- ✅ About dialog with app info and clickable GitHub link
- ✅ No admin rights required (uses pynput, not admin-dependent keyboard lib)
- ✅ Settings persistence in %APPDATA%\mac-converter-2\settings.json

### Release Artifacts
- **Installer**: `installer-output/MAC-Converter-Setup-v2.2.0.exe`
- **Standalone Executable**: `dist/MAC-Converter.exe`
- **Source**: Latest code in `clipboard_hotkey.py` with dark theme UI enhancements

### Next Steps for Future Sessions
- Deploy installer to GitHub releases page
- Create user installation guide
- Monitor feedback from end users
- Plan v2.3.0 features (if applicable)

---

Each session will be logged here with a summary of work done, pending tasks, and next steps.
