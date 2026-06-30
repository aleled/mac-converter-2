"""
update_check.py

Startup update check for MAC Address Converter.

Single source of truth for the running app version (APP_VERSION).
Fetches the latest release from the GitHub Releases API and reports
whether a newer version is available. Designed to fail silently:
all error paths return None rather than raising, so the caller can
unconditionally invoke this without wrapping in try/except.

Truststore (imported and ssl-injected by oui_lookup.py at module load)
means urllib uses Windows' certificate store and works on corporate
networks with TLS-intercepting proxies.
"""

import json
import sys
import urllib.error
import urllib.request

APP_VERSION = "2.5.1"

# The owner/repo path for the GitHub Releases API call. Centralised so
# tests can monkeypatch it if needed in the future, and so any rename
# of the repo can be done in one place.
GITHUB_REPO = "aleled/mac-converter-2"

# URL the Upgrade button opens in the user's default browser.
PORTAL_URL = "https://aleled.github.io/mac-converter-2/"

# How much of the release body to surface in the "details" pane.
_NOTES_EXCERPT_LIMIT = 500


def _parse_version(s):
    """Parse a version string like 'v2.5.0' or '2.5.0-beta1' into a tuple of ints.

    Strips a leading 'v' (case-insensitive). Splits on '.'. Stops at the
    first segment that isn't purely numeric (so pre-release suffixes are
    ignored). Returns an empty tuple if no numeric segments are found.
    """
    if not isinstance(s, str):
        return ()
    s = s.lstrip("vV").strip()
    parts = []
    for segment in s.split("."):
        # Strip pre-release suffix from this segment: "0-beta1" -> "0"
        digits = []
        for ch in segment:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        if not digits:
            break
        parts.append(int("".join(digits)))
    return tuple(parts)


def check_for_update():
    """Return a dict describing an available update, or None.

    Return dict shape:
        {
            'current': str,        # e.g. "2.5.0"
            'latest': str,         # e.g. "3.0.0"
            'release_url': str,    # github.com/.../releases/tag/v3.0.0
            'portal_url': str,     # the github.io download portal
            'notes_excerpt': str,  # first N chars of release body
        }

    Returns None if:
      - The HTTP request fails for any reason (network, DNS, rate-limit, etc.)
      - The JSON is malformed
      - The tag_name doesn't parse to a usable version tuple
      - The latest version is not strictly greater than APP_VERSION
    """
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"MAC-Converter/{APP_VERSION}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"[update_check] HTTP error: {e}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"[update_check] Network error: {e}", file=sys.stderr)
        return None
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[update_check] Parse error: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[update_check] Unexpected error: {type(e).__name__}: {e}",
              file=sys.stderr)
        return None

    tag_name = data.get("tag_name", "")
    body = data.get("body", "") or ""
    release_url = data.get("html_url", "") or ""

    latest_tuple = _parse_version(tag_name)
    current_tuple = _parse_version(APP_VERSION)
    if not latest_tuple or not current_tuple:
        return None
    if latest_tuple <= current_tuple:
        return None

    latest_clean = tag_name.lstrip("vV").strip()

    return {
        "current": APP_VERSION,
        "latest": latest_clean,
        "release_url": release_url or
            f"https://github.com/{GITHUB_REPO}/releases/tag/{tag_name}",
        "portal_url": PORTAL_URL,
        "notes_excerpt": body[:_NOTES_EXCERPT_LIMIT],
    }
