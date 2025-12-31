> **NOTE:** For future development, always update this file, LICENSE.txt, and requirements.txt whenever new libraries, features, or external code are added. Ensure all legal attributions, author info, and license details are current and correct.

# Git user info for project commits:
# Name: Alejandro Lichtenfeld
# Email: 4leled@gmail.com
# (Set globally in git config as of 2025-06-04)

# MAC Address Converter Utility

> **NOTE:** As of v2.2.0, the app no longer requires administrator rights for global hotkey functionality. The hotkey system now uses pynput, which works without elevation. All future development must preserve this constraint: **the app must never require admin rights to run or register hotkeys.**

A Windows system tray utility for converting MAC addresses between industry formats with a global hotkey, auto-cycling format selection, and clipboard integration.

## Features
- System tray utility for Windows (and WSL/Linux) to convert and copy MAC addresses in multiple formats.
- Global hotkey (configurable, default Alt+Shift+M) to auto-cycle through MAC address formats (**no admin required**).
- Auto-cycling: Each hotkey press converts to the next format (cycles through 10 formats: colon-separated, hyphen-separated, dot-separated, plain, in uppercase/lowercase variants).
- Tray notifications showing converted MAC address (configurable duration, default 3 seconds).
- Error notifications for invalid MAC addresses in clipboard.
- Configurable hotkey: Change global hotkey via Settings dialog (e.g., alt+shift+m, ctrl+shift+c).
- Configurable notification duration (1-10 seconds).
- Persistent user preferences: autostart, hotkey, notification duration, about/credits/license info (settings stored in %APPDATA%/mac-converter-2/settings.json).
- Settings dialog accessible from tray menu.
- About dialog with app info, author, credits, and MIT license.
- Clean, production-ready codebase with no legacy dialog selector.

## Design Constraints
- **No admin rights required:** The app must never require administrator privileges to run or register hotkeys. All hotkey and tray functionality must work for standard users.

## Milestones
- v2.1: Persistent user preferences, settings dialog, about dialog, robust error handling, and documentation polish.
- v2.0: Stable release with all UI/UX, hotkey, and info box improvements.

## Version

Current version: 2.2.0 (auto-cycling with notifications)

## Usage
1. Run the app (no admin required).
2. Copy a MAC address to clipboard.
3. Press the configured hotkey (default Alt+Shift+M) to auto-convert to the next format.
4. A tray notification shows the converted MAC address (auto-dismisses after configured duration).
5. The converted MAC is automatically copied to clipboard, ready to paste immediately.

## Roadmap / TODO (as of 2025-06-04)
- [ ] Implement persistent settings (hotkey, timeout, default MAC format) with both a config file (standardized location, e.g. %APPDATA%/mac-converter-2/settings.json) and a settings dialog accessible from the tray menu.
    - Settings must persist between app executions.
    - When packaging as an installer, ensure settings are stored in a user-writable, standard location.
- [ ] Add notification (popup or sound) when a MAC address is converted (user-configurable in settings). [Planned, not started]
- [ ] Full Windows installer (Start Menu shortcut, autostart, per-user/system-wide install) [Planned, not started]
- [ ] Add screenshots/GIFs and troubleshooting section to README.md [Planned, not started]
- [ ] Revisit release planning and cross-platform support at a later stage.

