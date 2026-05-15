"""
MAC Address Converter Utility - Session Progress (2025-06-05)

- Info label always shows the original MAC address from the first hotkey press (fixed).
- Timer in info label always counts down while dialog is visible, regardless of user interaction (fixed).
- UI is robust, visually clear, and cross-platform (Windows/PowerShell and WSL/Linux).
- Legacy QTableWidget code is still present below, but not used in the UI. It can be removed in a future cleanup.
- See DEVELOPMENT_LOG.md, TODO.md, and CHANGELOG.md for details.
"""

"""
clipboard_hotkey.py

Listens for a global hotkey, checks clipboard for a valid MAC address, and if found, prompts user to select a format and copies the result to clipboard.
Uses pynput for cross-platform hotkey support (no root required on Linux).
"""

import pyperclip
import pystray
from PIL import Image, ImageDraw
import threading
import sys
from mac_formats import detect_mac, convert_mac
from oui_lookup import OUIDatabase
import platform
import os
from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget,
    QSizePolicy, QCheckBox, QPushButton, QLineEdit, QSpinBox, QGroupBox, QProgressBar,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QScrollArea, QShortcut)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QFont, QColor, QIcon, QBrush, QPixmap, QCursor, QKeySequence
import queue
import ctypes
import time
from pynput import keyboard
import json

# --- Atomic settings I/O (Phase 2 fix for F7, F16, F23, F28) ---

_settings_lock = threading.Lock()


def _atomic_write_json(path, data):
    """Write `data` to `path` atomically via temp file + os.replace.

    Caller is responsible for serialization (e.g. holding _settings_lock).
    Raises OSError on failure; the live file is never partially written.
    """
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def _validate_hotkey_string(hotkey_str):
    """Return None if valid, an error message string if not.

    Uses pynput.keyboard.HotKey.parse to mirror what listen_hotkey will do.
    pynput canonical form wraps multi-character named keys (e.g. ctrl, shift,
    alt, cmd) in angle brackets but leaves single-character keys bare.
    """
    if not hotkey_str or not hotkey_str.strip():
        return "Hotkey cannot be empty"
    try:
        parts = []
        for k in hotkey_str.split('+'):
            token = k.strip().lower()
            if not token:
                raise ValueError("empty key segment")
            # Single-character keys are passed bare; named keys go in <>.
            parts.append(token if len(token) == 1 else f'<{token}>')
        canonical = '+'.join(parts)
        keyboard.HotKey.parse(canonical)
        return None
    except (ValueError, KeyError) as e:
        return f"Invalid hotkey: {e}"


# --- Autostart via Startup-folder shortcut (Phase 2 fix for F13, F31) ---

def _autostart_lnk_path():
    """Path to the user's Startup-folder shortcut for MAC Converter."""
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    startup_dir = os.path.join(
        appdata, 'Microsoft', 'Windows', 'Start Menu', 'Programs', 'Startup'
    )
    return os.path.join(startup_dir, 'MAC-Converter.lnk')


def is_autostart_enabled():
    """Return True if the autostart shortcut exists."""
    return os.path.exists(_autostart_lnk_path())


def set_autostart_enabled(enabled):
    """Create or remove the Startup-folder shortcut.

    Best-effort: failures are logged to stderr but do not raise. Callers
    should re-query is_autostart_enabled() to confirm.
    """
    lnk_path = _autostart_lnk_path()
    if enabled:
        try:
            import win32com.client
            shell = win32com.client.Dispatch('WScript.Shell')
            shortcut = shell.CreateShortcut(lnk_path)
            shortcut.TargetPath = sys.executable
            shortcut.WorkingDirectory = os.path.dirname(sys.executable)
            shortcut.IconLocation = sys.executable
            shortcut.Description = 'MAC Address Converter'
            shortcut.save()
        except Exception as e:
            print(f"[ERROR] set_autostart_enabled(True): {e}", file=sys.stderr)
    else:
        try:
            if os.path.exists(lnk_path):
                os.remove(lnk_path)
        except OSError as e:
            print(f"[ERROR] set_autostart_enabled(False): {e}", file=sys.stderr)


# --- Single-instance mutex (Phase 2 fix for F25) ---

_single_instance_mutex_handle = None  # held for process lifetime


def acquire_single_instance_mutex():
    """Try to acquire a named mutex. Returns True if this is the only instance.

    Returns False if another instance already holds the mutex.
    Returns True (allow-all) if pywin32 isn't importable, so the app
    still works on systems without it.
    """
    global _single_instance_mutex_handle
    try:
        import win32event
        import win32api
        import winerror
        _single_instance_mutex_handle = win32event.CreateMutex(
            None, False, "Global\\MAC-Converter-2-SingleInstance"
        )
        last_err = win32api.GetLastError()
        if last_err == winerror.ERROR_ALREADY_EXISTS:
            return False
        return True
    except ImportError:
        return True


# --- Tray Icon Setup ---
def get_icon_path():
    """
    Returns the absolute path to the tray icon image (icon-v1.png) located in the same directory as this script.
    Returns:
        str: Absolute file path to icon-v1.png
    """
    # Get absolute path to icon-v1.png in the same directory as this script
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon-v1.png")

def create_image():
    """
    Loads the tray icon image from file. If loading fails, creates a fallback icon image.
    Returns:
        PIL.Image: The tray icon image.
    """
    # Load icon-v1.png as tray icon
    try:
        icon_path = get_icon_path()
        img = Image.open(icon_path)
        return img
    except Exception as e:
        print(f"[WARNING] Could not load icon-v1.png: {e}. Using fallback icon.")
        # Fallback: black circle with white M
        img = Image.new('RGB', (64, 64), color='black')
        d = ImageDraw.Draw(img)
        d.ellipse((8, 8, 56, 56), fill='white')
        d.text((22, 18), 'M', fill='black')
        return img

def on_quit(icon, item):
    """
    Handles the tray menu 'Quit' action. Stops the tray icon, hotkey listener, and exits the Qt application.
    Args:
        icon (pystray.Icon): The tray icon instance.
        item: The menu item (unused).
    """
    global listener
    icon.stop()
    # F29: give the pynput listener a chance to terminate cleanly
    if listener is not None:
        try:
            listener.stop()
            listener.join(timeout=2.0)
        except RuntimeError:
            pass
    # F26: give the OUI worker a chance to finish os.replace before the
    # process dies. The worker thread reference is held by
    # OUIDownloadDialog (which may not be reachable from here); the best
    # we can do without a bigger refactor is wait briefly so the cancel
    # signal propagates.
    if _oui_download_in_progress.is_set():
        import time as _time
        _time.sleep(0.5)
    app = QApplication.instance()
    if app is not None:
        # F27: stop any QTimers that may still be running so they don't
        # fire during shutdown teardown.
        for widget in app.allWidgets():
            for timer in widget.findChildren(QTimer):
                timer.stop()
        app.quit()


about_dialog_request_queue = queue.Queue()
settings_dialog_request_queue = queue.Queue()
format_popup_request_queue = queue.Queue()  # Queue for format popup requests

# Global icon reference for notifications
tray_icon = None
tray_icon_ready = threading.Event()

