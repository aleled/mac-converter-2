# Troubleshooting

If something isn't working, scan this list for your symptom. Each entry has a likely cause and a step-by-step fix.

**Quick check:** before diving deeper, right-click the tray icon → **About** → confirm the version shown. Many issues are resolved by [downloading the latest version from the portal](https://aleled.github.io/mac-converter-2/) and installing over the existing app.

---

## Hotkey doesn't do anything

**Symptoms:** You press Alt+Shift+M (or your configured hotkey) and nothing happens — no popup, no notification, no tray flash.

**Likely causes** (in order of probability):

### 1. The hotkey is already used by another app

Windows lets multiple apps register the same hotkey, but only the first one to register wins. Common conflicts: Snipping Tool (`Win+Shift+S`), Microsoft Teams (various Alt combos), screen recorders.

**Fix:** right-click tray icon → Settings → change the hotkey to something unusual (e.g. `ctrl+shift+alt+m`). Click Save. **Restart the app** — hotkey changes only take effect on app restart (this is the one settings change that isn't live).

### 2. The app process isn't running

Check the Windows tray (the up-arrow `^` in the bottom-right). If the MAC Converter icon isn't there, the app exited or never started.

**Fix:** launch the app from the Start Menu, desktop shortcut, or `%PROGRAMFILES%\MAC-Converter\MAC-Converter.exe`. If it immediately exits, see "App won't start" below.

### 3. pynput's keyboard hook was blocked by antivirus

Some endpoint protection products (especially enterprise ones — Cylance, CrowdStrike, SentinelOne) flag low-level keyboard hooks as suspicious. The app may launch but silently fail to register the hotkey.

**Fix:** check your AV's quarantine / activity log for `pynput` or `MAC-Converter.exe`. Add an exception. If you can't add an exception, this app may not be usable in your environment — there's no admin-free alternative to pynput's hook.

### 4. The hotkey value in settings.json is corrupt

If a previous Settings dialog Save somehow persisted garbage (shouldn't happen since v2.4.0's F14 validation, but a hand-edited `settings.json` can do it), the listener falls back silently to the default `alt+shift+m`.

**Fix:** open `%APPDATA%\mac-converter-2\settings.json` in Notepad. The `hotkey` value should be like `"alt+shift+m"`. If it's gibberish, replace it with the default and save. Then restart the app.

---

## Format popup appears, but pressing Enter doesn't show the vendor

**Symptoms:** the hotkey works (format popup appears in the bottom-right), but pressing Enter does nothing — the popup just times out.

**If you're on v2.4.0 or v2.4.1:** upgrade. This was a regression fixed in v2.4.2. The format popup is a `Qt.Tool` window that doesn't take focus on Windows by default, so the keyboard shortcut never fired.

**If you're on v2.4.2 or later and it still doesn't work:** the OUI database probably isn't loaded yet. In v2.4.2 a tray notification should say "OUI database is still loading, try again in a moment." If you see that, wait for the download to finish (~10–30 seconds on a fast connection, longer on slow ones). Once the database is loaded, Enter will work.

If the issue persists with v2.4.2+ and the OUI database is loaded (About dialog shows "OUI Entries: 38900+"), try:

1. **Click the format popup once** before pressing Enter. This forces focus to the popup. If this works, the `AttachThreadInput` foreground-grab is failing — please report which Windows version you're on.
2. Check `%APPDATA%\mac-converter-2\oui.csv` exists and is ~3.5 MB. If it's tiny, the auto-download was rejected (likely a captive portal — see "OUI download fails").

---

## App won't start

**Symptoms:** double-clicking the shortcut does nothing, or the app starts and immediately exits.

### 1. Another instance is already running

Since v2.4.0, the app uses a Win32 named mutex to prevent double-launch. If a previous instance crashed or was killed forcibly, the mutex might still be alive briefly.

**Fix:** open Task Manager → Details tab → look for `MAC-Converter.exe`. If it's there, the previous instance is fine — just check the tray. If not, wait 5 seconds and try again. If the issue persists, restart Windows.

### 2. settings.json is so corrupt the validator can't even rename it

The v2.4.0 corrupt-file recovery (F24) renames `settings.json` to `settings.json.corrupt-<unix-ts>` and falls back to defaults. If even THIS path fails (e.g. permission denied because OneDrive locked the file), the app may exit.

**Fix:** open `%APPDATA%\mac-converter-2\` in Explorer. Move `settings.json` to your Desktop manually. Relaunch the app — it'll create a fresh `settings.json` with defaults.

### 3. Missing dependency (running from source)

If you're running `python clipboard_hotkey.py` from source and you see `ImportError` or `ModuleNotFoundError`, install dependencies:

```bash
pip install -r requirements.txt
```

If you get the error specifically for `pywin32`, run `python venv\Scripts\pywin32_postinstall.py -install` once after installing it.

### 4. Antivirus quarantined the .exe

The exe is unsigned and uses Win32 keyboard hooks — common antivirus false-positive triggers (UPX was disabled in v2.4.0 to reduce this, but it's not fully eliminated).

**Fix:** restore the exe from your AV's quarantine, then add an exception for `%PROGRAMFILES%\MAC-Converter\MAC-Converter.exe`. If your endpoint security doesn't allow exceptions, you may need to use the standalone `MAC-Converter.exe` (the same binary, just not packaged in an installer) — same issue but easier to put in a custom location your AV trusts.

---

## OUI vendor lookup says "Unknown vendor" for a MAC I know belongs to a real company

**Likely cause:** the IEEE `oui.csv` only contains **MA-L** (Large) block assignments — 16M MACs each. Smaller block assignments (**MA-M** for 1M, **MA-S** for 4K) aren't in this CSV.

Affected vendors typically: niche IoT companies, small contract manufacturers, prototypes. A residential router from a major brand will always be in MA-L.

**Workarounds:**

1. Look the prefix up manually at <https://standards.ieee.org/products-services/regauth/oui/>
2. Use a more comprehensive third-party database like Wireshark's manuf file

This is a data limitation, not a bug in the app.

---

## OUI download fails / database won't update

**Symptoms:** the manual Update button in Settings shows an error, or auto-update never seems to happen.

### Common errors

| Error message | Cause | Fix |
|---------------|-------|-----|
| `Network error: ...` | No internet, firewall blocking HTTPS to `standards-oui.ieee.org`, proxy required | Check network. The app uses Python `urllib`, which honors `HTTP_PROXY` / `HTTPS_PROXY` env vars but not browser proxy settings. |
| `Server returned text/html ...` | Captive portal (hotel WiFi, corporate guest network) is intercepting the download | Authenticate to the captive portal first, then retry. The v2.4.0 fix specifically prevents the captive-portal HTML from overwriting your good `oui.csv`. |
| `Response body looks like HTML/XML, not CSV ...` | Same as above (belt-and-suspenders detection) | Same fix. |
| `Downloaded file too small, may be corrupt` | The download was truncated | Retry. If it persists, network issue between you and IEEE. |
| `OUI database parsed to zero entries (empty or corrupt)` | The file downloaded but has no parseable rows | Could be an IEEE CSV format change. Open `oui.csv` in a text editor and verify the header matches `Registry,Assignment,Organization Name,Organization Address`. |

### Force a fresh download

1. Quit the app (right-click tray → Quit)
2. Delete `%APPDATA%\mac-converter-2\oui.csv`
3. Relaunch the app — auto-update will trigger because the file is now "missing" (which is considered stale)

---

## "Start with Windows" doesn't survive a reboot

**Symptoms:** you toggle the autostart checkbox on, save settings, reboot, and the app doesn't auto-launch.

**Likely cause:** the `.lnk` file wasn't created (permission issue) or was deleted by some cleanup utility (CCleaner-style).

**Diagnosis steps:**

1. Open `%APPDATA%\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\` in Explorer
2. Check if `MAC-Converter.lnk` exists
3. If it doesn't exist, the `set_autostart_enabled(True)` call failed — likely pywin32 wasn't able to dispatch `WScript.Shell`. Try reinstalling the app.
4. If the file DOES exist but it's not running on boot, check Task Manager → Startup tab. Windows may have disabled it (right-click → Enable).
5. Some Windows installations restrict Startup-folder entries via Group Policy. Run `gpresult /h gp.html` and search for "Startup".

**Pre-v2.4.0 note:** in v2.3.0 and earlier, the checkbox was cosmetic (no code ever created a shortcut). If you're seeing this on an old version, just upgrade.

---

## Antivirus / SmartScreen warns when running the installer

**This is expected and not a bug.** The installer and exe are unsigned. Windows SmartScreen shows "Windows protected your PC" on first run of an unsigned exe.

**Workaround:** click "More info" → "Run anyway". The exe will be remembered after the first run so subsequent launches don't prompt.

**Permanent fix:** code-signing the binary would eliminate the warning. That requires a paid certificate and is out of scope for this free open-source project.

**If your enterprise AV blocks the installer entirely:** see the "App won't start" section above. Add an exception or use the standalone exe.

---

## Tray icon disappeared but the process is still running

**Symptoms:** Task Manager shows `MAC-Converter.exe` is running, but there's no icon in the tray.

**Likely cause:** Windows' tray icon cache got confused.

**Fix:**

1. Right-click the taskbar → Taskbar settings → Notification area → Select which icons appear on the taskbar → ensure "MAC Address Converter" is on
2. Or: restart Explorer. Task Manager → find `Windows Explorer` in Processes → right-click → Restart. The tray will refresh.

If the icon never reappears, kill `MAC-Converter.exe` from Task Manager and relaunch.

---

## Settings dialog crashes or shows weird layout

**Symptoms:** clicking Settings opens a dialog with overlapping text, cut-off buttons, or unreadable dark-theme glitches.

**Pre-v2.3.0:** known issues, fixed in v2.3.0.

**v2.3.0+:** if you see layout glitches, it's likely a Windows display-scaling issue. PyQt5 generally respects DPI scaling but very high-DPI monitors (4K+) may need a tweak.

**Workaround:** right-click the desktop shortcut for MAC-Converter → Properties → Compatibility → Change high DPI settings → check "Override high DPI scaling behavior" → "System". Test if that helps.

---

## I want to back up my settings before reinstalling

`%APPDATA%\mac-converter-2\settings.json` — just copy this file. It's plain JSON.

The OUI database (`oui.csv`) is large and gets re-downloaded automatically, so no need to back it up.

---

## I uninstalled but my Startup-folder shortcut is still there

The Inno Setup uninstaller asks "Do you want to remove application settings and preferences?" before deleting `%APPDATA%\mac-converter-2\`. If you said No, the settings stayed — including remembering that autostart was enabled.

However, the autostart `.lnk` lives in a different folder (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\MAC-Converter.lnk`). The uninstaller doesn't clean this up.

**Fix:** delete `MAC-Converter.lnk` from your Startup folder manually. Or, before uninstalling: open Settings → uncheck "Start with Windows" → Save. The toggle-off removes the shortcut.

---

## I'm seeing `settings.json.corrupt-1747260123` files in %APPDATA%

These are evidence that the app's corrupt-file recovery fired (introduced in v2.4.0). Each one is a copy of a `settings.json` that failed to parse, preserved so you can recover hand-edits.

**Action:** if you've never hand-edited `settings.json`, you can safely delete these. They're text files — open one to confirm there's nothing you care about losing.

If you DO see these regularly, something is corrupting your settings file — antivirus, an external sync tool (OneDrive), or a real bug. Please open an issue with one of the corrupt files attached.

---

## I want more verbose logging

The app doesn't have a built-in log file. If you're running from source, the `print(...)` calls in error paths go to stderr. To capture them:

```bash
python clipboard_hotkey.py 2> mac-converter.log
```

When running the installed exe, there's no easy way to capture stderr (the exe is built with `console=False`). For deeper debugging, consider running from source or opening an issue describing the symptom.

---

## My issue isn't here

1. Open the [GitHub Issues page](https://github.com/aleled/mac-converter-2/issues) and check for similar reports.
2. If nothing matches, open a new issue with:
   - Version (right-click tray → About → version number)
   - Windows version (Win+R → `winver` → screenshot)
   - Step-by-step to reproduce
   - What you expected to happen vs what actually happened
   - Contents of `%APPDATA%\mac-converter-2\settings.json` (sanitized if you've put anything sensitive there)
3. For suspected security issues, follow [`SECURITY.md`](SECURITY.md) instead of the public tracker.

---

## See also

- [`README.md`](README.md) — features and usage
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — deep technical reference, especially § 12 ("Where to look when something breaks")
- [`CHANGELOG.md`](CHANGELOG.md) — version-by-version fix list
- [`SECURITY.md`](SECURITY.md) — vulnerability reporting
