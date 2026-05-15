# MAC Address Converter

A lightweight Windows system tray utility for converting MAC addresses between different formats with a global hotkey, auto-cycling format selection, and clipboard integration.

**Current Version:** 2.4.2
**Status:** Production-ready ✅
**License:** MIT
**Author:** Alejandro Lichtenfeld

### 📥 Download

**[https://aleled.github.io/mac-converter-2/](https://aleled.github.io/mac-converter-2/)** — one-click installer for Windows. The download portal auto-points at the latest release.

Direct links to the latest version:
- **[MAC-Converter-Setup-v2.4.2.exe](https://github.com/aleled/mac-converter-2/releases/download/v2.4.2/MAC-Converter-Setup-v2.4.2.exe)** — Windows installer (~54 MB)
- **[MAC-Converter.exe](https://github.com/aleled/mac-converter-2/releases/download/v2.4.2/MAC-Converter.exe)** — Standalone executable (~51 MB)

---

## What's new

### 2.4.2 (2026-05-15) — Enter-to-vendor-lookup actually fixed

v2.4.1's first attempt at restoring the Enter key didn't fully solve the focus regression introduced by v2.4.0. v2.4.2 layers three mechanisms that together make the popup reliably receive keyboard focus on Windows: `Qt.StrongFocus` policy on the dialog, the `AttachThreadInput` trick to satisfy Windows' foreground-steal rules, and `Qt.ApplicationShortcut` plus a `keyPressEvent` override as belt-and-suspenders. The architectural improvement of v2.4.0 — no system-wide keystroke capture — is preserved.

### 2.4.1 (2026-05-15) — first focus-grab attempt (superseded)

Attempted to fix the Enter regression by calling `activateWindow()`, `setFocus()`, and `SetForegroundWindow`. Insufficient — see v2.4.2.

### 2.4.0 (2026-05-14) — Bug-fix release: 37 audit findings closed

A focused bug-fix release closing **37 audit findings** (5 high, 12 medium, 20 low) from a full security and correctness review of the codebase. Highlights:

- 🛡️ **Locked clipboard no longer crashes the hotkey listener.** All `pyperclip` calls are wrapped — clipboard contention from Snipping Tool / RDP / etc. is now a recoverable notification rather than a silent death.
- 🔒 **No more system-wide keyboard hook.** The format popup's Enter key was previously detected via a global pynput listener that received every keystroke (including passwords in other apps). It now uses a Qt-scoped `QShortcut`.
- ✅ **"Start with Windows" actually works now.** The checkbox was previously cosmetic; it now creates/removes a real shortcut in the Startup folder.
- 🚫 **Single-instance check.** Launching a second copy shows a notification and exits cleanly — no more double-hotkey-fire or settings races.
- 🔐 **Atomic settings & OUI writes.** Crashes mid-write no longer corrupt your configuration. Corrupt `settings.json` is renamed aside (not silently obliterated) so you can recover hand edits.
- 🌐 **OUI download hardening.** Rejects HTML / captive-portal responses before they can overwrite the live database; cooperative shutdown of the download worker; preserves the prior database on rename failure.
- 🎨 **Real `.ico` icon** (7 sizes) for the Windows executable; UPX disabled to reduce antivirus false positives.
- ✏️ **Hotkey input is validated on Save** — gibberish is rejected with an inline error instead of being silently replaced by the default on next launch.

See [`CHANGELOG.md`](CHANGELOG.md) for the full per-finding list and [`docs/AUDIT-2026-05-14.md`](docs/AUDIT-2026-05-14.md) for the audit report.

---

## Features

### System tray utility

Runs in the background with a custom icon in the Windows system tray. The app is **not** a window — there's no taskbar entry while it's running. The tray icon is the only persistent UI surface. Right-click it for Settings, About, and Quit.

### Auto-cycling format conversion

Press the configured hotkey while a MAC address is on the clipboard. The app:

1. Reads the clipboard
2. Detects whether it's a valid MAC address (handles colon, hyphen, dot, plain-12-hex, and 6-6-hyphen variants)
3. Cycles to the **next** format from the list of 10 (modulo wraps, so format 9 → format 0)
4. Writes the new format back to the clipboard
5. Shows a popup with the converted MAC and a hint that you can press Enter for vendor lookup

The "last format index" is persisted in `settings.json`, so the cycle is **resumed** across app restarts — if you ended on dot-separated lowercase before restarting, the next press starts at the format after that.

### Global hotkey

Default: `Alt+Shift+M`. Configurable in Settings. Uses `pynput.keyboard.GlobalHotKeys` — a low-level Win32 hook that works **without admin rights**. The hotkey is bound at startup; changes require an app restart (the only setting with that limitation).

Invalid hotkeys are caught on Save (since v2.4.0) — you get an inline error label and the bad value isn't persisted. If you somehow get a corrupt hotkey into `settings.json` (e.g. hand-edit), the listener falls back to the default at launch rather than refusing to start.

### Automatic clipboard management

The converted MAC is **automatically** copied back to the clipboard. No manual "Copy" step needed. Just press the hotkey, then paste wherever you needed the new format.

Clipboard errors (e.g. when another app has the clipboard locked, like Snipping Tool mid-capture) are handled gracefully — a notification surfaces "Clipboard busy, try again" instead of silently killing the listener thread. This was fixed in v2.4.0 (audit finding F6).

### Format popup with Enter-for-vendor

The popup that appears after pressing the hotkey:

- Shows the converted MAC in bold at the top
- Lists all 10 formats — **click any** to copy that variant instead
- Includes a hint "Press Enter for vendor lookup" if the OUI database is loaded
- Auto-closes after the configured duration (default 3 seconds, 1–10 configurable)
- Closes immediately on `Escape` or `Enter` (Enter triggers the vendor lookup)
- Replaces any previous popup if you press the hotkey again (no popup pile-up)

The popup is a tool-style window (no taskbar entry) positioned in the bottom-right near the system tray.

### OUI vendor lookup

After the format popup appears, **press Enter** to look up the MAC address's manufacturer using the IEEE OUI (Organizationally Unique Identifier) database. A second popup appears showing:

- The vendor name (e.g. "Cisco Systems", "Xerox Corporation", "Apple, Inc.")
- The MAC address you queried
- A countdown timer
- A "Copy to Clipboard" button — pressing it copies the **vendor name** to the clipboard (replacing the MAC you had there); cancel by letting the popup auto-close, which preserves the MAC

The database contains ~38,900 MA-L (Large block) OUI assignments. Smaller blocks (MA-M, MA-S) are not in the free CSV and will return "Unknown vendor" — see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for context.

### OUI database management

- **Auto-update:** the database is re-downloaded weekly by default (configurable in Settings). The download happens in a background thread; the app remains responsive.
- **Manual update:** Settings dialog → "Update OUI database now" button. A progress dialog shows the percentage and MB downloaded in real time. You can close the dialog mid-download to cancel safely (since v2.4.0 — cooperative shutdown, audit finding F11).
- **Database viewer:** Settings dialog → "View OUI database" button. A searchable read-only table of all entries. Filter by prefix or vendor name.
- **Source:** [`https://standards-oui.ieee.org/oui/oui.csv`](https://standards-oui.ieee.org/oui/oui.csv) — Python `urllib` with TLS verification. Rejects HTML / captive-portal responses (audit finding F3).
- **Storage:** `%APPDATA%\mac-converter-2\oui.csv` (about 3.5 MB).

### Dark theme UI

All dialogs (Settings, About, format popup, vendor popup, OUI viewer, OUI download progress) use a unified dark theme: `#2b2b2b` background, `#0078d4` accent (Microsoft Fluent blue), `#e0e0e0` body text, monospace code fonts (`Courier New`) for MAC addresses and OUI prefixes.

There's no light-theme toggle — the design is dark-only by deliberate choice. Adding a light theme is on the v2.5.0+ roadmap.

### Settings dialog

Right-click tray icon → **Settings**. Wrapped in a scroll area so all sections fit on small screens. Sections:

- **Hotkey:** text input with inline validation (red label on parse failure)
- **Notifications:** spinbox 1–10 seconds for popup display duration
- **Startup:** "Start with Windows" checkbox — toggles a `.lnk` in `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\` (single source of truth; the installer does not add its own shortcut)
- **OUI Vendor Lookup:** enable/disable, auto-update toggle, update interval (1–365 days), vendor popup timeout (1–60 seconds), "Update OUI database now" button, "View OUI database" button

Save persists everything atomically (audit finding F7).

### About dialog

Right-click tray icon → **About**. Shows:

- App icon (centered, 64×64)
- App name and version
- Author
- Copyright year and license
- Clickable GitHub link
- OUI database statistics: entry count, unique vendor count, file size, last-modified timestamp, last-downloaded timestamp, source URL, on-disk location

### Persistent settings

Everything you configure persists across app restarts in `%APPDATA%\mac-converter-2\settings.json` — a small human-readable JSON file. You can back it up, hand-edit it, or sync it across machines (be aware that the autostart `.lnk` is per-machine and won't sync).

Settings writes are **atomic** (temp file + `os.replace`) and **locked** (three threads can write concurrently; only one wins per write). Corrupt files are renamed to `settings.json.corrupt-<unix-ts>` rather than silently overwritten.

### No admin rights required

The app uses `pynput` for hotkey registration (low-level Win32 hook, works without elevation), writes settings to `%APPDATA%` (user-writable), creates the autostart shortcut in the user's Startup folder (no registry, no admin). The installer declares `PrivilegesRequired=lowest` and installs into `%LOCALAPPDATA%\Programs\MAC-Converter\` for non-admin users.

### Single-instance enforcement

Launching a second copy of the app shows "MAC Converter is already running" and exits cleanly. Uses a Win32 named mutex (`Global\MAC-Converter-2-SingleInstance`) — works across RDP sessions too. Prevents the double-hotkey-fire and `settings.json` race that v2.3.0 and earlier could exhibit.

### 24 pytest regression tests

Pure-logic surfaces (`mac_formats.py`, `oui_lookup.py`, settings I/O) are covered by 24 automated tests. They run in under a second and are green on every commit. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`tests/`](tests/) for the suite.

UI behavior is verified manually before each release — PyQt5 widget tests would require significant extra scaffolding (probably `pytest-qt`) that isn't in scope today.

---

## Supported MAC Address Formats

The app cycles through 10 formats:

1. Colon-separated uppercase: `AA:BB:CC:DD:EE:FF`
2. Colon-separated lowercase: `aa:bb:cc:dd:ee:ff`
3. Hyphen-separated uppercase: `AA-BB-CC-DD-EE-FF`
4. Hyphen-separated lowercase: `aa-bb-cc-dd-ee-ff`
5. Dot-separated uppercase: `AABB.CCDD.EEFF`
6. Dot-separated lowercase: `aabb.ccdd.eeff`
7. Plain uppercase: `AABBCCDDEEFF`
8. Plain lowercase: `aabbccddeeff`
9. Hyphen-6char uppercase (Cisco-style): `AABBCC-DDEEFF`
10. Hyphen-6char lowercase (Cisco-style): `aabbcc-ddeeff`

---

## Installation

### Option 1: Windows Installer (Recommended)

1. Go to **[https://aleled.github.io/mac-converter-2/](https://aleled.github.io/mac-converter-2/)** and click **Download for Windows**, OR grab `MAC-Converter-Setup-v2.4.0.exe` directly from the [Releases page](https://github.com/aleled/mac-converter-2/releases/latest)
2. Run the installer and follow the wizard
3. Choose optional features:
   - Desktop shortcut
   - Start with Windows (autostart — managed entirely by the app via a Startup-folder shortcut, no registry writes)
4. App launches automatically after installation
5. No admin rights required

### Option 2: Standalone Executable

1. Download `MAC-Converter.exe` from the [Releases page](https://github.com/aleled/mac-converter-2/releases/latest)
2. Run the executable directly
3. App will reside in system tray

### Option 3: Run from Source (Development)

1. Clone the repository:
   ```bash
   git clone https://github.com/aleled/mac-converter-2.git
   cd mac-converter-2
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the app:
   ```bash
   python clipboard_hotkey.py
   ```

---

## Usage

1. **Start the App**: Run the executable or installer
2. **Minimize to Tray**: App runs in system tray (appears as icon in taskbar)
3. **Copy MAC Address**: Copy a MAC address to clipboard
4. **Press Hotkey**: Press Alt+Shift+M (or your configured hotkey)
5. **See Result**: A notification popup appears showing the converted MAC address
6. **Paste**: The converted MAC is automatically in clipboard - paste anywhere

### Notification Behavior

- **Valid MAC Address**: Shows converted format in tray notification for configured duration (default 3 seconds)
- **Invalid MAC Address**: Shows error message "No valid MAC address in clipboard"
- **Rapid Presses**: Each hotkey press instantly replaces the previous notification

### OUI Vendor Lookup

1. Press hotkey with a MAC address in clipboard - format popup appears
2. Press **Enter** to look up the manufacturer (OUI vendor)
3. Vendor popup appears showing the manufacturer name with a countdown timer
4. Click **Copy to Clipboard** to copy the vendor name, or let it auto-close
5. If the popup auto-closes, your clipboard still contains the converted MAC address

The OUI database is downloaded automatically from IEEE on first run and auto-updates weekly (configurable).

### Accessing Menus

Right-click the tray icon to access:
- **Settings**: Configure hotkey, notification duration, autostart option
- **About**: View app information, version, license, and GitHub link
- **Quit**: Close the application

---

## Configuration

### Settings file location

`%APPDATA%\mac-converter-2\settings.json`

The app reads this file on startup and writes it whenever you save in the Settings dialog or whenever an internal value changes (e.g. `last_format_index` is bumped on every hotkey press). The file is human-readable JSON and can be hand-edited — just close the app first so your edit isn't immediately overwritten.

### Default settings

```json
{
  "hotkey": "alt+shift+m",
  "notification_duration": 3,
  "autostart": false,
  "last_format_index": 0,
  "oui_enabled": true,
  "oui_auto_update": true,
  "oui_update_interval_days": 7,
  "oui_vendor_timeout": 5
}
```

### Per-setting reference

| Key | Type | Valid range | Default | Description | Takes effect |
|-----|------|-------------|---------|-------------|--------------|
| `hotkey` | string | `<modifier>+<modifier>+<key>` parseable by pynput | `"alt+shift+m"` | The global hotkey that triggers MAC conversion | On app restart |
| `notification_duration` | int | 1–10 | `3` | Seconds the format popup stays visible before auto-closing | Immediate |
| `autostart` | bool | true / false | `false` | Whether the Startup-folder shortcut exists. Reading this is **derived from the filesystem** — the JSON value is just a cache. | Immediate |
| `last_format_index` | int | 0–9 | `0` | Index into the format list. Bumped on every hotkey press. Persisted so cycling resumes across app restarts. | Read on each hotkey press |
| `oui_enabled` | bool | true / false | `true` | Whether the "Press Enter for vendor lookup" hint and Enter-key handler are active | Immediate |
| `oui_auto_update` | bool | true / false | `true` | Whether to auto-download a fresh OUI database when the existing file is older than `oui_update_interval_days` | On next app start |
| `oui_update_interval_days` | int | 1–365 | `7` | How old `oui.csv` must be before it's considered stale | On next app start |
| `oui_vendor_timeout` | int | 1–60 | `5` | Seconds the vendor popup countdown runs before auto-closing | Immediate |
| `oui_last_downloaded` | string (ISO timestamp) or null | — | `null` | When the OUI database was last successfully downloaded. Used for display in the About dialog. | (Read-only display) |

All values are validated on load (since v2.4.0 — audit findings F8, F15, F24). If the JSON is corrupt or a key has a wrong type/range, the file is renamed aside to `settings.json.corrupt-<unix-ts>` and defaults are loaded.

### Changing settings via the dialog

1. Right-click tray icon → **Settings**
2. Edit any field. Spinboxes enforce ranges; the hotkey field is validated on Save.
3. Click **Save**. Settings are written atomically.
4. Hotkey changes require an app restart (right-click tray → Quit, then relaunch). All other settings take effect immediately.

### Hotkey format

`<modifier>+<modifier>+<key>` — modifiers separated by `+`, ending with a key.

Examples:
- `alt+shift+m` (default)
- `ctrl+shift+c`
- `alt+m`
- `ctrl+shift+x`
- `ctrl+alt+shift+v`

Special key tokens you can use: `alt`, `ctrl`, `shift`, `cmd`, `tab`, `enter`, `space`, `delete`, `backspace`, `up`, `down`, `left`, `right`, `home`, `end`, `pageup`, `pagedown`, `f1`–`f12`, plus any printable character.

If the hotkey conflicts with another app (Windows lets multiple apps register the same combination, but only the first wins), Enter a different combination and Save. See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md#hotkey-doesnt-do-anything) for diagnostics.

---

## How it works (architecture in 60 seconds)

When you press the hotkey:

1. **pynput's listener thread** wakes up. It reads the clipboard, detects whether the contents are a valid MAC address using a strict regex in `mac_formats.py`, normalizes the MAC to 12 hex chars (no separators), looks up the next format in the cycle, and writes the new format back to the clipboard.
2. The listener thread **puts a request onto a queue** (it never touches Qt widgets — that's a hard invariant). A 50ms `QTimer` on the Qt main thread is polling that queue.
3. The Qt main thread **creates a `FormatSelectorPopup`** (a `QDialog` with `Qt.Tool` flag — no taskbar entry), positions it bottom-right, calls `.show()`, then defers a focus-grab routine that uses the Win32 `AttachThreadInput` trick to satisfy Windows' foreground-steal rules.
4. If you press **Enter** while the popup is visible: a `QShortcut` (application-scoped) and `keyPressEvent` override both call `_on_enter_pressed`. The handler puts another request onto a separate queue. A different `QTimer` picks it up, calls `oui_db.lookup(mac_prefix)`, and shows the vendor popup.
5. If you press **Escape** or click anywhere outside, or the auto-close timer fires, the popup closes.

The complete architecture (threading model, data flow diagrams, key design decisions and their rationale, troubleshooting starting points) is in [`ARCHITECTURE.md`](ARCHITECTURE.md). Read that if you're going to modify the code.

---

## File locations

Everything the app writes lives in `%APPDATA%\mac-converter-2\` and the user's Startup folder. The app **never** touches the registry, never writes to `Program Files`, never creates files in your Documents or Desktop.

| Path | Purpose |
|------|---------|
| `%APPDATA%\mac-converter-2\settings.json` | Your preferences (hotkey, durations, OUI options, etc.) |
| `%APPDATA%\mac-converter-2\oui.csv` | IEEE OUI vendor database (~3.5 MB, downloaded weekly) |
| `%APPDATA%\mac-converter-2\settings.json.corrupt-<unix-ts>` | Automatically-renamed copies of corrupt settings files, for recovery |
| `%APPDATA%\mac-converter-2\oui.csv.tmp` | Temp file during OUI download; replaced into place atomically |
| `%APPDATA%\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk` | Autostart shortcut (only when "Start with Windows" is enabled) |

The installer additionally writes to:

| Path | Purpose |
|------|---------|
| `%LOCALAPPDATA%\Programs\MAC-Converter\` (or `%PROGRAMFILES%\MAC-Converter\` for admin installs) | The exe, icon, README, LICENSE |
| `%APPDATA%\Microsoft\Windows\Start Menu\Programs\MAC Address Converter\` | Start Menu shortcuts |
| Optional desktop shortcut, if you ticked the install option |

Uninstalling removes everything in the install folder and the Start Menu entries. You're prompted whether to also remove `%APPDATA%\mac-converter-2\` (settings and OUI database).

---

## System Requirements

- **OS**: Windows 7 or later (Windows 10/11 recommended)
- **Python**: 3.8+ (if running from source)
- **Admin Rights**: Not required (uses pynput for hotkey)
- **Dependencies**: PyQt5, pynput, pyperclip, pystray, pillow

---

## Development

### Project Structure

```
mac-converter-2/
├── clipboard_hotkey.py      # Main application (UI, hotkey, tray, popups, settings, autostart)
├── mac_formats.py           # MAC format detection and conversion (pure logic, no Qt/pynput)
├── oui_lookup.py            # OUI vendor database: download, parse, lookup (no Qt)
├── mac-converter.spec       # PyInstaller configuration
├── installer.iss            # Inno Setup installer script
├── icon-v1.png              # App icon (source PNG)
├── icon-v1.ico              # App icon (multi-size, used by PyInstaller for the exe icon)
├── env_load.ps1             # PowerShell venv activation helper
├── env_load.sh              # bash venv activation helper
├── LICENSE.txt              # MIT License
├── requirements.txt         # Python runtime dependencies
├── requirements-dev.txt     # Python test dependencies (pytest)
├── pytest.ini               # pytest configuration
├── tests/                   # 24 regression tests (mac_formats, oui_lookup, settings)
│   ├── conftest.py          # Pytest fixtures
│   ├── test_mac_formats.py  # F1 regression + format conversion correctness
│   ├── test_oui_lookup.py   # F2/F3/F4/F5 OUI download hardening
│   ├── test_settings_atomic.py    # F7/F23 atomic write
│   └── test_settings_validate.py  # F8/F15/F24 load validation + corrupt recovery
├── docs/                    # GitHub Pages portal + audit + design specs + plans
│   ├── index.html           # Portal landing page
│   ├── styles.css           # Portal stylesheet
│   ├── icon-v1.png          # Portal icon (copy)
│   ├── README.md            # Portal operator instructions (Pages setup)
│   ├── AUDIT-2026-05-14.md  # Security & bug audit (37 findings, severity-sorted)
│   └── superpowers/         # Design specs and implementation plans
│       ├── specs/           # Phase-level design documents
│       └── plans/           # Implementation plans (TDD-style task lists)
├── README.md                # This file — user-facing features & quick-start
├── ARCHITECTURE.md          # Module-by-module code walkthrough, threading model, design rationale
├── CHANGELOG.md             # Version-by-version fix list
├── CONTRIBUTING.md          # Contribution workflow, code standards, release process
├── BUILDING.md              # Detailed build instructions (PyInstaller + Inno Setup)
├── TROUBLESHOOTING.md       # Full user-facing troubleshooting reference
├── SECURITY.md              # Security policy & vulnerability reporting
├── DEVELOPMENT_LOG.md       # Session-by-session development notes
└── TODO.md                  # Roadmap and completed milestones
```

### Building from source

For a one-line build:

```bash
pyinstaller mac-converter.spec --noconfirm
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
```

For the **detailed** build guide — prerequisites, icon regeneration, release process, troubleshooting — see [`BUILDING.md`](BUILDING.md).

### Running the tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Expected: 24 passed. The suite covers pure-logic fixes in `mac_formats.py`, `oui_lookup.py`, and settings I/O. UI behavior is verified manually before each release — see [`CONTRIBUTING.md`](CONTRIBUTING.md).

### Building Your Own Installer

1. Install build tools:
   ```bash
   pip install PyInstaller
   ```

2. Build executable:
   ```bash
   pyinstaller mac-converter.spec
   ```

3. Install Inno Setup (https://jrsoftware.org/isdl.php)

4. Build installer:
   ```bash
   "C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
   ```

Output files:
- Executable: `dist/MAC-Converter.exe`
- Installer: `installer-output/MAC-Converter-Setup-v2.4.0.exe`

---

## Design Principles

- **No Admin Rights**: App never requires administrator privileges
- **No Configuration Files Required**: Works out of the box with sensible defaults
- **Responsive Hotkey**: Instant format cycling without dialog delays
- **Clean UX**: Modern dark theme, professional appearance
- **Persistent Settings**: User preferences saved automatically
- **Error Handling**: Graceful handling of invalid clipboard content

---

## Troubleshooting

Common quick fixes are below. For the **complete** user-facing troubleshooting guide — including hotkey conflicts, OUI download failures, antivirus issues, corrupt settings recovery, autostart not surviving reboot, and a dozen other scenarios — see **[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md)**.

### Hotkey doesn't do anything

1. Check if the hotkey is already used by another app (Snipping Tool, Teams, etc.)
2. Right-click tray icon → **Settings** → verify the hotkey value
3. Try a different combination (e.g. `ctrl+shift+alt+m`)
4. **Restart the app** — hotkey changes only take effect on restart

### Format popup appears but Enter doesn't show vendor

1. **Upgrade to v2.4.2** — earlier v2.4.x versions had a focus regression
2. Make sure the OUI database is loaded (right-click tray → About → check entry count)
3. If still broken: try clicking the format popup once before pressing Enter

### Settings not persisting

1. Verify `%APPDATA%\mac-converter-2\settings.json` exists and is writable
2. Look for `settings.json.corrupt-<timestamp>` files — these indicate JSON corruption recovered automatically (each is a backup of the corrupt file)
3. If your antivirus is locking the file, add an exception for the `%APPDATA%\mac-converter-2\` folder

### Tray icon missing

1. Check the Windows system tray overflow (`^` arrow in the bottom-right)
2. Right-click taskbar → **Taskbar settings** → Notification area → ensure MAC Address Converter is shown
3. If the process is running but no icon shows, kill it via Task Manager and relaunch — sometimes the tray cache gets stuck

---

## Supported Platforms

- **Windows**: Full support (10, 11 recommended)
- **WSL/Linux**: Partial support (tray icon may not display)
- **macOS**: Not tested

---

## Version History

- **2.4.2** (2026-05-15): Enter-to-vendor-lookup actually fixed (Qt.StrongFocus + AttachThreadInput + Qt.ApplicationShortcut + keyPressEvent fallback)
- **2.4.1** (2026-05-15): First focus-grab attempt (superseded — see 2.4.2)
- **2.4.0** (2026-05-14): Bug-fix release — 37 audit findings closed across 5 high-severity (locked-clipboard crash, OUI download race, autostart now actually functional, hotkey validation, removal of system-wide keyboard hook), plus atomic settings/OUI writes, single-instance check, .ico icon, and dependency hygiene.
- **2.3.0** (2026-02-17): OUI vendor lookup, IEEE database integration, vendor popup, database management UI
- **2.2.0** (2025-12-31): Auto-cycling converter, dark theme UI enhancements, Windows installer
- **2.1.0** (2025-06-07): Persistent settings, Settings dialog, About dialog, admin rights removed
- **2.0.0** (2025-06-06): Stable release with global hotkey and format selector

See [`CHANGELOG.md`](CHANGELOG.md) for the per-finding fix list.

---

## Quality & Testing

- ✅ 24 automated regression tests (pytest) — green on every commit
- ✅ Full security & bug audit completed for v2.4.0 (37 findings, all closed) — see [`docs/AUDIT-2026-05-14.md`](docs/AUDIT-2026-05-14.md)
- ✅ Atomic file writes for settings and OUI database (no corruption under crash/race)
- ✅ No system-wide keyboard hooks beyond the configurable hotkey itself
- ✅ Single-instance enforcement (Win32 named mutex)
- ✅ Graceful clipboard-error handling
- ✅ Corrupt-settings recovery (renamed aside, defaults loaded, app continues)

---

## Documentation map

This project is comprehensively documented — start here:

| If you want to... | Read this |
|-------------------|-----------|
| Install and use the app | This README (you're here) |
| See per-version changes | [`CHANGELOG.md`](CHANGELOG.md) |
| Diagnose an issue you're having | [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) |
| Understand the codebase before changing it | [`ARCHITECTURE.md`](ARCHITECTURE.md) — module-by-module deep dive with design rationale |
| Build the exe / installer yourself | [`BUILDING.md`](BUILDING.md) — detailed step-by-step |
| Contribute code | [`CONTRIBUTING.md`](CONTRIBUTING.md) — workflow + coding standards |
| Report a security issue | [`SECURITY.md`](SECURITY.md) — disclosure policy |
| See the roadmap and completed milestones | [`TODO.md`](TODO.md) |
| Read session-by-session development notes | [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md) |
| See the full v2.4.0 security audit | [`docs/AUDIT-2026-05-14.md`](docs/AUDIT-2026-05-14.md) — 37 findings sorted by severity, with file:line precision, why-it's-a-bug rationale, and proposed fixes |
| See the design specs and implementation plans | [`docs/superpowers/`](docs/superpowers/) — phase-level design docs and TDD-style task lists |

---

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for the contribution workflow, code-quality standards, and testing guidance.

For vulnerability reports, see [`SECURITY.md`](SECURITY.md).

---

## License

MIT License - See [LICENSE.txt](LICENSE.txt) for details

---

## Support & Links

- **Download portal:** [https://aleled.github.io/mac-converter-2/](https://aleled.github.io/mac-converter-2/)
- **Releases:** [https://github.com/aleled/mac-converter-2/releases](https://github.com/aleled/mac-converter-2/releases)
- **Issues:** [https://github.com/aleled/mac-converter-2/issues](https://github.com/aleled/mac-converter-2/issues)
- **Repository:** [https://github.com/aleled/mac-converter-2](https://github.com/aleled/mac-converter-2)

---

**Enjoy converting MAC addresses effortlessly! 🎯**
