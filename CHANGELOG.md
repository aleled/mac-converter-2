# Git user info for project commits:
# Name: Alejandro Lichtenfeld
# Email: 4leled@gmail.com
# (Set globally in git config as of 2025-06-04)

# Changelog

## [Unreleased]
- Major debug session for selector dialog: added detailed debug output for navigation, selection, and cell state.
- Improved highlight: selected cell now has green background, orange text, and bold font for maximum visibility.
- Navigation logic confirmed: only columns 1 and 2 are selectable, up/down/left/right keys work as intended.
- Reduced dialog spam in console by throttling repeated messages.
- Added cell state printout for further troubleshooting.
- All changes committed and session state saved for seamless continuation.

## [2025-06-04] Major documentation and maintenance update:
- All functions and classes now have detailed docstrings (clipboard_hotkey.py, mac_formats.py, test_mac_formats.py)
- Documented persistent Windows focus bug and all attempted workarounds in TODO.md
- Moved unused/old files (clipboard_hotkey_new.py, clipboard_hotkey_fixed.py, clipboard_hotkey_broken.py) to old/
- Updated README.md, TODO.md, DEVELOPMENT_LOG.md with current state, known issues, and progress
- Removed native table selection/focus border, leaving only custom highlight
- No changes to selector logic or highlight per user request
- All debug output reviewed; only essential debug remains
- All changes pushed to git

---

Each milestone and version will be logged here.
