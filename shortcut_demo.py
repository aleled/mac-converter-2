"""
shortcut_demo.py

Small looping animations that show what each global hotkey actually does.

Telling someone "select a MAC and press alt+shift+m" does not land; showing the
selection appear, the keys go down and the text change in place does. Each demo
is a programmatic animation, not a video or a GIF: one QTimer per canvas drives
a five-phase state machine and everything is drawn with QPainter. No new
dependencies and no image assets — the installer is already 54 MB.

Public API (clipboard_hotkey.py wires to exactly this):

    ShortcutDemoDialog(mac_hotkey, layout_hotkey, tutorial=False, parent=None)
    show_demos(mac_hotkey, layout_hotkey, parent=None)
    show_tutorial(mac_hotkey, layout_hotkey, parent=None)

Importing this module has no side effects: no QApplication, no widgets, no fonts
at import time, so the tray app can import it at startup for free.

DPI: the Qt5 Windows plugin is system-DPI aware, so point-size fonts grow at
150% scaling but raw pixel values do not. Every dimension below is derived from
font metrics (the height of one caption line is the unit), never hard-coded.
"""

import os

from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QWidget, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer, QRectF, QSize
from PyQt5.QtGui import QFont, QColor, QIcon, QPainter, QPen, QFontMetricsF

# --- Palette: the same values the other dialogs in clipboard_hotkey.py use.
# Hex strings, not QColor objects, so nothing is constructed at import time.
C_DIALOG_BG = "#2b2b2b"
C_EDITOR_BG = "#1e1e1e"
C_EDITOR_BORDER = "#555555"
C_CHROME_DOT = "#4a4a4a"
C_TEXT = "#e6e6e6"
C_TEXT_FRESH = "#4cc2ff"       # the just-replaced text, before it settles
C_ACCENT = "#0078d4"           # app accent: selection, caret, pressed key
C_ACCENT_LIGHT = "#4ba3e3"
C_BADGE_BG = "#3c3c3c"
C_BADGE_BORDER = "#6a6a6a"
C_BADGE_TEXT = "#e0e0e0"
C_CAPTION = "#b0b0b0"

# --- Animation state machine -------------------------------------------------
# One pass through this table is one demo step. Leaving the last phase advances
# the text index, so the text produced by one step is the text the next step
# starts from: that is what makes it loop, and for the layout fixer it is also
# what demonstrates pressing the hotkey again to get the original back.
PHASES = (
    ("idle", 900),      # nothing selected yet
    ("select", 650),    # highlight grows across the text
    ("hold", 320),      # fully selected, hand moving to the keys
    ("press", 420),     # key badge down
    ("result", 1500),   # text replaced, read it
)
TICK_MS = 33            # ~30 fps; only ticks while the dialog is open
PRESS_HOLD_MS = 170     # badge stays down this far into "result"
SELECT_FADE_MS = 320    # selection fades out this fast once text is replaced

_MOD_LABELS = {"ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift",
               "win": "Win", "cmd": "Win", "super": "Win"}
_KEY_LABELS = {"space": "Space", "tab": "Tab", "enter": "Enter", "return": "Enter",
               "esc": "Esc", "escape": "Esc", "backspace": "Backspace",
               "delete": "Delete", "del": "Delete", "insert": "Insert",
               "ins": "Insert", "home": "Home", "end": "End", "pageup": "PgUp",
               "pgup": "PgUp", "pagedown": "PgDn", "pgdn": "PgDn",
               "left": "Left", "up": "Up", "right": "Right", "down": "Down"}


def format_hotkey(hotkey):
    """'alt+shift+m' -> 'Alt + Shift + M'.

    Token order is the user's own, straight from the settings string, so the
    badge reads the way they typed it. Anything this doesn't recognise is
    title-cased and passed through rather than dropped.
    """
    if not hotkey or not str(hotkey).strip():
        return "(not set)"
    parts = []
    for raw in str(hotkey).split("+"):
        token = raw.strip().lower()
        if not token:
            continue
        if token in _MOD_LABELS:
            parts.append(_MOD_LABELS[token])
        elif token in _KEY_LABELS:
            parts.append(_KEY_LABELS[token])
        elif len(token) == 1:
            parts.append(token.upper())
        elif token.startswith("f") and token[1:].isdigit():
            parts.append(token.upper())
        else:
            parts.append(token.title())
    return " + ".join(parts) if parts else "(not set)"


