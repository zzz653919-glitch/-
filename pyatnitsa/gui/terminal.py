"""Buyruq terminali: faqat ilovaning HAQIQIY hodisalari (controller.log). Bezak yozuvlar yo'q."""
from __future__ import annotations

import html
import time

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout

from .icons import icon
from .theme import LEVEL_COLORS


class TerminalPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 8, 12, 10); lay.setSpacing(6)
        head = QHBoxLayout()
        t = QLabel("COMMAND TERMINAL"); t.setObjectName("section"); head.addWidget(t); head.addStretch(1)
        self.count = QLabel("0 events"); self.count.setObjectName("dim"); head.addWidget(self.count)
        clr = QPushButton("Clear"); clr.setObjectName("ghost"); clr.setIcon(icon("trash", "#8aa0bd", 16)); clr.clicked.connect(self.clear)
        head.addWidget(clr); lay.addLayout(head)
        self.view = QPlainTextEdit(); self.view.setObjectName("terminal"); self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(500); self.view.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        lay.addWidget(self.view, 1)
        self._n = 0
        self._show_empty()

    def _show_empty(self) -> None:
        self.view.setPlaceholderText("No activity yet. Events appear here as the assistant works.")

    def add(self, level: str, line: str) -> None:
        color = LEVEL_COLORS.get(level, LEVEL_COLORS["info"])
        stamp = time.strftime("%H:%M:%S")
        tag, _, rest = line.partition("] ")
        self.view.appendHtml(
            f"<span style='color:#46597a'>{stamp}</span> <span style='color:{color};font-weight:bold'>{html.escape(tag)}]</span> "
            f"<span style='color:{color}'>{html.escape(rest)}</span>")
        self._n += 1
        self.count.setText(f"{self._n} event{'s' if self._n != 1 else ''}")

    def clear(self) -> None:
        self.view.clear()
        self._n = 0
        self.count.setText("0 events")
