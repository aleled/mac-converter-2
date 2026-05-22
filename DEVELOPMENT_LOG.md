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

## 2026-02-17: v2.3.0 - OUI Vendor Lookup Feature

### Session Summary
- Implemented OUI vendor lookup feature — the major new feature for v2.3.0
- Created standalone `oui_lookup.py` module with thread-safe download, parse, and lookup
- IEEE OUI database (~3.5 MB CSV, ~38,900 vendor entries, ~19,885 unique vendors)

### New Features
- **Vendor Lookup**: Press Enter in format popup to identify MAC manufacturer via OUI prefix
- **Vendor Popup**: Dark-themed popup with vendor name, OUI prefix, countdown timer, and copy button
- **Database Management**: Manual update with real-time percentage progress bar (MB/MB, %)
- **Database Viewer**: Searchable read-only table dialog for browsing all 38,900+ OUI entries
- **Settings**: New OUI section with enable/disable, auto-update toggle, interval (1-90 days), vendor timeout
- **About Dialog**: OUI database stats (entries, unique vendors, file size, download time, location)

### Bug Fixes
- Fixed app exiting when Settings or About dialogs were closed (`setQuitOnLastWindowClosed(False)`)
- Fixed dark theme not applying inside QScrollArea in Settings dialog
- Fixed QGroupBox content clipping (buttons/text cut off at borders)
- Multiple rounds of layout fixes for font sizes, margins, and padding

### Technical Details
- `oui_lookup.py`: Standalone module, no Qt dependency, stdlib-only (urllib, csv, threading)
- OUI CSV stored at `%APPDATA%/mac-converter-2/oui.csv`
- Download uses chunked reads (16KB) with progress callback (supports both string and dict messages)
- Global Enter key detection via temporary pynput listener (runs only while format popup is visible)
- Thread-safe communication via `queue.Queue` objects polled by `QTimer` instances

### Build
- Built executable with PyInstaller: `dist/MAC-Converter.exe` (~48 MB)
- Built installer with Inno Setup v6.5.4: `installer-output/MAC-Converter-Setup-v2.3.0.exe` (~51 MB)
- Cleaned up old files (removed empty `clipboard_hotkey_fixed.py`, old installers)
- Updated all documentation (CHANGELOG.md, README.md, TODO.md, DEVELOPMENT_LOG.md)

---

Each session will be logged here with a summary of work done, pending tasks, and next steps.

---

## 2026-05-14 (Windows/PowerShell Session) — v2.4.0: Full audit, all-finding remediation, GitHub Pages portal

### Engagement scope
Owner-level pass over the whole repository: full code/security audit, fix everything found, ship a public download portal. Four phases planned (audit → fixes → installer-touch → portal). All four delivered in this session.

### Phase 1 — Audit
- Read every tracked source/build/doc file at the root.
- Produced `docs/AUDIT-2026-05-14.md` (572 lines, 37 findings).
- Severity distribution: 5 HIGH, 12 MEDIUM, 20 LOW, 0 CRITICAL.
- Top 5 HIGH findings:
  - F6: `pyperclip` not wrapped — locked clipboard crashes listener
  - F11: OUI download worker race + orphan on dialog close
  - F13: "Start with Windows" checkbox was cosmetic (no `winreg`/shortcut code)
  - F14: Hotkey input not validated on Save — gibberish persists
  - F19: FormatSelectorPopup used a global pynput keyboard listener (captured every keystroke system-wide)

