"""Regression tests for atomic settings write (F7, F23)."""

import json
import os
import sys
import tempfile
from unittest.mock import patch

import pytest

# Defer import until after sys.path is set by conftest
import clipboard_hotkey


def test_save_settings_writes_atomically(tmp_path, monkeypatch):
    """save_settings must write via temp file + os.replace; partial writes never overwrite the live file."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"hotkey": "original"}))

    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_FILENAME", "settings.json")

    # Patch os.replace to raise — simulates crash between temp-write and replace.
    calls = {"count": 0}

    def failing_replace(src, dst):
        calls["count"] += 1
        raise OSError("simulated crash mid-replace")

    monkeypatch.setattr(os, "replace", failing_replace)

    with pytest.raises(OSError):
        clipboard_hotkey.save_settings({"hotkey": "new"})

    # Original file MUST still be intact
    assert json.loads(settings_file.read_text()) == {"hotkey": "original"}
    assert calls["count"] == 1
