# Update Check on Startup — Implementation Plan (v2.5.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship v2.5.0 with a startup update-check that prompts the user via a modal QMessageBox when a newer release is available on GitHub, with Upgrade/Skip buttons.

**Architecture:** New pure-logic module `update_check.py` mirrors the existing `oui_lookup.py` pattern — no Qt dependency, urllib + truststore for the GitHub API call, defensive return-`None`-on-failure semantics. Qt integration in `clipboard_hotkey.py`: daemon worker thread + queue + 1Hz QTimer poll + modal QMessageBox. `APP_VERSION` becomes the single source of truth for the version string, replacing three currently-hardcoded sites.

**Tech Stack:** Python 3.8+, urllib (stdlib), truststore (already a runtime dependency since v2.4.3), PyQt5 (QMessageBox, QTimer, QDesktopServices), pytest + unittest.mock for tests.

---

## Conventions used in every task

- **Working directory:** `C:\working\mac-converter-2\.claude\worktrees\eloquent-payne-7d7c9c`
- **Activate venv before pytest:** PowerShell `. .\venv\Scripts\Activate.ps1` or bash `source venv/Scripts/activate`. The venv is already populated with truststore, PyQt5, pynput, pytest, etc.
- **Commit message style:** match existing repo style — short imperative subject, blank line, body explaining *why*, end with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.
- **Manual UI verification:** the QMessageBox flow can't be tested by pytest. Steps that say "Manual verification" are advisory checks the controller / user runs after the commit lands; subagents should report DONE after the code change + tests + commit, not block on UI exercise.
- **All tests run from worktree root:** `python -m pytest -v`. Should always end with **all** tests green (24 prior + 5 new = 29 by the end of Task 2).

---

## Task 1: Create `update_check.py` with TDD

**Files:**
- Create: `update_check.py`
- Create: `tests/test_update_check.py`

- [ ] **Step 1.1: Write the failing tests**

Write `tests/test_update_check.py` with this exact content:

```python
"""Regression tests for the startup update-check module."""

import json
from io import BytesIO
from unittest.mock import patch, MagicMock
import urllib.error

import pytest

import update_check


def test_parse_version_handles_v_prefix():
    assert update_check._parse_version("v2.5.0") == (2, 5, 0)


def test_parse_version_handles_no_v_prefix():
    assert update_check._parse_version("2.5.0") == (2, 5, 0)


def test_parse_version_strips_prerelease_suffix():
    assert update_check._parse_version("2.5.0-beta1") == (2, 5, 0)


def test_parse_version_handles_two_segments():
    assert update_check._parse_version("v3.0") == (3, 0)


def test_parse_version_returns_empty_tuple_on_garbage():
    assert update_check._parse_version("not-a-version") == ()


def _mock_release_response(tag_name, body="release notes here", html_url=None):
    """Build a mock urlopen response shaped like the GitHub Releases API."""
    if html_url is None:
        html_url = f"https://github.com/aleled/mac-converter-2/releases/tag/{tag_name}"
    payload = json.dumps({
        "tag_name": tag_name,
        "body": body,
        "html_url": html_url,
    }).encode("utf-8")
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *a: None
    return response


def test_check_for_update_returns_none_when_already_latest(monkeypatch):
    """If the installed version equals the latest release, return None."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               return_value=_mock_release_response("v2.5.0")):
        result = update_check.check_for_update()
    assert result is None


def test_check_for_update_returns_dict_when_newer_release(monkeypatch):
    """When the latest release is newer, return a dict with current/latest/urls."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               return_value=_mock_release_response("v99.0.0", body="big new things")):
        result = update_check.check_for_update()
    assert result is not None
    assert result["current"] == "2.5.0"
    assert result["latest"] == "99.0.0"
    assert "99.0.0" in result["release_url"]
    assert result["portal_url"] == "https://aleled.github.io/mac-converter-2/"
    assert "big new things" in result["notes_excerpt"]


def test_check_for_update_returns_none_on_network_failure(monkeypatch):
    """URLError (no network, DNS failure, firewall) returns None without raising."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               side_effect=urllib.error.URLError("Network unreachable")):
        result = update_check.check_for_update()
    assert result is None


def test_check_for_update_returns_none_on_http_error(monkeypatch):
    """HTTPError (e.g. rate limit, 404) returns None without raising."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               side_effect=urllib.error.HTTPError(
                   "url", 403, "Forbidden", {}, BytesIO(b"rate limited"))):
        result = update_check.check_for_update()
    assert result is None


def test_check_for_update_returns_none_on_malformed_tag(monkeypatch):
    """If tag_name has no parseable version digits, return None."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               return_value=_mock_release_response("some-non-semver-tag")):
        result = update_check.check_for_update()
    assert result is None
```

- [ ] **Step 1.2: Run the tests to verify they FAIL**

Run from the worktree root with the venv active:

```bash
python -m pytest tests/test_update_check.py -v
```

