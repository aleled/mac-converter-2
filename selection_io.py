"""
selection_io.py

Read the text currently selected in the foreground window, and replace it.

Used by the layout-fix hotkey: the user selects mistyped text in whatever app
they're in, presses the hotkey, and the selection is rewritten in place.

## The held-modifier problem

RegisterHotKey delivers WM_HOTKEY the instant the chord matches, while the user
is still physically holding Ctrl and Alt. If we send Ctrl+C right then, the
target application sees Ctrl+Alt+C, because the physical modifier state is
global and the target reads it when our synthetic keystroke arrives. In most
apps that does nothing; in some it triggers a different command entirely.

So before sending anything we wait (briefly) for the user to let go, and
force-release any modifier still down. That is what _settle_modifiers does, and
it is the single most important part of this module. Removing it appears to work
on a fast machine and fails intermittently on a loaded one.

## Everything else that can go wrong, and what we do about it

- The target app writes the clipboard asynchronously after Ctrl+C. Reading
  immediately returns the PREVIOUS clipboard contents. We watch
  GetClipboardSequenceNumber and wait for it to change.
- No change in the sequence number is also how we detect "nothing was selected"
  — a Ctrl+C with no selection is a no-op in every app we care about.
- The clipboard is a shared, single-owner resource; OpenClipboard fails while
  another process holds it. Every access retries briefly.
- The user's clipboard may hold something precious, and may not be text at all
  (an image, files). We snapshot every format, restore it afterwards, and never
  silently discard it.
- Restoring too early races the target app's paste, which reads the clipboard
  asynchronously too. We wait before restoring.
- An elevated foreground window silently ignores SendInput from this
  non-elevated process (UIPI). We detect that as "nothing came back" and report
  failure rather than appearing to succeed.

Nothing here raises to the caller: every entry point returns None/False instead,
because the caller runs on the hotkey message-loop thread.
"""

import sys
import time

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    import win32clipboard
    import win32con

    _u32 = ctypes.WinDLL("user32", use_last_error=True)

    VK_SHIFT, VK_CONTROL, VK_MENU = 0x10, 0x11, 0x12
    VK_LWIN, VK_RWIN = 0x5B, 0x5C
    VK_LSHIFT, VK_RSHIFT = 0xA0, 0xA1
    VK_LCONTROL, VK_RCONTROL = 0xA2, 0xA3
    VK_LMENU, VK_RMENU = 0xA4, 0xA5
    VK_C, VK_V = 0x43, 0x56
    VK_LEFT = 0x25

    # Every modifier that could be held down by a hotkey chord. We release the
    # side-specific keys: releasing only VK_CONTROL leaves VK_LCONTROL down.
    # Release order matters. Only the chord's FINAL key is consumed by
    # RegisterHotKey -- the Ctrl/Alt key-downs already reached the focused
    # window as ordinary key messages. So if Alt goes up alone, that is the
    # canonical "tap Alt" gesture and DefWindowProc turns it into
    # WM_SYSCOMMAND/SC_KEYMENU: the target's menu bar takes focus and the
    # user's next keystrokes go there instead of into their document. A lone
    # Win key-up opens the Start menu for the same reason. Releasing them
    # while a Ctrl is still down keeps them as plain key-ups.
    _HELD_MODIFIERS = (VK_LWIN, VK_RWIN,
                       VK_LMENU, VK_RMENU,
                       VK_LSHIFT, VK_RSHIFT,
                       VK_LCONTROL, VK_RCONTROL)
    _MODIFIER_PROBES = (VK_CONTROL, VK_MENU, VK_SHIFT, VK_LWIN, VK_RWIN)
    # Everything that counts as a modifier, for 'is a real key still down?'
    _MODIFIER_VKS = frozenset(_HELD_MODIFIERS + _MODIFIER_PROBES)

    INPUT_KEYBOARD = 1
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    KEYEVENTF_SCANCODE = 0x0008
    MAPVK_VK_TO_VSC = 0

    # E0-prefixed keys. Without this flag the target is told a DIFFERENT key
    # went up than the one that is down (MapVirtualKeyW returns the same scan
    # code for both sides: 0x1D for either Ctrl, 0x38 for either Alt), so the
    # modifier stays stuck in that application's view of the world.
    _EXTENDED_KEYS = frozenset((VK_RCONTROL, VK_RMENU, VK_LWIN, VK_RWIN, VK_LEFT))

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class _HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        # All three members are required: the union's size is part of the ABI,
        # and SendInput rejects a struct of the wrong size (returns 0).
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]

    class _INPUT(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _u32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    _u32.SendInput.restype = wintypes.UINT
    _u32.GetAsyncKeyState.argtypes = [ctypes.c_int]
    _u32.GetAsyncKeyState.restype = ctypes.c_short
    _u32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    _u32.MapVirtualKeyW.restype = wintypes.UINT
    _u32.GetClipboardSequenceNumber.restype = wintypes.DWORD
else:  # pragma: no cover - Windows-only app; keeps import safe elsewhere
    _u32 = None


# --- timings ---------------------------------------------------------------
# Deliberately generous: these run once per hotkey press, and being slow is far
# better than being wrong. Tuned against Notepad, Chrome and VS Code.

MODIFIER_RELEASE_TIMEOUT_MS = 1000   # how long to wait for the user to let go
CLIPBOARD_SETTLE_MS = 30             # after forcing modifiers up, before sending keys
CLIPBOARD_POLL_MS = 10               # how often to check for a clipboard change
PASTE_SETTLE_MS = 150                # before restoring the clipboard after paste
CLIPBOARD_RETRY_MS = 300             # total time to keep retrying a locked clipboard
RESELECT_MAX_CHARS = 2000            # above this we skip re-selecting after a paste


def _modifiers_down():
    """Any modifier key physically held right now."""
    return [vk for vk in _MODIFIER_PROBES if _u32.GetAsyncKeyState(vk) & 0x8000]


def _send_keys(events):
    """events: list of (vk, is_keyup). Sent as one atomic SendInput batch.

    Scan codes are included because some applications (notably games, remote
    desktop clients and a few Electron apps) read the scan code rather than the
    virtual key.
    """
    arr = (_INPUT * len(events))()
    for i, (vk, up) in enumerate(events):
        arr[i].type = INPUT_KEYBOARD
        arr[i].ki = _KEYBDINPUT(
            wVk=vk,
            wScan=_u32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC),
            dwFlags=((KEYEVENTF_KEYUP if up else 0)
                     | (KEYEVENTF_EXTENDEDKEY if vk in _EXTENDED_KEYS else 0)),
            time=0,
            dwExtraInfo=None,
        )
    sent = _u32.SendInput(len(events), arr, ctypes.sizeof(_INPUT))
    return sent == len(events)


