"""
shortcut_demo.py

Two things live in here:

* `show_demos()` — short looping animations of what each global hotkey does,
  reachable from the tray menu at any time.
* `show_tutorial()` — a stepped first-launch wizard with explanation bubbles and
  two steps where the user presses the real hotkeys and watches them work.

The two shortcuts behave completely differently, and that is the whole point of
this file. Verified against clipboard_hotkey.py:

    alt+shift+m (handle_hotkey)      reads pyperclip.paste(), converts to the
                                     next of 12 formats, writes the result back
                                     with pyperclip.copy(). The selection is
                                     never read and nothing on screen changes.

    ctrl+alt+l  (handle_layout_fix)  reads the foreground window's selection via
                                     selection_io.read_selection() and replaces
                                     it in place with replace_selection(),
                                     leaving its own output selected so a second
                                     press converts back.

Everything is drawn with QPainter and laid out with Qt widgets: no new
dependencies, no image/video/GIF assets — the installer is already 54 MB.

Public API (clipboard_hotkey.py wires to exactly this):

    ShortcutDemoDialog(mac_hotkey, layout_hotkey, tutorial=False, parent=None)
    show_demos(mac_hotkey, layout_hotkey, parent=None)
    show_tutorial(mac_hotkey, layout_hotkey, parent=None)

Importing this module has no side effects: no QApplication, no widgets, no fonts
and no clipboard access at import time, so the tray app can import it at startup
for free. clipboard_hotkey is deliberately NOT imported (circular); mac_formats
is, because it is a leaf module — `import re` and nothing else.

DPI: the Qt5 Windows plugin is system-DPI aware, so point-size fonts grow at
150% scaling but raw pixel values do not. Every drawn dimension below is derived
from font metrics (the height of one small text line is the unit), never
hard-coded, and nothing holding text gets a fixed width or height.
"""

import html
import os

from PyQt5.QtWidgets import (QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QWidget, QSizePolicy, QStackedWidget,
                             QScrollArea, QFrame, QLineEdit)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, QSize
from PyQt5.QtGui import (QFont, QColor, QIcon, QPainter, QPen, QFontMetricsF,
                         QPainterPath)

from mac_formats import convert_mac, detect_mac

# --- Palette: the same values the other dialogs in clipboard_hotkey.py use.
# Hex strings, not QColor objects, so nothing is constructed at import time.
C_DIALOG_BG = "#2b2b2b"
C_EDITOR_BG = "#1e1e1e"
C_EDITOR_BORDER = "#555555"
C_CHROME_DOT = "#4a4a4a"
C_TEXT = "#e6e6e6"
C_TEXT_DIM = "#8a8a8a"
C_TEXT_FRESH = "#4cc2ff"       # the just-changed value, before it settles
C_ACCENT = "#0078d4"           # app accent: selection, caret, pressed key
C_ACCENT_LIGHT = "#4ba3e3"
C_BADGE_BG = "#3c3c3c"
C_BADGE_BORDER = "#6a6a6a"
C_BADGE_TEXT = "#e0e0e0"
C_CAPTION = "#b0b0b0"
C_OK = "#4ec977"               # success tick / confirmed practice step

# Callout bubbles. Four tones; the border carries the meaning, the fill is just
# enough to lift the panel off the #2b2b2b dialog background.
_BUBBLE_TONES = {
    "info":    ("#1f3246", C_ACCENT),
    "warn":    ("#3b3222", "#c08a2e"),
    "ok":      ("#20352a", "#3fa85d"),
    "neutral": ("#333333", "#5a5a5a"),
}

# --- Animation state machines ------------------------------------------------
# One pass through a table is one demo step. Leaving the last phase advances the
# value index, so the value produced by one step is the value the next step
# starts from: that is what makes it loop.
SELECTION_PHASES = (
    ("idle", 900),      # nothing selected yet
    ("select", 650),    # highlight grows across the text
    ("hold", 320),      # fully selected, hand moving to the keys
    ("press", 420),     # key badge down
    ("result", 1500),   # text replaced in place, read it
)
CLIPBOARD_PHASES = (
    ("idle", 1000),     # the copied address sits on the clipboard
    ("hold", 420),      # hand moving to the keys
    ("press", 460),     # key badge down, the value travels
    ("result", 1600),   # the clipboard now holds the next format
)
TICK_MS = 33            # ~30 fps; only ticks while the dialog is open

PRESS_HOLD_MS = 170     # badge stays down this far into "result"

# How often the live practice step re-reads the clipboard. Fast enough that the
# change feels immediate, slow enough that we are not hammering a global lock
# that another process can be holding.
CLIPBOARD_POLL_MS = 250

# After the layout hotkey converts the practice box, re-select its contents so
# the next press has something to act on.
#
# selection_io.replace_selection() asks the target to keep the pasted text
# selected by sending Shift+Left once per character, but it sends that batch
# ~150 ms AFTER the paste (it waits for the target to read the clipboard, then
# restores it). Measured here, whether the selection survives is a race: it
# held on some runs of the practice step and not others. So we re-select
# ourselves, and the delay has to be comfortably longer than that 150 ms plus
# the clipboard restore, or our selectAll lands first and the late Shift+Left
# collapses it again. Firing too early is exactly the bug this value fixes.
PRACTICE_RESELECT_MS = 600

# The sample the MAC practice step puts on the clipboard, and the text the
# layout practice step starts from. 'akuo' is Hebrew שלום typed with the US
# layout active (a sits on shin, k on lamed, u on vav, o on final mem).
PRACTICE_MAC = "00:1A:2B:3C:4D:5E"
PRACTICE_LAYOUT_TEXT = "akuo"
PRACTICE_LAYOUT_HEBREW = "שלום"      # שלום

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


def _esc(text):
    """Escape a value before it goes into one of the rich-text bubbles.

    The hotkey labels come out of the settings file, so they are not ours to
    trust as HTML.
    """
    return html.escape(str(text), quote=False)


def _is_rtl(text):
    """True for Hebrew/Arabic text, so the demo selects it in the right direction."""
    return any("֐" <= ch <= "ࣿ" for ch in text)


def _has_hebrew(text):
    """True if the string contains a Hebrew letter — used to confirm practice."""
    return any("֐" <= ch <= "׿" for ch in text or "")


