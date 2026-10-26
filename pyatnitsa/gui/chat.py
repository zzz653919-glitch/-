"""Suhbat oynasi: foydalanuvchi va yordamchi xabarlari alohida pufakchalarda, vaqt belgisi bilan."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from .theme import soft_wrap

MAX_BUBBLES = 300


class _Bubble(QFrame):
    def __init__(self, role: str, text: str, ts: float, error: bool = False, on_retry=None):
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
            self.setObjectName("bubbleUser" if role == "user" else ("bubbleErr" if error else "bubbleAI"))
            head = QLabel(("YOU" if role == "user" else "ПЯТНИЦА" + ("  ·  ERROR" if error else "")) + f"  ·  {stamp}")
            head.setObjectName("bubbleHead")
            body = QLabel(soft_wrap(text))
            lay.addWidget(head); lay.addWidget(body)
            self.retry_btn = None
            if error and on_retry:
                from PySide6.QtWidgets import QPushButton
                self.retry_btn = QPushButton("Retry"); self.retry_btn.setObjectName("primary"); self.retry_btn.setFocusPolicy(Qt.NoFocus)
                self.retry_btn.clicked.connect(on_retry); lay.addWidget(self.retry_btn, 0, Qt.AlignLeft)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        body.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)
        self.role = role
        self._body, self._head = body, (None if role == "system" else head)

    def set_text(self, text: str) -> None:
        self._body.setText(soft_wrap(text))

    def disable_retry(self) -> None:
        if getattr(self, "retry_btn", None):
            self.retry_btn.setEnabled(False); self.retry_btn.hide()

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
        self._stick = True                                   # pastda bo'lsa — yangi xabar bilan birga pastga aylanadi; foydalanuvchi yuqoriga chiqsa — majburlanmaydi
        bar = self.verticalScrollBar()
        bar.rangeChanged.connect(lambda _lo, hi: self._stick and bar.setValue(hi))
        bar.valueChanged.connect(lambda v: setattr(self, "_stick", v >= bar.maximum() - 6))

    def add(self, role: str, text: str, ts: float | None = None, error: bool = False, on_retry=None) -> "_Bubble":
        self._empty.hide()
        b = _Bubble(role, text, ts or time.time(), error, on_retry)
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
        if role == "user":
            self._stick = True
        QTimer.singleShot(0, lambda: self._stick and self._to_bottom())
        return b

    # ---- oqimli (streaming) javob
    def stream_start(self) -> None:
        self._stream_text = ""
        self._stream = self.add("assistant", "…")

    def stream_delta(self, chunk: str) -> None:
        if getattr(self, "_stream", None) is None:
            self.stream_start()
        self._stream_text += chunk
        self._stream.set_text(self._stream_text)
        self._stream.fit(int(max(220, self.viewport().width()) * 0.82))
        self._to_bottom()

    def stream_end(self, final: str | None = None, suffix: str = "") -> None:
        if getattr(self, "_stream", None) is not None:
            self._stream.set_text((final if final is not None else self._stream_text) + suffix)
            self._stream.fit(int(max(220, self.viewport().width()) * 0.82))
            self._stream = None
            QTimer.singleShot(0, self._to_bottom)

    def stream_text(self) -> str:
        return getattr(self, "_stream_text", "") if getattr(self, "_stream", None) is not None else ""

    def stream_discard(self) -> None:
        """Hali matn kelmagan bo'sh javob pufakchasini olib tashlaydi."""
        b = getattr(self, "_stream", None)
        if b is not None:
            for row in list(self._bubbles):
                if row.bubble is b:  # type: ignore[attr-defined]
                    self._bubbles.remove(row); row.setParent(None); row.deleteLater()
            self._stream = None

    def has_stream(self) -> bool:
        return getattr(self, "_stream", None) is not None

    # ---- «Thinking…» ko'rsatkichi
    def thinking_on(self, text: str = "Thinking", animate: bool = True) -> None:
        self.thinking_off()
        self._think_base, self._think_n, self._animate = text, 0, animate
        self._think = self.add("system", f"{text}…")
        if animate:
            self._think_timer = QTimer(self, interval=420)
            self._think_timer.timeout.connect(self._think_tick)
            self._think_timer.start()

    def _think_tick(self) -> None:
        self._think_n = (self._think_n + 1) % 4
        if getattr(self, "_think", None) is not None:
            self._think.set_text(f"{self._think_base}{'.' * self._think_n}")

    def thinking_off(self) -> None:
        t = getattr(self, "_think_timer", None)
        if t:
            t.stop(); t.deleteLater(); self._think_timer = None
        b = getattr(self, "_think", None)
        if b is not None:
            for row in list(self._bubbles):
                if row.bubble is b:  # type: ignore[attr-defined]
                    self._bubbles.remove(row); row.setParent(None); row.deleteLater()
            self._think = None

    def disable_retries(self) -> None:
        for row in self._bubbles:
            row.bubble.disable_retry()  # type: ignore[attr-defined]

    def clear(self) -> None:
        self.thinking_off()
        self._stream = None
        for row in self._bubbles:
            row.setParent(None); row.deleteLater()
        self._bubbles.clear()
        self._empty.show()

    def count(self) -> int:
        return len(self._bubbles)

    def _to_bottom(self) -> None:
        bar = self.verticalScrollBar()
        self._stick = True
        bar.setValue(bar.maximum())

    def _limit_width(self) -> None:
        w = int(max(220, self.viewport().width()) * 0.82)
        for row in self._bubbles:
            row.bubble.fit(w)  # type: ignore[attr-defined]

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._limit_width()
