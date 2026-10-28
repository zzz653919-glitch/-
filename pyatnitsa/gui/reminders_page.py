"""Reminders: yaratish, tahrirlash, kechiktirish, bajarildi, o'chirish (tasdiq bilan); kechikkan va yaqinlashayotganlar. SQLite'da saqlanadi."""
from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QMenu, QPushButton, QTableWidgetItem, QVBoxLayout

from ..reminders import describe_recur
from . import common
from .common import Page, empty_label, make_table, panel, selected_data, status_style
from .dialogs import ReminderDialog
from .icons import icon
from .pages import page_header
from .theme import C

FILTERS = [("Upcoming", "upcoming"), ("Overdue", "overdue"), ("Today", "today"), ("Completed", "done"), ("All", "all")]


class RemindersPage(Page):
    changed = Signal(str)
    watches = ("reminders",)

    def __init__(self, ex):
        super().__init__()
        self.ex = ex
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        top = QHBoxLayout(); top.addLayout(page_header("REMINDERS", "One-time and repeating reminders, saved on this computer. Desktop notifications appear while Пятница is running."), 1)
        self.add_btn = QPushButton("New reminder"); self.add_btn.setObjectName("primary"); self.add_btn.setIcon(icon("reminders", C["cyan"], 16)); top.addWidget(self.add_btn, 0, Qt.AlignTop)
        lay.addLayout(top)
        box, bl = panel()
        row = QHBoxLayout()
        self.view = QComboBox(); [self.view.addItem(n, v) for n, v in FILTERS]
        self.summary = QLabel(); self.summary.setObjectName("sub")
        row.addWidget(QLabel("Show:")); row.addWidget(self.view); row.addWidget(self.summary, 1)
        self.edit_btn = QPushButton("Edit"); self.post_btn = QPushButton("Postpone"); self.done_btn = QPushButton("Complete"); self.del_btn = QPushButton("Delete")
        menu = QMenu(self.post_btn)
        for label, fn in (("In 10 minutes", lambda: self.postpone(minutes=10)), ("In 1 hour", lambda: self.postpone(minutes=60)), ("Tomorrow, same time", lambda: self.postpone(days=1)),
                          ("Next week, same time", lambda: self.postpone(days=7))):
            menu.addAction(label, fn)
        self.post_btn.setMenu(menu)
        self.done_btn.setObjectName("primary")
        for b in (self.edit_btn, self.post_btn, self.done_btn, self.del_btn):
            row.addWidget(b)
        bl.addLayout(row)
        self.table = make_table(["When", "Reminder", "Repeat", "Status"], stretch=(1,))
        self.empty = empty_label("")
        bl.addWidget(self.table, 1); bl.addWidget(self.empty, 1)
        self.msg = QLabel(); self.msg.setObjectName("sub"); self.msg.setWordWrap(True); self.msg.setTextFormat(Qt.PlainText); bl.addWidget(self.msg)
        lay.addWidget(box, 1)
        self.add_btn.clicked.connect(self.create); self.edit_btn.clicked.connect(self.edit); self.done_btn.clicked.connect(self.complete); self.del_btn.clicked.connect(self.delete)
        self.view.currentIndexChanged.connect(lambda _i: self.refresh())
        self.table.itemSelectionChanged.connect(self._sync_buttons); self.table.itemDoubleClicked.connect(lambda _i: self.edit())
        self.refresh()

    # ---- ko'rinish
    def _items(self):
        st, now = self.ex.reminders, self.ex.now()
        return {"upcoming": lambda: st.upcoming(now, 200), "overdue": lambda: st.overdue(now), "today": lambda: st.today(now),
                "done": lambda: [r for r in st.all() if r.done], "all": st.all}[self.view.currentData()]()

    def refresh(self) -> None:
        now, keep = self.ex.now(), selected_data(self.table)
        items = self._items()
        self.table.setRowCount(0)
        for r in items:
            row = self.table.rowCount(); self.table.insertRow(row)
            overdue = not r.done and r.due_dt < now
            status = "Completed" if r.done else "Overdue" if overdue else "Upcoming"
            cells = [common.human_when(r.due_dt, now), r.title, describe_recur(r.recur, "en"), status]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                if c == 0:
                    it.setData(Qt.UserRole, r.id)
                if c == 3:
                    it.setForeground(QColor(C["err"] if overdue else C["muted"] if r.done else C["ok"]))
                self.table.setItem(row, c, it)
            if r.id == keep:
                self.table.selectRow(row)
        n_over = len(self.ex.reminders.overdue(now))
        self.summary.setText(f"{len(items)} shown · {n_over} overdue" if n_over else f"{len(items)} shown")
        has = bool(items)
        self.table.setVisible(has); self.empty.setVisible(not has)
        self.empty.setText({"upcoming": "No upcoming reminders.\nPress “New reminder”, or say: “Remind me tomorrow at 9 AM to …”.", "overdue": "Nothing is overdue.",
                            "today": "No reminders for today.", "done": "No completed reminders.", "all": "No reminders yet."}[self.view.currentData()])
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        sel = bool(selected_data(self.table))
        for b in (self.edit_btn, self.post_btn, self.done_btn, self.del_btn):
            b.setEnabled(sel)

    def _notify(self, text: str, level: str = "ok") -> None:
        status_style(self.msg, text, level)
        self.changed.emit("reminders")

    # ---- amallar
    def create(self) -> None:
        dlg = ReminderDialog(self, None, self.ex.now())
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        r, created = self.ex.reminders.add_unique(v["title"], v["due"], v["recur"])
        self._notify("Reminder saved." if created else "An identical reminder already exists — nothing was added twice.", "ok" if created else "warn")

    def edit(self) -> None:
        rid = selected_data(self.table)
        r = self.ex.reminders.get(rid) if rid else None
        if r is None:
            return
        dlg = ReminderDialog(self, r, self.ex.now())
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        self.ex.reminders.update(rid, title=v["title"], due=v["due"], recur=v["recur"])
        self._notify("Reminder updated.")

    def complete(self) -> None:
        rid = selected_data(self.table)
        if not rid:
            return
        r = self.ex.reminders.complete(rid)
        self._notify("Completed — next occurrence scheduled." if r and r.recur else "Marked as completed.")

    def postpone(self, minutes: int = 0, days: int = 0) -> None:
        rid = selected_data(self.table)
        r = self.ex.reminders.get(rid) if rid else None
        if r is None:
            return
        if days:
            target = max(r.due_dt, self.ex.now()) + timedelta(days=days)
        else:
            target = (self.ex.now() + timedelta(minutes=minutes)).replace(second=0, microsecond=0)
        self.ex.reminders.postpone(rid, to=target)
        self._notify(f"Postponed to {target:%d.%m.%Y %H:%M}.")

    def delete(self) -> None:
        rid = selected_data(self.table)
        r = self.ex.reminders.get(rid) if rid else None
        if r is None:
            return
        if not common.ask(self, "Delete reminder", f"Permanently delete this reminder?\n\n“{r.title}” — {r.due_dt:%d.%m.%Y %H:%M}", yes="Delete"):
            return
        self.ex.reminders.delete(rid)
        self._notify("Reminder deleted.")
