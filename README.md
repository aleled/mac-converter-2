# MAC Address Converter

A lightweight Windows system tray utility for converting MAC addresses between different formats with a global hotkey, auto-cycling format selection, and clipboard integration.

**Current Version:** 2.4.0
**Status:** Production-ready ✅
**License:** MIT
**Author:** Alejandro Lichtenfeld

---

## Features

- **System Tray Utility**: Runs in the background with custom icon in system tray
- **Auto-Cycling Format Conversion**: Press hotkey to instantly cycle through 10 MAC address formats
- **Global Hotkey**: Configurable hotkey (default: Alt+Shift+M) - no admin rights required
- **Automatic Clipboard Management**: Converted MAC address is automatically copied to clipboard
- **Tray Notifications**: Shows converted MAC address in a popup notification (configurable duration: 1-10 seconds, default: 3)
- **Error Handling**: Displays error notifications for invalid MAC addresses in clipboard
- **OUI Vendor Lookup**: Press Enter in format popup to identify MAC address manufacturer (IEEE database, ~38,900 vendors)
- **OUI Database Management**: Auto-update, manual update with percentage progress bar, searchable database viewer
- **Dark Theme UI**: Modern, professional dark theme with organized dialogs
- **Settings Dialog**: Configure hotkey, notification duration, autostart, and OUI vendor lookup options via tray menu
- **About Dialog**: View app information, version, author, license, GitHub link, and OUI database statistics
- **Persistent Settings**: All user preferences stored in `%APPDATA%\mac-converter-2\settings.json`
- **No Admin Rights Required**: Uses pynput for hotkey registration - runs without elevation

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

1. Download `MAC-Converter-Setup-v2.4.0.exe` from GitHub releases
2. Run the installer and follow the wizard
3. Choose optional features:
   - Desktop shortcut
   - Start with Windows (autostart)
4. App launches automatically after installation
5. No admin rights required

### Option 2: Standalone Executable

1. Download `MAC-Converter.exe` from GitHub releases
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

### Default Settings

Settings are stored in: `%APPDATA%\mac-converter-2\settings.json`

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

### Changing Settings

1. Right-click tray icon → **Settings**
2. **Hotkey Configuration**: Enter custom hotkey (e.g., `ctrl+shift+c`, `alt+m`)
3. **Notification Preferences**: Select popup duration (1-10 seconds)
4. **Startup Options**: Enable "Start with Windows" to auto-launch on startup
5. **OUI Vendor Lookup**: Enable/disable vendor lookup, configure auto-update interval and vendor popup timeout
6. Click **Save**
7. **Note**: Hotkey changes require app restart

### Hotkey Format

Hotkey format: `modifier+modifier+key`

Examples:
- `alt+shift+m` (default)
- `ctrl+shift+c`
- `alt+m`
- `ctrl+shift+x`

Special keys: `alt`, `ctrl`, `shift`, `tab`, `enter`, `delete`, `backspace`

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
├── clipboard_hotkey.py      # Main application (UI, hotkey, tray, popups)
├── mac_formats.py           # MAC format detection and conversion
├── oui_lookup.py            # OUI vendor database (download, parse, lookup)
├── mac-converter.spec       # PyInstaller configuration
├── installer.iss            # Inno Setup installer script
├── icon-v1.png              # App icon
├── LICENSE.txt              # MIT License
├── requirements.txt         # Python dependencies
├── README.md                # This file
├── CHANGELOG.md             # Version history
├── DEVELOPMENT_LOG.md       # Session notes
└── TODO.md                  # Feature roadmap
```

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

### Hotkey Not Working

1. Check if hotkey is already used by another application
2. Right-click tray icon → **Settings** → verify hotkey setting
3. Try a different hotkey combination
4. Restart the app after changing hotkey

### Notification Not Showing

1. Check notification duration setting (should be 1-10 seconds)
2. Verify notification duration is not set to 0
3. Right-click tray icon → **Settings** → adjust duration
4. Restart the app

### Tray Icon Missing

1. Check Windows system tray (arrow icon on taskbar)
2. Right-click taskbar → **Taskbar settings** → ensure notifications are enabled
3. Restart the app

### Settings Not Persisting

1. Verify settings file exists: `%APPDATA%\mac-converter-2\settings.json`
2. Check file permissions (should be readable/writable)
3. Delete settings file to restore defaults and restart

---

## Supported Platforms

- **Windows**: Full support (10, 11 recommended)
- **WSL/Linux**: Partial support (tray icon may not display)
- **macOS**: Not tested

---

## Version History

- **2.4.0** (2026-05-14): Bug-fix release — 37 audit findings closed across 5 high-severity (locked-clipboard crash, OUI download race, autostart now actually functional, hotkey validation, removal of system-wide keyboard hook), plus atomic settings/OUI writes, single-instance check, .ico icon, and dependency hygiene.
- **2.3.0** (2026-02-17): OUI vendor lookup, IEEE database integration, vendor popup, database management UI
- **2.2.0** (2025-12-31): Auto-cycling converter, dark theme UI enhancements, Windows installer
- **2.1.0** (2025-06-07): Persistent settings, Settings dialog, About dialog, admin rights removed
- **2.0.0** (2025-06-06): Stable release with global hotkey and format selector

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

---

## Contributing

To contribute:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## License

MIT License - See [LICENSE.txt](LICENSE.txt) for details

---

## Support

For issues, questions, or suggestions:
- GitHub Issues: https://github.com/aleled/mac-converter-2/issues
- GitHub Repository: https://github.com/aleled/mac-converter-2

---

**Enjoy converting MAC addresses effortlessly! 🎯**
