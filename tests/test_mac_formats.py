"""Regression tests for mac_formats (F1)."""

import pytest

from mac_formats import detect_mac, convert_mac


def test_f1_rejects_mixed_separators():
    """F1: mixed colon and hyphen separators are not a real MAC notation."""
    assert detect_mac("00-1A:2B-3C:4D-5E") is None
    assert detect_mac("00:1A-2B:3C-4D:5E") is None
    assert detect_mac("AA-BB:CC-DD:EE-FF") is None


@pytest.mark.parametrize("text,expected", [
    ("00:1A:2B:3C:4D:5E", "001A2B3C4D5E"),
    ("00-1A-2B-3C-4D-5E", "001A2B3C4D5E"),
    ("AA:BB:CC:DD:EE:FF", "AABBCCDDEEFF"),
    ("aa-bb-cc-dd-ee-ff", "aabbccddeeff"),
    ("aabb.ccdd.eeff", "aabbccddeeff"),
    ("AABBCC-DDEEFF", "AABBCCDDEEFF"),
    ("aabbccddeeff", "aabbccddeeff"),
    ("AABBCCDDEEFF", "AABBCCDDEEFF"),
    ("  00:1A:2B:3C:4D:5E  ", "001A2B3C4D5E"),
])
def test_detect_mac_happy_path(text, expected):
    assert detect_mac(text) == expected


@pytest.mark.parametrize("text", [
    "AABBCCDDEEFF1",  # 13 chars
    "GG-HH-II-JJ-KK-LL",  # non-hex
    "00:1A:2B:3C:4D:5E:FF",  # 7 octets
    "",  # empty
    "not-a-mac",  # nonsense
])
def test_detect_mac_rejects(text):
    assert detect_mac(text) is None


def test_convert_mac_emits_ten_formats():
    formats = convert_mac("001A2B3C4D5E")
    assert len(formats) == 10
    by_desc = dict(formats)
    assert by_desc["Colon-separated uppercase"] == "00:1A:2B:3C:4D:5E"
    assert by_desc["Hyphen-6char uppercase"] == "001A2B-3C4D5E"
    assert by_desc["Dot-separated lowercase"] == "001a.2b3c.4d5e"
