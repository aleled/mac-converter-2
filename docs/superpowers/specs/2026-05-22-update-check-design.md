# Update Check on Startup — Design Spec

**Date:** 2026-05-22
**Author:** Alejandro Lichtenfeld (with Claude)
**Branch:** `claude/eloquent-payne-7d7c9c`
**Target version:** v2.5.0

## Goal

When the user launches the app, automatically check whether a newer release exists on GitHub. If yes, show a modal prompt with the current version, the latest version, and a release-notes excerpt, plus two buttons: **Upgrade** and **Skip**. Upgrade opens the download portal in the user's default browser and exits the app so the installer can replace the running exe. Skip dismisses the prompt for the current session.

## Scope

A small, focused feature. One new pure-logic module, one new test file, light integration into `clipboard_hotkey.py`, three hardcoded version strings consolidated into a single source of truth.

**Not in scope:**
- Auto-downloading the installer
- Persistent "skip this version" or "disable update checks" settings
- Pre-release / beta channel support
- A manual "Check for updates now" menu item
- Differential version diffs or rich Markdown release notes rendering

## Design decisions resolved during brainstorming

- **Upgrade flow:** Open the GitHub Pages download portal in the user's default browser, then exit the app. The browser handles any corporate TLS / proxy complications natively; the existing installer handles upgrading over the running exe.
- **Check frequency:** Every startup. Cached in memory for the session (no persistent timestamp). Simple, predictable, low-volume.
- **Dismissal model:** Two buttons only — Upgrade / Skip. Skip dismisses for the current launch only; the next launch prompts again until the user upgrades. No persistent state.

## Architecture

Mirrors the existing `oui_lookup.py` pattern: a small pure-logic module with no Qt dependency, plus a Qt integration in `clipboard_hotkey.py` that polls a queue.

### New module: `update_check.py`

Single source of truth for the running app version, plus the check function.

```python
APP_VERSION = "2.5.0"

def check_for_update():
    """Returns dict with update info if a newer release exists, else None.
    Silent on network/parse failures — never raises to the caller.
    """
    # GET https://api.github.com/repos/aleled/mac-converter-2/releases/latest
    # Parse tag_name, body, html_url
    # If _parse_version(latest) > _parse_version(current): return dict
    # Else: return None

def _parse_version(s):
    """'v2.5.0' or '2.5.0' -> (2, 5, 0). Stops at first non-numeric component."""
```

The return dict shape:
```python
{
    'current': '2.4.3',
    'latest': '2.5.0',
    'release_url': 'https://github.com/aleled/mac-converter-2/releases/tag/v2.5.0',
    'portal_url': 'https://aleled.github.io/mac-converter-2/',
    'notes_excerpt': '<first ~500 chars of release body>',
}
```

No Qt imports in this module. Uses `urllib.request.urlopen` (truststore-injected at oui_lookup module load — same SSL context will be used here since both modules end up calling `ssl.create_default_context()`).

### `clipboard_hotkey.py` changes

1. **Import `APP_VERSION`** from `update_check` at the top. Use it everywhere the version is currently hardcoded:
   - `AboutDialog` `version_label = QLabel(f"Version {APP_VERSION}")`
   - `DEFAULT_SETTINGS['about']` interpolates `APP_VERSION`
2. **New module-level globals:**
   - `update_check_queue = queue.Queue()` — single-message capacity in practice
   - `_update_prompt_shown_this_session = False` — guard against re-showing if the timer somehow fires twice
3. **New function `_start_update_check()`** — spawns a daemon thread:
   ```python
   def _start_update_check():
       def worker():
           result = update_check.check_for_update()
           if result is not None:
               update_check_queue.put(result)
       threading.Thread(target=worker, daemon=True).start()
   ```
4. **New function `_poll_update_check()`** — called by a QTimer at 1 Hz on the Qt main thread:
   ```python
   def _poll_update_check():
       global _update_prompt_shown_this_session
       try:
           info = update_check_queue.get_nowait()
       except queue.Empty:
           return
       if _update_prompt_shown_this_session:
           return
       _update_prompt_shown_this_session = True
       show_update_prompt(info)
   ```
5. **New function `show_update_prompt(info)`** — Qt main thread, modal QMessageBox:
   ```python
   def show_update_prompt(info):
       msg = QMessageBox()
       msg.setWindowTitle("MAC Converter — Update Available")
       try:
           msg.setWindowIcon(QIcon(get_icon_path()))
       except Exception:
           pass
       msg.setIcon(QMessageBox.Information)
       msg.setText(f"A newer version of MAC Converter is available.\n\n"
                   f"Current: v{info['current']}\n"
                   f"Latest: v{info['latest']}")
       if info.get('notes_excerpt'):
           msg.setDetailedText(info['notes_excerpt'])
       upgrade_btn = msg.addButton("Upgrade", QMessageBox.AcceptRole)
       skip_btn = msg.addButton("Skip", QMessageBox.RejectRole)
       msg.setDefaultButton(upgrade_btn)
       msg.exec_()
       if msg.clickedButton() is upgrade_btn:
           from PyQt5.QtCore import QUrl
           from PyQt5.QtGui import QDesktopServices
           QDesktopServices.openUrl(QUrl(info['portal_url']))
           on_quit(tray_icon, None)
   ```
