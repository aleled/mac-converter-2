"""Regression tests for settings load validation (F8, F15, F24)."""

import json
import os
import time

import pytest

import clipboard_hotkey


def test_validate_settings_coerces_bad_types():
    """A string in last_format_index must fall back to the default int."""
    raw = {
        "hotkey": "alt+shift+m",
        "last_format_index": "garbage",  # F8: must coerce/fallback
        "notification_duration": -1,  # F15: out-of-range, must clamp
        "autostart": "no",  # F8: wrong type, must fallback
    }
    out = clipboard_hotkey._validate_settings(raw)
    assert isinstance(out["last_format_index"], int)
    # v2.5.1: format count grew from 10 to 12; range expanded accordingly.
    assert 0 <= out["last_format_index"] < 12
    assert 1 <= out["notification_duration"] <= 10
    assert isinstance(out["autostart"], bool)


def test_validate_settings_accepts_index_eleven():
    """v2.5.1: index 11 (the new Dash-4char lowercase) is valid; 12 is out of range."""
    out = clipboard_hotkey._validate_settings({"last_format_index": 11})
    assert out["last_format_index"] == 11

    # Out-of-range index falls back to default 0
    out = clipboard_hotkey._validate_settings({"last_format_index": 12})
    assert out["last_format_index"] == 0


def test_validate_settings_keeps_good_values():
    raw = {
        "hotkey": "ctrl+shift+c",
        "last_format_index": 4,
        "notification_duration": 5,
        "autostart": True,
    }
    out = clipboard_hotkey._validate_settings(raw)
    assert out["hotkey"] == "ctrl+shift+c"
    assert out["last_format_index"] == 4
    assert out["notification_duration"] == 5
    assert out["autostart"] is True


def test_load_settings_renames_corrupt_file(tmp_path, monkeypatch):
    """F24: a corrupt settings.json is renamed to settings.json.corrupt-<ts>, not silently overwritten."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text("{not valid json")

    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_FILENAME", "settings.json")

    result = clipboard_hotkey.load_settings()

    # Defaults loaded
    assert result["hotkey"] == clipboard_hotkey.DEFAULT_SETTINGS["hotkey"]
    # Corrupt file moved aside
    assert not settings_file.exists()
    corrupt_files = list(tmp_path.glob("settings.json.corrupt-*"))
    assert len(corrupt_files) == 1
    assert "not valid json" in corrupt_files[0].read_text()


def test_load_settings_missing_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(clipboard_hotkey, "SETTINGS_FILENAME", "settings.json")
    result = clipboard_hotkey.load_settings()
    assert result == clipboard_hotkey.DEFAULT_SETTINGS
