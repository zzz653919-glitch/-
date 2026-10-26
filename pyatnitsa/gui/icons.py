"""Vektor ikonkalar (QPainter bilan chiziladi, tashqi fayl kerak emas) — barchasi bir xil uslubda."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _draw(name: str, p: QPainter, s: float) -> None:
    c = s / 2
    if name == "assistant":                       # AI yadrosi: halqa + nuqta
        p.drawEllipse(QPointF(c, c), s * 0.38, s * 0.38)
        p.drawEllipse(QPointF(c, c), s * 0.16, s * 0.16)
        for a in (0, 90, 180, 270):
            r = math.radians(a)
            p.drawLine(QPointF(c + math.cos(r) * s * 0.38, c + math.sin(r) * s * 0.38), QPointF(c + math.cos(r) * s * 0.48, c + math.sin(r) * s * 0.48))
    elif name == "history":                       # soat + aylanma strelka
        p.drawEllipse(QPointF(c, c), s * 0.38, s * 0.38)
        p.drawLine(QPointF(c, c), QPointF(c, s * 0.28)); p.drawLine(QPointF(c, c), QPointF(s * 0.66, c + s * 0.08))
    elif name == "monitor":                       # ustunli diagramma
        for i, h in enumerate((0.3, 0.55, 0.42, 0.7)):
            x = s * (0.17 + i * 0.19)
            p.drawLine(QPointF(x, s * 0.82), QPointF(x, s * (0.82 - h)))
    elif name == "diagnostics":                   # yurak urishi
        path = QPainterPath(QPointF(s * 0.08, c))
        for x, y in ((0.28, 0.5), (0.38, 0.22), (0.52, 0.78), (0.62, 0.5), (0.92, 0.5)):
            path.lineTo(s * x, s * y)
        p.drawPath(path)
    elif name == "settings":                      # tishli g'ildirak
        p.drawEllipse(QPointF(c, c), s * 0.2, s * 0.2)
        for k in range(8):
            r = math.radians(k * 45)
            p.drawLine(QPointF(c + math.cos(r) * s * 0.3, c + math.sin(r) * s * 0.3), QPointF(c + math.cos(r) * s * 0.44, c + math.sin(r) * s * 0.44))
        p.drawEllipse(QPointF(c, c), s * 0.32, s * 0.32)
    elif name == "about":                         # «i»
        p.drawEllipse(QPointF(c, c), s * 0.4, s * 0.4)
        p.drawLine(QPointF(c, s * 0.44), QPointF(c, s * 0.7)); p.drawPoint(QPointF(c, s * 0.3))
    elif name == "mic":
        p.drawRoundedRect(QRectF(s * 0.38, s * 0.12, s * 0.24, s * 0.4), s * 0.12, s * 0.12)
        p.drawArc(QRectF(s * 0.27, s * 0.28, s * 0.46, s * 0.38), 180 * 16, 180 * 16)
        p.drawLine(QPointF(c, s * 0.66), QPointF(c, s * 0.84)); p.drawLine(QPointF(s * 0.36, s * 0.84), QPointF(s * 0.64, s * 0.84))
    elif name == "send":
        path = QPainterPath(QPointF(s * 0.14, s * 0.2)); path.lineTo(s * 0.88, c); path.lineTo(s * 0.14, s * 0.8); path.lineTo(s * 0.3, c); path.closeSubpath()
        p.drawPath(path)
    elif name == "trash":
        p.drawLine(QPointF(s * 0.2, s * 0.28), QPointF(s * 0.8, s * 0.28)); p.drawRect(QRectF(s * 0.28, s * 0.3, s * 0.44, s * 0.52))
        p.drawLine(QPointF(s * 0.4, s * 0.18), QPointF(s * 0.6, s * 0.18))
    elif name == "play":
        path = QPainterPath(QPointF(s * 0.3, s * 0.2)); path.lineTo(s * 0.8, c); path.lineTo(s * 0.3, s * 0.8); path.closeSubpath()
        p.drawPath(path)


_cache: dict[tuple[str, str, int], QIcon] = {}


def icon(name: str, color: str = "#8aa0bd", size: int = 22) -> QIcon:
    key = (name, color, size)
    if key not in _cache:
        pm = QPixmap(size * 2, size * 2)
        pm.setDevicePixelRatio(2.0)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color), 1.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        p.setPen(pen)
        _draw(name, p, float(size))
        p.end()
        _cache[key] = QIcon(pm)
    return _cache[key]
