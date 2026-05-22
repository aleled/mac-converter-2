# MAC Address Converter — Architecture

This document is the **"how it actually works"** reference. It explains the codebase module by module, the threading model, the data flow between components, the key design decisions and the reasoning behind them, and where things live on disk. The goal is that someone (including future-you) can pick this up cold months from now and understand why the code looks the way it does — and crucially, **what to preserve when fixing or changing something so we don't regress to a previous broken state.**

**Last updated:** 2026-05-15 (v2.4.2)

---

## 1. High-level overview

MAC Address Converter is a single-process Windows tray application. It uses three Python modules and several auxiliary files. The runtime is PyQt5 + pynput + pystray. There is no client/server split, no IPC, and no network dependency other than the IEEE OUI CSV fetch.

```
                  ┌────────────────────────────┐
                  │     Windows desktop        │
                  │  (user's foreground app)   │
                  └────────────┬───────────────┘
                               │ user presses Alt+Shift+M
                               ▼
              ┌────────────────────────────────────┐
              │   pynput GlobalHotKeys listener    │
              │   (own thread, daemon)             │
              └────────────────┬───────────────────┘
                               │ pyperclip.paste()
                               │ mac_formats.detect_mac()
                               │ mac_formats.convert_mac()
                               │ pyperclip.copy(new_format)
                               │ format_popup_request_queue.put(...)
                               ▼
              ┌────────────────────────────────────┐
              │   Qt main thread                   │
              │   QTimer polls request queues      │
              │   creates FormatSelectorPopup      │
              └────────────────┬───────────────────┘
                               │ User presses Enter
                               │ QShortcut / keyPressEvent
                               │ vendor_lookup_request_queue.put(...)
                               ▼
              ┌────────────────────────────────────┐
              │   Qt main thread                   │
              │   QTimer polls vendor queue        │
              │   oui_db.lookup(mac_prefix)        │
              │   creates VendorPopup              │
              └────────────────────────────────────┘
```

The producer (pynput thread) and the consumer (Qt main thread) never touch each other's widgets. They communicate through `queue.Queue` objects. This invariant is critical — violating it leads to crashes that are very hard to reproduce.

---

## 2. Module map

| File | Lines | Role |
|------|-------|------|
| `clipboard_hotkey.py` | ~1850 | Main application: tray icon, hotkey listener, settings I/O, all PyQt5 dialogs, queue plumbing, single-instance mutex, autostart shortcut management, OUI worker lifecycle. |
| `mac_formats.py` | ~55 | Pure-logic MAC address detection and format conversion. No I/O, no Qt, no pynput. Importable in isolation. |
| `oui_lookup.py` | ~270 | IEEE OUI database: download (urllib + atomic replace + content sniff), parse (csv), lookup (dict). Thread-safe. No Qt. |
| `mac-converter.spec` | ~50 | PyInstaller build script. Hidden imports for pystray and pywin32, multi-size `.ico` icon, UPX disabled, console=False (windowed app). |
| `installer.iss` | ~70 | Inno Setup installer script. `PrivilegesRequired=lowest` (no admin), fixed AppId GUID for upgrade tracking, removes settings on uninstall (with confirmation). |
| `requirements.txt` | runtime deps | pystray, Pillow, pyperclip, pynput, PyQt5, pywin32, PyInstaller |
| `requirements-dev.txt` | dev deps | pytest |
| `pytest.ini` | test config | testpaths=tests, addopts=-ra --tb=short |
| `tests/conftest.py` | test fixture | Puts worktree root on sys.path so tests can import mac_formats etc. |
| `tests/test_*.py` | regression tests | 24 tests covering mac_formats regex, oui_lookup download/parse, settings atomic I/O and validation |

### Why this split?

