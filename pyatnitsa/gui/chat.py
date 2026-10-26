"""Suhbat oynasi: foydalanuvchi va yordamchi xabarlari alohida pufakchalarda, vaqt belgisi bilan."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .theme import soft_wrap

MAX_BUBBLES = 300


class _Bubble(QFrame):
    def __init__(self, role: str, text: str, ts: float):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 9); lay.setSpacing(3)
        stamp = time.strftime("%H:%M:%S", time.localtime(ts))
        if role == "system":
            self.setStyleSheet("background: transparent; border: none;")
            body = QLabel(f"ⓘ  {soft_wrap(text)}  ·  {stamp}")
            body.setObjectName("bubbleSys"); body.setAlignment(Qt.AlignCenter)
            lay.addWidget(body)
        else:
            self.setObjectName("bubbleUser" if role == "user" else "bubbleAI")
            head = QLabel(("YOU" if role == "user" else "ПЯТНИЦА") + f"  ·  {stamp}")
            head.setObjectName("bubbleHead")
            body = QLabel(soft_wrap(text))
            lay.addWidget(head); lay.addWidget(body)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.role = role
        self._body, self._head = body, (None if role == "system" else head)

    def fit(self, max_w: int) -> None:
        """Pufakcha kengligi: matn kengligi (ko'pi bilan max_w); uzun matn o'ralib, balandlikka o'sadi."""
        if self.role == "system":
            return
        inner = max_w - 26
        fm = self._body.fontMetrics()
        text_w = fm.boundingRect(0, 0, inner, 100000, Qt.TextWordWrap, self._body.text()).width()
        head_w = self._head.fontMetrics().horizontalAdvance(self._head.text())
        self.setFixedWidth(min(max_w, max(text_w, head_w, 120) + 30))


class ChatView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._host = QWidget()
        self._lay = QVBoxLayout(self._host)
        self._lay.setContentsMargins(6, 6, 6, 6); self._lay.setSpacing(8)
        self._lay.addStretch(1)
        self.setWidget(self._host)
        self._empty = QLabel("No conversation yet.\nPress SPACE to speak, or type a command below.")
        self._empty.setObjectName("empty"); self._empty.setAlignment(Qt.AlignCenter)
        self._lay.insertWidget(0, self._empty, 1)
        self._bubbles: list[_Bubble] = []

    def add(self, role: str, text: str, ts: float | None = None) -> None:
        self._empty.hide()
        b = _Bubble(role, text, ts or time.time())
        row = QWidget(); from PySide6.QtWidgets import QHBoxLayout
        h = QHBoxLayout(row); h.setContentsMargins(0, 0, 0, 0)
        if role == "user":
            h.addStretch(1); h.addWidget(b, 0)
        elif role == "assistant":
            h.addWidget(b, 0); h.addStretch(1)
        else:
            h.addWidget(b, 1)
        row.bubble = b  # type: ignore[attr-defined]
        self._lay.insertWidget(self._lay.count() - 1, row)
        self._bubbles.append(row)  # type: ignore[arg-type]
        while len(self._bubbles) > MAX_BUBBLES:
            old = self._bubbles.pop(0)
            old.setParent(None); old.deleteLater()
        self._limit_width()
        QTimer.singleShot(0, self._to_bottom)

    def clear(self) -> None:
        for row in self._bubbles:
            row.setParent(None); row.deleteLater()
        self._bubbles.clear()
        self._empty.show()

    def count(self) -> int:
        return len(self._bubbles)

    def _to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _limit_width(self) -> None:
        w = int(max(220, self.viewport().width()) * 0.82)
        for row in self._bubbles:
            row.bubble.fit(w)  # type: ignore[attr-defined]

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._limit_width()
