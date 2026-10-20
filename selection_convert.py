"""
selection_convert.py

Convert the text the user has SELECTED in any application, in place, without
taking focus and without leaving the clipboard changed.

Design: snapshot / sentinel / verify / rollback. The WM_HOTKEY callback samples
the foreground window and the physical modifier state (microseconds) and hands
them to a persistent worker thread; the worker verifies preconditions,
neutralises held modifiers, snapshots every clipboard format, writes a unique
sentinel, injects Ctrl+C, waits for the target to write the clipboard (sequence
number + owner change, not a fixed sleep), converts, publishes and verifies the
converted text, re-verifies the target, injects Ctrl+V, then restores the
snapshot. Every failure path rolls the clipboard back and notifies; nothing is
left half-applied. Whether the target consumed the paste is not observable on
Windows, so the converted text is also kept in `last_result` for recovery.

No keyboard hook (a WH_KEYBOARD_LL hook was removed in v2.5.2 because it broke
Razer Synapse macros). No Qt. No pyperclip - the clipboard is driven through
user32 directly so sequence numbers, ownership, format enumeration and
open-retries are all under our control. Never touch a Qt widget from here.
"""

import ctypes
import ctypes.wintypes as wintypes
import os
import queue
import sys
import threading
import time
import uuid

# --------------------------------------------------------------------------
# Tunables. Every number is justified in the module docstring of the step
# that uses it; they are also surfaced as settings so a slow RDP/VM session
# can be accommodated without a code change.
# --------------------------------------------------------------------------
MOD_GRACE_MS = 250          # wait this long for the user to let go of the chord
MOD_POLL_MS = 5
MOD_SETTLE_MS = 30          # after injecting modifier key-ups, before re-checking
MOD_ROUNDS = 3              # neutralisation attempts before giving up
PRE_INJECT_SETTLE_MS = 20   # let the target thread drain the key-ups
KEY_HOLD_MS = 8             # how long Ctrl+C / Ctrl+V stay "held"
COPY_TIMEOUT_MS = 600       # how long the target app may take to write the clipboard
COPY_POLL_MS = 10
WRITER_SETTLE_MS = 20       # a multi-format writer bumps the sequence number first
PASTE_SETTLE_MS = 150       # before restoring the clipboard under the paste
CLIP_OPEN_ATTEMPTS = 10     # OpenClipboard retries ...
CLIP_OPEN_DELAY_MS = 20     # ... 10 x 20 ms = 200 ms
COOLDOWN_MS = 300           # swallow a double-fire of the hotkey
WATCHDOG_MS = 5000          # hard ceiling for one operation
MAX_CHARS = 65536           # refuse absurd selections
MAX_SNAPSHOT_BYTES = 64 * 1024 * 1024

# Zero-width space, so that if a sentinel ever does escape onto the clipboard
# (process killed mid-operation) pasting it is invisible rather than noisy.
_SENTINEL_PREFIX = chr(0x200B) + "__macconv_"

# --------------------------------------------------------------------------
# Win32
# --------------------------------------------------------------------------
if sys.platform == "win32":
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
else:  # importable on non-Windows so the test suite can run
    _user32 = _kernel32 = _advapi32 = None

ULONG_PTR = wintypes.WPARAM
LRESULT = ctypes.c_ssize_t

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
MAPVK_VK_TO_VSC = 0

VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_C = 0x43
VK_V = 0x56

# The side-specific VKs are what we inject: a key-up for the generic VK_CONTROL
# does not clear the per-side bits that GetAsyncKeyState/GetKeyState report.
_MODIFIER_VKS = (VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU,
                 VK_LSHIFT, VK_RSHIFT, VK_LWIN, VK_RWIN)
# Generic VKs, checked as well: some drivers only set the generic bit.
_GENERIC_VKS = (VK_CONTROL, VK_MENU, VK_SHIFT)
_EXTENDED_VKS = frozenset((VK_RCONTROL, VK_RMENU, VK_LWIN, VK_RWIN))

_VK_NAMES = {
    VK_LCONTROL: "LCtrl", VK_RCONTROL: "RCtrl", VK_LMENU: "LAlt", VK_RMENU: "RAlt",
    VK_LSHIFT: "LShift", VK_RSHIFT: "RShift", VK_LWIN: "LWin", VK_RWIN: "RWin",
    VK_CONTROL: "Ctrl", VK_MENU: "Alt", VK_SHIFT: "Shift",
}

# Our injected events carry this signature in dwExtraInfo. Nothing in this app
# reads it (there is no hook), but it makes our input identifiable in traces and
# lets a cooperating tool ignore it.
INJECT_SIGNATURE = 0x4D414343  # 'MACC'

CF_TEXT = 1
CF_BITMAP = 2
CF_METAFILEPICT = 3
CF_OEMTEXT = 7
CF_DIB = 8
CF_PALETTE = 9
CF_UNICODETEXT = 13
CF_ENHMETAFILE = 14
CF_LOCALE = 16
CF_DIBV5 = 17
CF_OWNERDISPLAY = 0x0080
CF_DSPTEXT = 0x0081
CF_DSPBITMAP = 0x0082
CF_DSPMETAFILEPICT = 0x0083
CF_DSPENHMETAFILE = 0x008E