- **`mac_formats.py` is pure** so it's trivially testable with no fixtures or mocks. The regex and the format functions are the kind of code that *must* be exhaustively tested because everything else assumes they're correct.
- **`oui_lookup.py` is self-contained** — it doesn't import Qt or pynput. This means it can be reused in another tool or imported in a script without dragging the full PyQt5 dependency tree. It's also the only module that talks to the network.
- **`clipboard_hotkey.py` carries the integration concerns** — Qt, pynput, pystray, pywin32, settings I/O. It's large (~1850 lines) but it has a single responsibility: be the app. Splitting it further was considered during the Phase 2 audit and left for future work; the file is monolithic because the dialogs share global state (queues, the `oui_db` instance, the `settings` dict, the `tray_icon` reference) and splitting them without introducing a coordinator class would just move the coupling around.

---

## 3. Threading model

Five threads are alive in steady state. Each is named here for clarity even though Python's `threading.Thread` doesn't enforce names.

| Thread | Owner | Lifetime | Touches |
|--------|-------|----------|---------|
| **Main thread (Qt event loop)** | `main()` | Process lifetime | All PyQt5 widgets, all QTimers, all `*_request_queue` consumers. The ONLY thread allowed to touch Qt objects. |
| **pynput hotkey listener** | `listen_hotkey()` started in `tray_app()` | Process lifetime, joined on quit | Reads clipboard via `pyperclip`, calls `mac_formats.detect_mac` and `convert_mac`, writes clipboard, puts to `format_popup_request_queue`. Never touches Qt. |
| **pystray tray icon** | `tray_app()` | Process lifetime, `icon.stop()` on quit | Renders the icon, handles right-click menu. Triggers menu actions which run on this thread; they `*_dialog_request_queue.put()` to hand off to the Qt main thread. |
| **OUI auto-update worker** | spawned by the auto-update logic, optional, daemon | One-shot per startup or scheduled refresh | Calls `oui_lookup.download()` and `oui_lookup.load()`. Reports progress via `oui_download_progress_queue` or `oui_status_queue`. |
| **OUI manual update worker** | `OUIDownloadDialog._start_download` | One-shot per "Update" button click | Same as above, scoped to a single dialog. Honors `cancel_event` on dialog close. |
| **Update-check worker** | spawned by `_start_update_check` 2s after `main()`, daemon | One-shot per launch | Calls `update_check.check_for_update()`. On result, `update_check_queue.put(result)`. Never touches Qt. |

### Invariants

1. **Only the Qt main thread creates, modifies, or destroys QWidget objects.** Worker threads communicate exclusively through `queue.Queue` instances polled by `QTimer`.
2. **`save_settings()` is serialized through `_settings_lock`.** Three different threads write to `settings.json` (hotkey listener via `handle_hotkey`, Qt main via Settings dialog Save, OUI worker after a successful download to record the timestamp). Without the lock and atomic write, the file would tear under contention. The lock is acquired inside `save_settings()` so callers don't need to be aware.
3. **`oui_db.lookup()` is read-only after `oui_db.load()` returns.** Multiple threads can call `lookup()` concurrently; CPython's GIL plus the fact that `_db` is replaced atomically on reload makes this safe.
4. **`exit_event` was removed** in v2.4.0 (F9). Quit is signaled by `icon.stop()`, `app.quit()`, and `listener.stop()` — there's no separate sentinel.

### Why not use `QThread`?

The natural fit for a Qt-friendly worker would be `QThread`, but pynput's listener doesn't compose with `QThread` cleanly — pynput owns its own thread lifecycle, and trying to host its event loop inside `QThread.run()` adds complexity for no win. So we use a plain `threading.Thread` for the listener and a `queue.Queue` + `QTimer` to bridge.

---

## 4. Data flow walkthroughs

### 4.1 Hotkey press → format popup