# Global hotkey listener
listener = None

# Global notification timer management - allows cancelling previous notification
current_notification_timer = None

# Global format popup instance tracker - allows instant replacement
current_format_popup = None

# Global vendor popup instance tracker
current_vendor_popup = None

# Global OUI database instance
oui_db = None
oui_status_queue = queue.Queue()

# Queue for vendor lookup requests (Enter key detected globally)
vendor_lookup_request_queue = queue.Queue()

# Queue for manual OUI download progress updates (for interactive progress bar)
oui_download_progress_queue = queue.Queue()

# F11/F18: Re-entrance guard for OUI download dialog. Set while a download
# is running so a second Update click can be rejected, and so on_quit can
# briefly wait for the worker to finish os.replace before process death.
_oui_download_in_progress = threading.Event()

# --- Format popup display function ---
def show_format_popup(app, formats, current_index, duration_seconds, mac_normalized=None):
    """
    Show format selector popup with current format in bold.
    Replaces any existing popup instantly for responsive UX.

    Args:
        app (QApplication): The running Qt application instance.
        formats (list): List of (name, value) tuples for all MAC formats.
        current_index (int): Index of the currently selected format.
        duration_seconds (int): How long to display the popup (in seconds).
        mac_normalized (str): Normalized 12-char hex MAC for OUI lookup.
    """
    global current_format_popup

    # Close and clean up previous popup if exists
    if current_format_popup is not None:
        try:
            current_format_popup.close()
        except Exception:
            pass
        current_format_popup = None

    # Create and show new popup
    current_format_popup = FormatSelectorPopup(formats, current_index, duration_seconds, mac_normalized)
    current_format_popup.show()

    # Force keyboard focus to the popup so the Qt-scoped Enter QShortcut
    # actually fires (post-F19). Without this, Windows' focus-stealing
    # prevention leaves focus on whatever app the user was typing in.
    # The hotkey thread just received the user's input, so SetForegroundWindow
    # is allowed by Windows' foreground-steal rules.
    current_format_popup.activateWindow()
    current_format_popup.raise_()
    current_format_popup.setFocus()
    try:
        import ctypes
        hwnd = int(current_format_popup.winId())
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception:
        pass  # best-effort; activateWindow above usually suffices


def show_error_popup(app, message, duration_seconds):
    """
    Show error message popup.

    Args:
        app (QApplication): The running Qt application instance.
        message (str): The error message to display.
        duration_seconds (int): How long to display the popup (in seconds).
    """
    dlg = QDialog(None)
    dlg.setWindowTitle("MAC Converter")
    try:
        icon_path = get_icon_path()
        dlg.setWindowIcon(QIcon(icon_path))
    except Exception:
        pass

    dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowStaysOnTopHint | Qt.Tool)

    layout = QVBoxLayout()
    layout.setContentsMargins(15, 15, 15, 15)

    label = QLabel(message)
    label.setStyleSheet("color: #d32f2f; font-weight: bold;")
    layout.addWidget(label)

    dlg.setLayout(layout)
    dlg.setFixedWidth(300)
    dlg.adjustSize()

    # Position near system tray
    try:
        screen_geom = QApplication.desktop().screenGeometry()
        x = screen_geom.width() - dlg.width() - 20
        y = screen_geom.height() - dlg.height() - 20
        dlg.move(x, y)
    except Exception:
        pass

    # Auto-close timer
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(dlg.close)
    timer.start(int(duration_seconds * 1000))

    dlg.show()

def handle_hotkey(app):
    """
    Handle hotkey press: auto-cycle MAC format and queue format selector popup.
    Displays current format in bold with clickable options for other formats.
    Uses queue to pass request to Qt event loop (thread-safe).

    Args:
        app (QApplication): The running Qt application instance.
    """
    try:
        text = pyperclip.paste()
    except pyperclip.PyperclipException as e:
        duration = settings.get('notification_duration', 3)
        format_popup_request_queue.put({
            'type': 'error',
            'message': f"Clipboard busy: {e}",
            'duration': duration,
        })
        return
    mac = detect_mac(text)

    if not mac:
        # Queue error popup request
        duration = settings.get('notification_duration', 3)
        format_popup_request_queue.put({
            'type': 'error',
            'message': "No valid MAC address in clipboard",
            'duration': duration
        })
        return

    # Get all formats
    formats = convert_mac(mac)

    # Auto-cycle to next format
    last_idx = settings.get('last_format_index', 0)
    next_idx = (last_idx + 1) % 10  # Cycle 0->1->...->9->0

    # Get converted MAC (formats is list of tuples: [(name, value), ...])
    converted_mac = formats[next_idx][1]

    # Copy to clipboard
    try:
        pyperclip.copy(converted_mac)
    except pyperclip.PyperclipException as e:
        duration = settings.get('notification_duration', 3)
        format_popup_request_queue.put({
            'type': 'error',
            'message': f"Clipboard busy, can't copy: {e}",
            'duration': duration,
        })
        return

    # Update last used format index
    settings['last_format_index'] = next_idx
    save_settings(settings)

    # Queue format selector popup request (thread-safe)
    duration = settings.get('notification_duration', 3)
    format_popup_request_queue.put({
        'type': 'format',
        'formats': formats,
        'current_index': next_idx,
        'duration': duration,
        'mac_normalized': mac,
    })

