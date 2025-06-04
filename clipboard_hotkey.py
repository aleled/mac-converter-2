"""
clipboard_hotkey.py

Listens for a global hotkey, checks clipboard for a valid MAC address, and if found, prompts user to select a format and copies the result to clipboard.
Uses pynput for cross-platform hotkey support (no root required on Linux).
"""

import pyperclip
from pynput import keyboard as pynput_keyboard
import pystray
from PIL import Image, ImageDraw
import threading
import sys
from mac_formats import detect_mac, convert_mac
import platform
import os
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QDesktopWidget, QAbstractItemView, QWidget
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QIcon, QBrush
from PyQt5.QtCore import QTimer
import queue
import ctypes
import time

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
dialog_request_queue = queue.Queue()

# --- PyQt Format Selector Dialog ---
class FormatSelector(QDialog):
    """
    PyQt5 dialog for selecting a MAC address format. Modern dark theme, orange/gray palette, green highlight, background texture, and improved layout per UI/UX requirements.
    """
    def __init__(self, formats, timeout=6, clipboard_mac=None):
        super().__init__()
        self.formats = formats
        self.selected = None
        self.timeout = timeout
        self.current_row = 0
        self.current_col = 0  # Always default to Upper Case, first entry
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timeout)
        self.timer.setSingleShot(True)
        self.selection_made = False
        self.clipboard_mac = clipboard_mac
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("MAC Address Converter")
        self.setWindowIcon(QIcon(get_icon_path()))
        self.setFixedSize(700, 400)
        try:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        except Exception:
            pass
        title = QLabel("Select which MAC address copy to clipboard")
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
        self.table = self.FormatTable(self)
        self.table.setHorizontalHeaderLabels(["Format Style", "Upper Case", "Lower Case"])
        for row in range(4):
            style_name = self.formats[row*2][0].split()[0]
            style_item = QTableWidgetItem(style_name)
            align_right = getattr(Qt, 'AlignRight', 0x0002)
            align_vcenter = getattr(Qt, 'AlignVCenter', 0x0080)
            style_item.setTextAlignment(align_right | align_vcenter)
            style_item.setForeground(QColor("#ff9800"))
            self.table.setItem(row, 0, style_item)
            upper_item = QTableWidgetItem(self.formats[row*2][1])
            upper_item.setFont(QFont("Consolas", 14))
            self.table.setItem(row, 1, upper_item)
            lower_item = QTableWidgetItem(self.formats[row*2+1][1])
            lower_item.setFont(QFont("Consolas", 14))
            self.table.setItem(row, 2, lower_item)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 250)
        self.table.setColumnWidth(2, 250)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.clearSelection()
        self.table.setStyleSheet("""
            QTableWidget {
                background: #23272e;
                color: #fff;
                border: none;
                font-family: Consolas, monospace;
                font-size: 14px;
            }
            QTableWidget::item {
                background: #23272e;
                color: #fff;
                border: none;
            }
        """)
        # Add widgets to layout (no explicit alignment for maximum compatibility)
        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(mac_label)
        layout.addWidget(self.table)
        layout.addWidget(instr_box)
        self.setLayout(layout)
        # Always default to first row, UPPER CASE cell (row 0, col 1)
        self.current_row = 0
        self.current_col = 1  # 1 = UPPER CASE, 2 = LOWER CASE
        self.update_selection()
        self.timer.start(self.timeout * 1000)
        self.table.setFocus()
        self.table.repaint()

    def update_selection(self):
        print(f"[DEBUG] update_selection: current_row={self.current_row}, current_col={self.current_col}")
        # Remove highlight from all UPPER/LOWER cells
        for row in range(4):
            for col in range(1, 3):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QBrush(QColor("#23272e")))
                    item.setForeground(QBrush(QColor("#fff")))
                    font = item.font()
                    font.setBold(False)
                    item.setFont(font)
        # Only highlight the selector at (current_row, current_col) in green with orange text
        if 0 <= self.current_row < 4 and self.current_col in (1, 2):
            item = self.table.item(self.current_row, self.current_col)
            if item:
                print(f"[DEBUG] Highlighting cell: row={self.current_row}, col={self.current_col}")
                item.setBackground(QBrush(QColor("#39d353")))
                item.setForeground(QBrush(QColor("#ff9800")))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
        # Debug: print all cell backgrounds and foregrounds
        for row in range(4):
            for col in range(1, 3):
                item = self.table.item(row, col)
                if item:
                    bg = item.background().color().name()
                    fg = item.foreground().color().name()
                    print(f"[DEBUG] cell ({row},{col}) bg={bg} fg={fg}")
        self.table.repaint()
        self.table.setCurrentCell(-1, -1)
        self.table.clearSelection()
        # Set a stylesheet for the table to add a border to the selected cell
        self.table.setStyleSheet('''
            QTableWidget {
                background: #23272e;
                color: #fff;
                border: none;
                font-family: Consolas, monospace;
                font-size: 14px;
            }
            QTableWidget::item {
                background: #23272e;
                color: #fff;
                border: none;
            }
            QTableWidget::item[selected="true"] {
                border: 3px solid #ff9800;
                background: #39d353;
                color: #23272e;
            }
        ''')
    class FormatTable(QTableWidget):
        def __init__(self, parent):
            super().__init__(4, 3, parent)
            self.parent_dialog = parent
        def mousePressEvent(self, e):
            if e is not None:
                pos = e.pos()
                row = self.rowAt(pos.y())
                col = self.columnAt(pos.x())
                print(f"[DEBUG] mousePressEvent: pos=({pos.x()},{pos.y()}), row={row}, col={col}")
                if row >= 0 and col in (1, 2):
                    print(f"[DEBUG] Mouse selecting: row={row}, col={col}")
                    self.parent_dialog.current_row = row
                    self.parent_dialog.current_col = col
                    self.parent_dialog.update_selection()
                    self.parent_dialog.selected = (self.parent_dialog.current_row, self.parent_dialog.current_col)
                    self.parent_dialog.selection_made = True
                    idx = row*2 + (col-1)
                    print(f"[DEBUG] Copying to clipboard: idx={idx}, value={self.parent_dialog.formats[idx][1]}")
                    pyperclip.copy(self.parent_dialog.formats[idx][1])
                    self.parent_dialog.hide()
                else:
                    print(f"[DEBUG] Mouse click ignored: row={row}, col={col}")

    def keyPressEvent(self, a0):
        if self.timer and self.timer.isActive():
            self.timer.stop()
        key = a0.key() if a0 else None
        print(f"[DEBUG] keyPressEvent: key={key}, current_row={self.current_row}, current_col={self.current_col}")
        if key == getattr(Qt, 'Key_Up', 0x01000013):
            self.current_row = (self.current_row - 1) % 4
            print(f"[DEBUG] Arrow Up: new current_row={self.current_row}")
            self.update_selection()
        elif key == getattr(Qt, 'Key_Down', 0x01000015):
            self.current_row = (self.current_row + 1) % 4
            print(f"[DEBUG] Arrow Down: new current_row={self.current_row}")
            self.update_selection()
        elif key == getattr(Qt, 'Key_Left', 0x01000012):
            if self.current_col == 2:
                self.current_col = 1
                print(f"[DEBUG] Arrow Left: new current_col={self.current_col}")
                self.update_selection()
        elif key == getattr(Qt, 'Key_Right', 0x01000014):
            if self.current_col == 1:
                self.current_col = 2
                print(f"[DEBUG] Arrow Right: new current_col={self.current_col}")
                self.update_selection()
        elif key == getattr(Qt, 'Key_Return', 0x01000004) or key == getattr(Qt, 'Key_Enter', 0x01000005):
            if self.current_col in (1, 2):
                self.selected = (self.current_row, self.current_col)
                self.selection_made = True
                idx = self.current_row*2 + (self.current_col-1)
                print(f"[DEBUG] Enter pressed: selected=({self.current_row},{self.current_col}), idx={idx}, value={self.formats[idx][1]}")
                pyperclip.copy(self.formats[idx][1])
                self.hide()
        elif key == getattr(Qt, 'Key_Escape', 0x01000000):
            print(f"[DEBUG] Escape pressed: dialog cancelled")
            self.selected = None
            self.selection_made = False
            self.hide()
        else:
            print(f"[DEBUG] Unhandled key: {key}")
            super().keyPressEvent(a0)

    def hideEvent(self, a0):
        """
        Handles the dialog hide event. Resets the global dialog_open flag.
        Args:
            a0 (QHideEvent): The hide event.
        """
        global dialog_open
        print("[DEBUG] Dialog hidden, resetting dialog_open to False")
        dialog_open = False
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
        self.table.setFocus()
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

