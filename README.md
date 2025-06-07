> **NOTE:** For future development, always update this file, LICENSE.txt, and requirements.txt whenever new libraries, features, or external code are added. Ensure all legal attributions, author info, and license details are current and correct.

# Git user info for project commits:
# Name: Alejandro Lichtenfeld
# Email: 4leled@gmail.com
# (Set globally in git config as of 2025-06-04)

# MAC Address Converter Utility

A Windows system tray utility for converting MAC addresses between industry formats with a global hotkey and clipboard integration.

## Features
- System tray utility for Windows (and WSL/Linux) to convert and copy MAC addresses in multiple formats.
- Global hotkey (Alt+Shift+M) to trigger the format selector dialog (requires admin on Windows).
- Modern, robust, and visually clear UI/UX with keyboard and mouse navigation.
- Info box always shows the original MAC address from the clipboard.
- Persistent user preferences: autostart, default format, timer, about/credits/license info (settings stored in %APPDATA%/mac-converter-2/settings.json).
- Settings dialog accessible from tray menu (change preferences: autostart, default format, timer, etc.).
- About dialog with app info, author, credits, and MIT license.
- No debug output or legacy code; codebase is clean and production-ready.
- Tray quit is clean and error-free.

## Milestones
- v2.1: Persistent user preferences, settings dialog, about dialog, robust error handling, and documentation polish.
- v2.0: Stable release with all UI/UX, hotkey, and info box improvements.

## Version

Current version: 2.1.0 (feature branch)

## Usage
1. Run as administrator (Windows) for hotkey support.
2. Copy a MAC address to clipboard.
3. Press Alt+Shift+M to open the selector and copy the desired format.

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
- If the clipboard content is not a valid MAC address, it copies "not a valid mac :-)" to the clipboard and keeps waiting for the next hotkey press.
- If the clipboard content is a valid MAC address, it shows the user a window selector dialog.
- When the selector window is displayed:
  - The window is brought to the front and focused over any other window.
  - A timer (default 6 seconds) starts ticking.
  - If the user presses any key, the timer stops permanently.
  - If the timer reaches 0, the window hides and the clipboard remains unchanged.
  - The user can use the arrow keys (up, down, left, right), ESC, and ENTER to navigate, select, or exit.
  - Once a value is selected, it is copied to the clipboard and the window hides (minimized back to the tray bar).

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