# Formats whose clipboard handle is NOT an HGLOBAL, so the bytes cannot be
# copied out and put back. CF_BITMAP/CF_PALETTE are tolerated when a DIB is
# present, because Windows re-synthesises them from CF_DIB/CF_DIBV5.
_HANDLE_FORMATS = frozenset((CF_BITMAP, CF_METAFILEPICT, CF_PALETTE, CF_ENHMETAFILE,
                             CF_OWNERDISPLAY, CF_DSPBITMAP, CF_DSPMETAFILEPICT,
                             CF_DSPENHMETAFILE))
_SYNTH_FROM_DIB = frozenset((CF_BITMAP, CF_PALETTE))

GMEM_MOVEABLE = 0x0002
HWND_MESSAGE = -3
GWL_STYLE = -16
ES_READONLY = 0x0800

GUI_INMENUMODE = 0x00000004
GUI_INMOVESIZE = 0x00000002
GUI_POPUPMENUMODE = 0x00000010
GUI_SYSTEMMENUMODE = 0x00000020

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
TOKEN_QUERY = 0x0008
TokenIntegrityLevel = 25
ERROR_ACCESS_DENIED = 5
ERROR_INSUFFICIENT_BUFFER = 122

# Terminal host window classes. Ctrl+C in a console with no selection is SIGINT,
# so these are refused unless the user opts in.
_CONSOLE_CLASSES = frozenset((
    "ConsoleWindowClass",                  # conhost
    "CASCADIA_HOSTING_WINDOW_CLASS",       # Windows Terminal
    "PseudoConsoleWindow",
    "VirtualConsoleClass",                 # ConEmu
    "mintty",                              # Git Bash
    "PuTTY",
))
_READONLY_EDIT_CLASSES = frozenset((
    "Edit", "RichEdit", "RichEdit20A", "RichEdit20W", "RichEdit50W",
))


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class _GUITHREADINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                ("rcCaret", wintypes.RECT)]


class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


class _TOKEN_MANDATORY_LABEL(ctypes.Structure):
    _fields_ = [("Label", _SID_AND_ATTRIBUTES)]


def _bind():
    u, k, a = _user32, _kernel32, _advapi32
    u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    u.SendInput.restype = wintypes.UINT
    u.GetAsyncKeyState.argtypes = [ctypes.c_int]
    u.GetAsyncKeyState.restype = ctypes.c_short
    u.GetForegroundWindow.restype = wintypes.HWND
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.GetWindowThreadProcessId.restype = wintypes.DWORD
    u.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(_GUITHREADINFO)]
    u.GetGUIThreadInfo.restype = wintypes.BOOL
    u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetClassNameW.restype = ctypes.c_int
    u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetWindowLongW.restype = wintypes.LONG
    u.IsWindow.argtypes = [wintypes.HWND]
    u.IsWindow.restype = wintypes.BOOL
    u.GetKeyboardLayout.argtypes = [wintypes.DWORD]
    u.GetKeyboardLayout.restype = wintypes.HKL
    u.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HKL]
    u.MapVirtualKeyExW.restype = wintypes.UINT
    u.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                  wintypes.DWORD, ctypes.c_int, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, wintypes.HWND,
                                  wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    u.CreateWindowExW.restype = wintypes.HWND
    u.DestroyWindow.argtypes = [wintypes.HWND]
    u.DestroyWindow.restype = wintypes.BOOL
    u.OpenClipboard.argtypes = [wintypes.HWND]
    u.OpenClipboard.restype = wintypes.BOOL
    u.CloseClipboard.restype = wintypes.BOOL
    u.EmptyClipboard.restype = wintypes.BOOL
    u.GetClipboardData.argtypes = [wintypes.UINT]
    u.GetClipboardData.restype = wintypes.HANDLE
    u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u.SetClipboardData.restype = wintypes.HANDLE
    u.EnumClipboardFormats.argtypes = [wintypes.UINT]
    u.EnumClipboardFormats.restype = wintypes.UINT
    u.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
    u.IsClipboardFormatAvailable.restype = wintypes.BOOL
    u.GetClipboardSequenceNumber.restype = wintypes.DWORD
    u.GetClipboardOwner.restype = wintypes.HWND
    u.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    u.RegisterClipboardFormatW.restype = wintypes.UINT
    u.GetClipboardFormatNameW.argtypes = [wintypes.UINT, wintypes.LPWSTR, ctypes.c_int]
    u.GetClipboardFormatNameW.restype = ctypes.c_int

    k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    k.GlobalAlloc.restype = wintypes.HGLOBAL
    k.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k.GlobalLock.restype = wintypes.LPVOID
    k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    k.GlobalUnlock.restype = wintypes.BOOL
    k.GlobalSize.argtypes = [wintypes.HGLOBAL]
    k.GlobalSize.restype = ctypes.c_size_t
    k.GlobalFree.argtypes = [wintypes.HGLOBAL]
    k.GlobalFree.restype = wintypes.HGLOBAL
    k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k.OpenProcess.restype = wintypes.HANDLE
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    k.CloseHandle.restype = wintypes.BOOL
    k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                             wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    k.QueryFullProcessImageNameW.restype = wintypes.BOOL
    k.GetCurrentProcess.restype = wintypes.HANDLE

    a.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                   ctypes.POINTER(wintypes.HANDLE)]
    a.OpenProcessToken.restype = wintypes.BOOL
    a.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID,
                                      wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    a.GetTokenInformation.restype = wintypes.BOOL
    a.GetSidSubAuthorityCount.argtypes = [ctypes.c_void_p]
    a.GetSidSubAuthorityCount.restype = ctypes.POINTER(ctypes.c_ubyte)
    a.GetSidSubAuthority.argtypes = [ctypes.c_void_p, wintypes.DWORD]
    a.GetSidSubAuthority.restype = ctypes.POINTER(wintypes.DWORD)