## Setup (Development)
1. Clone the repository
2. Create a virtual environment:
   ```zsh
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install requirements:
   ```zsh
   pip install -r requirements.txt
   ```

## Environment Setup (Every Session)
> **IMPORTANT:**
> Before working on this project, always activate the Python virtual environment:
> 
> ```zsh
> source ./env_load.sh
> ```
> 
> This ensures all dependencies are available and the environment is isolated.

## Packaging
- Will use PyInstaller for .exe generation
- Installer will be created for Windows

## Documentation
- See `DEVELOPMENT_LOG.md` for session logs
- See `CHANGELOG.md` for version history

## Git Remote Setup (Windows/PowerShell)

If you need to update your remote repository URL (for example, after creating a new GitHub repo), use the following command in your project directory:

```powershell
git remote set-url origin https://github.com/aleled/mac-converter-2.git
```

This will point your local repository to the correct remote on GitHub. After this, you can use `git push`, `git pull`, and other git commands as usual.

## Application Behavior

- When the app executes, it resides in memory and waits for the global hotkey.
- When the hotkey is pressed, it reads the last entry from the clipboard.
- If the clipboard content is not a valid MAC address, a tray notification displays "No valid MAC address in clipboard" for the configured duration (default 3 seconds), and the app resumes waiting for the next hotkey press.
- If the clipboard content is a valid MAC address:
  - The app auto-cycles to the next format (index 0→1→2→...→9→0).
  - The converted MAC address is copied to the clipboard.
  - A tray notification displays the converted MAC address for the configured duration.
  - The user can immediately paste the converted MAC address.
  - Each subsequent hotkey press cycles to the next format in the sequence.

## Debugging and UI/UX Improvements (2025-06-05)
- Selector dialog navigation and highlight logic are robust and debugged.
- Only columns 1 and 2 are selectable; highlight is green with orange text and bold font.
- Debug output is present for troubleshooting and will be removed in the next session.
- Session state and progress are preserved for seamless continuation.

## Project Status (2025-06-04)
- All code and tests now have thorough docstrings.
- Persistent Windows focus bug is documented in TODO.md and code comments.
- Old/unused files moved to old/ for archival.
- See CHANGELOG.md for full details.

## HOW TO COOK: General Guidelines

1. The hotkey opens a window, referred to as the "main window".
2. The tray menu opens other windows such as About, Settings, and possibly future ones (names TBD).
3. Each window is independent from the others. No shared functions, callbacks, timers, or deadlocks. The only thing in common is the UI/UX design look and feel.
4. The hotkey must not interfere in any way with the operation of any other app element, keys, bindings, or block execution.
5. If any window launched from the tray menu is open, it will not allow moving to any other window until it is closed.
6. Every window should have common control buttons like Close, Minimize, etc.

See also: TODO.md and DEVELOPMENT_LOG.md for implementation notes.

## UI/UX Design Guidelines for MAC Address Formatter App

### Layout and Appearance

```
+-----------------------------------------------------------+
| icon  MAC Address Formatter App                  [_] [X]  |
+-----------------------------------------------------------+
| Select the MAC address format to copy to clipboard        |
+-----------------------------------------------------------+
| [column 1]       | [column 2]         | [column 3]        |
| FORMAT STYLE     | LOWER CASE         | UPPER CASE        |
|------------------+--------------------+-------------------|
| Colon-separated  | aa:bb:cc:dd:ee:ff  | AA:BB:CC:DD:EE:FF |
| Hyphen-separated | aa-bb-cc-dd-ee-ff  | AA-BB-CC-DD-EE-FF |
| Dot-separated    | aabb.ccdd.eeff     | AABB.CCDD.EEFF    |
| Plain            | aabbccddeeff       | AABBCCDDEEFF      |
+-----------------------------------------------------------+

INFORMATION:
| [label] [information                   ] |

Controls:

[ Arrow Keys  ] [ Navigate Up/Down/Left/Right ]
[ Esc / Enter ] [ Cancel Selection / Confirm  ]
[ Tab         ] [ Switch Between Fields       ]


- column1 - width for entire column and row should be the same, min width as largest string in that row.
- column2 - width for entire column and row should be the same, min width as largest string in that row.
- column3 - width for entire column and row should be the same, min width as largest string in that row.

```

### Color and Theme Guidelines
- **Background:** Deep dark gray (`#23272e`), with lighter dark for info areas (`#181a20`).
- **Headers/Labels:** Orange (`#ffb347`) for section headers and format names.
- **Highlight:** Green (`#39d353`) for the selected cell background, with purple (`#b266ff`) text.
- **Text:** White (`#fff`) for normal text, purple (`#b266ff`) for info and highlights.
- **Borders:** Subtle gray (`#444`) for cell and header separators.
- **Font:** Use monospace (Consolas) for MAC addresses, bold for headers.

### UX Guidelines
- All headers and cells are left-aligned for clarity.
- Consistent cell and header widths for perfect column alignment.
- Info/instructions always visible at the top.
- Keyboard and mouse navigation supported.
- Dialog always appears on top and receives focus.
- Controls and instructions are always visible and clear.

### Controls
- **Arrow Keys:** Navigate between cells.
- **Enter/Click:** Copy selected MAC format to clipboard.
- **Esc:** Cancel/close dialog.
- **Tab:** Switch between fields (future: for accessibility).

> **Maintain these guidelines for all future UI/UX iterations.**
