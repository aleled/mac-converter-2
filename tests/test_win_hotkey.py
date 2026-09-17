"""Tests for win_hotkey — the RegisterHotKey-based global hotkey (v2.5.2).

Replaces the pynput low-level keyboard hook, which intercepted every
keystroke system-wide and broke Razer Synapse macros/shortcuts.
"""

import sys
import threading

import pytest

import win_hotkey
from win_hotkey import MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, parse_hotkey


# --- parse_hotkey -----------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("alt+shift+m", (MOD_ALT | MOD_SHIFT, ord("M"))),
    ("ALT+Shift+M", (MOD_ALT | MOD_SHIFT, ord("M"))),
    (" ctrl + shift + c ", (MOD_CONTROL | MOD_SHIFT, ord("C"))),
    ("control+alt+7", (MOD_CONTROL | MOD_ALT, ord("7"))),
    ("win+shift+x", (MOD_WIN | MOD_SHIFT, ord("X"))),
    ("ctrl+alt+f5", (MOD_CONTROL | MOD_ALT, 0x74)),
    ("ctrl+alt+f24", (MOD_CONTROL | MOD_ALT, 0x87)),
    ("alt+space", (MOD_ALT, 0x20)),
    ("ctrl+shift+pagedown", (MOD_CONTROL | MOD_SHIFT, 0x22)),
])
def test_parse_hotkey_valid(text, expected):
    assert parse_hotkey(text) == expected


@pytest.mark.parametrize("text", [
    "",                # empty
    "   ",             # whitespace
    "m",               # no modifier — would steal a normal key globally
    "alt+shift",       # no key
    "alt+shift+",      # trailing +
    "xyz+abc",         # unknown tokens
    "ctrl+a+b",        # two non-modifier keys
    "alt+alt+m",       # duplicate modifier
    "alt+shift+f25",   # F-key out of range
    None,              # wrong type
])
def test_parse_hotkey_invalid(text):
    with pytest.raises(ValueError):
        parse_hotkey(text)


# --- GlobalHotkey (real Windows registration) -------------------------------

# An obscure chord nobody will have bound, so the test doesn't collide
# with a real app on the dev machine.
_TEST_CHORD = "ctrl+alt+shift+f23"

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Win32 API")


@windows_only
def test_global_hotkey_registers_and_stops_cleanly():
    hk = win_hotkey.GlobalHotkey(_TEST_CHORD, callback=lambda: None)
    hk.start()
    try:
        assert hk.wait_registered(timeout=5) is True
        assert hk.error is None
        assert hk.is_alive()
    finally:
        hk.stop()
    assert not hk.is_alive()


@windows_only
def test_global_hotkey_reports_chord_already_in_use():
    """RegisterHotKey refuses a chord another registration already owns."""
    first = win_hotkey.GlobalHotkey(_TEST_CHORD, callback=lambda: None)
    first.start()
    try:
        assert first.wait_registered(timeout=5) is True

        second = win_hotkey.GlobalHotkey(_TEST_CHORD, callback=lambda: None)
        second.start()
        try:
            assert second.wait_registered(timeout=5) is False
            assert second.error is not None
            assert "in use" in second.error.lower()
        finally:
            second.stop()
    finally:
        first.stop()


@windows_only
def test_global_hotkey_can_reregister_after_stop():
    """stop() must UnregisterHotKey, otherwise a restart would fail as 'in use'."""
    for _ in range(2):
        hk = win_hotkey.GlobalHotkey(_TEST_CHORD, callback=lambda: None)
        hk.start()
        try:
            assert hk.wait_registered(timeout=5) is True
        finally:
            hk.stop()


@windows_only
def test_global_hotkey_fires_callback_on_real_keypress():
    """Inject Ctrl+Alt+Shift+F23 through the OS input stream and confirm WM_HOTKEY reaches the callback."""
    import ctypes
    import time

    fired = threading.Event()
    hk = win_hotkey.GlobalHotkey(_TEST_CHORD, callback=fired.set)
    hk.start()
    try:
        assert hk.wait_registered(timeout=5) is True

        user32 = ctypes.windll.user32
        KEYUP = 0x0002
        VK_CONTROL, VK_MENU, VK_SHIFT, VK_F23 = 0x11, 0x12, 0x10, 0x86
        for vk in (VK_CONTROL, VK_MENU, VK_SHIFT, VK_F23):
            user32.keybd_event(vk, 0, 0, 0)
        time.sleep(0.05)
        for vk in (VK_F23, VK_SHIFT, VK_MENU, VK_CONTROL):
            user32.keybd_event(vk, 0, KEYUP, 0)

        assert fired.wait(timeout=3), "WM_HOTKEY never reached the callback"
    finally:
        hk.stop()


def test_global_hotkey_invalid_string_raises_before_thread_starts():
    with pytest.raises(ValueError):
        win_hotkey.GlobalHotkey("not a hotkey", callback=lambda: None)