### Phase 2 — Bug fixes (15 commit groups)
Each group references the F-IDs it closes in its commit message:
1. `d262f7a` — pytest infrastructure
2. `885a779` — atomic settings + lock (F7, F16, F23, F28)
3. `9035697` — settings load validation + corrupt recovery (F8, F15, F24)
4. `e669646` — OUI download hardening (F2, F3, F4, F5)
5. `625fd7a` — regex tightening, reject mixed `:`/`-` (F1)
6. `802d9cd` — pyperclip wrapping (F6, F20, F21)
7. `4226c3e` — hotkey validation on Save (F14)
8. `3c146b7` — Startup-folder autostart + installer cleanup (F13, F31)
9. `7a73c83` — single-instance mutex (F25)
10. `ef2a368` — Qt-scoped Enter key, remove pynput listener (F19)
11. `a5704bd` — OUI worker shutdown + re-entrance guard + error sanitization (F11, F12, F18, F26)
12. `6fd6326` — PyInstaller spec: real `.ico`, hidden imports, UPX off (F32, F33, F34); drop `keyboard` dep (F35)
13. `7b21fc1` — cleanup batch: bare excepts, exit_event, timer/listener cleanup, env_load.ps1 (F9, F10, F17, F22, F27, F29, F30, F36)
14. `4688bb6` — README format table + stale TODO claim (F37)
15. `358885c` — version bump to 2.4.0 + CHANGELOG entry

### Phase 3 — Installer
Absorbed into Phase 2 commits 8 and 12. No standalone installer phase needed.

### Phase 4 — GitHub Pages download portal
- Built single-page static portal at `docs/index.html` + `docs/styles.css` + `docs/icon-v1.png`.
- Dark theme matching the app palette (`#2b2b2b`, `#0078d4`).
- Inline JS auto-fetches `https://api.github.com/repos/aleled/mac-converter-2/releases/latest` and updates the download button. Falls back to "Coming soon" if no release exists.
- Operator instructions added at `docs/README.md`.
- Pages enabled on `claude/eloquent-payne-7d7c9c` / `/docs` — live at https://aleled.github.io/mac-converter-2/.

### Release
- Built `dist/MAC-Converter.exe` (51 MB) via PyInstaller.
- Built `installer-output/MAC-Converter-Setup-v2.4.0.exe` (54 MB) via Inno Setup.
- Published GitHub Release `v2.4.0` with both artifacts attached.
- Portal auto-detected the release and the download button is now live.

### Documentation sweep
- README, TODO, DEVELOPMENT_LOG, CHANGELOG all updated for v2.4.0.
- Added SECURITY.md (vulnerability disclosure + audit reference).
- Added CONTRIBUTING.md (consolidates development guidelines).
- Updated GitHub repo metadata (description, homepage URL, topics).

### Test coverage at end of session
- 24/24 pytest regression tests green
- Pure logic in `mac_formats.py`, `oui_lookup.py`, and settings I/O covered
- UI behaviors verified by reading code; manual UI exercise still owed by maintainer

### Pending / owed by maintainer
- Run the installed v2.4.0 app once and exercise: hotkey, Settings save/load, autostart toggle, OUI Update + close mid-download
- After merging PR #1, switch GitHub Pages source from `claude/eloquent-payne-7d7c9c` to `dev` (or wherever PR lands) so Pages tracks the canonical branch
- Optionally: code-sign the exe (out of scope here)

### Artifacts produced this session
- `docs/AUDIT-2026-05-14.md` — security & bug audit
- `docs/superpowers/specs/2026-05-14-full-review-fix-portal-design.md` — engagement-level design spec
- `docs/superpowers/specs/2026-05-14-phase2-bug-fixes-design.md` — Phase 2 design spec
- `docs/superpowers/specs/2026-05-14-phase4-portal-design.md` — Phase 4 design spec
- `docs/superpowers/plans/2026-05-14-phase1-audit.md` — audit implementation plan
- `docs/superpowers/plans/2026-05-14-phase2-bug-fixes.md` — Phase 2 implementation plan
- `docs/index.html`, `docs/styles.css`, `docs/icon-v1.png`, `docs/README.md` — portal files
- `tests/test_mac_formats.py`, `tests/test_oui_lookup.py`, `tests/test_settings_atomic.py`, `tests/test_settings_validate.py` — regression tests
- `requirements-dev.txt`, `pytest.ini`, `tests/__init__.py`, `tests/conftest.py` — test infra
- `icon-v1.ico` — multi-size icon for PyInstaller
- `SECURITY.md`, `CONTRIBUTING.md` — repo policy docs

