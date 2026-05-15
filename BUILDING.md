# Building MAC Address Converter from source

This is the **detailed** build guide — for someone who wants to cut a fresh release. For day-to-day development workflow (linting, testing, contributing), see [`CONTRIBUTING.md`](CONTRIBUTING.md).

There are two artifacts: a standalone Windows `.exe` (built with PyInstaller) and a Windows installer (built with Inno Setup that wraps the exe).

---

## 1. Prerequisites

| Tool | Version | Purpose | Required? |
|------|---------|---------|-----------|
| Python | 3.8+ (tested on 3.13) | Runtime + build env | yes |
| pip | any recent | Dependency management | yes (ships with Python) |
| Git | any | Version control | yes |
| PyInstaller | 5.0+ (auto-installed via requirements.txt) | Builds the `.exe` | yes |
| Inno Setup | 6.0+ | Builds the installer wrapping the exe | only if you want the .exe-with-installer flow |
| pywin32 | any recent (auto-installed) | Runtime dep for autostart and single-instance; also used by Pillow for icon generation | yes |
| Pillow | any recent (auto-installed) | Generates the multi-size `.ico` from the PNG | yes |

Inno Setup is free: <https://jrsoftware.org/isdl.php>. Install with all defaults; the compiler ends up at `C:\Program Files (x86)\Inno Setup 6\iscc.exe`.

---

## 2. One-time dev environment setup

```powershell
# Clone the repo
git clone https://github.com/aleled/mac-converter-2.git
cd mac-converter-2

# Create a venv (recommended — keeps the build env isolated)
python -m venv venv

# Activate it (PowerShell)
. .\venv\Scripts\Activate.ps1
# Or bash/zsh:
# source venv/Scripts/activate

# Install runtime + dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

Verify everything is wired up:

```powershell
# Quick smoke check — should print "Python 3.X.Y" and "pytest X.Y.Z"
python --version
python -m pytest --version

# Run the regression suite — should report 24 passed
python -m pytest

# Optionally launch the app from source to confirm it works
python clipboard_hotkey.py
```

If `pytest` reports anything other than 24 passed, **stop and investigate** before building. Don't ship a build with failing tests.

---

## 3. Regenerate the `.ico` icon (only when icon-v1.png changes)

PyInstaller embeds an `.ico` for the Windows exe icon. The `.ico` is a multi-resolution container — Pillow can build it from the existing PNG:

```powershell
python -c "from PIL import Image; img = Image.open('icon-v1.png'); img.save('icon-v1.ico', sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])"
```

The output is `icon-v1.ico` at the repo root, around 50–200 KB. Commit it alongside `icon-v1.png` if you've changed the source PNG.

To verify the .ico has all the embedded sizes:

```powershell
python -c "from PIL import Image; img = Image.open('icon-v1.ico'); print('Sizes:', img.ico.sizes())"
```

Expected output: `Sizes: {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}`.

---

## 4. Build the standalone `.exe` (PyInstaller)

```powershell
# From the repo root, with the venv activated:
pyinstaller mac-converter.spec --noconfirm
```

This takes ~1–2 minutes. Output:

- `dist/MAC-Converter.exe` — the single-file standalone exe (~51 MB). Run it directly; no installer needed.
- `build/` — PyInstaller's working directory. Can be deleted between builds.

The `.spec` file already encodes all the build options (hidden imports, icon, UPX disabled, console=False). **Don't edit `mac-converter.spec` ad-hoc** — changes there are intentional and listed in CHANGELOG. See `ARCHITECTURE.md` § 7 for the rationale.

### Verifying the build

```powershell
# Verify the exe loads and the icon is embedded
Start-Process .\dist\MAC-Converter.exe

# Should appear in the system tray with the proper icon.
# Press your hotkey to test functionality.
# Right-click tray → Quit when done.
```

If the exe crashes on launch with a missing-import error, the most likely culprit is a hidden import that PyInstaller didn't pick up. Check the imports in your code change against `mac-converter.spec`'s `hiddenimports` list — add any that PyInstaller missed.

---

## 5. Build the Windows installer (Inno Setup)

The installer wraps `dist/MAC-Converter.exe` plus `icon-v1.png`, `README.md`, and `LICENSE.txt` into a setup wizard.

```powershell
& 'C:\Program Files (x86)\Inno Setup 6\iscc.exe' installer.iss
```

Output: `installer-output/MAC-Converter-Setup-vX.Y.Z.exe` (~54 MB, where X.Y.Z is what's in `installer.iss` line 5).

### Verifying the installer

1. Run it on a clean test machine (or VM, or a different Windows user account).
2. Check that:
   - It installs without admin elevation
   - It creates a Start Menu group and (optionally) a desktop shortcut
   - The "Run at Windows startup" option is offered
   - The app launches at the end of install
   - The tray icon appears
3. Uninstall via Control Panel → Programs → Uninstall, and confirm:
   - The Start Menu shortcut goes away
   - The desktop shortcut (if installed) goes away
   - The autostart shortcut in the Startup folder goes away (if it was enabled)
   - You're prompted whether to remove `%APPDATA%\mac-converter-2\` — and that "Yes" actually removes it

---

## 6. Cutting a release

When you're ready to publish a new version:

### 6.1 Bump the version

Update the version string in **all** of these:

- `installer.iss` line 5 — `#define MyAppVersion "X.Y.Z"`
- `clipboard_hotkey.py` — `version_label = QLabel("Version X.Y.Z")` (in the About dialog, around line 497)
- `clipboard_hotkey.py` — `'about': 'MAC Address Converter Utility vX.Y.Z\n...'` (in `DEFAULT_SETTINGS`, around line 1839)
- `oui_lookup.py` — `'User-Agent': 'MAC-Converter/X.Y.Z'` (around line 71)
- `README.md` — header line `**Current Version:** X.Y.Z`, the direct-download links, and the version history
- `TODO.md` — header `**Current Version:** X.Y.Z`, `**Last Updated:**`

