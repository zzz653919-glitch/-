"""Kichik umumiy vidjetlar: mini-grafik, ovoz vizualizatsiyasi, yuborish maydoni."""
from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QPlainTextEdit, QWidget

from .theme import C


class Sparkline(QWidget):
    """Haqiqiy o'lchovlar tarixi (0–100%). Ma'lumot bo'lmasa — bo'sh holat matni."""

    def __init__(self, color: str = C["cyan"], parent=None, empty_text: str = "Collecting data…"):
        super().__init__(parent)
        self.values: list[float] = []
        self.color = QColor(color)
        self.empty_text = empty_text
        self.setMinimumHeight(36)

    def set_values(self, values, color: str | None = None) -> None:
        self.values = list(values)
        if color:
            self.color = QColor(color)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor(255, 255, 255, 18), 1))
        for frac in (0.5,):
            p.drawLine(0, int(h * frac), w, int(h * frac))
        if len(self.values) < 2:
            p.setPen(QColor(C["dim"])); p.drawText(self.rect(), Qt.AlignCenter, self.empty_text)
            return
        n = len(self.values)
        pts = [QPointF(w * i / (n - 1), h - 2 - (min(100.0, max(0.0, v)) / 100.0) * (h - 4)) for i, v in enumerate(self.values)]
        area = QPainterPath(QPointF(0, h))
        for pt in pts:
            area.lineTo(pt)
        area.lineTo(QPointF(w, h))
        grad = QLinearGradient(0, 0, 0, h)
        top = QColor(self.color); top.setAlpha(80)
        bot = QColor(self.color); bot.setAlpha(0)
        grad.setColorAt(0, top); grad.setColorAt(1, bot)
        p.setPen(Qt.NoPen); p.setBrush(grad); p.drawPath(area)
        line = QPainterPath(pts[0])
        for pt in pts[1:]:
            line.lineTo(pt)
        p.setPen(QPen(self.color, 1.8)); p.setBrush(Qt.NoBrush); p.drawPath(line)


class VoiceBars(QWidget):
    """Mikrofon darajasi vizualizatsiyasi. Faqat HAQIQIY daraja (controller.level) keladi; tinglanmayotganda tekis chiziq."""
    N = 44

    def __init__(self, parent=None, reduced: bool = False):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setMinimumWidth(160)
        self._vals: deque[float] = deque([0.0] * self.N, maxlen=self.N)
        self.active = False
        self.reduced = reduced
        self._decay = QTimer(self, interval=40)
        self._decay.timeout.connect(self._fade)

    def set_active(self, on: bool) -> None:
        self.active = on
        if not on:
            self._decay.start()
        self.update()

    def push(self, level: float) -> None:
        if self.active:
            self._vals.append(max(0.0, min(1.0, level)))
            self.update()

    def _fade(self) -> None:
        if self.active:
            return
        self._vals.append(0.0)
        self.update()
        if not any(self._vals):
            self._decay.stop()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        gap = 3.0
        bw = max(2.0, (w - gap * (self.N - 1)) / self.N)
        for i, v in enumerate(self._vals):
            x = i * (bw + gap)
            bh = max(2.0, v * (h - 4)) if self.active or v else 2.0
            col = QColor(C["cyan"] if self.active else C["dim"])
            col.setAlpha(int(70 + 185 * v) if self.active else 70)
            p.setPen(Qt.NoPen); p.setBrush(col)
            p.drawRoundedRect(QRectF(x, (h - bh) / 2, bw, bh), 1.5, 1.5)


class ChatInput(QPlainTextEdit):
    """Enter — yuborish, Shift+Enter — yangi qator. Bo'sh maydonda Space — mikrofonni almashtirish so'rovi (matn yozilmaydi)."""
    sendRequested = Signal()
    micToggleRequested = Signal()
    micReleased = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Пятница ga buyruq yozing...   (Enter — send · Shift+Enter — new line)")
        self.setTabChangesFocus(True)
        self.document().contentsChanged.connect(self._resize)
        self._resize()

    def set_voice_only(self, on: bool) -> None:
        """«Faqat ovoz» rejimi: maydon yozishga yopiq (Space hamon mikrofon tugmasi), buyruqlar faqat ovozdan."""
        self.setReadOnly(bool(on))
        if on:
            self.clear()
            self.setPlaceholderText("Voice-only mode — hold SPACE, speak your command, release SPACE.   (Enter confirms a pending action)")
        else:
            self.setPlaceholderText("Пятница ga buyruq yozing...   (Enter — send · Shift+Enter — new line)")

    def _resize(self) -> None:
        lines = min(5, max(1, self.document().blockCount()))
        self.setFixedHeight(int(self.fontMetrics().lineSpacing() * lines + 24))

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.sendRequested.emit()
            return
        if e.key() == Qt.Key_Space and not self.toPlainText() and not e.modifiers():
            if not e.isAutoRepeat():
                self.micToggleRequested.emit()
            return                       # bo'sh maydonda bosh bo'shliq yozilmaydi: bu mikrofon tugmasi
        super().keyPressEvent(e)

    def keyReleaseEvent(self, e):
        if e.key() == Qt.Key_Space and not e.isAutoRepeat() and not self.toPlainText():
            self.micReleased.emit()
            return
        super().keyReleaseEvent(e)