### Branch state at session end
- Branch: `claude/eloquent-payne-7d7c9c` (pushed to GitHub)
- PR #1 open against `dev`: https://github.com/aleled/mac-converter-2/pull/1
- Release v2.4.0 published: https://github.com/aleled/mac-converter-2/releases/tag/v2.4.0
- Portal live: https://aleled.github.io/mac-converter-2/

---

## 2026-05-15 (Windows/PowerShell Session) — Portal fix, v2.4.1, v2.4.2, full documentation pass

This session followed immediately after the 2026-05-14 v2.4.0 ship. Three issues emerged from user testing, plus a comprehensive documentation expansion request.

### Issue 1: Portal returning 404

The first GitHub Pages build of commit `7b725df` errored with "Page build failed" — Jekyll (which Pages runs by default) choked on the Markdown files in `docs/` (the 133 KB audit, the design specs, the implementation plans).

**Fix:** added `docs/.nojekyll` (commit `166c2be`). The sentinel file tells GitHub Pages to skip Jekyll entirely and serve `docs/` as static files. The new build succeeded on first try. Portal went live at https://aleled.github.io/mac-converter-2/.

### Issue 2: Enter doesn't show the vendor popup (first attempt — v2.4.1)

User reported pressing Enter in the format popup didn't trigger vendor lookup. Initial diagnosis: the v2.4.0 F19 fix replaced the global pynput keyboard listener with a Qt-scoped `QShortcut`, but the popup is a `Qt.Tool` window that doesn't take keyboard focus on Windows.

**First fix (v2.4.1, commit `34260e6`):** added `activateWindow()`, `raise_()`, `setFocus()`, and Win32 `SetForegroundWindow` calls after `show()`. Built and released v2.4.1.

**Result:** insufficient. User reported the issue persisted in v2.4.1.

### Issue 2 (cont): Real fix — v2.4.2

Deeper diagnosis revealed three structural problems:

1. `QDialog` default `focusPolicy` is `Qt.NoFocus` — `setFocus()` was a no-op because the dialog itself wasn't focusable.
2. `SetForegroundWindow` was being rejected by Windows. The converter process didn't "receive the last input event" — pynput's `WH_KEYBOARD_LL` hook is passive, so the actual keypress went to the foreground app.
3. `QShortcut` with `Qt.WidgetWithChildrenShortcut` only fires when the widget or a child has focus. With no focusable children and no focus on the dialog, the shortcut never fired.

**Fix (v2.4.2, commit `fcd3cb3`):**

- Set `Qt.StrongFocus` on `FormatSelectorPopup` so the dialog itself can receive keyboard focus.
- Use `AttachThreadInput` to temporarily merge our thread's input queue with the foreground thread's, satisfying Windows' foreground-steal rules. Then `SetForegroundWindow` succeeds. Then detach.
- Change `QShortcut` context to `Qt.ApplicationShortcut` so any active app window fires the shortcut.
- Add `keyPressEvent` override on the popup for Enter and Escape as belt-and-suspenders.
- Defer focus calls one event-loop tick via `QTimer.singleShot(0, _grab_focus)` so the window is fully realized before we grab focus.
- Show a tray notification ("OUI database is still loading, try again in a moment") when Enter is pressed before the OUI database has finished loading, so the silent-rejection case is no longer invisible.

Built and released v2.4.2 with both `.exe` artifacts. Portal auto-detected the release within 30 seconds. User confirmed: "working fine!"

### Issue 3: Comprehensive documentation pass

User requested that all project elements be documented in Markdown so that "if something breaks we know how it was working so far."

**Deliverables (this session):**