6. **Hook in `main()`** — after `app.exec_()` is about to start, schedule the check. Store `update_timer` as a module global so `on_quit` can stop it explicitly (mirrors the F27 pattern; standalone QTimer instances aren't reliably stopped by the existing widget-walk in `on_quit`):
   ```python
   # Module-level:
   _update_timer = None  # holds the QTimer; populated by main()

   # In main():
   global _update_timer
   QTimer.singleShot(2000, _start_update_check)
   _update_timer = QTimer()
   _update_timer.timeout.connect(_poll_update_check)
   _update_timer.start(1000)
   ```
   And in `on_quit`, before quitting the app:
   ```python
   if _update_timer is not None:
       _update_timer.stop()
   ```

### `oui_lookup.py` change

Replace the hardcoded UA string:

```python
from update_check import APP_VERSION  # at top
# ...
req = urllib.request.Request(OUI_URL, headers={
    'User-Agent': f'MAC-Converter/{APP_VERSION}'
})
```

This means `oui_lookup.py` gains a dependency on `update_check.py`. Acceptable because `update_check.py` has no other dependencies — the dependency graph stays a DAG.

## Data flow

```
main() startup
  ├─ acquire single-instance mutex
  ├─ initialize tray icon, hotkey listener, OUI db
  ├─ QTimer.singleShot(0, _start_oui_init)       # existing F30 fix
  ├─ QTimer.singleShot(2000, _start_update_check) # NEW: 2s after startup
  └─ app.exec_()

_start_update_check (Qt main thread)
  └─ spawns daemon thread

worker thread
  ├─ update_check.check_for_update()
  │    ├─ urllib GET https://api.github.com/.../releases/latest
  │    ├─ parse JSON
  │    ├─ _parse_version(latest) > _parse_version(current)?
  │    └─ return dict | None
  └─ if dict: update_check_queue.put(dict)

_poll_update_check (Qt main thread, 1Hz QTimer)
  ├─ update_check_queue.get_nowait()
  ├─ if _update_prompt_shown_this_session: return
  ├─ _update_prompt_shown_this_session = True
  └─ show_update_prompt(info)

show_update_prompt (Qt main thread, modal)
  ├─ QMessageBox with Upgrade / Skip buttons
  └─ if Upgrade clicked:
       ├─ QDesktopServices.openUrl(portal_url)  # opens browser
       └─ on_quit(tray_icon, None)               # exits app
```

## Error handling

All paths in `update_check.check_for_update()` are wrapped to return `None` on failure rather than raising:

| Failure | Behavior |
|---------|----------|
| `urllib.error.URLError` (no network, DNS, firewall) | Return `None`. Log to stderr. |
| HTTP 403 (rate limit) | Return `None`. Log to stderr. |
| HTTP 404 (repo deleted or no releases) | Return `None`. |
| JSON parse error | Return `None`. Log to stderr. |
| `tag_name` malformed (no version digits) | Return `None`. |
| Latest version ≤ current version | Return `None`. |
| Any other unexpected exception | Return `None`. Log type. |

No popups are surfaced on failure. The user shouldn't see "couldn't check for updates" noise at every launch on a flaky network.

## Testing

New file: `tests/test_update_check.py`. Five tests:

1. `test_parse_version_handles_v_prefix` — `_parse_version("v2.5.0") == (2, 5, 0)`
2. `test_parse_version_strips_prerelease_suffix` — `_parse_version("2.5.0-beta1") == (2, 5, 0)`
3. `test_check_for_update_no_update` — mock `urlopen` returns a release with `tag_name == f"v{APP_VERSION}"`, expect `None`
4. `test_check_for_update_new_version` — mock `urlopen` returns `tag_name == "v99.0.0"`, expect dict with `latest == "99.0.0"` and `portal_url` populated
5. `test_check_for_update_network_failure` — mock `urlopen` raises `URLError`, expect `None` (no exception escapes)

UI behavior (QMessageBox showing, button responses, app exit on Upgrade) is manually verified — same as other UI fixes.

## Version bump

This is a new feature, so SemVer minor: **v2.5.0**.

Mechanical bumps required:
- `update_check.py:APP_VERSION = "2.5.0"` (new — single source of truth)
- `installer.iss` line 5
- `README.md` header, direct download links, version history
- `TODO.md` header
- `CHANGELOG.md` new `[2.5.0]` section

Removed hardcoded strings:
- `clipboard_hotkey.py:497` `version_label = QLabel("Version 2.4.3")` → `QLabel(f"Version {APP_VERSION}")`
- `clipboard_hotkey.py:1839` `'about': '...v2.4.3...'` → uses `APP_VERSION`
- `oui_lookup.py:71` `'User-Agent': 'MAC-Converter/2.4.3'` → uses `APP_VERSION`

## Documentation updates

- `CHANGELOG.md` — new `[2.5.0]` section: Added — startup update check
- `README.md` — new "Update notifications" feature paragraph; version-history entry
- `ARCHITECTURE.md` — new subsection in §3 (threading model: 6 threads instead of 5 now, counting the update-check worker); new entry in §6 (key design decisions: why we open the portal instead of auto-downloading); new entry in §12 ("Where to look when something breaks") for "update prompt doesn't appear"
- `TROUBLESHOOTING.md` — new entry: "I never see the update prompt" (offline, rate-limited, latest)
- `TODO.md` — new Milestone 15 entry for v2.5.0
- `DEVELOPMENT_LOG.md` — new session entry

## Success criteria

- Launching the app at v2.4.3 prompts with the v2.5.0 release notes within ~3 seconds of startup
- Clicking **Upgrade** opens the portal in the default browser and the app exits cleanly
- Clicking **Skip** dismisses the prompt; no further popup during the session; the prompt re-appears on the next launch
- When `update_check.check_for_update()` is called while running the latest version, it returns `None` and no prompt appears
- Network failures (offline, blocked) produce no user-visible error
- All 24 prior pytest tests still pass; 5 new tests pass; total 29 green

## Deliverable

A single commit (or commit set, if the diff is large enough to split logically) on `claude/eloquent-payne-7d7c9c` adding `update_check.py`, `tests/test_update_check.py`, and the integration changes. Followed by a build + GitHub Release for v2.5.0.
