"""Tests for the selection capture/replace layer.

The interesting part is re-selection after a paste. Without it the caret sits
at the end of the pasted text with nothing selected, so the layout-fix hotkey
cannot act on its own output and the user has no way to convert the text back.
"""
import sys

import pytest

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")

selection_io = pytest.importorskip("selection_io")


# --- caret arithmetic ------------------------------------------------------

@pytest.mark.parametrize("text,expected", [
    ("", 0),
    ("abc", 3),
    ("שלום", 4),        # Hebrew is still one caret step each
    ("a\r\nb", 3),                           # CRLF is ONE line break, not two
    ("a\nb", 3),
    ("a\rb", 3),
    ("\r\n\r\n", 2),
    ("line1\r\nline2\r\n", 12),
])
def test_caret_length(text, expected):
    assert selection_io._caret_length(text) == expected


def test_caret_length_never_exceeds_len():
    for text in ["", "a", "a\r\nb", "\r\n" * 10, "mixed\nendings\r\nhere\r"]:
        assert selection_io._caret_length(text) <= len(text)


# --- the Shift+Left batch --------------------------------------------------

@windows_only
def test_reselect_zero_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(selection_io, "_send_keys", lambda ev: sent.append(ev) or True)
    assert selection_io._reselect_left(0) is True
    assert sent == []


@windows_only
def test_reselect_negative_sends_nothing(monkeypatch):
    sent = []
    monkeypatch.setattr(selection_io, "_send_keys", lambda ev: sent.append(ev) or True)
    assert selection_io._reselect_left(-5) is True
    assert sent == []


@windows_only
def test_reselect_brackets_the_arrows_with_shift(monkeypatch):
    """One batch: Shift down, N x (Left down, Left up), Shift up."""
    sent = []
    monkeypatch.setattr(selection_io, "_send_keys", lambda ev: sent.append(ev) or True)

    selection_io._reselect_left(3)

    assert len(sent) == 1, "must be a single atomic batch"
    events = sent[0]
    assert len(events) == 2 + 2 * 3
    assert events[0] == (selection_io.VK_SHIFT, False), "opens with Shift down"
    assert events[-1] == (selection_io.VK_SHIFT, True), "closes with Shift up"
    arrows = events[1:-1]
    assert all(vk == selection_io.VK_LEFT for vk, _ in arrows)
    # strictly alternating down/up so no key is left pressed
    assert [up for _, up in arrows] == [False, True] * 3


@windows_only
def test_reselect_leaves_no_modifier_held(monkeypatch):
    """Shift must be released in the same batch, or it stays stuck for the user."""
    sent = []
    monkeypatch.setattr(selection_io, "_send_keys", lambda ev: sent.append(ev) or True)
    selection_io._reselect_left(7)
    events = sent[0]
    downs = sum(1 for vk, up in events if vk == selection_io.VK_SHIFT and not up)
    ups = sum(1 for vk, up in events if vk == selection_io.VK_SHIFT and up)
    assert downs == ups == 1


# --- replace_selection's re-selection decision -----------------------------

@pytest.fixture
def stub_paste(monkeypatch):
    """Neutralise everything replace_selection touches except re-selection."""
    calls = {"reselect": []}
    monkeypatch.setattr(selection_io, "_settle_modifiers", lambda: True)
    monkeypatch.setattr(selection_io, "_snapshot_clipboard", lambda: {})
    monkeypatch.setattr(selection_io, "_restore_clipboard", lambda s: None)
    monkeypatch.setattr(selection_io, "_set_clipboard_text", lambda t: True)
    monkeypatch.setattr(selection_io, "_ctrl_chord", lambda vk: True)
    monkeypatch.setattr(selection_io, "PASTE_SETTLE_MS", 0)
    monkeypatch.setattr(selection_io, "_reselect_left",
                        lambda n: calls["reselect"].append(n) or True)
    return calls


@windows_only
def test_replace_reselects_by_default(stub_paste):
    assert selection_io.replace_selection("hello") is True
    assert stub_paste["reselect"] == [5]


@windows_only
def test_replace_reselect_counts_crlf_once(stub_paste):
    selection_io.replace_selection("ab\r\ncd")
    assert stub_paste["reselect"] == [5]


@windows_only
def test_replace_can_opt_out_of_reselecting(stub_paste):
    assert selection_io.replace_selection("hello", reselect=False) is True
    assert stub_paste["reselect"] == []


@windows_only
def test_replace_skips_reselect_above_the_cap(stub_paste):
    """A huge paste would need thousands of arrow presses; don't try."""
    big = "x" * (selection_io.RESELECT_MAX_CHARS + 1)
    assert selection_io.replace_selection(big) is True
    assert stub_paste["reselect"] == [], "should not attempt re-selection"


@windows_only
def test_replace_reselects_exactly_at_the_cap(stub_paste):
    at = "x" * selection_io.RESELECT_MAX_CHARS
    selection_io.replace_selection(at)
    assert stub_paste["reselect"] == [selection_io.RESELECT_MAX_CHARS]


@windows_only
def test_replace_rejects_none():
    assert selection_io.replace_selection(None) is False


# --- fail-closed clipboard handling ----------------------------------------

