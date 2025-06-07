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
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QHBoxLayout, QWidget, QSizePolicy
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QIcon, QBrush
from PyQt5.QtCore import QTimer
import queue
import ctypes
import time
import keyboard as kb  # pip install keyboard
import json

# --- Admin Privilege Check for keyboard package ---
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    print("[WARNING] This script must be run as Administrator for global hotkeys to work on Windows (keyboard package requirement).\nRight-click PowerShell and choose 'Run as administrator'.")

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
        listener.unhook_all_hotkeys()
    exit_event.set()
    app = QApplication.instance()
    if app:
        app.quit()

exit_event = threading.Event()
dialog_request_queue = queue.Queue()

# --- PyQt Format Selector Dialog ---
# Alignment helper for PyQt5/PySide2 compatibility
try:
    ALIGN_LEFT = Qt.AlignmentFlag.AlignLeft
    ALIGN_VCENTER = Qt.AlignmentFlag.AlignVCenter
    ALIGN_RIGHT = Qt.AlignmentFlag.AlignRight
    ALIGN_CENTER = Qt.AlignmentFlag.AlignCenter
    qt_align = lambda val: val
except AttributeError:
    ALIGN_LEFT = 0x0001
    ALIGN_VCENTER = 0x0080
    ALIGN_RIGHT = 0x0002
    ALIGN_CENTER = 0x0084
    qt_align = lambda val: Qt.Alignment(val)

