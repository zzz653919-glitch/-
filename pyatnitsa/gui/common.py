"""Sahifalar uchun umumiy yordamchilar: jadval yasash, tasdiq so'rash (testlarda almashtiriladi), bo'sh holat, sana formatlari."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QFrame, QHeaderView, QLabel, QMessageBox, QTableWidget, QVBoxLayout, QWidget

from .theme import C


def ask(parent, title: str, text: str, yes: str = "Yes") -> bool:
    """Xavfli/qaytarib bo'lmaydigan amallardan oldin aniq tasdiq (standart javob — «No»). Testlar shu funksiyani almashtiradi."""
    box = QMessageBox(QMessageBox.Question, title, text, QMessageBox.NoButton, parent)
    y = box.addButton(yes, QMessageBox.AcceptRole)
    n = box.addButton("Cancel", QMessageBox.RejectRole)
    box.setDefaultButton(n)
    box.exec()
    return box.clickedButton() is y


def info(parent, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


def make_table(headers: list[str], stretch: tuple[int, ...] = (0,), multi: bool = False) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection if multi else QAbstractItemView.SingleSelection)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.verticalHeader().hide(); t.setShowGrid(False); t.setWordWrap(True)
    hh = t.horizontalHeader()
    for c in range(len(headers)):
        hh.setSectionResizeMode(c, QHeaderView.Stretch if c in stretch else QHeaderView.ResizeToContents)
    return t


def empty_label(text: str) -> QLabel:
    lb = QLabel(text); lb.setObjectName("empty"); lb.setAlignment(Qt.AlignCenter); lb.setWordWrap(True)
    return lb


def panel(title: str = "") -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setObjectName("panel")
    lay = QVBoxLayout(f); lay.setContentsMargins(16, 12, 16, 12); lay.setSpacing(8)
    if title:
        t = QLabel(title); t.setObjectName("section"); lay.addWidget(t)
    return f, lay


def selected_data(table: QTableWidget, col: int = 0) -> str:
    sm = table.selectionModel()
    rows = sm.selectedRows() if sm else []
    if not rows:
        return ""
    it = table.item(rows[0].row(), col)
    return (it.data(Qt.UserRole) or "") if it else ""


def status_style(label: QLabel, text: str, level: str = "neutral") -> None:
    col = {"ok": C["ok"], "warn": C["warn"], "err": C["err"]}.get(level, C["muted"])
    label.setStyleSheet(f"color:{col};")
    label.setText(text)


def human_when(dt: datetime, now: datetime) -> str:
    d = dt.date() - now.date()
    day = {0: "Today", 1: "Tomorrow", -1: "Yesterday"}.get(d.days, dt.strftime("%d.%m.%Y"))
    return f"{day} {dt:%H:%M}"


def clear_layout(lay) -> None:
    while lay.count():
        item = lay.takeAt(0)
        w = item.widget()
        if w is not None:
            w.setParent(None); w.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


class Page(QWidget):
    """Ma'lumot sahifalari uchun asos: `refresh()` — ma'lumotlarni qayta o'qish; `watches` — qaysi o'zgarishlarda yangilanadi."""
    watches: tuple[str, ...] = ()

    def refresh(self) -> None:  # pragma: no cover - tegishli sahifada aniqlanadi
        pass