def _non_modifier_held():
    """True if any non-modifier key is physically down right now.

    Mouse buttons are skipped: holding one is not a reason to refuse.
    """
    for vk in range(0x08, 0xFF):
        if vk in _MODIFIER_VKS:
            continue
        if _u32.GetAsyncKeyState(vk) & 0x8000:
            return True
    return False


def _settle_modifiers():
    """Wait for the hotkey's keys to be released. True if the keyboard is clean.

    A deliberate press-and-release is 60-150 ms from key-down to all-keys-up, so
    in almost every real press the user's own key-up clears the state and we
    inject nothing at all. That is by far the safest path, so we wait first.

    If the wait expires, WHY the keyboard is still busy decides what we do:

    - Only modifiers are down (a sticky or remapped key): force them up, in
      _HELD_MODIFIERS order so no lone Alt/Win release opens a menu.

    - A non-modifier is ALSO down, i.e. the user is leaning on the hotkey. We
      must NOT force the modifiers up. Typematic repeat is still generating
      key-downs for that key (~31/s); win32k swallows them only because the
      chord keeps matching a registered hotkey -- MOD_NOREPEAT suppresses the
      duplicate WM_HOTKEY notifications, not the key repeat itself. Break the
      chord by releasing Ctrl and Alt and those repeats get delivered to the
      foreground window as an ordinary character, which REPLACES the selection
      we were about to convert. Aborting costs the user one keypress; forcing
      it through corrupts their text.
    """
    deadline = time.monotonic() + MODIFIER_RELEASE_TIMEOUT_MS / 1000.0
    while time.monotonic() < deadline:
        if not _modifiers_down() and not _non_modifier_held():
            return True
        time.sleep(CLIPBOARD_POLL_MS / 1000.0)

    if _non_modifier_held():
        return False

    _send_keys([(vk, True) for vk in _HELD_MODIFIERS])
    time.sleep(CLIPBOARD_SETTLE_MS / 1000.0)
    return not _modifiers_down()


def _ctrl_chord(vk):
    """Send a clean Ctrl+<vk>, leaving no modifier state behind."""
    return _send_keys([
        (VK_CONTROL, False),
        (vk, False),
        (vk, True),
        (VK_CONTROL, True),
    ])


# --- clipboard -------------------------------------------------------------

def _clipboard_open(write=False):
    """Open the clipboard, retrying while another process holds it."""
    deadline = time.monotonic() + CLIPBOARD_RETRY_MS / 1000.0
    while True:
        try:
            win32clipboard.OpenClipboard()
            return True
        except Exception:
            if time.monotonic() >= deadline:
                return False
            time.sleep(CLIPBOARD_POLL_MS / 1000.0)