class FormatSelector(QDialog):
    """
    PyQt5 dialog for selecting a MAC address format. Modern dark theme, orange/gray palette, green highlight, background texture, and improved layout per UI/UX requirements.
    Now uses a custom QWidget-based layout to mimic a table, avoiding QTableWidget confusion.
    """
    def __init__(self, formats, timeout=None, clipboard_mac=None):
        super().__init__()
        self.formats = formats
        self.selected = None
        self.timeout = timeout if timeout is not None else settings.get('timer', 8)
        self.current_row = 0
        self.current_col = 0  # 0 = UPPER CASE, 1 = LOWER CASE
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timeout)
        self.timer.setSingleShot(True)
        self.selection_made = False
        self.clipboard_mac = clipboard_mac
        self.cell_labels = []  # 2D list: [row][col] -> QLabel
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("MAC Address Converter")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setFixedSize(700, 400)
        # Fix WindowStaysOnTopHint for PyQt5 compatibility
        try:
            flag = getattr(Qt, 'WindowStaysOnTopHint', None)
            if flag is not None:
                self.setWindowFlags(self.windowFlags() | flag)
        except Exception:
            pass
        title = QLabel("Select which mac address to copy to clipboard")
        title.setStyleSheet("background: #ff9800; color: #23272e; font-size: 20px; font-weight: bold; padding: 12px; border-radius: 8px; margin-bottom: 10px;")
        mac_label = QLabel(f"<span style='font-family:monospace;font-size:16px;color:#ff9800'>{self.clipboard_mac or ''}</span>")
        mac_label.setStyleSheet("color: #ff9800; background: transparent; margin-bottom: 8px;")
        instr_box = QLabel(
            "<span style='color:#fff;font-size:13px;'>"
            "Use <b>↑</b> <b>↓</b> to move, <b>←</b> <b>→</b> to select UPPER/LOWER, <b>ENTER</b> to copy, <b>ESC</b> to cancel.<br>"
            f"Auto-selects default after {self.timeout} seconds."
            "</span>"
        )
        instr_box.setStyleSheet("background: #2d313a; border-radius: 6px; padding: 8px; margin-top: 10px; color: #ff9800;")

        # --- Calculate max width for each column ---
        font = QFont("Consolas", 14)
        label_font = QFont()
        label_font.setBold(True)
        label_font.setPointSize(15)
        fm_label = self.fontMetrics() if hasattr(self, 'fontMetrics') else None
        # Gather all text for each column
        label_texts = [self.formats[row*2][0].split()[0] for row in range(4)]
        upper_texts = [self.formats[row*2][1] for row in range(4)]
        lower_texts = [self.formats[row*2+1][1] for row in range(4)]
        # Include headers
        label_texts.append("")
        upper_texts.append("Upper Case")
        lower_texts.append("Lower Case")
        # Use QFontMetrics to get pixel width
        metrics = self.fontMetrics()
        label_width = max([metrics.boundingRect(text).width() for text in label_texts]) + 24
        upper_width = max([metrics.boundingRect(text).width() for text in upper_texts]) + 24
        lower_width = max([metrics.boundingRect(text).width() for text in lower_texts]) + 24

        # --- Custom Table-Like Layout ---
        table_widget = QWidget()
        table_layout = QVBoxLayout()
        table_layout.setSpacing(0)
        table_layout.setContentsMargins(0, 0, 0, 0)
        # Header row
        header_row = QHBoxLayout()
        header_row.setSpacing(0)
        header_row.setContentsMargins(0, 0, 0, 0)
        header_label = self._make_header_label("Description", qt_align(ALIGN_LEFT | ALIGN_VCENTER), label_width)
        header_upper = self._make_header_label("Upper Case", qt_align(ALIGN_LEFT | ALIGN_VCENTER), upper_width)
        header_lower = self._make_header_label("Lower Case", qt_align(ALIGN_LEFT | ALIGN_VCENTER), lower_width)
        header_row.addWidget(header_label)
        header_row.addWidget(header_upper)
        header_row.addWidget(header_lower)
        table_layout.addLayout(header_row)
        self.cell_labels = []
        row_layouts = []  # Store row layouts for post-layout sizing
        label_widgets = [header_label]
        upper_widgets = [header_upper]
        lower_widgets = [header_lower]
        for row in range(4):
            row_layout = QHBoxLayout()
            row_layout.setSpacing(0)
            row_layout.setContentsMargins(0, 0, 0, 0)
            # Use the full description for the first column
            style_name = self.formats[row*2][0]
            label = QLabel(style_name)
            label.setStyleSheet("background: #23272e; color: #ff9800; font-weight: bold; font-size: 17px; padding: 8px 0px 8px 16px;")
            label.setAlignment(qt_align(ALIGN_LEFT | ALIGN_VCENTER))
            label.setMinimumWidth(label_width)
            row_layout.addWidget(label)
            row_cells = []
            label_widgets.append(label)
            for col, width, col_widgets in zip(range(2), [upper_width, lower_width], [upper_widgets, lower_widgets]):
                mac_val = self.formats[row*2+col][1]
                cell = QLabel(mac_val)
                cell.setFont(QFont("Consolas", 16))
                cell.setAlignment(qt_align(ALIGN_LEFT | ALIGN_VCENTER))
                cell.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                cell.setMinimumWidth(width)
                cell.setStyleSheet("padding: 8px 0px 8px 16px; background: #23272e; color: #fff; font-family: Consolas; font-size: 16px; border: none;")
                row_layout.addWidget(cell)
                row_cells.append(cell)
                col_widgets.append(cell)
            self.cell_labels.append(row_cells)
            table_layout.addLayout(row_layout)
            row_layouts.append(row_layout)
        table_widget.setLayout(table_layout)

        # --- Post-layout: ensure all widgets in a column have the same min width ---
        columns = [label_widgets, upper_widgets, lower_widgets]
        for col_widgets in columns:
            max_width = max(w.sizeHint().width() for w in col_widgets if w is not None)
            for w in col_widgets:
                if w is not None:
                    w.setMinimumWidth(max_width)

        # Make window large enough to avoid scrollbars
        self.setFixedSize(max(label_width + upper_width + lower_width + 80, 900), 420)

        layout = QVBoxLayout()
        # Move the instruction closer to the table, and show the clipboard mac above it
        layout.addWidget(table_widget)
        # Add the moved instruction right below the table
        title = QLabel("Select which mac address to copy to clipboard")
        title.setStyleSheet("background: #ff9800; color: #23272e; font-size: 20px; font-weight: bold; padding: 12px; border-radius: 8px; margin-bottom: 4px; margin-top: 10px;")
        layout.addWidget(title)
        # Information label for clipboard mac and timer
        if not hasattr(self, '_initial_clipboard_mac') or not self._initial_clipboard_mac:
            self._initial_clipboard_mac = self.clipboard_mac or "(none)"
        self._info_mac_val = QLabel(self._initial_clipboard_mac)
        self._info_mac_val.setStyleSheet("background: #e3f2fd; color: #1a237e; font-family: Consolas, monospace; padding: 8px 16px; border-top-right-radius: 7px; border-bottom-right-radius: 7px; font-size: 16px; border-left: 1.5px solid #90caf9;")
        self._info_timer_val = QLabel(f"{self.timeout}")
        self._info_timer_val.setStyleSheet("background: #fffde7; color: #b26a00; font-weight: bold; padding: 8px 16px; border-radius: 7px; font-size: 16px; margin-left: 8px; border: 1.5px solid #ffe082;")
        mac_info = QWidget()
        mac_info_layout = QHBoxLayout()
        mac_info_layout.setContentsMargins(0, 0, 0, 0)
        mac_info_layout.setSpacing(0)
        label = QLabel("Mac address brought from clipboard:")
        label.setStyleSheet("background: #1976d2; color: #fff; font-weight: bold; padding: 8px 12px; border-top-left-radius: 7px; border-bottom-left-radius: 7px; font-size: 15px;")
        mac_info_layout.addWidget(label)
        mac_info_layout.addWidget(self._info_mac_val)
        # Timer label
        timer_label = QLabel("Time left:")
        timer_label.setStyleSheet("background: #fffde7; color: #b26a00; font-weight: bold; padding: 8px 12px; border-radius: 7px 0 0 7px; font-size: 15px; margin-left: 16px;")
        mac_info_layout.addWidget(timer_label)
        mac_info_layout.addWidget(self._info_timer_val)
        mac_info.setLayout(mac_info_layout)
        layout.addWidget(mac_info)
        instr_box = QLabel(
            "<span style='color:#fff;font-size:13px;'>"
            "Use <b>↑</b> <b>↓</b> to move, <b>←</b> <b>→</b> to select UPPER/LOWER, <b>ENTER</b> to copy, <b>ESC</b> to cancel.<br>"
            f"Auto-selects default after {self.timeout} seconds."
            "</span>"
        )
        instr_box.setStyleSheet("background: #2d313a; border-radius: 6px; padding: 8px; margin-top: 4px; color: #ff9800;")
        layout.addWidget(instr_box)
        self.setLayout(layout)
        self.current_row = 0
        self.current_col = 0
        self.update_selection()
        self.timer.start(self.timeout * 1000)
        self.setFocus()
        # Add timer update
        self._remaining_time = self.timeout
        self._timer_tick = QTimer(self)
        def _update_info_timer():
            if self._remaining_time > 0:
                self._remaining_time -= 1
                self._info_timer_val.setText(str(self._remaining_time))
            else:
                self._timer_tick.stop()
        self._update_info_timer = _update_info_timer
        self._timer_tick.timeout.connect(self._update_info_timer)
        self._timer_tick.start(1000)

    def _make_header_label(self, text, align, min_width):
        label = QLabel(text)
        # Match cell left padding for perfect alignment, force left alignment
        label.setStyleSheet("background: #23272e; color: #fff; font-weight: bold; font-size: 17px; padding: 8px 0px 8px 16px; border-bottom: 2px solid #444; text-align: left;")
        label.setAlignment(align)
        label.setMinimumWidth(min_width)
        return label

    def update_selection(self):
        # Clamp indices
        if self.current_col < 0:
            self.current_col = 0
        elif self.current_col > 1:
            self.current_col = 1
        if self.current_row < 0:
            self.current_row = 0
        elif self.current_row > 3:
            self.current_row = 3
        # Reset all cells
        for row in range(4):
            for col in range(2):
                cell = self.cell_labels[row][col]
                cell.setAlignment(qt_align(ALIGN_LEFT | ALIGN_VCENTER))
                cell.setStyleSheet("padding: 8px 0px 8px 16px; background: #23272e; color: #fff; font-family: Consolas; font-size: 16px; border: none;")
        # Highlight current cell
        cell = self.cell_labels[self.current_row][self.current_col]
        cell.setAlignment(qt_align(ALIGN_LEFT | ALIGN_VCENTER))
        # Use a more vibrant purple for text on green background
        cell.setStyleSheet("padding: 8px 0px 8px 16px; background: #39d353; color: #b266ff; font-family: Consolas; font-size: 16px; font-weight: bold; border: none;")

    def keyPressEvent(self, a0):
        # Only stop the main selection timer, never stop the info label timer
        if self.timer and self.timer.isActive():
            self.timer.stop()
        key = a0.key() if a0 else None
        if key == getattr(Qt, 'Key_Up', 0x01000013):
            self.current_row = (self.current_row - 1) % 4
            self.update_selection()
        elif key == getattr(Qt, 'Key_Down', 0x01000015):
            self.current_row = (self.current_row + 1) % 4
            self.update_selection()
        elif key == getattr(Qt, 'Key_Left', 0x01000012):
            if self.current_col == 1:
                self.current_col = 0
                self.update_selection()
        elif key == getattr(Qt, 'Key_Right', 0x01000014):
            if self.current_col == 0:
                self.current_col = 1
                self.update_selection()
        elif key == getattr(Qt, 'Key_Return', 0x01000004) or key == getattr(Qt, 'Key_Enter', 0x01000005):
            self.selected = (self.current_row, self.current_col)
            self.selection_made = True
            idx = self.current_row*2 + self.current_col
            pyperclip.copy(self.formats[idx][1])
            self.hide()
        elif key == getattr(Qt, 'Key_Escape', 0x01000000):
            self.selected = None
            self.selection_made = False
            self.hide()
        else:
            super().keyPressEvent(a0)

    def mousePressEvent(self, a0):
        if a0 is not None:
            pos = a0.pos()
            # Map click to cell by checking label geometries
            found = False
            for row in range(len(self.cell_labels)):
                for col in range(len(self.cell_labels[row])):
                    cell = self.cell_labels[row][col]
                    # Only columns 0 and 1 (index 0,1) are selectable
                    if col not in (0, 1):
                        continue
                    rect = cell.geometry()
                    # Map cell geometry to dialog coordinates
                    cell_pos = cell.mapTo(self, rect.topLeft())
                    cell_rect = rect.translated(cell_pos - rect.topLeft())
                    if cell_rect.contains(pos):
                        # Only allow selection for columns 0 and 1
                        self.current_row = row
                        self.current_col = col
                        self.update_selection()
                        self.selected = (row, col)
                        self.selection_made = True
                        idx = row*2 + col
                        pyperclip.copy(self.formats[idx][1])
                        self.hide()
                        found = True
                        break
                if found:
                    break
        # else: ignore clicks outside selectable cells
        super().mousePressEvent(a0)

    def mouseDoubleClickEvent(self, a0):
        # For robustness, treat double-click the same as single click
        self.mousePressEvent(a0)

    def hideEvent(self, a0):
        """
        Handles the dialog hide event. Resets the global dialog_open flag and stops the info label timer.
        """
        global dialog_open
        dialog_open = False
        if hasattr(self, '_timer_tick') and self._timer_tick.isActive():
            self._timer_tick.stop()
        super().hideEvent(a0)

    def on_timeout(self):
        """
        Handles the dialog timeout event. Closes the dialog without selection.
        """
        self.selected = None
        self.selection_made = False
        self.hide()

    def showEvent(self, a0):
        super().showEvent(a0)
        self.activateWindow()
        self.raise_()
        self.setFocus()
        # Reset timer display on show
        self._remaining_time = self.timeout
        self._info_timer_val.setText(str(self._remaining_time))
        if hasattr(self, '_timer_tick') and not self._timer_tick.isActive():
            self._timer_tick.start(1000)
        # Force window to foreground and focus on Windows
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 1)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            ctypes.windll.user32.SetFocus(hwnd)
            ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        except Exception as e:
            print(f"[DEBUG] Foreground force failed: {e}")

