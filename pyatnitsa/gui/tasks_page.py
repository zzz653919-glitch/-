"""Tasks: sarlavha, tavsif, muddat, ustuvorlik, holat, kategoriya; qidirish, filtr, kunlik/haftalik ko'rinish, progress; o'chirish tasdiq bilan."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QTableWidgetItem, QVBoxLayout

from . import common
from .common import Page, empty_label, make_table, panel, selected_data, status_style
from .dialogs import TaskDialog
from .icons import icon
from .pages import page_header
from .theme import C

VIEWS = [("Active", "active"), ("Today", "today"), ("This week", "week"), ("Overdue", "overdue"), ("Completed", "done"), ("All", "all")]
PRI = {"low": "Low", "medium": "Medium", "high": "High"}
ST = {"todo": "To Do", "doing": "In Progress", "done": "Completed"}
PRI_COLOR = {"low": "#8aa0bd", "medium": "#ffb020", "high": "#ff4d6d"}


class TasksPage(Page):
    changed = Signal(str)
    watches = ("tasks",)

    def __init__(self, ex):
        super().__init__()
        self.ex = ex
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        top = QHBoxLayout(); top.addLayout(page_header("TASKS", "Your to-do list with priorities, due dates and progress. Everything stays on this computer."), 1)
        self.add_btn = QPushButton("New task"); self.add_btn.setObjectName("primary"); self.add_btn.setIcon(icon("tasks", C["cyan"], 16)); top.addWidget(self.add_btn, 0, Qt.AlignTop)
        lay.addLayout(top)
        box, bl = panel()
        f = QHBoxLayout(); f.setSpacing(8)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search tasks…"); self.search.setClearButtonEnabled(True)
        self.view = QComboBox(); [self.view.addItem(n, v) for n, v in VIEWS]
        self.category = QComboBox(); self.priority = QComboBox()
        self.priority.addItem("Any priority", ""); [self.priority.addItem(n, v) for v, n in PRI.items()]
        for w, label in ((self.search, None), (self.view, "View"), (self.category, None), (self.priority, None)):
            if label:
                f.addWidget(QLabel(label))
            f.addWidget(w, 1 if w is self.search else 0)
        bl.addLayout(f)
        pr = QHBoxLayout()
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setTextVisible(False)
        self.progress = QLabel(); self.progress.setObjectName("sub")
        pr.addWidget(self.bar, 1); pr.addWidget(self.progress)
        bl.addLayout(pr)
        self.table = make_table(["Task", "Priority", "Status", "Due", "Category"], stretch=(0,))
        self.empty = empty_label("")
        bl.addWidget(self.table, 1); bl.addWidget(self.empty, 1)
        row = QHBoxLayout()
        self.edit_btn = QPushButton("Edit"); self.doing_btn = QPushButton("Start (In Progress)"); self.done_btn = QPushButton("Complete"); self.reopen_btn = QPushButton("Reopen"); self.del_btn = QPushButton("Delete")
        self.done_btn.setObjectName("primary")
        self.msg = QLabel(); self.msg.setObjectName("sub"); self.msg.setWordWrap(True); self.msg.setTextFormat(Qt.PlainText)
        row.addWidget(self.msg, 1)
        for b in (self.edit_btn, self.doing_btn, self.done_btn, self.reopen_btn, self.del_btn):
            row.addWidget(b)
        bl.addLayout(row)
        lay.addWidget(box, 1)
        self.add_btn.clicked.connect(self.create); self.edit_btn.clicked.connect(self.edit); self.del_btn.clicked.connect(self.delete)
        self.done_btn.clicked.connect(lambda: self._set("done")); self.doing_btn.clicked.connect(lambda: self._set("doing")); self.reopen_btn.clicked.connect(lambda: self._set("todo"))
        self.search.textChanged.connect(lambda _t: self.refresh())
        for w in (self.view, self.category, self.priority):
            w.currentIndexChanged.connect(lambda _i: self.refresh())
        self.table.itemSelectionChanged.connect(self._sync_buttons); self.table.itemDoubleClicked.connect(lambda _i: self.edit())
        self.refresh()

    def _tasks(self):
        v = self.view.currentData()
        return self.ex.tasks.search(self.search.text(), "done" if v == "done" else "", self.category.currentData() or "", self.priority.currentData() or "",
                                    "all" if v == "done" else v, self.ex.now())

    def refresh(self) -> None:
        now, keep = self.ex.now(), selected_data(self.table)
        cats = self.ex.tasks.categories()
        self.category.blockSignals(True)
        cur = self.category.currentData()
        self.category.clear(); self.category.addItem("Any category", "")
        for c in cats:
            self.category.addItem(c, c)
        self.category.setCurrentIndex(max(0, self.category.findData(cur)))
        self.category.blockSignals(False)
        items = self._tasks()
        self.table.setRowCount(0)
        for t in items:
            row = self.table.rowCount(); self.table.insertRow(row)
            over = t.overdue(now)
            cells = [t.title, PRI[t.priority], ST[t.status], (t.due.replace("T", " ") if t.due else "—") + ("  (overdue)" if over else ""), t.category or "—"]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                it.setToolTip(t.description or t.title)
                if c == 0:
                    it.setData(Qt.UserRole, t.id)
                    if t.status == "done":
                        f = it.font(); f.setStrikeOut(True); it.setFont(f)
                if c == 1:
                    it.setForeground(QColor(PRI_COLOR[t.priority]))
                if c == 3 and over:
                    it.setForeground(QColor(C["err"]))
                self.table.setItem(row, c, it)
            if t.id == keep:
                self.table.selectRow(row)
        done, total = self.ex.tasks.progress(items)
        self.bar.setValue(int(100 * done / total) if total else 0)
        self.progress.setText(f"{done} / {total} completed" + (f" ({100 * done // total}%)" if total else ""))
        has = bool(items)
        self.table.setVisible(has); self.empty.setVisible(not has)
        self.empty.setText("No tasks match.\nPress “New task”, or say: “Add a task to finish my homework”." if not self.ex.tasks.all() else "No tasks match the current filters.")
        self._sync_buttons()

    def _selected(self):
        tid = selected_data(self.table)
        return self.ex.tasks.get(tid) if tid else None

    def _sync_buttons(self) -> None:
        t = self._selected()
        self.edit_btn.setEnabled(bool(t)); self.del_btn.setEnabled(bool(t))
        self.done_btn.setEnabled(bool(t) and t.status != "done"); self.doing_btn.setEnabled(bool(t) and t.status == "todo"); self.reopen_btn.setEnabled(bool(t) and t.status == "done")

    def _notify(self, text: str, level: str = "ok") -> None:
        status_style(self.msg, text, level)
        self.changed.emit("tasks")

    def create(self) -> None:
        dlg = TaskDialog(self, None, self.ex.tasks.categories(), self.ex.now())
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        t, created = self.ex.tasks.add_unique(v["title"], v["description"], v["due"], v["priority"], v["status"], v["category"])
        self._notify("Task added." if created else "An identical open task already exists — nothing was added twice.", "ok" if created else "warn")

    def edit(self) -> None:
        t = self._selected()
        if t is None:
            return
        dlg = TaskDialog(self, t, self.ex.tasks.categories(), self.ex.now())
        if dlg.exec() != QDialog.Accepted:
            return
        v = dlg.values()
        self.ex.tasks.update(t.id, **v)
        self._notify("Task updated.")

    def _set(self, status: str) -> None:
        t = self._selected()
        if t is None:
            return
        self.ex.tasks.set_status(t.id, status)
        self._notify({"done": "Task completed.", "doing": "Task marked as in progress.", "todo": "Task reopened."}[status])

    def delete(self) -> None:
        t = self._selected()
        if t is None:
            return
        if not common.ask(self, "Delete task", f"Permanently delete this task?\n\n“{t.title}”\n\nThis cannot be undone.", yes="Delete"):
            return
        self.ex.tasks.delete(t.id)
        self._notify("Task deleted.")