1. User presses `Alt+Shift+M` (or their configured hotkey).
2. `pynput.keyboard.GlobalHotKeys` running in `listen_hotkey()` matches the chord and calls `handle_hotkey(app)`.
3. `handle_hotkey` runs **on the pynput listener thread**:
   - `pyperclip.paste()` — wrapped in `try/except PyperclipException` (F6 fix). If clipboard is locked (e.g. Snipping Tool is mid-capture), an error message goes into `format_popup_request_queue` and the function returns. The listener thread does NOT die.
   - `mac_formats.detect_mac(text)` — returns the normalized 12-hex-char string, or `None`.
   - If `None`: puts an error request onto the queue and returns.
   - If valid: looks up `settings['last_format_index']`, increments mod 10, looks up the new format string from `mac_formats.convert_mac(mac)`, calls `pyperclip.copy(...)` (also wrapped), updates `settings['last_format_index']`, and `save_settings(settings)`.
   - Puts a `{'type': 'format', 'formats': ..., 'current_index': ..., 'duration': ..., 'mac_normalized': ...}` request onto `format_popup_request_queue`.
4. The Qt main thread's `format_timer` (a `QTimer` firing every 50ms) calls `poll_format_popup()`, which drains the queue.
5. `poll_format_popup()` calls either `show_format_popup(...)` or `show_error_popup(...)`.
6. `show_format_popup()` closes any existing `current_format_popup`, creates a fresh `FormatSelectorPopup`, calls `.show()`, then deferred-calls a focus-grab routine via `QTimer.singleShot(0, _grab_focus)`. The focus grab uses `AttachThreadInput` + `SetForegroundWindow` (v2.4.2 fix — see §6).

### 4.2 Format popup Enter → vendor lookup

1. The format popup is visible. The user presses Enter.
2. Two paths can fire:
   - **`QShortcut`** with `Qt.ApplicationShortcut` context, bound to `Qt.Key_Return` and `Qt.Key_Enter`.
   - **`keyPressEvent`** override on `FormatSelectorPopup` itself, catching `Qt.Key_Return` / `Qt.Key_Enter` when the popup has focus.
   - Whichever fires first calls `_on_enter_pressed()`. The second is a no-op because the popup closes inside the handler.
3. `_on_enter_pressed()`:
   - Returns early if `mac_normalized` isn't set on the popup instance.
   - Returns early if `settings['oui_enabled']` is False.
   - If `oui_db` isn't loaded yet, shows a tray notification ("OUI database is still loading, try again in a moment") and returns. This was added in v2.4.2 so the silent-rejection case is no longer invisible.
   - Otherwise, puts `{'mac_normalized': mac}` onto `vendor_lookup_request_queue` and calls `self.close()`.
4. The Qt main thread's `vendor_timer` (a separate `QTimer`, 50ms) calls `poll_vendor_lookup()`.
5. `poll_vendor_lookup()` calls `oui_db.lookup(mac)` (returns the vendor name string or `None`), reads `settings['oui_vendor_timeout']`, calls `show_vendor_popup(vendor_name, mac, duration_seconds)`.
6. `show_vendor_popup()` creates a `VendorPopup` showing the vendor name (or "Unknown vendor" if `None`), with a countdown timer and a "Copy to Clipboard" button.

### 4.3 OUI database first-run download

