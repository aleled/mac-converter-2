# Phase 1 Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a committed audit report (`docs/AUDIT-2026-05-14.md`) listing every real bug or security weakness in the `mac-converter-2` repository at v2.3.0, with file:line precision, severity, and a proposed fix per finding.

**Architecture:** Read-only audit — no source code changes in this phase. Tasks read files in topical groups, document findings in a running scratchpad (which IS the deliverable file from Task 1 onward), and finalize/commit at the end. Each task lists the explicit threat categories to inspect so the engineer doesn't have to re-derive them from the spec.

**Tech Stack:** Markdown deliverable. Python 3.x available locally for quick sanity probes against `mac_formats.py` and `oui_lookup.py`. Git for the single closing commit.

---

## Conventions used in every task

- **Findings format** (append to the report's `## Findings` section as you go):
  ```markdown
  ### F<N> [SEVERITY] One-line title
  - **File:** `path/to/file.py:LINE` or `LINE-LINE`
  - **What:** Observable bug or weakness in one or two sentences
  - **Why it's a bug:** Trigger condition; what goes wrong
  - **Proposed fix:** Concrete remediation (a code snippet or specific change)
  - **Effort:** S | M | L
  ```
- **Severity rubric** (from the design spec, do not invent new levels):
  - **Critical** — data loss, RCE, persistent app failure
  - **High** — crash or wrong result on a common path
  - **Medium** — wrong behavior in edge cases, latent bugs behind unlikely input
  - **Low** — defensive hardening
- **Non-findings**: when a threat category was inspected and is sound, briefly note it under the `## Non-findings` section so coverage is auditable. One bullet per category, not per file.
- **No code changes in this phase.** If you spot a fix worth doing, write it in the **Proposed fix** field and move on — Phase 2 will implement it.
- **Number findings F1, F2, …** across the whole audit, in the order discovered. Do not renumber when sorting by severity at the end.
- **Run from the worktree root:** `C:\working\mac-converter-2\.claude\worktrees\eloquent-payne-7d7c9c`. All file paths in the report are relative to this root.

---

### Task 1: Create the audit scratchpad

**Files:**
- Create: `docs/AUDIT-2026-05-14.md`

- [ ] **Step 1: Write the initial report skeleton**

Create `docs/AUDIT-2026-05-14.md` with this exact content:

```markdown
# MAC Address Converter — Security & Bug Audit

**Date:** 2026-05-14
**Version audited:** v2.3.0
**Branch:** `claude/eloquent-payne-7d7c9c`
**Scope:** All tracked files at repo root except `old/` and `icon-v1.png`.
**Severity rubric:** Critical / High / Medium / Low (see design spec).

## Summary

_To be filled in Task 12 after all findings are collected._

## Findings

_Findings appended in discovery order, F1, F2, ... across all tasks._

## Non-findings

_Areas inspected that were sound. Appended as each task completes._

## Files reviewed

_Listed in Task 12._
```

- [ ] **Step 2: Verify the file is present**

Run: `ls docs/AUDIT-2026-05-14.md`
Expected: file exists.

---

### Task 2: Audit `mac_formats.py`

**Files:**
- Read: `mac_formats.py` (55 lines, full file)
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **Regex correctness** (`MAC_REGEX` at line 27): does it accept exactly the formats the codebase claims to support? Does it reject obvious non-MACs like 13-hex-char strings? Does the negative lookbehind/ahead `(?<![0-9A-Fa-f])` / `(?![0-9A-Fa-f])` actually fire for the intended boundaries given that `detect_mac` already calls `fullmatch`?
2. **Format coverage vs README claim**: README lines 32-43 claim formats 9-10 are "Windows format alternate"; `MAC_FORMATS` lines 18-19 actually emit `Hyphen-6char` (`AABBCC-DDEEFF`). Confirm the mismatch, decide if the *code* is wrong, the *README* is wrong, or both.
3. **Detect_mac normalization**: line 38 — `len(norm) == 12` and `all(c in '0123456789abcdefABCDEF' for c in norm)`. Is the second check redundant given the regex already restricted character class? Is there any input where it would matter?
4. **Locale/case behavior**: lambdas at lines 14-23 — do `.upper()` and `.lower()` behave correctly under a Turkish or other non-ASCII locale (the `dotted I` problem)? Hex digits are ASCII so likely safe, but state the conclusion in non-findings.

- [ ] **Step 1: Read the file end-to-end**

Run: `cat mac_formats.py` (or open in editor). Make sure you have the entire file held in mind.

- [ ] **Step 2: Sanity-probe the regex with edge cases**

Run from the worktree root:

```bash
python -c "
from mac_formats import detect_mac, convert_mac
cases = [
    '00-1A-2B-3C-4D-5E',           # standard hyphen
    'AA:BB:CC:DD:EE:FF',           # standard colon
    'aabb.ccdd.eeff',              # cisco dot lowercase
    'AABBCC-DDEEFF',               # hyphen-6char (formats 9/10)
    'aabbccddeeff',                # plain 12-hex
    'AABBCCDDEEFF1',               # 13 chars — must reject
    'GG-HH-II-JJ-KK-LL',           # non-hex
    '00:1A:2B:3C:4D:5E:FF',        # 7 octets — must reject
    '  AA:BB:CC:DD:EE:FF  ',       # whitespace — strip handles it
    '',                            # empty
]
for c in cases:
    print(repr(c), '->', detect_mac(c))
"
```

Expected: first 5 return a 12-char hex string; cases 6-9 return `None`; whitespace case returns the normalized MAC; empty returns `None`. Note in the audit any deviation.

- [ ] **Step 3: Verify each format output**

```bash
python -c "
from mac_formats import detect_mac, convert_mac, MAC_FORMATS
mac = detect_mac('00-1A-2B-3C-4D-5E')
for desc, val in convert_mac(mac):
    print(f'{desc:35s} -> {val}')
print()
print('Total formats:', len(MAC_FORMATS))
"
```

Expected: 10 lines, each format output matches its description. Total: 10.

- [ ] **Step 4: Append findings**

Append discovered issues (numbered starting at F1) to the `## Findings` section of `docs/AUDIT-2026-05-14.md`. If `mac_formats.py` is clean, append nothing to Findings.

Append to `## Non-findings`:
- `**mac_formats.py:** Regex correctly rejects [list of edge cases verified]; format functions verified to emit expected strings.`

- [ ] **Step 5: Do NOT commit yet** — single closing commit at Task 13.

---

### Task 3: Audit `oui_lookup.py`

**Files:**
- Read: `oui_lookup.py` (257 lines, full file)
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **TLS / certificate verification** (line 71 `urlopen`): Python's `urllib` on Windows uses the system trust store via OpenSSL by default since 3.6, but the URL is `https://standards-oui.ieee.org/oui/oui.csv` — is the cert chain validated? Is there any `ssl._create_unverified_context` lurking? If verification could fail silently, that's a finding.
2. **Atomic rename on Windows** (lines 98-104): `os.rename` on Windows fails if the destination exists; code handles that by `os.remove` first, but there's a window where the file is gone before the rename succeeds. If the rename fails, the user loses their old database. Severity ≥ Medium.
3. **Download size sanity** (line 94): `< 1000` bytes is considered "too small". The real IEEE CSV is ~3.5 MB. Is the threshold meaningful protection against a hijacked / captive-portal HTML response? Could a 1001-byte HTML page slip past? What happens at parse time?
4. **CSV parsing tolerance** (lines 135-143): `len(row) >= 3` and `len(assignment) == 6`. Is there any way a malformed row could `IndexError`? What about embedded commas in `Organization Name` that aren't quoted? (CSV module handles standard quoting, but worth confirming the IEEE feed format.)
5. **Threading correctness** (`_lock` usage): `load()` acquires `_lock`, sets `_loading`, releases. Meanwhile `lookup()` reads `_db` and `_loaded` without holding the lock. Is that a race? Likely safe on CPython due to GIL on dict reads, but is `_loaded` and `_db` ever set in an order where a reader could see `_loaded == True` but `_db` partially populated?
6. **File-handle / response leak** (line 71): `response = urllib.request.urlopen(...)` is not in a `with` block. If `response.read()` raises mid-loop, the socket isn't closed. Severity Low/Medium.
7. **Disk full / OSError on rename or write** (lines 98-104): handled by the generic `except OSError`? Trace the error paths.
8. **Path traversal**: `data_dir` is supplied by caller — verify call site in `clipboard_hotkey.py` uses a hardcoded safe path, not user input.
9. **Encoding** (line 135): `errors='replace'` — does silent substitution of bad bytes produce wrong vendor names? Low severity.

- [ ] **Step 1: Read the file end-to-end**

Run: `cat oui_lookup.py`.

- [ ] **Step 2: Verify cert handling explicitly**

```bash
python -c "
import ssl, urllib.request
# Does the default context verify? Print and confirm.
ctx = ssl.create_default_context()
print('Verify mode:', ctx.verify_mode)
print('Check hostname:', ctx.check_hostname)
"
```

Expected: `CERT_REQUIRED`, `True`. If `urllib.request.urlopen` is called without an explicit context, it uses this default — confirm by reading the code that no `context=` arg overrides it.

- [ ] **Step 3: Probe for the rename race**

Inspect lines 98-104. Confirm sequence: write temp → remove dest → rename temp → dest. Yes, there is a window. Document under findings if confirmed (severity Medium: "old database lost on rename failure").

- [ ] **Step 4: Probe size threshold logic**

Read lines 94-95. The threshold is 1000 bytes. A captive-portal redirect to an HTML login page is typically 2-10 KB. Could pass the size check then crash the CSV parser with cryptic errors. Document if so.

- [ ] **Step 5: Probe call site for `data_dir`**

```bash
grep -n "OUIDatabase(" clipboard_hotkey.py
```

Confirm the caller passes a hardcoded `%APPDATA%`-derived path, not user input. Note in non-findings.

- [ ] **Step 6: Append findings**

Append numbered findings (continuing from where Task 2 left off) to `## Findings`. Append one or more bullets to `## Non-findings` for the threat categories that came up clean.

- [ ] **Step 7: Do NOT commit yet.**

---

### Task 4: Audit `clipboard_hotkey.py` — Part 1 (lines 1–413: tray icon, hotkey handler, AboutDialog)

**Files:**
- Read: `clipboard_hotkey.py:1-413`
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **Bare `except:` clauses** (lines 59, 159, 252, 291): catching `BaseException` swallows `KeyboardInterrupt` and `SystemExit`. Severity Low if non-critical paths, Medium if it can mask real failures.
2. **`exit_event` not actually waited on** (line 84): is `exit_event.set()` checked anywhere? If not, dead code.
3. **`queue.Queue` producers without consumers**: every queue declared globally (lines 85-110) needs to be drained somewhere. Confirm each has a reader. If a producer pushes without a reader running, it's a memory leak. (Each queue is small so leak is bounded, but worth flagging if obvious.)
4. **Global mutable state racing** (`current_notification_timer`, `current_format_popup`, `current_vendor_popup`): are these accessed from multiple threads? `handle_hotkey` runs on the pynput listener thread; the popups are created on the Qt main thread. The globals are touched from both? Trace and confirm.
5. **`pyperclip.paste()` failure modes**: on Windows can raise `PyperclipWindowsException` if clipboard locked. Is the call at line 199 wrapped? If not, the listener thread dies silently. Severity High if so.
6. **`pyperclip.copy()` partial-write**: same concern at line 223.
7. **`save_settings` called from listener thread** (line 227): race against the Settings dialog also writing to the same file. Document the file path: `%APPDATA%\mac-converter-2\settings.json`. Atomic write? Look ahead to Task 8 confirmation.
8. **Format index wrap correctness** (line 217): `(last_idx + 1) % 10` — what if `last_idx` was tampered with in `settings.json` and is ≥ 10 or negative? `% 10` saves us from positive overflow but not from arbitrary garbage in the config.
9. **AboutDialog `setStyleSheet` injection**: line 328 builds a clickable GitHub link with hardcoded URL. No user input flows in. Note in non-findings.

- [ ] **Step 1: Read the region**

Read lines 1-413 of `clipboard_hotkey.py` (use the Read tool with `offset=0, limit=413` or scroll through).

- [ ] **Step 2: List every bare `except:`**

```bash
grep -n "except:" clipboard_hotkey.py
```

For each occurrence in lines 1-413, note whether the suppressed exception could hide a real bug. Add a finding per problematic one (group obvious ones if the pattern is identical, e.g., "icon load fallback at lines 59, 159, 252, 291").

- [ ] **Step 3: Verify pyperclip error handling**

Confirm: is line 199 (`pyperclip.paste()`) inside a try/except? If not, document as **High** — listener thread crashes on locked clipboard, hotkey stops working until app restart.

- [ ] **Step 4: Trace thread access to global popup vars**

Specifically: `show_format_popup` (line 116) reads/writes `current_format_popup`. Who calls it? Is it Qt main thread only, or also the pynput listener? Tracing across the file: `format_popup_request_queue` is the bridge, so popups should be on main thread. Confirm by reading how `handle_hotkey` interacts (it only puts to queue — good). Note in non-findings if clean.

- [ ] **Step 5: Append findings and non-findings**

Continue numbering from Task 3.

- [ ] **Step 6: Do NOT commit.**

---

### Task 5: Audit `clipboard_hotkey.py` — Part 2 (lines 414–783: OUIViewerDialog, OUIDownloadDialog)

**Files:**
- Read: `clipboard_hotkey.py:414-783`
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **`get_all_entries()` memory blow-up**: line 533 calls `oui_db.get_all_entries()` returning ~38,900 tuples. `populate_table` creates 2×N `QTableWidgetItem` objects. Is this acceptable? Measure-or-note memory footprint. Likely fine but note as non-finding if so.
2. **Search filter recomputes on every keystroke** (line 510 `textChanged.connect(self.filter_table)`): with 38,900 rows, filtering rebuilds the entire table each call. Latent perf issue; severity Low — not a bug, but flag if `populate_table` clears+repopulates the QTableWidget on every char.
3. **OUIDownloadDialog `_poll_timer` lifecycle** (lines 678-681, 778-781): timer is stopped in `closeEvent`, but what if `_poll_timer` was never set (constructor exits early)? `hasattr` check exists. Note.
4. **Worker thread orphaning** (line 730): `t = threading.Thread(target=worker, daemon=True)` — daemon thread is killed at process exit; if the user closes the dialog mid-download, what happens? The `worker` keeps pushing to `oui_download_progress_queue`, the dialog is gone, but the daemon thread keeps running with a download. Producer keeps writing to a queue nobody reads. Memory leak bounded by queue size (unbounded queue!). Severity Medium or High depending on impact.
5. **`os.remove` followed by `os.rename`** in `oui_lookup.py` was flagged in Task 3 — confirm again that this dialog has no relevant additional risk.
6. **Error message disclosure**: `self.result_label.setText(msg['message'])` at line 772 — does it ever surface a full traceback or file path that contains a username? IEEE error messages are short, but `str(e)` in `oui_lookup.py:111-116` could include user paths via OSError. Severity Low (info leak in a local app — usually fine but document).
7. **Stylesheet injection**: dark-theme stylesheets at lines 596-628 are static strings. No user input. Note as non-finding for the file.

- [ ] **Step 1: Read the region**

Read lines 414-783 of `clipboard_hotkey.py`.

- [ ] **Step 2: Confirm worker-after-dialog-close behavior**

Specifically trace what happens if the user clicks the system-X on the dialog mid-download. Walk through:
1. Dialog `closeEvent` stops `_poll_timer`.
2. Worker thread keeps running its download loop.
3. Worker calls `progress_callback`, which pushes to `oui_download_progress_queue` — nobody reads it.
4. Worker eventually finishes and pushes `done` or `error` — same.
5. App exit: daemon thread is killed mid-write to disk?

If step 5 can corrupt the OUI file (worker mid-rename when daemon thread is terminated), that's **High**. The atomic-rename pattern partly protects this — confirm.

- [ ] **Step 3: Probe filter performance heuristically**

Read `populate_table` (line 555). Count of `setRowCount(N)` followed by N×2 `setItem` calls. With N=38,900, each keystroke triggers a full rebuild. Document as finding if user-visible (likely is on slower machines). Severity Low — defensive perf improvement, not a bug per se. Per the spec's severity threshold ("real bugs + security only"), this may not qualify; only include if it produces visibly broken UX.

- [ ] **Step 4: Append findings and non-findings**

Continue numbering. Be honest about which items are real bugs vs maintainability.

- [ ] **Step 5: Do NOT commit.**

---

### Task 6: Audit `clipboard_hotkey.py` — Part 3 (lines 784–1055: SettingsDialog)

**Files:**
- Read: `clipboard_hotkey.py:784-1055`
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **Hotkey string validation**: when the user types a new hotkey, is it validated before save? An invalid string written to `settings.json` would crash `pynput` on next startup. Severity High if the app fails to launch. Look for try/except around the parse, or a `validate_hotkey` helper.
2. **Notification duration bounds**: spinbox is supposed to be 1-10s. Is the range enforced in code (`setRange(1, 10)`) or only in the UI label? What if `settings.json` says `notification_duration: -1`? Could break `QTimer.start`.
3. **Autostart registry write**: writing to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` via `winreg`. Path correctness, key cleanup on disable, atomicity. Severity High if path is wrong (orphaned autostart entry).
4. **Settings save flow**: when "Save" is clicked, is `save_settings(settings)` called atomically? If user spams Save, multiple writes overlap?
5. **OUI section** (auto-update toggle, interval, timeout): same kind of validation issues. Interval ≤ 0 days would mean "always stale" — does the auto-updater then spam IEEE on every launch?
6. **Scroll area dark-theme fix referenced in CHANGELOG** ("QGroupBox content no longer clips at borders"): inspect the relevant CSS — is the fix still present, or could a regression be lurking?

- [ ] **Step 1: Read the region**

Read lines 784-1055 of `clipboard_hotkey.py`.

- [ ] **Step 2: Trace hotkey validation specifically**

Find the Save handler. Trace: user types `xyz+abc` (gibberish) → clicks Save → settings written → app needs restart. On next launch, `listen_hotkey` (line 1489) tries to parse `xyz+abc` via pynput. Does it raise? Is there a recovery path? If unrecovered, the app is now broken.

- [ ] **Step 3: Trace autostart toggle**

Find the autostart checkbox handler. Verify:
- Enable: writes a single value to `Run` key with the exe path
- Disable: deletes that value (not the whole key)
- Path: includes quotes if it contains spaces
- Error handling: PermissionError, FileNotFoundError on the registry key itself

- [ ] **Step 4: Append findings and non-findings**

Continue numbering.

- [ ] **Step 5: Do NOT commit.**

---

### Task 7: Audit `clipboard_hotkey.py` — Part 4 (lines 1056–1460: FormatSelectorPopup, VendorPopup)

**Files:**
- Read: `clipboard_hotkey.py:1056-1460`
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **Enter-key listener scope in FormatSelectorPopup**: per CHANGELOG, Enter triggers vendor lookup. Is the listener global (catches Enter anywhere on the system) or scoped to the popup? If global, it'll interfere with user typing in other apps while the popup is open. Severity High if global.
2. **`vendor_lookup_request_queue` consumer**: is it polled? Where? If not, Enter does nothing.
3. **VendorPopup countdown timer**: lifecycle, off-by-one on display ("5...4...3..." or "5...4...3...2...1..."), behavior if user clicks Copy mid-countdown.
4. **`current_vendor_popup` global** (declared at line 103, used here): same multi-thread access concern as Task 4 — but vendor popup is created from Qt main thread? Confirm.
5. **Auto-close vs user interaction**: if the timer fires after the user clicked Copy, do we double-close?
6. **`pyperclip.copy(vendor_name)` failure**: same as Task 4 — wrap or unwrap?

- [ ] **Step 1: Read the region**

Read lines 1056-1460 of `clipboard_hotkey.py`.

- [ ] **Step 2: Specifically locate the Enter-key handler**

The key questions:
- Is it a `QKeyEvent` filter on the popup widget (good — scoped)?
- Or is it a `pynput` listener catching Enter system-wide while the popup is open (bad — interferes with other windows)?

This is one of the higher-impact possible bugs. Be thorough.

- [ ] **Step 3: Append findings and non-findings**

Continue numbering.

- [ ] **Step 4: Do NOT commit.**

---

### Task 8: Audit `clipboard_hotkey.py` — Part 5 (lines 1461–1747: tray_app, listen_hotkey, settings I/O, main)

**Files:**
- Read: `clipboard_hotkey.py:1461-1747`
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **`load_settings` (line 1565) and `save_settings` (line 1581)**: confirm atomic write (temp file + rename), JSON decode error fallback to defaults, missing-key fallback per setting, schema corruption handling.
2. **`listen_hotkey` (line 1489)**: pynput error handling on invalid hotkey string (links to Task 6). Listener thread lifecycle — what stops it on quit?
3. **`tray_app` (line 1461)**: pystray icon setup, menu wiring, fallback if `icon-v1.png` is missing (already partly handled by `create_image`).
4. **`main` (line 1589)**: app lifecycle. `setQuitOnLastWindowClosed(False)` — confirmed per CHANGELOG fix. Bootstrap order: does OUI auto-load block startup? Race between Qt event loop start and hotkey listener thread start?
5. **Single-instance check**: does the app prevent two copies running at once? Two listeners would double-fire the hotkey. If no check, severity Medium.
6. **`oui_status_queue` consumer**: who reads it? If unread, leak.
7. **Exit cleanup**: thread joins, listener stop, queue drain, settings flush.

- [ ] **Step 1: Read the region**

Read lines 1461-1747 of `clipboard_hotkey.py`.

- [ ] **Step 2: Verify settings atomic-write**

Look at `save_settings`. Does it:
1. Write to `settings.json.tmp` first?
2. `os.replace(tmp, settings.json)`?

If it writes directly to `settings.json` with no atomic boundary, a crash mid-write loses all user settings. Severity Medium (settings can be regenerated from defaults, but it's a real bug).

- [ ] **Step 3: Verify single-instance**

```bash
grep -n "instance\|mutex\|lockfile" clipboard_hotkey.py
```

If nothing turns up, two app instances will both register the hotkey and both fire on press, doing two clipboard updates and showing two popups. Document as **Medium** finding — confusing UX but recoverable.

- [ ] **Step 4: Verify hotkey-parse error recovery**

In `listen_hotkey`, what happens if `settings['hotkey']` is bogus? Specifically:
- Does `keyboard.GlobalHotKeys({...})` raise on the bogus string?
- Is it caught and replaced with the default `alt+shift+m`?
- Or does the listener thread die and the app become unresponsive?

This connects to Task 6's finding about validation.

- [ ] **Step 5: Append findings and non-findings**

Continue numbering. This is the last code-audit task.

- [ ] **Step 6: Do NOT commit.**

---

### Task 9: Audit build/distribution files

**Files:**
- Read: `mac-converter.spec`, `installer.iss`, `requirements.txt`
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **`requirements.txt:10-11`**: `PyQt5` listed twice. Documentation hygiene, not a bug per se (pip dedupes). Per spec's severity threshold, this is **not** a finding. Note in non-findings as "intentional or harmless duplicate".
2. **`requirements.txt`**: `keyboard` listed at line 6 but CHANGELOG says it was removed in v2.1.0 ("Switched from keyboard to pynput"). Confirm by `grep -n "import keyboard" *.py`. If unused, it's bloat that ships with the executable (PyInstaller pulls deps in). Severity Low — wasted binary size. Per the severity rubric this may or may not qualify; document only if it indicates dead-code risk.
3. **`mac-converter.spec`**: `hiddenimports=['pynput.keyboard._win32', 'pynput.mouse._win32']`. Are there other PyQt5 or pystray hidden imports needed but missing? PyInstaller has a long history of silently missing imports on Windows. Real bug if the built exe fails to load a module at runtime.
4. **`mac-converter.spec`**: `console=False` is correct for a tray app. `icon='icon-v1.png'` — PyInstaller needs `.ico`, not `.png`, for the Windows exe icon. Severity Medium — exe icon may be missing or wrong. Verify by running `pyinstaller mac-converter.spec` if a venv is available, OR document the concern with the PyInstaller docs reference.
5. **`mac-converter.spec`**: `upx=True` — UPX compression can trigger antivirus false positives. Not a bug, but document if relevant.
6. **`installer.iss:13`**: `AppId={{8F9A3B2C-...}` — fixed GUID is correct for upgrade tracking. Good.
7. **`installer.iss:29`**: `PrivilegesRequired=lowest` — matches the "no admin" design principle. Good.
8. **`installer.iss:43`**: `Source: "icon-v1.png"; DestDir: "{app}"` — the installer copies the icon next to the exe. Good (`get_icon_path()` looks next to the exe in the PyInstaller-bundled case).
9. **`installer.iss:51`**: `Name: "{userstartup}\..."` — autostart entry via Start Menu Startup folder rather than registry. This is **different from** the in-app autostart toggle (registry). If both are set, you get two autostart entries. Document as Medium if confirmed.

- [ ] **Step 1: Read each file**

Read `mac-converter.spec`, `installer.iss`, `requirements.txt`. (Each is short.)

- [ ] **Step 2: Verify icon format for PyInstaller**

```bash
file icon-v1.png 2>/dev/null || python -c "from PIL import Image; img = Image.open('icon-v1.png'); print(img.format, img.size)"
```

Expected output: PNG. Confirm finding: PyInstaller `icon=` argument on Windows expects `.ico`. If a PNG is passed, PyInstaller >5.0 may auto-convert, but older versions silently produce an exe with no icon. Document as Medium with proposed fix: generate an `.ico` and update the spec.

- [ ] **Step 3: Check for `import keyboard` usage**

```bash
grep -rn "import keyboard\|from keyboard" *.py
```

If no hits, the `keyboard` line in `requirements.txt` is dead. Document.

- [ ] **Step 4: Diff installer-startup vs in-app-autostart**

Confirm:
- Installer setup task `startup` creates `{userstartup}\MAC-Converter.lnk` (Startup folder).
- In-app "Start with Windows" writes to registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

If both are enabled, the app launches twice. Document as Medium with proposed fix: in-app toggle should manage the same Startup folder shortcut OR the installer task should be removed in favor of the in-app toggle.

- [ ] **Step 5: Append findings and non-findings**

Continue numbering.

- [ ] **Step 6: Do NOT commit.**

---

### Task 10: Audit environment scripts and `.gitignore`

**Files:**
- Read: `env_load.ps1`, `env_load.sh`, `.gitignore`
- Append findings to: `docs/AUDIT-2026-05-14.md`

**Threat categories to check:**

1. **`env_load.ps1:9`**: literal text `[33m...[0m` — these are ANSI escape sequences but PowerShell `Write-Host` won't interpret the `\u` form. The user sees garbage instead of yellow text. Severity Low (cosmetic) but document.
2. **`env_load.sh:1`**: `#!/bin/zsh` — uses zsh as interpreter, but the documented usage is `source ./env_load.sh` (which uses the current shell, not zsh). Severity Low — shebang is misleading but not actually a bug because `source` ignores it. Optional finding.
3. **`.gitignore:62`**: `.claude/` is ignored — correct.
4. **`.gitignore:66`**: `BUGFIX_SUMMARY.md` — relic from a past one-off summary file. Not a bug.
5. **No tests directory ignored** — `tests/` doesn't exist yet; will be added in Phase 2 if findings need regression tests. Note.

- [ ] **Step 1: Read each file**

- [ ] **Step 2: Append findings and non-findings**

Most likely outcome: 1 low-severity finding (the `` in env_load.ps1) or none. Continue numbering.

- [ ] **Step 3: Do NOT commit.**

---

### Task 11: Cross-check docs vs code

**Files:**
- Read: `README.md`, `CHANGELOG.md`, `TODO.md`, `DEVELOPMENT_LOG.md`, `LICENSE.txt`
- Cross-reference: `mac_formats.py`, `clipboard_hotkey.py`, `installer.iss`
- Append findings to: `docs/AUDIT-2026-05-14.md`

`DEVELOPMENT_LOG.md` is internal session notes and `LICENSE.txt` is the standard MIT license text. Skim both — confirm they don't contain stale technical claims that could mislead a future maintainer, but no deep audit is needed. Mark them as `audited (clean)` in Task 12.

**Threat categories to check (documentation correctness, not prose quality):**

1. **README format claim (lines 32-43)** vs `mac_formats.py:18-19`: README says formats 9-10 are "Windows format alternate" but code emits `Hyphen-6char` (`AABBCC-DDEEFF`). One of them is wrong. This is the mismatch from the original analysis — Severity depends on user-visible impact (does the user paste `AABBCC-DDEEFF` expecting `aa-bb-cc-dd-ee-ff`?). Document as **Medium** for documentation/behavior mismatch.
2. **README version (line 5: 2.3.0)** matches `installer.iss:5` and `AboutDialog` line 304 (`Version 2.3.0`) and `oui_lookup.py:69` (UA). Confirm or note any drift.
3. **README "Last Updated" stamps** in TODO.md (2026-02-17) — not a bug, just data.
4. **TODO.md "Known Limitations" claim** that "Doesn't remember user-selected format between sessions (always resets to 0)" — is this true? `last_format_index` IS saved in `settings.json` (handle_hotkey line 226-227). So the TODO claim is stale. Documentation/code mismatch, but does NOT affect behavior — note as Low or as documentation-only non-finding per severity threshold.

- [ ] **Step 1: Read each doc file**

- [ ] **Step 2: For each numeric/behavioral claim, verify against code**

Open both side by side. Verify in particular:
- The 10 format examples in README — do they all actually match what `convert_mac` returns?
- "No admin rights required" — confirmed by `installer.iss:29 PrivilegesRequired=lowest` and pynput usage.
- "OUI database location" — confirmed by `oui_lookup.py` constructor argument.
- Version strings consistent across files.

- [ ] **Step 3: Append findings and non-findings**

Continue numbering. Per the spec severity threshold, only document doc/code mismatches as findings if they affect user behavior (the README format-9/10 mismatch qualifies; the stale TODO claim does not unless it affects users).

- [ ] **Step 4: Do NOT commit.**

---

### Task 12: Finalize the report

**Files:**
- Modify: `docs/AUDIT-2026-05-14.md`

- [ ] **Step 1: Sort findings by severity**

Within `## Findings`, reorder so all Critical findings appear first, then High, then Medium, then Low. **Do not change the F-numbers** — keep them in discovery order so they're stable references. Just reorder the blocks.

- [ ] **Step 2: Fill in the Summary section**

Replace the placeholder in `## Summary` with:

```markdown
## Summary

- **Total findings:** N
- **Critical:** X | **High:** Y | **Medium:** Z | **Low:** W
- **Files reviewed:** mac_formats.py, oui_lookup.py, clipboard_hotkey.py, mac-converter.spec, installer.iss, requirements.txt, env_load.ps1, env_load.sh, .gitignore, README.md, CHANGELOG.md, TODO.md, DEVELOPMENT_LOG.md, LICENSE.txt
- **Out of scope:** old/ archive directory, icon-v1.png

### Recommended fix priority for Phase 2

1. [Highest-severity finding ID and title]
2. [Next]
3. ... etc.

Fixes can be batched or individual per user direction.
```

- [ ] **Step 3: Fill in the "Files reviewed" section**

List each file with one of: `audited (clean)`, `audited (N findings)`, `out of scope`. Helps the reader audit coverage.

- [ ] **Step 4: Sanity-check the report**

- Every finding has File, What, Why, Proposed fix, Effort.
- No "TBD" or "TODO" left over.
- F-numbers are unique and contiguous.
- Severity tags match the rubric.
- Non-findings cover the threat categories the spec mentioned (TLS, atomic rename, threading, hotkey parsing, clipboard, format conversion, installer privileges, autostart, OUI download).

- [ ] **Step 5: Do NOT commit yet** — Task 13 handles commit.

---

### Task 13: Commit and surface to user

**Files:**
- Stage: `docs/AUDIT-2026-05-14.md`

- [ ] **Step 1: Verify only the audit file is changed**

```bash
git status
```

Expected: one new untracked file `docs/AUDIT-2026-05-14.md`. If any source file is modified, the engineer made a code change in violation of the phase scope — `git diff` it, revert, restart Task 13.

- [ ] **Step 2: Stage the audit**

```bash
git add docs/AUDIT-2026-05-14.md
```

- [ ] **Step 3: Commit**

```bash
git commit -m "$(cat <<'EOF'
docs: add Phase 1 security and bug audit

Read-only audit of all source, build, and documentation files at v2.3.0.
Findings sorted by severity with file:line precision and proposed fixes
per the design spec in docs/superpowers/specs/2026-05-14-full-review-fix-portal-design.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 4: Print summary for the user**

Output a chat-visible summary:

```
Audit complete. <N> findings (<X> critical, <Y> high, <Z> medium, <W> low).
Top 3 to fix:
- F<id>: <title> (file:line)
- F<id>: <title> (file:line)
- F<id>: <title> (file:line)
Full report: docs/AUDIT-2026-05-14.md (commit <hash>).
Ready for Phase 2 — please pick which findings to fix.
```

- [ ] **Step 5: Hand off**

State to the user: Phase 1 is complete. Phase 2 (bug fixes) requires their direction on which findings to implement. Do not proceed to Phase 2 without explicit approval of a fix list.