- **`ARCHITECTURE.md` (new, ~12 KB)** — module map, threading model (5 threads), data flow walkthroughs for the three key user paths (hotkey → popup, popup → vendor lookup, OUI download), file locations, 8 key design decisions with their rationale (no-admin constraint, tool-window focus saga, atomic writes + lock, single-instance mutex, OUI HTML rejection, cooperative worker shutdown, Startup-folder autostart, ApplicationShortcut vs WidgetWithChildren), test architecture, security boundaries, known limitations, "where to look when something breaks" table.

- **`TROUBLESHOOTING.md` (new, ~7 KB)** — user-facing diagnostic guide. Sections: hotkey not working, format popup but no vendor, app won't start, unknown vendor, OUI download failures, autostart not surviving reboot, antivirus warnings, tray icon missing, layout glitches, backup/restore, uninstall leftovers, corrupt-settings files, verbose logging.

- **`BUILDING.md` (new, ~6 KB)** — detailed build guide. Prerequisites table, one-time setup, regenerate .ico, build the standalone exe, build the installer, cut a release (version bump checklist, CHANGELOG, full test run, build, smoke test, commit, tag, gh release create), build troubleshooting.

- **`README.md` significantly expanded** — every feature gets a deep paragraph (tray utility, auto-cycling, hotkey, clipboard, format popup, OUI lookup, database management, dark theme, Settings dialog, About dialog, persistence, no-admin, single-instance, pytest), full per-setting reference table, "How it works in 60 seconds" architecture summary, file locations table, documentation map linking all the other docs.

- **`TODO.md` updated** — Milestone 13 (v2.4.1 + v2.4.2 patches), Milestone 14 (documentation pass), Recent Changes section restructured.

- **`DEVELOPMENT_LOG.md`** (this entry).

### Commits this session

1. `166c2be` — `fix(pages): add .nojekyll to disable Jekyll processing`
2. `34260e6` — `fix(ui): restore Enter-to-vendor-lookup; release v2.4.1` (insufficient)
3. `fcd3cb3` — `fix(ui): land Enter-to-vendor-lookup properly; release v2.4.2`
4. (this commit) — `docs: comprehensive documentation pass — ARCHITECTURE, TROUBLESHOOTING, BUILDING, expanded README`

### Branch state at session end

- Branch: `claude/eloquent-payne-7d7c9c`
- PR #1 still open against `dev` with all 2026-05-14 + 2026-05-15 work
- Releases live: v2.4.0, v2.4.1, v2.4.2
- Portal live and serving v2.4.2 as the latest download
- 24/24 pytest tests green
- Documentation: README + ARCHITECTURE + TROUBLESHOOTING + BUILDING + CHANGELOG + CONTRIBUTING + SECURITY + TODO + DEVELOPMENT_LOG + docs/AUDIT + docs/superpowers/specs + docs/superpowers/plans + docs/README

### Lessons learned

- **Windows focus mechanics are subtle.** Three things had to be right simultaneously for the Enter key to work on a `Qt.Tool` popup: dialog focus policy, the Win32 foreground-steal rules, and the `QShortcut` context. Missing any one of them silently broke the feature. Documenting this in ARCHITECTURE.md § 6.2 is essential — anyone who refactors `show_format_popup` in the future needs to preserve all three.

- **Jekyll-by-default on GitHub Pages is a footgun for repos with technical Markdown.** The audit document had section headers with brackets like `[CRITICAL]` and bracketed F-IDs that Jekyll's Liquid templating tried to parse. `.nojekyll` is the standard prophylactic — should be added to any `/docs` folder that contains arbitrary `.md` files.

- **Tray notifications for silent-failure paths are cheap insurance.** The v2.4.2 "OUI database is still loading" notification eliminates a confusing user experience for ~$0 of engineering cost. Worth applying this pattern everywhere a function early-returns under unusual conditions.

