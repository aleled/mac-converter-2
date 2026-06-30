"""
mac_formats.py

Provides MAC address detection and conversion utilities for the system tray utility.

Functions:
    detect_mac(text: str) -> str | None: Detects a MAC address in the input string.
    convert_mac(mac: str) -> list[tuple[str, str]]: Returns all format variants for a MAC address.
"""
import re

# Supported MAC address formats (upper/lower). 12 entries — the hotkey
# cycles through them in order; the index wraps via len(MAC_FORMATS).
MAC_FORMATS = [
    ("Colon-separated uppercase",    lambda mac: ':'.join(mac[i:i+2] for i in range(0, 12, 2)).upper()),
    ("Colon-separated lowercase",    lambda mac: ':'.join(mac[i:i+2] for i in range(0, 12, 2)).lower()),
    ("Hyphen-separated uppercase",   lambda mac: '-'.join(mac[i:i+2] for i in range(0, 12, 2)).upper()),
    ("Hyphen-separated lowercase",   lambda mac: '-'.join(mac[i:i+2] for i in range(0, 12, 2)).lower()),
    ("Hyphen-6char uppercase",       lambda mac: f"{mac[:6].upper()}-{mac[6:].upper()}"),
    ("Hyphen-6char lowercase",       lambda mac: f"{mac[:6].lower()}-{mac[6:].lower()}"),
    ("Dot-separated uppercase",      lambda mac: '.'.join(mac[i:i+4] for i in range(0, 12, 4)).upper()),
    ("Dot-separated lowercase",      lambda mac: '.'.join(mac[i:i+4] for i in range(0, 12, 4)).lower()),
    # v2.5.1 — 4-4-4 with dashes (e.g. AABB-CCDD-EEFF). Common in some
    # vendor configs as an alternative to the dot-separated 4-4-4.
    ("Dash-4char uppercase",         lambda mac: '-'.join(mac[i:i+4] for i in range(0, 12, 4)).upper()),
    ("Dash-4char lowercase",         lambda mac: '-'.join(mac[i:i+4] for i in range(0, 12, 4)).lower()),
    ("Plain uppercase",              lambda mac: mac.upper()),
    ("Plain lowercase",              lambda mac: mac.lower()),
]

# Regex to match MAC addresses in various formats (strict, must be delimited or at string boundaries).
# Space-separated (e.g. "aa bb cc dd ee ff") is recognized as input only —
# not added to MAC_FORMATS, the app never generates it as output.
MAC_REGEX = re.compile(
    r"(?<![0-9A-Fa-f])("
    r"(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}"   # colon-separated
    r"|"
    r"(?:[0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}"   # hyphen-separated
    r"|"
    r"(?:[0-9A-Fa-f]{2} ){5}[0-9A-Fa-f]{2}"   # v2.5.1: space-separated (detect only)
    r"|"
    r"[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}\.[0-9A-Fa-f]{4}"  # dot-separated 4-4-4
    r"|"
    r"[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}"    # v2.5.1: dash-separated 4-4-4
    r"|"
    r"[0-9A-Fa-f]{6}-[0-9A-Fa-f]{6}"          # Hyphen-6char (Cisco)
    r"|"
    r"[0-9A-Fa-f]{12}"                         # plain 12-hex
    r")(?![0-9A-Fa-f])"
)

def normalize_mac(mac: str) -> str:
    """Remove all separators and return 12 hex digits (no case change)."""
    return re.sub(r'[^0-9A-Fa-f]', '', mac)

def detect_mac(text: str) -> str | None:
    """Return normalized MAC if the entire string is a valid MAC, else None."""
    text = text.strip()
    match = MAC_REGEX.fullmatch(text)
    if match:
        norm = normalize_mac(match.group(0))
        if len(norm) == 12 and all(c in '0123456789abcdefABCDEF' for c in norm):
            return norm
    return None

def convert_mac(mac: str) -> list[tuple[str, str]]:
    """Return all format conversions for a normalized MAC address."""
    return [(desc, fmt(mac)) for desc, fmt in MAC_FORMATS]

# Example usage (for testing only)
if __name__ == "__main__":
    test = "00-1A-2B-3C-4D-5E"
    norm = detect_mac(test)
    if norm:
        for desc, val in convert_mac(norm):
            print(f"{desc}: {val}")
    else:
        print("No MAC address found.")
