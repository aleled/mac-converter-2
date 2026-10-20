"""Tests for layout_fix — keyboard-layout transliteration ("I typed in the wrong language").

Tests that need a specific layout installed (he-IL) skip themselves when it isn't,
so the suite stays green on any Windows machine.
"""

import sys

import pytest

import layout_fix

windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Win32 keyboard layout API")


# --- layout enumeration -----------------------------------------------------

@windows_only
def test_installed_layouts_returns_at_least_one():
    ls = layout_fix.installed_layouts()
    assert len(ls) >= 1
    for l in ls:
        assert isinstance(l.hkl, int)
        assert isinstance(l.name, str) and l.name


@windows_only
def test_layouts_are_unique_by_hkl():
    ls = layout_fix.installed_layouts()
    assert len({l.hkl for l in ls}) == len(ls)


# --- helpers for layout-specific tests --------------------------------------

def _layout(prefix):
    for l in layout_fix.installed_layouts():
        if l.name.lower().startswith(prefix):
            return l
    return None


def _need(prefix):
    l = _layout(prefix)
    if l is None:
        pytest.skip(f"no {prefix}* keyboard layout installed on this machine")
    return l


# --- conversion -------------------------------------------------------------

@windows_only
def test_convert_en_to_he_produces_hebrew():
    """The headline case: Hebrew words typed while the US layout was active."""
    en, he = _need("en"), _need("he")
    assert layout_fix.convert("akuo", en.hkl, he.hkl) == "שלום"
    assert layout_fix.convert("ahkuo", en.hkl, he.hkl) == "שילום"


@windows_only
def test_convert_he_to_en_produces_latin():
    """The reverse: English typed while the Hebrew layout was active."""
    en, he = _need("en"), _need("he")
    assert layout_fix.convert("דישךםצ", he.hkl, en.hkl) == "shalom"


@windows_only
def test_convert_round_trips_ascii_letters_and_digits():
    en, he = _need("en"), _need("he")
    src = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    assert layout_fix.convert(layout_fix.convert(src, en.hkl, he.hkl), he.hkl, en.hkl) == src


@windows_only
def test_convert_preserves_characters_it_cannot_map():
    en, he = _need("en"), _need("he")
    # digits and spaces exist identically in both layouts
    assert layout_fix.convert("123 456", en.hkl, he.hkl) == "123 456"


@windows_only
def test_convert_is_identity_when_src_equals_dst():
    en = _need("en")
    assert layout_fix.convert("hello world", en.hkl, en.hkl) == "hello world"


@windows_only
def test_convert_handles_empty_string():
    en, he = _need("en"), _need("he")
    assert layout_fix.convert("", en.hkl, he.hkl) == ""


# --- source detection -------------------------------------------------------

@windows_only
def test_typeable_score_discriminates_scripts():
    en, he = _need("en"), _need("he")
    assert layout_fix.typeable_score("akuo", en.hkl) == 1.0
    assert layout_fix.typeable_score("akuo", he.hkl) < 0.5
    assert layout_fix.typeable_score("שלום", he.hkl) == 1.0
    assert layout_fix.typeable_score("שלום", en.hkl) == 0.0


@windows_only
def test_typeable_score_ignores_digits_and_whitespace():
    en = _need("en")
    # no scorable letters at all -> 0.0, and must not raise
    assert layout_fix.typeable_score("123 456", en.hkl) == 0.0
    assert layout_fix.typeable_score("", en.hkl) == 0.0


# --- top-level fix_text -----------------------------------------------------

@windows_only
def test_fix_text_latin_gibberish_becomes_hebrew():
    _need("he")
    r = layout_fix.fix_text("akuo")
    assert r is not None
    assert r.text == "שלום"
    assert r.src.name.lower().startswith("en")
    assert r.dst.name.lower().startswith("he")


@windows_only
def test_fix_text_hebrew_gibberish_becomes_latin():
    _need("he")
    r = layout_fix.fix_text("דישךםצ")
    assert r is not None
    assert r.text == "shalom"
    assert r.dst.name.lower().startswith("en")


@windows_only
def test_fix_text_returns_none_for_empty_or_unconvertible():
    assert layout_fix.fix_text("") is None
    assert layout_fix.fix_text("   ") is None
    # digits only: every candidate converts to itself -> nothing to offer
    assert layout_fix.fix_text("12345") is None


@windows_only
def test_fix_text_never_returns_unchanged_text():
    """A candidate identical to the input is useless and must be filtered out."""
    for probe in ["akuo", "שלום", "hello", "12345", "a1b2"]:
        r = layout_fix.fix_text(probe)
        if r is not None:
            assert r.text != probe


@windows_only
def test_fix_text_skip_cycles_through_candidates():
    """Repeated presses walk the candidate list, then wrap to the start."""
    _need("he")
    first = layout_fix.fix_text("akuo", skip=0)
    assert first is not None
    n = first.candidate_count
    assert n >= 1
    # skipping by exactly the candidate count wraps back to the first result
    assert layout_fix.fix_text("akuo", skip=n).text == first.text


@windows_only
def test_fix_text_handles_multiline_and_punctuation_without_raising():
    r = layout_fix.fix_text("akuo\nahkuo!\t(ba`i)")
    if r is not None:
        assert isinstance(r.text, str)
        assert len(r.text) == len("akuo\nahkuo!\t(ba`i)")


@windows_only
def test_fix_text_preserves_length():
    """Single-key-per-character mapping: output length always equals input length."""
    for probe in ["akuo", "Hello World 123", "דישךםצ"]:
        r = layout_fix.fix_text(probe)
        if r is not None:
            assert len(r.text) == len(probe)