def _smooth(t):
    """Smoothstep easing, so motion doesn't start and stop abruptly."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def _pick(value, index):
    """Captions may be one string for every step, or one per step."""
    if isinstance(value, (list, tuple)):
        return value[index % len(value)] if value else ""
    return value


def _base_point_size():
    """The app font's point size, which is what carries DPI scaling.

    Falls back to 9pt when there is no QApplication — which can only happen if
    something builds a widget outside a running app, and then the size is
    academic anyway. We never create an application here.
    """
    app = QApplication.instance()
    if app is not None and app.font().pointSizeF() > 0:
        return app.font().pointSizeF()
    return 9.0


def _ui_unit():
    """Height of one line of the app font — the unit widget padding is built on."""
    return max(10.0, QFontMetricsF(
        QFont("Segoe UI", int(round(_base_point_size())))).height())


def _mix(a, b, t):
    """Blend two QColors; t=0 gives a, t=1 gives b."""
    return QColor(int(a.red() + (b.red() - a.red()) * t),
                  int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


# --- Clipboard access --------------------------------------------------------
# pyperclip is what the hotkey handler itself uses, so reading through it sees
# exactly what the handler sees. It is imported lazily: `import pyperclip`
# probes the platform for a clipboard mechanism, and this module promises to do
# nothing at import time. QApplication.clipboard() is the fallback.
#
# Every path is wrapped. The Windows clipboard is a single global lock and any
# other process can be holding it; a locked clipboard must never take the
# tutorial down with it.

_pyperclip = None          # the module once imported, False once known missing


def _pyperclip_module():
    global _pyperclip
    if _pyperclip is None:
        try:
            import pyperclip
            _pyperclip = pyperclip
        except Exception:
            _pyperclip = False
    return _pyperclip or None


def _read_clipboard_text():
    """Current clipboard text, or None if it could not be read."""
    mod = _pyperclip_module()
    if mod is not None:
        try:
            return mod.paste()
        except Exception:
            pass
    try:
        app = QApplication.instance()
        if app is not None:
            board = app.clipboard()
            if board is not None:
                return board.text()
    except Exception:
        pass
    return None


def _write_clipboard_text(text):
    """Put `text` on the clipboard. True if it went somewhere."""
    mod = _pyperclip_module()
    if mod is not None:
        try:
            mod.copy(text)
            return True
        except Exception:
            pass
    try:
        app = QApplication.instance()
        if app is not None:
            board = app.clipboard()
            if board is not None:
                board.setText(text)
                return True
    except Exception:
        pass
    return False


def _shorten(text, limit=52):
    """One-line preview of arbitrary clipboard content.

    Newlines become a glyph rather than being dropped, so a multi-line
    clipboard reads as multi-line — which is exactly the case where the MAC
    hotkey will refuse to do anything.
    """
    if text is None:
        return ""
    flat = (text.replace("\r\n", "↵").replace("\n", "↵")
                .replace("\r", "↵").replace("\t", " "))
    if len(flat) <= limit:
        return flat
    return flat[:limit - 1] + "…"


# --- Animated canvases -------------------------------------------------------

class _AnimCanvas(QWidget):
    """Shared plumbing for the looping animations.

    Subclasses supply a PHASES table and `_paint_stage()`; this class owns the
    phase clock, the fonts (all derived from the app font so they scale with
    DPI) and the key-badge-plus-caption row underneath.

    `texts` is the cycle of values the hotkey produces, in order; the animation
    walks it forever. `captions` maps a phase name to a caption, each either a
    single string or one string per step.
    """

    PHASES = SELECTION_PHASES

    def __init__(self, texts, hotkey_label, captions, font_family="Segoe UI", parent=None):
        super().__init__(parent)
        self._texts = list(texts) or [""]
        self._hotkey_label = hotkey_label
        self._captions = captions

        # Phase clock. _index is the step we are in: phases up to "press" show
        # texts[_index], "result" shows the next one.
        self._index = 0
        self._phase = 0
        self._elapsed = 0
        self._ticks = 0

        base_pt = _base_point_size()

        # Value font is per-demo: Consolas reads like a config file for hex MAC
        # addresses; the layout demo uses Segoe UI because it has the Hebrew
        # coverage that fixed-width faces can't be relied on for.
        self._text_font = QFont(font_family)
        self._text_font.setPointSizeF(base_pt * 1.35)
        self._badge_font = QFont("Segoe UI")
        self._badge_font.setPointSizeF(base_pt * 0.95)
        self._badge_font.setBold(True)
        self._caption_font = QFont("Segoe UI")
        self._caption_font.setPointSizeF(base_pt * 0.9)
        self._label_font = QFont("Segoe UI")
        self._label_font.setPointSizeF(base_pt * 0.82)

        self._fm_text = QFontMetricsF(self._text_font)
        self._fm_badge = QFontMetricsF(self._badge_font)
        self._fm_caption = QFontMetricsF(self._caption_font)
        self._fm_label = QFontMetricsF(self._label_font)

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

    def start(self):
        """Restart the animation timer. Idempotent."""
        if self._timer is not None and not self._timer.isActive():
            self._timer.start()

    def is_running(self):
        return self._timer is not None and self._timer.isActive()

    def _tick(self):
        self._ticks += 1
        self._elapsed += TICK_MS
        if self._elapsed >= self.PHASES[self._phase][1]:
            self._elapsed = 0
            self._phase = (self._phase + 1) % len(self.PHASES)
            if self.PHASES[self._phase][0] == "idle":
                # A full step just finished: the value that was produced becomes
                # the value we start from, and the loop continues from there.
                self._index = (self._index + 1) % len(self._texts)
        self.update()

    # --- state read by paintEvent ----------------------------------------
    @property
    def _phase_name(self):
        return self.PHASES[self._phase][0]

    def _phase_ms(self):
        return float(self.PHASES[self._phase][1])

    def _in_index(self):
        """Index of the value the step started from."""
        return self._index % len(self._texts)

    def _out_index(self):
        """Index of the value this step produces."""
        return (self._index + 1) % len(self._texts)

    def _key_down(self):
        name = self._phase_name
        return name == "press" or (name == "result" and self._elapsed < PRESS_HOLD_MS)

    def _freshness(self):
        """1.0 right after the value changed, decaying to 0 — drives the flash."""
        if self._phase_name != "result":
            return 0.0
        return max(0.0, 1.0 - self._elapsed / 500.0)

    def _caption(self):
        name = self._phase_name
        if name == "result":
            # Indexed by the value being produced, not the one we came from.
            return _pick(self._captions.get("result", ""), self._index + 1)
        if name in ("hold", "press"):
            return _pick(self._captions.get("press", ""), self._index)
        return _pick(self._captions.get(name, ""), self._index)

    # --- geometry (all derived from font metrics, never hard-coded px) ----
    def _unit(self):
        return self._fm_caption.height()

    def _stage_height(self):
        raise NotImplementedError

    def _stage_width_hint(self):
        raise NotImplementedError

    def _paint_stage(self, p, stage, radius, u):
        raise NotImplementedError

    def _row_height(self):
        return self._fm_badge.height() + self._unit() * 0.75

    def _caption_width_hint(self):
        return max((self._fm_caption.horizontalAdvance(_pick(v, i))
                    for v in self._captions.values()
                    for i in range(len(self._texts))), default=0.0)

    def sizeHint(self):
        u = self._unit()
        badge_w = self._fm_badge.horizontalAdvance(self._hotkey_label) + u * 1.8
        row_w = badge_w + u * 0.8 + self._caption_width_hint()
        height = self._stage_height() + u * 0.7 + self._row_height() + 2
        return QSize(int(max(self._stage_width_hint(), row_w, 360.0)) + 2,
                     int(height) + 1)

    def minimumSizeHint(self):
        # Narrower than the hint is allowed: captions elide and the stage clips
        # rather than forcing the dialog wide at 150% scaling.
        hint = self.sizeHint()
        return QSize(min(hint.width(), 320), hint.height())

    # --- painting ---------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        u = self._unit()
        radius = u * 0.35
        stage = QRectF(0.5, 0.5, self.width() - 1.0, self._stage_height())
        self._paint_stage(p, stage, radius, u)

        row = QRectF(0.0, stage.bottom() + u * 0.7, self.width(), self._row_height())
        self._paint_badge_and_caption(p, row, radius, u)

    def _paint_badge_and_caption(self, p, row, radius, u):
        """The key badge (idle or pressed) and the caption for the current phase."""
        down = self._key_down()
        badge_w = self._fm_badge.horizontalAdvance(self._hotkey_label) + u * 1.8
        drop = u * 0.12 if down else 0.0
        badge = QRectF(row.left() + 1.0, row.top() + drop, badge_w, row.height() - drop)

        if down:
            if self._phase_name == "press":
                # Ring expanding out of the key, strongest at the moment of the
                # press and gone by the time the value changes.
                ring_t = _smooth(self._elapsed / self._phase_ms())
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

    # --- small shared painters -------------------------------------------
    def _value_colour(self):
        """Normal text colour, flashing accent-blue just after a change."""
        return _mix(QColor(C_TEXT), QColor(C_TEXT_FRESH), self._freshness())

    def _paint_tick(self, p, cx, cy, size, colour, alpha=255):
        """A check mark, drawn as two strokes — no font glyph, no icon asset."""
        pen_colour = QColor(colour)
        pen_colour.setAlpha(max(0, min(255, alpha)))
        p.setPen(QPen(pen_colour, max(1.4, size * 0.22), Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        path = QPainterPath()
        path.moveTo(cx - size * 0.5, cy)
        path.lineTo(cx - size * 0.1, cy + size * 0.42)
        path.lineTo(cx + size * 0.55, cy - size * 0.45)
        p.drawPath(path)


class _SelectionCanvas(_AnimCanvas):
    """Selection semantics: text in a window is selected and replaced in place.

    This is the layout fixer, and it is literally what the hotkey does — read
    the foreground selection, paste over it, leave the result selected.
    """

    PHASES = SELECTION_PHASES

    def _stage_height(self):
        u = self._unit()
        return u * 0.95 + self._fm_text.height() * 1.5 + u * 0.55

    def _stage_width_hint(self):
        u = self._unit()
        widest = max((self._fm_text.horizontalAdvance(t) for t in self._texts), default=0.0)
        return widest + u * 2.4

    def _current_text(self):
        """The string on screen right now."""
        if self._phase_name == "result":
            return self._texts[self._out_index()]
        return self._texts[self._in_index()]

    def _selection_progress(self):
        """0.0 (nothing selected) .. 1.0 (whole string selected)."""
        name = self._phase_name
        if name == "idle":
            return 0.0
        if name == "select":
            return _smooth(self._elapsed / self._phase_ms())
        # Including "result": the hotkey leaves its own output selected, which
        # is exactly why a second press can act on it. Fading the highlight out
        # here would quietly misrepresent that.
        return 1.0

    def _paint_stage(self, p, editor, radius, u):
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
            fill = QColor(C_ACCENT)
            fill.setAlpha(150)
            p.setPen(Qt.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(sel, u * 0.1, u * 0.1)

        # Text over the highlight. Rect-based drawText lets Qt do the bidi
        # reordering, which keeps the Hebrew readable instead of reversed.
        p.setPen(QPen(self._value_colour()))
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


class _ClipboardCanvas(_AnimCanvas):
    """Clipboard semantics: a clipboard going in, a clipboard coming out.

    Deliberately NOT a text field with a selection in it. The MAC hotkey reads
    pyperclip.paste() and writes pyperclip.copy() — it never looks at what is
    selected and never changes anything on screen. Drawing an editor here was
    the factual error in the previous version of this file.
    """

    PHASES = CLIPBOARD_PHASES

    def _label_out(self):
        return "clipboard out  ·  format %d of %d" % (self._out_index() + 1,
                                                           len(self._texts))

    # --- geometry ---------------------------------------------------------
    def _card_height(self):
        u = self._unit()
        return u * 0.7 + self._fm_text.height() * 1.25 + u * 0.7

    def _glyph_width(self):
        return self._fm_text.height() * 0.72

    def _tick_room(self):
        return self._fm_text.height() * 0.85

    def _arrow_width(self):
        return self._unit() * 3.0

    def _card_width(self):
        u = self._unit()
        widest = max((self._fm_text.horizontalAdvance(t) for t in self._texts), default=0.0)
        return self._glyph_width() + u * 0.55 + widest + u * 1.1 + self._tick_room()

    def _stage_height(self):
        return self._card_height() + self._unit() * 0.3 + self._fm_label.height()

    def _stage_width_hint(self):
        return self._card_width() * 2.0 + self._arrow_width()

    def _transfer(self):
        """0.0 .. 1.0 along the arrow: how far the new value has travelled."""
        name = self._phase_name
        if name == "press":
            return _smooth(self._elapsed / self._phase_ms())
        if name == "result":
            return 1.0
        return 0.0

    # --- painting ---------------------------------------------------------
    def _paint_stage(self, p, stage, radius, u):
        card_h = self._card_height()
        arrow_w = self._arrow_width()
        card_w = max((stage.width() - arrow_w) / 2.0, u * 4.0)

        left = QRectF(stage.left(), stage.top(), card_w, card_h)
        right = QRectF(stage.right() - card_w, stage.top(), card_w, card_h)

        transfer = self._transfer()
        filled = self._phase_name == "result"

        self._paint_card(p, left, radius, u,
                         text=self._texts[self._in_index()],
                         label="clipboard in",
                         active=True, fresh=0.0, tick_alpha=0)
        self._paint_card(p, right, radius, u,
                         text=self._texts[self._out_index()] if filled else "",
                         label=self._label_out() if filled else "clipboard out",
                         active=filled, fresh=self._freshness(),
                         tick_alpha=255 if filled else 0)

        arrow = QRectF(left.right(), stage.top(),
                       max(0.0, right.left() - left.right()), card_h)
        self._paint_arrow(p, arrow, u, transfer)

    def _paint_card(self, p, rect, radius, u, text, label, active, fresh, tick_alpha):
        """One clipboard: glyph, value, optional tick, and a caption underneath."""
        body = QRectF(rect.left() + 0.5, rect.top() + 0.5,
                      max(1.0, rect.width() - 1.0), max(1.0, rect.height() - 1.0))
        if active:
            p.setPen(QPen(QColor(C_EDITOR_BORDER), 1.0))
            p.setBrush(QColor(C_EDITOR_BG))
        else:
            # Empty slot: dashed outline, no fill. Reads as "nothing here yet"
            # without needing a placeholder string.
            p.setPen(QPen(QColor(C_CHROME_DOT), 1.0, Qt.DashLine))
            p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(body, radius, radius)

        glyph_w = self._glyph_width()
        glyph_h = glyph_w * 1.3
        glyph = QRectF(body.left() + u * 0.55, body.center().y() - glyph_h / 2.0,
                       glyph_w, glyph_h)
        self._paint_clipboard_glyph(p, glyph, active)

        if text:
            tick_w = self._tick_room() if tick_alpha > 0 else 0.0
            inner = QRectF(glyph.right() + u * 0.55, body.top(),
                           max(0.0, body.right() - glyph.right() - u * 1.1 - tick_w),
                           body.height())
            p.setPen(QPen(_mix(QColor(C_TEXT), QColor(C_TEXT_FRESH), fresh)))
            p.setFont(self._text_font)
            p.drawText(inner, int(Qt.AlignVCenter | Qt.AlignLeft) | int(Qt.TextSingleLine),
                       self._fm_text.elidedText(text, Qt.ElideRight, inner.width()))

        if tick_alpha > 0:
            self._paint_tick(p, body.right() - self._tick_room() * 0.55,
                             body.center().y(), self._tick_room() * 0.55,
                             C_OK, tick_alpha)

        caption = QRectF(rect.left(), rect.bottom() + self._unit() * 0.3,
                         rect.width(), self._fm_label.height())
        p.setPen(QPen(QColor(C_CAPTION if active else C_TEXT_DIM)))
        p.setFont(self._label_font)
        p.drawText(caption,
                   int(Qt.AlignVCenter | Qt.AlignLeft) | int(Qt.TextSingleLine),
                   self._fm_label.elidedText(label, Qt.ElideRight, caption.width()))

    def _paint_clipboard_glyph(self, p, rect, active):
        """A clipboard: the board plus the clip at the top. Two rounded rects."""
        colour = QColor(C_BADGE_BORDER if active else C_CHROME_DOT)
        p.setPen(QPen(colour, max(1.0, rect.width() * 0.09)))
        p.setBrush(QColor(C_BADGE_BG) if active else Qt.NoBrush)
        clip_h = rect.height() * 0.17
        board = QRectF(rect.left(), rect.top() + clip_h * 0.7,
                       rect.width(), rect.height() - clip_h * 0.7)
        p.drawRoundedRect(board, rect.width() * 0.16, rect.width() * 0.16)
        clip = QRectF(rect.left() + rect.width() * 0.26, rect.top(),
                      rect.width() * 0.48, clip_h * 1.5)
        p.setBrush(QColor(C_DIALOG_BG))
        p.drawRoundedRect(clip, clip_h * 0.4, clip_h * 0.4)

    def _paint_arrow(self, p, rect, u, transfer):
        """Dim track with an accent fill that advances as the value is written."""
        y = rect.top() + self._card_height() / 2.0
        x0 = rect.left() + u * 0.5
        head = u * 0.42
        x1 = rect.right() - u * 0.5
        track_end = x1 - head * 0.6
        if track_end - x0 < head:
            return

        p.setPen(QPen(QColor(C_CHROME_DOT), max(1.0, u * 0.09), Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(x0, y), QPointF(track_end, y))

        if transfer > 0.0:
            lit = QColor(C_ACCENT_LIGHT)
            p.setPen(QPen(lit, max(1.4, u * 0.12), Qt.SolidLine, Qt.RoundCap))
            tip = x0 + (track_end - x0) * transfer
            p.drawLine(QPointF(x0, y), QPointF(tip, y))
            # A chip riding the line, so the eye follows the value across.
            if transfer < 1.0:
                p.setPen(Qt.NoPen)
                p.setBrush(lit)
                p.drawEllipse(QRectF(tip - u * 0.16, y - u * 0.16, u * 0.32, u * 0.32))

        # Arrowhead, lit once the value has arrived.
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(C_ACCENT_LIGHT) if transfer >= 1.0 else QColor(C_CHROME_DOT))
        head_path = QPainterPath()
        head_path.moveTo(x1, y)
        head_path.lineTo(x1 - head, y - head * 0.62)
        head_path.lineTo(x1 - head, y + head * 0.62)
        head_path.closeSubpath()
        p.drawPath(head_path)


# --- Wizard furniture --------------------------------------------------------

class _Bubble(QWidget):
    """A callout: rounded panel with a small tail, holding one rich-text label.

    The label does the text layout (word wrap, heightForWidth), so the bubble
    grows with the font instead of clipping at 150% scaling. The tail and the
    body are stroked as a single united path, so no border line runs through
    the join.
    """

    def __init__(self, text, tone="info", parent=None):
        super().__init__(parent)
        self._bg, self._border = _BUBBLE_TONES.get(tone, _BUBBLE_TONES["neutral"])
        self._u = _ui_unit()

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setStyleSheet("color: #e6e6e6; font-size: 9pt; background: transparent;")
        self._label.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)

        pad = int(self._u * 0.72)
        box = QVBoxLayout(self)
        box.setContentsMargins(pad + int(self._u * 0.2), self._tail_h() + pad,
                               pad + int(self._u * 0.2), pad)
        box.setSpacing(0)
        box.addWidget(self._label)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)

    def _tail_h(self):
        return int(self._u * 0.42)

    def setText(self, text):
        self._label.setText(text)

    def set_tone(self, tone):
        self._bg, self._border = _BUBBLE_TONES.get(tone, _BUBBLE_TONES["neutral"])
        self.update()

    def label(self):
        """The inner label. Used by the DPI clipping checks."""
        return self._label

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        tail = float(self._tail_h())
        radius = self._u * 0.35
        body = QRectF(0.5, tail + 0.5, max(1.0, self.width() - 1.0),
                      max(1.0, self.height() - tail - 1.0))

        path = QPainterPath()
        path.addRoundedRect(body, radius, radius)
        tip_x = body.left() + self._u * 1.5
        tail_path = QPainterPath()
        tail_path.moveTo(tip_x - self._u * 0.45, body.top() + 1.0)
        tail_path.lineTo(tip_x, body.top() - tail)
        tail_path.lineTo(tip_x + self._u * 0.45, body.top() + 1.0)
        tail_path.closeSubpath()

        p.setPen(QPen(QColor(self._border), 1.0))
        p.setBrush(QColor(self._bg))
        p.drawPath(path.united(tail_path))


class _StepDots(QWidget):
    """Progress dots. No text in it, so its size may follow the font exactly."""

    def __init__(self, count, parent=None):
        super().__init__(parent)
        self._count = max(1, count)
        self._current = 0
        self._u = _ui_unit()
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_current(self, index):
        self._current = max(0, min(self._count - 1, index))
        self.update()

    def _dot_r(self):
        return self._u * 0.19

    def _gap(self):
        return self._u * 0.42

    def _span(self):
        r = self._dot_r()
        return self._count * r * 2 + (self._count - 1) * self._gap()

    def sizeHint(self):
        return QSize(int(self._span()) + 2, int(self._dot_r() * 3.2) + 2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = self._dot_r()
        gap = self._gap()
        y = self.height() / 2.0
        x = (self.width() - self._span()) / 2.0
        p.setPen(Qt.NoPen)
        for i in range(self._count):
            cx = x + r + i * (r * 2 + gap)
            if i == self._current:
                p.setBrush(QColor(C_ACCENT_LIGHT))
                rr = r * 1.35
            elif i < self._current:
                p.setBrush(QColor(C_ACCENT))
                rr = r
            else:
                p.setBrush(QColor(C_CHROME_DOT))
                rr = r
            p.drawEllipse(QRectF(cx - rr, y - rr, rr * 2, rr * 2))


class _ValueField(QFrame):
    """A read-only, editor-looking box showing one line of live text.

    Used for the clipboard read-out. A QFrame rather than a QLineEdit, so there
    is nothing to focus or edit by accident. The stylesheet is scoped with an
    object-name selector: QLabel derives from QFrame, so a bare `QFrame {...}`
    rule here would give the child label its own border too.
    """

    def __init__(self, placeholder="", parent=None):
        super().__init__(parent)
        self.setObjectName("valueField")
        self.setFrameShape(QFrame.NoFrame)
        self._placeholder = placeholder
        self._ok = False

        base_pt = _base_point_size()
        self._value = QLabel(placeholder)
        value_font = QFont("Consolas")
        value_font.setPointSizeF(base_pt * 1.25)
        self._value.setFont(value_font)
        self._value.setWordWrap(False)
        self._value.setStyleSheet("background: transparent; color: %s;" % C_TEXT_DIM)

        pad = int(max(6.0, base_pt * 0.9))
        box = QHBoxLayout(self)
        box.setContentsMargins(pad, pad, pad, pad)
        box.setSpacing(0)
        box.addWidget(self._value)

        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)
        self._restyle()

    def _restyle(self):
        self.setStyleSheet(
            "QFrame#valueField { background-color: %s; border: 1px solid %s;"
            " border-radius: 4px; }" % (C_EDITOR_BG, C_OK if self._ok else C_EDITOR_BORDER))

    def set_value(self, text, ok=False, dim=False):
        shown = text if text else self._placeholder
        # Elide against the width the label actually has, rather than trusting a
        # character count: the same 52 characters are half as wide again at 150%
        # scaling, and a clipboard can hold anything. width() is meaningless
        # before the first layout pass, and the next poll 250 ms later fixes it.
        available = self._value.width()
        if available > 20:
            shown = QFontMetricsF(self._value.font()).elidedText(
                shown, Qt.ElideRight, available)
        self._value.setText(shown)
        colour = C_OK if ok else (C_TEXT_DIM if (dim or not text) else C_TEXT)
        self._value.setStyleSheet("background: transparent; color: %s;" % colour)
        if ok != self._ok:
            self._ok = ok
            self._restyle()

    def value_label(self):
        return self._value


class ShortcutDemoDialog(QDialog):
    """Both hotkeys explained. Two shapes, picked by `tutorial`.

    tutorial=False — the sheet reachable from the tray menu at any time: one
    looping animation per hotkey and a Close button.

    tutorial=True — a six-step wizard with Back / Next / Finish, explanation
    bubbles, and two steps where the user presses the real hotkeys and watches
    them work. The MAC step polls the clipboard; the layout step offers a real
    text box, which the layout hotkey can act on because it operates on whatever
    is selected in the foreground window — and that is this dialog.
    """

    # Page indices, so the wizard's wiring reads as something other than magic
    # numbers. The order is the order they are added to the stack.
    PAGE_WELCOME = 0
    PAGE_MAC_EXPLAIN = 1
    PAGE_MAC_PRACTICE = 2
    PAGE_LAYOUT_EXPLAIN = 3
    PAGE_LAYOUT_PRACTICE = 4
    PAGE_FINISH = 5
    PAGE_COUNT = 6

    def __init__(self, mac_hotkey, layout_hotkey, tutorial=False, parent=None):
        super().__init__(parent)
        self._tutorial = bool(tutorial)
        self._mac_label = format_hotkey(mac_hotkey)
        self._layout_label = format_hotkey(layout_hotkey)

        # Every QTimer this dialog owns, so closing can stop all of them in one
        # place. A leaked timer in a tray app that runs for weeks is a real bug.
        self._timers = []
        self.mac_canvas = None
        self.layout_canvas = None
        self._stack = None
        self._dots = None
        self._step_label = None
        self._back_button = None
        self._next_button = None

        # Practice-step widgets and state; only built in tutorial mode.
        self._mac_timer = None
        self._mac_field = None
        self._mac_status = None
        self._mac_seed_norm = None
        self._mac_last_seen = None
        self._mac_done = False
        self._layout_input = None
        self._layout_status = None
        self._layout_converted = False
        self._layout_prev = PRACTICE_LAYOUT_TEXT
        self._reselect_timer = None

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
            QPushButton:disabled {
                background-color: #3c3c3c;
                color: #777777;
            }
            QPushButton[flavour="secondary"] {
                background-color: #3c3c3c;
                color: #e0e0e0;
                border: 1px solid #6a6a6a;
                font-weight: normal;
            }
            QPushButton[flavour="secondary"]:hover {
                background-color: #474747;
            }
            QLineEdit {
                background-color: #1e1e1e;
                color: #e6e6e6;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 7px 9px;
                selection-background-color: #0078d4;
                selection-color: #ffffff;
            }
            QLineEdit:focus {
                border: 1px solid #0078d4;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)

        if self._tutorial:
            self._build_wizard()
        else:
            self._build_demo_sheet()

    # ------------------------------------------------------------------ #
    # Shape 1: the looping demo sheet (tray -> "How the shortcuts work")
    # ------------------------------------------------------------------ #
    def _build_demo_sheet(self):
        layout = QVBoxLayout()
        layout.setSpacing(6)
        layout.setContentsMargins(20, 20, 20, 20)

        self.mac_canvas = self._make_mac_canvas()
        self._add_section(
            layout, "MAC format cycling  —  %s" % self._mac_label,
            "Copy a MAC address, press the hotkey, paste. It rewrites what is on "
            "your clipboard, one format further round the cycle on each press. "
            "Nothing on screen is touched and the selection is never read.",
            self.mac_canvas, separator=False)

        self.layout_canvas = self._make_layout_canvas()
        self._add_section(
            layout, "Keyboard layout fix  —  %s" % self._layout_label,
            "Select text that came out in the wrong alphabet and press the hotkey. "
            "It replaces the selection in place, and leaves its own output "
            "selected so pressing again changes it back.",
            self.layout_canvas)

        layout.addSpacing(6)

        # close() rather than accept(), so closeEvent runs and the timers stop.
        button = QPushButton("Close")
        button.clicked.connect(self.close)
        # Minimum, not fixed: at 150% scaling the label grows and a fixed width
        # would clip it.
        button.setMinimumWidth(130)

        button_row = QHBoxLayout()
        button_row.addStretch()
        button_row.addWidget(button)
        button_row.addStretch()
        layout.addLayout(button_row)

        self.setLayout(layout)
        self.setMinimumWidth(560)
        self.adjustSize()

    def _add_section(self, layout, title, subtitle, canvas, separator=True):
        """Separator, bold heading, grey one-liner, then the animation.

        `separator` is off for the first section when nothing precedes it, so
        the dialog doesn't open with a rule hanging under the title bar.
        """
        if separator:
            layout.addWidget(self._rule())

        header = QLabel(title)
        header_font = QFont()
        header_font.setPointSize(10)
        header_font.setBold(True)
        header.setFont(header_font)
        header.setWordWrap(True)
        layout.addWidget(header)

        hint = QLabel(subtitle)
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #999999; font-size: 9pt;")
        layout.addWidget(hint)

        layout.addSpacing(2)
        layout.addWidget(canvas)
        layout.addSpacing(6)

    def _rule(self):
        """A 1px horizontal rule. setFixedHeight is safe — it holds no text."""
        rule = QLabel()
        rule.setFixedHeight(1)
        rule.setStyleSheet("background-color: #555555;")
        return rule

    # --- the two canvases, shared by both shapes --------------------------
    def _make_mac_canvas(self):
        """Clipboard-semantics animation, walking the real 12-format cycle.

        The strings come from mac_formats.convert_mac(), so they are the exact
        values the hotkey produces, in the exact order it produces them. If the
        format list ever changes, this follows it.
        """
        try:
            formats = [value for _name, value in convert_mac(detect_mac(PRACTICE_MAC))]
        except Exception:
            formats = [PRACTICE_MAC]
        return _ClipboardCanvas(
            texts=formats,
            hotkey_label=self._mac_label,
            captions={
                "idle": "You copied a MAC address — it is on your clipboard",
                "press": "Press %s" % self._mac_label,
                "result": "Clipboard now holds the next format — just paste it",
            },
            font_family="Consolas",
            parent=self,
        )

    def _make_layout_canvas(self):
        """Selection-semantics animation: replaced in place, press again to revert."""
        return _SelectionCanvas(
            texts=[PRACTICE_LAYOUT_TEXT, PRACTICE_LAYOUT_HEBREW],
            hotkey_label=self._layout_label,
            captions={
                "idle": ["Typed with the wrong layout active — gibberish",
                         "The text you meant, in the right alphabet"],
                "select": "Select it, in whatever window it is in",
                "press": "Press %s" % self._layout_label,
                "result": ["Pressed again: the original comes back",
                           "Replaced in place, and left selected"],
            },
            font_family="Segoe UI",
            parent=self,
        )

    # ------------------------------------------------------------------ #
    # Shape 2: the stepped tutorial
    # ------------------------------------------------------------------ #
    def _build_wizard(self):
        outer = QVBoxLayout()
        outer.setSpacing(8)
        outer.setContentsMargins(20, 18, 20, 18)

        # --- header: step counter on the left, dots on the right
        self._step_label = QLabel("")
        step_font = QFont()
        step_font.setPointSize(9)
        step_font.setBold(True)
        self._step_label.setFont(step_font)
        self._step_label.setStyleSheet("color: #9a9a9a;")

        self._dots = _StepDots(self.PAGE_COUNT, self)

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self._step_label)
        head.addStretch()
        head.addWidget(self._dots)
        outer.addLayout(head)
        outer.addWidget(self._rule())

        # --- pages
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._page_welcome())
        self._stack.addWidget(self._page_mac_explain())
        self._stack.addWidget(self._page_mac_practice())
        self._stack.addWidget(self._page_layout_explain())
        self._stack.addWidget(self._page_layout_practice())
        self._stack.addWidget(self._page_finish())

        # A scroll area around the stack is the DPI insurance policy. Six pages
        # at 150% scaling on a 1080p laptop can want more height than the screen
        # has, and without this something would be clipped off the bottom.
        # QStackedLayout's size hint is the maximum over all pages, so the
        # dialog does not resize as the user steps through.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setAutoFillBackground(False)
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(self._stack)
        scroll.setMinimumHeight(self._page_area_height())
        outer.addWidget(scroll, 1)

        # --- navigation
        self._back_button = QPushButton("‹  Back")
        self._back_button.setProperty("flavour", "secondary")
        self._back_button.setMinimumWidth(120)
        self._back_button.clicked.connect(self.go_back)

        self._next_button = QPushButton("Next  ›")
        self._next_button.setMinimumWidth(140)
        self._next_button.setDefault(True)
        self._next_button.clicked.connect(self._on_next_clicked)

        nav = QHBoxLayout()
        nav.setContentsMargins(0, 0, 0, 0)
        nav.addWidget(self._back_button)
        nav.addStretch()
        nav.addWidget(self._next_button)
        outer.addLayout(nav)

        self.setLayout(outer)
        self.setMinimumWidth(self._dialog_min_width())
        self._on_step_changed(self.PAGE_WELCOME)
        self.adjustSize()

    def _page_area_height(self):
        """How tall to let the page area be before it starts scrolling.

        The tallest page, capped at a share of the screen so the dialog always
        fits. Both numbers scale with DPI on their own. QScrollArea.sizeHint()
        is internally clamped to 24 text lines, which is why this is set
        explicitly rather than left to the hint.
        """
        want = self._stack.sizeHint().height() + 6
        cap = self._screen_fraction(1, 0.68)
        if cap:
            want = min(want, max(240, cap))
        return max(220, int(want))

    def _dialog_min_width(self):
        """Wide enough for the widest page, capped so it fits on the screen."""
        want = self._stack.sizeHint().width() + 56     # margins + a scrollbar
        cap = self._screen_fraction(0, 0.90)
        if cap:
            want = min(want, cap)
        return max(620, int(want))

    def _screen_fraction(self, axis, fraction):
        """`fraction` of the available screen width (axis 0) or height (axis 1)."""
        try:
            screen = QApplication.primaryScreen()
            if screen is not None:
                geom = screen.availableGeometry()
                return int((geom.width() if axis == 0 else geom.height()) * fraction)
        except Exception:
            pass
        return 0

    # --- page construction helpers ---------------------------------------
    def _page(self):
        """An empty page with its own layout, ready to have content added."""
        page = QWidget()
        box = QVBoxLayout(page)
        box.setSpacing(9)
        box.setContentsMargins(2, 8, 2, 4)
        return page, box

    def _title(self, text):
        label = QLabel(text)
        font = QFont()
        font.setPointSize(13)
        font.setBold(True)
        label.setFont(font)
        label.setWordWrap(True)
        label.setStyleSheet("color: #ffffff;")
        return label

    def _body(self, text, colour="#c8c8c8", size="9pt"):
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setStyleSheet("color: %s; font-size: %s;" % (colour, size))
        return label

    def _button_row(self, button):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(button)
        row.addStretch()
        return row

    # --- step 1: welcome --------------------------------------------------
    def _page_welcome(self):
        page, box = self._page()
        box.addWidget(self._title("Two hotkeys, two different habits"))
        box.addWidget(self._body(
            "MAC Converter has no main window. It sits in the system tray next to "
            "the clock and waits for one of two keyboard shortcuts. The two look "
            "alike and work in completely different ways — which is the one "
            "thing worth taking away from this tutorial."))
        box.addWidget(_Bubble(
            "<b>%s &mdash; works on your clipboard.</b><br>"
            "Copy a MAC address, press the keys, paste. The reformatted address "
            "is waiting on your clipboard. <b>Nothing on your screen changes</b>, "
            "and it does not care what you have selected."
            % _esc(self._mac_label), tone="info", parent=page))
        box.addWidget(_Bubble(
            "<b>%s &mdash; works on your selection.</b><br>"
            "Select the text that came out wrong, press the keys, and it is "
            "<b>replaced where it sits</b>. Your clipboard is saved and put back "
            "afterwards, so nothing you had copied is lost."
            % _esc(self._layout_label), tone="info", parent=page))
        box.addWidget(self._body(
            "Six short steps. Two of them hand you the real hotkeys so you can "
            "watch what happens and be sure they work before you need them. "
            "Nothing in here changes your settings.",
            colour="#9a9a9a", size="8pt"))
        box.addStretch()
        return page

    # --- step 2: MAC, explained ------------------------------------------
    def _page_mac_explain(self):
        page, box = self._page()
        box.addWidget(self._title("MAC format cycling  —  %s" % self._mac_label))
        box.addWidget(_Bubble(
            "<b>What to do</b><br>"
            "1. &nbsp;Copy a MAC address with <b>Ctrl&nbsp;+&nbsp;C</b> &mdash; out of "
            "a switch config, a browser, a ticket, anywhere.<br>"
            "2. &nbsp;Press <b>%s</b>.<br>"
            "3. &nbsp;Paste with <b>Ctrl&nbsp;+&nbsp;V</b>. The address arrives in the "
            "next format.<br><br>"
            "Press the hotkey again before pasting and it moves one more step "
            "round the cycle, so you can tab through formats until the one you "
            "want is on the clipboard."
            % _esc(self._mac_label), tone="info", parent=page))
        box.addWidget(_Bubble(
            "<b>Two things that trip people up</b><br>"
            "&bull; &nbsp;<b>Selecting is not enough — you have to copy.</b> This "
            "hotkey reads your clipboard and writes back to your clipboard. It "
            "never looks at the selection and never edits the window in front of "
            "you.<br>"
            "&bull; &nbsp;<b>The clipboard must hold the address and nothing else.</b> "
            "Surrounding spaces and newlines are fine, other words are not: copy "
            "<i>&ldquo;the AP mac is 00:1A:2B:3C:4D:5E&rdquo;</i> and you get the "
            "notification <i>&ldquo;No valid MAC address in clipboard&rdquo;</i>. "
            "Copy just the address and it works.",
            tone="warn", parent=page))

        self.mac_canvas = self._make_mac_canvas()
        box.addWidget(self.mac_canvas)
        box.addWidget(self._body(
            "There are <b>12 formats</b> in the cycle — colon, hyphen, Cisco "
            "dotted, six-and-six, 4-4-4 and bare, each in upper and lower case — "
            "and it wraps round to the start. After each press a small popup "
            "appears near the tray listing them all, with the one you just got at "
            "the top in bold: click any other line to copy that one instead. It "
            "closes itself after a few seconds, or on <b>Esc</b>.",
            colour="#9a9a9a", size="8pt"))
        box.addStretch()
        return page

    # --- step 3: MAC, live practice --------------------------------------
    def _page_mac_practice(self):
        page, box = self._page()
        box.addWidget(self._title("Your turn  —  press %s" % self._mac_label))
        box.addWidget(_Bubble(
            "<b>Try it now, for real.</b><br>"
            "1. &nbsp;Click the button below. That puts <b>%s</b> on your clipboard, "
            "exactly as if you had copied it out of a config.<br>"
            "2. &nbsp;Press <b>%s</b>.<br>"
            "3. &nbsp;Watch the read-out. <b>Nothing on this page is selected</b> and "
            "nothing on it changes — but your clipboard does.<br><br>"
            "Keep pressing to walk round the cycle."
            % (_esc(PRACTICE_MAC), _esc(self._mac_label)), tone="info", parent=page))

        seed_button = QPushButton("Copy %s to the clipboard" % PRACTICE_MAC)
        seed_button.setMinimumWidth(260)
        seed_button.clicked.connect(self._seed_practice_clipboard)
        box.addLayout(self._button_row(seed_button))

        box.addWidget(self._body("Your clipboard, live:", colour="#9a9a9a", size="8pt"))
        self._mac_field = _ValueField("(nothing read yet)", parent=page)
        box.addWidget(self._mac_field)

        self._mac_status = _Bubble("Click the button above to begin.",
                                   tone="neutral", parent=page)
        box.addWidget(self._mac_status)

        box.addWidget(self._body(
            "If the read-out never changes, the hotkey is not reaching the app — "
            "another program may have claimed the same combination. Tray icon "
            "&rarr; <b>Settings</b> lets you pick a different one.",
            colour="#9a9a9a", size="8pt"))
        box.addStretch()

        # Polls the clipboard while this page is visible. Registered in
        # self._timers so closing the dialog stops it wherever we happen to be.
        self._mac_timer = QTimer(self)
        self._mac_timer.setInterval(CLIPBOARD_POLL_MS)
        self._mac_timer.timeout.connect(self._poll_practice_clipboard)
        self._timers.append(self._mac_timer)
        return page

    def _seed_practice_clipboard(self):
        """Put the sample MAC on the clipboard and arm the read-out."""
        if _write_clipboard_text(PRACTICE_MAC):
            # Case-folded: mac_formats.normalize_mac() strips separators but
            # leaves the case alone, and half the formats in the cycle are
            # lowercase. Comparing raw would call format 2 "a different
            # address" — which is exactly what it did before this was fixed.
            self._mac_seed_norm = (detect_mac(PRACTICE_MAC) or "").lower()
            self._mac_last_seen = PRACTICE_MAC
            self._mac_done = False
            self._mac_status.set_tone("info")
            self._mac_status.setText(
                "On the clipboard. Now press <b>%s</b> — the read-out below "
                "updates on its own." % _esc(self._mac_label))
        else:
            self._mac_status.set_tone("warn")
            self._mac_status.setText(
                "Could not write to the clipboard — another program is holding "
                "it open. Try the button again in a moment.")
        self._poll_practice_clipboard()

    def _poll_practice_clipboard(self):
        """Read the clipboard and decide whether the hotkey has been pressed.

        Success test: the clipboard still holds the same twelve hex digits we
        seeded, but as a different string. That is exactly what the hotkey does,
        and nothing else does it by accident. The format number comes from
        looking the new string up in mac_formats.convert_mac(), so it is the
        real position in the cycle rather than a count of polls — a press we
        missed between two polls still reports the right number.
        """
        text = _read_clipboard_text()
        if text is None:
            self._mac_field.set_value("(clipboard could not be read)", dim=True)
            return

        stripped = text.strip()
        self._mac_field.set_value(_shorten(text) or "(empty)",
                                  ok=self._mac_done, dim=not stripped)

        if self._mac_seed_norm is None:
            return                      # not armed yet: nothing to judge

        norm = detect_mac(text)
        if norm is None:
            self._mac_done = False
            self._mac_status.set_tone("warn")
            self._mac_status.setText(
                "The clipboard no longer holds a MAC address on its own, so the "
                "hotkey would answer <i>&ldquo;No valid MAC address in "
                "clipboard&rdquo;</i>. Click the button again to reset it.")
            return

        if norm.lower() != self._mac_seed_norm:
            self._mac_status.set_tone("neutral")
            self._mac_status.setText(
                "That is a different address from the sample. Click the button "
                "again to go back to <b>%s</b>." % _esc(PRACTICE_MAC))
            return

        if stripped == (self._mac_last_seen or "").strip():
            if not self._mac_done:
                self._mac_status.set_tone("info")
                self._mac_status.setText(
                    "Waiting for <b>%s</b>… &nbsp;(nothing is selected, and "
                    "nothing needs to be — just press the keys)"
                    % _esc(self._mac_label))
            return

        # Same address, different string: the hotkey ran.
        self._mac_last_seen = stripped
        self._mac_done = True
        position, name = self._describe_format(norm, stripped)
        self._mac_field.set_value(_shorten(text), ok=True)
        self._mac_status.set_tone("ok")
        tail = ("Format <b>%d of %d</b>: %s. " % (position, len(convert_mac(norm)),
                                                  _esc(name))) if position else ""
        self._mac_status.setText(
            "✓ <b>That's it — the reformatted address is on your clipboard "
            "now.</b><br>%sNothing on this page moved. Press <b>%s</b> again to "
            "step to the next format, or paste it somewhere to prove it."
            % (tail, _esc(self._mac_label)))

    def _describe_format(self, norm, value):
        """(1-based position in the cycle, format name) for `value`, or (None, '')."""
        try:
            for i, (name, candidate) in enumerate(convert_mac(norm)):
                if candidate == value:
                    return i + 1, name
        except Exception:
            pass
        return None, ""

    # --- step 4: layout fix, explained -----------------------------------
    def _page_layout_explain(self):
        page, box = self._page()
        box.addWidget(self._title("Keyboard layout fix  —  %s" % self._layout_label))
        box.addWidget(self._body(
            "You start typing before noticing the layout indicator still says EN, "
            "and out comes <i>akuo</i> instead of %s. The keystrokes were right; "
            "only the layout reading them was wrong. This hotkey re-reads those "
            "same keystrokes under another installed layout."
            % PRACTICE_LAYOUT_HEBREW))
        box.addWidget(_Bubble(
            "<b>What to do</b><br>"
            "1. &nbsp;<b>Select</b> the text that came out wrong — drag over it, or "
            "click in it and press <b>Ctrl&nbsp;+&nbsp;A</b>.<br>"
            "2. &nbsp;Press <b>%s</b>.<br>"
            "3. &nbsp;The selection is <b>replaced in place</b>. No copying, no "
            "pasting, nothing for you to do afterwards."
            % _esc(self._layout_label), tone="info", parent=page))
        box.addWidget(_Bubble(
            "<b>Worth knowing</b><br>"
            "&bull; &nbsp;It leaves its own output selected, so <b>pressing again "
            "converts it back</b> — or, with three or more layouts installed, "
            "walks on to the next candidate. A few editors drop that selection; "
            "there, select the text again before the second press.<br>"
            "&bull; &nbsp;Press it with <b>nothing selected</b> and you get a tray "
            "notification instead: <i>&ldquo;Select the text you want to fix, then "
            "press the hotkey again.&rdquo;</i> It will never select the whole "
            "document on your behalf.<br>"
            "&bull; &nbsp;<b>Tap the keys, don't hold them.</b> While a key is still "
            "down the operation aborts on purpose, rather than fighting your "
            "fingers over a synthetic keystroke.<br>"
            "&bull; &nbsp;Your clipboard is snapshotted and restored, so whatever you "
            "had copied survives.",
            tone="warn", parent=page))

        self.layout_canvas = self._make_layout_canvas()
        box.addWidget(self.layout_canvas)
        box.addStretch()
        return page

    # --- step 5: layout fix, live practice -------------------------------
    def _page_layout_practice(self):
        page, box = self._page()
        box.addWidget(self._title("Your turn  —  press %s" % self._layout_label))
        box.addWidget(_Bubble(
            "<b>Try it now, for real.</b><br>"
            "The box below is an ordinary text box, and the hotkey acts on "
            "whatever is selected in the window in front — which right now is "
            "this one. So this genuinely works.<br><br>"
            "1. &nbsp;<b>Select the text in the box</b>: click in it and press "
            "<b>Ctrl&nbsp;+&nbsp;A</b>, or drag across it.<br>"
            "2. &nbsp;Press <b>%s</b>.<br>"
            "3. &nbsp;Then press it once more and watch <i>akuo</i> come back."
            % _esc(self._layout_label), tone="info", parent=page))

        self._layout_input = QLineEdit(PRACTICE_LAYOUT_TEXT, page)
        # Segoe UI covers Hebrew; fixed-width faces can't be relied on for it.
        practice_font = QFont("Segoe UI")
        practice_font.setPointSizeF(_base_point_size() * 1.45)
        self._layout_input.setFont(practice_font)
        self._layout_input.setMinimumWidth(220)
        # Connected after construction, so building the box emits nothing and
        # _layout_prev starts in step with what is on screen.
        self._layout_prev = PRACTICE_LAYOUT_TEXT
        self._layout_input.textChanged.connect(self._on_layout_text_changed)
        box.addWidget(self._layout_input)

        reset = QPushButton("Reset to akuo and select it")
        reset.setProperty("flavour", "secondary")
        reset.setMinimumWidth(230)
        reset.clicked.connect(self._reset_layout_practice)
        box.addLayout(self._button_row(reset))

        self._layout_status = _Bubble(
            "Select the text in the box, then press <b>%s</b>." % _esc(self._layout_label),
            tone="neutral", parent=page)
        box.addWidget(self._layout_status)

        box.addWidget(self._body(
            "Press the hotkey with <b>nothing selected</b> and you will get the "
            "tray notification instead of a change. That is worth doing once — "
            "it is the mistake you are most likely to make later.<br>"
            "This box also <b>re-selects the result for you</b> after each "
            "conversion, so you can press again straight away. Out in a real "
            "editor the hotkey asks for the same thing; if your editor drops the "
            "selection, just select the text again before pressing.",
            colour="#9a9a9a", size="8pt"))
        box.addStretch()

        # Re-arms the box after a conversion. A child QTimer rather than
        # QTimer.singleShot, so closing the dialog can stop it like any other.
        self._reselect_timer = QTimer(self)
        self._reselect_timer.setSingleShot(True)
        self._reselect_timer.setInterval(PRACTICE_RESELECT_MS)
        self._reselect_timer.timeout.connect(self._select_practice_text)
        self._timers.append(self._reselect_timer)
        return page

    def _select_practice_text(self):
        """Focus the practice box and select everything in it.

        Guarded on the current step: a stray fire while the user is on another
        page must not yank focus out from under them.
        """
        box = self._layout_input
        if box is None or self.current_step() != self.PAGE_LAYOUT_PRACTICE:
            return
        if not box.text():
            return
        box.setFocus(Qt.OtherFocusReason)
        box.selectAll()

    def _reset_layout_practice(self):
        if self._layout_input is None:
            return
        self._layout_converted = False
        self._layout_input.setText(PRACTICE_LAYOUT_TEXT)
        self._layout_input.setFocus(Qt.OtherFocusReason)
        self._layout_input.selectAll()
        self._layout_status.set_tone("info")
        self._layout_status.setText(
            "Selected and ready. Press <b>%s</b>." % _esc(self._layout_label))

    def _on_layout_text_changed(self, text):
        """Decide whether what just happened was a layout conversion.

        The conversion is one character in, one character out, and every
        character comes out different — so the signature is: same length as
        before, and not one position left alone. Typing by hand can reach the
        right length but never changes every position at once, so it is told it
        is not a conversion instead of being congratulated for editing the box.
        """
        original = PRACTICE_LAYOUT_TEXT
        previous, self._layout_prev = self._layout_prev, text
        wholesale = (len(text) == len(previous) > 0
                     and all(a != b for a, b in zip(previous, text)))
        if text == original:
            if self._layout_converted:
                self._layout_converted = False
                self._arm_reselect()
                self._layout_status.set_tone("ok")
                self._layout_status.setText(
                    "✓ <b>And back again.</b> The output stayed selected after "
                    "the first conversion, which is why the second press had "
                    "something to act on. That is the whole trick — press it "
                    "twice and you are back where you started.")
            else:
                self._layout_status.set_tone("neutral")
                self._layout_status.setText(
                    "Select the text in the box, then press <b>%s</b>."
                    % _esc(self._layout_label))
            return

        if wholesale and text.strip() and len(text) == len(original):
            self._layout_converted = True
            self._arm_reselect()
            extra = (" Those are the same four keystrokes, read under your Hebrew "
                     "layout." if _has_hebrew(text) else "")
            self._layout_status.set_tone("ok")
            self._layout_status.setText(
                "✓ <b>Replaced in place — and still selected.</b> Your "
                "clipboard was saved and put back; check it if you like.%s<br>"
                "Now press <b>%s</b> again to turn it back into <i>akuo</i>."
                % (extra, _esc(self._layout_label)))
            return

        self._layout_status.set_tone("neutral")
        self._layout_status.setText(
            "That does not look like a layout conversion — that swaps one "
            "character for one character. Use <b>Reset to akuo and select it</b>, "
            "then press the hotkey.")

    def _arm_reselect(self):
        """Re-select the practice box shortly, so the next press has a target."""
        if self._reselect_timer is not None:
            self._reselect_timer.start()

    # --- step 6: finish ---------------------------------------------------
    def _page_finish(self):
        page, box = self._page()
        box.addWidget(self._title("Where everything lives"))
        box.addWidget(self._body(
            "That is both shortcuts. From here on the app stays out of the way — "
            "there is no window to keep open."))
        box.addWidget(_Bubble(
            "<b>Right-click the tray icon</b>, next to the clock:<br>"
            "&bull; &nbsp;<b>Settings</b> &mdash; rebind either hotkey, or clear the box "
            "to switch one off entirely. The notification duration and the vendor "
            "database live there too.<br>"
            "&bull; &nbsp;<b>How the shortcuts work</b> &mdash; the two looping "
            "animations from steps 2 and 4, any time you want them.<br>"
            "&bull; &nbsp;<b>About</b> &mdash; version, licence and the vendor database "
            "status.<br>"
            "&bull; &nbsp;<b>Quit</b> &mdash; the hotkeys stop working until you start "
            "the app again.", tone="info", parent=page))
        box.addWidget(_Bubble(
            "<b>This tutorial is not a one-off.</b> It can be re-run from the tray "
            "menu whenever you want it — including the two practice steps.",
            tone="neutral", parent=page))
        box.addWidget(self._body(
            "One last reminder, because it is the only thing that is easy to get "
            "wrong:<br><b>%s</b> works on what you <b>copied</b>. &nbsp;<b>%s</b> "
            "works on what you <b>selected</b>."
            % (_esc(self._mac_label), _esc(self._layout_label)),
            colour="#c8c8c8", size="9pt"))
        box.addStretch()
        return page

    # ------------------------------------------------------------------ #
    # Wizard navigation (public, so a test harness can drive it)
    # ------------------------------------------------------------------ #
    def is_tutorial(self):
        return self._tutorial

    def step_count(self):
        """Number of wizard steps, or 0 for the plain demo sheet."""
        return self._stack.count() if self._stack is not None else 0

    def current_step(self):
        """0-based index of the visible step, or -1 for the plain demo sheet."""
        return self._stack.currentIndex() if self._stack is not None else -1

    def is_last_step(self):
        return self._stack is not None and self.current_step() == self.step_count() - 1

    def go_next(self):
        """Advance one step. No-op on the last step. True if it moved."""
        if self._stack is None or self.is_last_step():
            return False
        self._on_step_changed(self.current_step() + 1)
        return True

    def go_back(self):
        """Go back one step. No-op on the first step. True if it moved."""
        if self._stack is None or self.current_step() <= 0:
            return False
        self._on_step_changed(self.current_step() - 1)
        return True

    def _on_next_clicked(self):
        # On the last step the same button reads Finish and closes the dialog.
        # close() rather than accept() keeps closeEvent in the picture, though
        # done() stops the timers as well.
        if self.is_last_step():
            self.close()
        else:
            self.go_next()

    def _on_step_changed(self, index):
        """Show step `index`, then run only the timers that step needs."""
        self._stack.setCurrentIndex(index)
        total = self.step_count()
        self._step_label.setText("Step %d of %d" % (index + 1, total))
        self._dots.set_current(index)
        self._back_button.setEnabled(index > 0)
        self._next_button.setText("Finish" if index == total - 1 else "Next  ›")

        # Animations run only on the page they are on. This dialog can sit open
        # for a while and there is no reason to repaint a hidden canvas 30 times
        # a second.
        if self.mac_canvas is not None:
            (self.mac_canvas.start if index == self.PAGE_MAC_EXPLAIN
             else self.mac_canvas.stop)()
        if self.layout_canvas is not None:
            (self.layout_canvas.start if index == self.PAGE_LAYOUT_EXPLAIN
             else self.layout_canvas.stop)()

        if self._mac_timer is not None:
            if index == self.PAGE_MAC_PRACTICE:
                self._poll_practice_clipboard()
                self._mac_timer.start()
            else:
                self._mac_timer.stop()

        if index == self.PAGE_LAYOUT_PRACTICE and self._layout_input is not None:
            # Focus and select, so the very first press works without the user
            # having to find the box first. The instructions still spell out how
            # to select, because out in the real world they will have to.
            self._layout_input.setFocus(Qt.OtherFocusReason)
            self._layout_input.selectAll()
        elif self._next_button is not None:
            self._next_button.setFocus(Qt.OtherFocusReason)

    # ------------------------------------------------------------------ #
    # Timer lifetime
    # ------------------------------------------------------------------ #
    def stop_animations(self):
        """Stop every timer this dialog owns. Idempotent."""
        for canvas in (self.mac_canvas, self.layout_canvas):
            if canvas is not None:
                canvas.stop()
        for timer in self._timers:
            try:
                if timer.isActive():
                    timer.stop()
            except RuntimeError:
                pass        # C++ side already gone; nothing left to stop

    def animations_running(self):
        """True while any timer this dialog owns is still live."""
        if any(c is not None and c.is_running()
               for c in (self.mac_canvas, self.layout_canvas)):
            return True
        for timer in self._timers:
            try:
                if timer.isActive():
                    return True
            except RuntimeError:
                pass
        return False

    def closeEvent(self, event):
        # A leaked QTimer in a tray app that runs for weeks is a real bug, so
        # this is the main place everything is shut down.
        self.stop_animations()
        super().closeEvent(event)

    def done(self, result):
        # accept()/reject()/Esc funnel through done() and do NOT raise a close
        # event, so stop here too rather than trusting the caller to use close().
        self.stop_animations()
        super().done(result)


def show_demos(mac_hotkey, layout_hotkey, parent=None):
    """Looping animations of both hotkeys, run modally. Qt main thread only."""
    dlg = ShortcutDemoDialog(mac_hotkey, layout_hotkey, tutorial=False, parent=parent)
    return dlg.exec_()


def show_tutorial(mac_hotkey, layout_hotkey, parent=None):
    """Stepped tutorial with live practice, run modally. Qt main thread only."""
    dlg = ShortcutDemoDialog(mac_hotkey, layout_hotkey, tutorial=True, parent=parent)
    return dlg.exec_()
