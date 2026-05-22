# Contributing to MAC Address Converter

Thanks for considering a contribution. This project is small and personal but PRs are welcome — especially bug fixes, additional MAC-format support, and platform-portability improvements.

## Before you start

- Read [`README.md`](README.md) to understand what the app does.
- Read [`docs/AUDIT-2026-05-14.md`](docs/AUDIT-2026-05-14.md) if you're touching `clipboard_hotkey.py`, `oui_lookup.py`, or settings I/O — it documents recent fixes and the design rationale.
- For security issues: please follow [`SECURITY.md`](SECURITY.md), not the public issue tracker.

## Development setup

```bash
git clone https://github.com/aleled/mac-converter-2.git
cd mac-converter-2

# Create venv (Windows)
python -m venv venv
. .\venv\Scripts\Activate.ps1

# Install runtime + dev deps
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
python -m pytest

# Run the app
python clipboard_hotkey.py
```

The venv helper scripts `env_load.ps1` (PowerShell) and `env_load.sh` (bash) activate an existing `venv/`.

## Workflow

1. Fork the repo, or create a branch off `dev`.
2. Make changes in small, atomic commits.
3. Run the regression suite (`python -m pytest`). All 24 tests should stay green.
4. If your change affects pure logic in `mac_formats.py`, `oui_lookup.py`, or settings I/O, **add a regression test** in `tests/`.
5. If your change is user-visible, update `CHANGELOG.md` under a new `[Unreleased]` section.
6. Open a PR against `dev`. Reference any related audit finding IDs (e.g. `Closes F<N>`) if applicable.

## Coding standards

These are constraints inherited from the design — please respect them:

- **No admin rights ever.** The app must run as an ordinary user. Don't introduce features that require elevation.
- **Dark theme only.** All UI uses the same palette (`#2b2b2b` background, `#0078d4` accent).
- **Settings live in `%APPDATA%\mac-converter-2\`.** Don't pollute the install directory or scatter files elsewhere.
- **Atomic file writes.** Anything that mutates a persistent file should use the temp-file + `os.replace` pattern. See `_atomic_write_json` in `clipboard_hotkey.py`.
- **Thread-safe.** Producer-consumer flow between worker threads and Qt main thread should go through `queue.Queue` polled by `QTimer`. Don't touch Qt widgets from worker threads.
- **No bare `except:`.** Use `except Exception:` or a more specific type — bare excepts swallow `KeyboardInterrupt` and `SystemExit`.
- **No global keyboard hooks** beyond the configurable application hotkey. Per-popup keyboard handling uses Qt's `QShortcut` / `keyPressEvent`, not `pynput.keyboard.Listener`.
- **Single source of truth for autostart.** Don't add a competing mechanism (e.g. registry write) alongside the existing Startup-folder shortcut.

## Testing guidance

- `tests/test_mac_formats.py` — pure-function tests, no fixtures needed.
- `tests/test_oui_lookup.py` — uses `unittest.mock.patch` against `urllib.request.urlopen` to simulate network responses.
- `tests/test_settings_atomic.py` and `tests/test_settings_validate.py` — use `tmp_path` and `monkeypatch` to redirect `SETTINGS_DIR`/`SETTINGS_FILENAME`.

UI behaviors aren't currently in the automated suite — they're verified manually before release. If you add a UI fix, document the manual verification steps in your PR.

## Building releases

```bash
# Build standalone .exe
pyinstaller mac-converter.spec
# Output: dist/MAC-Converter.exe

# Build Windows installer
"C:\Program Files (x86)\Inno Setup 6\iscc.exe" installer.iss
# Output: installer-output/MAC-Converter-Setup-vX.Y.Z.exe
```

Version is bumped in `installer.iss`, `oui_lookup.py` (User-Agent), `clipboard_hotkey.py` (AboutDialog + DEFAULT_SETTINGS 'about'), `README.md`, and `TODO.md`. Use `grep -n "X\.Y\.Z" .` to find all sites.

## Release process

1. Bump version everywhere (see above).
2. Add a new `## [X.Y.Z] - YYYY-MM-DD` section to `CHANGELOG.md` with Added/Changed/Fixed lists.
3. Build the artifacts.
4. Push, open PR against `dev`, merge.
5. Create a GitHub Release tagged `vX.Y.Z`, paste the CHANGELOG entry as the release notes, attach both artifacts.
6. The download portal at https://aleled.github.io/mac-converter-2/ will auto-detect the new release within ~30 seconds.

## License

By contributing, you agree your contributions are licensed under the MIT License (same as the rest of the project).