1. On `main()` startup, `oui_db = OUIDatabase(SETTINGS_DIR)` is constructed. No I/O happens here.
2. `QTimer.singleShot(0, _start_oui_init)` (F30 fix — defers OUI work one Qt event-loop tick so it doesn't race the event loop start).
3. `_start_oui_init` checks `oui_db.is_stale` (true if the file is missing or older than `oui_update_interval_days`). If stale and auto-update is enabled, spawns a daemon `threading.Thread(target=worker)`.
4. The worker thread calls `oui_db.download(progress_callback=...)`:
   - Connects to `https://standards-oui.ieee.org/oui/oui.csv` via `urllib.request.urlopen` (TLS verification via Python's default `ssl.create_default_context`).
   - Sniffs the Content-Type header. If `text/html` is returned (captive portal, error page), aborts with `(False, "...")` without touching `oui.csv` (F3 fix).
   - Sniffs the first ~200 bytes of the body. If it looks like HTML or XML, same rejection (F3 belt-and-suspenders).
   - Reads chunks, calling `progress_callback` with byte counts.
   - On completion: writes to `oui.csv.tmp`, then `os.replace(tmp, oui.csv)` (atomic on Windows where supported; preserves the prior file on rename failure — F2 fix).
5. The worker then calls `oui_db.load()` to parse the CSV into the in-memory `_db: dict[str, str]` mapping `prefix_uppercase_no_separator` → `vendor_name`. If zero entries are parsed (header-only or corrupt CSV), returns `(False, ...)` (F5 fix).
6. On success, `oui_db._loaded` flips to True and `lookup()` calls start returning real vendor names.

---

## 5. File locations (where things live on the user's machine)

| Path | Purpose | Mode |
|------|---------|------|
| `%APPDATA%\mac-converter-2\settings.json` | User preferences (hotkey, durations, OUI options, last-format-index, autostart flag) | Read on startup, atomic-written on change |
| `%APPDATA%\mac-converter-2\oui.csv` | IEEE OUI database (~3.5 MB) | Downloaded weekly (configurable), atomic-replaced |
| `%APPDATA%\mac-converter-2\settings.json.corrupt-<unix-ts>` | Renamed copy of a corrupt `settings.json` | Created automatically when load fails (F24 fix) |
| `%APPDATA%\mac-converter-2\oui.csv.tmp` | Temp file during download | Created during download, replaced into place; left behind only if the process is killed mid-replace |
| `%APPDATA%\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk` | Autostart shortcut (when enabled) | Created/removed by the in-app "Start with Windows" toggle (F13 + F31 fix) |
| `%PROGRAMFILES%\MAC-Converter\MAC-Converter.exe` | Installed executable | Created by the installer |

The app **never writes anywhere else** — no registry writes, no temp files outside `%APPDATA%`, no Documents folder modifications.

---

## 6. Key design decisions (why things are the way they are)

This section records the **rationale** for design choices that aren't obvious from reading the code. If you're about to "fix" one of these, please understand the original constraint first.

### 6.1 No admin rights, ever

The app uses **pynput** (not the `keyboard` package) for global hotkey registration. `pynput.keyboard.GlobalHotKeys` uses a `WH_KEYBOARD_LL` low-level Win32 hook installed via `SetWindowsHookEx`, which works without elevation. The older `keyboard` package required SeDebugPrivilege on Windows — which means admin rights — and was dropped in v2.1.0.

`installer.iss` declares `PrivilegesRequired=lowest`. The installer installs into `{autopf}` (which expands to `%LOCALAPPDATA%\Programs\MAC-Converter` for unprivileged users), not `Program Files`. Autostart is via a Startup-folder shortcut in `%APPDATA%` (no registry, no admin).

**Why this matters:** removing the no-admin constraint would let users install into `Program Files` and write registry autostart, but it would also make the app refuse to launch on locked-down corporate machines. Many users specifically chose this app because it doesn't need elevation.

### 6.2 Tool-window popups + manual focus grab

The format popup and vendor popup use `Qt.Tool` window flag so they don't appear in the taskbar (they're transient). However, `Qt.Tool` windows on Windows don't take keyboard focus by default — and Windows' foreground-steal prevention blocks `SetForegroundWindow` calls from a process that didn't receive the last input event.

Pre-v2.4.0 this was masked by a global `pynput.keyboard.Listener` that caught Enter system-wide. That listener was removed in v2.4.0 (F19) because it received every keystroke in every app — an unnecessary architectural privacy concern.

The v2.4.2 fix layers three mechanisms:

1. **`Qt.StrongFocus`** on the popup so `setFocus()` works (default `QDialog.focusPolicy()` is `Qt.NoFocus`, so without this, focus calls were silent no-ops).
2. **`AttachThreadInput` trick** in `show_format_popup` to satisfy Windows' foreground-steal rules. The converter's thread is temporarily merged with the foreground app's thread, `SetForegroundWindow` succeeds, then the threads are detached. Wrapped in try/except so non-Windows platforms (untested but possible) don't crash.
3. **`Qt.ApplicationShortcut` + `keyPressEvent`** double-handling on the popup itself. If focus reaches the popup, `keyPressEvent` fires. If only the app is active but the popup widget isn't focused, the application-level shortcut still fires.

**Don't try to "simplify" by removing one of these layers without understanding the failure modes** — see CHANGELOG `[2.4.1]` and `[2.4.2]` for what went wrong when only some of the layers were in place.

### 6.3 Atomic file writes + lock for settings

All `settings.json` writes go through `save_settings()`, which acquires `_settings_lock` (module-level `threading.Lock`) and calls `_atomic_write_json(path, data)`. The helper writes to `path.tmp` and calls `os.replace(tmp, path)`, which is atomic on Windows where the underlying filesystem supports it.

Three threads write settings: the pynput hotkey listener (updates `last_format_index` on every hotkey press), the Qt main thread (Settings dialog Save handler), and the OUI auto-update worker (records `oui_last_downloaded` after successful download). Without the lock, these would interleave and produce a torn JSON file. Without atomic write, a power loss or kill -9 mid-write would corrupt the file. Both happened often enough in pre-v2.4.0 versions that the audit (F7, F16, F23, F28) wrapped them all together.

`load_settings()` is the mirror: if it can't parse `settings.json`, it renames the file to `settings.json.corrupt-<unix-ts>` (so the user can recover) and returns `DEFAULT_SETTINGS`. Without this, a single corrupt file silently lost every user preference forever.

### 6.4 Single-instance via Win32 named mutex

`acquire_single_instance_mutex()` calls `win32event.CreateMutex(None, False, "Global\\MAC-Converter-2-SingleInstance")` at `main()` entry. If `GetLastError()` returns `ERROR_ALREADY_EXISTS`, another instance is already running and the second copy shows a QMessageBox and exits. The handle is stored in a module-level global `_single_instance_mutex_handle` so Windows keeps it alive for the process lifetime.

**Why "Global\\"?** Local mutexes are per-session. The Global namespace catches cross-session double-launches (e.g., RDP into the same machine where the app is already running). For a tray app, this is the safer choice.

**Why not skip the check if pywin32 isn't importable?** `acquire_single_instance_mutex()` returns True (allow-all) on `ImportError`. The app still works without single-instance protection if pywin32 is missing — degraded but functional. This is intentional graceful degradation.

### 6.5 OUI download HTML rejection

The IEEE CSV is ~3.5 MB. A pre-v2.4.0 download path had only a 1000-byte minimum size check. A captive-portal HTML page (typically 2–10 KB) easily slipped past, replaced the live `oui.csv` with HTML, and the next `load()` call returned (True, 0) silently — the database appeared "loaded" but had no entries.

v2.4.0's `download()` adds two layers of HTML detection:

1. **Content-Type header check** — if it contains `html`, reject before reading the body.
2. **First-chunk magic-byte sniff** — if the first 200 bytes start with `<!doctype`, `<html`, or `<?xml`, reject.

Plus `load()` now returns `(False, "...")` if the parsed dict is empty (F5).

### 6.6 OUI worker cooperative shutdown

The OUI download worker is `daemon=True`. Daemon threads are forcibly killed at process exit, which is fine for most workloads but **dangerous mid-`os.replace`**: if the OS partially completes the rename and then the thread dies, the live `oui.csv` could be missing or partial.

v2.4.0 added a `cancel_event: threading.Event` parameter to `download()`. The worker checks it between chunks. `OUIDownloadDialog.closeEvent` sets it and `join(timeout=2.0)`s the worker, then drains `oui_download_progress_queue` so stale messages don't leak into a future dialog. `on_quit` also sleeps briefly if `_oui_download_in_progress` is set, giving the worker a chance to finish before the process dies.

This is best-effort — a hard process kill (Task Manager → End Task) still risks corruption, but the F2 atomic-replace pattern minimizes the window.

### 6.7 Autostart via Startup-folder shortcut, not registry

Two natural choices existed for "Start with Windows":

- **Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`** — quick `winreg` calls, no admin needed. But it feels heavier than necessary and users sometimes object to registry autostart.
- **Startup-folder `.lnk`** — `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk`. The installer was already creating this entry via Inno Setup's `{userstartup}\...` icon entry. Two mechanisms = potential conflict (F31).

v2.4.0 chose the Startup-folder shortcut as the single source of truth. `set_autostart_enabled(True)` calls `WScript.Shell.CreateShortcut(...)` via `pywin32`'s COM dispatch and writes the `.lnk`. The installer's `[Tasks] startup` entry was removed so there's only one place the shortcut comes from.

**Don't reintroduce both mechanisms** without a deliberate plan — F31 was specifically about avoiding that footgun.

### 6.8 Update check opens the portal instead of auto-downloading

The startup update prompt's "Upgrade" button opens the GitHub Pages download portal in the user's default browser, then calls `on_quit` to exit the running app. It does **not** download the installer itself.

Why: the user's browser uses Windows' certificate store natively and handles corporate TLS-intercepting proxies (Zscaler, FortiGate, etc.) fine — the same reason we recommended manual browser downloads as the OUI fallback before v2.4.3's truststore work. Auto-downloading the installer from inside the app would re-introduce a class of failures (partial downloads, AV interception of the temp .exe, rate limits, retry logic) that the existing Inno Setup installer-over-running-exe pattern already handles cleanly when the user starts from a freshly-downloaded `.exe`.

The trade-off is one extra click for the user (download → run installer) in exchange for substantially less code surface inside our app and zero compatibility complications with whatever endpoint security is in place. If user feedback shows that the extra click is friction, the auto-download path can be added in a future version on top of the existing infrastructure (a `urllib` GET to the asset URL, a `subprocess.Popen` of the downloaded exe, exit) — but ship the simple version first.

### 6.9 Qt.ApplicationShortcut > Qt.WidgetWithChildrenShortcut

For the format popup's Enter key handling, the natural Qt choice is `Qt.WidgetWithChildrenShortcut` (the shortcut fires only when the widget or a child has focus — properly scoped to this popup). But `QDialog` defaults to `Qt.NoFocus` policy, so the dialog itself can't have focus, and the dialog has no focusable child widgets (labels are not focusable by default). The shortcut just never fires.

Setting `Qt.StrongFocus` solves the policy issue. `Qt.ApplicationShortcut` solves the "any app window is active" case as a fallback — this is wider than ideal but safe because the only shortcut bound this way is on the format popup, which is short-lived.

### 6.10 Single monolithic clipboard_hotkey.py

The file is ~1850 lines. Splitting it has been considered. The arguments for splitting are:

- Easier to navigate
- Smaller files are easier for code review
- Easier to test pieces in isolation

The arguments against:

- All the dialogs share global state — `settings`, `oui_db`, `tray_icon`, the queues. Splitting them requires either (a) passing state explicitly through constructors, which is verbose and brittle, or (b) introducing a coordinator object, which is a substantial refactor.
- The audit (F-coded findings) was conducted in this layout. Splitting would invalidate the file:line precision of the audit report.
- A monolithic file is easier to grep across.

**The current decision:** leave it monolithic. If future feature work makes the file unworkable, the right refactor is to introduce a small `AppContext` class that owns `settings`, `oui_db`, `tray_icon`, and the queues, then move each dialog into its own file with `AppContext` injected. Don't split without that scaffolding.

---

## 7. Build system

PyInstaller (one-folder mode disabled — single-file exe) builds `dist/MAC-Converter.exe`. The spec file lists explicit `hiddenimports` for `pynput.keyboard._win32`, `pynput.mouse._win32`, `pystray._win32`, and the pywin32 modules used by autostart / single-instance (F33). UPX is disabled (F34) to reduce antivirus false positives — the resulting binary is ~30% larger but ships to many more endpoints without SmartScreen complaints.

Inno Setup wraps `dist/MAC-Converter.exe` plus `icon-v1.png`, `README.md`, and `LICENSE.txt` into `installer-output/MAC-Converter-Setup-vX.Y.Z.exe`. The installer uses `PrivilegesRequired=lowest` and a fixed AppId GUID (`{{8F9A3B2C-1D4E-5F6A-7B8C-9D0E1F2A3B4C}`) so subsequent versions upgrade in place rather than installing alongside.

The `.ico` icon is generated from `icon-v1.png` via Pillow (`Image.open(...).save('icon-v1.ico', sizes=[...])`) — see `BUILDING.md` for the command. PyInstaller embeds the multi-size .ico into the exe so Windows Explorer and the taskbar show the icon at every resolution.

See [`BUILDING.md`](BUILDING.md) for the detailed step-by-step.

---

## 8. Test architecture

Tests live in `tests/` and are run with `python -m pytest`. The suite covers **pure-logic** surfaces only:

- `test_mac_formats.py` — regex correctness, format conversion correctness, parametrized happy-path and rejection cases.
- `test_oui_lookup.py` — atomic replace failure preservation, HTML response rejection, zero-entry parse rejection (uses `unittest.mock` to fake `urlopen`).
- `test_settings_atomic.py` — atomic write under simulated crash.
- `test_settings_validate.py` — `_validate_settings` coercion / clamping; corrupt-JSON renaming; missing-file fallback.

**What's NOT tested:** anything that requires a running QApplication. PyQt5 widget testing on Windows in CI is a separate engineering project. UI fixes are verified manually before release — see `CONTRIBUTING.md` § Testing guidance.

The full suite is 24 tests today and runs in <1 second. Adding more pure-logic tests is encouraged; adding UI tests requires deciding on a test framework (probably `pytest-qt`) first.

---

## 9. Security boundaries

See [`SECURITY.md`](SECURITY.md) for the full threat model and disclosure policy. Quick recap:

- The app runs as the current user. No elevation, ever.
- Network I/O is HTTPS-only to `standards-oui.ieee.org`. TLS certificates are verified via Python's default context.
- Filesystem I/O is limited to `%APPDATA%\mac-converter-2\` and the user's Startup folder.
- No clipboard data is persisted to disk beyond the immediate copy-back.
- No telemetry, no analytics, no third-party servers other than IEEE.

The pynput hotkey is the only Win32 hook the app installs. The pre-v2.4.0 format-popup Enter listener (a second, system-wide pynput keyboard listener) was removed in F19 — that's an important architectural property: **the only keyboard hook today catches a specific configurable chord, not every keystroke.**

---

## 10. Known limitations and tradeoffs

- **Windows-only in practice.** macOS and Linux paths exist (pynput works on those platforms) but the autostart shortcut, single-instance mutex, and `SetForegroundWindow` calls are all Win32-specific. Cross-platform support would require platform-detection in `set_autostart_enabled`, `acquire_single_instance_mutex`, and `show_format_popup`'s focus grab.
- **No code signing.** The exe and installer are unsigned. Windows SmartScreen may warn on first run. UPX is disabled to reduce false positives but signing is the proper fix; it's out of scope for this open-source project.
- **OUI lookup is best-effort.** The IEEE database doesn't include every vendor (MA-S and MA-M smaller allocations aren't in `oui.csv`), and some MAC prefixes are reserved or private. Lookups for those return `None` and the vendor popup shows "Unknown vendor".
- **No batch processing.** One MAC per hotkey press. Batch conversion is on the v2.5.0+ roadmap.
- **Settings changes that require restart:** hotkey changes only. All other settings take effect immediately. This is enforced by re-reading `settings` from the running dict — not by re-reading the file. The hotkey is bound once at listener startup and can't be rebound without restarting the listener thread.

---

## 11. Glossary

- **OUI** — Organizationally Unique Identifier. The first 3 octets (24 bits) of a MAC address identify the manufacturer. IEEE assigns these.
- **MA-L / MA-M / MA-S** — IEEE's three OUI block sizes (Large, Medium, Small). Only MA-L is in the free `oui.csv` we use.
- **Tool window (`Qt.Tool`)** — A Qt window flag. Indicates a transient secondary window — no taskbar entry, smaller-than-normal decoration. On Windows, also affects activation semantics (the cause of the v2.4.0–v2.4.2 focus saga).
- **Foreground-steal** — Microsoft's term for one process taking the foreground window away from another. Restricted by Windows for usability and security; the standard workaround for legitimate cases is `AttachThreadInput`.
- **F-IDs (F1, F2, ...)** — Audit finding IDs from `docs/AUDIT-2026-05-14.md`. Referenced throughout the CHANGELOG and the v2.4.0 commits.
- **Atomic write** — Write to `path.tmp`, then `os.replace(tmp, path)`. The replace is atomic on most filesystems, so observers see either the old file or the new file, never a partial.

---

## 12. Where to look when something breaks

| Symptom | Start here |
|---------|------------|
| Hotkey not firing | `listen_hotkey()` in `clipboard_hotkey.py`; check `settings['hotkey']`; verify pynput is installed and not blocked by AV. See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md). |
| Format popup appears but Enter does nothing | The focus saga. See §6.2 above and CHANGELOG `[2.4.2]`. Check whether `Qt.StrongFocus` is still set, whether `AttachThreadInput` is being called, whether `QShortcut` context is still `Qt.ApplicationShortcut`. |
| Settings keep resetting | Check whether `_atomic_write_json` is being used; check `_settings_lock`; see if `settings.json.corrupt-*` files appear in `%APPDATA%\mac-converter-2\` (indicates JSON corruption). |
| OUI lookup returns no vendor | Either the database isn't loaded (`oui_db.is_loaded` is False — try the Update button in Settings) or the prefix isn't in IEEE's MA-L list. Confirm by opening `oui.csv` and grepping for the prefix. |
| Autostart doesn't survive reboot | Check that `%APPDATA%\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk` exists. If not, the Settings dialog `set_autostart_enabled(True)` call failed — likely pywin32 issue. |
| App won't launch (single-instance check) | Look for an orphan `MAC-Converter.exe` process in Task Manager. The mutex is released on process exit; if the process is gone but the mutex isn't, restart Windows. |
| App launches but immediately exits | Likely a `settings.json` corruption that the rename-and-fallback didn't catch. Move `%APPDATA%\mac-converter-2\settings.json` aside and relaunch — defaults will load. |
| Update prompt doesn't appear | Either there's no newer release on GitHub, or the network request failed silently. Check stderr for `[update_check]` messages. Verify `update_check_queue` is being drained by `_update_timer` (is the timer running and connected?). |

See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for the full user-facing troubleshooting guide.

---

## 13. Reference documents

- [`README.md`](README.md) — user-facing features and quick-start
- [`CHANGELOG.md`](CHANGELOG.md) — version-by-version changes
- [`SECURITY.md`](SECURITY.md) — vulnerability disclosure
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — contributor workflow
- [`BUILDING.md`](BUILDING.md) — build instructions
- [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) — user-facing troubleshooting
- [`TODO.md`](TODO.md) — roadmap and milestones
- [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md) — session-by-session notes
- [`docs/AUDIT-2026-05-14.md`](docs/AUDIT-2026-05-14.md) — security and bug audit (37 findings)
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — design specifications
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — implementation plans
