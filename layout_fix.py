"""
layout_fix.py

Fix text typed with the wrong keyboard layout active.

You meant to type Hebrew, but the US layout was active, so "shalom" came out as
"akuo" instead of "שלום". Every character here was produced by a physical key:
reinterpret those same keys under a different layout and the intended text comes
back.

The mapping is derived from Windows at run time, never hard-coded, so it works
for whatever layouts the user has installed:

    VkKeyScanExW(ch, src)      char -> which physical key + shift state produces it
    ToUnicodeEx(vk, .., dst)   that same key + shift state -> char in the other layout

Pure logic plus Win32 layout queries. No Qt, no clipboard, no input injection —
see selection_io.py for getting text out of and back into the foreground window.

Limits, by construction:
- One character per keypress. AltGr/Ctrl combinations are skipped, so characters
  that need them pass through unchanged.
- Dead keys (Spanish ´ + a = á) are not composed; those characters pass through.
- A handful of punctuation keys are not 1:1 between layouts (US "/" and "`" both
  land on Hebrew keys that map back to "." and ";"). Letters and digits are exact.
"""

import sys
from collections import namedtuple

Layout = namedtuple("Layout", "hkl langid name")
FixResult = namedtuple("FixResult", "text src dst candidate_count")

SHIFT, CTRL, ALT = 0x01, 0x02, 0x04
MAPVK_VK_TO_VSC = 0

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _u32 = ctypes.WinDLL("user32", use_last_error=True)
    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)

    _u32.GetKeyboardLayoutList.argtypes = [ctypes.c_int, ctypes.POINTER(wintypes.HKL)]
    _u32.GetKeyboardLayoutList.restype = ctypes.c_int
    _u32.GetKeyboardLayout.argtypes = [wintypes.DWORD]
    _u32.GetKeyboardLayout.restype = wintypes.HKL
    _u32.VkKeyScanExW.argtypes = [wintypes.WCHAR, wintypes.HKL]
    _u32.VkKeyScanExW.restype = ctypes.c_short
    _u32.MapVirtualKeyExW.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HKL]
    _u32.MapVirtualKeyExW.restype = wintypes.UINT
    _u32.ToUnicodeEx.argtypes = [wintypes.UINT, wintypes.UINT,
                                 ctypes.POINTER(ctypes.c_ubyte),
                                 ctypes.POINTER(ctypes.c_wchar), ctypes.c_int,
                                 wintypes.UINT, wintypes.HKL]
    _u32.ToUnicodeEx.restype = ctypes.c_int
    _k32.LCIDToLocaleName.argtypes = [wintypes.LCID, ctypes.c_wchar_p,
                                      ctypes.c_int, wintypes.DWORD]
    _k32.LCIDToLocaleName.restype = ctypes.c_int
else:  # pragma: no cover - the app is Windows-only; this keeps imports safe
    _u32 = _k32 = None


def installed_layouts():
    """Every keyboard layout currently installed, in Windows' own order."""
    if _u32 is None:
        return []
    n = _u32.GetKeyboardLayoutList(0, None)
    if n <= 0:
        return []
    buf = (wintypes.HKL * n)()
    _u32.GetKeyboardLayoutList(n, buf)
    out, seen = [], set()
    for hkl in buf[:n]:
        hkl = int(hkl)
        if hkl in seen:
            continue
        seen.add(hkl)
        langid = hkl & 0xFFFF
        name = ctypes.create_unicode_buffer(85)
        got = _k32.LCIDToLocaleName(langid, name, 85, 0)
        out.append(Layout(hkl, langid, name.value if got else f"0x{langid:04X}"))
    return out


def active_layout_hkl():
    """HKL of the layout active in the foreground thread, or None."""
    if _u32 is None:
        return None
    return int(_u32.GetKeyboardLayout(0)) or None