if _user32 is not None:
    _bind()
    # Registered formats that tell Windows' clipboard history and the cloud
    # clipboard, and well-behaved third-party clipboard managers, to ignore an
    # entry. We tag the sentinel and the converted text with these so the
    # feature does not pollute Win+V or sync intermediate values to the cloud.
    CF_EXCLUDE_MONITOR = _user32.RegisterClipboardFormatW(
        "ExcludeClipboardContentFromMonitorProcessing")
    CF_NO_HISTORY = _user32.RegisterClipboardFormatW("CanIncludeInClipboardHistory")
    CF_NO_CLOUD = _user32.RegisterClipboardFormatW("CanUploadToCloudClipboard")
else:
    CF_EXCLUDE_MONITOR = CF_NO_HISTORY = CF_NO_CLOUD = 0


def _ms(v):
    return v / 1000.0


def _log(msg):
    print(f"[selection] {msg}", file=sys.stderr)


class AbortOperation(Exception):
    """Raised to unwind to the single rollback point. `user_message` is shown."""

    def __init__(self, user_message, detail=None):
        super().__init__(user_message if detail is None else f"{user_message} ({detail})")
        self.user_message = user_message
        self.detail = detail


# ==========================================================================
# Low-level helpers
# ==========================================================================

def _is_down(vk):
    """Physical/async state of a key. Bit 0x8000 = currently down."""
    return bool(_user32.GetAsyncKeyState(vk) & 0x8000)


def _down_modifiers():
    """Every modifier VK currently reported down, side-specific first."""
    return [vk for vk in (_MODIFIER_VKS + _GENERIC_VKS) if _is_down(vk)]


def _scan_code(vk, hkl):
    """Scan code for `vk` under the TARGET window's keyboard layout.

    MapVirtualKeyW would use *our* thread's layout; with Hebrew or Spanish
    active in the target and something else in our process that yields the
    wrong scan code for apps that read scan codes (games, terminals, RDP).
    0 means unknown, and the VK is then injected alone.
    """
    try:
        return _user32.MapVirtualKeyExW(vk, MAPVK_VK_TO_VSC, hkl) or 0
    except OSError:
        return 0


def _send_keys(events, hkl):
    """Inject one atomic batch of (vk, is_up) key events.

    One SendInput call per batch: the batch enters the input stream atomically,
    so physical keystrokes cannot interleave within it. A short return means
    UIPI blocked us (elevated foreground window) or another process called
    BlockInput - both hard failures.
    """
    n = len(events)
    arr = (_INPUT * n)()
    for i, (vk, is_up) in enumerate(events):
        flags = 0
        sc = _scan_code(vk, hkl)
        if sc:
            flags |= KEYEVENTF_SCANCODE
        if vk in _EXTENDED_VKS:
            flags |= KEYEVENTF_EXTENDEDKEY
        if is_up:
            flags |= KEYEVENTF_KEYUP
        arr[i].type = INPUT_KEYBOARD
        # Supplying both wVk and wScan is what a real driver does; with
        # KEYEVENTF_SCANCODE set Windows derives the VK from the scan code
        # under the FOREGROUND layout, which is exactly what we want.
        arr[i].u.ki = _KEYBDINPUT(wVk=vk, wScan=sc, dwFlags=flags, time=0,
                                  dwExtraInfo=INJECT_SIGNATURE)
    ctypes.set_last_error(0)
    sent = _user32.SendInput(n, arr, ctypes.sizeof(_INPUT))
    if sent != n:
        _log(f"SendInput sent {sent}/{n}, err={ctypes.get_last_error()}")
        return False
    return True


def _class_name(hwnd):
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(256)
    if _user32.GetClassNameW(hwnd, buf, 256):
        return buf.value
    return ""


def _gui_info(thread_id):
    gti = _GUITHREADINFO()
    gti.cbSize = ctypes.sizeof(_GUITHREADINFO)
    if not _user32.GetGUIThreadInfo(thread_id, ctypes.byref(gti)):
        return None
    return gti


def _integrity_rid(process_handle):
    """Mandatory integrity level RID of a process, or None if unreadable."""
    token = wintypes.HANDLE()
    if not _advapi32.OpenProcessToken(process_handle, TOKEN_QUERY, ctypes.byref(token)):
        return None
    try:
        need = wintypes.DWORD(0)
        _advapi32.GetTokenInformation(token, TokenIntegrityLevel, None, 0,
                                      ctypes.byref(need))
        if not need.value:
            return None
        buf = ctypes.create_string_buffer(need.value)
        if not _advapi32.GetTokenInformation(token, TokenIntegrityLevel, buf,
                                             need.value, ctypes.byref(need)):
            return None
        label = ctypes.cast(buf, ctypes.POINTER(_TOKEN_MANDATORY_LABEL)).contents
        count_ptr = _advapi32.GetSidSubAuthorityCount(label.Label.Sid)
        if not count_ptr:
            return None
        last = count_ptr.contents.value - 1
        rid_ptr = _advapi32.GetSidSubAuthority(label.Label.Sid, last)
        return rid_ptr.contents.value if rid_ptr else None
    finally:
        _kernel32.CloseHandle(token)


