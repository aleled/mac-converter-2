# Phase 2 Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all 37 findings from `docs/AUDIT-2026-05-14.md`, ship v2.4.0 of the MAC Address Converter, and produce a `dev`-mergeable branch.

**Architecture:** Refactor `clipboard_hotkey.py` settings I/O and OUI worker lifecycle around two patterns — atomic `os.replace` writes guarded by `_settings_lock`, and cooperative-shutdown `threading.Event` plumbing for the OUI worker. Tighten `mac_formats.py` regex; harden `oui_lookup.py` download against content hijack and crashes. Introduce a `tests/` regression suite covering pure-logic fixes. Replace the global pynput listener with a Qt-scoped `QShortcut`. Add Startup-folder shortcut autostart (replacing the non-functional checkbox) and a single-instance mutex.

**Tech Stack:** Python 3.8+, PyQt5, pynput, pyperclip, pystray, pywin32 (already in `requirements.txt`), Pillow (for `.ico` generation), pytest (new dev dependency), PyInstaller, Inno Setup. Windows-only.

---

## Conventions used in every task

- **Working directory:** `C:\working\mac-converter-2\.claude\worktrees\eloquent-payne-7d7c9c`. All commands and paths assume this is the current working directory.
- **F-ID closure tracking:** every commit's message must list the F-IDs it closes in the form `Closes F<N>, F<M>, ...`. The final CHANGELOG entry (Task 15) references those IDs too.
- **Test commands:** all `pytest` invocations assume the worktree's venv is active (or that pytest is on PATH). If `pytest` is missing, run `pip install -r requirements-dev.txt` from the worktree root before retrying.
- **Single source-of-truth for the F-IDs and their text:** `docs/AUDIT-2026-05-14.md`. When in doubt, re-read the finding text there.
- **Commit message style:** matches existing repo style — single short imperative line, blank line, body explaining *why*. Include `Closes F<N>, ...` on its own line. End with the `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.
- **Manual UI verification:** for commits 6–11 the in-task "Manual verification" steps describe what to test, but **subagents do not run them** — subagents have no reliable way to drive a Windows GUI. After committing, the subagent reports DONE; the controller/user runs the manual checks at Task 16 (Final sanity pass) and re-opens the task as DONE_WITH_CONCERNS if anything misbehaves. Each manual-verification step is the engineer's checklist for what to look at when they eventually launch the app.
- **Atomic JSON write helper:** introduced in Task 2 and used by all subsequent settings/OUI changes. Do not duplicate it.

## Task 0: Dev environment readiness check

**Files:** none — this is a pre-flight.

- [ ] **Step 0.1: Verify Python is available**

Run from the worktree root:

```bash
python --version
```

Expected: `Python 3.8+` or higher. If `python` fails, try `py -3` (Windows launcher).

- [ ] **Step 0.2: Verify a venv exists or create one**

```bash
ls venv/Scripts/Activate.ps1 2>$null || python -m venv venv
```

If the venv was just created, activate it:

PowerShell: `. .\venv\Scripts\Activate.ps1`
Bash: `source venv/Scripts/activate`

- [ ] **Step 0.3: Install runtime dependencies**

```bash
pip install -r requirements.txt
```

Expected: PyQt5, pynput, pyperclip, pystray, Pillow, pywin32, PyInstaller installed.

(Dev dependencies are installed in Task 1.)

---

## Task 1: Test infrastructure (closes no F-IDs; foundation for later tasks)

**Files:**
- Create: `requirements-dev.txt`
- Create: `pytest.ini`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1.1: Create `requirements-dev.txt`**

Write the following exact content to `requirements-dev.txt`:

```
# Test dependencies (not bundled into the production executable)
pytest>=8.0
```

- [ ] **Step 1.2: Install dev dependencies**

```bash
pip install -r requirements-dev.txt
```

Expected: pytest installed.

- [ ] **Step 1.3: Create `pytest.ini`**

Write the following exact content to `pytest.ini`:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -ra --tb=short
```

- [ ] **Step 1.4: Create `tests/__init__.py`**

Write an empty file at `tests/__init__.py` (zero bytes).

- [ ] **Step 1.5: Create `tests/conftest.py`**

Write the following exact content to `tests/conftest.py`:

```python
"""Shared pytest fixtures for the MAC Converter regression suite."""

import os
import sys

# Ensure the worktree root is on sys.path so tests can import mac_formats etc.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

- [ ] **Step 1.6: Verify pytest runs with zero tests collected**

```bash
python -m pytest
```

Expected output (zero tests is GREEN, not a failure):

```
============================= test session starts =============================
...
collected 0 items
============================= 0 tests collected ===============================
```

The exit code is 5 ("no tests collected"). Pytest treats this as non-zero, but the structural setup is correct. Proceed.

- [ ] **Step 1.7: Update `.gitignore` to ignore pytest cache**

The existing `.gitignore` already includes `.pytest_cache/` at line 41. Verify with:

```bash
grep -n "pytest_cache" .gitignore
```

Expected: line 41 reports `.pytest_cache/`. If missing, append.

- [ ] **Step 1.8: Commit**

```bash
git add requirements-dev.txt pytest.ini tests/
git commit -m "$(cat <<'EOF'
test: add pytest infrastructure for Phase 2 regression suite

Sets up tests/ directory, pytest.ini, conftest.py (to put the worktree
root on sys.path), and requirements-dev.txt. No tests yet — those land
in later commits alongside their corresponding fixes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Atomic settings write + module-level lock (closes F7, F16, F23, F28)

**Files:**
- Modify: `clipboard_hotkey.py` — replace `save_settings` (line 1581) and add module-level helpers near the top
- Create: `tests/test_settings_atomic.py`

- [ ] **Step 2.1: Add the failing test for atomic write**

Write `tests/test_settings_atomic.py`:

```python
"""Regression tests for atomic settings write (F7, F23)."""

import json
import os
import sys
import tempfile
from unittest.mock import patch

import pytest

# Defer import until after sys.path is set by conftest
import clipboard_hotkey


def test_save_settings_writes_atomically(tmp_path, monkeypatch):
    """save_settings must write via temp file + os.replace; partial writes never overwrite the live file."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"hotkey": "original"}))

    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_FILENAME", "settings.json")

    # Patch os.replace to raise — simulates crash between temp-write and replace.
    real_replace = os.replace
    calls = {"count": 0}

    def failing_replace(src, dst):
        calls["count"] += 1
        raise OSError("simulated crash mid-replace")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError):
        clipboard_hotkey.save_settings({"hotkey": "new"})

    # Original file MUST still be intact
    assert json.loads(settings_file.read_text()) == {"hotkey": "original"}
    assert calls["count"] == 1
```

- [ ] **Step 2.2: Run the test to verify it FAILS**

```bash
python -m pytest tests/test_settings_atomic.py -v
```

Expected: FAIL — current `save_settings` doesn't use `os.replace`, so the test either passes spuriously OR fails for a different reason (the patched replace never gets called because the original implementation writes directly). Confirm the failure mode is "patched replace not called" or "live file got overwritten with new content".

- [ ] **Step 2.3: Implement atomic write + lock**

Find the current `save_settings` definition in `clipboard_hotkey.py` (around line 1581). Replace it with the following implementation. ALSO add the helpers near the top of the file (after the `import json` line, around line 36):

Near the top of `clipboard_hotkey.py`, after the existing imports, add:

```python
# --- Atomic settings I/O (Phase 2 fix for F7, F16, F23, F28) ---
import sys as _sys  # already imported, but ensure namespace

_settings_lock = threading.Lock()


def _atomic_write_json(path, data):
    """Write `data` to `path` atomically via temp file + os.replace.

    Caller is responsible for serialization (e.g. holding _settings_lock).
    Raises OSError on failure; the live file is never partially written.
    """
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)
```

Replace the existing `save_settings` body with:

```python
def save_settings(settings):
    """Save settings atomically to disk. Thread-safe via _settings_lock."""
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    path = os.path.join(SETTINGS_DIR, SETTINGS_FILENAME)
    with _settings_lock:
        _atomic_write_json(path, settings)
```