def char_to_key(ch, hkl):
    """(vk, shift_state) that types `ch` under `hkl`, or None if it can't."""
    if _u32 is None:
        return None
    r = _u32.VkKeyScanExW(ch, hkl)
    if r == -1:
        return None
    vk, state = r & 0xFF, (r >> 8) & 0xFF
    if state & (CTRL | ALT):
        return None  # AltGr/Ctrl combos: not a plain keypress, leave alone
    return vk, state


def key_to_char(vk, state, hkl):
    """Character produced by (vk, shift_state) under `hkl`, or None."""
    if _u32 is None:
        return None
    ks = (ctypes.c_ubyte * 256)()
    if state & SHIFT:
        ks[0x10] = 0x80
    scan = _u32.MapVirtualKeyExW(vk, MAPVK_VK_TO_VSC, hkl)
    buf = ctypes.create_unicode_buffer(8)
    n = _u32.ToUnicodeEx(vk, scan, ks, buf, 8, 0, hkl)
    if n < 0:
        # Dead key. It left composition state in the kernel for this layout;
        # call again with the same key to flush it so later lookups are clean.
        _u32.ToUnicodeEx(vk, scan, ks, buf, 8, 0, hkl)
        return None
    return buf.value[0] if n >= 1 and buf.value else None


def convert(text, src_hkl, dst_hkl):
    """Reinterpret `text`'s keystrokes from layout `src_hkl` under `dst_hkl`.

    Characters that can't be mapped pass through unchanged, so the result is
    always the same length as the input.
    """
    if not text or src_hkl == dst_hkl:
        return text
    out = []
    for ch in text:
        key = char_to_key(ch, src_hkl)
        if key is None:
            out.append(ch)
            continue
        mapped = key_to_char(key[0], key[1], dst_hkl)
        out.append(mapped if mapped is not None else ch)
    return "".join(out)


def _scorable(ch):
    """Characters that actually discriminate between layouts.

    Digits, whitespace and most punctuation sit on the same keys everywhere, so
    counting them would make every layout look equally plausible.
    """
    return ch.isalpha()


def typeable_score(text, hkl):
    """Fraction of letters in `text` that this layout can type (0.0-1.0).

    1.0 means the text looks like it was typed under this layout; 0.0 means it
    certainly wasn't. Text with no letters scores 0.0.
    """
    letters = [c for c in text if _scorable(c)]
    if not letters:
        return 0.0
    return sum(1 for c in letters if char_to_key(c, hkl) is not None) / len(letters)


def candidates(text, layouts=None):
    """Plausible (src, dst, converted) fixes for `text`, best first.

    Source layouts are ranked by how well the text matches what they can type,
    so Hebrew characters are recognised as Hebrew-typed and Latin as Latin-typed.
    Conversions that change nothing are dropped — they are never a useful offer.
    """
    if not text or not text.strip():
        return []
    if layouts is None:
        layouts = installed_layouts()
    if len(layouts) < 2:
        return []

    scored = sorted(((typeable_score(text, l.hkl), i, l) for i, l in enumerate(layouts)),
                    key=lambda t: (-t[0], t[1]))
    active = active_layout_hkl()

    out, seen = [], set()
    for score, _, src in scored:
        if score <= 0.0:
            continue  # this layout cannot have produced the text at all
        # Prefer sending to the layout the user is NOT currently in; among the
        # rest keep Windows' own ordering, which matches the user's switch order.
        dsts = sorted((l for l in layouts if l.hkl != src.hkl),
                      key=lambda l: (l.hkl == active, layouts.index(l)))
        for dst in dsts:
            converted = convert(text, src.hkl, dst.hkl)
            if converted == text or converted in seen:
                continue
            seen.add(converted)
            out.append((src, dst, converted))
    return out


def fix_text(text, layouts=None, skip=0):
    """Best guess at what `text` was meant to be, or None if there's nothing to offer.

    `skip` walks further down the candidate list and wraps, so a hotkey pressed
    repeatedly cycles through the alternatives.
    """
    cands = candidates(text, layouts)
    if not cands:
        return None
    src, dst, converted = cands[skip % len(cands)]
    return FixResult(converted, src, dst, len(cands))
