"""Regression tests for OUI download hardening (F2, F3, F4, F5)."""

import io
from unittest.mock import MagicMock, patch

import pytest

from oui_lookup import OUIDatabase


@pytest.fixture
def db(tmp_path):
    return OUIDatabase(str(tmp_path))


def _mock_response(payload_bytes, content_type="text/csv"):
    """Build a context-manager-compatible mock urlopen response."""
    response = MagicMock()
    response.headers = {"Content-Length": str(len(payload_bytes)), "Content-Type": content_type}

    state = {"read": False}
    def read(chunk_size=None):
        if state["read"]:
            return b""
        state["read"] = True
        return payload_bytes
    response.read = read

    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *a: None
    return response


def test_f3_rejects_html_response(db):
    """F3: a captive-portal HTML response must NOT overwrite oui.csv."""
    html = b"<!DOCTYPE html><html><body>Login required</body></html>"
    # Pad to exceed the 1000-byte floor so the size check passes
    payload = html + b" " * 2000
    with patch("oui_lookup.urllib.request.urlopen", return_value=_mock_response(payload, content_type="text/html")):
        success, err = db.download()
    assert success is False
    assert "html" in err.lower() or "content-type" in err.lower() or "captive" in err.lower()


def test_f5_rejects_zero_entry_csv(db, tmp_path):
    """F5: a CSV that parses to zero OUI entries is treated as a load failure."""
    # Create a header-only CSV (no data rows)
    (tmp_path / "oui.csv").write_text("Registry,Assignment,Organization Name,Organization Address\n")
    success, result = db.load()
    assert success is False
    assert "zero" in str(result).lower() or "empty" in str(result).lower()


def test_f2_atomic_replace_preserves_old_db_on_replace_failure(db, tmp_path, monkeypatch):
    """F2: if os.replace fails, the prior oui.csv is preserved."""
    # Pre-populate a "good" oui.csv
    good = (
        b"Registry,Assignment,Organization Name,Organization Address\n"
        b"MA-L,001122,Cisco Systems,\"170 W Tasman Dr\"\n"
    )
    (tmp_path / "oui.csv").write_bytes(good)

    new_payload = b"Registry,Assignment,Organization Name,Organization Address\n" + b"MA-L,AABBCC,New Vendor,addr\n" * 1000

    def failing_replace(src, dst):
        raise OSError("simulated rename failure")

    monkeypatch.setattr("os.replace", failing_replace)
    with patch("oui_lookup.urllib.request.urlopen", return_value=_mock_response(new_payload)):
        success, err = db.download()
    assert success is False
    # Old DB intact
    assert (tmp_path / "oui.csv").read_bytes() == good
