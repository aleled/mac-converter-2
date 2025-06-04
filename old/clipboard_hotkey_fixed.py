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
from PyQt5.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

# --- Tray Icon Setup ---
def get_icon_path():
    # Get absolute path to icon-v1.png in the same directory as this script
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon-v1.png")

def create_image():
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
    icon.stop()
    sys.exit(0)

# --- PyQt Format Selector Dialog ---
class FormatSelector(QDialog):
    def __init__(self, formats, timeout=6):
        super().__init__()
        self.formats = formats
        self.selected = None
        self.timeout = timeout
        self.current_row = 0
        self.current_col = 0  # 0 = Upper Case, 1 = Lower Case
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timeout)
        self.setup_ui()
        
    def setup_ui(self):
        self.setWindowTitle("Select MAC Address Format")
        self.setFixedSize(700, 400)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)
        
        # Center the window
        screen_geometry = QApplication.desktop().screenGeometry()
        self.move(
            (screen_geometry.width() - self.width()) // 2,
            (screen_geometry.height() - self.height()) // 2
        )
        
        layout = QVBoxLayout()
        
        # Instructions
        instructions = QLabel(
            f"Use arrow keys to move (UP/DOWN/LEFT/RIGHT)\n"
            f"ENTER to select • ESC to cancel\n"
            f"Auto-selects default after {self.timeout} seconds"
        )
        instructions.setAlignment(Qt.AlignCenter)
        instructions.setFont(QFont("Arial", 11))
        instructions.setStyleSheet("padding: 10px; background: #f0f0f0; border: 1px solid #ccc;")
        layout.addWidget(instructions)
        
        # Table widget
        self.table = QTableWidget(4, 3)  # 4 rows, 3 columns
        self.table.setHorizontalHeaderLabels(["Format Style", "Upper Case", "Lower Case"])
        
        # Populate table
        for row in range(4):
            # Format style (read-only)
            style_name = self.formats[row*2][0].split()[0]  # e.g. 'Colon-separated'
            style_item = QTableWidgetItem(style_name)
            style_item.setFlags(Qt.ItemIsEnabled)  # Not selectable
            self.table.setItem(row, 0, style_item)
            
            # Upper case format
            upper_item = QTableWidgetItem(self.formats[row*2][1])
            upper_item.setFlags(Qt.ItemIsEnabled)  # Not selectable by mouse
            self.table.setItem(row, 1, upper_item)
            
            # Lower case format
            lower_item = QTableWidgetItem(self.formats[row*2+1][1])
            lower_item.setFlags(Qt.ItemIsEnabled)  # Not selectable by mouse
            self.table.setItem(row, 2, lower_item)
        
        # Set column widths
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 250)
        self.table.setColumnWidth(2, 250)
        
        # Disable selection and scrolling
        self.table.setSelectionMode(QTableWidget.NoSelection)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(self.table)
        self.setLayout(layout)
        
        # Update initial selection
        self.update_selection()
        
        # Start timeout timer
        self.timer.start(self.timeout * 1000)
        
    def update_selection(self):
        # Clear all highlights
        for row in range(4):
            for col in range(1, 3):  # Only columns 1 and 2 are selectable
                item = self.table.item(row, col)
                if item:
                    item.setBackground(QColor("white"))
        
        # Highlight current selection (only in columns 1 or 2)
        if 0 <= self.current_row < 4:
            col = self.current_col + 1  # Convert to table column (1 or 2)
            item = self.table.item(self.current_row, col)
            if item:
                item.setBackground(QColor("cyan"))
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            self.current_row = (self.current_row - 1) % 4
            self.update_selection()
        elif event.key() == Qt.Key_Down:
            self.current_row = (self.current_row + 1) % 4
            self.update_selection()
        elif event.key() == Qt.Key_Left:
            self.current_col = 0  # Upper Case
            self.update_selection()
        elif event.key() == Qt.Key_Right:
            self.current_col = 1  # Lower Case
            self.update_selection()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.selected = (self.current_row, self.current_col)
            self.timer.stop()
            self.accept()
        elif event.key() == Qt.Key_Escape:
            self.selected = None
            self.timer.stop()
            self.reject()
        else:
            super().keyPressEvent(event)
    
    def on_timeout(self):
        # Default: first row, upper case
        self.selected = (0, 0)
        self.timer.stop()
        self.accept()

# --- Hotkey Handler ---
def handle_hotkey():
    text = pyperclip.paste()
    mac = detect_mac(text)
    if not mac:
        pyperclip.copy("no mac-address found :-)")
        return
    formats = convert_mac(mac)
    app = QApplication.instance() or QApplication(sys.argv)
    dlg = FormatSelector(formats)
    if dlg.exec_() == QDialog.Accepted and dlg.selected:
        row, col = dlg.selected
        idx = row*2 + col
        pyperclip.copy(formats[idx][1])
        print(f"Copied: {formats[idx][1]}")
    else:
        print("No selection made.")

# --- Main Tray App ---
def tray_app():
    try:
        icon = pystray.Icon("mac_converter", create_image(), "MAC Converter", menu=pystray.Menu(
            pystray.MenuItem("Quit", on_quit)
        ))
        icon.run()
    except Exception as e:
        print(f"[WARNING] Tray icon could not be started: {e}\nHotkey functionality will still work.")

def listen_hotkey():
    # Alt+Shift+M (accept both left and right Alt)
    ALT_KEYS = {pynput_keyboard.Key.alt, pynput_keyboard.Key.alt_l, pynput_keyboard.Key.alt_r}
    SHIFT_KEYS = {pynput_keyboard.Key.shift, pynput_keyboard.Key.shift_l, pynput_keyboard.Key.shift_r}
    M_KEY = pynput_keyboard.KeyCode.from_char('m')
    current = set()
    print("[DEBUG] Hotkey listener started. Waiting for Alt+Shift+M...")
    def on_press(key):
        # Normalize character keys to KeyCode
        if isinstance(key, pynput_keyboard.KeyCode):
            norm_key = pynput_keyboard.KeyCode.from_char(key.char.lower()) if key.char else key
        else:
            norm_key = key
        print(f"[DEBUG] Key pressed: {norm_key}")
        current.add(norm_key)
        print(f"[DEBUG] Current pressed keys: {current}")
        if (any(k in current for k in ALT_KEYS)
            and any(k in current for k in SHIFT_KEYS)
            and M_KEY in current):
            print("[DEBUG] Hotkey detected!")
            handle_hotkey()
    def on_release(key):
        # Normalize character keys to KeyCode
        if isinstance(key, pynput_keyboard.KeyCode):
            norm_key = pynput_keyboard.KeyCode.from_char(key.char.lower()) if key.char else key
        else:
            norm_key = key
        if norm_key in current:
            current.remove(norm_key)
    listener = pynput_keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    return listener

def main():
    import time
    # Start tray icon in a separate thread (now also on Windows)
    t = threading.Thread(target=tray_app, daemon=True)
    t.start()
    print("MAC Converter running. Press Alt+Shift+M to convert clipboard MAC. Press Ctrl+C to quit.")
    listener = listen_hotkey()
    try:
        while True:
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\n[INFO] Exiting MAC Converter.")
        listener.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
