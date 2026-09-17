"""
win_hotkey.py

Global hotkey via the Win32 RegisterHotKey API (v2.5.2).

Why this exists: until v2.5.1 the hotkey used pynput.keyboard.Listener,
which installs a WH_KEYBOARD_LL low-level keyboard hook. Every keystroke
on the machine was routed through a Python callback before any other app
saw it. When the Python process was busy (Qt, OUI database parsing), those
callbacks lagged, Windows' hook timeout kicked in, and keystrokes injected
by other tools were delayed or dropped — most visibly, Razer Synapse
macros and shortcuts stopped working while the app was running.

RegisterHotKey asks Windows to deliver a single WM_HOTKEY message when the
exact chord is pressed. No hook, no per-keystroke code in our process, no
interference with other input tools. Works without admin rights.

Trade-off: Windows refuses to register a chord another application already
owns. GlobalHotkey reports that via .error so the caller can tell the user.

No Qt dependency. The message loop runs on its own thread; the callback is
invoked on that thread, so it must not touch Qt widgets (hand work to the
Qt main thread through a queue, as clipboard_hotkey.handle_hotkey does).
"""

import ctypes
import sys
import threading
from ctypes import wintypes

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000  # don't re-fire while the chord is held down

WM_QUIT = 0x0012
WM_HOTKEY = 0x0312
PM_NOREMOVE = 0x0000
ERROR_HOTKEY_ALREADY_REGISTERED = 1409

_MODIFIERS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "cmd": MOD_WIN,
    "super": MOD_WIN,
}

_NAMED_KEYS = {
    "space": 0x20,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pgup": 0x21,
    "pagedown": 0x22,
    "pgdn": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}


def parse_hotkey(text):
    """Parse 'alt+shift+m' into (modifier_flags, virtual_key_code).

    Accepts modifiers alt / ctrl / control / shift / win / cmd / super,
    exactly one key (a-z, 0-9, f1-f24, or a named key such as space,
    enter, pageup), case-insensitive, whitespace-tolerant.

    Raises ValueError with a user-readable message on anything else.
    At least one modifier is required: a bare global hotkey would swallow
    that key in every application.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Hotkey cannot be empty")

    modifiers = 0
    vk = None
    for raw in text.split("+"):
        token = raw.strip().lower()
        if not token:
            raise ValueError("Hotkey has an empty part (check for a stray '+')")
        if token in _MODIFIERS:
            flag = _MODIFIERS[token]
            if modifiers & flag:
                raise ValueError(f"Modifier '{token}' appears twice")
            modifiers |= flag
            continue
        if vk is not None:
            raise ValueError("Hotkey can only have one non-modifier key")
        vk = _key_to_vk(token)

    if vk is None:
        raise ValueError("Hotkey needs a key after the modifiers (e.g. alt+shift+m)")
    if modifiers == 0:
        raise ValueError("Hotkey needs at least one modifier (alt, ctrl, shift or win)")
    return modifiers, vk


def _key_to_vk(token):
    if len(token) == 1 and ("a" <= token <= "z" or "0" <= token <= "9"):
        return ord(token.upper())
    if token in _NAMED_KEYS:
        return _NAMED_KEYS[token]
    if token.startswith("f") and token[1:].isdigit():
        n = int(token[1:])
        if 1 <= n <= 24:
            return 0x70 + n - 1  # VK_F1 = 0x70 ... VK_F24 = 0x87
    raise ValueError(f"Unknown key '{token}'")


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
    _user32.GetMessageW.argtypes = [ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
    _user32.GetMessageW.restype = wintypes.BOOL
    _user32.PeekMessageW.argtypes = [ctypes.POINTER(_MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT, wintypes.UINT]
    _user32.PeekMessageW.restype = wintypes.BOOL
    _user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
else:
    _user32 = None
    _kernel32 = None


class GlobalHotkey(threading.Thread):
    """Owns one RegisterHotKey registration and the message loop that receives it.

    Usage:
        hk = GlobalHotkey("alt+shift+m", callback=on_hotkey)
        hk.start()
        if not hk.wait_registered(timeout=5):
            show_error(hk.error)
        ...
        hk.stop()   # unregisters and joins

    The constructor parses the hotkey string and raises ValueError if it's
    invalid, so a bad string never starts a thread.
    """

    _HOTKEY_ID = 1  # per-thread id; each GlobalHotkey has its own thread

    def __init__(self, hotkey_text, callback):
        super().__init__(daemon=True, name="GlobalHotkey")
        self.hotkey_text = hotkey_text
        self.modifiers, self.vk = parse_hotkey(hotkey_text)
        self.callback = callback
        self.error = None
        self._registered = False
        self._thread_id = None
        self._ready = threading.Event()

    def run(self):
        if _user32 is None:
            self.error = "Global hotkeys are only supported on Windows"
            self._ready.set()
            return

        msg = _MSG()
        # Force this thread's message queue to exist before anyone can
        # PostThreadMessage to it (stop() relies on that).
        _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_NOREMOVE)
        self._thread_id = _kernel32.GetCurrentThreadId()

        ok = _user32.RegisterHotKey(None, self._HOTKEY_ID, self.modifiers | MOD_NOREPEAT, self.vk)
        if not ok:
            code = ctypes.get_last_error()
            if code == ERROR_HOTKEY_ALREADY_REGISTERED:
                self.error = (f"Hotkey '{self.hotkey_text}' is already in use by "
                              f"another application")
            else:
                self.error = f"Could not register hotkey '{self.hotkey_text}' (Windows error {code})"
            self._ready.set()
            return

        self._registered = True
        self._ready.set()
        try:
            while True:
                result = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if result == 0 or result == -1:  # WM_QUIT or error
                    break
                if msg.message == WM_HOTKEY and msg.wParam == self._HOTKEY_ID:
                    try:
                        self.callback()
                    except Exception as e:  # never let a callback kill the loop
                        print(f"[hotkey] callback error: {type(e).__name__}: {e}",
                              file=sys.stderr)
        finally:
            _user32.UnregisterHotKey(None, self._HOTKEY_ID)
            self._registered = False

    def wait_registered(self, timeout=None):
        """Block until registration succeeded or failed. True if the hotkey is live."""
        self._ready.wait(timeout)
        return self._registered and self.error is None

    def stop(self, timeout=2.0):
        """Unregister the hotkey and end the message loop. Safe to call more than once."""
        if not self.is_alive():
            return
        self._ready.wait(timeout)
        if self._thread_id is not None and _user32 is not None:
            _user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        self.join(timeout)
