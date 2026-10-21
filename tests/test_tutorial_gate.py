"""When the first-launch tutorial is shown, and when it is remembered.

The user's complaint was that it reappeared at every launch. The flag used to
be written after the dialog closed, so anything that ended the process while
the tutorial was on screen left it unrecorded. It is now written first.
"""
import pytest

import clipboard_hotkey as ch


class FakeDemo:
    """Stands in for the shortcut_demo module."""

    def __init__(self, on_show=None, raises=False):
        self.shown = []
        self.demos = []
        self._on_show = on_show
        self._raises = raises

    def show_tutorial(self, mac_hotkey, layout_hotkey, parent=None):
        if self._on_show is not None:
            self._on_show()
        if self._raises:
            raise RuntimeError("display failed")
        self.shown.append((mac_hotkey, layout_hotkey))

    def show_demos(self, mac_hotkey, layout_hotkey, parent=None):
        self.demos.append((mac_hotkey, layout_hotkey))


@pytest.fixture
def gate(monkeypatch):
    """Isolate the settings dict and the save, and capture notifications."""
    saved = []
    notes = []
    monkeypatch.setattr(ch, "settings", dict(ch.DEFAULT_SETTINGS), raising=False)
    monkeypatch.setattr(ch, "save_settings", lambda s: saved.append(dict(s)))
    monkeypatch.setattr(ch, "_notify_tray", lambda msg, title=None: notes.append(msg))
    ch.settings["tutorial_shown"] = False
    return saved, notes


# --- recording the flag ----------------------------------------------------

def test_record_sets_and_saves(gate):
    saved, _ = gate
    ch._record_tutorial_shown()
    assert ch.settings["tutorial_shown"] is True
    assert len(saved) == 1
    assert saved[0]["tutorial_shown"] is True


def test_record_is_idempotent(gate):
    """Re-running the tutorial from the menu must not rewrite settings."""
    saved, _ = gate
    ch._record_tutorial_shown()
    ch._record_tutorial_shown()
    ch._record_tutorial_shown()
    assert len(saved) == 1, "should only write the first time"


def test_record_survives_a_failing_save(gate, monkeypatch):
    def boom(_s):
        raise OSError("disk full")
    monkeypatch.setattr(ch, "save_settings", boom)
    ch._record_tutorial_shown()          # must not raise
    assert ch.settings["tutorial_shown"] is True


# --- the ordering that was the actual bug ----------------------------------

def test_flag_is_written_before_the_dialog_opens(gate, monkeypatch):
    """The whole point of the fix: by the time the dialog runs, it is recorded.

    If the process dies while the tutorial is on screen, the user has still
    seen it and it will not reappear at the next launch.
    """
    seen_during_show = {}

    def on_show():
        seen_during_show["flag"] = ch.settings.get("tutorial_shown")

    fake = FakeDemo(on_show=on_show)
    monkeypatch.setattr(ch, "shortcut_demo", fake)

    ch.show_first_launch_tutorial()

    assert seen_during_show["flag"] is True, "flag must already be set while showing"
    assert fake.shown, "the tutorial must still actually be shown"


def test_flag_stays_set_if_the_dialog_raises(gate, monkeypatch):
    """A broken dialog must not cause a retry at every launch."""
    fake = FakeDemo(raises=True)
    monkeypatch.setattr(ch, "shortcut_demo", fake)

    ch.show_first_launch_tutorial()      # must not propagate

    assert ch.settings["tutorial_shown"] is True


# --- re-running from the tray menu -----------------------------------------

def test_menu_rerun_works_even_though_the_flag_is_set(gate, monkeypatch):
    fake = FakeDemo()
    monkeypatch.setattr(ch, "shortcut_demo", fake)
    ch.settings["tutorial_shown"] = True

    ch.show_tutorial_dialog()

    assert len(fake.shown) == 1, "the menu item must ignore the flag"


def test_menu_rerun_does_not_touch_settings(gate, monkeypatch):
    saved, _ = gate
    monkeypatch.setattr(ch, "shortcut_demo", FakeDemo())
    ch.settings["tutorial_shown"] = True

    ch.show_tutorial_dialog()

    assert saved == [], "re-running is not a settings change"


def test_rerun_passes_the_configured_hotkeys(gate, monkeypatch):
    fake = FakeDemo()
    monkeypatch.setattr(ch, "shortcut_demo", fake)
    ch.settings["hotkey"] = "ctrl+shift+9"
    ch.settings["layout_fix_hotkey"] = "ctrl+alt+k"

    ch.show_tutorial_dialog()

    assert fake.shown == [("ctrl+shift+9", "ctrl+alt+k")]


# --- the module being absent ------------------------------------------------

def test_missing_module_notifies_instead_of_crashing(gate, monkeypatch):
    _saved, notes = gate
    monkeypatch.setattr(ch, "shortcut_demo", None)

    ch.show_tutorial_dialog()

    assert notes, "the user should be told, not left guessing"
    assert "unavailable" in notes[0].lower()


def test_missing_module_still_records_on_first_launch(gate, monkeypatch):
    """Otherwise a build without the module retries forever."""
    monkeypatch.setattr(ch, "shortcut_demo", None)
    ch.show_first_launch_tutorial()
    assert ch.settings["tutorial_shown"] is True


def test_demos_are_independent_of_the_tutorial_flag(gate, monkeypatch):
    fake = FakeDemo()
    monkeypatch.setattr(ch, "shortcut_demo", fake)
    ch.settings["tutorial_shown"] = False

    ch.show_shortcut_demos()

    assert len(fake.demos) == 1


# --- the setting itself -----------------------------------------------------

def test_tutorial_shown_defaults_to_false():
    assert ch.DEFAULT_SETTINGS["tutorial_shown"] is False


@pytest.mark.parametrize("raw,expected", [
    ({"tutorial_shown": True}, True),
    ({"tutorial_shown": False}, False),
    ({"tutorial_shown": "yes"}, False),      # not a bool -> default
    ({}, False),                             # absent -> default
])
def test_tutorial_shown_validation_is_a_strict_bool(raw, expected):
    assert ch._validate_settings(raw)["tutorial_shown"] is expected
