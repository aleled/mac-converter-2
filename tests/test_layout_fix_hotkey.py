"""Behaviour of the layout-fix hotkey handler in clipboard_hotkey.

selection_io is monkeypatched throughout: these tests never touch the real
clipboard or send real keystrokes.
"""

import sys

import pytest

import clipboard_hotkey as ch

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Win32 keyboard layout API")


class FakeIO:
    """Stands in for selection_io: records what was written, serves what's 'selected'."""

    def __init__(self, selection):
        self.selection = selection
        self.written = []
        self.replace_result = True

    def read_selection(self, timeout_ms=600):
        return self.selection

    def replace_selection(self, text, reselect=True):
        self.written.append(text)
        if self.replace_result:
            self.selection = text  # the app now shows the converted text, as it would
        return self.replace_result


@pytest.fixture
def io_and_notes(monkeypatch):
    """Patch selection_io + notifications, and reset the cycling state."""
    notes = []
    fake = FakeIO("")
    monkeypatch.setattr(ch.selection_io, "read_selection", fake.read_selection)
    monkeypatch.setattr(ch.selection_io, "replace_selection", fake.replace_selection)
    monkeypatch.setattr(ch, "_notify_tray", lambda msg, title=None: notes.append(msg))
    ch._reset_layout_fix_state()
    return fake, notes


def _he_installed():
    import layout_fix
    return any(l.name.lower().startswith("he") for l in layout_fix.installed_layouts())


# --- happy path -------------------------------------------------------------

@windows_only
def test_converts_the_selection_in_place(io_and_notes):
    if not _he_installed():
        pytest.skip("needs he-IL layout")
    fake, notes = io_and_notes
    fake.selection = "akuo"
    ch.handle_layout_fix()
    assert fake.written == ["שלום"]


@windows_only
def test_reverse_direction_also_works(io_and_notes):
    if not _he_installed():
        pytest.skip("needs he-IL layout")
    fake, notes = io_and_notes
    fake.selection = "דישךםצ"
    ch.handle_layout_fix()
    assert fake.written == ["shalom"]


# --- guards -----------------------------------------------------------------

@windows_only
def test_empty_selection_writes_nothing_and_tells_the_user(io_and_notes):
    fake, notes = io_and_notes
    fake.selection = ""
    ch.handle_layout_fix()
    assert fake.written == []
    assert notes and "select" in notes[0].lower()


@windows_only
def test_failed_capture_writes_nothing(io_and_notes):
    fake, notes = io_and_notes
    fake.selection = None  # selection_io reports failure
    ch.handle_layout_fix()
    assert fake.written == []
    assert notes


@windows_only
def test_unconvertible_selection_is_left_alone(io_and_notes):
    fake, notes = io_and_notes
    fake.selection = "12345"
    ch.handle_layout_fix()
    assert fake.written == []
    assert notes


@windows_only
def test_oversized_selection_is_refused(io_and_notes):
    """A whole document selected by accident must not be rewritten."""
    fake, notes = io_and_notes
    fake.selection = "a" * (ch.LAYOUT_FIX_MAX_CHARS + 1)
    ch.handle_layout_fix()
    assert fake.written == []
    assert notes and "too" in notes[0].lower()


@windows_only
def test_replace_failure_is_reported_and_state_not_advanced(io_and_notes):
    if not _he_installed():
        pytest.skip("needs he-IL layout")
    fake, notes = io_and_notes
    fake.selection = "akuo"
    fake.replace_result = False
    ch.handle_layout_fix()
    assert notes
    # a failed write must not be remembered as "our output"
    fake.replace_result = True
    fake.selection = "akuo"
    ch.handle_layout_fix()
    assert fake.written[-1] == "שלום"


# --- cycling ----------------------------------------------------------------

@windows_only
def test_pressing_again_reverses_or_cycles(io_and_notes):
    """A second press must never reproduce the first result.

    With two layouts there is a single candidate, so pressing again converts
    what is on screen and the text returns to what the user typed. With three
    or more layouts it walks to a different candidate instead. Either way,
    pressing again has to visibly change something -- the old behaviour wrapped
    straight back to the same answer, which read as the hotkey being dead.
    """
    if not _he_installed():
        pytest.skip("needs he-IL layout")
    import layout_fix
    fake, notes = io_and_notes
    fake.selection = "akuo"

    ch.handle_layout_fix()          # press 1
    first = fake.written[-1]
    ch.handle_layout_fix()          # press 2, selection is now `first`
    second = fake.written[-1]

    assert second != first, "a second press must change the text"

    n = layout_fix.fix_text("akuo").candidate_count
    if n == 1:
        assert second == "akuo", "two layouts: pressing again returns the original"


@windows_only
def test_reverse_round_trip_is_stable_over_several_presses(io_and_notes):
    """Press four times on two layouts and you should land back where you started."""
    if not _he_installed():
        pytest.skip("needs he-IL layout")
    import layout_fix
    if layout_fix.fix_text("akuo").candidate_count != 1:
        pytest.skip("needs exactly one candidate (two installed layouts)")
    fake, notes = io_and_notes
    fake.selection = "akuo"

    seen = []
    for _ in range(4):
        ch.handle_layout_fix()
        seen.append(fake.written[-1])

    converted = seen[0]
    assert seen == [converted, "akuo", converted, "akuo"], seen


@windows_only
def test_editing_between_presses_starts_a_fresh_cycle(io_and_notes):
    if not _he_installed():
        pytest.skip("needs he-IL layout")
    fake, notes = io_and_notes
    fake.selection = "akuo"
    ch.handle_layout_fix()
    assert fake.written[-1] == "שלום"

    fake.selection = "nhbe"  # user selected different text
    ch.handle_layout_fix()
    assert fake.written[-1] == "מינק"   # converted from scratch, not cycled


# --- the notification -------------------------------------------------------

@windows_only
def test_notification_truncates_long_text(io_and_notes):
    """The selection can be sensitive; don't splash all of it across the screen."""
    if not _he_installed():
        pytest.skip("needs he-IL layout")
    fake, notes = io_and_notes
    fake.selection = "akuo " * 60
    ch.handle_layout_fix()
    assert notes
    assert len(notes[0]) < 200