@windows_only
def test_replace_aborts_when_clipboard_cannot_be_snapshotted(monkeypatch):
    """A clipboard we cannot save must never be overwritten."""
    wrote = []
    monkeypatch.setattr(selection_io, "_settle_modifiers", lambda: True)
    monkeypatch.setattr(selection_io, "_snapshot_clipboard", lambda: None)
    monkeypatch.setattr(selection_io, "_set_clipboard_text",
                        lambda t: wrote.append(t) or True)

    assert selection_io.replace_selection("hello") is False
    assert wrote == [], "must not touch the clipboard it could not save"


@windows_only
def test_read_aborts_when_clipboard_cannot_be_snapshotted(monkeypatch):
    copied = []
    monkeypatch.setattr(selection_io, "_settle_modifiers", lambda: True)
    monkeypatch.setattr(selection_io, "_snapshot_clipboard", lambda: None)
    monkeypatch.setattr(selection_io, "_ctrl_chord",
                        lambda vk: copied.append(vk) or True)

    assert selection_io.read_selection() is None
    assert copied == [], "must not send Ctrl+C if the clipboard is unsaveable"


@windows_only
def test_replace_restores_clipboard_if_setting_text_fails(monkeypatch):
    restored = []
    monkeypatch.setattr(selection_io, "_settle_modifiers", lambda: True)
    monkeypatch.setattr(selection_io, "_snapshot_clipboard", lambda: {"snap": 1})
    monkeypatch.setattr(selection_io, "_set_clipboard_text", lambda t: False)
    monkeypatch.setattr(selection_io, "_restore_clipboard",
                        lambda s: restored.append(s))

    assert selection_io.replace_selection("hello") is False
    assert restored == [{"snap": 1}], "a failed write must still put it back"


# --- modifier release safety ------------------------------------------------

@windows_only
def test_release_order_puts_alt_and_win_before_ctrl():
    """A lone Alt or Win key-up opens a menu; they must go up while Ctrl is down."""
    order = list(selection_io._HELD_MODIFIERS)
    last_altwin = max(order.index(vk) for vk in
                      (selection_io.VK_LMENU, selection_io.VK_RMENU,
                       selection_io.VK_LWIN, selection_io.VK_RWIN))
    first_ctrl = min(order.index(vk) for vk in
                     (selection_io.VK_LCONTROL, selection_io.VK_RCONTROL))
    assert last_altwin < first_ctrl, f"unsafe release order: {order}"


@windows_only
def test_settle_aborts_while_a_non_modifier_is_held(monkeypatch):
    """Leaning on the hotkey must abort, not force the modifiers up.

    Forcing them up breaks the chord, so win32k stops swallowing the key's
    typematic repeats and they land in the user's document as text.
    """
    sent = []
    monkeypatch.setattr(selection_io, "MODIFIER_RELEASE_TIMEOUT_MS", 0)
    monkeypatch.setattr(selection_io, "_modifiers_down", lambda: True)
    monkeypatch.setattr(selection_io, "_non_modifier_held", lambda: True)
    monkeypatch.setattr(selection_io, "_send_keys", lambda ev: sent.append(ev) or True)

    assert selection_io._settle_modifiers() is False
    assert sent == [], "must inject nothing while a real key is down"


@windows_only
def test_settle_force_releases_when_only_modifiers_are_stuck(monkeypatch):
    sent = []
    monkeypatch.setattr(selection_io, "MODIFIER_RELEASE_TIMEOUT_MS", 0)
    monkeypatch.setattr(selection_io, "CLIPBOARD_SETTLE_MS", 0)
    monkeypatch.setattr(selection_io, "_non_modifier_held", lambda: False)
    monkeypatch.setattr(selection_io, "_send_keys", lambda ev: sent.append(ev) or True)

    # Timeout stubbed to 0, so the wait loop is skipped and we go straight to
    # the force-release; _modifiers_down is then called once to confirm it took.
    monkeypatch.setattr(selection_io, "_modifiers_down", lambda: False)

    assert selection_io._settle_modifiers() is True
    assert len(sent) == 1
    assert all(up for _, up in sent[0]), "force-release must be key-ups only"


@windows_only
def test_settle_injects_nothing_when_keyboard_is_already_quiet(monkeypatch):
    """The common case: the user let go, so we touch nothing at all."""
    sent = []
    monkeypatch.setattr(selection_io, "_modifiers_down", lambda: False)
    monkeypatch.setattr(selection_io, "_non_modifier_held", lambda: False)
    monkeypatch.setattr(selection_io, "_send_keys", lambda ev: sent.append(ev) or True)

    assert selection_io._settle_modifiers() is True
    assert sent == []


@windows_only
def test_extended_keys_get_the_e0_flag(monkeypatch):
    """Right Ctrl/Alt, the Win keys and Left arrow are E0-prefixed."""
    for vk in (selection_io.VK_RCONTROL, selection_io.VK_RMENU,
               selection_io.VK_LWIN, selection_io.VK_RWIN, selection_io.VK_LEFT):
        assert vk in selection_io._EXTENDED_KEYS, hex(vk)
    for vk in (selection_io.VK_LCONTROL, selection_io.VK_LMENU,
               selection_io.VK_C, selection_io.VK_V):
        assert vk not in selection_io._EXTENDED_KEYS, hex(vk)