# --- About Dialog ---
class AboutDialog(QDialog):
    """About dialog with app information, author, license, and links."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About MAC Converter")
        self.setModal(True)

        # Set window icon
        try:
            icon_path = get_icon_path()
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 24px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(20, 20, 20, 20)

        # Icon at top (centered)
        try:
            icon_path = get_icon_path()
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label = QLabel()
            icon_label.setPixmap(scaled_pixmap)
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
        except Exception:
            pass

        # App name
        app_name = QLabel("MAC Address Converter")
        app_name.setAlignment(Qt.AlignCenter)
        app_font = QFont()
        app_font.setPointSize(14)
        app_font.setBold(True)
        app_name.setFont(app_font)
        layout.addWidget(app_name)

        # Version
        version_label = QLabel("Version 2.4.1")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #999999; font-size: 10pt;")
        layout.addWidget(version_label)

        # Separator
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #555555;")
        layout.addWidget(separator)

        # Author
        author_label = QLabel("Created by Alejandro Lichtenfeld")
        author_label.setAlignment(Qt.AlignCenter)
        author_label.setStyleSheet("font-size: 10pt;")
        layout.addWidget(author_label)

        # Year + License on one line
        year_license_label = QLabel("© 2026  •  MIT License")
        year_license_label.setAlignment(Qt.AlignCenter)
        year_license_label.setStyleSheet("color: #999999; font-size: 9pt;")
        layout.addWidget(year_license_label)

        # GitHub link (clickable)
        github_label = QLabel('<a href="https://github.com/aleled/mac-converter-2" style="color: #0078d4;">View on GitHub</a>')
        github_label.setOpenExternalLinks(True)
        github_label.setAlignment(Qt.AlignCenter)
        github_label.setStyleSheet("font-size: 9pt;")
        layout.addWidget(github_label)

        layout.addSpacing(3)

        # OUI Database Information Section
        oui_separator = QLabel()
        oui_separator.setFixedHeight(1)
        oui_separator.setStyleSheet("background-color: #555555;")
        layout.addWidget(oui_separator)

        oui_header = QLabel("OUI Vendor Database")
        oui_header.setAlignment(Qt.AlignCenter)
        oui_header_font = QFont()
        oui_header_font.setPointSize(10)
        oui_header_font.setBold(True)
        oui_header.setFont(oui_header_font)
        layout.addWidget(oui_header)

        # Database stats - build info lines
        if oui_db and oui_db.is_loaded:
            oui_stats = []
            oui_stats.append(f"OUI Entries: {oui_db.vendor_count:,}  •  Unique Vendors: {oui_db.unique_vendor_count:,}")
            oui_stats.append(f"File Size: {oui_db.file_size_display}  •  Updated: {oui_db.last_modified_display}")

            # Check settings for last download timestamp
            last_dl = settings.get('oui_last_downloaded')
            if last_dl:
                try:
                    import datetime
                    dt = datetime.datetime.fromisoformat(last_dl)
                    oui_stats.append(f"Downloaded: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
                except Exception:
                    oui_stats.append(f"Downloaded: {last_dl}")
            else:
                oui_stats.append("Downloaded: Unknown")

            oui_stats.append(f"Source: standards-oui.ieee.org/oui/oui.csv")

            for line in oui_stats:
                stat_label = QLabel(line)
                stat_label.setAlignment(Qt.AlignCenter)
                stat_label.setStyleSheet("color: #b0b0b0; font-size: 8pt;")
                stat_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                layout.addWidget(stat_label)

            # Location on separate line with word wrap
            if oui_db:
                loc_label = QLabel(oui_db.oui_path)
                loc_label.setAlignment(Qt.AlignCenter)
                loc_label.setStyleSheet("color: #888888; font-size: 7pt; font-family: 'Courier New';")
                loc_label.setWordWrap(True)
                loc_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
                layout.addWidget(loc_label)
        else:
            no_db_label = QLabel("Database not loaded")
            no_db_label.setAlignment(Qt.AlignCenter)
            no_db_label.setStyleSheet("color: #d32f2f; font-size: 9pt;")
            layout.addWidget(no_db_label)

        layout.addSpacing(6)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setFixedWidth(100)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setFixedWidth(460)
        self.adjustSize()


def show_about_dialog():
    """Show About dialog in main Qt thread."""
    dlg = AboutDialog()
    dlg.exec_()

# --- OUI Database Viewer ---
class OUIViewerDialog(QDialog):
    """Read-only viewer for the OUI vendor database with search/filter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OUI Database Viewer")
        self.setModal(True)

        try:
            icon_path = get_icon_path()
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
            }
            QLineEdit {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QTableWidget {
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: 1px solid #555555;
                gridline-color: #3c3c3c;
                font-size: 9pt;
            }
            QTableWidget::item {
                padding: 4px;
            }
            QTableWidget::item:selected {
                background-color: #0078d4;
            }
            QHeaderView::section {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                padding: 6px;
                font-weight: bold;
                font-size: 9pt;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # Header
        header = QLabel("OUI Vendor Database")
        hfont = header.font()
        hfont.setBold(True)
        hfont.setPointSize(14)
        header.setFont(hfont)
        layout.addWidget(header)

        # Stats row
        if oui_db and oui_db.is_loaded:
            stats_text = f"{oui_db.vendor_count} OUI entries  |  {oui_db.unique_vendor_count} unique vendors  |  Source: IEEE"
        else:
            stats_text = "Database not loaded"
        stats_label = QLabel(stats_text)
        stats_label.setStyleSheet("color: #999999; font-size: 9pt;")
        layout.addWidget(stats_label)

        # Search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search:")
        search_label.setStyleSheet("font-size: 10pt;")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by OUI prefix or vendor name...")
        self.search_input.textChanged.connect(self.filter_table)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        layout.addLayout(search_layout)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["OUI Prefix", "Vendor / Organization"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(self.table.styleSheet() + """
            QTableWidget {
                alternate-background-color: #262626;
            }
        """)

        # Load data
        self.all_entries = []
        if oui_db and oui_db.is_loaded:
            self.all_entries = oui_db.get_all_entries()
        self.populate_table(self.all_entries)

        layout.addWidget(self.table)

        # Result count label
        self.result_label = QLabel(f"Showing {len(self.all_entries)} of {len(self.all_entries)} entries")
        self.result_label.setStyleSheet("color: #999999; font-size: 9pt;")
        layout.addWidget(self.result_label)

        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setFixedWidth(120)
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.resize(650, 550)

    def populate_table(self, entries):
        """Fill the table with OUI entries."""
        self.table.setRowCount(len(entries))
        for row, (prefix, vendor) in enumerate(entries):
            prefix_item = QTableWidgetItem(prefix)
            prefix_item.setFont(QFont("Courier New", 9))
            vendor_item = QTableWidgetItem(vendor)
            self.table.setItem(row, 0, prefix_item)
            self.table.setItem(row, 1, vendor_item)

    def filter_table(self, text):
        """Filter table based on search text."""
        if not text.strip():
            filtered = self.all_entries
        else:
            query = text.strip().upper()
            filtered = [
                (prefix, vendor) for prefix, vendor in self.all_entries
                if query in prefix.upper().replace(':', '') or query in prefix.upper() or query in vendor.upper()
            ]
        self.populate_table(filtered)
        self.result_label.setText(f"Showing {len(filtered)} of {len(self.all_entries)} entries")


# --- OUI Download Progress Dialog ---
class OUIDownloadDialog(QDialog):
    """Modal dialog showing OUI database download progress."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("OUI Database Update")
        self.setModal(True)
        self._success = False
        self._error_msg = None

        # F11: cooperative-shutdown plumbing. The worker watches
        # _cancel_event; closeEvent sets it and joins the thread.
        self._cancel_event = threading.Event()
        self._worker_thread = None
        # F18: mark in-progress so a second click is refused.
        _oui_download_in_progress.set()

        try:
            icon_path = get_icon_path()
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
            }
            QProgressBar {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-size: 8pt;
            }
            QProgressBar::chunk {
                background-color: #0078d4;
                border-radius: 3px;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Header
        header = QLabel("Updating OUI Database")
        hfont = header.font()
        hfont.setBold(True)
        hfont.setPointSize(11)
        header.setFont(hfont)
        layout.addWidget(header)

        # Source info
        source_label = QLabel("Source: standards-oui.ieee.org")
        source_label.setStyleSheet("color: #999999; font-size: 8pt;")
        layout.addWidget(source_label)

        # Status message
        self.status_label = QLabel("Preparing download...")
        self.status_label.setStyleSheet("font-size: 9pt;")
        layout.addWidget(self.status_label)

        # Progress bar (indeterminate)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.setFixedHeight(20)
        layout.addWidget(self.progress_bar)

        # Result label (hidden initially)
        self.result_label = QLabel("")
        self.result_label.setWordWrap(True)
        self.result_label.setVisible(False)
        layout.addWidget(self.result_label)

        # Close button (hidden initially)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setVisible(False)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self.setFixedWidth(380)
        self.adjustSize()

        # Poll progress queue
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_progress)
        self._poll_timer.start(100)

        # Start download in background thread
        self._start_download()

    def _start_download(self):
        """Start OUI download in background thread."""
        def worker():
            import datetime
            if not oui_db:
                oui_download_progress_queue.put({'status': 'error', 'message': 'OUI database not initialized'})
                return

            def progress_cb(msg):
                if isinstance(msg, dict):
                    # Chunked progress update with bytes info
                    oui_download_progress_queue.put({
                        'status': 'downloading',
                        'bytes_downloaded': msg['bytes_downloaded'],
                        'total_bytes': msg['total_bytes']
                    })
                else:
                    oui_download_progress_queue.put({'status': 'progress', 'message': msg})

            oui_download_progress_queue.put({'status': 'progress', 'message': 'Connecting to IEEE...'})
            success, error = oui_db.download(progress_callback=progress_cb, cancel_event=self._cancel_event)

            if success:
                # Record download time
                settings['oui_last_downloaded'] = datetime.datetime.now().isoformat()
                save_settings(settings)

                oui_download_progress_queue.put({'status': 'progress', 'message': 'Loading database into memory...'})
                load_ok, result = oui_db.load()
                if load_ok:
                    # F12: do not leak the full oui.csv path (contains user's
                    # Windows username) in the success message shown in the UI.
                    oui_download_progress_queue.put({
                        'status': 'done',
                        'message': f'Database updated successfully!\n{result} OUI entries loaded.\nSize: {oui_db.file_size_display}'
                    })
                else:
                    oui_download_progress_queue.put({
                        'status': 'error',
                        'message': f'Download succeeded but load failed: {result}'
                    })
            else:
                oui_download_progress_queue.put({
                    'status': 'error',
                    'message': f'Download failed: {error}'
                })

        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()

    def _poll_progress(self):
        """Poll download progress queue."""
        try:
            msg = oui_download_progress_queue.get_nowait()
        except queue.Empty:
            return

        status = msg['status']

        if status == 'downloading':
            # Percentage-based progress update
            downloaded = msg['bytes_downloaded']
            total = msg['total_bytes']
            if total > 0:
                pct = int(downloaded * 100 / total)
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(pct)
                mb_down = downloaded / (1024 * 1024)
                mb_total = total / (1024 * 1024)
                self.status_label.setText(f"Downloading... {mb_down:.1f} / {mb_total:.1f} MB ({pct}%)")
            return
        elif status == 'progress':
            self.status_label.setText(msg['message'])
        elif status == 'done':
            self._success = True
            self.status_label.setText("Download complete!")
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(100)
            self.result_label.setText(msg['message'])
            self.result_label.setStyleSheet("color: #4caf50; font-size: 9pt;")
            self.result_label.setVisible(True)
            self.close_btn.setVisible(True)
            self._poll_timer.stop()
        elif status == 'error':
            self._success = False
            self._error_msg = msg['message']
            self.status_label.setText("Update failed")
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.result_label.setText(msg['message'])
            self.result_label.setStyleSheet("color: #d32f2f; font-size: 9pt;")
            self.result_label.setVisible(True)
            self.close_btn.setVisible(True)
            self._poll_timer.stop()

    def closeEvent(self, event):
        # F11: signal the worker to stop and wait for it briefly so it
        # doesn't keep writing to the (about-to-be-orphaned) progress
        # queue or racing on oui.csv.tmp.
        self._cancel_event.set()
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        if hasattr(self, '_poll_timer'):
            self._poll_timer.stop()
        # Drain any pending queue messages so they don't leak into a
        # future dialog instance.
        try:
            while True:
                oui_download_progress_queue.get_nowait()
        except queue.Empty:
            pass
        _oui_download_in_progress.clear()
        super().closeEvent(event)


# --- Settings Dialog ---
class SettingsDialog(QDialog):
    """Settings dialog with dark theme, organized sections, and app icon."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MAC Converter - Settings")
        self.setModal(True)

        # Set window icon
        try:
            icon_path = get_icon_path()
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 9pt;
            }
            QLineEdit, QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px;
                font-size: 9pt;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #0078d4;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 9pt;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 5px 12px;
                font-size: 9pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
            QPushButton#cancel {
                background-color: #555555;
            }
            QPushButton#cancel:hover {
                background-color: #666666;
            }
            QGroupBox {
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
                font-weight: bold;
                font-size: 9pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        outer_layout = QVBoxLayout()
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Scroll area for all content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: #2b2b2b; border: none; }")

        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("QWidget { background-color: #2b2b2b; }")
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(20, 15, 20, 15)

        # Header with icon and title
        header_layout = QHBoxLayout()
        try:
            icon_path = get_icon_path()
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(36, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label = QLabel()
            icon_label.setPixmap(scaled_pixmap)
            header_layout.addWidget(icon_label)
        except Exception:
            pass

        header_text = QLabel("Settings")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_text.setFont(header_font)
        header_layout.addWidget(header_text)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # Hotkey Configuration Group
        hotkey_group = QGroupBox("Hotkey Configuration")
        hotkey_layout = QVBoxLayout()

        hotkey_label = QLabel("Global Hotkey:")
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setText(settings.get('hotkey', 'alt+shift+m'))
        self.hotkey_input.setPlaceholderText("e.g., alt+shift+m, ctrl+shift+c")

        hotkey_hint = QLabel("Note: Hotkey change requires app restart")
        hotkey_hint.setStyleSheet("color: #999999; font-size: 8pt; font-style: italic;")

        self.hotkey_error_label = QLabel("")
        self.hotkey_error_label.setStyleSheet("color: #d32f2f; font-size: 9pt;")
        self.hotkey_error_label.setVisible(False)

        hotkey_layout.addWidget(hotkey_label)
        hotkey_layout.addWidget(self.hotkey_input)
        hotkey_layout.addWidget(self.hotkey_error_label)
        hotkey_layout.addWidget(hotkey_hint)
        hotkey_group.setLayout(hotkey_layout)
        main_layout.addWidget(hotkey_group)

        # Notification Preferences Group
        notification_group = QGroupBox("Notification Preferences")
        notification_layout = QVBoxLayout()

        duration_label = QLabel("Popup Duration (seconds):")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(1, 10)
        self.duration_spinbox.setValue(settings.get('notification_duration', 3))

        notification_layout.addWidget(duration_label)
        notification_layout.addWidget(self.duration_spinbox)
        notification_group.setLayout(notification_layout)
        main_layout.addWidget(notification_group)

        # Startup Options Group
        startup_group = QGroupBox("Startup Options")
        startup_layout = QVBoxLayout()

        self.autostart_checkbox = QCheckBox("Start with Windows")
        # Query the actual filesystem state, not just the settings value
        self.autostart_checkbox.setChecked(is_autostart_enabled())

        startup_layout.addWidget(self.autostart_checkbox)
        startup_group.setLayout(startup_layout)
        main_layout.addWidget(startup_group)

        # OUI Vendor Lookup Group
        oui_group = QGroupBox("OUI Vendor Lookup")
        oui_layout = QVBoxLayout()

        self.oui_enabled_checkbox = QCheckBox("Enable vendor lookup (press Enter in format popup)")
        self.oui_enabled_checkbox.setChecked(settings.get('oui_enabled', True))
        oui_layout.addWidget(self.oui_enabled_checkbox)

        self.oui_auto_update_checkbox = QCheckBox("Auto-update OUI database when outdated")
        self.oui_auto_update_checkbox.setChecked(settings.get('oui_auto_update', True))
        oui_layout.addWidget(self.oui_auto_update_checkbox)

        update_interval_label = QLabel("Update interval (days):")
        self.oui_interval_spinbox = QSpinBox()
        self.oui_interval_spinbox.setRange(1, 90)
        self.oui_interval_spinbox.setValue(settings.get('oui_update_interval_days', 7))
        oui_layout.addWidget(update_interval_label)
        oui_layout.addWidget(self.oui_interval_spinbox)

        vendor_timeout_label = QLabel("Vendor popup timeout (seconds):")
        self.oui_vendor_timeout_spinbox = QSpinBox()
        self.oui_vendor_timeout_spinbox.setRange(1, 30)
        self.oui_vendor_timeout_spinbox.setValue(settings.get('oui_vendor_timeout', 5))
        oui_layout.addWidget(vendor_timeout_label)
        oui_layout.addWidget(self.oui_vendor_timeout_spinbox)

        # Database file location
        if oui_db:
            db_path_label = QLabel(f"Location: {oui_db.oui_path}")
            db_path_label.setStyleSheet("color: #888888; font-size: 7pt; font-family: 'Courier New';")
            db_path_label.setWordWrap(True)
            db_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            oui_layout.addWidget(db_path_label)

        # Database status info
        if oui_db and oui_db.is_loaded:
            db_info = f"{oui_db.vendor_count} entries  •  {oui_db.file_size_display}  •  {oui_db.last_modified_display}"
            oui_info_label = QLabel(db_info)
        else:
            oui_info_label = QLabel("Database: Not loaded")
        oui_info_label.setStyleSheet("color: #999999; font-size: 8pt; font-style: italic;")
        oui_layout.addWidget(oui_info_label)

        # Buttons row: Update Now + View Database
        oui_btn_layout = QHBoxLayout()
        oui_btn_layout.setContentsMargins(0, 4, 0, 4)

        update_btn = QPushButton("Update")
        update_btn.clicked.connect(self.manual_oui_update)
        oui_btn_layout.addWidget(update_btn)

        view_btn = QPushButton("View")
        view_btn.clicked.connect(self.view_oui_database)
        if not (oui_db and oui_db.is_loaded):
            view_btn.setEnabled(False)
            view_btn.setToolTip("Database not loaded")
        oui_btn_layout.addWidget(view_btn)

        oui_btn_layout.addStretch()
        oui_layout.addLayout(oui_btn_layout)

        oui_group.setLayout(oui_layout)
        main_layout.addWidget(oui_group)

        main_layout.addStretch()

        scroll_widget.setLayout(main_layout)
        scroll_area.setWidget(scroll_widget)
        outer_layout.addWidget(scroll_area)

        # Buttons (outside scroll area, always visible at bottom)
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(20, 8, 20, 12)
        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancel")
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        outer_layout.addLayout(button_layout)

        self.setLayout(outer_layout)
        self.setFixedSize(480, 620)

    def save_settings(self):
        """Save settings and close dialog."""
        hotkey_str = self.hotkey_input.text().strip()
        err = _validate_hotkey_string(hotkey_str)
        if err is not None:
            self.hotkey_error_label.setText(err)
            self.hotkey_error_label.setVisible(True)
            return  # do NOT call save_settings or close the dialog
        else:
            self.hotkey_error_label.setVisible(False)

        settings['hotkey'] = hotkey_str
        settings['notification_duration'] = self.duration_spinbox.value()
        autostart_wanted = self.autostart_checkbox.isChecked()
        set_autostart_enabled(autostart_wanted)
        settings['autostart'] = is_autostart_enabled()  # reflect actual state
        settings['oui_enabled'] = self.oui_enabled_checkbox.isChecked()
        settings['oui_auto_update'] = self.oui_auto_update_checkbox.isChecked()
        settings['oui_update_interval_days'] = self.oui_interval_spinbox.value()
        settings['oui_vendor_timeout'] = self.oui_vendor_timeout_spinbox.value()
        save_settings(settings)
        self.accept()

    def manual_oui_update(self):
        """Launch manual OUI database update with progress dialog."""
        # F18: refuse to spawn a second concurrent download dialog.
        if _oui_download_in_progress.is_set():
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, "MAC Converter",
                "An OUI database update is already in progress.")
            return
        dlg = OUIDownloadDialog(self)
        dlg.exec_()

    def view_oui_database(self):
        """Open the OUI database viewer dialog."""
        dlg = OUIViewerDialog(self)
        dlg.exec_()

def show_settings_dialog():
    """Show settings dialog in main Qt thread."""
    dlg = SettingsDialog()
    dlg.exec_()

# --- Format Selector Popup ---
class FormatSelectorPopup(QDialog):
    """
    Non-modal popup that displays MAC address formats.
    Shows current format in bold with all available formats clickable.
    Auto-closes after configured duration or when user clicks a format.
    """

    def __init__(self, formats, current_index, duration_seconds, mac_normalized=None):
        super().__init__(None)
        self.formats = formats
        self.current_index = current_index
        self.duration_seconds = duration_seconds
        self.mac_normalized = mac_normalized

        # Window setup
        self.setWindowTitle("MAC Converter")
        try:
            icon_path = get_icon_path()
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass  # Ignore if icon not found

        # Window flags: always on top, tool window (no taskbar entry)
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Header with icon (new)
        header_layout = QHBoxLayout()
        try:
            icon_path = get_icon_path()
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label = QLabel()
            icon_label.setPixmap(scaled_pixmap)
            header_layout.addWidget(icon_label)
        except Exception:
            pass  # Icon not found, just skip

        header_title = QLabel("MAC Converter")
        header_font = header_title.font()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header_title.setFont(header_font)
        header_layout.addWidget(header_title)
        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Separator after header
        separator_header = QLabel()
        separator_header.setStyleSheet("border-bottom: 1px solid #cccccc;")
        separator_header.setFixedHeight(6)
        layout.addWidget(separator_header)

        # Current format (bold)
        current_format_name = formats[current_index][0]
        current_format_value = formats[current_index][1]

        current_label = QLabel(f"{current_format_name}:")
        current_font = current_label.font()
        current_font.setBold(True)
        current_font.setPointSize(12)
        current_label.setFont(current_font)
        layout.addWidget(current_label)

        mac_label = QLabel(current_format_value)
        mac_font = mac_label.font()
        mac_font.setBold(True)
        mac_font.setPointSize(11)
        mac_font.setFamily("Courier New")
        mac_label.setFont(mac_font)
        layout.addWidget(mac_label)

        # Separator
        separator = QLabel("-" * 40)
        separator.setStyleSheet("color: #cccccc;")
        layout.addWidget(separator)

        # Other formats
        other_label = QLabel("Click any format to copy:")
        other_font = other_label.font()
        other_font.setPointSize(9)
        other_label.setFont(other_font)
        other_label.setStyleSheet("color: #666666;")
        layout.addWidget(other_label)

        # Add all other formats as clickable labels
        for i, (fmt_name, fmt_value) in enumerate(formats):
            if i != current_index:
                # Create clickable format label
                fmt_label = QLabel(f"{fmt_name}\n{fmt_value}")
                fmt_label.setCursor(Qt.PointingHandCursor)
                fmt_label.setStyleSheet("""
                    QLabel {
                        padding: 6px;
                        background-color: #f5f5f5;
                        border-radius: 4px;
                        color: #333333;
                    }
                    QLabel:hover {
                        background-color: #e8e8e8;
                        text-decoration: underline;
                    }
                """)

                # Store MAC value for click handler
                fmt_label.mac_value = fmt_value
                fmt_label.mac_index = i

                # Connect click event
                fmt_label.mousePressEvent = lambda event, label=fmt_label: self.on_format_clicked(label)

                layout.addWidget(fmt_label)

        # OUI vendor lookup hint (only shown when OUI is enabled and loaded)
        if settings.get('oui_enabled', True) and oui_db and oui_db.is_loaded:
            oui_hint = QLabel("Press Enter for vendor lookup")
            oui_hint_font = oui_hint.font()
            oui_hint_font.setPointSize(10)
            oui_hint_font.setBold(True)
            oui_hint.setFont(oui_hint_font)
            oui_hint.setStyleSheet("color: #0078d4; padding: 6px; background-color: #e8f0fe; border-radius: 4px;")
            oui_hint.setAlignment(Qt.AlignCenter)
            layout.addWidget(oui_hint)

        layout.addStretch()
        self.setLayout(layout)

        # Auto-close timer
        self.auto_close_timer = QTimer()
        self.auto_close_timer.setSingleShot(True)
        self.auto_close_timer.timeout.connect(self.close)
        self.auto_close_timer.start(int(duration_seconds * 1000))

        # Set window size
        self.setFixedWidth(350)
        self.adjustSize()

        # Position near bottom-right (near system tray)
        self.position_near_tray()

        # F19: scope Enter handling to this popup widget via QShortcut.
        # Previously a global pynput.keyboard.Listener was used, which
        # captured every keystroke system-wide while the popup was open.
        self._enter_shortcut = QShortcut(QKeySequence(Qt.Key_Return), self)
        self._enter_shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        self._enter_shortcut.activated.connect(self._on_enter_pressed)
        self._enter_shortcut_pad = QShortcut(QKeySequence(Qt.Key_Enter), self)
        self._enter_shortcut_pad.setContext(Qt.WidgetWithChildrenShortcut)
        self._enter_shortcut_pad.activated.connect(self._on_enter_pressed)

    def _on_enter_pressed(self):
        """Triggered when Enter is pressed while this popup has focus.

        Replaces the previous global pynput listener (F19). Triggers OUI
        vendor lookup via the existing vendor_lookup_request_queue.
        """
        mac = getattr(self, 'mac_normalized', None)
        if not mac:
            return
        if not (settings.get('oui_enabled', True) and oui_db and oui_db.is_loaded):
            return
        vendor_lookup_request_queue.put({
            'mac_normalized': mac,
        })
        self.close()

    def position_near_tray(self):
        """Position the popup near the system tray (bottom-right corner)."""
        try:
            screen_geom = QApplication.desktop().screenGeometry()
            screen_width = screen_geom.width()
            screen_height = screen_geom.height()

            # Margin from corner
            margin = 20

            # Position: bottom-right with margins
            x = screen_width - self.width() - margin
            y = screen_height - self.height() - margin

            self.move(x, y)
        except Exception:
            # Fallback: center on screen
            self.move(QApplication.desktop().screen().rect().center() - self.rect().center())

    def on_format_clicked(self, label):
        """Handle format click: copy to clipboard and close."""
        # Copy to clipboard
        try:
            pyperclip.copy(label.mac_value)
        except pyperclip.PyperclipException:
            self.setWindowTitle("Clipboard busy")
            return

        # Update settings with new format index
        settings['last_format_index'] = label.mac_index
        save_settings(settings)

        # Close popup
        self.close()

    def closeEvent(self, event):
        """Stop the auto-close timer when closing."""
        if hasattr(self, 'auto_close_timer'):
            self.auto_close_timer.stop()
        super().closeEvent(event)

# --- Vendor Lookup Popup ---
class VendorPopup(QDialog):
    """
    Non-modal popup that displays OUI vendor information for a MAC address.
    Shows vendor name with option to copy to clipboard.
    Auto-closes after countdown without copying vendor.
    """

    def __init__(self, vendor_name, mac_normalized, duration_seconds):
        super().__init__(None)
        self.vendor_name = vendor_name
        self.mac_normalized = mac_normalized
        self.duration_seconds = duration_seconds
        self.remaining_seconds = duration_seconds
        self.vendor_copied = False

        self.setWindowTitle("MAC Converter - Vendor Lookup")
        try:
            icon_path = get_icon_path()
            self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )

        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
            }
            QPushButton {
                background-color: #0078d4;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 10pt;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1084d8;
            }
        """)

        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)

        # Header with icon
        header_layout = QHBoxLayout()
        try:
            icon_path = get_icon_path()
            pixmap = QPixmap(icon_path)
            scaled = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label = QLabel()
            icon_label.setPixmap(scaled)
            header_layout.addWidget(icon_label)
        except Exception:
            pass

        header_title = QLabel("Vendor Lookup")
        hfont = header_title.font()
        hfont.setBold(True)
        hfont.setPointSize(11)
        header_title.setFont(hfont)
        header_layout.addWidget(header_title)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Separator
        sep = QLabel()
        sep.setStyleSheet("border-bottom: 1px solid #555555;")
        sep.setFixedHeight(6)
        layout.addWidget(sep)

        # OUI prefix label
        prefix = mac_normalized[:6].upper()
        prefix_display = ':'.join(prefix[i:i+2] for i in range(0, 6, 2))
        prefix_label = QLabel(f"OUI Prefix: {prefix_display}")
        prefix_label.setStyleSheet("color: #999999; font-size: 9pt;")
        layout.addWidget(prefix_label)

        # Vendor name (large, prominent)
        display_name = vendor_name if vendor_name else "Unknown vendor"
        vendor_label = QLabel(display_name)
        vfont = vendor_label.font()
        vfont.setBold(True)
        vfont.setPointSize(14)
        vendor_label.setFont(vfont)
        if not vendor_name:
            vendor_label.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 14pt;")
        else:
            vendor_label.setStyleSheet("color: #4caf50; font-weight: bold; font-size: 14pt;")
        vendor_label.setWordWrap(True)
        layout.addWidget(vendor_label)

        layout.addSpacing(10)

        # Copy button + timer row
        button_row = QHBoxLayout()

        if vendor_name:
            self.copy_btn = QPushButton("Copy to Clipboard")
            self.copy_btn.clicked.connect(self.copy_vendor)
            button_row.addWidget(self.copy_btn)

        button_row.addStretch()

        # Countdown label
        self.timer_label = QLabel(f"{self.remaining_seconds}s")
        self.timer_label.setStyleSheet("color: #999999; font-size: 9pt;")
        button_row.addWidget(self.timer_label)

        layout.addLayout(button_row)
        self.setLayout(layout)
        self.setFixedWidth(350)
        self.adjustSize()

        # Position near tray
        self.position_near_tray()

        # Ensure keyboard focus
        self.setFocusPolicy(Qt.StrongFocus)
        self.activateWindow()
        self.raise_()

        # Countdown timer (1-second ticks)
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.tick)
        self.countdown_timer.start(1000)

    def position_near_tray(self):
        """Position the popup near the system tray (bottom-right corner)."""
        try:
            screen_geom = QApplication.desktop().screenGeometry()
            x = screen_geom.width() - self.width() - 20
            y = screen_geom.height() - self.height() - 20
            self.move(x, y)
        except Exception:
            pass

    def tick(self):
        """Countdown tick. Auto-close when reaching 0."""
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.close()
        else:
            self.timer_label.setText(f"{self.remaining_seconds}s")

    def copy_vendor(self):
        """Copy vendor name to clipboard and close."""
        if self.vendor_name:
            try:
                pyperclip.copy(self.vendor_name)
            except pyperclip.PyperclipException:
                self.copy_btn.setText("Clipboard busy")
                return
            self.vendor_copied = True
        self.close()

    def closeEvent(self, event):
        """Clean up timer on close."""
        if hasattr(self, 'countdown_timer'):
            self.countdown_timer.stop()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """Escape closes the popup."""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


def show_vendor_popup(vendor_name, mac_normalized, duration_seconds):
    """Show vendor lookup popup. Replaces any existing vendor popup."""
    global current_vendor_popup
    if current_vendor_popup is not None:
        try:
            current_vendor_popup.close()
        except Exception:
            pass
        current_vendor_popup = None
    current_vendor_popup = VendorPopup(vendor_name, mac_normalized, duration_seconds)
    current_vendor_popup.show()


# --- Tray Menu ---
def tray_app():
    """
    Starts the system tray icon with menu. Runs in a background thread.
    Sets global tray_icon and signals tray_icon_ready.
    """
    global tray_icon
    try:
        def about_callback(icon, item):
            about_dialog_request_queue.put(True)

        def settings_callback(icon, item):
            settings_dialog_request_queue.put(True)

        tray_icon = pystray.Icon(
            "mac_converter",
            create_image(),
            "MAC Converter",
            menu=pystray.Menu(
                pystray.MenuItem("Settings", settings_callback),
                pystray.MenuItem("About", about_callback),
                pystray.MenuItem("Quit", on_quit)
            )
        )
        tray_icon_ready.set()  # Signal that icon is ready
        tray_icon.run()
    except Exception as e:
        print(f"[ERROR] Tray app failed: {e}")

def listen_hotkey(app):
    """
    Start global hotkey listener using configurable hotkey from settings.
    Uses pynput.keyboard for cross-platform support (no admin required).

    Args:
        app (QApplication): The running Qt application instance.

    Returns:
        The keyboard listener instance for later cleanup.
    """

    def on_activate():
        handle_hotkey(app)

    # Parse hotkey from settings (e.g., 'alt+shift+m' -> '<alt>+<shift>+m')
    hotkey_str = settings.get('hotkey', 'alt+shift+m')

    def format_hotkey_for_pynput(hotkey_str):
        """
        Convert hotkey string like 'alt+shift+m' to pynput format '<alt>+<shift>+m'.
        Special keys (alt, shift, ctrl, etc.) get angle brackets; regular chars don't.
        """
        special_keys = {
            'alt', 'shift', 'ctrl', 'control', 'win', 'cmd',
            'tab', 'enter', 'space', 'backspace', 'delete', 'escape', 'esc',
            'home', 'end', 'pageup', 'pagedown', 'insert', 'f1', 'f2', 'f3', 'f4',
            'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'up', 'down', 'left', 'right'
        }
        parts = hotkey_str.lower().split('+')
        formatted_parts = []
        for part in parts:
            if part in special_keys:
                formatted_parts.append(f'<{part}>')
            else:
                formatted_parts.append(part)  # Regular chars without angle brackets
        return '+'.join(formatted_parts)

    try:
        formatted = format_hotkey_for_pynput(hotkey_str)
        parsed_hotkey = keyboard.HotKey.parse(formatted)
        print(f"[INFO] Hotkey '{hotkey_str}' registered as '{formatted}' (no admin required).")
    except Exception as e:
        print(f"[ERROR] Invalid hotkey '{hotkey_str}', using default 'alt+shift+m': {e}")
        parsed_hotkey = keyboard.HotKey.parse('<alt>+<shift>+m')

    h = keyboard.HotKey(parsed_hotkey, on_activate)

    def for_canonical(f):
        return lambda k: f(l.canonical(k))

    l = keyboard.Listener(
        on_press=for_canonical(h.press),
        on_release=for_canonical(h.release)
    )
    l.start()
    return l

# --- Settings: Load/Save Logic ---
SETTINGS_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'mac-converter-2')
SETTINGS_FILENAME = 'settings.json'
SETTINGS_PATH = os.path.join(SETTINGS_DIR, SETTINGS_FILENAME)
DEFAULT_SETTINGS = {
    'autostart': False,
    'last_format_index': 0,              # Track last used format (0-9)
    'hotkey': 'alt+shift+m',             # Configurable hotkey
    'notification_duration': 3,          # Notification display seconds
    'author': 'Alejandro Lichtenfeld',   # Correct author name
    'license': 'MIT',
    'about': 'MAC Address Converter Utility v2.4.1\nAuthor: Alejandro Lichtenfeld\nLicense: MIT\nhttps://github.com/aleled/mac-converter-2',
    'oui_enabled': True,                 # Enable OUI vendor lookup
    'oui_auto_update': True,             # Auto-download OUI database when stale
    'oui_update_interval_days': 7,       # Days before OUI database is considered stale
    'oui_vendor_timeout': 5,             # Vendor popup countdown (seconds)
    'oui_last_downloaded': None,         # ISO timestamp of last successful download
}

def _validate_settings(d):
    """Coerce/clamp a raw settings dict, falling back to DEFAULT_SETTINGS per key.

    Returns a fully populated dict where every value passes type+range checks.
    Used by load_settings to reject corrupted or hand-edited bad values, and
    defensively before save to prevent garbage from being persisted.
    """
    out = dict(DEFAULT_SETTINGS)
    if not isinstance(d, dict):
        return out

    # hotkey: non-empty string
    if isinstance(d.get("hotkey"), str) and d["hotkey"].strip():
        out["hotkey"] = d["hotkey"].strip()

    # notification_duration: int in [1, 10]
    nd = d.get("notification_duration")
    if isinstance(nd, int) and not isinstance(nd, bool) and 1 <= nd <= 10:
        out["notification_duration"] = nd

    # autostart: strict bool
    if isinstance(d.get("autostart"), bool):
        out["autostart"] = d["autostart"]

    # last_format_index: int in [0, 9]
    lfi = d.get("last_format_index")
    if isinstance(lfi, int) and not isinstance(lfi, bool) and 0 <= lfi < 10:
        out["last_format_index"] = lfi

    # OUI options
    if isinstance(d.get("oui_enabled"), bool):
        out["oui_enabled"] = d["oui_enabled"]
    if isinstance(d.get("oui_auto_update"), bool):
        out["oui_auto_update"] = d["oui_auto_update"]
    oui_int = d.get("oui_update_interval_days")
    if isinstance(oui_int, int) and not isinstance(oui_int, bool) and 1 <= oui_int <= 365:
        out["oui_update_interval_days"] = oui_int
    oui_t = d.get("oui_vendor_timeout")
    if isinstance(oui_t, int) and not isinstance(oui_t, bool) and 1 <= oui_t <= 60:
        out["oui_vendor_timeout"] = oui_t

    # Last-downloaded timestamp passes through as-is if string
    if isinstance(d.get("oui_last_downloaded"), str):
        out["oui_last_downloaded"] = d["oui_last_downloaded"]

    return out


def load_settings():
    """Load settings from disk. Returns a fully validated dict.

    On JSON parse failure, renames the corrupt file to
    settings.json.corrupt-<unix-ts> and returns DEFAULT_SETTINGS.
    """
    path = os.path.join(SETTINGS_DIR, SETTINGS_FILENAME)
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        ts = int(time.time())
        corrupt_path = f"{path}.corrupt-{ts}"
        try:
            os.replace(path, corrupt_path)
        except OSError:
            pass
        print(f"[WARN] settings.json corrupt, renamed to {corrupt_path}: {e}", file=sys.stderr)
        return dict(DEFAULT_SETTINGS)
    except OSError as e:
        print(f"[WARN] settings.json unreadable: {e}", file=sys.stderr)
        return dict(DEFAULT_SETTINGS)
    return _validate_settings(raw)

def save_settings(settings):
    """Save settings atomically to disk. Thread-safe via _settings_lock."""
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    path = os.path.join(SETTINGS_DIR, SETTINGS_FILENAME)
    with _settings_lock:
        _atomic_write_json(path, settings)

settings = load_settings()

# --- Main ---
def main():
    """
    Main entry point. Starts the Qt application, tray icon, and hotkey listener. Runs the event loop.
    """
    if not acquire_single_instance_mutex():
        # Another instance is already running. Show a brief notification and exit.
        app = QApplication(sys.argv)
        from PyQt5.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("MAC Converter")
        try:
            msg.setWindowIcon(QIcon(get_icon_path()))
        except Exception:
            pass
        msg.setText("MAC Converter is already running.")
        msg.setIcon(QMessageBox.Information)
        msg.exec_()
        sys.exit(0)

    global listener, oui_db
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # Don't exit when dialogs close; tray manages lifecycle

    # Start tray icon in background thread
    t = threading.Thread(target=tray_app, daemon=True)
    t.start()

    # Wait for tray icon to be ready (max 5 seconds)
    if not tray_icon_ready.wait(timeout=5):
        print("[ERROR] Tray icon failed to initialize")
        sys.exit(1)

    # Start hotkey listener
    listener = listen_hotkey(app)

    # Initialize OUI database (background thread)
    if settings.get('oui_enabled', True):
        oui_db = OUIDatabase(
            data_dir=SETTINGS_DIR,
            update_interval_days=settings.get('oui_update_interval_days', 7)
        )

        def oui_init_worker():
            """Background thread: download if stale, then load into memory."""
            import datetime
            if settings.get('oui_auto_update', True) and oui_db.is_stale:
                def progress_cb(msg):
                    if isinstance(msg, dict):
                        return  # Skip chunked progress for startup (no UI)
                    oui_status_queue.put({'type': 'info', 'message': msg})

                success, error = oui_db.download(progress_callback=progress_cb)
                if success:
                    settings['oui_last_downloaded'] = datetime.datetime.now().isoformat()
                    save_settings(settings)
                else:
                    oui_status_queue.put({
                        'type': 'error',
                        'message': f"OUI update failed: {error}"
                    })

            # Load database (even if download failed, try existing file)
            success, result = oui_db.load()
            if success:
                oui_status_queue.put({
                    'type': 'info',
                    'message': f"OUI database loaded: {result} vendors"
                })
            else:
                oui_status_queue.put({
                    'type': 'error',
                    'message': f"OUI database unavailable: {result}"
                })

        # F30: defer OUI auto-update one Qt tick so progress updates
        # don't race the event-loop startup.
        def _start_oui_init():
            oui_thread = threading.Thread(target=oui_init_worker, daemon=True)
            oui_thread.start()

        QTimer.singleShot(0, _start_oui_init)

    # Add QTimer for About dialog
    def poll_about_dialog():
        try:
            about_dialog_request_queue.get_nowait()
        except queue.Empty:
            return
        show_about_dialog()

    about_timer = QTimer()
    about_timer.timeout.connect(poll_about_dialog)
    about_timer.start(200)

    # Add QTimer for Settings dialog
    def poll_settings_dialog():
        try:
            settings_dialog_request_queue.get_nowait()
        except queue.Empty:
            return
        show_settings_dialog()

    settings_timer = QTimer()
    settings_timer.timeout.connect(poll_settings_dialog)
    settings_timer.start(200)

    # Add QTimer for Format Popup
    def poll_format_popup():
        try:
            request = format_popup_request_queue.get_nowait()
        except queue.Empty:
            return

        if request['type'] == 'format':
            show_format_popup(
                app,
                request['formats'],
                request['current_index'],
                request['duration'],
                request.get('mac_normalized')
            )
        elif request['type'] == 'error':
            show_error_popup(
                app,
                request['message'],
                request['duration']
            )

    format_timer = QTimer()
    format_timer.timeout.connect(poll_format_popup)
    format_timer.start(50)  # Poll more frequently for responsive UI

    # Add QTimer for vendor lookup requests (Enter key from global listener)
    def poll_vendor_lookup():
        try:
            request = vendor_lookup_request_queue.get_nowait()
        except queue.Empty:
            return
        mac = request['mac_normalized']
        # Close the format popup
        if current_format_popup is not None:
            try:
                current_format_popup.close()
            except Exception:
                pass
        vendor_name = oui_db.lookup(mac) if oui_db and oui_db.is_loaded else None
        duration = settings.get('oui_vendor_timeout', 5)
        show_vendor_popup(vendor_name, mac, duration)

    vendor_timer = QTimer()
    vendor_timer.timeout.connect(poll_vendor_lookup)
    vendor_timer.start(50)

    # Add QTimer for OUI status notifications
    def poll_oui_status():
        try:
            msg = oui_status_queue.get_nowait()
        except queue.Empty:
            return
        if tray_icon and tray_icon_ready.is_set():
            try:
                tray_icon.notify(
                    title="MAC Converter",
                    message=msg['message']
                )
            except Exception:
                pass
        print(f"[OUI] {msg.get('type', 'info').upper()}: {msg['message']}")

    oui_status_timer = QTimer()
    oui_status_timer.timeout.connect(poll_oui_status)
    oui_status_timer.start(500)

    app.exec_()
    if listener:
        listener.stop()

if __name__ == "__main__":
    main()
