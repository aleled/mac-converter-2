# Phase 2 — Bug Fixes Design Spec

**Date:** 2026-05-14
**Author:** Alejandro Lichtenfeld (with Claude)
**Branch:** `claude/eloquent-payne-7d7c9c`
**Parent spec:** `docs/superpowers/specs/2026-05-14-full-review-fix-portal-design.md`
**Audit input:** `docs/AUDIT-2026-05-14.md` (37 findings)

## Goal

Fix every finding from the Phase 1 audit. End state: a `dev`-mergeable branch with all 37 issues remediated, a regression test suite covering the pure-logic fixes, a Windows installer that produces a single-source-of-truth autostart, and the codebase tagged v2.4.0.

## Scope

All 37 audit findings (HIGH + MEDIUM + LOW) — confirmed by the user. No new features. No refactoring outside what a fix requires.

**Phase 3 absorption.** The parent spec defined Phase 3 ("Installer") as a conditional separate phase. Two installer-side findings exist (F31 — Startup-folder shortcut conflict; F33/F34 — `mac-converter.spec` settings). These are tightly coupled to Phase 2 code changes (F13 implements autostart, which requires removing F31's installer task) and are too small to justify a separate spec/plan cycle. Phase 3 is therefore absorbed into Phase 2 commits 8 and 12. No separate Phase 3 plan will be written.

## Design decisions resolved during brainstorming

- **F13+F31 autostart mechanism:** the app owns a Startup-folder `.lnk` shortcut. The installer's `[Tasks] startup` entry is removed. Single source of truth.
- **Commit granularity:** one commit per logical fix group (≈15 commits), not per finding. Each commit is self-contained and references the F-IDs it closes.
- **Version bump:** 2.4.0 in Phase 2. F13, F14, F19, and F32 produce user-visible behavior changes that warrant a release.
- **Tests:** `pytest` + `tests/` directory + `requirements-dev.txt`. Regression tests for pure-logic fixes in `mac_formats.py` and `oui_lookup.py`, plus settings load/save. UI fixes in `clipboard_hotkey.py` manually verified.
- **UPX (F34):** flip `upx=False` in `mac-converter.spec`. Trades ~30% binary size for fewer AV false positives. Acceptable for a free-distribution tool.
- **Corrupt-settings recovery:** rename `settings.json` to `settings.json.corrupt-<unix-ts>` before falling back to defaults. User can recover settings manually; the file isn't silently obliterated.

## Architecture (key patterns introduced)

- **Atomic JSON write** — `save_settings` writes to `path.tmp` and calls `os.replace(tmp, path)`. Single `_settings_lock = threading.Lock()` wraps every `save_settings` call. Three producers funnel through it: listener thread, Qt main, OUI auto-update worker.
- **Atomic OUI replace** — in `oui_lookup.OUIDatabase.download`, the existing temp-then-rename sequence becomes a single `os.replace(temp_path, self.oui_path)` call (Windows-safe, atomic where the filesystem supports it).
- **`_validate_settings(d) -> dict`** — pure function applied after JSON parse: coerces/clamps each known key, falls back to defaults per-key when the value is wrong type or out of range. Also defensively applied before save to prevent garbage from being persisted.
- **`set_autostart_enabled(bool)` / `is_autostart_enabled()`** — manage `%APPDATA%\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk` via `pywin32`'s `WScript.Shell` COM dispatch. Reads/writes are file-system operations; idempotent.
- **Single-instance mutex** — Win32 named mutex via `pywin32` at app entry. If acquisition fails, show a brief tray notification "MAC Converter is already running" and exit cleanly.
- **Qt-scoped Enter key** — `FormatSelectorPopup` uses `QShortcut(QKeySequence("Return"), self)` instead of a global `pynput.keyboard.Listener`. Retires the system-wide keyboard hook entirely.
- **OUI worker cooperative shutdown** — worker checks a `threading.Event` between download chunks. `OUIDownloadDialog.closeEvent` sets the event and `join(timeout=2.0)`. `on_quit` also joins the worker before `app.quit()` so daemon-kill cannot interrupt `os.replace`.

## Component groups (commits in execution order)

1. **Test infrastructure** — `tests/`, `pytest.ini`, `requirements-dev.txt`. Verifies `python -m pytest` exits 0 with zero tests collected.
2. **Atomic settings + lock** — closes F7, F16, F23, F28.
3. **Settings load validation + corrupt-file recovery** — closes F8, F15, F24. Regression test.
4. **OUI download hardening** — closes F2, F3, F4, F5. Adds `os.replace`, content sniff (reject if response starts with `<!DOCTYPE` or `<html` or `Content-Type` is `text/html`), parse-zero guard, response context manager. Regression tests via mocked `urlopen`.
5. **Regex tightening** — closes F1. Split alternative so mixed `:`/`-` is rejected. Regression test.
6. **Clipboard wrapping** — closes F6, F20, F21. Three `try/except PyperclipException` blocks; on failure show a brief tray notification.
7. **Hotkey validation on Save** — closes F14. Validate via `pynput.keyboard.HotKey.parse`; on failure show inline error and refuse save.
8. **Autostart via Startup-folder shortcut** — closes F13 and F31. New helpers, hook to existing checkbox, remove `[Tasks] startup` line and `Icons` entry from `installer.iss`.
9. **Single-instance mutex** — closes F25.
10. **Format popup Enter key scoped to Qt** — closes F19. Removes pynput listener and its plumbing.
11. **OUI worker cooperative shutdown + re-entrance guard** — closes F11, F18, F26, plus F12 (error-message sanitization: strip absolute paths from user-facing strings).
12. **PyInstaller + dep hygiene** — closes F32 (generate `icon-v1.ico` from PNG; `icon='icon-v1.ico'` in spec), F33 (`pystray._win32` hidden import), F35 (drop `keyboard` from `requirements.txt`), F34 (`upx=False`).
13. **Cleanup batch** — closes F9, F10, F17, F22 (bare-except cleanup, 15 sites), F27 (timer stops in `on_quit`), F29 (`listener.join(timeout=2.0)`), F30 (defer OUI auto-update one Qt tick after `app.exec_()`), F36 (env_load.ps1 ANSI escape fix).
14. **Documentation fixes** — closes F37 (README format 9/10 renamed "Hyphen-6char (Cisco-style)"), removes stale `last_format_index` claim from TODO.md, audits README autostart phrasing (now actually true post-commit 8).
15. **Version bump to 2.4.0 + CHANGELOG `[2.4.0]` section** — bump in `installer.iss:5`, `oui_lookup.py:69` (User-Agent), `AboutDialog` version label (`clipboard_hotkey.py:304`), README header, README version-history table. CHANGELOG entry groups by Added/Changed/Fixed; references the F-IDs each commit closed.

## Data flow changes

- `save_settings` now serializes under `_settings_lock`. No call-site changes required; the lock is acquired inside the function.
- `load_settings` on first call: read → parse → `_validate_settings`. On `JSONDecodeError`: rename `settings.json` to `settings.json.corrupt-<unix-ts>`, log to stderr, return `DEFAULT_SETTINGS`.
- `pyperclip.paste()` / `pyperclip.copy()` failures: caught, surfaced via `tray_icon.notify("Clipboard busy, try again", "MAC Converter")`. Listener thread does NOT die.
- Autostart toggle: write or delete `%APPDATA%\…\Startup\MAC-Converter.lnk`. State is queried via `is_autostart_enabled()` (file exists check) when the Settings dialog opens.
- OUI download: response opened in `with` block; chunks read inside; `_cancel_event` checked between chunks. On cancel: discard temp file, return cleanly. On finish: `os.replace(tmp, oui.csv)`.
- App startup: try to acquire named mutex. On failure: notify + exit. On success: hold for process lifetime.

## Error handling changes (user-visible)

- Locked clipboard → tray notification "Clipboard busy, try again" instead of silent listener death.
- Corrupt `settings.json` → renamed to `settings.json.corrupt-<unix-ts>`, defaults loaded, app continues. Stderr log lists the renamed file path.
- Invalid hotkey on Save → red error label in the dialog. Save button refused. Settings file not touched.
- OUI download HTML hijack or zero-entry parse → rejected. Prior `oui.csv` preserved. Error popup explains what happened.
- App already running → tray notification "MAC Converter is already running" + clean exit. No double-fire.
- Format popup Enter key while typing in another app → no effect anymore (was a system-wide capture before).

## Testing

- `tests/test_mac_formats.py`
  - F1 regression: `detect_mac("00-1A:2B-3C:4D-5E")` returns `None`.
  - Happy-path: parametrized test verifying every input in the 10 canonical formats round-trips.
- `tests/test_oui_lookup.py`
  - F2 regression: simulate rename failure mid-replace, assert prior `oui.csv` is preserved.
  - F3 regression: `urlopen` mock returns HTML payload starting with `<!DOCTYPE`; download rejects.
  - F4 regression: mocked `urlopen` raises mid-read; assert `response.__exit__` was called.
  - F5 regression: mock OUI file with zero parseable rows; `load()` returns `(False, "Empty database")`.
- `tests/test_settings.py`
  - F8/F15 regression: `_validate_settings({"last_format_index": "garbage", "notification_duration": -1})` returns defaults for both keys.
  - F24 regression: write a corrupt `settings.json`, call `load_settings`, assert corrupt file was renamed and defaults returned.
  - F7/F23 regression: write to settings.json.tmp succeeds, but simulated crash before `os.replace`; assert original file untouched.
- UI behaviors verified manually after Phase 2 lands: launch app, hotkey flow, popup behavior, settings save/load, autostart toggle creates/removes `.lnk`, single-instance check fires when launching a second copy.

## Out of scope

- Splitting `clipboard_hotkey.py` into multiple modules (separate maintainability concern, not a bug).
- Adding macOS/Linux support beyond what already exists.
- Code signing the installer or the executable.
- CI/CD workflows or automated release pipelines.
- Localization.
- Replacing PyQt5 with PyQt6/PySide.
- Reorganizing dialog classes; existing structure is kept.

## Success criteria

- All 37 findings closed; CHANGELOG `[2.4.0]` section enumerates the fixes.
- `python -m pytest` passes locally (all regression tests green).
- App launches, hotkey flow works end-to-end including OUI lookup.
- Autostart toggle creates/removes a real `.lnk` that survives reboot.
- A second app launch is rejected with a tray notification.
- The Format popup no longer interferes with typing in other apps.
- `installer.iss` no longer has `[Tasks] startup` / `{userstartup}\…` entries.
- `mac-converter.spec` references a real `.ico` and has `upx=False`.
- `requirements.txt` no longer lists `keyboard`.
- Version 2.4.0 appears consistently across all surfaces.

## Deliverable

A branch (`claude/eloquent-payne-7d7c9c`) with ≈15 atomic commits ready for a single PR against `dev`. No code pushed to GitHub until the user opens the PR (controller will offer to push when Phase 2 lands).