def _own_integrity_rid():
    return _integrity_rid(_kernel32.GetCurrentProcess())


def _process_info(pid):
    """(exe_name, integrity_rid, access_denied) for a pid. Never raises."""
    h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return (None, None, ctypes.get_last_error() == ERROR_ACCESS_DENIED)
    try:
        size = wintypes.DWORD(260)
        buf = ctypes.create_unicode_buffer(size.value)
        name = None
        if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            name = buf.value.split(chr(92))[-1]
        rid = _integrity_rid(h)
        denied = rid is None and ctypes.get_last_error() == ERROR_ACCESS_DENIED
        return (name, rid, denied)
    finally:
        _kernel32.CloseHandle(h)


# ==========================================================================
# Clipboard
# ==========================================================================

class _Clipboard:
    """OpenClipboard/CloseClipboard as a context manager, 10 retries x 20 ms.

    `owner` must be a real HWND: EmptyClipboard() after OpenClipboard(NULL)
    leaves the clipboard owner NULL, which is documented to make
    SetClipboardData fail. The worker owns a message-only window for this.
    """

    def __init__(self, owner):
        self._owner = owner
        self.opened = False

    def __enter__(self):
        for attempt in range(CLIP_OPEN_ATTEMPTS):
            if _user32.OpenClipboard(self._owner):
                self.opened = True
                return self
            time.sleep(_ms(CLIP_OPEN_DELAY_MS))
        err = ctypes.get_last_error()
        raise AbortOperation(
            "Clipboard is locked by another program - try again in a moment",
            f"OpenClipboard failed {CLIP_OPEN_ATTEMPTS}x, err={err}")

    def __exit__(self, *exc):
        if self.opened:
            _user32.CloseClipboard()
            self.opened = False
        return False


def _format_name(fmt):
    if fmt < 0xC000:
        return f"#{fmt}"
    buf = ctypes.create_unicode_buffer(256)
    if _user32.GetClipboardFormatNameW(fmt, buf, 256):
        return buf.value
    return f"#{fmt}"


def _read_unicode_text_locked():
    """CF_UNICODETEXT as str, or None. Clipboard must already be open."""
    h = _user32.GetClipboardData(CF_UNICODETEXT)
    if not h:
        return None
    p = _kernel32.GlobalLock(h)
    if not p:
        return None
    try:
        return ctypes.wstring_at(p)
    finally:
        _kernel32.GlobalUnlock(h)


def _set_text_locked(text, exclude_from_history):
    """Put `text` on the already-emptied, already-open clipboard."""
    data = text.encode("utf-16-le") + bytes(2)   # NUL terminator
    h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
    if not h:
        raise AbortOperation("Out of memory writing the clipboard")
    p = _kernel32.GlobalLock(h)
    if not p:
        _kernel32.GlobalFree(h)
        raise AbortOperation("Out of memory writing the clipboard", "GlobalLock failed")
    ctypes.memmove(p, data, len(data))
    _kernel32.GlobalUnlock(h)
    if not _user32.SetClipboardData(CF_UNICODETEXT, h):
        err = ctypes.get_last_error()
        _kernel32.GlobalFree(h)
        raise AbortOperation("Could not write the clipboard", f"SetClipboardData err={err}")
    if exclude_from_history:
        for fmt in (CF_EXCLUDE_MONITOR, CF_NO_HISTORY, CF_NO_CLOUD):
            if not fmt:
                continue
            hz = _kernel32.GlobalAlloc(GMEM_MOVEABLE, 4)
            if not hz:
                continue
            pz = _kernel32.GlobalLock(hz)
            if pz:
                ctypes.memset(pz, 0, 4)
                _kernel32.GlobalUnlock(hz)
                if not _user32.SetClipboardData(fmt, hz):
                    _kernel32.GlobalFree(hz)
            else:
                _kernel32.GlobalFree(hz)