def show_format_selector_from_queue():
    """
    Checks the dialog request queue and shows the FormatSelector dialog if not already open.
    Ensures only one dialog is open at a time. Brings dialog to front and focuses it.
    """
    global dialog_open, last_dialog_open_warning
    if dialog_open:
        now = time.time()
        if now - last_dialog_open_warning > 2:
            print("[DEBUG] Dialog already open, skipping new dialog.")
            last_dialog_open_warning = now
        return
    try:
        formats = dialog_request_queue.get_nowait()
    except queue.Empty:
        return
    dialog_open = True
    print("[DEBUG] Creating and showing new FormatSelector dialog.")

    # --- Windows focus workaround: dummy window ---
    dummy = QWidget()
    dummy.setGeometry(0, 0, 1, 1)
    dummy.show()
    dummy.activateWindow()
    dummy.raise_()
    dummy.hide()
    dummy.deleteLater()

    dlg = FormatSelector(formats)
    dlg.show()
    try:
        hwnd = int(dlg.winId())
        SW_SHOWNORMAL = 1
        ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNORMAL)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"[DEBUG] Foreground force failed: {e}")
    dlg.raise_()
    dlg.activateWindow()
    dlg.setFocus()

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
    dialog_request_queue.put(formats)

def tray_app():
    """
    Starts the system tray icon with a Quit menu item. Runs in a background thread.
    """
    try:
        icon = pystray.Icon("mac_converter", create_image(), "MAC Converter", menu=pystray.Menu(
            pystray.MenuItem("Quit", on_quit)
        ))
        icon.run()
    except Exception as e:
        print(f"[WARNING] Tray icon could not be started: {e}\nHotkey functionality will still work.")

