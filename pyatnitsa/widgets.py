"""Maxsus vidjetlar: animatsiyali orb, mini-grafik, chat kiritish maydoni."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QPlainTextEdit, QWidget

MODE_COLORS = {"idle": "#5b8def", "listening": "#22d3ee", "checking": "#fbbf24",
               "confirm": "#f59e0b", "running": "#a78bfa", "done": "#34d399"}


class OrbWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mode, self._level, self._target, self._phase = "idle", 0.0, 0.0, 0.0
        self.setMinimumSize(220, 220)
        self._timer = QTimer(self, interval=33)
        self._timer.timeout.connect(self._tick)

    def showEvent(self, e):
        self._timer.start()

    def hideEvent(self, e):
        self._timer.stop()

    def set_mode(self, mode: str) -> None:
        self.mode = mode

    def set_level(self, v: float) -> None:
        self._target = max(0.0, min(1.0, v))

    def _tick(self) -> None:
        speed = {"listening": 0.16, "checking": 0.2, "running": 0.25}.get(self.mode, 0.05)
        self._phase += speed
        self._level += (self._target - self._level) * 0.25
        if self.mode != "listening":
            self._target *= 0.8
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        R = min(self.width(), self.height()) / 2
        base = R * 0.5
        col = QColor(MODE_COLORS.get(self.mode, "#5b8def"))
        breathe = math.sin(self._phase) * 0.5 + 0.5
        lvl = self._level if self.mode == "listening" else (0.25 * breathe if self.mode in ("checking", "running") else 0.06 * breathe)
        glow = QRadialGradient(c, R)
        g0 = QColor(col); g0.setAlpha(90 + int(80 * lvl))
        g1 = QColor(col); g1.setAlpha(0)
        glow.setColorAt(0.35, g0); glow.setColorAt(1, g1)
        p.setPen(Qt.NoPen); p.setBrush(QBrush(glow)); p.drawEllipse(c, R, R)
        for i in range(3):
            path = QPainterPath()
            amp = base * (0.03 + 0.28 * lvl) * (1 - i * 0.2)
            for k in range(181):
                th = k / 180 * 2 * math.pi
                r = base * (1 + 0.11 * i) + amp * math.sin(5 * th + self._phase * (1 + 0.4 * i) + i * 1.7)
                pt = QPointF(c.x() + r * math.cos(th), c.y() + r * math.sin(th))
                path.moveTo(pt) if k == 0 else path.lineTo(pt)
            ring = QColor(col); ring.setAlpha(200 - i * 55)
            p.setPen(QPen(ring, 2.2 - i * 0.5)); p.setBrush(Qt.NoBrush); p.drawPath(path)
        core = QRadialGradient(c, base * (0.85 + 0.12 * lvl))
        c0 = QColor(col); c0.setAlpha(230)
        c1 = QColor("#0d0f14")
        core.setColorAt(0, c0.lighter(130)); core.setColorAt(0.6, c0.darker(160)); core.setColorAt(1, c1)
        p.setPen(Qt.NoPen); p.setBrush(QBrush(core)); p.drawEllipse(c, base * (0.85 + 0.12 * lvl), base * (0.85 + 0.12 * lvl))
        if self.mode in ("checking", "running"):
            p.setPen(QPen(QColor("white"), 3, Qt.SolidLine, Qt.RoundCap)); p.setBrush(Qt.NoBrush)
            rect = QRectF(c.x() - base * 1.28, c.y() - base * 1.28, base * 2.56, base * 2.56)
            p.drawArc(rect, int(-self._phase * 600) % 5760, 16 * 70)


class Sparkline(QWidget):
    def __init__(self, color: str = "#22d3ee", parent=None):
        super().__init__(parent)
        self.values: list[float] = []
        self.color = QColor(color)
        self.setMinimumHeight(54)

    def set_values(self, values, color: str | None = None) -> None:
        self.values = list(values)
        if color:
            self.color = QColor(color)
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QPen(QColor("#232734"), 1))
        for frac in (0.25, 0.5, 0.75):
            p.drawLine(0, int(h * frac), w, int(h * frac))
        if len(self.values) < 2:
            p.setPen(QColor("#6b7280")); p.drawText(self.rect(), Qt.AlignCenter, "Ma'lumot yig'ilmoqda…")
            return
        n = len(self.values)
        pts = [QPointF(w * i / (n - 1), h - (min(100.0, max(0.0, v)) / 100.0) * (h - 4) - 2) for i, v in enumerate(self.values)]
        area = QPainterPath(QPointF(0, h)); [area.lineTo(pt) for pt in pts]; area.lineTo(QPointF(w, h))
        fill = QColor(self.color); fill.setAlpha(45)
        p.setPen(Qt.NoPen); p.setBrush(fill); p.drawPath(area)
        line = QPainterPath(pts[0]); [line.lineTo(pt) for pt in pts[1:]]
        p.setPen(QPen(self.color, 2)); p.setBrush(Qt.NoBrush); p.drawPath(line)


class ChatInput(QPlainTextEdit):
    """Enter — yuborish, Shift+Enter — yangi qator."""
    sendRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Пятница ga buyruq yozing...")
        self.setTabChangesFocus(True)
        self.document().contentsChanged.connect(self._resize)
        self._resize()

    def _resize(self) -> None:
        lines = min(4, max(1, self.document().blockCount()))
        self.setFixedHeight(int(self.fontMetrics().lineSpacing() * lines + 24))

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.sendRequested.emit()
            return
        super().keyPressEvent(e)