- **Subagent-driven development can't fully cover UI fixes.** The F19 → focus-saga sequence happened because the audit subagent for clipboard_hotkey.py Part 4 (Task 7) correctly identified the global pynput listener as a privacy concern, and the fix subagent for Phase 2 Task 10 correctly removed it — but neither could test the resulting UI behavior on Windows. The focus regression was only caught by the user running the actual installer. Future audits should explicitly call out "this change needs UI verification" for any code that touches focus, window flags, or event filtering.

---

## 2026-05-22 (Windows/PowerShell Session) — v2.4.3 + v2.5.0

Two patch/minor releases in one session, both driven by user-reported issues.

### v2.4.3 — Corporate-network TLS interception

User on a corporate network reported the OUI download failing with `[SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate in certificate chain`. Their environment used a TLS-intercepting proxy that re-signed HTTPS with a self-signed CA root — trusted by Windows (because IT installed it) but not by Python's bundled CA list.

**Fix (commits leading to v2.4.3):** added the `truststore` package, which makes `ssl.create_default_context()` use the OS trust store. Same approach pip uses. `truststore.inject_into_ssl()` is called at `oui_lookup` module load; all subsequent `urllib` HTTPS calls use Windows' cert store automatically.

**Belt-and-suspenders:** added an "Import from file…" button to Settings → OUI section. Lets the user point at a `oui.csv` they downloaded via their browser (which uses Windows' cert store and handles the corp CA fine). The app validates the file, atomically replaces the live database, and reloads.

### v2.5.0 — Startup update check

User requested an update-check-on-startup feature. Five-task implementation following the plan at `docs/superpowers/plans/2026-05-22-update-check.md`:

1. New `update_check.py` module — `APP_VERSION = "2.5.0"`, `check_for_update()` returning dict-or-None, `_parse_version()` for tuple comparison. 10 pytest regression tests cover prefix handling, prerelease suffixes, garbage input, and all error paths (URLError, HTTPError, malformed tag, no-update, newer-release).
2. Consolidate `clipboard_hotkey.py` and `oui_lookup.py` version strings to read from `APP_VERSION`. Three previously-hardcoded sites now flow through one constant.
3. Wire into Qt: queue + daemon worker + 1Hz QTimer poll + session-guard flag + main() hook + on_quit cleanup.
4. Replace the stub `show_update_prompt` with a real modal QMessageBox. Upgrade opens the portal via `QDesktopServices.openUrl` and calls `on_quit` so the installer can replace the running exe.
5. Version bump to 2.5.0 + CHANGELOG `[2.5.0]` + doc updates (README "What's new", ARCHITECTURE threading-model row + § 6.8 design decision + § 12 entry, TROUBLESHOOTING "I never see the update prompt", TODO Milestone 16).

### Architecture observations from this session

- **`update_check.py` benefits for free from `oui_lookup.py`'s truststore injection.** Because Python's `ssl` module is monkey-patched at `oui_lookup` import time, any subsequent module that uses `urllib` (including the new `update_check`) inherits the Windows-cert-store behavior. Module load order matters: `oui_lookup` is imported by `clipboard_hotkey` early, before `update_check` does its first network call. If the load order ever changes, document the dependency.
- **Three previously-hardcoded version strings should have been a single constant from day one.** The consolidation in v2.5.0 means future bumps touch one Python file instead of three. The remaining bumps (installer.iss, README, TODO, CHANGELOG) are non-Python and inevitable.
- **"Open portal + exit" beats "auto-download installer" for the Upgrade flow.** Explicitly documented in ARCHITECTURE.md § 6.8 so future contributors don't second-guess it. Auto-download would re-introduce a class of failures (AV interception of the temp .exe, partial downloads, retry logic) that the existing "freshly downloaded installer over running exe" pattern already handles.

### Session output

- `update_check.py`, `tests/test_update_check.py`
- Commits: `bc6e09a` (module + tests), `a6b343c` (version consolidation), `77aea78` (Qt integration), `dc73301` (QMessageBox UI). Doc-pass commit + version bump + release follow.
- Releases: v2.4.3, v2.5.0
- All 34 pytest tests green throughout