NOTE: this is a behavior change — `save_settings` now RAISES `OSError` on failure rather than swallowing it. The previous behavior silently lost writes; the new behavior surfaces failures so the engineer can decide call-site handling. For now, all existing callers can let the exception propagate (it's rare and indicates a real disk problem).

- [ ] **Step 2.4: Run the test to verify it PASSES**

```bash
python -m pytest tests/test_settings_atomic.py -v
```

Expected: PASS.

- [ ] **Step 2.5: Also run a quick smoke test that the live app still saves**

```bash
python -c "
import clipboard_hotkey
import tempfile, os, json
with tempfile.TemporaryDirectory() as td:
    clipboard_hotkey.SETTINGS_DIR = td
    clipboard_hotkey.save_settings({'hotkey': 'alt+shift+m', 'last_format_index': 0})
    with open(os.path.join(td, clipboard_hotkey.SETTINGS_FILENAME)) as f:
        print(json.load(f))
"
```

Expected: prints `{'hotkey': 'alt+shift+m', 'last_format_index': 0}`.

- [ ] **Step 2.6: Commit**

```bash
git add clipboard_hotkey.py tests/test_settings_atomic.py
git commit -m "$(cat <<'EOF'
fix: atomic settings write + module-level lock

Introduces _settings_lock (threading.Lock) and _atomic_write_json helper.
save_settings now writes settings.json via temp file + os.replace under
the lock, eliminating the corruption window when listener / Qt main /
OUI auto-update worker write concurrently.

Behavior change: save_settings now raises OSError on disk failure
instead of silently swallowing — callers can let it propagate.

Closes F7, F16, F23, F28.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Settings load validation + corrupt-file recovery (closes F8, F15, F24)

**Files:**
- Modify: `clipboard_hotkey.py` — replace `load_settings` (line 1565) and add `_validate_settings`
- Modify: `tests/test_settings_atomic.py` — extend with load-validation tests, or
- Create: `tests/test_settings_validate.py`

- [ ] **Step 3.1: Add the failing tests for validation + corrupt recovery**

Create `tests/test_settings_validate.py`:

```python
"""Regression tests for settings load validation (F8, F15, F24)."""

import json
import os
import time

import pytest

import clipboard_hotkey


def test_validate_settings_coerces_bad_types():
    """A string in last_format_index must fall back to the default int."""
    raw = {
        "hotkey": "alt+shift+m",
        "last_format_index": "garbage",  # F8: must coerce/fallback
        "notification_duration": -1,  # F15: out-of-range, must clamp
        "autostart": "no",  # F8: wrong type, must fallback
    }
    out = clipboard_hotkey._validate_settings(raw)
    assert isinstance(out["last_format_index"], int)
    assert 0 <= out["last_format_index"] < 10
    assert 1 <= out["notification_duration"] <= 10
    assert isinstance(out["autostart"], bool)


def test_validate_settings_keeps_good_values():
    raw = {
        "hotkey": "ctrl+shift+c",
        "last_format_index": 4,
        "notification_duration": 5,
        "autostart": True,
    }
    out = clipboard_hotkey._validate_settings(raw)
    assert out["hotkey"] == "ctrl+shift+c"
    assert out["last_format_index"] == 4
    assert out["notification_duration"] == 5
    assert out["autostart"] is True


def test_load_settings_renames_corrupt_file(tmp_path, monkeypatch):
    """F24: a corrupt settings.json is renamed to settings.json.corrupt-<ts>, not silently overwritten."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{not valid json")

    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_FILENAME", "settings.json")

    result = clipboard_hotkey.load_settings()

    # Defaults loaded
    assert result["hotkey"] == clipboard_hotkey.DEFAULT_SETTINGS["hotkey"]
    # Corrupt file moved aside
    assert not settings_file.exists()
    corrupt_files = list(tmp_path.glob("settings.json.corrupt-*"))
    assert len(corrupt_files) == 1
    assert "not valid json" in corrupt_files[0].read_text()


def test_load_settings_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_FILENAME", "settings.json")
    result = clipboard_hotkey.load_settings()
    assert result == clipboard_hotkey.DEFAULT_SETTINGS
```

- [ ] **Step 3.2: Run the tests to verify they FAIL**

```bash
python -m pytest tests/test_settings_validate.py -v
```

Expected: 4 failures — `_validate_settings` doesn't exist yet, and `load_settings` doesn't rename corrupt files.

- [ ] **Step 3.3: Implement validation + corrupt recovery**

In `clipboard_hotkey.py`, find `DEFAULT_SETTINGS` (around line 1548). Make sure it includes every known key with a reasonable default. Then ADD `_validate_settings` immediately after `DEFAULT_SETTINGS`:

```python
def _validate_settings(d):
    """Coerce/clamp a raw settings dict, falling back to DEFAULT_SETTINGS per key.

    Returns a fully populated dict where every value passes type+range checks.
    Used by load_settings to reject corrupted or hand-edited bad values, and
    defensively before save to prevent garbage from being persisted.
    """
    out = dict(DEFAULT_SETTINGS)
    if not isinstance(d, dict):
        return out

    # hotkey: non-empty string
    if isinstance(d.get("hotkey"), str) and d["hotkey"].strip():
        out["hotkey"] = d["hotkey"].strip()

    # notification_duration: int in [1, 10]
    nd = d.get("notification_duration")
    if isinstance(nd, int) and not isinstance(nd, bool) and 1 <= nd <= 10:
        out["notification_duration"] = nd

    # autostart: strict bool
    if isinstance(d.get("autostart"), bool):
        out["autostart"] = d["autostart"]

    # last_format_index: int in [0, 9]
    lfi = d.get("last_format_index")
    if isinstance(lfi, int) and not isinstance(lfi, bool) and 0 <= lfi < 10:
        out["last_format_index"] = lfi

    # OUI options
    if isinstance(d.get("oui_enabled"), bool):
        out["oui_enabled"] = d["oui_enabled"]
    if isinstance(d.get("oui_auto_update"), bool):
        out["oui_auto_update"] = d["oui_auto_update"]
    oui_int = d.get("oui_update_interval_days")
    if isinstance(oui_int, int) and not isinstance(oui_int, bool) and 1 <= oui_int <= 365:
        out["oui_update_interval_days"] = oui_int
    oui_t = d.get("oui_vendor_timeout")
    if isinstance(oui_t, int) and not isinstance(oui_t, bool) and 1 <= oui_t <= 60:
        out["oui_vendor_timeout"] = oui_t

    # Last-downloaded timestamp passes through as-is if string
    if isinstance(d.get("oui_last_downloaded"), str):
        out["oui_last_downloaded"] = d["oui_last_downloaded"]

    return out
```

Replace the existing `load_settings` body with:

```python
def load_settings():
    """Load settings from disk. Returns a fully validated dict.

    On JSON parse failure, renames the corrupt file to
    settings.json.corrupt-<unix-ts> and returns DEFAULT_SETTINGS.
    """
    path = os.path.join(SETTINGS_DIR, SETTINGS_FILENAME)
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        ts = int(time.time())
        corrupt_path = f"{path}.corrupt-{ts}"
        try:
            os.replace(path, corrupt_path)
        except OSError:
            pass
        print(f"[WARN] settings.json corrupt, renamed to {corrupt_path}: {e}", file=sys.stderr)
        return dict(DEFAULT_SETTINGS)
    except OSError as e:
        print(f"[WARN] settings.json unreadable: {e}", file=sys.stderr)
        return dict(DEFAULT_SETTINGS)
    return _validate_settings(raw)
```

If `time` and `sys` are not yet imported at module top, add them. Verify with:

```bash
grep -n "^import time\|^import sys" clipboard_hotkey.py | head -5
```

- [ ] **Step 3.4: Run the tests to verify they PASS**

```bash
python -m pytest tests/test_settings_validate.py -v
```

Expected: 4 PASSES.

- [ ] **Step 3.5: Commit**

```bash
git add clipboard_hotkey.py tests/test_settings_validate.py
git commit -m "$(cat <<'EOF'
fix: settings load validation and corrupt-file recovery

Adds _validate_settings(d) to coerce/clamp each known key with type+range
checks, falling back to DEFAULT_SETTINGS per key. load_settings now
renames a corrupt settings.json to settings.json.corrupt-<unix-ts>
before falling back to defaults, so the user can recover hand edits.

Closes F8, F15, F24.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: OUI download hardening (closes F2, F3, F4, F5)

**Files:**
- Modify: `oui_lookup.py` (lines 50-156)
- Create: `tests/test_oui_lookup.py`

- [ ] **Step 4.1: Add failing tests**

Create `tests/test_oui_lookup.py`:

```python
"""Regression tests for OUI download hardening (F2, F3, F4, F5)."""

import io
from unittest.mock import MagicMock, patch

import pytest

from oui_lookup import OUIDatabase


@pytest.fixture
def db(tmp_path):
    return OUIDatabase(str(tmp_path))


def _mock_response(payload_bytes, content_type="text/csv"):
    response = MagicMock()
    response.read.side_effect = lambda chunk_size=None: payload_bytes if not response._read else b""
    response._read = False
    response.headers = {"Content-Length": str(len(payload_bytes)), "Content-Type": content_type}

    # Track read calls to drain after first
    def read(chunk_size=None):
        if response._read:
            return b""
        response._read = True
        return payload_bytes
    response.read = read

    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *a: None
    return response


def test_f3_rejects_html_response(db):
    """F3: a captive-portal HTML response must NOT overwrite oui.csv."""
    html = b"<!DOCTYPE html><html><body>Login required</body></html>"
    # Pad to exceed the 1000-byte floor so the size check passes
    payload = html + b" " * 2000
    with patch("oui_lookup.urllib.request.urlopen", return_value=_mock_response(payload, content_type="text/html")):
        success, err = db.download()
    assert success is False
    assert "html" in err.lower() or "content-type" in err.lower() or "captive" in err.lower()


def test_f5_rejects_zero_entry_csv(db, tmp_path):
    """F5: a CSV that parses to zero OUI entries is treated as a load failure."""
    # Create a header-only CSV (no data rows)
    (tmp_path / "oui.csv").write_text("Registry,Assignment,Organization Name,Organization Address\n")
    success, result = db.load()
    assert success is False
    assert "zero" in str(result).lower() or "empty" in str(result).lower()


def test_f2_atomic_replace_preserves_old_db_on_replace_failure(db, tmp_path, monkeypatch):
    """F2: if os.replace fails, the prior oui.csv is preserved."""
    # Pre-populate a "good" oui.csv
    good = (
        b"Registry,Assignment,Organization Name,Organization Address\n"
        b"MA-L,001122,Cisco Systems,\"170 W Tasman Dr\"\n"
    )
    (tmp_path / "oui.csv").write_bytes(good)

    new_payload = b"Registry,Assignment,Organization Name,Organization Address\n" + b"MA-L,AABBCC,New Vendor,addr\n" * 1000

    def failing_replace(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr("os.replace", failing_replace)
    with patch("oui_lookup.urllib.request.urlopen", return_value=_mock_response(new_payload)):
        success, err = db.download()
    assert success is False
    # Old DB intact
    assert (tmp_path / "oui.csv").read_bytes() == good
```

- [ ] **Step 4.2: Run the tests to verify they FAIL**

```bash
python -m pytest tests/test_oui_lookup.py -v
```

Expected: 3 failures (the current code doesn't sniff HTML, doesn't guard zero-entry, and uses temp+rename which is not atomic on Windows).

- [ ] **Step 4.3: Implement OUI hardening in `oui_lookup.py`**

Modify the `download` method (replacing roughly lines 50-116). The full replacement:

```python
    def download(self, progress_callback=None, cancel_event=None):
        """
        Download OUI CSV from IEEE. Blocking call — run in a background thread.

        Args:
            progress_callback: Optional callable accepting either a status
                string or a dict with 'bytes_downloaded'/'total_bytes' keys.
            cancel_event: Optional threading.Event. If set during download,
                the call returns (False, "cancelled") without touching the
                live oui.csv.

        Returns:
            (True, None) on success, (False, error_message) on failure.
        """
        try:
            os.makedirs(self.data_dir, exist_ok=True)

            if progress_callback:
                progress_callback("Connecting to IEEE...")

            req = urllib.request.Request(OUI_URL, headers={
                'User-Agent': 'MAC-Converter/2.4.0'
            })

            with urllib.request.urlopen(req, timeout=30) as response:
                # F3: reject if the server returned HTML / non-CSV
                content_type = response.headers.get('Content-Type', '').lower()
                if 'html' in content_type:
                    return (False, f"Server returned text/html (likely captive portal or error page), refusing to overwrite oui.csv")

                total_bytes = int(response.headers.get('Content-Length', 0))

                chunk_size = 16384
                data = bytearray()
                bytes_downloaded = 0
                first_chunk = True

                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        return (False, "cancelled")

                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    # F3: sniff the first chunk for HTML magic-bytes
                    if first_chunk:
                        leading = bytes(chunk[:200]).lstrip().lower()
                        if leading.startswith(b'<!doctype') or leading.startswith(b'<html') or leading.startswith(b'<?xml'):
                            return (False, "Response body looks like HTML/XML, not CSV — refusing to overwrite oui.csv")
                        first_chunk = False

                    data.extend(chunk)
                    bytes_downloaded += len(chunk)

                    if progress_callback and total_bytes > 0:
                        progress_callback({
                            'bytes_downloaded': bytes_downloaded,
                            'total_bytes': total_bytes
                        })

            if len(data) < 1000:
                return (False, "Downloaded file too small, may be corrupt")

            # F2: atomic replace. os.replace is atomic where the OS supports it
            # and works on Windows where os.rename would fail if dest exists.
            temp_path = self.oui_path + ".tmp"
            with open(temp_path, 'wb') as f:
                f.write(data)
            os.replace(temp_path, self.oui_path)

            if progress_callback:
                progress_callback("OUI database downloaded successfully")
            return (True, None)

        except urllib.error.URLError as e:
            msg = str(e.reason) if hasattr(e, 'reason') else str(e)
            return (False, f"Network error: {msg}")
        except OSError as e:
            # F12: don't leak full paths to the UI — caller is responsible for sanitization
            return (False, f"File error: {os.path.basename(self.oui_path)} could not be written")
        except Exception as e:
            return (False, f"Download failed: {type(e).__name__}")
```

Then modify the `load` method (around lines 118-156) to add the F5 zero-entry guard. Find the line `with self._lock:` near the bottom and modify the surrounding code:

```python
        try:
            if not os.path.exists(self.oui_path):
                return (False, "OUI database file not found")

            db = {}
            with open(self.oui_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) >= 3:
                        assignment = row[1].strip().upper()
                        org_name = row[2].strip()
                        if len(assignment) == 6 and org_name:
                            db[assignment] = org_name

            # F5: a header-only or empty CSV is a corruption signal, not a success.
            if len(db) == 0:
                return (False, "OUI database parsed to zero entries (empty or corrupt)")

            with self._lock:
                self._db = db
                self._loaded = True

            return (True, len(db))
```

- [ ] **Step 4.4: Run the tests to verify they PASS**

```bash
python -m pytest tests/test_oui_lookup.py -v
```

Expected: 3 PASSES.

- [ ] **Step 4.5: Commit**

```bash
git add oui_lookup.py tests/test_oui_lookup.py
git commit -m "$(cat <<'EOF'
fix: harden OUI download against atomic-replace, HTML hijack, and zero-entry parse

- F2: replace temp+rename with os.replace (atomic on Windows where supported,
  preserves prior oui.csv on failure).
- F3: sniff Content-Type and first-chunk magic bytes; reject HTML responses
  (captive portals, error pages) before they can overwrite the live file.
- F4: wrap urlopen in a `with` block so the socket closes on exception.
- F5: load() returns (False, ...) when the CSV parses to zero entries
  rather than silently marking the DB as loaded.

Also adds `cancel_event` parameter to download() in preparation for Task 11
(OUI worker cooperative shutdown). Updates UA to MAC-Converter/2.4.0.

Closes F2, F3, F4, F5.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Regex tightening — reject mixed `:`/`-` separators (closes F1)

**Files:**
- Modify: `mac_formats.py:27` (the `MAC_REGEX` regex literal)
- Create: `tests/test_mac_formats.py`

- [ ] **Step 5.1: Add failing test**

Create `tests/test_mac_formats.py`:

```python
"""Regression tests for mac_formats (F1)."""

import pytest

from mac_formats import detect_mac, convert_mac


def test_f1_rejects_mixed_separators():
    """F1: mixed colon and hyphen separators are not a real MAC notation."""
    assert detect_mac("00-1A:2B-3C:4D-5E") is None
    assert detect_mac("00:1A-2B:3C-4D:5E") is None
    assert detect_mac("AA-BB:CC-DD:EE-FF") is None


@pytest.mark.parametrize("text,expected", [
    ("00:1A:2B:3C:4D:5E", "001A2B3C4D5E"),
    ("00-1A-2B-3C-4D-5E", "001A2B3C4D5E"),
    ("AA:BB:CC:DD:EE:FF", "AABBCCDDEEFF"),
    ("aa-bb-cc-dd-ee-ff", "aabbccddeeff"),
    ("aabb.ccdd.eeff", "aabbccddeeff"),
    ("AABBCC-DDEEFF", "AABBCCDDEEFF"),
    ("aabbccddeeff", "aabbccddeeff"),
    ("AABBCCDDEEFF", "AABBCCDDEEFF"),
    ("  00:1A:2B:3C:4D:5E  ", "001A2B3C4D5E"),
])
def test_detect_mac_happy_path(text, expected):
    assert detect_mac(text) == expected


@pytest.mark.parametrize("text", [
    "AABBCCDDEEFF1",  # 13 chars
    "GG-HH-II-JJ-KK-LL",  # non-hex
    "00:1A:2B:3C:4D:5E:FF",  # 7 octets
    "",  # empty
    "not-a-mac",  # nonsense
])
def test_detect_mac_rejects(text):
    assert detect_mac(text) is None


def test_convert_mac_emits_ten_formats():
    formats = convert_mac("001A2B3C4D5E")
    assert len(formats) == 10
    # Spot-check key formats
    by_desc = dict(formats)
    assert by_desc["Colon-separated uppercase"] == "00:1A:2B:3C:4D:5E"
    assert by_desc["Hyphen-6char uppercase"] == "001A2B-3C4D5E"
    assert by_desc["Dot-separated lowercase"] == "001a.2b3c.4d5e"
```

- [ ] **Step 5.2: Run the tests to verify they FAIL**

```bash
python -m pytest tests/test_mac_formats.py -v
```

Expected: `test_f1_rejects_mixed_separators` fails on all 3 mixed inputs (current regex accepts them); happy-path tests should mostly pass; reject tests should pass.

- [ ] **Step 5.3: Implement the regex fix**

In `mac_formats.py`, replace line 27 (the `MAC_REGEX` definition) with:

```python
MAC_REGEX = re.compile(
    r"(?<![0-9A-Fa-f])("
    r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}"   # colon-separated
    r"|"
    r"(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}"   # hyphen-separated
    r"|"
    r"[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}"  # dot-separated
    r"|"
    r"[0-9A-Fa-f]{6}-[0-9A-Fa-f]{6}"          # Hyphen-6char (Cisco)
    r"|"
    r"[0-9A-Fa-f]{12}"                         # plain 12-hex
    r")(?![0-9A-Fa-f])"
)
```

The key change: the first alternative `(?:[0-9A-Fa-f]{2}[:-]){5}` is split into two distinct alternatives, each pinning a single separator.

- [ ] **Step 5.4: Run the tests to verify they PASS**

```bash
python -m pytest tests/test_mac_formats.py -v
```

Expected: ALL PASS (mixed-separator rejection + happy path + reject path + convert_mac shape).

- [ ] **Step 5.5: Commit**

```bash
git add mac_formats.py tests/test_mac_formats.py
git commit -m "$(cat <<'EOF'
fix: reject MAC addresses with mixed colon/hyphen separators

MAC_REGEX previously used the character class [:-] per octet, which
silently accepted '00-1A:2B-3C:4D-5E'. The first alternative is now
split into two branches that each pin one separator.

Adds tests/test_mac_formats.py covering F1 regression, parametrized
happy-path coverage of the 10 canonical formats, and rejection of
malformed input.

Closes F1.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Wrap clipboard calls (closes F6, F20, F21)

**Files:**
- Modify: `clipboard_hotkey.py` — wrap `pyperclip` calls at lines 199, 223, 1249, 1429

This task is UI behavior; no automated test. Manual verification at the end.

- [ ] **Step 6.1: Wrap `pyperclip.paste()` in `handle_hotkey` (line 199)**

Find the `handle_hotkey` function. The first few lines look like:

```python
def handle_hotkey(app):
    """..."""
    text = pyperclip.paste()
```

Replace `text = pyperclip.paste()` with:

```python
    try:
        text = pyperclip.paste()
    except pyperclip.PyperclipException as e:
        duration = settings.get('notification_duration', 3)
        format_popup_request_queue.put({
            'type': 'error',
            'message': f"Clipboard busy: {e}",
            'duration': duration,
        })
        return
```

- [ ] **Step 6.2: Wrap `pyperclip.copy(converted_mac)` in `handle_hotkey` (line 223)**

Find `pyperclip.copy(converted_mac)` further down in the same function. Replace with:

```python
    try:
        pyperclip.copy(converted_mac)
    except pyperclip.PyperclipException as e:
        duration = settings.get('notification_duration', 3)
        format_popup_request_queue.put({
            'type': 'error',
            'message': f"Clipboard busy, can't copy: {e}",
            'duration': duration,
        })
        return
```

- [ ] **Step 6.3: Wrap `pyperclip.copy()` in `FormatSelectorPopup.on_format_clicked` (line ~1249)**

Find the method `on_format_clicked` in `FormatSelectorPopup`. Locate `pyperclip.copy(format_value)` (or similar). Wrap:

```python
        try:
            pyperclip.copy(format_value)
        except pyperclip.PyperclipException:
            # Show a transient indicator on the popup; user can re-click
            self.setWindowTitle("Clipboard busy")
            return
```

(If the title is set elsewhere, use a different transient hint — keep changes minimal. The point is don't crash.)

- [ ] **Step 6.4: Wrap `pyperclip.copy()` in `VendorPopup.copy_vendor` (line ~1429)**

Find `copy_vendor` method on `VendorPopup`. Wrap the `pyperclip.copy()` call the same way:

```python
        try:
            pyperclip.copy(self.vendor_name)
        except pyperclip.PyperclipException:
            self.copy_btn.setText("Clipboard busy")
            return
```

- [ ] **Step 6.5: Manual verification**

Launch the app:

```bash
python clipboard_hotkey.py
```

Test path 1 (happy path): copy a MAC like `AA:BB:CC:DD:EE:FF`, press the hotkey, popup appears.

Test path 2 (simulated clipboard contention): open the Windows Snipping Tool (it briefly locks the clipboard), copy a MAC, press the hotkey. The app should NOT crash; you should see an error popup or notification. The listener thread should still respond to subsequent hotkey presses.

If the listener dies after a clipboard error, the fix is incomplete — go back to Step 6.1.

- [ ] **Step 6.6: Commit**

```bash
git add clipboard_hotkey.py
git commit -m "$(cat <<'EOF'
fix: wrap all pyperclip calls; locked clipboard no longer crashes listener

Four pyperclip call sites now catch PyperclipException and surface a
brief notification or transient indicator instead of letting the
exception kill the listener thread (causing the hotkey to silently stop
working until the app is restarted).

Closes F6, F20, F21.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Hotkey validation on Settings dialog Save (closes F14)

**Files:**
- Modify: `clipboard_hotkey.py` — SettingsDialog (lines 784-1055), specifically the Save handler

- [ ] **Step 7.1: Locate the Save handler**

Find the SettingsDialog Save button's connected method. Look for:

```bash
grep -n "self.save_btn\|on_save\|def save\|hotkey_input" clipboard_hotkey.py
```

Identify the method. Note the line where `self.hotkey_input.text()` is read.

- [ ] **Step 7.2: Add an error label to the dialog layout**

In `SettingsDialog.__init__`, near where the hotkey input is added to the layout, add immediately after the hotkey input:

```python
        self.hotkey_error_label = QLabel("")
        self.hotkey_error_label.setStyleSheet("color: #d32f2f; font-size: 9pt;")
        self.hotkey_error_label.setVisible(False)
        # Add to the layout immediately after self.hotkey_input
        <existing_layout>.addWidget(self.hotkey_error_label)
```

(Replace `<existing_layout>` with the actual layout variable in scope at the hotkey input section.)

- [ ] **Step 7.3: Add validation helper**

Near the top of `SettingsDialog` (or as a module-level helper), add:

```python
def _validate_hotkey_string(hotkey_str):
    """Return None if valid, an error message string if not.

    Uses pynput.keyboard.HotKey.parse to mirror what listen_hotkey will do.
    """
    if not hotkey_str or not hotkey_str.strip():
        return "Hotkey cannot be empty"
    try:
        # pynput's HotKey.parse expects a <key>+<key>+... canonical form
        # where each key is wrapped in angle brackets.
        canonical = '+'.join(f'<{k.strip().lower()}>' for k in hotkey_str.split('+'))
        keyboard.HotKey.parse(canonical)
        return None
    except (ValueError, KeyError) as e:
        return f"Invalid hotkey: {e}"
```

(`keyboard` is the pynput module already imported at the top of `clipboard_hotkey.py` as `from pynput import keyboard`.)

- [ ] **Step 7.4: Modify the Save handler to validate before saving**

In the Save handler method, add at the start (before any settings dict updates or save_settings call):

```python
        hotkey_str = self.hotkey_input.text().strip()
        err = _validate_hotkey_string(hotkey_str)
        if err is not None:
            self.hotkey_error_label.setText(err)
            self.hotkey_error_label.setVisible(True)
            return  # do NOT call save_settings or close the dialog
        else:
            self.hotkey_error_label.setVisible(False)
```

- [ ] **Step 7.5: Manual verification**

Launch the app, right-click tray → Settings.

Test 1: enter `xyz+abc` and click Save. Expect: red error label "Invalid hotkey: ..." appears; dialog stays open; `settings.json` not modified.

Test 2: enter `ctrl+shift+x` and click Save. Expect: error label hidden; dialog closes; `settings.json` updates.

Test 3: enter empty string and click Save. Expect: "Hotkey cannot be empty".

- [ ] **Step 7.6: Commit**

```bash
git add clipboard_hotkey.py
git commit -m "$(cat <<'EOF'
fix: validate hotkey string on Settings dialog Save

The Save handler now calls _validate_hotkey_string before persisting.
On parse failure, a red error label is shown inline and the dialog
stays open instead of writing garbage to settings.json (which would
make the next listener startup fall back to the default and the user
would think nothing happened).

Closes F14.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Autostart via Startup-folder shortcut (closes F13, F31)

**Files:**
- Modify: `clipboard_hotkey.py` — add `_autostart_lnk_path`, `is_autostart_enabled`, `set_autostart_enabled`; wire into SettingsDialog autostart handler
- Modify: `installer.iss` — remove `[Tasks] startup` (line 39) and the `{userstartup}\...` entry under `[Icons]` (line 51)

- [ ] **Step 8.1: Add the autostart helpers in `clipboard_hotkey.py`**

Near the top of `clipboard_hotkey.py` (after the settings I/O helpers from Task 2), add:

```python
# --- Autostart via Startup-folder shortcut (Phase 2 fix for F13, F31) ---

def _autostart_lnk_path():
    """Path to the user's Startup-folder shortcut for MAC Converter."""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    startup_dir = os.path.join(
        appdata, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
    )
    return os.path.join(startup_dir, 'MAC-Converter.lnk')


