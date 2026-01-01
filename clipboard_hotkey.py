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
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QSizePolicy, QCheckBox, QPushButton, QLineEdit, QSpinBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QIcon, QBrush
from PyQt5.QtCore import QTimer
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

# Global icon reference for notifications
tray_icon = None
tray_icon_ready = threading.Event()

# Global hotkey listener
listener = None

# Global notification timer management - allows cancelling previous notification
current_notification_timer = None

# --- Helper function for notifications with custom duration ---
def show_notification_with_duration(icon, message, title, duration_seconds):
    """
    Show notification and auto-remove after specified duration.
    Cancels any previous notification timer to allow immediate updates.

    Args:
        icon (pystray.Icon): The tray icon instance.
        message (str): The notification message (usually the MAC address).
        title (str): The notification title.
        duration_seconds (int): How long to display the notification in seconds.
    """
    global current_notification_timer

    if not icon:
        return

    # Cancel previous notification timer if one is active
    if current_notification_timer is not None:
        current_notification_timer.cancel()
        try:
            icon.remove_notification()
        except:
            pass  # Ignore errors if notification already dismissed

    icon.notify(message, title)

    # Auto-remove after duration using threading.Timer
    def remove():
        try:
            icon.remove_notification()
        except:
            pass  # Ignore errors if notification already dismissed

    current_notification_timer = threading.Timer(duration_seconds, remove)
    current_notification_timer.daemon = True
    current_notification_timer.start()

def handle_hotkey(app):
    """
    Handle hotkey press: auto-cycle MAC format and show notification.
    Uses global tray_icon variable to display notifications.

    Args:
        app (QApplication): The running Qt application instance.
    """
    global tray_icon

    text = pyperclip.paste()
    mac = detect_mac(text)

    if not mac:
        # Show error notification
        if tray_icon:
            duration = settings.get('notification_duration', 3)
            show_notification_with_duration(
                tray_icon,
                "No valid MAC address in clipboard",
                "MAC Converter",
                duration
            )
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

    # Show success notification with just the MAC address
    if tray_icon:
        duration = settings.get('notification_duration', 3)
        show_notification_with_duration(
            tray_icon,
            converted_mac,
            "MAC Converter",
            duration
        )

# --- About Dialog ---
def show_about_dialog():
    """
    Shows a modal About dialog that blocks all other app windows until closed. No timer, no auto-close.
    """
    from PyQt5.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton
    from PyQt5.QtCore import Qt
    app = QApplication.instance()
    dlg = QDialog(None)
    dlg.setWindowTitle("About MAC Address Converter")
    modality = getattr(Qt, 'WindowModal', None)
    if modality is not None:
        dlg.setWindowModality(modality)
    stays_on_top = getattr(Qt, 'WindowStaysOnTopHint', None)
    if stays_on_top is not None:
        dlg.setWindowFlags(dlg.windowFlags() | stays_on_top)
    layout = QVBoxLayout()
    label = QLabel(settings['about'])
    label.setWordWrap(True)
    layout.addWidget(label)
    btn = QPushButton("OK")
    btn.clicked.connect(lambda: dlg.done(0))  # Use done(0) to close immediately
    layout.addWidget(btn)
    dlg.setLayout(layout)
    dlg.setFixedWidth(400)
    dlg.exec_()  # Modal: blocks until closed

# --- Settings Dialog ---
class SettingsDialog(QDialog):
    """Settings dialog for configuring hotkey and notification preferences."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MAC Converter - Settings")
        self.setModal(True)
        try:
            stays_on_top = getattr(Qt, 'WindowStaysOnTopHint', None)
            if stays_on_top is not None:
                self.setWindowFlags(self.windowFlags() | stays_on_top)
        except Exception:
            pass

        layout = QVBoxLayout()

        # Hotkey setting
        hotkey_label = QLabel("Global Hotkey:")
        self.hotkey_input = QLineEdit()
        self.hotkey_input.setText(settings.get('hotkey', 'alt+shift+m'))
        self.hotkey_input.setPlaceholderText("e.g., alt+shift+m, ctrl+shift+c")

        # Notification duration setting
        duration_label = QLabel("Notification Duration (seconds):")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(1, 10)
        self.duration_spinbox.setValue(settings.get('notification_duration', 3))

        # Autostart setting
        self.autostart_checkbox = QCheckBox("Start with Windows")
        self.autostart_checkbox.setChecked(settings.get('autostart', False))

        # Buttons
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        save_button.clicked.connect(self.save_settings)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)

        # Add all to layout
        layout.addWidget(hotkey_label)
        layout.addWidget(self.hotkey_input)
        layout.addWidget(duration_label)
        layout.addWidget(self.duration_spinbox)
        layout.addWidget(self.autostart_checkbox)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def save_settings(self):
        """Save settings and close dialog."""
        settings['hotkey'] = self.hotkey_input.text().strip()
        settings['notification_duration'] = self.duration_spinbox.value()
        settings['autostart'] = self.autostart_checkbox.isChecked()
        save_settings(settings)
        self.accept()

        # Note: Hotkey change requires app restart
        # Could show a message box here to notify user

def show_settings_dialog():
    """Show settings dialog in main Qt thread."""
    dlg = SettingsDialog()
    dlg.exec_()

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

    app.exec_()
    if listener:
        listener.stop()

if __name__ == "__main__":
    main()
