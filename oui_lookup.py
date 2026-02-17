"""
oui_lookup.py

OUI (Organizationally Unique Identifier) vendor lookup database.
Downloads and parses the IEEE OUI CSV file, provides vendor lookup by MAC prefix.

Source: https://standards-oui.ieee.org/oui/oui.csv
Format: Registry,Assignment,Organization Name,Organization Address
"""

import os
import csv
import time
import urllib.request
import urllib.error
import threading

OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"
OUI_FILENAME = "oui.csv"


class OUIDatabase:
    """Thread-safe OUI database with download, parse, and lookup capabilities."""

    def __init__(self, data_dir, update_interval_days=7):
        self.data_dir = data_dir
        self.oui_path = os.path.join(data_dir, OUI_FILENAME)
        self.update_interval_days = update_interval_days
        self._db = {}
        self._loaded = False
        self._loading = False
        self._lock = threading.Lock()

    @property
    def is_loaded(self):
        return self._loaded

    @property
    def is_stale(self):
        """Check if local OUI file is missing or older than update_interval_days."""
        if not os.path.exists(self.oui_path):
            return True
        try:
            file_age_seconds = time.time() - os.path.getmtime(self.oui_path)
            file_age_days = file_age_seconds / (60 * 60 * 24)
            return file_age_days > self.update_interval_days
        except OSError:
            return True

    def download(self, progress_callback=None):
        """
        Download OUI CSV from IEEE. Blocking call — run in a background thread.

        Args:
            progress_callback: Optional callable that accepts either:
                - A string message (status text), or
                - A dict with 'bytes_downloaded' and 'total_bytes' keys (progress update).

        Returns:
            (True, None) on success, (False, error_message) on failure.
        """
        try:
            os.makedirs(self.data_dir, exist_ok=True)

            if progress_callback:
                progress_callback("Connecting to IEEE...")

            req = urllib.request.Request(OUI_URL, headers={
                'User-Agent': 'MAC-Converter/2.3.0'
            })
            response = urllib.request.urlopen(req, timeout=30)

            # Get total size from Content-Length header (if available)
            total_bytes = int(response.headers.get('Content-Length', 0))

            # Read in chunks and report progress
            chunk_size = 16384  # 16 KB chunks
            data = bytearray()
            bytes_downloaded = 0

            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                data.extend(chunk)
                bytes_downloaded += len(chunk)

                if progress_callback and total_bytes > 0:
                    progress_callback({
                        'bytes_downloaded': bytes_downloaded,
                        'total_bytes': total_bytes
                    })

            if len(data) < 1000:
                return (False, "Downloaded file too small, may be corrupt")

            # Atomic write: temp file then rename
            temp_path = self.oui_path + ".tmp"
            with open(temp_path, 'wb') as f:
                f.write(data)

            if os.path.exists(self.oui_path):
                os.remove(self.oui_path)
            os.rename(temp_path, self.oui_path)

            if progress_callback:
                progress_callback("OUI database downloaded successfully")
            return (True, None)

        except urllib.error.URLError as e:
            msg = str(e.reason) if hasattr(e, 'reason') else str(e)
            return (False, f"Network error: {msg}")
        except OSError as e:
            return (False, f"File error: {str(e)}")
        except Exception as e:
            return (False, f"Download failed: {str(e)}")

    def load(self):
        """
        Parse OUI CSV into memory dict. Blocking call.

        Returns:
            (True, entry_count) on success, (False, error_message) on failure.
        """
        with self._lock:
            if self._loading:
                return (False, "Already loading")
            self._loading = True

        try:
            if not os.path.exists(self.oui_path):
                return (False, "OUI database file not found")

            db = {}
            with open(self.oui_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.reader(f)
                header = next(reader, None)  # Skip header row
                for row in reader:
                    if len(row) >= 3:
                        assignment = row[1].strip().upper()
                        org_name = row[2].strip()
                        if len(assignment) == 6 and org_name:
                            db[assignment] = org_name

            with self._lock:
                self._db = db
                self._loaded = True

            return (True, len(db))

        except Exception as e:
            return (False, f"Parse error: {str(e)}")
        finally:
            with self._lock:
                self._loading = False

    def lookup(self, mac_normalized):
        """
        Lookup vendor by normalized MAC address (12 hex chars).

        Args:
            mac_normalized: 12-character hex string (e.g., "001A2B3C4D5E")

        Returns:
            Organization name string, or None if not found.
        """
        if not self._loaded or not mac_normalized or len(mac_normalized) < 6:
            return None
        prefix = mac_normalized[:6].upper()
        return self._db.get(prefix)

    @property
    def vendor_count(self):
        """Total number of OUI prefix entries in the database."""
        return len(self._db)

    @property
    def unique_vendor_count(self):
        """Number of unique vendor/organization names in the database."""
        if not self._loaded:
            return 0
        return len(set(self._db.values()))

    @property
    def file_size_bytes(self):
        """Size of the OUI CSV file on disk, or 0 if not found."""
        try:
            return os.path.getsize(self.oui_path) if os.path.exists(self.oui_path) else 0
        except OSError:
            return 0

    @property
    def file_size_display(self):
        """Human-readable file size string."""
        size = self.file_size_bytes
        if size == 0:
            return "N/A"
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        else:
            return f"{size / (1024 * 1024):.1f} MB"

    @property
    def last_modified_time(self):
        """Last modified timestamp of the OUI file, or None."""
        try:
            if os.path.exists(self.oui_path):
                return os.path.getmtime(self.oui_path)
        except OSError:
            pass
        return None

    @property
    def last_modified_display(self):
        """Human-readable last modified time string."""
        ts = self.last_modified_time
        if ts is None:
            return "Never"
        import datetime
        dt = datetime.datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def get_all_entries(self):
        """
        Return all OUI entries as a sorted list of (prefix, vendor_name) tuples.
        Prefix is formatted as XX:XX:XX.
        """
        if not self._loaded:
            return []
        entries = []
        for prefix, vendor in sorted(self._db.items()):
            formatted = ':'.join(prefix[i:i+2] for i in range(0, 6, 2))
            entries.append((formatted, vendor))
        return entries


if __name__ == "__main__":
    import sys
    db = OUIDatabase(os.path.dirname(os.path.abspath(__file__)))
    print("Checking if OUI database is stale...")
    if db.is_stale:
        print("Downloading OUI database...")
        success, err = db.download(progress_callback=print)
        if not success:
            print(f"Download failed: {err}")
            sys.exit(1)
    print("Loading OUI database...")
    success, result = db.load()
    if success:
        print(f"Loaded {result} vendors")
        test_mac = "001A2B3C4D5E"
        vendor = db.lookup(test_mac)
        print(f"Vendor for {test_mac}: {vendor or 'Unknown'}")
    else:
        print(f"Load failed: {result}")
