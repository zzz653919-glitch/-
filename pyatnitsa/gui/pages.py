"""Command History, Diagnostics va About sahifalari."""
from __future__ import annotations

import html
import threading
import time

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__, diagnostics, health
from ..settings import data_dir
from .icons import icon
from .theme import C

OUTCOME_COLORS = {"executed": C["ok"], "failed": C["err"], "blocked": C["warn"], "denied": C["warn"], "cancelled": C["muted"],
                  "clarify": C["blue"], "unknown": C["dim"], "answered": C["cyan"], "ai_failed": C["err"]}
OUTCOME_LABELS = {"executed": "Executed", "failed": "Failed", "blocked": "Blocked", "denied": "Disabled", "cancelled": "Cancelled",
                  "clarify": "Clarification", "unknown": "Not understood", "answered": "AI answered", "ai_failed": "AI error"}


def page_header(title: str, subtitle: str = "") -> QVBoxLayout:
    box = QVBoxLayout(); box.setSpacing(2)
    t = QLabel(title); t.setObjectName("pageTitle"); box.addWidget(t)
    if subtitle:
        s = QLabel(subtitle); s.setObjectName("sub"); s.setWordWrap(True); box.addWidget(s)
    return box


# ===================================================================== Command History
class HistoryPage(QWidget):
    reuse = Signal(str)            # matnni kiritish maydoniga qo'yish (avtomatik bajarilmaydi!)
    cleared = Signal()

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        top = QHBoxLayout(); top.addLayout(page_header("COMMAND HISTORY", "Every command you gave this session and what happened to it. History is kept in memory only."), 1)
        self.use = QPushButton("Use in input"); self.use.setIcon(icon("send", C["cyan"], 16)); self.use.setEnabled(False)
        self.use.setToolTip("Puts the selected command into the input field. It is not executed until you send it.")
        self.use.clicked.connect(self._reuse)
        self.clear_btn = QPushButton("Clear history"); self.clear_btn.setIcon(icon("trash", C["muted"], 16)); self.clear_btn.clicked.connect(self.clear)
        top.addWidget(self.use); top.addWidget(self.clear_btn); lay.addLayout(top)
        frame = QFrame(); frame.setObjectName("panel"); fl = QVBoxLayout(frame)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Time", "Source", "Command", "Intent", "Result"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.verticalHeader().hide(); self.table.setShowGrid(False)
        self.table.setWordWrap(True); self.table.setAlternatingRowColors(False)
        hh = self.table.horizontalHeader(); hh.setSectionResizeMode(2, QHeaderView.Stretch)
        for c in (0, 1, 3, 4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(lambda: self.use.setEnabled(bool(self.table.selectedItems())))
        self.empty = QLabel("No commands yet.\nCommands you speak or type will be listed here."); self.empty.setObjectName("empty"); self.empty.setAlignment(Qt.AlignCenter)
        fl.addWidget(self.table, 1); fl.addWidget(self.empty, 1)
        lay.addWidget(frame, 1)
        self._sync()

    def _sync(self) -> None:
        has = self.table.rowCount() > 0
        self.table.setVisible(has); self.empty.setVisible(not has); self.clear_btn.setEnabled(has)

    def add(self, e: dict) -> None:
        r = 0                       # eng yangisi tepada
        self.table.insertRow(r)
        out = e.get("outcome", "unknown")
        cells = [time.strftime("%H:%M:%S", time.localtime(e["time"])), "Voice" if e["source"] == "voice" else "Text", e["text"],
                 ", ".join(e.get("intents") or []) or "—", OUTCOME_LABELS.get(out, out)]
        for c, txt in enumerate(cells):
            it = QTableWidgetItem(txt)
            if c == 4:
                from PySide6.QtGui import QColor
                it.setForeground(QColor(OUTCOME_COLORS.get(out, C["muted"])))
                it.setToolTip(e.get("summary", ""))
            if c == 2:
                it.setData(Qt.UserRole, e["text"])
            self.table.setItem(r, c, it)
        self.table.resizeRowToContents(r)
        while self.table.rowCount() > 500:
            self.table.removeRow(self.table.rowCount() - 1)
        self._sync()

    def _reuse(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.reuse.emit(self.table.item(rows[0].row(), 2).data(Qt.UserRole))

    def clear(self) -> None:
        self.table.setRowCount(0); self._sync(); self.cleared.emit()

    def count(self) -> int:
        return self.table.rowCount()


# ===================================================================== Diagnostics
STATUS_COLORS = {"operational": C["ok"], "warning": C["warn"], "unavailable": C["dim"], "error": C["err"], "pending": "#34476b"}


class DiagnosticsPage(QWidget):
    _finished = Signal(object)

    def __init__(self, monitor: health.HealthMonitor, on_event=None):
        super().__init__()
        self.monitor, self.on_event = monitor, on_event or (lambda *a: None)
        self._running = False
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        top = QHBoxLayout(); top.addLayout(page_header("DIAGNOSTICS", "Real, read-only checks. A component is only marked healthy after its check has actually run."), 1)
        self.run_btn = QPushButton("Run diagnostics"); self.run_btn.setObjectName("primary"); self.run_btn.setIcon(icon("play", C["cyan"], 16))
        self.run_btn.clicked.connect(self.run); top.addWidget(self.run_btn, 0, Qt.AlignTop); lay.addLayout(top)
        self.summary = QLabel("Not run yet"); self.summary.setObjectName("sub"); lay.addWidget(self.summary)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        host = QWidget(); self._rows = QVBoxLayout(host); self._rows.setSpacing(8); self._rows.setContentsMargins(0, 0, 4, 0)
        scroll.setWidget(host); lay.addWidget(scroll, 1)
        self.empty = QLabel("No diagnostics have been run.\nPress “Run diagnostics” to check this computer."); self.empty.setObjectName("empty"); self.empty.setAlignment(Qt.AlignCenter)
        self._rows.addWidget(self.empty, 1)
        self._row_widgets: list[QFrame] = []
        self._finished.connect(self._show)
        self.last: list[diagnostics.Check] = []

    def run(self) -> None:
        if self._running:
            return
        self._running = True
        self.run_btn.setEnabled(False); self.run_btn.setText("Running…")
        self.summary.setText("Running checks in the background…")
        self.on_event("active", "SYSTEM", "Diagnostics started")

        def work():
            try:
                res = diagnostics.run_all(self.monitor)
            except Exception as e:  # noqa: BLE001
                res = [diagnostics.Check("run", "Diagnostics", "error", f"Diagnostics failed: {e}")]
            self._finished.emit(res)
        threading.Thread(target=work, daemon=True).start()

    def _show(self, checks: list[diagnostics.Check]) -> None:
        self._running = False
        self.run_btn.setEnabled(True); self.run_btn.setText("Run again")
        self.last = checks
        self.empty.hide()
        for w in self._row_widgets:
            w.setParent(None); w.deleteLater()
        self._row_widgets.clear()
        for c in checks:
            row = QFrame(); row.setObjectName("card"); h = QHBoxLayout(row); h.setContentsMargins(14, 10, 14, 10)
            dot = QLabel("●"); dot.setStyleSheet(f"color:{STATUS_COLORS[c.status]}; font-size:16px;"); h.addWidget(dot)
            col = QVBoxLayout(); col.setSpacing(1)
            t = QLabel(c.title); t.setStyleSheet("font-weight:700;"); col.addWidget(t)
            d = QLabel(html.escape(c.detail)); d.setObjectName("sub"); d.setWordWrap(True); col.addWidget(d)
            h.addLayout(col, 1)
            badge = QLabel(c.label.upper()); badge.setStyleSheet(f"color:{STATUS_COLORS[c.status]}; font-weight:700; letter-spacing:2px;")
            h.addWidget(badge)
            self._rows.insertWidget(self._rows.count() - 1 if False else len(self._row_widgets), row)
            self._row_widgets.append(row)
        s = diagnostics.summarize(checks)
        self.summary.setText(f"{s['operational']} operational · {s['warning']} warning · {s['unavailable']} unavailable · {s['error']} error"
                             f"   —   checked {time.strftime('%H:%M:%S')}")
        self.on_event("success" if not s["error"] else "error", "SYSTEM",
                      f"Diagnostics finished: {s['operational']} operational, {s['warning']} warning, {s['unavailable']} unavailable, {s['error']} error")


# ===================================================================== About
class AboutPage(QWidget):
    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        lay.addLayout(page_header("ABOUT"))
        frame = QFrame(); frame.setObjectName("panel"); fl = QVBoxLayout(frame); fl.setContentsMargins(22, 18, 22, 18); fl.setSpacing(8)
        name = QLabel(f"{APP_NAME}  <span style='color:{C['muted']};font-size:13px'>v{__version__}</span>"); name.setObjectName("pageTitle"); name.setTextFormat(Qt.RichText)
        fl.addWidget(name)
        body = QLabel(
            "<p>Voice and text computer assistant (Uzbek · Russian · English). It acts <b>only on commands you give</b>, and only from a fixed "
            "allowlist of safe actions.</p>"
            "<p><b>Keyboard</b><br>SPACE — start / stop listening (also on an empty input box) &nbsp;·&nbsp; Enter — confirm / send "
            "&nbsp;·&nbsp; Shift+Enter — new line &nbsp;·&nbsp; Esc — cancel</p>"
            "<p><b>Privacy</b><br>The microphone is open only between two SPACE presses (max 30 s). Speech is sent to Google Web Speech for "
            "recognition at that moment only. Live monitoring reads local system counters while this window is open and sends nothing anywhere. "
            "Command history is kept in memory only.</p>"
            f"<p><b>Data folder</b><br><span style='font-family:Consolas,monospace'>{html.escape(str(data_dir()))}</span> (settings, log, reports)</p>"
            "<p><b>Stack</b><br>Python · PySide6 · psutil · SpeechRecognition · sounddevice · edge-tts / pyttsx3</p>")
        body.setTextFormat(Qt.RichText); body.setWordWrap(True); body.setTextInteractionFlags(Qt.TextSelectableByMouse)
        fl.addWidget(body); fl.addStretch(1)
        lay.addWidget(frame, 1)
