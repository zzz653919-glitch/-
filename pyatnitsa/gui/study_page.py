"""English Study Planner: kunlik reja (tahrirlanadi), faqat HAQIQATAN belgilangan faoliyat yoziladi; kunlik/haftalik progress, streak, tarix, qiyin so'z/grammatika,
ixtiyoriy eslatmalar. Bu tashkil etish vositasi: kurs yoki lug'at tizimining o'rnini bosmaydi; natija yoki IELTS bahosi va'da qilinmaydi."""
from __future__ import annotations

from datetime import timedelta

from PySide6.QtCore import QRectF, Qt, QTime, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton,
                               QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QTimeEdit, QVBoxLayout, QWidget)

from ..study import Activity
from . import common
from .common import Page, clear_layout, empty_label, make_table, panel, selected_data, status_style
from .icons import icon
from .pages import page_header
from .theme import C

DAILY_KEY, REVIEW_KEY = "study-daily", "study-review"
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class WeekBars(QWidget):
    """Haftalik yozilgan daqiqalar (haqiqiy yozuvlar). Reja chizig'i — kunlik reja daqiqasi."""

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(96)
        self.data: list[tuple] = []
        self.planned = 0

    def set_data(self, data, planned: int) -> None:
        self.data, self.planned = list(data), planned
        self.setToolTip(" · ".join(f"{DAY_NAMES[d.weekday()]} {m} min" for d, m in self.data))
        self.update()

    def paintEvent(self, _e) -> None:
        if not self.data:
            return
        p = QPainter(self)
        w, h = self.width(), self.height()
        top = max([m for _d, m in self.data] + [self.planned, 1])
        slot = w / 7
        for i, (d, m) in enumerate(self.data):
            bh = int((h - 28) * m / top)
            x = i * slot + slot * 0.2
            p.fillRect(QRectF(x, h - 18 - bh, slot * 0.6, max(bh, 1 if m else 0)), QColor(C["cyan"] if m else "#1a2a47"))
            p.setPen(QColor(C["muted"])); p.drawText(QRectF(i * slot, h - 16, slot, 16), Qt.AlignCenter, DAY_NAMES[d.weekday()])
            if m:
                p.setPen(QColor(C["text"])); p.drawText(QRectF(i * slot, h - 32 - bh, slot, 14), Qt.AlignCenter, str(m))
        if self.planned:
            y = h - 18 - int((h - 28) * self.planned / top)
            pen = QPen(QColor(C["warn"]), 1, Qt.DashLine); p.setPen(pen); p.drawLine(0, y, w, y)


class PlanDialog(QDialog):
    def __init__(self, parent, plan: list[Activity]):
        super().__init__(parent)
        self.setWindowTitle("Edit study plan"); self.setMinimumSize(520, 360)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Activity", "Minutes", "Category"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 220)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._ids: list[str] = []
        self.total = QLabel(); self.err = QLabel(); self.err.setStyleSheet("color:#ff4d6d;"); self.err.setWordWrap(True)
        for a in plan:
            self._add_row(a)
        self.add_btn = QPushButton("Add activity"); self.rm_btn = QPushButton("Remove selected"); self.reset_btn = QPushButton("Restore default (60 min)")
        row = QHBoxLayout(); [row.addWidget(b) for b in (self.add_btn, self.rm_btn, self.reset_btn)]; row.addStretch(1); row.addWidget(self.total)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._accept); self.buttons.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addWidget(QLabel("Change names, minutes and categories, add your own activities, or remove ones you do not need.")); lay.addWidget(self.table, 1)
        lay.addLayout(row); lay.addWidget(self.err); lay.addWidget(self.buttons)
        self.add_btn.clicked.connect(lambda: self._add_row(Activity("", "New activity", 10, "")))
        self.rm_btn.clicked.connect(self._remove)
        self.reset_btn.clicked.connect(self._reset)
        self.table.itemChanged.connect(lambda _i: self._total())
        self._total()

    def _add_row(self, a: Activity) -> None:
        self.table.blockSignals(True)
        r = self.table.rowCount(); self.table.insertRow(r)
        it = QTableWidgetItem(a.name); it.setData(Qt.UserRole, a.id)
        self.table.setItem(r, 0, it); self.table.setItem(r, 1, QTableWidgetItem(str(a.minutes))); self.table.setItem(r, 2, QTableWidgetItem(a.category))
        self.table.blockSignals(False)
        self._total()

    def _remove(self) -> None:
        for r in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(r)
        self._total()

    def _reset(self) -> None:
        from ..study import DEFAULT_PLAN
        self.table.setRowCount(0)
        for aid, name, mins, cat in DEFAULT_PLAN:
            self._add_row(Activity(aid, name, mins, cat))

    def _read(self) -> list[Activity]:
        out = []
        for r in range(self.table.rowCount()):
            name = (self.table.item(r, 0).text() if self.table.item(r, 0) else "").strip()
            mins_t = (self.table.item(r, 1).text() if self.table.item(r, 1) else "").strip()
            if not name:
                raise ValueError(f"Row {r + 1}: enter an activity name.")
            if not mins_t.isdigit() or not 1 <= int(mins_t) <= 600:
                raise ValueError(f"Row {r + 1}: minutes must be a number from 1 to 600.")
            out.append(Activity(self.table.item(r, 0).data(Qt.UserRole) or "", name, int(mins_t), (self.table.item(r, 2).text() if self.table.item(r, 2) else "").strip()))
        if not out:
            raise ValueError("The plan needs at least one activity.")
        if len(out) > 12:
            raise ValueError("At most 12 activities.")
        return out

    def _total(self) -> None:
        try:
            self.total.setText(f"Total: {sum(a.minutes for a in self._read())} min/day"); self.err.setText("")
        except ValueError as e:
            self.total.setText("Total: —"); self.err.setText(str(e))

    def _accept(self) -> None:
        try:
            self.activities = self._read()
        except ValueError as e:
            self.err.setText(str(e))
            return
        self.accept()