def is_autostart_enabled():
    """Return True if the autostart shortcut exists."""
    return os.path.exists(_autostart_lnk_path())


def set_autostart_enabled(enabled):
    """Create or remove the Startup-folder shortcut.

    Best-effort: failures are logged to stderr but do not raise. Callers
    should re-query is_autostart_enabled() to confirm.
    """
    lnk_path = _autostart_lnk_path()
    if enabled:
        try:
            import win32com.client
            shell = win32com.client.Dispatch('WScript.Shell')
            shortcut = shell.CreateShortcut(lnk_path)
            shortcut.TargetPath = sys.executable
            shortcut.WorkingDirectory = os.path.dirname(sys.executable)
            shortcut.IconLocation = sys.executable
            shortcut.Description = 'MAC Address Converter'
            shortcut.save()
        except Exception as e:
            print(f"[ERROR] set_autostart_enabled(True): {e}", file=sys.stderr)
    else:
        try:
            if os.path.exists(lnk_path):
                os.remove(lnk_path)
        except OSError as e:
            print(f"[ERROR] set_autostart_enabled(False): {e}", file=sys.stderr)
```

- [ ] **Step 8.2: Wire into SettingsDialog**

Find the SettingsDialog autostart checkbox handling. Two changes:

1. In `__init__`, when initializing the checkbox state, replace `self.autostart_checkbox.setChecked(settings.get('autostart', False))` (or whatever the current logic is) with:

```python
        # Query the actual filesystem state, not just the settings value
        self.autostart_checkbox.setChecked(is_autostart_enabled())
