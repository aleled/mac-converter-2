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
import platform
import os
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QSizePolicy, QCheckBox, QPushButton, QLineEdit, QSpinBox, QGroupBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QIcon, QBrush, QPixmap
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QCursor
import queue
import ctypes
import time
from pynput import keyboard
import json

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
    if listener:
        listener.stop()
    exit_event.set()
    app = QApplication.instance()
    if app:
        app.quit()

exit_event = threading.Event()
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

# --- Format popup display function ---
def show_format_popup(app, formats, current_index, duration_seconds):
    """
    Show format selector popup with current format in bold.
    Replaces any existing popup instantly for responsive UX.

    Args:
        app (QApplication): The running Qt application instance.
        formats (list): List of (name, value) tuples for all MAC formats.
        current_index (int): Index of the currently selected format.
        duration_seconds (int): How long to display the popup (in seconds).
    """
    global current_format_popup

    # Close and clean up previous popup if exists
    if current_format_popup is not None:
        try:
            current_format_popup.close()
        except:
            pass
        current_format_popup = None

    # Create and show new popup
    current_format_popup = FormatSelectorPopup(formats, current_index, duration_seconds)
    current_format_popup.show()


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
    except:
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
    except:
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
    text = pyperclip.paste()
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
    pyperclip.copy(converted_mac)

    # Update last used format index
    settings['last_format_index'] = next_idx
    save_settings(settings)

    # Queue format selector popup request (thread-safe)
    duration = settings.get('notification_duration', 3)
    format_popup_request_queue.put({
        'type': 'format',
        'formats': formats,
        'current_index': next_idx,
        'duration': duration
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
        except:
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
        layout.setSpacing(15)
        layout.setContentsMargins(30, 30, 30, 30)

        # Icon at top (larger, centered)
        try:
            icon_path = get_icon_path()
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label = QLabel()
            icon_label.setPixmap(scaled_pixmap)
            icon_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(icon_label)
        except:
            pass

        # App name
        app_name = QLabel("MAC Address Converter")
        app_name.setAlignment(Qt.AlignCenter)
        app_font = QFont()
        app_font.setPointSize(18)
        app_font.setBold(True)
        app_name.setFont(app_font)
        layout.addWidget(app_name)

        # Version
        version_label = QLabel("Version 2.2.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #999999; font-size: 11pt;")
        layout.addWidget(version_label)

        # Separator
        separator = QLabel()
        separator.setFixedHeight(1)
        separator.setStyleSheet("background-color: #555555;")
        layout.addWidget(separator)

        # Author
        author_label = QLabel("Created by Alejandro Lichtenfeld")
        author_label.setAlignment(Qt.AlignCenter)
        author_label.setStyleSheet("font-size: 11pt;")
        layout.addWidget(author_label)

        # Year
        year_label = QLabel("© 2026")
        year_label.setAlignment(Qt.AlignCenter)
        year_label.setStyleSheet("color: #999999; font-size: 10pt;")
        layout.addWidget(year_label)

        # License
        license_label = QLabel("Licensed under MIT License")
        license_label.setAlignment(Qt.AlignCenter)
        license_label.setStyleSheet("color: #999999; font-size: 10pt;")
        layout.addWidget(license_label)

        # GitHub link (clickable)
        github_label = QLabel('<a href="https://github.com/aleled/mac-converter-2" style="color: #0078d4;">View on GitHub</a>')
        github_label.setOpenExternalLinks(True)
        github_label.setAlignment(Qt.AlignCenter)
        github_label.setStyleSheet("font-size: 10pt;")
        layout.addWidget(github_label)

        layout.addSpacing(10)

        # Close button
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        close_button.setFixedWidth(120)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.setFixedSize(450, 500)


def show_about_dialog():
    """Show About dialog in main Qt thread."""
    dlg = AboutDialog()
    dlg.exec_()

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
        except:
            pass

        # Apply dark theme stylesheet
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 11pt;
            }
            QLineEdit, QSpinBox {
                background-color: #3c3c3c;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                font-size: 10pt;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 1px solid #0078d4;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 10pt;
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
                margin-top: 12px;
                font-weight: bold;
                font-size: 11pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Header with icon and title
        header_layout = QHBoxLayout()
        try:
            icon_path = get_icon_path()
            pixmap = QPixmap(icon_path)
            scaled_pixmap = pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            icon_label = QLabel()
            icon_label.setPixmap(scaled_pixmap)
            header_layout.addWidget(icon_label)
        except:
            pass

        header_text = QLabel("Settings")
        header_font = QFont()
        header_font.setPointSize(16)
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
        hotkey_hint.setStyleSheet("color: #999999; font-size: 9pt; font-style: italic;")

        hotkey_layout.addWidget(hotkey_label)
        hotkey_layout.addWidget(self.hotkey_input)
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
        self.autostart_checkbox.setChecked(settings.get('autostart', False))

        startup_layout.addWidget(self.autostart_checkbox)
        startup_group.setLayout(startup_layout)
        main_layout.addWidget(startup_group)

        main_layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("cancel")
        cancel_button.clicked.connect(self.reject)

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)
        self.setFixedWidth(500)

    def save_settings(self):
        """Save settings and close dialog."""
        settings['hotkey'] = self.hotkey_input.text().strip()
        settings['notification_duration'] = self.duration_spinbox.value()
        settings['autostart'] = self.autostart_checkbox.isChecked()
        save_settings(settings)
        self.accept()

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

    def __init__(self, formats, current_index, duration_seconds):
        super().__init__(None)
        self.formats = formats
        self.current_index = current_index
        self.duration_seconds = duration_seconds

        # Window setup
        self.setWindowTitle("MAC Converter")
        try:
            icon_path = get_icon_path()
            self.setWindowIcon(QIcon(icon_path))
        except:
            pass  # Ignore if icon not found

        # Window flags: always on top, tool window, no frame
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
        except:
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
        except:
            # Fallback: center on screen
            self.move(QApplication.desktop().screen().rect().center() - self.rect().center())

    def on_format_clicked(self, label):
        """Handle format click: copy to clipboard and close."""
        # Copy to clipboard
        pyperclip.copy(label.mac_value)

        # Update settings with new format index
        settings['last_format_index'] = label.mac_index
        save_settings(settings)

        # Close popup
        self.close()

    def closeEvent(self, event):
        """Stop timer when closing."""
        if hasattr(self, 'auto_close_timer'):
            self.auto_close_timer.stop()
        super().closeEvent(event)

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
SETTINGS_PATH = os.path.join(SETTINGS_DIR, 'settings.json')
DEFAULT_SETTINGS = {
    'autostart': False,
    'last_format_index': 0,              # Track last used format (0-9)
    'hotkey': 'alt+shift+m',             # Configurable hotkey
    'notification_duration': 3,          # Notification display seconds
    'author': 'Alejandro Lichtenfeld',   # Correct author name
    'license': 'MIT',
    'about': 'MAC Address Converter Utility v2.2.0\nAuthor: Alejandro Lichtenfeld\nLicense: MIT\nhttps://github.com/aleled/mac-converter-2'
}

def load_settings():
    if not os.path.exists(SETTINGS_PATH):
        os.makedirs(SETTINGS_DIR, exist_ok=True)
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            s = json.load(f)
        # Fill in any missing keys
        for k, v in DEFAULT_SETTINGS.items():
            if k not in s:
                s[k] = v
        return s
    except Exception:
        return DEFAULT_SETTINGS.copy()

def save_settings(settings):
    os.makedirs(SETTINGS_DIR, exist_ok=True)
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(settings, f, indent=2)

settings = load_settings()

# --- Main ---
def main():
    """
    Main entry point. Starts the Qt application, tray icon, and hotkey listener. Runs the event loop.
    """
    global listener
    app = QApplication(sys.argv)

    # Start tray icon in background thread
    t = threading.Thread(target=tray_app, daemon=True)
    t.start()

    # Wait for tray icon to be ready (max 5 seconds)
    if not tray_icon_ready.wait(timeout=5):
        print("[ERROR] Tray icon failed to initialize")
        sys.exit(1)

    # Start hotkey listener
    listener = listen_hotkey(app)

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
                request['duration']
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

    app.exec_()
    if listener:
        listener.stop()

if __name__ == "__main__":
    main()
