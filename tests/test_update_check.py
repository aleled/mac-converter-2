"""Regression tests for the startup update-check module."""

import json
from io import BytesIO
from unittest.mock import patch, MagicMock
import urllib.error

import pytest

import update_check


def test_parse_version_handles_v_prefix():
    assert update_check._parse_version("v2.5.0") == (2, 5, 0)


def test_parse_version_handles_no_v_prefix():
    assert update_check._parse_version("2.5.0") == (2, 5, 0)


def test_parse_version_strips_prerelease_suffix():
    assert update_check._parse_version("2.5.0-beta1") == (2, 5, 0)


def test_parse_version_handles_two_segments():
    assert update_check._parse_version("v3.0") == (3, 0)


def test_parse_version_returns_empty_tuple_on_garbage():
    assert update_check._parse_version("not-a-version") == ()


def _mock_release_response(tag_name, body="release notes here", html_url=None):
    """Build a mock urlopen response shaped like the GitHub Releases API."""
    if html_url is None:
        html_url = f"https://github.com/aleled/mac-converter-2/releases/tag/{tag_name}"
    payload = json.dumps({
        "tag_name": tag_name,
        "body": body,
        "html_url": html_url,
    }).encode("utf-8")
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *a: None
    return response


def test_check_for_update_returns_none_when_already_latest(monkeypatch):
    """If the installed version equals the latest release, return None."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               return_value=_mock_release_response("v2.5.0")):
        result = update_check.check_for_update()
    assert result is None


def test_check_for_update_returns_dict_when_newer_release(monkeypatch):
    """When the latest release is newer, return a dict with current/latest/urls."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               return_value=_mock_release_response("v99.0.0", body="big new things")):
        result = update_check.check_for_update()
    assert result is not None
    assert result["current"] == "2.5.0"
    assert result["latest"] == "99.0.0"
    assert "99.0.0" in result["release_url"]
    assert result["portal_url"] == "https://aleled.github.io/mac-converter-2/"
    assert "big new things" in result["notes_excerpt"]


def test_check_for_update_returns_none_on_network_failure(monkeypatch):
    """URLError (no network, DNS failure, firewall) returns None without raising."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               side_effect=urllib.error.URLError("Network unreachable")):
        result = update_check.check_for_update()
    assert result is None


def test_check_for_update_returns_none_on_http_error(monkeypatch):
    """HTTPError (e.g. rate limit, 404) returns None without raising."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               side_effect=urllib.error.HTTPError(
                   "url", 403, "Forbidden", {}, BytesIO(b"rate limited"))):
        result = update_check.check_for_update()
    assert result is None


def test_check_for_update_returns_none_on_malformed_tag(monkeypatch):
    """If tag_name has no parseable version digits, return None."""
    monkeypatch.setattr(update_check, "APP_VERSION", "2.5.0")
    with patch("update_check.urllib.request.urlopen",
               return_value=_mock_release_response("some-non-semver-tag")):
        result = update_check.check_for_update()
    assert result is None