def _snapshot_clipboard():
    """Every format currently on the clipboard, as {format_id: bytes-or-str}.

    Returns None if the clipboard couldn't be opened. Formats we can't copy are
    skipped rather than aborting the snapshot — restoring most of it beats
    restoring none of it.
    """
    if not _clipboard_open():
        return None
    data = {}
    try:
        fmt = 0
        while True:
            fmt = win32clipboard.EnumClipboardFormats(fmt)
            if fmt == 0:
                break
            try:
                data[fmt] = win32clipboard.GetClipboardData(fmt)
            except Exception:
                pass  # unsupported/odd format (delayed rendering, ownership)
    except Exception:
        pass
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass
    return data


def _restore_clipboard(snapshot):
    """Put a snapshot back. Best effort; never raises."""
    if snapshot is None:
        return False
    if not _clipboard_open(write=True):
        return False
    try:
        win32clipboard.EmptyClipboard()
        for fmt, value in snapshot.items():
            try:
                win32clipboard.SetClipboardData(fmt, value)
            except Exception:
                pass
        return True
    except Exception:
        return False
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _set_clipboard_text(text):
    if not _clipboard_open(write=True):
        return False
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
        return True
    except Exception:
        return False
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


def _get_clipboard_text():
    if not _clipboard_open():
        return None
    try:
        if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return None
        return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
    except Exception:
        return None
    finally:
        try:
            win32clipboard.CloseClipboard()
        except Exception:
            pass


# --- public API ------------------------------------------------------------

def read_selection(timeout_ms=600):
    """Return the text selected in the foreground window, or None.

    None means: nothing was selected, the app didn't respond to Ctrl+C, the
    selection wasn't text, or the clipboard was unavailable. The caller can't
    distinguish these and doesn't need to — all of them mean "don't proceed".

    The user's clipboard is left exactly as it was.
    """
    if _u32 is None:
        return None
    try:
        if not _settle_modifiers():
            return None

        # Fail closed. If we cannot snapshot the clipboard we must not
        # overwrite it -- the user may have something irreplaceable on there
        # and we would have no way to put it back.
        saved = _snapshot_clipboard()
        if saved is None:
            return None
        before = _u32.GetClipboardSequenceNumber()

        if not _ctrl_chord(VK_C):
            return None

        deadline = time.monotonic() + timeout_ms / 1000.0
        changed = False
        while time.monotonic() < deadline:
            if _u32.GetClipboardSequenceNumber() != before:
                changed = True
                break
            time.sleep(CLIPBOARD_POLL_MS / 1000.0)

        text = _get_clipboard_text() if changed else None
        _restore_clipboard(saved)
        return text or None
    except Exception as e:
        print(f"[selection_io] read_selection: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def _caret_length(text):
    """Caret positions `text` occupies once pasted.

    A CRLF pair is a single line break, so it costs one Left press, not two.
    Lone CR and lone LF already cost one each.
    """
    return len(text) - text.count("\r\n")


def _reselect_left(count):
    """Select `count` characters backwards from the caret with Shift+Left.

    Sent as one SendInput batch so no other input can interleave and leave
    Shift stuck down.
    """
    if count <= 0:
        return True
    events = [(VK_SHIFT, False)]
    for _ in range(count):
        events.append((VK_LEFT, False))
        events.append((VK_LEFT, True))
    events.append((VK_SHIFT, True))
    return _send_keys(events)


def replace_selection(text, reselect=True):
    """Replace the foreground window's selection with `text`. True if sent.

    True means the paste keystroke was delivered and the clipboard restored; it
    cannot guarantee the target app honoured it (nothing can, short of reading
    the app's state back).

    With reselect=True (the default) the pasted text is left selected, so the
    caller can act on it again — that is what makes converting the text back
    possible. Selections longer than RESELECT_MAX_CHARS are left unselected.
    """
    if _u32 is None or text is None:
        return False
    try:
        if not _settle_modifiers():
            return False

        saved = _snapshot_clipboard()
        if saved is None:
            return False          # see read_selection: never clobber unsaved
        if not _set_clipboard_text(text):
            _restore_clipboard(saved)
            return False
        if not _ctrl_chord(VK_V):
            _restore_clipboard(saved)
            return False

        # The target reads the clipboard asynchronously; restoring immediately
        # would race its paste and could paste the OLD clipboard contents.
        time.sleep(PASTE_SETTLE_MS / 1000.0)
        _restore_clipboard(saved)

        # Leave the pasted text selected. Without this the caret sits at the end
        # with nothing selected, so pressing the hotkey again reads an empty
        # selection and the user cannot convert the text back.
        if reselect:
            n = _caret_length(text)
            if n <= RESELECT_MAX_CHARS:
                _reselect_left(n)
        return True
    except Exception as e:
        print(f"[selection_io] replace_selection: {type(e).__name__}: {e}", file=sys.stderr)
        return False
