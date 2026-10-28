"""Home Dashboard: bugungi sana, eslatmalar, vazifalar, kechikkanlar, tezkor qaydlar, ingliz tili rejasi va progress.
Vazifa, eslatma va o'quv faoliyatini shu yerdan bajarilgan deb belgilash mumkin. Hamma ma'lumot haqiqiy ombordan olinadi."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QProgressBar, QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .common import Page, empty_label, panel, status_style
from .dialogs import ReminderDialog, TaskDialog
from .icons import icon
from .theme import C


class _Card(QWidget):
    """Sarlavhali, ro'yxatli va bo'sh holat yozuvli kartochka."""

    def __init__(self, title: str, empty: str, checkable: bool = True):
        super().__init__()
        self.frame, lay = panel(title)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(self.frame)
        self.list = QListWidget(); self.list.setMinimumHeight(110); self.list.setMaximumHeight(190)
        self.empty = empty_label(empty); self.empty.setMinimumHeight(60)
        lay.addWidget(self.list); lay.addWidget(self.empty)
        self.lay = lay

    def fill(self, rows: list[tuple[str, str, bool, str]], checkable: bool = True) -> None:
        """rows: (matn, id, belgilangan_mi, tooltip)."""
        self.list.blockSignals(True)
        self.list.clear()
        for text, rid, checked, tip in rows:
            it = QListWidgetItem(text)
            it.setData(Qt.UserRole, rid); it.setToolTip(tip or text)
            if checkable:
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked if checked else Qt.Unchecked)
            self.list.addItem(it)
        self.list.blockSignals(False)
        self.list.setVisible(bool(rows)); self.empty.setVisible(not rows)


class DashboardPage(Page):
    changed = Signal(str)
    openPage = Signal(str)
    openNote = Signal(str)
    watches = ("reminders", "tasks", "notes", "study")

    def __init__(self, ex):
        super().__init__()
        self.ex = ex
        self._loading = False
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        host = QWidget(); scroll.setWidget(host)
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(scroll)
        v = QVBoxLayout(host); v.setContentsMargins(0, 0, 6, 0); v.setSpacing(12)
        head = QHBoxLayout()
        t = QVBoxLayout(); t.setSpacing(2)
        self.date_lbl = QLabel(); self.date_lbl.setObjectName("pageTitle")
        self.sub_lbl = QLabel(); self.sub_lbl.setObjectName("sub"); self.sub_lbl.setWordWrap(True)
        t.addWidget(self.date_lbl); t.addWidget(self.sub_lbl)
        head.addLayout(t, 1)
        self.rem_btn = QPushButton("New reminder"); self.task_btn = QPushButton("New task"); self.note_btn = QPushButton("New note")
        for b, ic in ((self.rem_btn, "reminders"), (self.task_btn, "tasks"), (self.note_btn, "notes")):
            b.setObjectName("primary"); b.setIcon(icon(ic, C["cyan"], 16)); head.addWidget(b, 0, Qt.AlignTop)
        v.addLayout(head)
        self.msg = QLabel(); self.msg.setObjectName("sub"); self.msg.setWordWrap(True); self.msg.setTextFormat(Qt.PlainText); v.addWidget(self.msg)
        self.grid = QGridLayout(); self.grid.setSpacing(12)
        self.c_rem = _Card("TODAY'S REMINDERS", "No reminders for today.\nTick one to mark it completed.")
        self.c_tasks = _Card("TODAY'S TASKS", "No tasks due today.")
        self.c_over = _Card("OVERDUE TASKS", "Nothing is overdue.")
        self.c_notes = _Card("QUICK NOTES", "No notes yet.")
        self.c_study = _Card("ENGLISH STUDY PLAN", "")
        self.prog = QProgressBar(); self.prog.setRange(0, 100); self.prog.setTextVisible(False)
        self.prog_lbl = QLabel(); self.prog_lbl.setObjectName("sub"); self.prog_lbl.setWordWrap(True)
        self.open_study = QPushButton("Open study planner")
        self.c_study.lay.addWidget(self.prog); self.c_study.lay.addWidget(self.prog_lbl); self.c_study.lay.addWidget(self.open_study)
        self.quick = QLineEdit(); self.quick.setPlaceholderText("Quick note… (Enter to save)"); self.quick.setMaxLength(300)
        self.quick_btn = QPushButton("Save note")
        qr = QHBoxLayout(); qr.addWidget(self.quick, 1); qr.addWidget(self.quick_btn)
        self.c_notes.lay.addLayout(qr)
        self.cards = [self.c_rem, self.c_tasks, self.c_over, self.c_notes, self.c_study]
        v.addLayout(self.grid)
        v.addStretch(1)
        self._cols = 0
        self._layout_cards(2)

        self.rem_btn.clicked.connect(self.new_reminder); self.task_btn.clicked.connect(self.new_task); self.note_btn.clicked.connect(lambda: self.openPage.emit("notes:new"))
        self.c_rem.list.itemChanged.connect(self._rem_toggled); self.c_tasks.list.itemChanged.connect(self._task_toggled); self.c_over.list.itemChanged.connect(self._task_toggled)
        self.c_study.list.itemChanged.connect(self._study_toggled)
        self.c_notes.list.itemDoubleClicked.connect(lambda it: self.openNote.emit(it.data(Qt.UserRole)))
        self.quick.returnPressed.connect(self.quick_note); self.quick_btn.clicked.connect(self.quick_note)
        self.open_study.clicked.connect(lambda: self.openPage.emit("study"))
        self.refresh()

    # ---- maket: keng oynada 2 ustun, tor oynada 1 ustun
    def _layout_cards(self, cols: int) -> None:
        if cols == self._cols:
            return
        self._cols = cols
        while self.grid.count():
            self.grid.takeAt(0)
        for i, c in enumerate(self.cards):
            self.grid.addWidget(c, i // cols, i % cols)
        for c in range(cols):
            self.grid.setColumnStretch(c, 1)

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._layout_cards(2 if self.width() >= 760 else 1)

    # ---- ma'lumot
    def refresh(self) -> None:
        self._loading = True
        ex, now = self.ex, self.ex.now()
        self.date_lbl.setText(now.strftime("%A, %d %B %Y"))
        rems = list({r.id: r for r in ex.reminders.overdue(now) + [r for r in ex.reminders.today(now) if r.due_dt >= now]}.values())
        today_tasks = [t for t in ex.tasks.view("today", now) if t.status != "done"]
        done_today = len([t for t in ex.tasks.view("today", now) if t.status == "done"])
        over = ex.tasks.view("overdue", now)
        self.sub_lbl.setText(f"{len(rems)} reminder(s) · {len(today_tasks)} task(s) due today · {len(over)} overdue task(s)")
        self.c_rem.fill([(f"{r.due_dt:%H:%M}  {r.title}" + ("   [OVERDUE]" if r.due_dt < now else "") + ("  ↻" if r.recur else ""), r.id, False, r.due) for r in rems])
        self.c_tasks.fill([(f"[{t.priority.upper()[0]}] {t.title}" + (f"   ({t.due[11:]})" if len(t.due) > 10 else ""), t.id, False, t.description) for t in today_tasks])
        self.c_tasks.frame.layout().itemAt(0).widget().setText(f"TODAY'S TASKS  ·  {done_today} done")
        self.c_over.fill([(f"{t.title}   (due {t.due.replace('T', ' ')})", t.id, False, t.description) for t in over])
        notes = ex.notes.all()[:4]
        self.c_notes.fill([(n.title + (f" — {' '.join(n.body.split())[:50]}" if n.body else ""), n.id, False, n.title) for n in notes], checkable=False)
        self.c_notes.empty.setText("No notes yet. Write one below.")
        # ingliz tili
        st = ex.study
        plan, done = st.plan(), st.done_ids(now.date())
        self.c_study.fill([(f"{a.name} — {a.minutes} min", a.id, a.id in done, a.category) for a in plan])
        rec, planned = st.minutes_on(now.date()), st.planned_minutes()
        cur, best = st.streak(now.date())
        self.prog.setValue(min(100, int(100 * rec / planned)) if planned else 0)
        self.prog_lbl.setText(f"{rec}/{planned} min recorded today · streak {cur} day(s) (best {best}). Only ticked activities count.")
        self._loading = False

    # ---- bajarildi deb belgilash
    def _rem_toggled(self, it: QListWidgetItem) -> None:
        if self._loading or it.checkState() != Qt.Checked:
            return
        r = self.ex.reminders.complete(it.data(Qt.UserRole))
        status_style(self.msg, f"Reminder completed: {r.title}" if r else "Reminder not found.", "ok" if r else "err")
        self.refresh(); self.changed.emit("reminders")

    def _task_toggled(self, it: QListWidgetItem) -> None:
        if self._loading or it.checkState() != Qt.Checked:
            return
        t = self.ex.tasks.complete(it.data(Qt.UserRole))
        status_style(self.msg, f"Task completed: {t.title}" if t else "Task not found.", "ok" if t else "err")
        self.refresh(); self.changed.emit("tasks")

    def _study_toggled(self, it: QListWidgetItem) -> None:
        if self._loading:
            return
        aid = it.data(Qt.UserRole)
        try:
            if it.checkState() == Qt.Checked:
                e, created = self.ex.study.record(aid)
                status_style(self.msg, f"Recorded: {e.activity_name} — {e.minutes} min." if created else "Already recorded.", "ok" if created else "warn")
            else:
                self.ex.study.unrecord(aid)
                status_style(self.msg, "Record removed.", "neutral")
        except ValueError as e:
            status_style(self.msg, f"Could not record: {e}", "err")
        self.refresh(); self.changed.emit("study")

    # ---- yaratish
    def new_reminder(self) -> None:
        dlg = ReminderDialog(self, None, self.ex.now())
        if dlg.exec() != dlg.Accepted:
            return
        v = dlg.values()
        _r, created = self.ex.reminders.add_unique(v["title"], v["due"], v["recur"])
        status_style(self.msg, "Reminder saved." if created else "That reminder already exists.", "ok" if created else "warn")
        self.refresh(); self.changed.emit("reminders")

    def new_task(self) -> None:
        dlg = TaskDialog(self, None, self.ex.tasks.categories(), self.ex.now())
        if dlg.exec() != dlg.Accepted:
            return
        v = dlg.values()
        _t, created = self.ex.tasks.add_unique(v["title"], v["description"], v["due"], v["priority"], v["status"], v["category"])
        status_style(self.msg, "Task added." if created else "That task already exists.", "ok" if created else "warn")
        self.refresh(); self.changed.emit("tasks")

    def quick_note(self) -> None:
        text = self.quick.text().strip()
        if not text:
            return
        n, old = self.ex.notes.add_auto(" ".join(text.split()[:6])[:60], text)
        self.quick.clear()
        status_style(self.msg, f"Note saved: {n.title}" if not old else f"A note “{old}” already exists — it was not overwritten. Saved as “{n.title}”.", "ok" if not old else "warn")
        self.refresh(); self.changed.emit("notes")