def _is_rtl(text):
    """True for Hebrew/Arabic text, so the demo selects it in the right direction."""
    return any("֐" <= ch <= "ࣿ" for ch in text)


def _smooth(t):
    """Smoothstep easing, so the selection doesn't start and stop abruptly."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def _pick(value, index):
    """Captions may be one string for every step, or one per step."""
    if isinstance(value, (list, tuple)):
        return value[index % len(value)] if value else ""
    return value


class _DemoCanvas(QWidget):
    """One looping animation: a mock text field, a key badge and a caption.

    `texts` is the cycle of strings the hotkey produces, in order; the animation
    walks it forever. `captions` maps a phase ('idle', 'select', 'press',
    'result') to a caption, each either a single string or one string per step.
    """

    def __init__(self, texts, hotkey_label, captions, font_family="Segoe UI", parent=None):
        super().__init__(parent)
        self._texts = list(texts)
        self._hotkey_label = hotkey_label
        self._captions = captions

        # Phase clock. _index is the step we are in: phases up to "press" show
        # texts[_index], "result" shows the next one.
        self._index = 0
        self._phase = 0
        self._elapsed = 0
        self._ticks = 0

        # Sizes are relative to the app font, which is what carries DPI scaling.
        base_pt = 9.0
        app = QApplication.instance()
        if app is not None and app.font().pointSizeF() > 0:
            base_pt = app.font().pointSizeF()

        # Editor font is per-demo: Consolas reads like a config file for hex MAC
        # addresses; the layout demo uses Segoe UI because it has the Hebrew
        # coverage that fixed-width faces can't be relied on for.
        self._text_font = QFont(font_family)
        self._text_font.setPointSizeF(base_pt * 1.35)
        self._badge_font = QFont("Segoe UI")
        self._badge_font.setPointSizeF(base_pt * 0.95)
        self._badge_font.setBold(True)
        self._caption_font = QFont("Segoe UI")
        self._caption_font.setPointSizeF(base_pt * 0.9)

        self._fm_text = QFontMetricsF(self._text_font)
        self._fm_badge = QFontMetricsF(self._badge_font)
        self._fm_caption = QFontMetricsF(self._caption_font)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)

        self._timer = QTimer(self)
        self._timer.setInterval(TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # --- timer lifetime ---------------------------------------------------
    def stop(self):
        """Stop the animation timer. Idempotent — safe to call more than once."""
        if self._timer is not None and self._timer.isActive():
            self._timer.stop()

    def is_running(self):
        return self._timer is not None and self._timer.isActive()

    def _tick(self):
        self._ticks += 1
        self._elapsed += TICK_MS
        if self._elapsed >= PHASES[self._phase][1]:
            self._elapsed = 0
            self._phase = (self._phase + 1) % len(PHASES)
            if PHASES[self._phase][0] == "idle":
                # A full step just finished: the text that was produced becomes
                # the text we start from, and the loop continues from there.
                self._index = (self._index + 1) % len(self._texts)
        self.update()

    # --- state read by paintEvent ----------------------------------------
    @property
    def _phase_name(self):
        return PHASES[self._phase][0]

    def _current_text(self):
        """The string on screen right now."""
        if self._phase_name == "result":
            return self._texts[(self._index + 1) % len(self._texts)]
        return self._texts[self._index]

    def _selection_progress(self):
        """0.0 (nothing selected) .. 1.0 (whole string selected)."""
        name = self._phase_name
        if name == "idle":
            return 0.0
        if name == "select":
            return _smooth(self._elapsed / float(PHASES[self._phase][1]))
        if name == "result":
            # Replacement leaves the caret after the new text, so the highlight
            # fades out rather than hanging around.
            return max(0.0, 1.0 - self._elapsed / float(SELECT_FADE_MS))
        return 1.0

    def _key_down(self):
        name = self._phase_name
        return name == "press" or (name == "result" and self._elapsed < PRESS_HOLD_MS)

    def _freshness(self):
        """1.0 right after the text changed, decaying to 0 — drives the flash."""
        if self._phase_name != "result":
            return 0.0
        return max(0.0, 1.0 - self._elapsed / 500.0)

    def _caption(self):
        name = self._phase_name
        if name == "result":
            # Indexed by the text being produced, not the one we came from.
            return _pick(self._captions.get("result", ""), self._index + 1)
        if name in ("hold", "press"):
            return _pick(self._captions.get("press", ""), self._index)
        return _pick(self._captions.get(name, ""), self._index)

    # --- geometry (all derived from font metrics, never hard-coded px) ----
    def _unit(self):
        return self._fm_caption.height()

    def _editor_height(self):
        u = self._unit()
        return u * 0.95 + self._fm_text.height() * 1.5 + u * 0.55

    def _row_height(self):
        return self._fm_badge.height() + self._unit() * 0.75

    def sizeHint(self):
        u = self._unit()
        widest = max((self._fm_text.horizontalAdvance(t) for t in self._texts), default=0.0)
        editor_w = widest + u * 2.4
        badge_w = self._fm_badge.horizontalAdvance(self._hotkey_label) + u * 1.8
        caption_w = max((self._fm_caption.horizontalAdvance(_pick(v, i))
                         for v in self._captions.values()
                         for i in range(len(self._texts))), default=0.0)
        row_w = badge_w + u * 0.8 + caption_w
        height = self._editor_height() + u * 0.7 + self._row_height() + 2
        return QSize(int(max(editor_w, row_w, 360.0)) + 2, int(height) + 1)

    def minimumSizeHint(self):
        # Narrower than the hint is allowed: captions elide and the editor text
        # clips rather than forcing the dialog wide at 150% scaling.
        hint = self.sizeHint()
        return QSize(min(hint.width(), 320), hint.height())

    # --- painting ---------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        u = self._unit()
        radius = u * 0.35
        editor = QRectF(0.5, 0.5, self.width() - 1.0, self._editor_height())
        self._paint_editor(p, editor, radius, u)

        row = QRectF(0.0, editor.bottom() + u * 0.7, self.width(), self._row_height())
        self._paint_badge_and_caption(p, row, radius, u)

    def _paint_editor(self, p, editor, radius, u):
        """Mock text field: frame, a hint of window chrome, selection, text, caret."""
        p.setPen(QPen(QColor(C_EDITOR_BORDER), 1.0))
        p.setBrush(QColor(C_EDITOR_BG))
        p.drawRoundedRect(editor, radius, radius)

        # Three small dots, so the frame reads as "some window with text in it"
        # without needing an icon or a title string.
        dot_r = u * 0.13
        dot_y = editor.top() + u * 0.48
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_CHROME_DOT))
        for i in range(3):
            cx = editor.left() + u * 0.6 + i * dot_r * 3.2
            p.drawEllipse(QRectF(cx - dot_r, dot_y - dot_r, dot_r * 2, dot_r * 2))

        text = self._current_text()
        rtl = _is_rtl(text)
        inner = QRectF(editor.left() + u * 1.2, editor.top() + u * 0.95,
                       editor.width() - u * 2.4, self._fm_text.height() * 1.5)
        advance = min(self._fm_text.horizontalAdvance(text), inner.width())
        # RTL text starts at the right edge, and so does its selection: dragging
        # over Hebrew runs right-to-left, and showing it the other way round
        # would be plain wrong.
        lead_x = inner.right() - advance if rtl else inner.left()

        progress = self._selection_progress()
        if progress > 0.0:
            grown = advance * progress
            sel_x = inner.right() - grown if rtl else lead_x
            sel = QRectF(sel_x, inner.top() + u * 0.08, grown, inner.height() - u * 0.16)
            # Fully opaque once selected; only the fade-out after replacement
            # drops the alpha, so the growing highlight stays solid.
            alpha = int(150 * progress) if self._phase_name == "result" else 150
            fill = QColor(C_ACCENT)
            fill.setAlpha(max(0, min(255, alpha)))
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(sel, u * 0.1, u * 0.1)

        # Text over the highlight. Rect-based drawText lets Qt do the bidi
        # reordering, which keeps the Hebrew readable instead of reversed.
        # Fresh text flashes accent-blue and settles back to normal.
        fresh = self._freshness()
        base, hot = QColor(C_TEXT), QColor(C_TEXT_FRESH)
        colour = QColor(*[int(b + (h - b) * fresh) for b, h in
                          ((base.red(), hot.red()), (base.green(), hot.green()),
                           (base.blue(), hot.blue()))])
        p.setPen(QPen(colour))
        p.setFont(self._text_font)
        flags = Qt.AlignVCenter | (Qt.AlignRight if rtl else Qt.AlignLeft)
        p.drawText(inner, int(flags) | int(Qt.TextSingleLine), text)

        # Caret: blinking at the trailing edge while idle, riding the selection
        # edge while the text is being selected.
        caret_visible = self._phase_name == "select" or (
            self._phase_name == "idle" and (self._ticks // 14) % 2 == 0)
        if caret_visible:
            if self._phase_name == "select":
                grown = advance * progress
                caret_x = (inner.right() - grown) if rtl else (lead_x + grown)
            else:
                caret_x = lead_x if rtl else (lead_x + advance)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(C_ACCENT_LIGHT))
            p.drawRect(QRectF(caret_x - u * 0.06, inner.top() + u * 0.12,
                              u * 0.12, inner.height() - u * 0.24))

    def _paint_badge_and_caption(self, p, row, radius, u):
        """The key badge (idle or pressed) and the caption for the current phase."""
        down = self._key_down()
        badge_w = self._fm_badge.horizontalAdvance(self._hotkey_label) + u * 1.8
        drop = u * 0.12 if down else 0.0
        badge = QRectF(row.left() + 1.0, row.top() + drop, badge_w, row.height() - drop)

        if down:
            if self._phase_name == "press":
                # Ring expanding out of the key, strongest at the moment of the
                # press and gone by the time the text changes.
                ring_t = _smooth(self._elapsed / float(PHASES[self._phase][1]))
                glow = QColor(C_ACCENT_LIGHT)
                glow.setAlpha(int(120 * (1.0 - ring_t)))
                spread = u * 0.5 * ring_t
                p.setPen(QPen(glow, max(1.0, u * 0.1)))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(badge.adjusted(-spread, -spread, spread, spread),
                                  radius + spread, radius + spread)
            p.setPen(QPen(QColor(C_ACCENT_LIGHT), 1.0))
            p.setBrush(QColor(C_ACCENT))
            text_colour = QColor("#ffffff")
        else:
            p.setPen(QPen(QColor(C_BADGE_BORDER), 1.0))
            p.setBrush(QColor(C_BADGE_BG))
            text_colour = QColor(C_BADGE_TEXT)

        p.drawRoundedRect(badge, radius, radius)
        p.setPen(QPen(text_colour))
        p.setFont(self._badge_font)
        p.drawText(badge, int(Qt.AlignCenter) | int(Qt.TextSingleLine), self._hotkey_label)

        caption_rect = QRectF(badge.right() + u * 0.8, row.top(),
                              max(0.0, row.right() - badge.right() - u * 0.9),
                              row.height())
        if caption_rect.width() > u:
            p.setPen(QPen(QColor(C_CAPTION)))
            p.setFont(self._caption_font)
            caption = self._fm_caption.elidedText(self._caption(), Qt.ElideRight,
                                                  caption_rect.width())
            p.drawText(caption_rect,
                       int(Qt.AlignVCenter | Qt.AlignLeft) | int(Qt.TextSingleLine),
                       caption)


class ShortcutDemoDialog(QDialog):
    """Looping animated demos of both hotkeys, one canvas each.

    `tutorial=True` is the first-launch variant: a welcome line at the top and a
    'Get started' button instead of 'Close'.
    """

    def __init__(self, mac_hotkey, layout_hotkey, tutorial=False, parent=None):
        super().__init__(parent)
        self._tutorial = tutorial
        self.setWindowTitle("Welcome to MAC Converter" if tutorial
                            else "How the shortcuts work")
        self.setModal(True)

        # Same icon file as the rest of the app, resolved here rather than via
        # clipboard_hotkey.get_icon_path(), which would be a circular import.
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                     "icon-v1.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self.setStyleSheet("""
            QDialog {
                background-color: %s;
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
        """ % C_DIALOG_BG)

        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(20, 20, 20, 20)

        if tutorial:
            welcome = QLabel("MAC Converter lives in the system tray. Two hotkeys do "
                             "the work — here is what each one looks like in use.")
            welcome.setWordWrap(True)
            welcome.setAlignment(Qt.AlignCenter)
            welcome.setStyleSheet("color: #b0b0b0; font-size: 9pt;")
            layout.addWidget(welcome)
            layout.addSpacing(4)

        mac_label = format_hotkey(mac_hotkey)
        layout_label = format_hotkey(layout_hotkey)

        # MAC formats, in the order the hotkey cycles them (mac_formats.py).
        self.mac_canvas = _DemoCanvas(
            texts=["00:1A:2B:3C:4D:5E", "00-1A-2B-3C-4D-5E",
                   "001A.2B3C.4D5E", "001A2B3C4D5E"],
            hotkey_label=mac_label,
            captions={
                "idle": "A MAC address, in whatever format you were handed",
                "select": "Select it — in a config, a browser, a ticket",
                "press": "Press %s" % mac_label,
                "result": "Rewritten in place, in the next format",
            },
            font_family="Consolas",
            parent=self,
        )
        self._add_section(layout, "MAC format cycling",
                          "Each press rewrites the selected address in the next "
                          "format — colon, hyphen, Cisco dotted, bare.",
                          self.mac_canvas, separator=tutorial)

        # Hebrew typed with the US layout active comes out as 'akuo' (a sits on
        # shin, k on lamed, u on vav, o on final mem). Two texts, so the loop
        # itself shows the second press putting the original back.
        self.layout_canvas = _DemoCanvas(
            texts=["akuo", "שלום"],
            hotkey_label=layout_label,
            captions={
                "idle": ["Typed with the wrong layout active — gibberish",
                         "The text you meant, in the right alphabet"],
                "select": "Select the text",
                "press": "Press %s" % layout_label,
                "result": ["Pressed again: the original comes back",
                           "Same keystrokes, read under the other layout"],
            },
            font_family="Segoe UI",
            parent=self,
        )
        self._add_section(layout, "Keyboard layout fix",
                          "Typed in the wrong layout? Select it and press the "
                          "hotkey. Press it again to change it back.",
                          self.layout_canvas)

        layout.addSpacing(6)

        # close() rather than accept(), so closeEvent runs and the timers stop.
        button = QPushButton("Get started" if tutorial else "Close")
        button.clicked.connect(self.close)
        # Minimum, not fixed: at 150% scaling the label grows and a fixed width
        # would clip it ("Get started" -> "et starte").
        button.setMinimumWidth(130)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.setLayout(layout)
        self.setMinimumWidth(540)
        self.adjustSize()

    def _add_section(self, layout, title, subtitle, canvas, separator=True):
        """Separator, bold heading, grey one-liner, then the animation.

        `separator` is off for the first section when nothing precedes it, so
        the dialog doesn't open with a rule hanging under the title bar.
        """
        if separator:
            rule = QLabel()
            rule.setFixedHeight(1)
            rule.setStyleSheet("background-color: #555555;")
            layout.addWidget(rule)

        header = QLabel(title)
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)

        hint = QLabel(subtitle)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #999999; font-size: 9pt;")
        layout.addWidget(hint)

        layout.addSpacing(2)
        layout.addWidget(canvas)
        layout.addSpacing(6)

    # --- timer lifetime ---------------------------------------------------
    def stop_animations(self):
        """Stop every canvas timer. Idempotent."""
        for canvas in (getattr(self, "mac_canvas", None),
                       getattr(self, "layout_canvas", None)):
            if canvas is not None:
                canvas.stop()

    def animations_running(self):
        """True while any canvas timer is still live."""
        return any(c is not None and c.is_running()
                   for c in (getattr(self, "mac_canvas", None),
                             getattr(self, "layout_canvas", None)))

    def closeEvent(self, event):
        # A leaked QTimer in a tray app that runs for weeks is a real bug, so
        # this is the main place the animations are shut down.
        self.stop_animations()
        super().closeEvent(event)

    def done(self, result):
        # accept()/reject()/Esc funnel through done() and do NOT raise a close
        # event, so stop here too rather than trusting the caller to use close().
        self.stop_animations()
        super().done(result)


def show_demos(mac_hotkey, layout_hotkey, parent=None):
    """Construct the dialog and run it modally. Qt main thread only."""
    dlg = ShortcutDemoDialog(mac_hotkey, layout_hotkey, tutorial=False, parent=parent)
    return dlg.exec_()


def show_tutorial(mac_hotkey, layout_hotkey, parent=None):
    """First-launch variant: same animations, welcome line, 'Get started' button."""
    dlg = ShortcutDemoDialog(mac_hotkey, layout_hotkey, tutorial=True, parent=parent)
    return dlg.exec_()