class ClipboardSnapshot:
    """Byte-level copy of every restorable clipboard format.

    `restorable` is False when the clipboard holds something we provably
    cannot put back (non-HGLOBAL handle, a delay-rendered format the owner
    refused to render, or more than MAX_SNAPSHOT_BYTES). Strict mode then
    refuses the operation rather than destroying the user's clipboard.
    """

    def __init__(self):
        self.formats = []          # [(fmt, bytes)] in enumeration order
        self.text = None           # CF_UNICODETEXT at snapshot time, if any
        self.restorable = True
        self.problems = []
        self.was_empty = False

    @classmethod
    def capture(cls, owner):
        snap = cls()
        with _Clipboard(owner):
            present = []
            fmt = _user32.EnumClipboardFormats(0)
            while fmt:
                present.append(fmt)
                fmt = _user32.EnumClipboardFormats(fmt)
            err = ctypes.get_last_error()
            if not present and err not in (0, ):
                snap.problems.append(f"EnumClipboardFormats err={err}")
            snap.was_empty = not present

            has_dib = (CF_DIB in present) or (CF_DIBV5 in present)
            has_unicode = CF_UNICODETEXT in present
            total = 0
            for fmt in present:
                # Formats Windows re-synthesises for free; copying them back
                # would be wasted work and can confuse consumers.
                if has_unicode and fmt in (CF_TEXT, CF_OEMTEXT, CF_DSPTEXT):
                    continue
                if has_dib and fmt in _SYNTH_FROM_DIB:
                    continue
                if fmt in _HANDLE_FORMATS:
                    snap.restorable = False
                    snap.problems.append(f"{_format_name(fmt)} is not an HGLOBAL")
                    continue
                h = _user32.GetClipboardData(fmt)
                if not h:
                    # Typically a delay-rendered format whose owner declined
                    # to render it. Once we EmptyClipboard it is gone forever.
                    snap.restorable = False
                    snap.problems.append(f"{_format_name(fmt)} did not render")
                    continue
                size = _kernel32.GlobalSize(h)
                if size == 0:
                    snap.formats.append((fmt, b""))
                    continue
                total += size
                if total > MAX_SNAPSHOT_BYTES:
                    snap.restorable = False
                    snap.problems.append(
                        f"clipboard larger than {MAX_SNAPSHOT_BYTES // (1024 * 1024)} MiB")
                    break
                p = _kernel32.GlobalLock(h)
                if not p:
                    snap.restorable = False
                    snap.problems.append(f"{_format_name(fmt)} would not lock")
                    continue
                try:
                    snap.formats.append((fmt, ctypes.string_at(p, size)))
                finally:
                    _kernel32.GlobalUnlock(h)
            if has_unicode:
                snap.text = _read_unicode_text_locked()
        return snap

    def restore(self, owner):
        """Put the snapshot back. Returns True when verified."""
        with _Clipboard(owner):
            if not _user32.EmptyClipboard():
                raise AbortOperation("Could not clear the clipboard for restore",
                                     f"EmptyClipboard err={ctypes.get_last_error()}")
            for fmt, blob in self.formats:
                h = _kernel32.GlobalAlloc(GMEM_MOVEABLE, max(len(blob), 1))
                if not h:
                    continue
                p = _kernel32.GlobalLock(h)
                if not p:
                    _kernel32.GlobalFree(h)
                    continue
                if blob:
                    ctypes.memmove(p, blob, len(blob))
                _kernel32.GlobalUnlock(h)
                if not _user32.SetClipboardData(fmt, h):
                    _kernel32.GlobalFree(h)   # ownership did not transfer
        # Verify the part we can verify.
        if self.text is not None:
            with _Clipboard(owner):
                back = _read_unicode_text_locked()
            return back == self.text
        return True


# ==========================================================================
# The operation
# ==========================================================================

class _Snapshot:
    """What the foreground looked like at the instant the hotkey fired."""

    __slots__ = ("hwnd", "thread_id", "pid", "focus_hwnd", "flags", "hkl",
                 "class_name", "focus_class", "t0")


