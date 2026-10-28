"""Eslatma va vazifa dialoglari. Maydonlar tekshiriladi; noto'g'ri qiymat bilan «OK» o'chiq turadi va sababi ko'rsatiladi."""
from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateTimeEdit, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QSpinBox,
                               QVBoxLayout)

from ..reminders import Reminder
from ..tasks import Task

REPEATS = [("Once", "once"), ("Every N minutes", "interval"), ("Every day", "daily"), ("Every week", "weekly"), ("Every month", "monthly"), ("Weekdays (Mon–Fri)", "weekdays")]


def _qdt(dt: datetime) -> QDateTime:
    return QDateTime(dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)


def _py(q: QDateTime) -> datetime:
    d, t = q.date(), q.time()
    return datetime(d.year(), d.month(), d.day(), t.hour(), t.minute())


class ReminderDialog(QDialog):
    def __init__(self, parent=None, reminder: Reminder | None = None, now: datetime | None = None):
        super().__init__(parent)
        self.now = (now or datetime.now()).replace(second=0, microsecond=0)
        self.setWindowTitle("Edit reminder" if reminder else "New reminder"); self.setMinimumWidth(420)
        form = QFormLayout()
        self.title = QLineEdit(reminder.title if reminder else ""); self.title.setPlaceholderText("What should I remind you about?"); self.title.setMaxLength(200)
        self.when = QDateTimeEdit(_qdt(reminder.due_dt if reminder else self.now + timedelta(hours=1))); self.when.setCalendarPopup(True); self.when.setDisplayFormat("dd.MM.yyyy HH:mm")
        self.repeat = QComboBox(); [self.repeat.addItem(n, v) for n, v in REPEATS]
        self.every = QSpinBox(); self.every.setRange(1, 1440); self.every.setValue(30); self.every.setSuffix(" min")
        if reminder and reminder.recur:
            self.repeat.setCurrentIndex(max(0, self.repeat.findData(reminder.recur["type"])))
            if reminder.recur["type"] == "interval":
                self.every.setValue(min(1440, reminder.recur.get("n", 30)))
        form.addRow("Title", self.title); form.addRow("Date and time", self.when); form.addRow("Repeat", self.repeat); form.addRow("Interval", self.every)
        self.err = QLabel(""); self.err.setStyleSheet("color:#ff4d6d;"); self.err.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addLayout(form); lay.addWidget(self.err); lay.addWidget(self.buttons)
        for w in (self.title, self.when, self.repeat, self.every):
            sig = getattr(w, "textChanged", None) or getattr(w, "dateTimeChanged", None) or getattr(w, "currentIndexChanged", None)
            sig.connect(self._validate)
        self.repeat.currentIndexChanged.connect(self._validate)
        self._validate()

    def _validate(self, *_a) -> None:
        self.every.setVisible(self.repeat.currentData() == "interval")
        problem = ""
        if not self.title.text().strip():
            problem = "Enter a title."
        elif self.repeat.currentData() == "once" and _py(self.when.dateTime()) <= self.now:
            problem = "This time is in the past. Choose a future time (nothing is scheduled silently)."
        self.err.setText(problem)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(not problem)

    def values(self) -> dict:
        kind = self.repeat.currentData()
        recur = None if kind == "once" else {"type": kind, "n": self.every.value() if kind == "interval" else 1}
        return {"title": self.title.text().strip(), "due": _py(self.when.dateTime()), "recur": recur}


class TaskDialog(QDialog):
    def __init__(self, parent=None, task: Task | None = None, categories: list[str] | None = None, now: datetime | None = None):
        super().__init__(parent)
        self.now = (now or datetime.now()).replace(second=0, microsecond=0)
        self.setWindowTitle("Edit task" if task else "New task"); self.setMinimumWidth(460)
        form = QFormLayout()
        self.title = QLineEdit(task.title if task else ""); self.title.setPlaceholderText("Task title"); self.title.setMaxLength(200)
        self.desc = QPlainTextEdit(task.description if task else ""); self.desc.setFixedHeight(80); self.desc.setPlaceholderText("Description (optional)")
        self.has_due = QCheckBox("Set a due date"); self.has_due.setChecked(bool(task and task.due))
        self.with_time = QCheckBox("Include a time"); self.with_time.setChecked(bool(task and task.due and len(task.due) > 10))
        base = task.due_dt() if task and task.due else self.now + timedelta(days=1)
        self.due = QDateTimeEdit(_qdt(base)); self.due.setCalendarPopup(True)
        self.priority = QComboBox(); [self.priority.addItem(n, v) for n, v in (("Low", "low"), ("Medium", "medium"), ("High", "high"))]
        self.priority.setCurrentIndex(self.priority.findData(task.priority if task else "medium"))
        self.status = QComboBox(); [self.status.addItem(n, v) for n, v in (("To Do", "todo"), ("In Progress", "doing"), ("Completed", "done"))]
        self.status.setCurrentIndex(self.status.findData(task.status if task else "todo"))
        self.category = QComboBox(); self.category.setEditable(True); self.category.addItem("")
        for c in categories or []:
            self.category.addItem(c)
        self.category.setCurrentText(task.category if task else "")
        form.addRow("Title", self.title); form.addRow("Description", self.desc); form.addRow("", self.has_due); form.addRow("", self.with_time); form.addRow("Due", self.due)
        form.addRow("Priority", self.priority); form.addRow("Status", self.status); form.addRow("Category", self.category)
        self.err = QLabel(""); self.err.setStyleSheet("color:#ff4d6d;")
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept); self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addLayout(form); lay.addWidget(self.err); lay.addWidget(self.buttons)
        self.title.textChanged.connect(self._sync); self.has_due.toggled.connect(self._sync); self.with_time.toggled.connect(self._sync)
        self._sync()

    def _sync(self, *_a) -> None:
        self.due.setEnabled(self.has_due.isChecked()); self.with_time.setEnabled(self.has_due.isChecked())
        self.due.setDisplayFormat("dd.MM.yyyy HH:mm" if self.with_time.isChecked() else "dd.MM.yyyy")
        ok = bool(self.title.text().strip())
        self.err.setText("" if ok else "Enter a title.")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(ok)

    def values(self) -> dict:
        due = None
        if self.has_due.isChecked():
            dt = _py(self.due.dateTime())
            due = dt if self.with_time.isChecked() else dt.date()
        return {"title": self.title.text().strip(), "description": self.desc.toPlainText().strip(), "due": due, "priority": self.priority.currentData(),
                "status": self.status.currentData(), "category": self.category.currentText().strip()}
