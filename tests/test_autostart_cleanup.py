"""Regression test for v2.5.1's legacy autostart cleanup.

The pre-v2.4.0 installer created a Startup-folder shortcut named
"MAC Address Converter.lnk" (full app name with spaces). v2.4.0+'s
in-app autostart writes "MAC-Converter.lnk" — different file, same
target — so users who upgraded ended up with both shortcuts firing at
boot. The runtime cleanup helper sweeps known legacy filenames.
"""

import os

import clipboard_hotkey


def test_cleanup_removes_legacy_lnk(tmp_path, monkeypatch):
    """The helper deletes 'MAC Address Converter.lnk' but preserves the canonical."""
    # Redirect the Startup folder to a temp dir for this test
    monkeypatch.setattr(
        clipboard_hotkey, "_autostart_startup_dir", lambda: str(tmp_path)
    )

    # Set up the conflict scenario: both legacy and canonical exist
    legacy_path = tmp_path / "MAC Address Converter.lnk"
    canonical_path = tmp_path / "MAC-Converter.lnk"
    legacy_path.write_text("legacy shortcut")
    canonical_path.write_text("canonical shortcut")
    assert legacy_path.exists()
    assert canonical_path.exists()

    # Run the cleanup
    clipboard_hotkey._cleanup_legacy_autostart_shortcuts()

    # Legacy should be gone, canonical untouched
    assert not legacy_path.exists()
    assert canonical_path.exists()


def test_cleanup_is_idempotent(tmp_path, monkeypatch):
    """Calling the cleanup with nothing to clean is silent and safe."""
    monkeypatch.setattr(
        clipboard_hotkey, "_autostart_startup_dir", lambda: str(tmp_path)
    )

    # No legacy files exist
    assert not (tmp_path / "MAC Address Converter.lnk").exists()

    # Should not raise
    clipboard_hotkey._cleanup_legacy_autostart_shortcuts()
    clipboard_hotkey._cleanup_legacy_autostart_shortcuts()  # second call still safe

    # Still empty
    assert list(tmp_path.iterdir()) == []


def test_cleanup_preserves_unrelated_files(tmp_path, monkeypatch):
    """Files that aren't in _LEGACY_AUTOSTART_LNK_FILENAMES must be left alone."""
    monkeypatch.setattr(
        clipboard_hotkey, "_autostart_startup_dir", lambda: str(tmp_path)
    )

    other = tmp_path / "Something Else.lnk"
    other.write_text("some other app's shortcut")

    clipboard_hotkey._cleanup_legacy_autostart_shortcuts()

    assert other.exists()