Expected: import-time `ModuleNotFoundError: No module named 'update_check'` (because the module doesn't exist yet). All tests fail. That's correct — we'll implement next.

- [ ] **Step 1.3: Implement `update_check.py`**

Write `update_check.py` at the worktree root with this exact content:

```python
"""
update_check.py

Startup update check for MAC Address Converter.

Single source of truth for the running app version (APP_VERSION).
Fetches the latest release from the GitHub Releases API and reports
whether a newer version is available. Designed to fail silently:
all error paths return None rather than raising, so the caller can
unconditionally invoke this without wrapping in try/except.

Truststore (imported and ssl-injected by oui_lookup.py at module load)
means urllib uses Windows' certificate store and works on corporate
networks with TLS-intercepting proxies.
"""

import json
import sys
import urllib.error
import urllib.request

APP_VERSION = "2.5.0"

# The owner/repo path for the GitHub Releases API call. Centralised so
# tests can monkeypatch it if needed in the future, and so any rename
# of the repo can be done in one place.
GITHUB_REPO = "aleled/mac-converter-2"

# URL the Upgrade button opens in the user's default browser.
PORTAL_URL = "https://aleled.github.io/mac-converter-2/"

# How much of the release body to surface in the "details" pane.
_NOTES_EXCERPT_LIMIT = 500


def _parse_version(s):
    """Parse a version string like 'v2.5.0' or '2.5.0-beta1' into a tuple of ints.

    Strips a leading 'v' (case-insensitive). Splits on '.'. Stops at the
    first segment that isn't purely numeric (so pre-release suffixes are
    ignored). Returns an empty tuple if no numeric segments are found.
    """
    if not isinstance(s, str):
        return ()
    s = s.lstrip("vV").strip()
    parts = []
    for segment in s.split("."):
        # Strip pre-release suffix from this segment: "0-beta1" -> "0"
        digits = []
        for ch in segment:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        if not digits:
            break
        parts.append(int("".join(digits)))
    return tuple(parts)


def check_for_update():
    """Return a dict describing an available update, or None.

    Return dict shape:
        {
            'current': str,        # e.g. "2.5.0"
            'latest': str,         # e.g. "3.0.0"
            'release_url': str,    # github.com/.../releases/tag/v3.0.0
            'portal_url': str,     # the github.io download portal
            'notes_excerpt': str,  # first N chars of release body
        }

    Returns None if:
      - The HTTP request fails for any reason (network, DNS, rate-limit, etc.)
      - The JSON is malformed
      - The tag_name doesn't parse to a usable version tuple
      - The latest version is not strictly greater than APP_VERSION
    """
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"MAC-Converter/{APP_VERSION}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[update_check] HTTP error: {e}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"[update_check] Network error: {e}", file=sys.stderr)
        return None
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[update_check] Parse error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[update_check] Unexpected error: {type(e).__name__}: {e}",
              file=sys.stderr)
        return None

    tag_name = data.get("tag_name", "")
    body = data.get("body", "") or ""
    release_url = data.get("html_url", "") or ""

    latest_tuple = _parse_version(tag_name)
    current_tuple = _parse_version(APP_VERSION)
    if not latest_tuple or not current_tuple:
        return None
    if latest_tuple <= current_tuple:
        return None

    latest_clean = tag_name.lstrip("vV").strip()

    return {
        "current": APP_VERSION,
        "latest": latest_clean,
        "release_url": release_url or
            f"https://github.com/{GITHUB_REPO}/releases/tag/{tag_name}",
        "portal_url": PORTAL_URL,
        "notes_excerpt": body[:_NOTES_EXCERPT_LIMIT],
    }
```

- [ ] **Step 1.4: Run the tests to verify they PASS**

```bash
python -m pytest tests/test_update_check.py -v
```

Expected: 10 PASSES (5 `_parse_version` tests + 5 `check_for_update` tests). Plus run the full suite to confirm no regressions:

```bash
python -m pytest -q
```

Expected: 34 passed (24 prior + 10 new).

- [ ] **Step 1.5: Commit**

```bash
git add update_check.py tests/test_update_check.py
git commit -m "$(cat <<'EOF'
feat: add update_check module with version comparison and GitHub API fetch

New pure-logic module (no Qt dependency) for v2.5.0's startup update
check. APP_VERSION becomes the single source of truth for the running
app version. check_for_update() fetches the latest release via the
GitHub Releases API and returns a dict if a newer version exists,
None otherwise. All error paths (network, parse, rate-limit, etc.)
return None silently — caller never has to wrap in try/except.

10 pytest regression tests cover _parse_version (v-prefix, no-prefix,
prerelease suffix, two-segment, garbage) and check_for_update (already
latest, newer release, URLError, HTTPError, malformed tag).

Closes part of the v2.5.0 update-check feature; remaining work in
clipboard_hotkey.py integration and version-string consolidation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Consolidate version strings to APP_VERSION (single source of truth)

**Files:**
- Modify: `clipboard_hotkey.py` — replace two hardcoded version strings (lines ~497 and ~1839) with `APP_VERSION`
- Modify: `oui_lookup.py` — User-Agent uses `APP_VERSION` (line ~71)

- [ ] **Step 2.1: Add `update_check` import to `clipboard_hotkey.py`**

Locate the existing import block at the top of `clipboard_hotkey.py`. Run:

```bash
grep -n "^from update_check\|^import update_check\|^from oui_lookup" clipboard_hotkey.py
```

Find the existing `from oui_lookup import OUIDatabase` line. Add the new import right after it:

```python
from update_check import APP_VERSION
```

- [ ] **Step 2.2: Replace `Version 2.4.3` in AboutDialog**

```bash
grep -n "Version 2.4.3" clipboard_hotkey.py
```

The grep should report line ~497 with `version_label = QLabel("Version 2.4.3")`. Replace exactly:

Old:
```python
        version_label = QLabel("Version 2.4.3")
```

New:
```python
        version_label = QLabel(f"Version {APP_VERSION}")
```

- [ ] **Step 2.3: Replace `v2.4.3` in DEFAULT_SETTINGS 'about' string**

```bash
grep -n "MAC Address Converter Utility v2" clipboard_hotkey.py
```

Should report line ~1839. Replace exactly:

Old:
```python
    'about': 'MAC Address Converter Utility v2.4.3\nAuthor: Alejandro Lichtenfeld\nLicense: MIT\nhttps://github.com/aleled/mac-converter-2',
```

New:
```python
    'about': f'MAC Address Converter Utility v{APP_VERSION}\nAuthor: Alejandro Lichtenfeld\nLicense: MIT\nhttps://github.com/aleled/mac-converter-2',
```

- [ ] **Step 2.4: Use APP_VERSION in `oui_lookup.py` User-Agent**

```bash
grep -n "MAC-Converter/" oui_lookup.py
```

Should report line ~71. There's a subtlety here: `oui_lookup.py` is imported by `clipboard_hotkey.py`, and `update_check.py` will be imported by both. To avoid a circular import (since `update_check` is small and has no other imports), make `oui_lookup.py` import `APP_VERSION` from `update_check`.

Add at the top of `oui_lookup.py`, after the existing imports:

```python
from update_check import APP_VERSION
```

Then replace exactly:

Old:
```python
                'User-Agent': 'MAC-Converter/2.4.3'
```

New:
```python
                'User-Agent': f'MAC-Converter/{APP_VERSION}'
```

- [ ] **Step 2.5: Verify imports + full pytest suite**

```bash
python -c "import clipboard_hotkey; print('clipboard_hotkey import ok')"
python -c "import oui_lookup; print('oui_lookup import ok')"
python -c "import update_check; print('update_check.APP_VERSION =', update_check.APP_VERSION)"
```

Expected: three `ok` / value lines, no ImportError.

```bash
python -m pytest -q
```

Expected: 34 passed (no regressions).

- [ ] **Step 2.6: Final sanity grep — no stray version strings should remain**

```bash
grep -n "2\.4\.3\|2\.4\.2\|2\.4\.1\|2\.4\.0" clipboard_hotkey.py oui_lookup.py update_check.py
```

Expected: zero matches in source files (any references in the CHANGELOG history are fine — that file isn't part of this grep).

- [ ] **Step 2.7: Commit**

```bash
git add clipboard_hotkey.py oui_lookup.py
git commit -m "$(cat <<'EOF'
refactor: consolidate version strings via APP_VERSION single source of truth

Three previously-hardcoded version strings now read from
update_check.APP_VERSION:

- clipboard_hotkey.py AboutDialog version_label
- clipboard_hotkey.py DEFAULT_SETTINGS 'about' text
- oui_lookup.py urllib User-Agent

Future version bumps now touch one Python source file (update_check.py)
instead of three. Documented in BUILDING.md's release checklist update
(separate commit).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Integrate update check into `clipboard_hotkey.py` (queue + timer + worker)

**Files:**
- Modify: `clipboard_hotkey.py` — add queue, timer, worker function, poll function, main() hook, on_quit cleanup

This task wires `update_check.check_for_update()` into the running app. The QMessageBox UI is added in Task 4.

- [ ] **Step 3.1: Add module-level globals near the other OUI globals**

Run to locate them:

```bash
grep -n "_oui_download_in_progress\|format_popup_request_queue\|vendor_lookup_request_queue" clipboard_hotkey.py | head -5
```

Find the existing queue declarations near the top of the file (around line 100–120). Add immediately after the last queue declaration:

```python
# v2.5.0 — update check at startup
update_check_queue = queue.Queue()
_update_prompt_shown_this_session = False
_update_timer = None  # set in main(); referenced by on_quit
```

- [ ] **Step 3.2: Add `update_check` import (if not already there from Task 2)**

```bash
grep -n "^import update_check\|^from update_check" clipboard_hotkey.py
```

Expected: one line `from update_check import APP_VERSION` from Task 2. Modify it to also import the module:

Replace:
```python
from update_check import APP_VERSION
```

with:
```python
import update_check
from update_check import APP_VERSION
```

- [ ] **Step 3.3: Add the `_start_update_check` worker spawner**

Find a good spot — near the existing `tray_app()` or `listen_hotkey()` functions, alongside the other top-level helpers. Add this function:

```python
def _start_update_check():
    """Spawn a daemon thread that calls update_check.check_for_update().

    On a positive result (a newer release exists), the result dict is
    placed onto update_check_queue. _poll_update_check (called by the
    QTimer on the Qt main thread) picks it up and shows the prompt.

    All failure paths inside check_for_update return None silently —
    nothing is queued on failure, no popup is shown.
    """
    def worker():
        result = update_check.check_for_update()
        if result is not None:
            update_check_queue.put(result)
    threading.Thread(target=worker, daemon=True).start()
```

- [ ] **Step 3.4: Add the `_poll_update_check` Qt-thread poller**

Add immediately after `_start_update_check`:

```python
def _poll_update_check():
    """Drain update_check_queue. Shows the upgrade prompt at most once per session."""
    global _update_prompt_shown_this_session
    try:
        info = update_check_queue.get_nowait()
    except queue.Empty:
        return
    if _update_prompt_shown_this_session:
        return  # already shown in this session; subsequent finds are no-ops
    _update_prompt_shown_this_session = True
    show_update_prompt(info)
```

Note: `show_update_prompt` is the QMessageBox function added in Task 4. The function call here will raise `NameError` until Task 4 lands, but that's fine because the queue is only populated when a real update exists, and `_poll_update_check` is only called by the timer that we're about to wire up. The worktree's pytest suite doesn't exercise this code path, so Task 3 commits cleanly.

If you want belt-and-suspenders against an accidental partial state, add a placeholder stub before Task 4 ships:

```python
def show_update_prompt(info):
    """Stub — real implementation lands in Task 4."""
    print(f"[update_check] (stub) update available: {info.get('latest')}",
          file=sys.stderr)
```

The stub gets replaced wholesale in Task 4.

- [ ] **Step 3.5: Wire into `main()`**

```bash
grep -n "^def main():" clipboard_hotkey.py
```

Find the body of `main()`. Locate the existing call to `QTimer.singleShot(0, _start_oui_init)` or the equivalent OUI deferred call (the F30 fix from v2.4.0). Right after that, add:

```python
    # v2.5.0: schedule update check 2 seconds after startup so the tray
    # icon is fully alive before any prompt. Worker runs in a daemon
    # thread; results are picked up by _update_timer below.
    QTimer.singleShot(2000, _start_update_check)

    global _update_timer
    _update_timer = QTimer()
    _update_timer.timeout.connect(_poll_update_check)
    _update_timer.start(1000)  # 1 Hz poll of update_check_queue
```

- [ ] **Step 3.6: Stop `_update_timer` in `on_quit`**

```bash
grep -n "^def on_quit" clipboard_hotkey.py
```

Find the body. Add immediately after the existing `icon.stop()` / `listener.stop()` calls but before any sleep/join logic:

```python
    if _update_timer is not None:
        _update_timer.stop()
```

- [ ] **Step 3.7: Verify imports + tests still green**

```bash
python -c "import clipboard_hotkey; print('import ok')"
python -m pytest -q
```

Expected: import ok; 34 passed (no test regression).

- [ ] **Step 3.8: Commit**

```bash
git add clipboard_hotkey.py
git commit -m "$(cat <<'EOF'
feat: wire update_check into the running app (queue + timer + worker)

Adds the runtime plumbing for v2.5.0's startup update check:

- module-level update_check_queue plus a session-guard flag
- _start_update_check spawns a daemon thread calling
  update_check.check_for_update(); puts result on the queue if non-None
- _poll_update_check (1 Hz QTimer on Qt main thread) drains the queue
  and calls show_update_prompt (stub here; real UI in next commit)
- main() schedules the worker via QTimer.singleShot(2000, ...) so the
  tray icon is alive before any prompt
- on_quit stops _update_timer (matches F27 cleanup pattern)

show_update_prompt is a print-only stub at this commit so the queue
plumbing can be tested in isolation. The actual QMessageBox UI lands
in the next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add the QMessageBox UI and Upgrade-button action

**Files:**
- Modify: `clipboard_hotkey.py` — replace the `show_update_prompt` stub with the real implementation

- [ ] **Step 4.1: Replace the stub with the real `show_update_prompt`**

Find the stub from Task 3:

```bash
grep -n "show_update_prompt\|stub.*real implementation" clipboard_hotkey.py
```

Replace the entire stub function body with this real implementation:

```python
def show_update_prompt(info):
    """Show a modal QMessageBox with Upgrade / Skip buttons.

    Called by _poll_update_check on the Qt main thread when
    update_check.check_for_update() reports a newer release available.

    Upgrade: opens info['portal_url'] in the user's default browser via
    QDesktopServices, then calls on_quit so the running app exits and
    the installer can replace the exe.

    Skip: closes the dialog. No persistent state — relaunching prompts
    again until the user upgrades.
    """
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtCore import QUrl
    from PyQt5.QtGui import QDesktopServices

    msg = QMessageBox()
    msg.setWindowTitle("MAC Converter — Update Available")
    try:
        msg.setWindowIcon(QIcon(get_icon_path()))
    except Exception:
        pass
    msg.setIcon(QMessageBox.Information)
    msg.setText(
        f"A newer version of MAC Converter is available.\n\n"
        f"Current: v{info['current']}\n"
        f"Latest: v{info['latest']}"
    )
    if info.get("notes_excerpt"):
        msg.setDetailedText(info["notes_excerpt"])

    upgrade_btn = msg.addButton("Upgrade", QMessageBox.AcceptRole)
    skip_btn = msg.addButton("Skip", QMessageBox.RejectRole)
    msg.setDefaultButton(upgrade_btn)
    msg.exec_()

    if msg.clickedButton() is upgrade_btn:
        # Open the download portal in the user's default browser. The
        # browser uses Windows' cert store and handles corporate TLS
        # interception naturally — same reason the in-app OUI download
        # needs truststore but the browser doesn't.
        QDesktopServices.openUrl(QUrl(info["portal_url"]))
        # Exit the app so the installer can replace the running exe.
        on_quit(tray_icon, None)
```

- [ ] **Step 4.2: Sanity-check the imports it depends on**

```bash
grep -n "^from PyQt5.QtWidgets import\|^from PyQt5.QtGui import\|^from PyQt5.QtCore import" clipboard_hotkey.py | head -5
```

`QMessageBox`, `QUrl`, and `QDesktopServices` are imported lazily inside the function so they don't add to module-level import cost on every launch. `QIcon` is already at module top from existing code — verify with:

```bash
grep -n "QIcon" clipboard_hotkey.py | head -3
```

Expected: at least one `from PyQt5.QtGui import QIcon, ...` near the top.

`get_icon_path` and `on_quit` and `tray_icon` are all module-level names already used elsewhere — no new imports needed.

- [ ] **Step 4.3: Quick smoke check — module imports cleanly**

```bash
python -c "import clipboard_hotkey; print('import ok')"
python -m pytest -q
```

Expected: 34 passed (no test changes; UI isn't covered by pytest).

- [ ] **Step 4.4: Manual UI verification (advisory — runs after the commit lands)**

Launch the app from source:

```bash
python clipboard_hotkey.py
```

The app should start normally. To trigger the prompt without waiting for a real new release, temporarily monkeypatch in a Python REPL or test environment:

```bash
python -c "
import update_check
update_check.APP_VERSION = '0.0.1'  # force a 'newer release exists'
result = update_check.check_for_update()
print(result)
"
```

Expected: prints a dict with `current='0.0.1'`, `latest='2.5.0'` (or whatever the actual latest is), `portal_url=...`, `notes_excerpt=...`.

Then to actually see the QMessageBox: launch the app, wait ~3 seconds, prompt should appear. Click Upgrade — browser opens the portal, app exits cleanly. Relaunch and click Skip — dialog dismisses, app continues running, no further prompts in that session. Quit via tray and relaunch — prompt appears again.

If the prompt never appears: check stderr for "[update_check]" messages, and confirm `update_check_queue.get_nowait()` is being called by inspecting whether `_update_timer.timeout` is connected to `_poll_update_check`.

- [ ] **Step 4.5: Commit**

```bash
git add clipboard_hotkey.py
git commit -m "$(cat <<'EOF'
feat: add QMessageBox UI for the startup update prompt

Replaces the print-only stub from the previous commit with the real
modal QMessageBox. Two buttons:

- Upgrade (default, AcceptRole): opens the GitHub Pages portal in the
  user's default browser via QDesktopServices.openUrl, then calls
  on_quit so the running app exits and the installer can replace the
  exe in place.
- Skip (RejectRole): dismisses the dialog. No persistent state — the
  next launch re-checks and re-prompts.

The release notes body is surfaced via setDetailedText so the user
can expand for context but isn't visually overwhelmed by default.

Lazy-imports QMessageBox / QUrl / QDesktopServices inside the function
to keep module-level import cost low.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Version bump to 2.5.0 + CHANGELOG entry + doc updates

**Files:**
- Modify: `installer.iss` (line 5)
- Modify: `README.md` (header, direct download links, version history)
- Modify: `TODO.md` (header)
- Modify: `CHANGELOG.md` (prepend `[2.5.0]` section)
- Modify: `ARCHITECTURE.md` (threading model update, new design decision entry, "where to look" entry)
- Modify: `TROUBLESHOOTING.md` (new "I never see the update prompt" entry)
- Modify: `DEVELOPMENT_LOG.md` (session entry)

`update_check.py:APP_VERSION` is **already** `"2.5.0"` from Task 1 — that's now the single source of truth for the Python code. The remaining bumps are in non-Python files that reference the version string.

- [ ] **Step 5.1: Bump `installer.iss`**

```bash
grep -n "MyAppVersion" installer.iss
```

Should report line 5 with `#define MyAppVersion "2.4.3"`. Replace:

Old:
```
#define MyAppVersion "2.4.3"
```

New:
```
#define MyAppVersion "2.5.0"
```

- [ ] **Step 5.2: Bump `README.md` header and direct download links**

```bash
grep -n "Current Version\|MAC-Converter-Setup-v2.4.3.exe\|releases/download/v2.4.3" README.md
```

Replace:

| Old | New |
|-----|-----|
| `**Current Version:** 2.4.3` | `**Current Version:** 2.5.0` |
| `MAC-Converter-Setup-v2.4.3.exe` | `MAC-Converter-Setup-v2.5.0.exe` (both link text and URL — use Edit `replace_all=true` for the README) |
| `releases/download/v2.4.3/` | `releases/download/v2.5.0/` |
| `releases/download/v2.4.3/MAC-Converter.exe` | `releases/download/v2.5.0/MAC-Converter.exe` |

- [ ] **Step 5.3: Bump `README.md` version history**

Find the section starting with `## Version History` and immediately under it, add a new bullet point as the new top entry:

```markdown
- **2.5.0** (2026-05-22): Startup update check — app fetches the latest release from the GitHub API on launch; if a newer version exists, a modal prompt offers Upgrade (opens the portal in browser, exits app) or Skip. `APP_VERSION` consolidated into a single source of truth in `update_check.py`.
```

(Insert above the existing `- **2.4.3** ...` line.)

- [ ] **Step 5.4: Bump `TODO.md` header**

```bash
grep -n "Current Version" TODO.md
```

Replace:

Old:
```
**Current Version:** 2.4.3 (Production Ready)
**Last Updated:** 2026-05-15
```

New:
```
**Current Version:** 2.5.0 (Production Ready)
**Last Updated:** 2026-05-22
```

Also: in the "Future Enhancements (v2.5.0+)" section header, bump to "Future Enhancements (v2.6.0+)" to reflect that 2.5.0 is now released.

```bash
grep -n "Future Enhancements" TODO.md
```

Replace:

Old:
```
## Future Enhancements (v2.5.0+)
```

New:
```
## Future Enhancements (v2.6.0+)
```

Also bump the "Current Release" header:

```bash
grep -n "## Current Release" TODO.md
```

Replace:

Old:
```
## Current Release (v2.4.3)
```

(If the TODO still references v2.4.2, use `replace_all=false` on the actual current string.) New:

```
## Current Release (v2.5.0)
```

Also bump the installer file path in the Build Artifacts section:

```bash
grep -n "MAC-Converter-Setup-v2" TODO.md
```

Replace each `MAC-Converter-Setup-v2.4.X.exe` reference with `MAC-Converter-Setup-v2.5.0.exe`.

- [ ] **Step 5.5: Add a new Milestone 15 to TODO.md**

Find the existing "Milestone 14" block (the documentation-pass milestone) and immediately after it (before the `---` separator that precedes the Current Release section), add:

```markdown
### ✅ Milestone 15: Startup Update Check (v2.5.0)
- [x] New `update_check.py` module — pure logic, no Qt dependency, mirrors the `oui_lookup.py` pattern
- [x] `APP_VERSION` consolidated as single source of truth (replaces three previously-hardcoded version strings)
- [x] GitHub Releases API integration with TLS handled by the truststore injection in `oui_lookup.py`
- [x] Modal QMessageBox prompt with Upgrade / Skip buttons; Upgrade opens the portal in the default browser and exits the app
- [x] Defensive error handling — all failure paths return `None` silently, no popups for offline / rate-limited / network-broken cases
- [x] 10 new pytest regression tests (`_parse_version` + `check_for_update` happy/error paths)
- [x] Module-level `_update_timer` cleaned up in `on_quit` (matches F27 pattern)
- [x] Documentation updated across README, ARCHITECTURE, TROUBLESHOOTING, CHANGELOG, TODO, DEVELOPMENT_LOG
```

- [ ] **Step 5.6: Prepend `[2.5.0]` section to `CHANGELOG.md`**

```bash
grep -n "^## " CHANGELOG.md | head -3
```

Should report `## [2.4.3] - 2026-05-15` as the current first version section. Insert a new section above it (after the `# Changelog` header but before `## [2.4.3]`):

```markdown
## [2.5.0] - 2026-05-22
### Added
- **Startup update check.** On launch, the app fetches the latest release tag from the GitHub Releases API. If a newer version exists, a modal prompt appears with Upgrade and Skip buttons. Upgrade opens the GitHub Pages download portal in the user's default browser and exits the app so the installer can replace the running exe. Skip dismisses for the current session; the next launch re-checks.
- **New module `update_check.py`** — pure logic, no Qt dependency, mirrors the `oui_lookup.py` pattern. Single source of truth for `APP_VERSION` (consolidated from three previously-hardcoded sites). All failure paths return `None` silently — offline, rate-limited, malformed-tag cases never surface a user-visible error at startup.
- **10 new pytest regression tests** for `_parse_version` (v-prefix, no-prefix, prerelease suffix, two-segment, garbage) and `check_for_update` (no-update, newer-release, URLError, HTTPError, malformed-tag).

### Changed
- `clipboard_hotkey.py` and `oui_lookup.py` now read the version string from `update_check.APP_VERSION` instead of hardcoded literals — future version bumps touch one Python file instead of three.
- `on_quit` explicitly stops the new `_update_timer` (matches the F27 cleanup pattern from the v2.4.0 audit).
```

- [ ] **Step 5.7: Update `ARCHITECTURE.md`**

Add a new entry to the threading-model table in §3 (insert after the existing OUI worker rows):

```bash
grep -n "OUI manual update worker" ARCHITECTURE.md
```

After that table row, add:

```markdown
| **Update-check worker** | spawned by `_start_update_check` 2s after `main()`, daemon | One-shot per launch | Calls `update_check.check_for_update()`. On result, `update_check_queue.put(result)`. Never touches Qt. |
```

Add a new design-decision subsection to §6 — place it after § 6.7 (autostart) and before § 6.8 (ApplicationShortcut). Numbered §6.8 (renumber the old §6.8 to §6.9):

```markdown
### 6.8 Update check opens the portal instead of auto-downloading

The startup update prompt's "Upgrade" button opens the GitHub Pages download portal in the user's default browser, then calls `on_quit` to exit the running app. It does **not** download the installer itself.

Why: the user's browser uses Windows' certificate store natively and handles corporate TLS-intercepting proxies (Zscaler, FortiGate, etc.) fine — the same reason we recommended manual browser downloads as the OUI fallback before v2.4.3's truststore work. Auto-downloading the installer from inside the app would re-introduce a class of failures (partial downloads, AV interception of the temp .exe, rate limits, retry logic) that the existing Inno Setup installer-over-running-exe pattern already handles cleanly when the user starts from a freshly-downloaded `.exe`.

The trade-off is one extra click for the user (download → run installer) in exchange for substantially less code surface inside our app and zero compatibility complications with whatever endpoint security is in place. If user feedback shows that the extra click is friction, the auto-download path can be added in a future version on top of the existing infrastructure (a `urllib` GET to the asset URL, a `subprocess.Popen` of the downloaded exe, exit) — but ship the simple version first.
```

Add a new row to the §12 "Where to look when something breaks" table:

```markdown
| Update prompt doesn't appear | Either there's no newer release on GitHub, or the network request failed silently. Check stderr for `[update_check]` messages. Verify `update_check_queue` is being drained by `_update_timer` (is the timer running and connected?). |
```

- [ ] **Step 5.8: Update `TROUBLESHOOTING.md`**

Add a new section near the end (before the "My issue isn't here" section):

```markdown
## I never see the update prompt at startup

**Most common cause:** you're already on the latest version. The prompt only appears when GitHub reports a newer release. Right-click tray → About → check your version against [the Releases page](https://github.com/aleled/mac-converter-2/releases).

**If you know there's a newer version and the prompt still doesn't appear:**

1. The GitHub API call may have failed silently. Run the app from a terminal (`python clipboard_hotkey.py` from source, or attach a console to the exe) and watch stderr for `[update_check]` messages.
2. GitHub API rate-limits unauthenticated requests to 60/hour per IP. If you're behind a NAT with many other developers, you may hit the limit. Wait an hour and relaunch.
3. Your corporate firewall may be blocking `api.github.com` even though `github.com` itself is allowed. Test with `curl https://api.github.com/repos/aleled/mac-converter-2/releases/latest` from a terminal.
4. If you clicked Skip in this session, the prompt is suppressed until you quit and relaunch the app. There's no persistent skip — restarting the app re-checks.
```

- [ ] **Step 5.9: Update `DEVELOPMENT_LOG.md`**

Append a new session entry at the bottom of the file:

```markdown
---

## 2026-05-22 (Windows/PowerShell Session) — v2.5.0: startup update check

User requested a startup update-check feature: on launch, check GitHub for a newer release, and prompt the user with Upgrade / Skip buttons. Ship as v2.5.0.

### Design choices (resolved in brainstorming)

- **Upgrade flow:** open the GitHub Pages portal in the user's default browser, then exit the app. The browser handles corporate TLS naturally; the existing installer handles install-over-running-exe.
- **Check frequency:** every startup. In-memory session cache only — no persistent timestamp.
- **Dismissal:** two buttons, Upgrade / Skip. No persistent skip-this-version or disable-checks settings (matches the user's preference for minimal UI).

### Implementation

Five tasks per the implementation plan:

1. New `update_check.py` module — `APP_VERSION = "2.5.0"`, `check_for_update()` returning dict-or-None, `_parse_version()` for tuple comparison. 10 pytest regression tests.
2. Consolidate `clipboard_hotkey.py` and `oui_lookup.py` version strings to read from `APP_VERSION`. Three previously-hardcoded sites now flow through one constant.
3. Wire into Qt: queue + daemon worker + 1Hz QTimer poll + session-guard flag + main() hook + on_quit cleanup.
4. Replace the stub `show_update_prompt` with a real modal QMessageBox. Upgrade opens the portal via `QDesktopServices.openUrl` and calls `on_quit`.
5. Version bump to 2.5.0 + CHANGELOG + doc updates (README, ARCHITECTURE, TROUBLESHOOTING, TODO).

### Lessons noted

- The single-source-of-truth `APP_VERSION` should have existed from day one. Three hardcoded version strings was a maintenance footgun every release. The consolidation now means future bumps touch one Python file.
- truststore being imported by `oui_lookup.py` for OUI downloads also benefits `update_check.py` for free — both end up using Windows' certificate store. Good module-load-order design pays off in unexpected places.
- The "open portal in browser instead of auto-downloading" trade-off is explicit in ARCHITECTURE.md § 6.8 so future contributors don't second-guess it.
```

- [ ] **Step 5.10: Run the full test suite and verify version consistency**

```bash
python -m pytest -q
```

Expected: 34 passed.

```bash
grep -n "2\.5\.0" update_check.py installer.iss README.md TODO.md CHANGELOG.md ARCHITECTURE.md clipboard_hotkey.py oui_lookup.py | head -25
```

Expected output should show v2.5.0 references in the right places. No stray `2.4.3` should remain outside `CHANGELOG.md`'s historical entries:

```bash
grep -rn "2\.4\.3" -- ":!CHANGELOG.md" ":!docs/superpowers"
```

(or equivalent search). Any remaining `2.4.3` references in `README.md`'s Version History, `TODO.md`'s Milestone history, etc. should be the historical entries — that's correct.

- [ ] **Step 5.11: Commit**

```bash
git add installer.iss README.md TODO.md CHANGELOG.md ARCHITECTURE.md TROUBLESHOOTING.md DEVELOPMENT_LOG.md
git commit -m "$(cat <<'EOF'
release: bump version to 2.5.0 (startup update check)

Mechanical version bump + documentation updates for v2.5.0:

- installer.iss MyAppVersion -> 2.5.0
- README: header, direct download links, new version history entry
- TODO: header, Milestone 15, Current Release, Future Enhancements
  header bumped from v2.5.0+ to v2.6.0+
- CHANGELOG: new [2.5.0] section with Added/Changed
- ARCHITECTURE: threading model row for the update-check worker,
  new § 6.8 design decision (portal vs auto-download), new entry in
  the "where to look when something breaks" table
- TROUBLESHOOTING: new "I never see the update prompt" section
- DEVELOPMENT_LOG: full v2.5.0 session entry

APP_VERSION ("2.5.0") was set in update_check.py during Task 1 of
this feature and is now the single source of truth — no separate
Python source bump needed.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Build artifacts and publish v2.5.0 release

**Files:** none (build + release process)

- [ ] **Step 6.1: Final pytest run**

```bash
python -m pytest -v
```

Expected: 34 passed. Stop and investigate any failure — do not ship a release with failing tests.

- [ ] **Step 6.2: Build the standalone exe**

```bash
./venv/Scripts/python.exe -m PyInstaller mac-converter.spec --noconfirm
```

Expected: completes in ~1-2 minutes, outputs `dist/MAC-Converter.exe` (~51 MB).

- [ ] **Step 6.3: Build the installer**

```bash
"C:/Program Files (x86)/Inno Setup 6/iscc.exe" installer.iss
```

Expected: completes in ~10 seconds, outputs `installer-output/MAC-Converter-Setup-v2.5.0.exe` (~54 MB).

- [ ] **Step 6.4: Push the branch**

```bash
git push 2>&1 | tail -3
```

Expected: pushed cleanly to `origin/claude/eloquent-payne-7d7c9c`.

- [ ] **Step 6.5: Create the GitHub Release**

```bash
gh release create v2.5.0 \
  installer-output/MAC-Converter-Setup-v2.5.0.exe \
  dist/MAC-Converter.exe \
  --target claude/eloquent-payne-7d7c9c \
  --title "v2.5.0 — Startup update check" \
  --notes "$(cat <<'EOF'
New feature: the app now checks for updates on launch and prompts you when a newer version is available.

## What's new

When you start the app, it makes a quiet call to the GitHub Releases API (~2 seconds after launch, in a background thread — doesn't block the tray icon). If a newer release exists, a modal dialog appears with the current version, the latest version, and a release-notes excerpt. Two buttons:

- **Upgrade** — opens the [download portal](https://aleled.github.io/mac-converter-2/) in your default browser and exits the app. Your browser handles any corporate TLS or proxy complications naturally. Then run the downloaded installer; it replaces the previous install in place.
- **Skip** — dismisses the prompt for this session. The next time you launch the app, it'll check again.

If you're offline, behind a captive portal, hitting GitHub's rate limit, or already on the latest version, the check fails silently — no popup, no error, business as usual.

## Architectural notes

- New module `update_check.py` mirrors the existing `oui_lookup.py` pattern: pure logic, no Qt dependency, defensive error handling.
- `APP_VERSION` is now a single source of truth — three previously-hardcoded version strings across `clipboard_hotkey.py` and `oui_lookup.py` now read from one constant. Future version bumps touch one Python source file instead of three.
- truststore's Windows-cert-store injection from `oui_lookup.py` also covers the new GitHub API call — works fine on corporate networks that re-sign HTTPS.

## Downloads

- **MAC-Converter-Setup-v2.5.0.exe** — Windows installer (~54 MB). Run over the existing install; settings are preserved.
- **MAC-Converter.exe** — Standalone executable (~51 MB).

See [CHANGELOG `[2.5.0]`](https://github.com/aleled/mac-converter-2/blob/claude/eloquent-payne-7d7c9c/CHANGELOG.md) for the per-finding fix list.
EOF
)"
```

Expected: prints the release URL `https://github.com/aleled/mac-converter-2/releases/tag/v2.5.0`. Portal at https://aleled.github.io/mac-converter-2/ will auto-detect the new release within ~30 seconds.

- [ ] **Step 6.6: Report to user**

Summary to surface:

```
v2.5.0 published.
- Release: https://github.com/aleled/mac-converter-2/releases/tag/v2.5.0
- Portal will auto-pick up v2.5.0 within ~30s
- Tests: 34/34 green
- The update-prompt feature is now live — users on v2.4.3 or earlier will be prompted on next launch.

To test:
1. Install v2.5.0 over your current v2.4.3.
2. Right-click tray → About → confirm "Version 2.5.0".
3. To simulate a future release, the app's check_for_update() will return None if nothing newer than 2.5.0 exists on GitHub. To test the prompt UI, temporarily edit %APPDATA%\... (or just trust the unit tests).
```