class StudyPage(Page):
    changed = Signal(str)
    watches = ("study", "reminders")

    def __init__(self, ex):
        super().__init__()
        self.ex = ex
        self._loading = False
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        top = QHBoxLayout(); top.addLayout(page_header("ENGLISH STUDY PLANNER", "Organize your daily English study. Only activities you tick are recorded — nothing is counted automatically, and no score or timeline is promised."), 1)
        self.plan_btn = QPushButton("Edit plan…"); self.plan_btn.setIcon(icon("study", C["cyan"], 16)); top.addWidget(self.plan_btn, 0, Qt.AlignTop)
        lay.addLayout(top)
        # ---- xulosa
        sbox, sl = panel("TODAY & THIS WEEK")
        row = QHBoxLayout()
        self.today_lbl = QLabel(); self.today_lbl.setObjectName("big")
        self.streak_lbl = QLabel(); self.streak_lbl.setObjectName("sub")
        self.week_lbl = QLabel(); self.week_lbl.setObjectName("sub")
        left = QVBoxLayout(); left.addWidget(self.today_lbl); left.addWidget(self.streak_lbl); left.addWidget(self.week_lbl)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setTextVisible(False); left.addWidget(self.bar)
        self.bars = WeekBars()
        row.addLayout(left, 1); row.addWidget(self.bars, 1)
        sl.addLayout(row)
        lay.addWidget(sbox)
        # ---- bugungi ro'yxat
        cbox, cl = panel("TODAY'S CHECKLIST")
        self.check_host = QVBoxLayout(); self.check_host.setSpacing(6)
        cl.addLayout(self.check_host)
        self.note = QLabel("Tick an activity only after you have really done it. Adjust the minutes if you studied for a different time. Unticking removes your record."); self.note.setObjectName("dim"); self.note.setWordWrap(True)
        self.msg = QLabel(); self.msg.setObjectName("sub"); self.msg.setWordWrap(True); self.msg.setTextFormat(Qt.PlainText)
        cl.addWidget(self.note); cl.addWidget(self.msg)
        lay.addWidget(cbox)
        # ---- yorliqlar
        self.tabs = QTabWidget()
        self.hist = make_table(["Date", "Activity", "Minutes", "Note"], stretch=(1, 3)); self.hist_empty = empty_label("No study sessions recorded yet.\nTick an activity above after you finish it.")
        hw = QWidget(); hl = QVBoxLayout(hw); hl.addWidget(self.hist); hl.addWidget(self.hist_empty)
        iw = QWidget(); il = QVBoxLayout(iw)
        ar = QHBoxLayout()
        self.kind = QComboBox(); self.kind.addItem("Difficult word", "word"); self.kind.addItem("Grammar topic", "grammar")
        self.item_text = QLineEdit(); self.item_text.setPlaceholderText("Word or grammar topic"); self.item_text.setMaxLength(120)
        self.item_note = QLineEdit(); self.item_note.setPlaceholderText("Meaning / note (optional)"); self.item_note.setMaxLength(300)
        self.item_add = QPushButton("Add"); self.item_add.setObjectName("primary")
        for w, st in ((self.kind, 0), (self.item_text, 2), (self.item_note, 3), (self.item_add, 0)):
            ar.addWidget(w, st)
        self.items = make_table(["Type", "Word / topic", "Note", "Reviews", "Last review"], stretch=(1, 2)); self.items_empty = empty_label("Nothing recorded here yet.")
        br = QHBoxLayout(); self.review_btn = QPushButton("I reviewed this"); self.item_del = QPushButton("Delete")
        self.items_hint = QLabel("“Reviews” counts how many times you practiced an item — it does not mean the item is learned."); self.items_hint.setObjectName("dim"); self.items_hint.setWordWrap(True)
        br.addWidget(self.items_hint, 1); br.addWidget(self.review_btn); br.addWidget(self.item_del)
        il.addLayout(ar); il.addWidget(self.items, 1); il.addWidget(self.items_empty, 1); il.addLayout(br)
        rw = QWidget(); rl = QVBoxLayout(rw)
        self.daily_chk = QCheckBox("Daily study reminder"); self.daily_time = QTimeEdit(QTime(19, 0)); self.daily_time.setDisplayFormat("HH:mm")
        self.review_chk = QCheckBox("Daily review reminder for difficult words"); self.review_time = QTimeEdit(QTime(20, 0)); self.review_time.setDisplayFormat("HH:mm")
        r1 = QHBoxLayout(); r1.addWidget(self.daily_chk, 1); r1.addWidget(self.daily_time)
        r2 = QHBoxLayout(); r2.addWidget(self.review_chk, 1); r2.addWidget(self.review_time)
        self.rem_note = QLabel("Reminders are normal repeating reminders (see the Reminders page). Turning a switch off removes only that reminder."); self.rem_note.setObjectName("dim"); self.rem_note.setWordWrap(True)
        self.rem_msg = QLabel(); self.rem_msg.setObjectName("sub"); self.rem_msg.setWordWrap(True)
        rl.addLayout(r1); rl.addLayout(r2); rl.addWidget(self.rem_note); rl.addWidget(self.rem_msg); rl.addStretch(1)
        self.tabs.addTab(hw, "History"); self.tabs.addTab(iw, "Difficult words & grammar"); self.tabs.addTab(rw, "Reminders")
        lay.addWidget(self.tabs, 1)

        self.plan_btn.clicked.connect(self.edit_plan)
        self.item_add.clicked.connect(self.add_item); self.item_text.returnPressed.connect(self.add_item)
        self.review_btn.clicked.connect(self.review_item); self.item_del.clicked.connect(self.delete_item)
        self.items.itemSelectionChanged.connect(self._sync_items)
        self.daily_chk.toggled.connect(lambda _on: self._apply_reminder(DAILY_KEY))
        self.daily_time.timeChanged.connect(lambda _t: self.daily_chk.isChecked() and self._apply_reminder(DAILY_KEY))
        self.review_chk.toggled.connect(lambda _on: self._apply_reminder(REVIEW_KEY))
        self.review_time.timeChanged.connect(lambda _t: self.review_chk.isChecked() and self._apply_reminder(REVIEW_KEY))
        self.refresh()

    # ---- ko'rinish
    def refresh(self) -> None:
        self._loading = True
        st, now = self.ex.study, self.ex.now()
        today = now.date()
        plan, done = st.plan(), st.done_ids(today)
        rec, planned = st.minutes_on(today), st.planned_minutes()
        cur, best = st.streak(today)
        week = st.week_minutes(today)
        self.today_lbl.setText(f"{rec} / {planned} min recorded today")
        self.streak_lbl.setText(f"Study streak: {cur} day{'s' if cur != 1 else ''} (best: {best}) — counts only days with a recorded activity")
        self.week_lbl.setText(f"This week: {sum(m for _d, m in week)} min on {sum(1 for _d, m in week if m)} day(s) · Activities today: {len(done & {a.id for a in plan})}/{len(plan)}")
        self.bar.setValue(min(100, int(100 * rec / planned)) if planned else 0)
        self.bars.set_data(week, planned)
        clear_layout(self.check_host)
        self.rows: dict[str, tuple[QCheckBox, QSpinBox]] = {}
        logged = {h.activity_id: h for h in st.history(400) if h.day == today.strftime("%Y-%m-%d")}
        for a in plan:
            r = QHBoxLayout()
            chk = QCheckBox(f"{a.name}"); chk.setChecked(a.id in done)
            spin = QSpinBox(); spin.setRange(1, 600); spin.setSuffix(" min"); spin.setValue(logged[a.id].minutes if a.id in logged else a.minutes); spin.setEnabled(a.id not in done)
            hint = QLabel(f"planned {a.minutes} min" + (f" · {a.category}" if a.category else "")); hint.setObjectName("dim")
            chk.toggled.connect(lambda on, aid=a.id, sp=spin: self._toggle(aid, on, sp.value()))
            r.addWidget(chk, 1); r.addWidget(hint); r.addWidget(spin)
            w = QWidget(); w.setLayout(r); self.check_host.addWidget(w)
            self.rows[a.id] = (chk, spin)
        # tarix
        hist = st.history(100)
        self.hist.setRowCount(0)
        for h in hist:
            row = self.hist.rowCount(); self.hist.insertRow(row)
            for c, txt in enumerate((h.day, h.activity_name, str(h.minutes), h.note or "—")):
                self.hist.setItem(row, c, QTableWidgetItem(txt))
        self.hist.setVisible(bool(hist)); self.hist_empty.setVisible(not hist)
        self._fill_items()
        # eslatmalar holati
        for key, chk, tm in ((DAILY_KEY, self.daily_chk, self.daily_time), (REVIEW_KEY, self.review_chk, self.review_time)):
            r = self.ex.reminders.by_source(key)
            chk.setChecked(bool(r))
            if r:
                tm.setTime(QTime(r.due_dt.hour, r.due_dt.minute))
        self._loading = False

    def _toggle(self, aid: str, on: bool, minutes: int) -> None:
        if self._loading:
            return
        try:
            if on:
                e, created = self.ex.study.record(aid, minutes=minutes)
                status_style(self.msg, f"Recorded: {e.activity_name} — {e.minutes} min." if created else "Already recorded for today.", "ok" if created else "warn")
            else:
                self.ex.study.unrecord(aid)
                status_style(self.msg, "Record removed.", "neutral")
        except ValueError as e:
            status_style(self.msg, f"Could not record: {e}", "err")
        self.refresh()
        self.changed.emit("study")

    def edit_plan(self) -> None:
        dlg = PlanDialog(self, self.ex.study.plan())
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            self.ex.study.set_plan(dlg.activities)
        except ValueError as e:
            status_style(self.msg, f"Plan not saved: {e}", "err")
            return
        status_style(self.msg, f"Plan saved: {self.ex.study.planned_minutes()} min/day. Earlier records are kept.", "ok")
        self.refresh()
        self.changed.emit("study")

    # ---- qiyin so'zlar va grammatika
    def _fill_items(self) -> None:
        its = self.ex.study.items()
        self.items.setRowCount(0)
        for i in its:
            row = self.items.rowCount(); self.items.insertRow(row)
            cells = ["Word" if i.kind == "word" else "Grammar", i.text, i.note or "—", str(i.reviews), (i.last_review.replace("T", " ")[:16] or "—")]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                if c == 1:
                    it.setData(Qt.UserRole, i.id)
                self.items.setItem(row, c, it)
        self.items.setVisible(bool(its)); self.items_empty.setVisible(not its)
        self._sync_items()

    def _sync_items(self) -> None:
        sel = bool(selected_data(self.items, 1))
        self.review_btn.setEnabled(sel); self.item_del.setEnabled(sel)

    def add_item(self) -> None:
        text = self.item_text.text().strip()
        if not text:
            status_style(self.msg, "Type the word or grammar topic first.", "warn")
            return
        it, created = self.ex.study.add_item(self.kind.currentData(), text, self.item_note.text().strip())
        self.item_text.clear(); self.item_note.clear()
        status_style(self.msg, "Added to your list." if created else "Already in your list.", "ok" if created else "warn")
        self._fill_items()
        self.changed.emit("study")

    def review_item(self) -> None:
        iid = selected_data(self.items, 1)
        if iid:
            self.ex.study.mark_reviewed(iid)
            self._fill_items()
            self.changed.emit("study")

    def delete_item(self) -> None:
        iid = selected_data(self.items, 1)
        if not iid:
            return
        if not common.ask(self, "Delete item", "Remove this item from your difficult words / grammar list?", yes="Delete"):
            return
        self.ex.study.delete_item(iid)
        self._fill_items()
        self.changed.emit("study")

    # ---- ixtiyoriy eslatmalar (oddiy takrorlanuvchi eslatma sifatida, takrorlanmaydi)
    def _apply_reminder(self, key: str) -> None:
        if self._loading:
            return
        chk, tm, text = ((self.daily_chk, self.daily_time, "English study time: open today's plan") if key == DAILY_KEY
                         else (self.review_chk, self.review_time, "Review your difficult words"))
        self.ex.reminders.delete_by_source(key)
        if chk.isChecked():
            now = self.ex.now()
            due = now.replace(hour=tm.time().hour(), minute=tm.time().minute(), second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=1)
            self.ex.reminders.add_unique(text, due, {"type": "daily", "n": 1}, source_key=key)
            status_style(self.rem_msg, f"Reminder set: every day at {due:%H:%M}.", "ok")
        else:
            status_style(self.rem_msg, "Reminder removed.", "neutral")
        self.changed.emit("reminders")