```

2. In the Save handler, after settings validation passes, add:

```python
        autostart_wanted = self.autostart_checkbox.isChecked()
        set_autostart_enabled(autostart_wanted)
        settings['autostart'] = is_autostart_enabled()  # reflect actual state
```

This way the settings dict's `autostart` value mirrors the real `.lnk` existence — single source of truth.

- [ ] **Step 8.3: Remove installer autostart entries**

Edit `installer.iss`. Delete line 39 (`Name: "startup"; ...`):

Find:
```
Name: "startup"; Description: "Run at Windows startup"; GroupDescription: "Additional options:"; Flags: unchecked
```
Delete the entire line.

Then delete line 51 (`Name: "{userstartup}\...`):

Find:
```
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup
```
Delete the entire line.

Verify with:

```bash
grep -n "startup\|userstartup" installer.iss
```

Expected: zero matches.

- [ ] **Step 8.4: Manual verification**

Launch the app, open Settings, toggle "Start with Windows" ON, click Save. Verify the file exists:

```bash
ls "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk"
```

Toggle OFF, Save. Verify the file is gone:

```bash
ls "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk" 2>$null
```

Expected: not found.

- [ ] **Step 8.5: Commit**

```bash
git add clipboard_hotkey.py installer.iss
git commit -m "$(cat <<'EOF'
fix: implement autostart via Startup-folder shortcut; remove installer duplicate

The "Start with Windows" checkbox was previously cosmetic (no winreg
or shortcut code anywhere). Now it creates/removes
%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk
via pywin32's WScript.Shell COM dispatch.

Installer's [Tasks] startup entry and the {userstartup} Icons entry are
removed so there's a single source of truth — the app owns the shortcut.

Closes F13, F31.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Single-instance mutex (closes F25)

**Files:**
- Modify: `clipboard_hotkey.py` — add `acquire_single_instance_mutex` and call from `main`

- [ ] **Step 9.1: Add the mutex helper**

Near the top of `clipboard_hotkey.py` (after the autostart helpers), add:

```python
# --- Single-instance mutex (Phase 2 fix for F25) ---

