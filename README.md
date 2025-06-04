# Git user info for project commits:
# Name: Alejandro Lichtenfeld
# Email: 4leled@gmail.com
# (Set globally in git config as of 2025-06-04)

# MAC Address Converter

A Windows system tray utility for converting MAC addresses between industry formats with a global hotkey and clipboard integration.

## Features
- Convert MAC addresses between 8 industry formats (upper/lower case)
- Global hotkey (default: Alt+Shift+M, user-configurable)
- Clipboard integration
- System tray icon with options menu
- User preferences (hotkey, default format, autostart)
- Windows installer and autostart
- Milestone-based development with full documentation

## Roadmap
See `TODO.md` for detailed milestones and features.

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

## Project Status (2025-06-04)
- All code and tests now have thorough docstrings.
- Persistent Windows focus bug is documented in TODO.md and code comments.
- Old/unused files moved to old/ for archival.
- See CHANGELOG.md for full details.
