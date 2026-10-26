"""Markaziy animatsiyali AI Core. Holat va mikrofon darajasi ilovaning HAQIQIY holatidan keladi (controller.core_state())."""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen, QRadialGradient
from PySide6.QtWidgets import QWidget

from .theme import STATE_COLORS

# tezlik, yorug'lik, to'lqin amplitudasi, pulsatsiya chastotasi (Gs)
PARAMS = {
    "standby": (0.30, 0.35, 0.015, 0.25), "listening": (0.75, 0.80, 0.05, 0.9), "processing": (2.4, 0.65, 0.03, 2.0), "interpreting": (3.0, 0.70, 0.035, 2.6),
    "confirm": (0.45, 0.55, 0.02, 0.6), "executing": (1.7, 0.85, 0.05, 1.6), "responding": (0.9, 0.75, 0.04, 1.1), "error": (0.5, 0.60, 0.02, 0.4),
}


def _lerp(a: float, b: float, k: float) -> float:
    return a + (b - a) * k


class AICore(QWidget):
    def __init__(self, parent=None, reduced: bool = False):
        super().__init__(parent)
        self.setMinimumSize(150, 150)
        self.state = "standby"
        self.reduced = reduced
        self._level = 0.0           # silliqlangan mikrofon darajasi (haqiqiy)
        self._target_level = 0.0
        self._t = 0.0               # animatsiya vaqti
        self._spin = 0.0            # burchak (tezlik bilan o'sadi)
        self._cur = QColor(STATE_COLORS["standby"])
        self._speed, self._glow, self._amp, self._hz = PARAMS["standby"]
        rnd = random.Random(7)      # ambient zarrachalar: faqat bezak, hech qanday ma'lumot ifodalamaydi
        self._particles = [(rnd.uniform(0.28, 0.98), rnd.uniform(-0.9, 0.9) or 0.3, rnd.uniform(0, math.tau), rnd.uniform(0.8, 2.2)) for _ in range(30)]
        self._timer = QTimer(self, interval=33)
        self._timer.timeout.connect(self._tick)

    # ---- tashqi boshqaruv
    def set_state(self, state: str) -> None:
        if state in PARAMS and state != self.state:
            self.state = state
            if self.reduced:
                self._snap()
                self.update()

    def set_level(self, v: float) -> None:
        self._target_level = max(0.0, min(1.0, v))
        if self.reduced and self.state == "listening":
            self._level = self._target_level
            self.update()

    def set_reduced(self, reduced: bool) -> None:
        self.reduced = reduced
        if reduced:
            self._timer.stop(); self._snap(); self.update()
        elif self.isVisible():
            self._timer.start()

    def _snap(self) -> None:
        self._cur = QColor(STATE_COLORS[self.state])
        self._speed, self._glow, self._amp, self._hz = PARAMS[self.state]

    def showEvent(self, e):
        if not self.reduced:
            self._timer.start()
        else:
            self._snap()

    def hideEvent(self, e):
        self._timer.stop()

    # ---- animatsiya
    def _tick(self) -> None:
        dt = 0.033
        sp, gl, am, hz = PARAMS[self.state]
        k = 0.10                                          # holatlar orasida silliq o'tish
        self._speed, self._glow, self._amp, self._hz = _lerp(self._speed, sp, k), _lerp(self._glow, gl, k), _lerp(self._amp, am, k), _lerp(self._hz, hz, k)
        tgt = QColor(STATE_COLORS[self.state])
        self._cur = QColor(int(_lerp(self._cur.red(), tgt.red(), k)), int(_lerp(self._cur.green(), tgt.green(), k)), int(_lerp(self._cur.blue(), tgt.blue(), k)))
        self._t += dt
        self._spin += dt * self._speed
        self._level = _lerp(self._level, self._target_level if self.state == "listening" else 0.0, 0.3)
        if self.state != "listening":
            self._target_level *= 0.7
        self.update()

    def _color(self, alpha: int, base: QColor | None = None) -> QColor:
        c = QColor(base or self._cur)
        c.setAlpha(max(0, min(255, alpha)))
        return c

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        R = min(w, h) / 2 * 0.94
        c = QPointF(cx, cy)
        t, spin = self._t, self._spin
        pulse = 0.5 + 0.5 * math.sin(math.tau * self._hz * t) if not self.reduced else 0.5
        lvl = self._level
        flicker = (0.82 + 0.18 * math.sin(t * 5.0)) if self.state == "error" and not self.reduced else 1.0

        # 1) fon nuri
        g = QRadialGradient(c, R)
        g.setColorAt(0.25, self._color(int(120 * self._glow * flicker + 60 * lvl)))
        g.setColorAt(1.0, self._color(0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(c, R, R)

        # 2) tashqi nuqtali halqa
        p.save(); p.translate(c); p.rotate(math.degrees(spin * 0.5))
        pen = QPen(self._color(int(110 * flicker)), 1.2, Qt.CustomDashLine); pen.setDashPattern([2, 7])
        p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawEllipse(QPointF(0, 0), R * 0.97, R * 0.97)
        p.restore()

        # 3) shkala (teskari yo'nalishda aylanadi)
        p.save(); p.translate(c); p.rotate(-math.degrees(spin * 0.8))
        for i in range(72):
            long = i % 6 == 0
            p.setPen(QPen(self._color(int((150 if long else 70) * flicker)), 1.4 if long else 1))
            p.drawLine(QPointF(R * (0.86 if long else 0.89), 0), QPointF(R * 0.93, 0))
            p.rotate(5)
        p.restore()

        # 4) aylanuvchi yoy segmentlari; PROCESSING'da tez, EXECUTING'da kengayib-torayadi
        arcs = 3
        span_base = 60 if self.state != "executing" else 40 + 40 * (0.5 + 0.5 * math.sin(t * 3))
        rect = QRectF(cx - R * 0.8, cy - R * 0.8, R * 1.6, R * 1.6)
        for i in range(arcs):
            start = -math.degrees(spin * (1.2 + i * 0.35)) * (1 if i % 2 == 0 else -1) + i * (360 / arcs)
            p.setPen(QPen(self._color(int((210 - i * 45) * flicker), None), 3 - i * 0.6, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(rect, int(start * 16), int(span_base * 16))
        if self.state == "processing" and not self.reduced:
            p.setPen(QPen(self._color(255, QColor("#ffffff")), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawArc(QRectF(cx - R * 0.72, cy - R * 0.72, R * 1.44, R * 1.44), int(-math.degrees(t * 7) * 16), 30 * 16)

        # 5) energiya to'lqini (listening'da haqiqiy mikrofon darajasiga bog'liq)
        amp = R * (self._amp + 0.20 * lvl) * (0.7 + 0.6 * pulse if self.state in ("responding", "executing") else 1.0)
        base = R * 0.60
        path = QPainterPath()
        n = 140
        for k in range(n + 1):
            th = k / n * math.tau
            r = base + amp * math.sin(6 * th + t * 2.2) + amp * 0.5 * math.sin(11 * th - t * 3.1)
            pt = QPointF(cx + r * math.cos(th), cy + r * math.sin(th))
            path.moveTo(pt) if k == 0 else path.lineTo(pt)
        p.setPen(QPen(self._color(int(230 * flicker)), 1.8)); p.setBrush(Qt.NoBrush); p.drawPath(path)

        # 6) aylanuvchi geometriya
        for sides, rad, direction, alpha in ((6, 0.46, 1, 150), (3, 0.30, -1, 170)):
            p.save(); p.translate(c); p.rotate(direction * math.degrees(spin * 0.9))
            poly = QPainterPath()
            for k in range(sides + 1):
                th = k / sides * math.tau
                pt = QPointF(R * rad * math.cos(th), R * rad * math.sin(th))
                poly.moveTo(pt) if k == 0 else poly.lineTo(pt)
            p.setPen(QPen(self._color(int(alpha * flicker)), 1.3)); p.drawPath(poly)
            p.restore()

        # 7) tinglash pulsi: haqiqiy daraja bilan kengayuvchi halqalar
        if self.state == "listening":
            for k in range(3):
                f = ((t * 0.7 + k / 3) % 1.0) if not self.reduced else k / 3
                p.setPen(QPen(self._color(int((1 - f) * (90 + 140 * lvl))), 2))
                p.drawEllipse(c, R * (0.22 + 0.75 * f), R * (0.22 + 0.75 * f))

        # 8) zarrachalar
        if not self.reduced:
            p.setPen(Qt.NoPen)
            for rf, om, ph, sz in self._particles:
                a = ph + t * om * (0.2 + self._speed * 0.5)
                rr = R * rf * (1 + 0.03 * math.sin(t + ph))
                pt = QPointF(cx + rr * math.cos(a), cy + rr * math.sin(a) * 0.98)
                p.setBrush(self._color(int(45 * self._glow)));  p.drawEllipse(pt, sz * 2.4, sz * 2.4)
                p.setBrush(self._color(int(200 * self._glow))); p.drawEllipse(pt, sz * 0.8, sz * 0.8)

        # 9) yadro
        cr = R * (0.15 + 0.03 * pulse + 0.05 * lvl)
        cg = QRadialGradient(c, cr * 2.2)
        cg.setColorAt(0, QColor(255, 255, 255, int(235 * flicker)))
        cg.setColorAt(0.35, self._color(int(220 * flicker)))
        cg.setColorAt(1, self._color(0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(cg)); p.drawEllipse(c, cr * 2.2, cr * 2.2)