# --- Hotkey Handler ---
dialog_open = False
last_dialog_open_warning = 0
_dlg_refs = []  # Keep dialog references alive

def show_format_selector_from_queue():
    """
    Checks the dialog request queue and shows the FormatSelector dialog if not already open.
    Ensures only one dialog is open at a time. Brings dialog to front and focuses it.
    """
    global dialog_open, last_dialog_open_warning, _dlg_refs
    if dialog_open:
        now = time.time()
        last_dialog_open_warning = now
        return
    try:
        formats, clipboard_mac = dialog_request_queue.get_nowait()
    except queue.Empty:
        return
    dialog_open = True
    # --- Windows focus workaround: dummy window ---
    dummy = QWidget()
    dummy.setGeometry(0, 0, 1, 1)
    dummy.show()
    dummy.activateWindow()
    dummy.raise_()
    dummy.hide()
    dummy.deleteLater()
    # Keep a reference to the dialog to prevent garbage collection
    dlg = FormatSelector(formats, timeout=settings.get('timer', 8), clipboard_mac=clipboard_mac)
    _dlg_refs.append(dlg)
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    dlg.setFocus()
    try:
        hwnd = int(dlg.winId())
        ctypes.windll.user32.ShowWindow(hwnd, 1)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        ctypes.windll.user32.SetFocus(hwnd)
        ctypes.windll.user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
    except Exception:
        pass