_single_instance_mutex_handle = None  # held for process lifetime


def acquire_single_instance_mutex():
    """Try to acquire a named mutex. Returns True if this is the only instance.

    Returns False if another instance already holds the mutex.
    Returns True (allow-all) if pywin32 isn't importable, so the app
    still works on systems without it.
    """
    global _single_instance_mutex_handle
    try:
        import win32event
        import win32api
        import winerror
        _single_instance_mutex_handle = win32event.CreateMutex(
            None, False, "Global\\MAC-Converter-2-SingleInstance"
        )
        last_err = win32api.GetLastError()
        if last_err == winerror.ERROR_ALREADY_EXISTS:
            return False
        return True
    except ImportError:
        return True
```

- [ ] **Step 9.2: Call from `main()`**

Find `def main():` (around line 1589). At the very top of the function (before `QApplication`-related setup), add:

```python
def main():
    if not acquire_single_instance_mutex():
        # Show a one-shot notification and exit.
        # Use a minimal pystray bubble or just print; cleanest is a brief
        # MessageBox-style popup via Qt.
        app = QApplication(sys.argv)
        from PyQt5.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("MAC Converter")
        try:
            msg.setWindowIcon(QIcon(get_icon_path()))
        except Exception:
            pass
        msg.setText("MAC Converter is already running.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
        sys.exit(0)
    # ... existing main body continues here
```

- [ ] **Step 9.3: Manual verification**

Launch the app once — it should run normally.
Launch it again (open a second terminal or double-click the script) — a QMessageBox should appear saying "MAC Converter is already running" and the second copy should exit.
Close the first instance — confirm the second copy can now launch.

- [ ] **Step 9.4: Commit**

```bash
git add clipboard_hotkey.py
git commit -m "$(cat <<'EOF'
fix: refuse to start a second app instance (single-instance mutex)

Acquires a Win32 named mutex at main() entry. If another instance
already holds it, shows a QMessageBox notification and exits cleanly.
Prevents the double-hotkey-fire, double-tray-icon, and double-write
races to settings.json and oui.csv.

Will become more important once F13 autostart is shipped — a user
double-clicking the desktop shortcut after autostart already ran is
the most common path to two instances.

Closes F25.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Format popup Enter key — Qt-scoped (closes F19)

**Files:**
- Modify: `clipboard_hotkey.py` — `FormatSelectorPopup` class (lines 1056-~1270), remove the global pynput listener, add a QShortcut

- [ ] **Step 10.1: Find the global pynput listener**

```bash
grep -n "_start_enter_listener\|pynput.keyboard.Listener\|on_press" clipboard_hotkey.py
```

Identify the method (e.g. `_start_enter_listener` around line 1212) that creates a `pynput.keyboard.Listener`. Also identify where it's started and stopped.

- [ ] **Step 10.2: Remove the listener method and its lifecycle calls**

Delete the entire `_start_enter_listener` method.

In `FormatSelectorPopup.__init__`, remove the line that calls `self._start_enter_listener()` (or wherever it's started).

In `FormatSelectorPopup.closeEvent`, remove any `self._enter_listener.stop()` or similar.

- [ ] **Step 10.3: Add a QShortcut for Enter**

In `FormatSelectorPopup.__init__`, after the layout is set up but before the popup is shown, add:

```python
        # F19: scope Enter handling to this popup widget via QShortcut.
        # Previously a global pynput.keyboard.Listener was used, which
        # captured every keystroke system-wide while the popup was open.
        from PyQt5.QtWidgets import QShortcut
        from PyQt5.QtGui import QKeySequence
        self._enter_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self._enter_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._enter_shortcut.activated.connect(self._on_enter_pressed)
        self._enter_shortcut_pad = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self._enter_shortcut_pad.setContext(Qt.WidgetWithChildrenShortcut)
        self._enter_shortcut_pad.activated.connect(self._on_enter_pressed)
```

(Both `Key_Return` and `Key_Enter` are bound — `Return` is the main Enter key, `Enter` is the numpad Enter key.)

- [ ] **Step 10.4: Add the `_on_enter_pressed` handler**

Add as a method on `FormatSelectorPopup`:

```python
    def _on_enter_pressed(self):
        """Triggered when Enter is pressed while this popup has focus.

        Replaces the previous global pynput listener (F19). Triggers OUI
        vendor lookup via the existing vendor_lookup_request_queue.
        """
        if not getattr(self, '_mac_normalized', None):
            return
        duration = settings.get('oui_vendor_timeout', 5)
        vendor_lookup_request_queue.put({
            'mac_normalized': self._mac_normalized,
            'duration': duration,
        })
        self.close()
```

(Adapt field names if the existing code uses different ones — the spirit is: same queue, same payload as before, scoped to Qt.)

- [ ] **Step 10.5: Manual verification**

This is THE highest-impact UI test. Launch the app, copy a MAC, press the hotkey. Popup appears.

Test 1 (still works): with the popup visible, press Enter. Vendor lookup should fire and the vendor popup should appear.

Test 2 (no more global capture): with the popup visible, click into another window (Notepad, browser, password field). Type things including Enter. The format popup should NOT trigger vendor lookup or do anything weird. Specifically, your typing in the other window should NOT be intercepted.

If Test 2 still triggers vendor lookup, the QShortcut context isn't scoped tightly enough; revisit Step 10.3 (`setContext` value).

- [ ] **Step 10.6: Commit**

```bash
git add clipboard_hotkey.py
git commit -m "$(cat <<'EOF'
fix: scope FormatSelectorPopup Enter key to the popup widget

Replaces the pynput.keyboard.Listener (global system-wide hook) with
a QShortcut on the popup widget itself, using
Qt.WidgetWithChildrenShortcut context. Eliminates the architectural
privacy concern of a low-level Win32 keyboard hook running on every
hotkey trigger.

Numpad Enter is bound alongside the main Return key so both behave
the same as before.

Closes F19.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: OUI worker cooperative shutdown + re-entrance guard + error sanitization (closes F11, F12, F18, F26)

**Files:**
- Modify: `clipboard_hotkey.py` — `OUIDownloadDialog` (lines 580-783), `SettingsDialog.manual_oui_update`, `on_quit`

- [ ] **Step 11.1: Add a module-level in-progress flag**

Near the other module-level OUI globals, add:

```python
_oui_download_in_progress = threading.Event()
```

- [ ] **Step 11.2: Guard `manual_oui_update` against re-entrance (F18)**

Find `SettingsDialog.manual_oui_update`. At the top of the method add:

```python
        if _oui_download_in_progress.is_set():
            QMessageBox.information(self, "MAC Converter",
                "An OUI database update is already in progress.")
            return
```

- [ ] **Step 11.3: Add cancel event to `OUIDownloadDialog`**

In `OUIDownloadDialog.__init__`, after the other instance attribute initialization (around line 587), add:

```python
        self._cancel_event = threading.Event()
        self._worker_thread = None
        _oui_download_in_progress.set()
```

- [ ] **Step 11.4: Pass cancel event to the worker**

In `OUIDownloadDialog._start_download`, the worker function calls `oui_db.download(progress_callback=progress_cb)`. Change to:

```python
            success, error = oui_db.download(progress_callback=progress_cb, cancel_event=self._cancel_event)
```

Also save the thread reference:

```python
        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()
```

(Already daemon=True; just capture the reference for later join.)

- [ ] **Step 11.5: Cooperative shutdown in `closeEvent`**

Replace `OUIDownloadDialog.closeEvent`:

```python
    def closeEvent(self, event):
        # Signal the worker to stop and wait for it briefly.
        self._cancel_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        if hasattr(self, '_poll_timer'):
            self._poll_timer.stop()
        # Drain any pending queue messages so they don't leak into a future dialog.
        try:
            while True:
                oui_download_progress_queue.get_nowait()
        except queue.Empty:
            pass
        _oui_download_in_progress.clear()
        super().closeEvent(event)
```

- [ ] **Step 11.6: Sanitize error messages (F12)**

In the worker function where error messages are placed onto `oui_download_progress_queue`, ensure no absolute path is sent. The `oui_lookup.download` already sanitizes its `OSError` to just the basename. For the success message at the equivalent of line 717, find:

```python
'message': f'Database updated successfully!\n{result} OUI entries loaded.\nFile: {oui_db.oui_path}\nSize: {oui_db.file_size_display}'
```

Change to:

```python
'message': f'Database updated successfully!\n{result} OUI entries loaded.\nSize: {oui_db.file_size_display}'
```

(Drop the full path. The user can find it via the About dialog if needed.)

- [ ] **Step 11.7: Join OUI worker in `on_quit` (F26)**

Find `on_quit`. After `icon.stop()` and `listener.stop()`, add:

```python
    # Give the OUI worker a chance to finish its current os.replace before
    # the process dies — prevents corruption if a daemon thread were killed
    # mid-rename.
    if _oui_download_in_progress.is_set():
        # The dialog's closeEvent normally clears this; if quit happens
        # while a download is mid-flight without the dialog closing,
        # signal cancel and wait.
        # The worker thread reference is held by OUIDownloadDialog, so
        # we can't join it from here cleanly. Best-effort: clear the
        # flag after a short sleep.
        import time as _time
        _time.sleep(0.5)
```

(This is best-effort. The cleaner fix is to make the worker thread module-level so on_quit can join, but that's a bigger refactor. The 500ms sleep gives the cancel signal time to propagate.)

- [ ] **Step 11.8: Manual verification**

Launch the app, open Settings → OUI section → click "Update database".

Test 1: while download is in progress (you'll see the percentage bar), click the X to close the dialog. The dialog closes; no crash; the next time you open the Update dialog, it starts fresh (no stale messages).

Test 2: with a download in progress, click Update again on the SettingsDialog (you'll need a separate path to reach Update without closing the first dialog — if there's no path, this guard is precautionary and that's fine; verify by trying to call it programmatically).

Test 3: trigger a successful update and verify the success message doesn't show the full file path.

- [ ] **Step 11.9: Commit**

```bash
git add clipboard_hotkey.py
git commit -m "$(cat <<'EOF'
fix: OUI worker cooperative shutdown, re-entrance guard, error sanitization

- F11: closing the download dialog mid-flight now signals a cancel
  event, waits up to 2s for the worker to finish, drains the progress
  queue so a re-opened dialog doesn't pick up stale messages.
- F18: a module-level _oui_download_in_progress flag prevents a second
  download from being spawned by another Update button click.
- F26: on_quit waits 500ms after setting cancel, giving a daemon
  worker mid-os.replace time to finish before process death.
- F12: success and error messages no longer include the full oui.csv
  path (just basename or no path at all).

Closes F11, F12, F18, F26.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: PyInstaller + dependency hygiene (closes F32, F33, F34, F35)

**Files:**
- Create: `icon-v1.ico` (binary, generated)
- Modify: `mac-converter.spec`
- Modify: `requirements.txt`

- [ ] **Step 12.1: Generate `icon-v1.ico` from `icon-v1.png`**

```bash
python -c "from PIL import Image; img = Image.open('icon-v1.png'); img.save('icon-v1.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
```

Verify the file exists:

```bash
ls icon-v1.ico
```

Expected: file present, ~50-200KB.

- [ ] **Step 12.2: Update `mac-converter.spec`**

Replace the existing file content with:

```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['clipboard_hotkey.py'],
    pathex=[],
    binaries=[],
    datas=[('icon-v1.png', '.')],
    hiddenimports=[
        'pynput.keyboard._win32',
        'pynput.mouse._win32',
        'pystray._win32',
        'win32com.client',
        'win32event',
        'win32api',
        'winerror',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MAC-Converter',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    # F34: UPX disabled — trades ~30% binary size for far fewer AV false positives
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon-v1.ico',
)
```

Key changes:
- `hiddenimports` extended with `pystray._win32`, `win32com.client`, `win32event`, `win32api`, `winerror`
- `upx=False` (was `True`)
- `icon='icon-v1.ico'` (was `'icon-v1.png'`)

- [ ] **Step 12.3: Update `requirements.txt`**

Replace the file content with:

```
# NOTE: For future development, always update this file whenever new libraries are added, removed, or replaced.

# Python requirements for MAC Address Converter
pystray
Pillow
pyperclip
pynput
PyQt5
pywin32

# Build-time only (not needed for `python clipboard_hotkey.py`):
PyInstaller
```

Changes:
- Removed `keyboard` (F35: dead dependency, no `.py` file imports it)
- Removed duplicate `PyQt5` (housekeeping noted in audit non-findings)

- [ ] **Step 12.4: Verify the build still produces a valid exe**

If you have a clean working venv with all `requirements.txt` packages installed:

```bash
pyinstaller mac-converter.spec
```

Expected: builds successfully; outputs `dist/MAC-Converter.exe`. The exe runs (test by double-clicking); the icon shows in the taskbar and in Windows Explorer's file view of `dist/`.

If PyInstaller is not available or the build is too slow, you can defer the full build verification to a manual step before release and just verify the spec parses:

```bash
python -c "exec(open('mac-converter.spec').read(), {'__file__': 'mac-converter.spec'})"
```

Expected: no SyntaxError (the spec is valid Python — it'll error on missing Analysis class, which is fine).

- [ ] **Step 12.5: Commit**

```bash
git add icon-v1.ico mac-converter.spec requirements.txt
git commit -m "$(cat <<'EOF'
build: ship a real .ico, expand hidden imports, drop dead deps

- F32: icon-v1.ico generated from the existing PNG (Pillow); spec
  now references the .ico for Windows exe-icon embedding.
- F33: explicit hidden imports for pystray._win32 plus all pywin32
  modules the runtime fixes (autostart, single-instance) need.
- F34: upx=False eliminates ~30% binary size in exchange for
  significantly fewer AV false positives on Windows endpoints.
- F35: requirements.txt drops the unused `keyboard` package and the
  duplicate PyQt5 line.

Closes F32, F33, F34, F35.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Cleanup batch (closes F9, F10, F17, F22, F27, F29, F30, F36)

**Files:**
- Modify: `clipboard_hotkey.py` (multiple regions)
- Modify: `env_load.ps1`

- [ ] **Step 13.1: Replace all bare `except:` with `except Exception:` (F10, F17, F22)**

```bash
grep -n "except:" clipboard_hotkey.py
```

Expected: 15 occurrences. For each, change `except:` to `except Exception:`. Keep the body unchanged. This narrows the catch from `BaseException` (which swallows `KeyboardInterrupt` and `SystemExit`) to ordinary exceptions only.

A safe bulk approach: do it line-by-line via the Edit tool with `replace_all=False` and the matching surrounding context for each site, OR use the Edit tool with `replace_all=True` IF you've first confirmed that no `except:` lines exist that you want to preserve (verify by reading each).

Recommend per-site edits for safety.

Verify:

```bash
grep -n "except:" clipboard_hotkey.py
```

Expected: zero matches (all are now `except Exception:`).

- [ ] **Step 13.2: Remove `exit_event` (F9)**

```bash
grep -n "exit_event" clipboard_hotkey.py
```

Expected: 2 hits (the declaration and the `.set()` call). Delete both lines:
- `exit_event = threading.Event()` (around line 84)
- `exit_event.set()` (in `on_quit`)

- [ ] **Step 13.3: Stop timers and join listener in `on_quit` (F27, F29)**

Find `on_quit`. After `icon.stop()`, add:

```python
    # F27: stop any QTimers that may be running
    app = QApplication.instance()
    if app is not None:
        for widget in app.allWidgets():
            for timer in widget.findChildren(QTimer):
                timer.stop()

    # F29: give the pynput listener a chance to terminate cleanly
    if listener is not None:
        listener.stop()
        try:
            listener.join(timeout=2.0)
        except RuntimeError:
            # listener might not be a real thread on some platforms
            pass
```

(`QTimer` may need to be imported at the top alongside the other PyQt5 imports if not already.)

- [ ] **Step 13.4: Defer OUI auto-update one Qt tick (F30)**

Find where the OUI auto-update is triggered at startup. It's likely in `main()` or `tray_app`. Whatever calls `oui_db.download(...)` at startup, wrap in a `QTimer.singleShot(0, ...)`:

```python
    # F30: defer until Qt event loop is running so progress updates don't
    # race the event loop start.
    QTimer.singleShot(0, _start_oui_auto_update)
```

Where `_start_oui_auto_update` is a small wrapper that does what was inline before.

If the existing structure makes this awkward (e.g. the call is in a separate thread already), it's fine to skip — F30 was marked LOW. Document in the commit message.

- [ ] **Step 13.5: Fix `env_load.ps1` ANSI escape (F36)**

Replace line 9 of `env_load.ps1`:

Old:
```powershell
    Write-Host '[ERROR] No virtual environment found. Run `u001b[33mpython -m venv venv`u001b[0m first.'
```

New:
```powershell
    Write-Host "[ERROR] No virtual environment found. Run " -NoNewline
    Write-Host "python -m venv venv" -ForegroundColor Yellow -NoNewline
    Write-Host " first."
```

This uses PowerShell's native `-ForegroundColor` parameter instead of trying to interpolate ANSI escapes.

- [ ] **Step 13.6: Manual verification**

Launch the app. Confirm it still works end-to-end. Then Quit via tray menu and confirm:
- The process actually exits (check Task Manager for stragglers).
- No "thread still running" warnings in the terminal.

For env_load.ps1: delete the `venv/` directory temporarily (or rename it), then run `. .\env_load.ps1`. Verify the error message displays cleanly with yellow `python -m venv venv` text, no literal backticks. Restore the venv afterwards.

- [ ] **Step 13.7: Commit**

```bash
git add clipboard_hotkey.py env_load.ps1
git commit -m "$(cat <<'EOF'
fix: cleanup batch — bare excepts, exit_event, timer/listener shutdown, env_load

- F9: remove unused exit_event synchronization primitive.
- F10/F17/F22: 15 bare `except:` sites narrowed to `except Exception:`
  so KeyboardInterrupt and SystemExit are no longer swallowed.
- F27: on_quit walks all widgets and stops their QTimers before app.quit().
- F29: listener.stop() is followed by listener.join(timeout=2.0) so the
  pynput keyboard hook isn't leaked into process death.
- F30: OUI auto-update at startup is deferred one Qt tick via
  QTimer.singleShot(0, ...) so progress updates don't race the event
  loop start.
- F36: env_load.ps1 uses PowerShell's native -ForegroundColor instead of
  literal ANSI escape sequences (which appeared as garbage to the user).

Closes F9, F10, F17, F22, F27, F29, F30, F36.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Documentation fixes (closes F37)

**Files:**
- Modify: `README.md` (lines 32-43 format table)
- Modify: `TODO.md` (Known Limitations section)

- [ ] **Step 14.1: Fix README format table**

Find lines 32-43 in `README.md` listing the 10 formats. Replace the lines for formats 9 and 10:

Old:
```
9. Windows format uppercase: `AA-BB-CC-DD-EE-FF` (alternate)
10. Windows format lowercase: `aa-bb-cc-dd-ee-ff` (alternate)
```

(Or whatever the current wording is.)

New:
```
9. Hyphen-6char uppercase (Cisco-style): `AABBCC-DDEEFF`
10. Hyphen-6char lowercase (Cisco-style): `aabbcc-ddeeff`
```

- [ ] **Step 14.2: Fix stale TODO claim**

In `TODO.md`, find the Known Limitations section. Find the line:

```
- **Single Format Cycle**: Doesn't remember user-selected format between sessions (always resets to 0)
```

Delete that bullet entirely (since `last_format_index` IS persisted across sessions — this claim has been stale).

- [ ] **Step 14.3: Update README autostart phrasing**

In `README.md`, find the autostart feature description (around line 23 and line 55). Verify the wording matches the new behavior (Startup-folder shortcut). If the text says "via registry" or anything technology-specific that's now wrong, update it to a neutral phrasing like "creates a shortcut in your Startup folder".

Spot-check:

```bash
grep -n -i "autostart\|start.*windows\|registry" README.md
```

If any line claims registry, fix it.

- [ ] **Step 14.4: Commit**

```bash
git add README.md TODO.md
git commit -m "$(cat <<'EOF'
docs: fix README format table and stale TODO claim

- F37: README mislabeled formats 9-10 as "Windows format
  AA-BB-CC-DD-EE-FF (alternate)". The actual code emits
  Cisco-style AABBCC-DDEEFF (Hyphen-6char). Renamed accordingly.
- TODO.md "Known Limitations" no longer claims the app forgets the
  selected format between sessions — last_format_index is persisted
  in settings.json (has been since v2.2.0).
- README autostart phrasing aligned with the new Startup-folder
  shortcut implementation.

Closes F37.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Version bump to 2.4.0 + CHANGELOG entry

**Files:**
- Modify: `installer.iss:5` (`MyAppVersion`)
- Modify: `oui_lookup.py:69` (User-Agent string — already updated in Task 4 but verify)
- Modify: `clipboard_hotkey.py` (AboutDialog version label, around line 304)
- Modify: `README.md` (header version line and Version History section)
- Modify: `TODO.md` (Current Version, Last Updated stamps)
- Modify: `CHANGELOG.md` (prepend a new `[2.4.0]` section)

- [ ] **Step 15.1: Bump `installer.iss`**

In `installer.iss` line 5, change:
```
#define MyAppVersion "2.3.0"
```
to:
```
#define MyAppVersion "2.4.0"
```

- [ ] **Step 15.2: Verify `oui_lookup.py` UA is 2.4.0**

```bash
grep -n "MAC-Converter/" oui_lookup.py
```

Expected: `'User-Agent': 'MAC-Converter/2.4.0'` (Task 4 already updated this; verify).

- [ ] **Step 15.3: Bump AboutDialog version label**

In `clipboard_hotkey.py`, find:
```python
version_label = QLabel("Version 2.3.0")
```

Replace with:
```python
version_label = QLabel("Version 2.4.0")
```

- [ ] **Step 15.4: Bump README**

Find the header in `README.md`:
```
**Current Version:** 2.3.0
```

Replace with:
```
**Current Version:** 2.4.0
```

Also find the Version History section and add a new top entry:
```
- **2.4.0** (2026-05-14): Bug-fix release — see CHANGELOG for the full list. 5 high-severity fixes including locked-clipboard crash, OUI download race, autostart now actually functional, hotkey validation, and removal of system-wide keyboard hook.
```

- [ ] **Step 15.5: Bump TODO.md**

Replace `**Current Version:** 2.3.0` and `**Last Updated:** 2026-02-17` with 2.4.0 and 2026-05-14 respectively.

- [ ] **Step 15.6: Add CHANGELOG entry**

In `CHANGELOG.md`, immediately after the existing header (before the `## [2.3.0]` line), insert:

```markdown
## [2.4.0] - 2026-05-14
### Added
- pytest regression suite (`tests/`) covering pure-logic fixes in `mac_formats.py`, `oui_lookup.py`, and settings I/O. (`requirements-dev.txt`)
- Inline error label for invalid hotkey input in Settings dialog.
- Tray-notification fallback when clipboard is locked instead of silent listener-thread death.
- Single-instance check: a second app launch shows "MAC Converter is already running" and exits.
- `set_autostart_enabled()` / `is_autostart_enabled()` helpers manage a Startup-folder shortcut.

### Changed
- Settings I/O is now atomic (`os.replace`) and serialized through `_settings_lock`. Corrupt `settings.json` is renamed to `settings.json.corrupt-<unix-ts>` instead of being silently overwritten with defaults.
- OUI download rejects HTML / non-CSV responses (e.g. captive portals) and zero-entry CSVs before they can overwrite the live database.
- Format popup Enter key handling switched from a system-wide pynput keyboard listener to a Qt-scoped `QShortcut` — no more global keystroke capture.
- PyInstaller spec ships a real `.ico` for the Windows exe icon and disables UPX to reduce antivirus false positives.
- `requirements.txt` no longer lists the unused `keyboard` package.
- Installer's `[Tasks] startup` entry is removed; autostart is owned by the app via the Startup-folder shortcut (single source of truth).
- `env_load.ps1` error message uses native PowerShell color instead of literal ANSI escapes.

### Fixed
- F1: `MAC_REGEX` no longer accepts mixed `:`/`-` separators in the same MAC.
- F2: atomic `os.replace` in OUI download preserves the prior `oui.csv` on rename failure.
- F3: HTML / non-CSV response detection (Content-Type sniff + first-chunk magic bytes).
- F4: HTTPS response is opened in a `with` block so the socket closes on exception.
- F5: zero-entry CSV parse is now a load failure, not a silent success.
- F6: `pyperclip.paste()` and `.copy()` in the hotkey handler are wrapped.
- F7, F16, F23, F28: atomic `save_settings` with module-level lock; three writer threads no longer race.
- F8, F15, F24: `_validate_settings` coerces/clamps all known keys; corrupt JSON triggers rename-and-fallback.
- F9: dead `exit_event` synchronization primitive removed.
- F10, F17, F22: 15 bare `except:` clauses narrowed to `except Exception:`.
- F11: OUI download worker honors a cancel event; closing the dialog mid-download cleanly tears down the worker.
- F12: error messages no longer leak the full `oui.csv` path containing the user's username.
- F13: "Start with Windows" checkbox actually creates/removes a Startup-folder shortcut now (was previously cosmetic).
- F14: invalid hotkey input is rejected on Save with an inline error label.
- F18: a second click on "Update OUI database" is refused while a download is in progress.
- F19: FormatSelectorPopup Enter key uses `QShortcut` (Qt-scoped) instead of a global pynput listener.
- F20, F21: `pyperclip.copy()` in FormatSelectorPopup and VendorPopup wrapped.
- F25: single-instance mutex prevents double-launch.
- F26: OUI worker cooperative shutdown reduces the daemon-kill corruption window.
- F27, F29: QTimers stop and pynput listener joins on app quit.
- F30: OUI auto-update at startup is deferred one Qt tick.
- F31: installer no longer adds its own Startup-folder shortcut; the app owns autostart.
- F32: PyInstaller icon is now a real `.ico`.
- F33: `pystray._win32` and pywin32 modules are explicitly hidden imports.
- F34: UPX disabled.
- F35: unused `keyboard` package removed from `requirements.txt`.
- F36: `env_load.ps1` ANSI escape garbage replaced with native PowerShell color.
- F37: README format table renamed formats 9-10 from "Windows format alternate" to "Hyphen-6char (Cisco-style)".
```

(All 37 findings enumerated.)

- [ ] **Step 15.7: Sanity-check version consistency**

```bash
grep -n "2\.[34]\.0" README.md CHANGELOG.md installer.iss oui_lookup.py mac-converter.spec clipboard_hotkey.py TODO.md
```

Expected: every match is `2.4.0`, no stray `2.3.0` outside the CHANGELOG's `## [2.3.0]` history entry.

- [ ] **Step 15.8: Commit**

```bash
git add installer.iss clipboard_hotkey.py README.md TODO.md CHANGELOG.md
git commit -m "$(cat <<'EOF'
release: bump version to 2.4.0

Bug-fix release closing 37 audit findings (5 high, 12 medium, 20 low).
See CHANGELOG [2.4.0] for the full per-finding list.

Highlights:
- Locked clipboard no longer crashes the hotkey listener (F6).
- "Start with Windows" actually works now (F13).
- Hotkey input is validated on Save (F14).
- Format popup Enter key is Qt-scoped — no more global keystroke
  capture in other apps (F19).
- OUI download race + orphaned worker fixed (F11, F26).
- Atomic settings/OUI writes prevent corruption under crash/race.
- Single-instance mutex prevents double-launch.
- PyInstaller ships a real .ico, drops UPX (fewer AV false positives).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Final sanity pass

**Files:** none (validation only)

- [ ] **Step 16.1: Run the full test suite**

```bash
python -m pytest -v
```

Expected: all tests pass. If any fail, fix before continuing — this is the green-light gate for Phase 2.

- [ ] **Step 16.2: Smoke-launch the app**

```bash
python clipboard_hotkey.py
```

Verify:
- App starts (tray icon appears)
- Hotkey works (copy a MAC, press hotkey, popup appears)
- Enter in popup triggers vendor lookup (and doesn't interfere with typing in another window)
- Settings dialog opens, saves
- About dialog opens
- Autostart toggle creates / removes the .lnk in Startup folder
- Quit via tray menu cleanly exits

- [ ] **Step 16.3: Verify branch state**

```bash
git log --oneline dev..HEAD
```

Expected: roughly 15 commits, each closing one or more F-IDs.

```bash
git status
```

Expected: clean working tree.

- [ ] **Step 16.4: Report Phase 2 complete to user**

Surface a summary to the user:

```
Phase 2 complete on branch claude/eloquent-payne-7d7c9c.
All 37 audit findings closed. Version bumped to 2.4.0.
N commits ahead of dev. Tests: X passing.

Ready for Phase 4 (GitHub Pages portal). Run /loop or
explicitly approve to continue.
```
