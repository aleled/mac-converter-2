"""
test_mac_formats.py

Unit tests for mac_formats.py MAC address detection and conversion functions.
"""
import unittest
from mac_formats import detect_mac, normalize_mac, convert_mac

class TestMacFormats(unittest.TestCase):
    """
    Test case for testing MAC address formats: detection, normalization,
    conversion, and validation.
    """

    def test_detect_mac(self):
        """Test the detection and normalization of MAC addresses."""
        self.assertEqual(normalize_mac("00:1A:2B:3C:4D:5E"), "001A2B3C4D5E")
        self.assertEqual(normalize_mac("00-1a-2b-3c-4d-5e"), "001a2b3c4d5e")
        self.assertEqual(normalize_mac("001A.2B3C.4D5E"), "001A2B3C4D5E")
        self.assertEqual(normalize_mac("001A2B-3C4D5E"), "001A2B3C4D5E")
        self.assertEqual(normalize_mac("001a2b-3c4d5e"), "001a2b3c4d5e")
        self.assertEqual(normalize_mac("001a2b3c4d5e"), "001a2b3c4d5e")
        self.assertIsNone(detect_mac("not a mac"))
        # Only accept exact MAC, not substring
        self.assertIsNone(detect_mac("foo 00:1A:2B:3C:4D:5E bar"))

    def test_convert_mac(self):
        """Test conversion of MAC addresses to various formats."""
        mac = "001A2B3C4D5E"
        formats = dict(convert_mac(mac))
        self.assertEqual(formats["Colon-separated uppercase"], "00:1A:2B:3C:4D:5E")
        self.assertEqual(formats["Colon-separated lowercase"], "00:1a:2b:3c:4d:5e")
        self.assertEqual(formats["Hyphen-separated uppercase"], "00-1A-2B-3C-4D-5E")
        self.assertEqual(formats["Hyphen-separated lowercase"], "00-1a-2b-3c-4d-5e")
        self.assertEqual(formats["Hyphen-6char uppercase"], "001A2B-3C4D5E")
        self.assertEqual(formats["Hyphen-6char lowercase"], "001a2b-3c4d5e")
        self.assertEqual(formats["Dot-separated uppercase"], "001A.2B3C.4D5E")
        self.assertEqual(formats["Dot-separated lowercase"], "001a.2b3c.4d5e")
        self.assertEqual(formats["Plain uppercase"], "001A2B3C4D5E")
        self.assertEqual(formats["Plain lowercase"], "001a2b3c4d5e")

    def test_validation(self):
        """Test validation of MAC addresses."""
        # Valid MACs
        valid = [
            "00:1A:2B:3C:4D:5E",
            "00-1A-2B-3C-4D-5E",
            "001A2B-3C4D5E",
            "001A.2B3C.4D5E",
            "001A2B3C4D5E",
            "00:1a:2b:3c:4d:5e",
            "00-1a-2b-3c-4d-5e",
            "001a2b-3c4d5e",
            "001a.2b3c.4d5e",
            "001a2b3c4d5e"
        ]
        for mac in valid:
            norm = detect_mac(mac)
            self.assertIsNotNone(norm)
            if norm is not None:
                self.assertEqual(len(norm), 12)
                self.assertTrue(all(c in '0123456789abcdefABCDEF' for c in norm))
        # Invalid MACs
        invalid = [
            "00:1A:2B:3C:4D",  # too short
            "00:1A:2B:3C:4D:5E:7F",  # too long
            "00:1A:2B:3C:4D:ZZ",  # invalid hex
            "notamacaddress"
        ]
        for mac in invalid:
            self.assertIsNone(detect_mac(mac))

if __name__ == "__main__":
    unittest.main()