class SelectionConverter:
    """Owns the worker thread, the clipboard-owner window and the operation.

    convert_fn: pure str -> str (the already-solved layout conversion)
    notify_fn:  callable(message:str, level:str) - must be thread-safe and must
                NOT touch Qt. In this app it pushes onto the queue the Qt main
                thread drains (see integration notes).
    settings_getter: callable(key, default) - live settings lookup.
    """

    def __init__(self, convert_fn, notify_fn, settings_getter=None):
        self._convert = convert_fn
        self._notify = notify_fn
        self._setting = settings_getter or (lambda k, d: d)
        self._q = queue.Queue(maxsize=1)
        self._busy = threading.Lock()
        self._last_done = 0.0
        self._hwnd = None
        self._own_rid = None
        self._thread = threading.Thread(target=self._worker, name="SelectionConvert",
                                        daemon=True)
        self.last_result = None     # recovery: the most recent converted text

    # -- lifecycle ---------------------------------------------------------
    def start(self):
        self._thread.start()
        return self

    def stop(self, timeout=2.0):
        try:
            self._q.put_nowait(None)
        except queue.Full:
            pass
        if self._thread.is_alive():
            self._thread.join(timeout)

    # -- hotkey entry point (runs on the GlobalHotkey message-loop thread) --
    def on_hotkey(self):
        """Must return in well under a millisecond: this is the hotkey thread.

        The foreground window is sampled HERE because the window in front when
        the chord fired is the only correct target.
        """
        if _user32 is None:
            return
        now = time.monotonic()
        if now - self._last_done < _ms(COOLDOWN_MS):
            return                                  # double-fire, ignore silently
        if not self._busy.acquire(blocking=False):
            self._notify("Still working on the previous conversion", "warn")
            return
        try:
            snap = _Snapshot()
            snap.t0 = now
            snap.hwnd = _user32.GetForegroundWindow()
            pid = wintypes.DWORD(0)
            snap.thread_id = _user32.GetWindowThreadProcessId(snap.hwnd,
                                                              ctypes.byref(pid)) if snap.hwnd else 0
            snap.pid = pid.value
            gti = _gui_info(snap.thread_id) if snap.thread_id else None
            snap.focus_hwnd = gti.hwndFocus if gti else None
            snap.flags = gti.flags if gti else 0
            snap.hkl = _user32.GetKeyboardLayout(snap.thread_id) if snap.thread_id else None
            snap.class_name = _class_name(snap.hwnd)
            snap.focus_class = _class_name(snap.focus_hwnd)
            self._q.put_nowait(snap)
        except Exception as e:                      # never kill the hotkey loop
            self._busy.release()
            _log(f"on_hotkey failed: {type(e).__name__}: {e}")

    # -- worker ------------------------------------------------------------
    def _worker(self):
        # A message-only window, created on and owned by this thread, used as
        # the clipboard owner for every OpenClipboard call.
        self._hwnd = _user32.CreateWindowExW(0, "Static", None, 0, 0, 0, 0, 0,
                                             wintypes.HWND(HWND_MESSAGE), None, None, None)
        if not self._hwnd:
            _log(f"CreateWindowExW failed err={ctypes.get_last_error()}; "
                 f"falling back to a NULL clipboard owner")
            self._hwnd = None
        self._own_rid = _own_integrity_rid()
        try:
            while True:
                item = self._q.get()
                if item is None:
                    return
                try:
                    self._run(item)
                except Exception as e:
                    _log(f"unhandled: {type(e).__name__}: {e}")
                    self._notify(f"Conversion failed: {type(e).__name__}", "error")
                finally:
                    self._last_done = time.monotonic()
                    self._busy.release()
        finally:
            if self._hwnd:
                _user32.DestroyWindow(self._hwnd)
                self._hwnd = None

    # -- the eleven steps --------------------------------------------------
    def _run(self, s):
        owner = self._hwnd
        clipboard_dirty = False
        snap = None
        deadline = s.t0 + _ms(WATCHDOG_MS)

        def check_watchdog(stage):
            if time.monotonic() > deadline:
                raise AbortOperation("Took too long - nothing was changed",
                                     f"watchdog at {stage}")

        try:
            # ---- 1. preconditions -------------------------------------
            self._verify_target(s)
            check_watchdog("preconditions")

            # ---- 2. modifiers ------------------------------------------
            self._neutralise_modifiers(s)
            check_watchdog("modifiers")

            # ---- 3. snapshot the clipboard -----------------------------
            snap = ClipboardSnapshot.capture(owner)
            if not snap.restorable and self._setting("selection_strict_clipboard", True):
                raise AbortOperation(
                    "Clipboard holds data I could not put back afterwards "
                    "(image or special format) - copy something else first",
                    "; ".join(snap.problems[:3]))
            if snap.problems:
                _log("snapshot problems: " + "; ".join(snap.problems))
            check_watchdog("snapshot")

            # ---- 4. sentinel -------------------------------------------
            sentinel = _SENTINEL_PREFIX + uuid.uuid4().hex + "__"
            with _Clipboard(owner):
                if not _user32.EmptyClipboard():
                    raise AbortOperation("Could not take the clipboard",
                                         f"EmptyClipboard err={ctypes.get_last_error()}")
                clipboard_dirty = True
                _set_text_locked(sentinel, exclude_from_history=True)
            seq_sentinel = _user32.GetClipboardSequenceNumber()
            check_watchdog("sentinel")

            # ---- 5. Ctrl+C and wait for the app to write ---------------
            self._verify_still_there(s)
            self._assert_modifiers_clear(s)
            time.sleep(_ms(PRE_INJECT_SETTLE_MS))
            self._tap_with_ctrl(VK_C, s)
            selected = self._await_copy(owner, sentinel, seq_sentinel, s,
                                        snap.text or "")
            check_watchdog("copy")

            # ---- 6. convert --------------------------------------------
            if len(selected) > self._setting("selection_max_chars", MAX_CHARS):
                raise AbortOperation(
                    f"Selection is too large "
                    f"({len(selected)} characters, limit "
                    f"{self._setting('selection_max_chars', MAX_CHARS)})")
            try:
                converted = self._convert(selected)
            except Exception as e:
                raise AbortOperation(f"Conversion failed: {type(e).__name__}", str(e))
            if not isinstance(converted, str) or not converted:
                raise AbortOperation("Conversion produced nothing - selection unchanged")
            if converted == selected:
                # Nothing to do. Do not paste: a no-op paste still costs the
                # user an undo step and can scroll or re-wrap the document.
                self._notify("Nothing to convert in the selection", "info")
                return
            self.last_result = converted

            # ---- 7. publish the converted text, verify read-back -------
            with _Clipboard(owner):
                if not _user32.EmptyClipboard():
                    raise AbortOperation("Could not take the clipboard for the paste",
                                         f"EmptyClipboard err={ctypes.get_last_error()}")
                _set_text_locked(converted, exclude_from_history=True)
            with _Clipboard(owner):
                back = _read_unicode_text_locked()
            if back != converted:
                raise AbortOperation(
                    "Another program overwrote the clipboard - nothing was pasted",
                    f"read-back mismatch ({len(back or '')} vs {len(converted)} chars)")
            check_watchdog("publish")

            # ---- 8. re-verify the target, then Ctrl+V ------------------
            # The single most damaging failure would be pasting into the wrong
            # window, so the target is checked again immediately before the
            # injection, not only at the start.
            self._verify_still_there(s)
            self._assert_modifiers_clear(s)
            time.sleep(_ms(PRE_INJECT_SETTLE_MS))
            if not self._tap_with_ctrl(VK_V, s, raise_on_fail=False):
                raise AbortOperation("Windows refused the paste keystroke",
                                     "SendInput short write on Ctrl+V")

            # ---- 9. let the paste land, then restore -------------------
            time.sleep(_ms(self._setting("selection_paste_settle_ms", PASTE_SETTLE_MS)))
            ok = snap.restore(owner)
            if ok:
                self._notify(f"Converted {len(selected)} characters "
                             f"(clipboard restored)", "info")
            else:
                self._notify("Converted, but your original clipboard could not be "
                             "restored - it now holds the converted text", "warn")
            snap = None  # restored; nothing for the rollback to do

        except AbortOperation as e:
            _log(f"abort: {e}")
            if snap is not None and clipboard_dirty:
                self._rollback(snap, owner)
            self._notify(e.user_message, "error")

    # -- step 1 ------------------------------------------------------------
    def _verify_target(self, s):
        if not s.hwnd or not _user32.IsWindow(s.hwnd):
            raise AbortOperation("No active window to convert in")
        if s.pid == 0:
            raise AbortOperation("Could not identify the active window")
        if s.pid == os.getpid():
            raise AbortOperation("The active window belongs to MAC Converter itself")
        if s.flags & (GUI_INMENUMODE | GUI_POPUPMENUMODE | GUI_SYSTEMMENUMODE):
            raise AbortOperation("Close the open menu first, then press the hotkey")
        if s.flags & GUI_INMOVESIZE:
            raise AbortOperation("Finish moving or resizing the window first")
        if not s.focus_hwnd:
            # No focused control: nothing owns a caret or a selection.
            raise AbortOperation("Nothing is focused in the active window")

        exe, rid, denied = _process_info(s.pid)
        if denied or (rid is not None and self._own_rid is not None
                      and rid > self._own_rid):
            raise AbortOperation(
                f"Cannot convert in {exe or 'that window'}: it runs elevated and "
                f"Windows blocks keystrokes from this app",
                f"target IL {rid}, ours {self._own_rid}, denied={denied}")

        in_console = (s.class_name in _CONSOLE_CLASSES
                      or s.focus_class in _CONSOLE_CLASSES)
        if in_console and not self._setting("selection_allow_console", False):
            raise AbortOperation(
                "Not supported in terminal windows: Ctrl+C there would interrupt "
                "the running command",
                f"class={s.class_name!r}/{s.focus_class!r}")

        if s.focus_class in _READONLY_EDIT_CLASSES:
            style = _user32.GetWindowLongW(s.focus_hwnd, GWL_STYLE)
            if style & ES_READONLY:
                raise AbortOperation("That field is read-only - nothing to replace")

    def _verify_still_there(self, s):
        """The foreground and the focused control must be unchanged."""
        if _user32.GetForegroundWindow() != s.hwnd:
            raise AbortOperation("The active window changed - nothing was pasted",
                                 "foreground moved")
        gti = _gui_info(s.thread_id)
        if gti is None:
            raise AbortOperation("The target window stopped responding",
                                 "GetGUIThreadInfo failed")
        if gti.hwndFocus != s.focus_hwnd:
            raise AbortOperation("The focus moved inside the window - nothing was pasted",
                                 "hwndFocus changed")
        if gti.flags & (GUI_INMENUMODE | GUI_POPUPMENUMODE | GUI_SYSTEMMENUMODE
                        | GUI_INMOVESIZE):
            raise AbortOperation("A menu opened in the target window - nothing was pasted")

    # -- step 2: THE MODIFIER PROBLEM --------------------------------------
    def _neutralise_modifiers(self, s):
        """Make the system keyboard state hold NO modifiers before we inject.

        WM_HOTKEY arrives while Ctrl+Alt are still physically down; injecting
        Ctrl+C then reaches the target as Ctrl+Alt+C. Three stages:
        (a) wait up to 250 ms, polling every 5 ms, for the user to let go
            (a real chord is released 30-80 ms after the make; MOD_NOREPEAT
            prevents a re-fire while we wait);
        (b) inject a KEYUP for whatever is still down, side-specific
            (VK_LCONTROL/VK_RCONTROL, never the generic VK_CONTROL, whose
            key-up leaves the per-side bit set). HID keyboards do not
            auto-repeat modifiers, so the injected key-up sticks;
        (c) re-check, up to 3 rounds of 30 ms, then ABORT rather than inject
            into an unknown modifier state.
        """
        grace = _ms(self._setting("selection_modifier_grace_ms", MOD_GRACE_MS))
        end = time.monotonic() + grace
        while time.monotonic() < end:
            if not _down_modifiers():
                return
            time.sleep(_ms(MOD_POLL_MS))

        for round_no in range(MOD_ROUNDS):
            down = _down_modifiers()
            if not down:
                return
            # Only the side-specific VKs are injectable; a generic VK_CONTROL
            # that is down with neither side down means the state is derived,
            # so release both sides.
            targets = [vk for vk in down if vk in _MODIFIER_VKS]
            if not targets:
                targets = []
                if VK_CONTROL in down:
                    targets += [VK_LCONTROL, VK_RCONTROL]
                if VK_MENU in down:
                    targets += [VK_LMENU, VK_RMENU]
                if VK_SHIFT in down:
                    targets += [VK_LSHIFT, VK_RSHIFT]
            _log(f"neutralising round {round_no}: "
                 f"{[_VK_NAMES.get(v, hex(v)) for v in targets]}")
            if not _send_keys([(vk, True) for vk in targets], s.hkl):
                raise AbortOperation(
                    "Windows blocked keyboard input to that window "
                    "(it may be running as administrator)",
                    "SendInput short write on modifier release")
            time.sleep(_ms(MOD_SETTLE_MS))

        still = [_VK_NAMES.get(v, hex(v)) for v in _down_modifiers()]
        raise AbortOperation(
            f"Release {'+'.join(still)} and press the hotkey again",
            "modifiers would not clear")

    def _assert_modifiers_clear(self, s):
        """Cheap re-check right before an injection; one repair attempt."""
        down = _down_modifiers()
        if not down:
            return
        targets = [vk for vk in down if vk in _MODIFIER_VKS] or [
            VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU, VK_LSHIFT, VK_RSHIFT]
        _send_keys([(vk, True) for vk in targets], s.hkl)
        time.sleep(_ms(MOD_SETTLE_MS))
        if _down_modifiers():
            raise AbortOperation(
                "A modifier key is held down - release it and try again",
                f"still down: {[_VK_NAMES.get(v, hex(v)) for v in _down_modifiers()]}")

    def _tap_with_ctrl(self, vk, s, raise_on_fail=True):
        """Ctrl+<vk> as two atomic batches, held KEY_HOLD_MS apart.

        Each batch is atomic (nothing physical can interleave inside one
        SendInput call); the 8 ms gap gives a realistic hold time, because
        RDP, VM guests, DirectInput games and some Java/Qt apps drop a chord
        whose down and up arrive in the same millisecond.
        """
        ok = _send_keys([(VK_LCONTROL, False), (vk, False)], s.hkl)
        time.sleep(_ms(KEY_HOLD_MS))
        ok = _send_keys([(vk, True), (VK_LCONTROL, True)], s.hkl) and ok
        if not ok and raise_on_fail:
            raise AbortOperation(
                "Windows blocked keyboard input to that window "
                "(it may be running as administrator)",
                f"SendInput short write on Ctrl+{chr(vk)}")
        return ok

    # -- step 5: did the app copy anything? --------------------------------
    def _await_copy(self, owner, sentinel, seq_sentinel, s, prior_text):
        """Wait for the target to write the clipboard, and return the text.

        The clipboard write after Ctrl+C is asynchronous, so an immediate read
        returns stale data; and if the selection equals the previous clipboard,
        a content comparison cannot tell "copied" from "nothing selected". The
        sentinel removes the ambiguity: accept only when ALL of
          * GetClipboardSequenceNumber() changed   (somebody wrote)
          * GetClipboardOwner() != our window      (it was not us)
          * the text is no longer the sentinel     (the write carried content)
        If the writer is not the target process (a clipboard manager replaying
        history) we also refuse text identical to the pre-existing clipboard.

        600 ms: Notepad/browsers write in 5-20 ms, Word/Excel 50-300 ms for a
        large selection because they build a dozen formats.
        """
        timeout = _ms(self._setting("selection_copy_timeout_ms", COPY_TIMEOUT_MS))
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            seq = _user32.GetClipboardSequenceNumber()
            cb_owner = _user32.GetClipboardOwner()
            if seq != seq_sentinel and cb_owner != owner:
                # A multi-format writer empties the clipboard (bumping the
                # sequence number) before publishing each format, so do not
                # read the instant the number moves.
                time.sleep(_ms(WRITER_SETTLE_MS))
                with _Clipboard(owner):
                    text = _read_unicode_text_locked()
                if text is not None and text != sentinel and text.strip():
                    writer_pid = wintypes.DWORD(0)
                    if cb_owner:
                        _user32.GetWindowThreadProcessId(cb_owner,
                                                         ctypes.byref(writer_pid))
                    if writer_pid.value in (0, s.pid):
                        return text
                    # Not the target process: most likely a clipboard manager
                    # re-asserting history. Accept only content that cannot be
                    # a replay of what was on the clipboard before we started.
                    if text != prior_text:
                        _log(f"clipboard written by pid {writer_pid.value}, "
                             f"not target {s.pid}; accepting distinct content")
                        return text
            time.sleep(_ms(COPY_POLL_MS))
        raise AbortOperation("Nothing is selected (or this app does not support copy)",
                             f"no clipboard write within {int(timeout * 1000)} ms")

    # -- rollback ----------------------------------------------------------
    def _rollback(self, snap, owner):
        try:
            if snap.was_empty and not snap.formats:
                with _Clipboard(owner):
                    _user32.EmptyClipboard()
                return
            if not snap.restore(owner):
                _log("rollback: restore could not be verified")
        except AbortOperation as e:
            _log(f"rollback failed: {e}")
            self._notify("Your clipboard could not be restored - it may hold "
                         "temporary data from the conversion", "warn")
        except Exception as e:
            _log(f"rollback failed: {type(e).__name__}: {e}")


# ==========================================================================
# Integration helper
# ==========================================================================

def install(convert_fn, notify_fn, settings_getter, hotkey_text, hotkey_module):
    """Wire up a second GlobalHotkey for the selection feature.

    Returns (converter, hotkey) or (converter, None) when registration failed;
    `hotkey.error` then carries the reason. Each GlobalHotkey has its own
    thread and therefore its own hotkey id, so two instances coexist.
    """
    conv = SelectionConverter(convert_fn, notify_fn, settings_getter).start()
    try:
        hk = hotkey_module.GlobalHotkey(hotkey_text, conv.on_hotkey)
    except ValueError as e:
        notify_fn(f"Selection hotkey '{hotkey_text}' is invalid: {e}", "error")
        return conv, None
    hk.start()
    if not hk.wait_registered(timeout=3):
        notify_fn(f"{hk.error}. Choose another selection hotkey in Settings.", "error")
        return conv, hk
    _log(f"selection hotkey '{hotkey_text}' registered")
    return conv, hk