def listen_hotkey(app):
    """
    Starts a global hotkey listener for Alt+Shift+M. When triggered, calls handle_hotkey().
    Args:
        app (QApplication): The running Qt application instance.
    Returns:
        pynput.keyboard.Listener: The hotkey listener object.
    """
    global listener
    ALT_KEYS = {pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r}
    SHIFT_KEYS = {pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r}
    M_KEY = pynput_keyboard.KeyCode.from_char('m')
    current = set()
    print("[DEBUG] Hotkey listener started. Waiting for Alt+Shift+M...")
    def on_press(key):
        if isinstance(key, pynput_keyboard.KeyCode):
            norm_key = pynput_keyboard.KeyCode.from_char(key.char.lower()) if key.char else key
        else:
            norm_key = key
        current.add(norm_key)
        if (any(k in current for k in ALT_KEYS)
            and any(k in current for k in SHIFT_KEYS)
            and M_KEY in current):
            print("[DEBUG] Hotkey detected!")
            handle_hotkey(app)
    def on_release(key):
        if isinstance(key, pynput_keyboard.KeyCode):
            norm_key = pynput_keyboard.KeyCode.from_char(key.char.lower()) if key.char else key
        else:
            norm_key = key
        if norm_key in current:
            current.remove(norm_key)
    listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener

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
    print("MAC Converter running. Press Alt+Shift+M to convert clipboard MAC. Press Ctrl+C to quit.")
    # Use a QTimer to poll for dialog requests
    timer = QTimer()
    timer.timeout.connect(show_format_selector_from_queue)
    timer.start(100)
    app.exec_()
    if listener:
        listener.stop()
    # Do not call sys.exit(0) here; only exit on tray quit

if __name__ == "__main__":
    main()

# Move unused/old files to 'old/' folder for archival
# (No code change, just a note for future maintainers)
