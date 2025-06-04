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
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QDesktopWidget, QAbstractItemView
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtWidgets import QAbstractItemView, QTableWidgetItem, QWidget
import queue
import ctypes

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
    PyQt5 dialog for selecting a MAC address format. Displays a 4x2 table of formats (upper/lower case),
    supports keyboard and mouse navigation, and copies the selected format to clipboard.
    Closes on selection, timeout, or ESC.
    Args:
        formats (list): List of (format_name, formatted_mac) tuples.
        timeout (int): Timeout in seconds before auto-select/cancel.
    """
    selection_made = False  # Track if a selection was made
    class FormatTable(QTableWidget):
        """
        Custom QTableWidget for the format selector dialog. Handles mouse click selection.
        Args:
            parent (FormatSelector): The parent dialog instance.
        """
        def __init__(self, parent):
            super().__init__(4, 3, parent)
            self.parent_dialog = parent
        def mousePressEvent(self, e):
            """
            Handles mouse click events on the table. Selects and copies the clicked format if valid.
            Args:
                e (QMouseEvent): The mouse event.
            """
            if e is not None:
                pos = e.pos()
                row = self.rowAt(pos.y())
                col = self.columnAt(pos.x())
                if row >= 0 and col in (1, 2):
                    self.parent_dialog.current_row = row
                    self.parent_dialog.current_col = col - 1
                    self.parent_dialog.update_selection()
                    self.parent_dialog.selected = (self.parent_dialog.current_row, self.parent_dialog.current_col)
                    self.parent_dialog.selection_made = True
                    # Copy to clipboard and hide dialog
                    idx = row*2 + (col-1)
                    pyperclip.copy(self.parent_dialog.formats[idx][1])
                    self.parent_dialog.hide()
                else:
                    super().mousePressEvent(e)
    def __init__(self, formats, timeout=6):
        """
        Initializes the FormatSelector dialog.
        Args:
            formats (list): List of (format_name, formatted_mac) tuples.
            timeout (int): Timeout in seconds before auto-select/cancel.
        """
        super().__init__()
        self.formats = formats
        self.selected = None
        self.timeout = timeout
        self.current_row = 0
        self.current_col = 0  # 0 = Upper Case, 1 = Lower Case
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timeout)
        self.timer.setSingleShot(True)
        self.setup_ui()
        self.selection_made = False

    def showEvent(self, a0):
        """
        Handles the dialog show event. Brings the dialog to the foreground and focuses it.
        Args:
            a0 (QShowEvent): The show event.
        """
        super().showEvent(a0)
        self.activateWindow()
        self.raise_()
        self.setFocus()
        self.table.setFocus()
        # Force window to foreground on Windows
        try:
            hwnd = int(self.winId())
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception as e:
            pass

    def setup_ui(self):
        """
        Sets up the dialog UI: instructions label and format table.
        """
        self.setWindowTitle("Select MAC Address Format")
        self.setFixedSize(700, 400)
        # Always on top for Windows focus (if available)
        stays_on_top = getattr(Qt, 'WindowStaysOnTopHint', None)
        if stays_on_top is not None:
            self.setWindowFlags(self.windowFlags() | stays_on_top)
        # Center the window
        screen = QDesktopWidget().screenGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        layout = QVBoxLayout()
        # Instructions
        instructions = QLabel(
            f"Use arrow keys to move (UP/DOWN/LEFT/RIGHT)\n"
            f"ENTER to select • ESC to cancel\n"
            f"Auto-selects default after {self.timeout} seconds"
        )
        align_center = getattr(Qt, 'AlignCenter', None)
        if align_center is not None:
            try:
                instructions.setAlignment(align_center)
            except Exception:
                pass
        instructions.setFont(QFont("Arial", 11))
        instructions.setStyleSheet("padding: 10px; background: #f0f0f0; border: 1px solid #ccc;")
        layout.addWidget(instructions)
        # Table widget
        self.table = self.FormatTable(self)
        self.table.setHorizontalHeaderLabels(["Format Style", "Upper Case", "Lower Case"])
        for row in range(4):
            style_name = self.formats[row*2][0].split()[0]
            style_item = QTableWidgetItem(style_name)
            item_is_selectable = getattr(Qt, 'ItemIsSelectable', None)
            if item_is_selectable is not None:
                try:
                    style_item.setFlags(style_item.flags() & ~item_is_selectable)
                except Exception:
                    pass
            self.table.setItem(row, 0, style_item)
            upper_item = QTableWidgetItem(self.formats[row*2][1])
            self.table.setItem(row, 1, upper_item)
            lower_item = QTableWidgetItem(self.formats[row*2+1][1])
            self.table.setItem(row, 2, lower_item)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 250)
        self.table.setColumnWidth(2, 250)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.clearSelection()
        # Remove native focus border
        self.table.setStyleSheet("QTableWidget::item:focus { outline: none; border: none; }")
        self.table.setFocusPolicy(self.table.focusPolicy().__class__.NoFocus)
        layout.addWidget(self.table)
        self.setLayout(layout)
        self.update_selection()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_timeout)
        self.timer.setSingleShot(True)
        self.timer.start(self.timeout * 1000)

    def update_selection(self):
        """
        Updates the table cell highlight to reflect the current selection.
        """
        self.table.clearSelection()
        for row in range(4):
            for col in range(1, 3):
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("white"))
        if 0 <= self.current_row < 4:
            col = self.current_col + 1
            item = self.table.item(self.current_row, col)
            if item:
                item.setBackground(QColor("cyan"))

    def keyPressEvent(self, a0):
        """
        Handles keyboard navigation and selection in the dialog.
        Args:
            a0 (QKeyEvent): The key event.
        """
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
            self.current_col = 0
            self.update_selection()
        elif key == getattr(Qt, 'Key_Right', 0x01000014):
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

# --- Hotkey Handler ---
dialog_open = False

def show_format_selector_from_queue():
    """
    Checks the dialog request queue and shows the FormatSelector dialog if not already open.
    Ensures only one dialog is open at a time. Brings dialog to front and focuses it.
    """
    global dialog_open
    if dialog_open:
        print("[DEBUG] Dialog already open, skipping new dialog.")
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