A quick way to find any you missed:

```powershell
git grep -n "X\.Y\.Z" -- ":!CHANGELOG.md" ":!docs"
```

(CHANGELOG and historical doc references shouldn't be touched.)

### 6.2 Update the CHANGELOG

Add a new `## [X.Y.Z] - YYYY-MM-DD` section at the top of `CHANGELOG.md` with `### Added`, `### Changed`, `### Fixed` subsections as applicable. Reference the F-IDs from the audit if you closed any.

### 6.3 Run the full pytest suite one more time

```powershell
python -m pytest -v
```

All 24+ tests must be green.

### 6.4 Build artifacts

```powershell
pyinstaller mac-converter.spec --noconfirm
& 'C:\Program Files (x86)\Inno Setup 6\iscc.exe' installer.iss
```

### 6.5 Manual smoke test

Run the installed app and exercise the key paths:

- Hotkey converts a MAC and copies to clipboard
- Format popup appears and accepts Enter for vendor lookup
- Settings dialog opens, saves, hotkey change persists across restart
- About dialog shows the new version number
- Autostart toggle creates/removes the `.lnk` in Startup folder
- Quit cleanly exits

### 6.6 Commit and tag

```powershell
git add -A
git commit -m "release: bump version to X.Y.Z"
git push
```

### 6.7 Create the GitHub Release

Either via the web UI or `gh`:

```powershell
gh release create vX.Y.Z `
  installer-output/MAC-Converter-Setup-vX.Y.Z.exe `
  dist/MAC-Converter.exe `
  --title "vX.Y.Z — <short description>" `
  --notes "<changelog entry>"
```

Within ~30 seconds of publishing, the [download portal](https://aleled.github.io/mac-converter-2/) auto-detects the new release and updates the "Download" button. No portal redeploy needed — the JS fetches the latest release from the GitHub API on every page load.

---

## 7. Troubleshooting the build

### PyInstaller "ModuleNotFoundError: No module named 'pynput.keyboard._win32'"

Even though `mac-converter.spec` lists this as a hidden import, sometimes PyInstaller's hook resolution misbehaves. Try:

```powershell
pip install --upgrade pyinstaller
Remove-Item -Recurse -Force build, dist
pyinstaller mac-converter.spec --noconfirm
```

### Inno Setup "compiler error: <some path> not found"

The compiler can't find a source file. Most common reason: you haven't built the PyInstaller exe yet. Run `pyinstaller mac-converter.spec --noconfirm` first, then re-run `iscc.exe`.

### Windows Defender / SmartScreen flags the new exe

This is expected for any unsigned binary. UPX is already disabled in `mac-converter.spec` (`upx=False`) to reduce false positives. The only real fix is code-signing with a paid certificate, which is out of scope. See [`SECURITY.md`](SECURITY.md) for context.

### The built exe runs but the icon is missing in Explorer

Two possibilities:

1. The `.ico` wasn't generated — re-run the Pillow command in § 3.
2. Windows is caching an old icon. Open Command Prompt as admin and run:
   ```cmd
   ie4uinit.exe -show
   ```
   (`ie4uinit` is the icon-cache rebuild tool, despite the misleading name.)

---

## 8. Cleaning up build artifacts

If the working tree has stale `build/`, `dist/`, or `installer-output/` directories that you want gone:

```powershell
Remove-Item -Recurse -Force build, dist, installer-output -ErrorAction SilentlyContinue
```

These directories are already gitignored, so removing them locally doesn't affect the repo.

---

## See also

- [`ARCHITECTURE.md`](ARCHITECTURE.md) § 7 — why the build settings are the way they are
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — dev workflow for code changes
- [`mac-converter.spec`](mac-converter.spec) — the PyInstaller spec itself
- [`installer.iss`](installer.iss) — the Inno Setup script itself
