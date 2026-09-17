# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 2.5.x   | ✅        |
| 2.4.x   | ❌ — please upgrade to 2.5.2 (removes the low-level keyboard hook) |
| 2.3.x   | ❌ — please upgrade to 2.4.0 (closes 5 high-severity findings) |
| < 2.3   | ❌        |

## Reporting a vulnerability

If you find a security issue in MAC Address Converter:

1. **Do not open a public GitHub issue.** Security findings should be reported privately first so a fix can ship before details become public.
2. Email the maintainer: **4leled@gmail.com**.
   - Subject line: `[security] mac-converter-2: <short summary>`
   - Include: a description of the issue, a proof-of-concept or repro steps if applicable, and the version you observed it on.
3. You'll get an acknowledgement within ~7 days. Triage and a fix timeline follow from there.
4. Once a fix is released, you're welcome to disclose publicly (with credit if you'd like).

## Recent security work

A full audit of the codebase was performed on 2026-05-14 covering all source, build, and configuration files. The audit report is committed at [`docs/AUDIT-2026-05-14.md`](docs/AUDIT-2026-05-14.md) — 37 findings (5 high, 12 medium, 20 low), all closed in v2.4.0. Highlights of the security-relevant fixes:

- Removed an architectural privacy concern: a system-wide pynput keyboard listener was being created on every hotkey press for the format popup's Enter key detection. It captured every keystroke (including passwords in other apps). Replaced with a Qt-scoped `QShortcut` (F19).
- Hardened OUI database download: rejects HTML / captive-portal responses before they can overwrite the live `oui.csv` (F3); uses `os.replace` for atomic writes that preserve the prior file on rename failure (F2).
- Atomic settings writes: corrupt or partial `settings.json` files are now renamed to `settings.json.corrupt-<unix-ts>` rather than silently overwritten (F24).
- Error messages no longer leak filesystem paths containing the Windows username (F12).
- Single-instance Win32 mutex prevents double-launch races (F25).

Follow-up in v2.5.2: the main global hotkey, still a `pynput` low-level keyboard hook after F19, was replaced with the Win32 `RegisterHotKey` API. The app no longer installs any keyboard hook.

## Threat model

The app:
- Runs as the current Windows user (no elevation, no admin rights).
- Reads/writes only `%APPDATA%\mac-converter-2\` and the user's Startup folder.
- Reads from the system clipboard when the hotkey is pressed.
- Makes outbound HTTPS connections only to `standards-oui.ieee.org` for the OUI database (with TLS certificate verification — Python `urllib` default).
- Does not collect telemetry, phone home, or transmit any user data anywhere.

The app does NOT:
- Persist clipboard contents to disk beyond the immediate conversion.
- See or log keystrokes. Since v2.5.2 the global hotkey is registered with Windows' `RegisterHotKey` API, so Windows matches the chord and the app receives a single notification — no keyboard hook, no access to any other keystroke.
  - *Correction:* v2.1.0–v2.5.1 used `pynput.keyboard.Listener`, a low-level keyboard hook that received every keystroke system-wide (it only acted on the configured chord, but it did see all keys). Earlier versions of this file described it as only firing on the chord, which understated its access. No keystrokes were ever logged or stored.
- Connect to any third-party server other than IEEE for the OUI database.

## Out of scope

- **Unsigned binary on Windows.** The released `.exe` is not code-signed. SmartScreen and some AV products may flag it on first run. UPX has been disabled in v2.4.0 to reduce false positives, but signing is out of scope for this open-source project. Verify the SHA-256 of the installer against the GitHub Release assets page if you want extra assurance.
- **Source-code supply chain audits of dependencies** (PyQt5, pystray, pyperclip, Pillow, pywin32, truststore). These are widely-used PyPI packages; consult their own security policies for vulnerability information.