def handle_hotkey(app):
    """
    Handles the hotkey event: checks clipboard for a MAC address, converts it to all formats, and queues the format selector dialog.
    Args:
        app (QApplication): The running Qt application instance.
    """
    text = pyperclip.paste()
    mac = detect_mac(text)
    if not mac:
        pyperclip.copy("not a valid mac :-)")
        return
    formats = convert_mac(mac)
    dialog_request_queue.put((formats, mac))

# --- About Dialog Stub ---
from PyQt5.QtWidgets import QMessageBox

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

# --- Tray Menu: Add About, Settings, License ---
def tray_app():
    """
    Starts the system tray icon with a Quit menu item. Runs in a background thread.
    """
    try:
        icon = pystray.Icon("mac_converter", create_image(), "MAC Converter", menu=pystray.Menu(
            pystray.MenuItem("About", lambda icon, item: show_about_dialog()),
            pystray.MenuItem("Quit", on_quit)
        ))
        icon.run()
    except Exception:
        pass

def listen_hotkey(app):
    """
    Starts a global hotkey listener for Alt+Shift+M using the keyboard package.
    This approach is robust and suppresses the 'M' character in the terminal.
    Args:
        app (QApplication): The running Qt application instance.
    Returns:
        The keyboard module for later cleanup.
    """
    def on_hotkey():
        handle_hotkey(app)
    kb.add_hotkey('alt+shift+m', on_hotkey, suppress=True)
    print("[INFO] Hotkey Alt+Shift+M registered (requires admin on Windows). Press Alt+Shift+M to activate.")
    return kb

# --- Settings: Load/Save Logic ---
SETTINGS_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'mac-converter-2')
SETTINGS_PATH = os.path.join(SETTINGS_DIR, 'settings.json')
DEFAULT_SETTINGS = {
    'autostart': False,
    'default_format': 0,  # index in formats list
    'timer': 8,  # seconds
    'author': 'A. Lederman',
    'license': 'MIT',
    'about': 'MAC Address Converter Utility v2.0\nAuthor: A. Lederman\nLicense: MIT\nhttps://github.com/aleled/mac-converter-2'
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
    import time
    global listener
    app = QApplication(sys.argv)
    t = threading.Thread(target=tray_app, daemon=True)
    t.start()
    listener = listen_hotkey(app)
    # Use a QTimer to poll for dialog requests
    timer = QTimer()
    timer.timeout.connect(show_format_selector_from_queue)
    timer.start(100)
    app.exec_()
    if listener:
        listener.unhook_all_hotkeys()
    # Do not call sys.exit(0) here; only exit on tray quit

if __name__ == "__main__":
    main()

# Remove legacy/unused QTableWidget-based code below
# (All code below this comment is now obsolete and removed)
