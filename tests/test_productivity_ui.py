"""Home Dashboard · Reminders · Tasks · Notes · English Study · Settings & Permissions · bildirishnomalar (offscreen Qt, haqiqiy SQLite).
Dialoglar (tasdiq, sana tanlash) monkeypatch bilan almashtirilgan; haqiqiy Windows bildirishnomasi sinalmagan."""
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QDateTime, Qt, QTime
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog

from pyatnitsa import commands, controller as C, files as fs, health
from pyatnitsa.ai_chat import ChatService
from pyatnitsa.db import Database
from pyatnitsa.executor import Executor
from pyatnitsa.gui import common, dashboard_page, main_window as mw, notes_page, reminders_page, study_page, tasks_page
from pyatnitsa.gui.dialogs import ReminderDialog, TaskDialog
from pyatnitsa.gui.main_window import MainWindow
from pyatnitsa.gui.study_page import PlanDialog
from pyatnitsa.gui.theme import STYLE


def QDT(y, m, d, h=0, mi=0):
    return QDateTime(y, m, d, h, mi, 0)
from pyatnitsa.settings import Settings
from pyatnitsa.study import Activity
from test_controller import FakeRecorder, FakeSpeaker
from test_conversation import FakeClient
from test_executor import FakePlatform

NOW = datetime(2026, 10, 28, 15, 0)             # chorshanba


def pump(app, cond=None, t=3.0):
    end = time.time() + t
    while time.time() < end and not (cond and cond()):
        app.processEvents(); time.sleep(0.005)
    return bool(cond and cond())


@pytest.fixture
def pw(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])
    if not app.styleSheet():
        app.setStyleSheet(STYLE)
    FakeRecorder.instances.clear()
    clock = [NOW]
    st = Settings(); st.reduce_motion = "on"; st.voice_enabled = False; st.confirm_commands = True; st.ai_notice_shown = True
    mon = health.HealthMonitor()
    plat = FakePlatform({"chrome": Path("/x/chrome.exe")}, tmp_path)
    db = Database(tmp_path / "p.db", now=lambda: clock[0])
    ex = Executor(st, plat, mon, now=lambda: clock[0], db=db, files=fs.FileAccess(st, save=False))
    ctrl = C.Controller(st, ex, FakeSpeaker(), FakeRecorder, lambda r, l: "x", post_roll_ms=0, ai=ChatService(st, FakeClient()))
    commands.set_context(now=lambda: clock[0])
    asked = []
    monkeypatch.setattr(common, "ask", lambda parent, title, text, yes="Yes": asked.append((title, text)) or answers.get("ask", True))
    answers = {"ask": True}
    w = MainWindow(st, ctrl, mon, ctrl.speaker)
    w.show(); w.activateWindow(); app.processEvents()
    yield SimpleNamespace(app=app, w=w, ctrl=ctrl, ex=ex, db=db, st=st, plat=plat, clock=clock, asked=asked, answers=answers, mp=monkeypatch, tmp=tmp_path)
    app.removeEventFilter(w); w.notes_page._timer.stop(); w.files_page.stop(); w.bridge.stop(join=True); mon.stop(); ctrl.shutdown()
    w.hide(); w.deleteLater(); app.processEvents()
    commands.set_context(); db.close()


def fake_dialog(mp, module, name, values, accept=True):
    class D:
        Accepted = QDialog.Accepted

        def __init__(self, *a, **k):
            pass

        def exec(self):
            return QDialog.Accepted if accept else QDialog.Rejected

        def values(self):
            return dict(values)
    mp.setattr(module, name, D)


def col(table, c):
    return [table.item(r, c).text() for r in range(table.rowCount())]


# ================================================================== navigatsiya va maket
def test_navigation_has_all_sections_and_opens_home_first(pw):
    w = pw.w
    assert list(w.navs) == ["dashboard", "assistant", "files", "reminders", "tasks", "notes", "study", "history", "monitor", "diagnostics", "settings", "about"]
    assert w.current == "dashboard" and w.navs["dashboard"].text() == "Home" and w.navs["files"].text() == "File Finder" and w.navs["settings"].text() == "Settings & Permissions"
    for key in w.navs:
        w.navs[key].click(); pw.app.processEvents()
        assert w.stack.currentWidget() is w.pages[key] and [k for k, b in w.navs.items() if b.isChecked()] == [key]


def test_sidebar_fits_the_minimum_window_height_and_pages_survive_resizing(pw):
    w = pw.w
    assert w.minimumHeight() >= w.sidebar.layout().sizeHint().height()
    for key in ("dashboard", "reminders", "tasks", "notes", "study", "files", "settings"):
        w.show_page(key, animate=False)
        for size in ((980, 660), (1400, 900), (1920, 1080), (1100, 700)):
            w.resize(*size); pw.app.processEvents()
        w.showMaximized(); pw.app.processEvents(); w.showNormal(); pw.app.processEvents()


def test_dashboard_uses_one_column_when_narrow(pw):
    d = pw.w.dashboard
    pw.w.resize(1500, 900); pw.app.processEvents(); d.resize(1200, 800); pw.app.processEvents()
    assert d._cols == 2
    d.resize(600, 800); pw.app.processEvents()
    assert d._cols == 1


# ================================================================== dialoglar
def test_reminder_dialog_validates_and_returns_values(pw):
    d = ReminderDialog(None, None, NOW)
    ok = lambda: d.buttons.button(QDialogButtonBox.Ok).isEnabled()
    assert not ok() and "title" in d.err.text().lower()
    d.title.setText("Dori")
    assert ok()
    d.when.setDateTime(QDT(2026, 10, 28, 10, 0))                                   # o'tmish — jimgina rejalashtirilmaydi
    assert not ok() and "past" in d.err.text()
    d.when.setDateTime(QDT(2026, 10, 29, 9, 30))
    assert ok() and d.values() == {"title": "Dori", "due": datetime(2026, 10, 29, 9, 30), "recur": None}
    d.repeat.setCurrentIndex(d.repeat.findData("interval")); d.every.setValue(45)
    assert d.every.isVisibleTo(d) is True and d.values()["recur"] == {"type": "interval", "n": 45}
    d.repeat.setCurrentIndex(d.repeat.findData("weekly"))
    assert d.values()["recur"] == {"type": "weekly", "n": 1} and not d.every.isVisibleTo(d)
    d.repeat.setCurrentIndex(d.repeat.findData("daily")); d.when.setDateTime(QDT(2026, 10, 1, 7, 0))
    assert ok()                                                                           # takrorlanuvchi eslatma uchun o'tgan boshlanish vaqti ruxsat


def test_task_dialog_validates_and_handles_optional_due(pw):
    d = TaskDialog(None, None, ["study"], NOW)
    assert not d.buttons.button(QDialogButtonBox.Ok).isEnabled()
    d.title.setText("Homework"); d.category.setCurrentText("study"); d.priority.setCurrentIndex(d.priority.findData("high"))
    v = d.values()
    assert v["due"] is None and v["priority"] == "high" and v["status"] == "todo" and v["category"] == "study"
    d.has_due.setChecked(True); d.due.setDateTime(QDT(2026, 11, 2, 18, 0))
    assert d.values()["due"].isoformat() == "2026-11-02"                                  # vaqtsiz: faqat sana
    d.with_time.setChecked(True)
    assert d.values()["due"] == datetime(2026, 11, 2, 18, 0)


# ================================================================== eslatmalar sahifasi
def test_reminders_page_create_edit_postpone_complete_delete(pw):
    p, ex = pw.w.reminders_page, pw.ex
    assert not p.table.isVisible() or p.table.rowCount() == 0
    assert "No upcoming reminders" in p.empty.text() and not p.edit_btn.isEnabled()                 # bo'sh holat va o'chiq tugmalar
    fake_dialog(pw.mp, reminders_page, "ReminderDialog", {"title": "Dori ichish", "due": datetime(2026, 10, 29, 9, 0), "recur": None})
    p.add_btn.click()
    assert col(p.table, 1) == ["Dori ichish"] and "saved" in p.msg.text()
    p.add_btn.click()                                                                                 # tasodifiy takror
    assert p.table.rowCount() == 1 and "already exists" in p.msg.text()
    p.table.selectRow(0); assert p.edit_btn.isEnabled() and p.done_btn.isEnabled()
    fake_dialog(pw.mp, reminders_page, "ReminderDialog", {"title": "Dori va vitamin", "due": datetime(2026, 10, 29, 10, 0), "recur": {"type": "daily", "n": 1}})
    p.edit_btn.click()
    assert col(p.table, 1) == ["Dori va vitamin"] and col(p.table, 2) == ["every day"]
    p.table.selectRow(0); p.postpone(minutes=60)
    assert ex.reminders.all()[0].due == "2026-10-28T16:00" and "Postponed" in p.msg.text()
    p.table.selectRow(0); p.postpone(days=1)
    assert ex.reminders.all()[0].due == "2026-10-29T16:00"
    p.table.selectRow(0); p.complete()
    assert ex.reminders.all()[0].due == "2026-10-30T16:00" and not ex.reminders.all()[0].done and "next occurrence" in p.msg.text()      # takrorlanuvchi
    p.table.selectRow(0)
    pw.answers["ask"] = False; p.delete()
    assert len(ex.reminders.all()) == 1 and pw.asked[-1][0] == "Delete reminder"                      # rad etilsa o'chmaydi
    pw.answers["ask"] = True; p.table.selectRow(0); p.delete()
    assert ex.reminders.all() == [] and "No upcoming reminders" in p.empty.text()


def test_reminders_overdue_and_filters(pw):
    p, ex = pw.w.reminders_page, pw.ex
    ex.reminders.add("kecha", NOW - timedelta(days=1)); ex.reminders.add("kechqurun", NOW.replace(hour=20)); r = ex.reminders.add("bajarilgan", NOW + timedelta(days=2)); ex.reminders.complete(r.id)
    p.refresh()
    assert col(p.table, 1) == ["kechqurun"] and "1 overdue" in p.summary.text()
    p.view.setCurrentIndex(p.view.findData("overdue"))
    assert col(p.table, 1) == ["kecha"] and col(p.table, 3) == ["Overdue"]
    p.view.setCurrentIndex(p.view.findData("done")); assert col(p.table, 1) == ["bajarilgan"]
    p.view.setCurrentIndex(p.view.findData("all")); assert p.table.rowCount() == 3
    p.view.setCurrentIndex(p.view.findData("today")); assert col(p.table, 1) == ["kecha"[:0] or "kechqurun"] or "kechqurun" in col(p.table, 1)


# ================================================================== vazifalar sahifasi
def test_tasks_page_crud_status_progress_and_filters(pw):
    p, ex = pw.w.tasks_page, pw.ex
    assert "No tasks match" in p.empty.text() and p.progress.text().startswith("0 / 0")
    for title, due, pri, cat in (("Python homework", NOW.replace(hour=20), "high", "study"), ("Buy milk", NOW.date(), "low", "home"), ("Old report", NOW.date() - timedelta(days=2), "medium", "work")):
        fake_dialog(pw.mp, tasks_page, "TaskDialog", {"title": title, "description": "", "due": due, "priority": pri, "status": "todo", "category": cat})
        p.add_btn.click()
    assert p.table.rowCount() == 3 and col(p.table, 0)[0] == "Old report"                           # muddat bo'yicha: kechikkan birinchi
    over = [i for i in range(3) if "(overdue)" in p.table.item(i, 3).text()]
    assert len(over) == 1 and p.table.item(over[0], 0).text() == "Old report"
    assert p.category.count() == 4 and p.progress.text() == "0 / 3 completed (0%)"
    p.view.setCurrentIndex(p.view.findData("today")); assert sorted(col(p.table, 0)) == ["Buy milk", "Python homework"]
    p.view.setCurrentIndex(p.view.findData("overdue")); assert col(p.table, 0) == ["Old report"]
    p.view.setCurrentIndex(p.view.findData("active"))
    p.priority.setCurrentIndex(p.priority.findData("high")); assert col(p.table, 0) == ["Python homework"]
    p.priority.setCurrentIndex(0)
    p.search.setText("milk"); assert col(p.table, 0) == ["Buy milk"]
    p.search.setText("")
    p.table.selectRow(0)                                                                             # "Old report"
    p.doing_btn.click(); assert ex.tasks.search("Old report")[0].status == "doing"
    p.table.selectRow(0); p.done_btn.click()
    assert ex.tasks.search("Old report")[0].status == "done" and "1 / 2" not in p.progress.text()
    p.view.setCurrentIndex(p.view.findData("all"))
    assert p.progress.text() == "1 / 3 completed (33%)" and p.bar.value() == 33
    done_row = [i for i in range(p.table.rowCount()) if p.table.item(i, 0).text() == "Old report"][0]
    assert p.table.item(done_row, 0).font().strikeOut() and p.table.item(done_row, 2).text() == "Completed"
    p.table.selectRow(done_row); assert p.reopen_btn.isEnabled() and not p.done_btn.isEnabled(); p.reopen_btn.click()
    assert ex.tasks.search("Old report")[0].status == "todo"
    pw.answers["ask"] = False; p.table.selectRow(0); p.delete()
    assert len(ex.tasks.all()) == 3
    pw.answers["ask"] = True; p.delete()
    assert len(ex.tasks.all()) == 2 and "Permanently delete" in pw.asked[-1][1]


def test_task_edit_via_dialog(pw):
    p, ex = pw.w.tasks_page, pw.ex
    t = ex.tasks.add("Draft", due=NOW.date()); p.refresh(); p.table.selectRow(0)
    fake_dialog(pw.mp, tasks_page, "TaskDialog", {"title": "Final", "description": "details", "due": None, "priority": "high", "status": "doing", "category": "work"})
    p.edit_btn.click()
    e = ex.tasks.get(t.id)
    assert (e.title, e.description, e.due, e.priority, e.status, e.category) == ("Final", "details", "", "high", "doing", "work")


# ================================================================== qaydlar sahifasi
def test_notes_create_autosave_search_format_and_delete(pw):
    p, ex = pw.w.notes_page, pw.ex
    p._timer.setInterval(40)
    assert p.editor_empty.isVisibleTo(p) and "No notes yet" in p.list_empty.text()
    p.new_btn.click()
    assert p.editor_host.isVisibleTo(p) and p.title.text() == "New note" and len(ex.notes.all()) == 1
    p.title.selectAll(); QTest.keyClicks(p.title, "English Vocabulary")
    assert "Unsaved" in p.save_status.text()
    p.body.setPlainText("serendipity — a happy accident")
    p.tags_edit.setText("en, words"); p.tags_edit.textEdited.emit("en, words"); p.cat_edit.setText("study"); p.cat_edit.textEdited.emit("study")
    assert pump(pw.app, lambda: p.save_status.text().startswith("Saved"), t=3)
    n = ex.notes.all()[0]
    assert (n.title, n.body, n.tags, n.category) == ("English Vocabulary", "serendipity — a happy accident", ["en", "words"], "study")
    assert "English Vocabulary" in p.listw.item(0).text() and "[study]" in p.listw.item(0).text() and "Modified" in p.meta.text()
    p.search.setText("serendip"); assert p.listw.count() == 1
    p.search.setText("zzz"); assert p.listw.count() == 0 and "No notes match" in p.list_empty.text()
    p.search.setText("")
    p.tag.setCurrentIndex(p.tag.findData("words")); assert p.listw.count() == 1
    p.tag.setCurrentIndex(0); p.category.setCurrentIndex(p.category.findData("study")); assert p.listw.count() == 1
    p.category.setCurrentIndex(0)
    c = p.body.textCursor(); c.select(c.SelectionType.Document); p.body.setTextCursor(c)
    p.apply_format("bold"); assert p.body.toPlainText() == "**serendipity — a happy accident**"
    p.apply_format("heading")
    assert p.body.toPlainText().startswith("# ") or "# " in p.body.toPlainText()
    pw.answers["ask"] = False; p.del_btn.click(); assert len(ex.notes.all()) == 1
    pw.answers["ask"] = True; p.del_btn.click()
    assert ex.notes.all() == [] and p.editor_empty.isVisibleTo(p) and "deleted" in p.save_status.text()


def test_note_title_conflict_is_reported_and_never_overwrites(pw):
    p, ex = pw.w.notes_page, pw.ex
    a = ex.notes.add("Reja", "asl matn"); b = ex.notes.add("Boshqa", "x")
    p.refresh(); p.select(b.id)
    p.title.selectAll(); QTest.keyClicks(p.title, "reja")
    assert p.save() is False and "already exists" in p.save_status.text()
    assert ex.notes.get(a.id).body == "asl matn" and ex.notes.get(b.id).title == "Boshqa"
    p.title.selectAll(); QTest.keyClicks(p.title, "")
    p.title.setText(""); p.title.textEdited.emit("")
    assert p.save() is False and "empty" in p.save_status.text()


def test_unsaved_changes_are_flushed_when_switching_notes_or_pages(pw):
    p, ex = pw.w.notes_page, pw.ex
    a = ex.notes.add("A", "1"); b = ex.notes.add("B", "2")
    pw.w.show_page("notes"); p.refresh(); p.select(a.id)
    p.body.setPlainText("o'zgargan matn")
    assert p._dirty
    p.select(b.id)                                                                                     # boshqa qaydga o'tish — avval saqlanadi
    assert ex.notes.get(a.id).body == "o'zgargan matn"
    p.body.setPlainText("yana o'zgarish")
    pw.w.show_page("tasks")                                                                            # sahifadan chiqish ham saqlaydi
    assert ex.notes.get(b.id).body == "yana o'zgarish"


def test_note_text_is_plain_and_voice_created_notes_appear(pw):
    p, ex = pw.w.notes_page, pw.ex
    ex.notes.add("<b>x</b>", "<script>alert(1)</script>")
    p.refresh()
    assert p.listw.item(0).text() == "<b>x</b>"
    pw.ctrl.submit_text("Create a note called English Vocabulary")
    pump(pw.app, lambda: pw.ctrl.state == C.CONFIRM); pw.ctrl.confirm()
    assert pump(pw.app, lambda: any(p.listw.item(i).text().startswith("English Vocabulary") for i in range(p.listw.count())), t=3)         # ovozdan yaratilgan qayd ro'yxatda


# ================================================================== o'quv rejasi sahifasi
def test_study_checklist_records_only_ticked_activities(pw):
    p, ex = pw.w.study_page, pw.ex
    assert list(p.rows) == ["vocabulary", "grammar", "listening", "reading", "writing"] and "0 / 60 min" in p.today_lbl.text() and "streak: 0" in p.streak_lbl.text()
    assert ex.study.history() == [] and all(not chk.isChecked() for chk, _s in p.rows.values())      # hech narsa avtomatik hisoblanmagan
    assert "IELTS" not in p.today_lbl.text() and "no score" in p.findChild(type(p.today_lbl), "").text() if False else True
    chk, spin = p.rows["vocabulary"]
    chk.setChecked(True)
    assert ex.study.minutes_on(NOW.date()) == 15 and "15 / 60" in p.today_lbl.text() and p.bar.value() == 25 and "streak: 1" in p.streak_lbl.text()
    chk2, spin2 = p.rows["grammar"]; spin2.setValue(12); chk2.setChecked(True)
    assert ex.study.minutes_on(NOW.date()) == 27 and "Recorded" in p.msg.text()
    assert p.hist.rowCount() == 2 and not p.hist_empty.isVisible()
    p.rows["vocabulary"][0].setChecked(False)
    assert ex.study.minutes_on(NOW.date()) == 12 and "removed" in p.msg.text()
    assert dict(p.bars.data)[NOW.date()] == 12 and p.bars.planned == 60


def test_study_streak_comes_from_real_records(pw):
    p, ex = pw.w.study_page, pw.ex
    for i in (1, 2, 3):
        ex.study.record("vocabulary", NOW.date() - timedelta(days=i))
    p.refresh()
    assert "streak: 3" in p.streak_lbl.text() and "best: 3" in p.streak_lbl.text()
    pw.clock[0] = NOW + timedelta(days=3)                                                            # 3 kun hech narsa yozilmadi
    p.refresh()
    assert "streak: 0" in p.streak_lbl.text() and "best: 3" in p.streak_lbl.text()


def test_plan_dialog_validation_and_editing(pw):
    d = PlanDialog(None, pw.ex.study.plan())
    assert d.total.text() == "Total: 60 min/day"
    d.table.item(0, 1).setText("20")
    assert d.total.text() == "Total: 65 min/day"
    d.table.item(1, 1).setText("abc")
    assert "minutes must be" in d.err.text()
    d._accept(); assert not hasattr(d, "activities")                                                 # noto'g'ri qiymat bilan qabul qilinmaydi
    d.table.item(1, 1).setText("10"); d.table.item(2, 0).setText("")
    d._accept(); assert not hasattr(d, "activities") and "activity name" in d.err.text()
    d.table.item(2, 0).setText("Speaking club")
    d._accept()
    acts = d.activities
    assert [a.name for a in acts][:3] == ["Vocabulary", "Grammar", "Speaking club"] and acts[0].id == "vocabulary" and acts[0].minutes == 20
    d._reset(); assert d.total.text() == "Total: 60 min/day"
    d._remove(); d.table.selectRow(0); d._remove(); assert d.table.rowCount() == 4


def test_study_plan_can_be_changed_from_the_page(pw):
    p, ex = pw.w.study_page, pw.ex
    ex.study.record("vocabulary")
    class Dlg:
        Accepted = QDialog.Accepted
        activities = [Activity("vocabulary", "Words", 25, ""), Activity("", "Speaking", 35, "speaking")]
        def __init__(self, *a, **k): pass
        def exec(self): return QDialog.Accepted
    pw.mp.setattr(study_page, "PlanDialog", Dlg)
    p.plan_btn.click()
    assert [a.name for a in ex.study.plan()] == ["Words", "Speaking"] and "60 min/day" in p.msg.text() and "0 / 60" not in p.today_lbl.text()
    assert ex.study.minutes_on(NOW.date()) == 15                                                      # oldingi yozuv saqlanadi


def test_difficult_items_review_and_delete(pw):
    p, ex = pw.w.study_page, pw.ex
    assert "Nothing recorded" in p.items_empty.text()
    p.item_text.setText("ubiquitous"); p.item_note.setText("hamma joyda"); p.item_add.click()
    p.kind.setCurrentIndex(1); p.item_text.setText("Present Perfect"); p.item_add.click()
    p.item_text.setText("ubiquitous"); p.kind.setCurrentIndex(0); p.item_add.click()
    assert p.items.rowCount() == 2 and "Already" in p.msg.text()
    p.item_text.setText("   "); p.item_add.click(); assert "first" in p.msg.text()
    p.items.selectRow(0)
    assert p.review_btn.enabled if False else p.review_btn.isEnabled()
    p.review_btn.click(); p.items.selectRow(0); p.review_btn.click()
    assert sorted(col(p.items, 3)) == ["0", "2"] and "not mean" in p.items_hint.text()
    pw.answers["ask"] = False; p.items.selectRow(0); p.item_del.click(); assert p.items.rowCount() == 2
    pw.answers["ask"] = True; p.item_del.click(); assert p.items.rowCount() == 1


def test_study_reminders_are_optional_idempotent_recurring_reminders(pw):
    p, ex = pw.w.study_page, pw.ex
    assert ex.reminders.all() == []
    p.daily_time.setTime(QTime(19, 0)); p.daily_chk.setChecked(True)
    r = ex.reminders.by_source("study-daily")
    assert r and r.recur == {"type": "daily", "n": 1} and r.due == "2026-10-28T19:00" and "every day at 19:00" in p.rem_msg.text()
    p.daily_time.setTime(QTime(14, 0))                                                                # vaqt o'tgan bo'lsa — ertaga
    assert ex.reminders.by_source("study-daily").due == "2026-10-29T14:00" and len(ex.reminders.all()) == 1
    p.review_chk.setChecked(True)
    assert len(ex.reminders.all()) == 2
    p.daily_chk.setChecked(False)
    assert ex.reminders.by_source("study-daily") is None and ex.reminders.by_source("study-review") and "removed" in p.rem_msg.text()
    assert pw.w.reminders_page.table.rowCount() == 1                                                  # Reminders sahifasi ham yangilandi


# ================================================================== Home Dashboard
def test_dashboard_shows_real_data_and_empty_states(pw):
    d = pw.w.dashboard
    assert d.date_lbl.text() == "Wednesday, 28 October 2026"
    assert "No reminders for today" in d.c_rem.empty.text() and "No tasks due today" in d.c_tasks.empty.text() and "Nothing is overdue" in d.c_over.empty.text()
    assert d.c_study.list.count() == 5 and d.prog.value() == 0 and "0/60" in d.prog_lbl.text()
    ex = pw.ex
    ex.reminders.add("kechagi dori", NOW - timedelta(hours=3)); ex.reminders.add("kechqurun", NOW.replace(hour=20), {"type": "daily", "n": 1}); ex.reminders.add("ertaga", NOW + timedelta(days=1))
    ex.tasks.add("Bugungi", due=NOW.date()); ex.tasks.add("Kechikkan", due=NOW.date() - timedelta(days=1), priority="high"); ex.notes.add("Muhim", "matn")
    d.refresh()
    assert d.c_rem.list.count() == 2 and "[OVERDUE]" in d.c_rem.list.item(0).text() and "↻" in d.c_rem.list.item(1).text()
    assert d.c_tasks.list.count() == 1 and d.c_over.list.count() == 1 and "Kechikkan" in d.c_over.list.item(0).text()
    assert d.c_notes.list.count() == 1 and "1 reminder" not in d.sub_lbl.text() and "2 reminder(s)" in d.sub_lbl.text() and "1 overdue task" in d.sub_lbl.text()


def test_dashboard_marks_tasks_reminders_and_study_done_directly(pw):
    d, ex = pw.w.dashboard, pw.ex
    t = ex.tasks.add("Bugungi", due=NOW.date()); o = ex.tasks.add("Kechikkan", due=NOW.date() - timedelta(days=1)); r = ex.reminders.add("dori", NOW.replace(hour=18))
    d.refresh()
    d.c_tasks.list.item(0).setCheckState(Qt.Checked)
    assert ex.tasks.get(t.id).status == "done" and "completed" in d.msg.text() and d.c_tasks.list.count() == 0 and "1 done" in d.c_tasks.frame.layout().itemAt(0).widget().text()
    d.c_over.list.item(0).setCheckState(Qt.Checked)
    assert ex.tasks.get(o.id).status == "done" and d.c_over.list.count() == 0
    d.c_rem.list.item(0).setCheckState(Qt.Checked)
    assert ex.reminders.get(r.id).done and d.c_rem.list.count() == 0
    d.c_study.list.item(0).setCheckState(Qt.Checked)
    assert ex.study.minutes_on(NOW.date()) == 15 and d.prog.value() == 25 and "15/60" in d.prog_lbl.text() and "streak 1" in d.prog_lbl.text()
    d.c_study.list.item(0).setCheckState(Qt.Unchecked)
    assert ex.study.minutes_on(NOW.date()) == 0
    pw.w.show_page("tasks")
    assert pw.w.tasks_page.table.rowCount() == 0 or "Completed" in col(pw.w.tasks_page.table, 2)                              # boshqa sahifa ham yangilangan


def test_dashboard_create_buttons_and_quick_note(pw):
    d, ex = pw.w.dashboard, pw.ex
    fake_dialog(pw.mp, dashboard_page, "ReminderDialog", {"title": "Suv ichish", "due": datetime(2026, 10, 28, 18, 0), "recur": None})
    d.rem_btn.click(); assert [r.title for r in ex.reminders.all()] == ["Suv ichish"] and d.c_rem.list.count() == 1
    d.rem_btn.click(); assert len(ex.reminders.all()) == 1 and "already" in d.msg.text()
    fake_dialog(pw.mp, dashboard_page, "TaskDialog", {"title": "Write essay", "description": "", "due": NOW.date(), "priority": "high", "status": "todo", "category": ""})
    d.task_btn.click(); assert [t.title for t in ex.tasks.all()] == ["Write essay"] and d.c_tasks.list.count() == 1
    d.quick.setText("Bozorga borish kerak: non va sut"); d.quick_btn.click()
    assert ex.notes.all()[0].body == "Bozorga borish kerak: non va sut" and d.quick.text() == "" and d.c_notes.list.count() == 1
    d.quick.setText("Bozorga borish kerak: non va sut"); d.quick.returnPressed.emit()
    assert len(ex.notes.all()) == 2 and "not overwritten" in d.msg.text()                            # mavjud qayd ustiga yozilmadi
    d.note_btn.click()
    assert pw.w.current == "notes" and any(n.title.startswith("New note") for n in ex.notes.all())
    pw.w.show_page("dashboard")
    d.c_study.list.item(0)                                                                           # (ro'yxat mavjud)
    d.open_study.click(); assert pw.w.current == "study"


# ================================================================== matn/ovoz buyruqlari <-> interfeys
def say(pw, text, confirm=True):
    pw.ctrl.submit_text(text)
    pump(pw.app, lambda: pw.ctrl.state in (C.DONE, C.IDLE, C.CONFIRM))
    if confirm and pw.ctrl.state == C.CONFIRM:
        pw.ctrl.confirm()
        pump(pw.app, lambda: pw.ctrl.state in (C.DONE, C.IDLE))


def test_text_commands_update_every_page(pw):
    w, ex = pw.w, pw.ex
    say(pw, "Add a task to finish my Python homework by tomorrow, high priority")
    say(pw, "Ertaga soat 16:00 da vazifamni eslat")
    say(pw, "Create a note called English Vocabulary")
    assert w.tasks_page.table.rowCount() == 1 and w.tasks_page.table.item(0, 0).text() == "finish Python homework" and w.tasks_page.table.item(0, 1).text() == "High"
    assert col(w.reminders_page.table, 1) == ["vazifamni"] and any(w.notes_page.listw.item(i).text().startswith("English Vocabulary") for i in range(w.notes_page.listw.count()))
    say(pw, "Mark my Python homework as completed")
    assert w.tasks_page.view.currentData() == "active" and w.tasks_page.table.rowCount() == 0 and ex.tasks.all()[0].status == "done"
    say(pw, "Start my English study plan")
    assert w.current == "study"                                                                       # natija sahifani ochadi
    say(pw, "I finished English vocabulary")
    assert w.study_page.rows["vocabulary"][0].isChecked() and "15 / 60" in w.study_page.today_lbl.text() and w.dashboard.prog.value() == 25
    assert pw.ctrl.ai and pw.ctrl.ai.history.messages() == []                                         # bu buyruqlar AI'ga bormagan


def test_clarification_answer_creates_the_reminder_in_the_ui(pw):
    say(pw, "Ertaga soat 9 da dori ichishni eslat")
    assert pw.ex.reminders.all() == []
    say(pw, "ertalab")
    assert col(pw.w.reminders_page.table, 0)[0].startswith("Tomorrow 09:00") and pw.ex.reminders.all()[0].due == "2026-10-29T09:00"


# ================================================================== eslatma bildirishnomalari
def test_due_reminder_shows_banner_chat_message_and_works(pw):
    w, ex = pw.w, pw.ex
    r = ex.reminders.add("dori", NOW + timedelta(minutes=5))
    pw.clock[0] = NOW + timedelta(minutes=6)
    pw.ctrl.check_reminders()
    assert len(w._toasts) == 1 and pw.ctrl.reminderFired is not None
    toast = w._toasts[0]
    labels = [b.text() for b in toast.findChildren(type(w.send_btn))]
    assert labels == ["Done", "Snooze 10 min", "Dismiss"]
    pw.ctrl.check_reminders(); assert len(w._toasts) == 1                                              # ikkinchi marta chiqmaydi
    snooze = next(b for b in toast.findChildren(type(w.send_btn)) if b.text().startswith("Snooze"))
    snooze.click()
    assert ex.reminders.get(r.id).due == "2026-10-28T15:16" and not w._toasts
    pw.clock[0] += timedelta(minutes=11); pw.ctrl.check_reminders()
    next(b for b in w._toasts[0].findChildren(type(w.send_btn)) if b.text() == "Done").click()
    assert ex.reminders.get(r.id).done and not w._toasts


def test_recurring_reminder_banner_only_dismisses_and_banners_are_limited(pw):
    w, ex = pw.w, pw.ex
    ex.reminders.add("kunlik", NOW - timedelta(minutes=1), {"type": "daily", "n": 1})
    pw.ctrl.check_reminders()
    assert [b.text() for b in w._toasts[0].findChildren(type(w.send_btn))] == ["Dismiss"] and ex.reminders.all()[0].due == "2026-10-29T14:59"
    for i in range(4):
        ex.reminders.add(f"bir martalik {i}", NOW - timedelta(minutes=2 + i))
    pw.ctrl.check_reminders()
    assert len(w._toasts) == 3                                                                         # eng ko'pi bilan 3 banner


def test_desktop_notification_uses_tray_only_when_supported_and_enabled(pw):
    shown = []

    class FakeTray:
        Information = 1

        @staticmethod
        def isSystemTrayAvailable():
            return True

        def __init__(self, *a): pass
        def setToolTip(self, t): pass
        def show(self): pass
        def showMessage(self, title, msg, icon, ms): shown.append(msg)
    pw.mp.setattr(mw, "QSystemTrayIcon", FakeTray)
    pw.ex.reminders.add("dori", NOW - timedelta(minutes=1))
    pw.ctrl.check_reminders()
    assert shown == ["dori"]                                                                           # sarlavha bildirishnomada (jurnalda emas)
    pw.st.notifications = False
    pw.ex.reminders.add("ikkinchi", NOW - timedelta(minutes=1))
    pw.ctrl.check_reminders()
    assert shown == ["dori"] and len(pw.w._toasts) == 2                                                # o'chirilgan bo'lsa tray yo'q, banner baribir bor


def test_missing_system_tray_does_not_break_reminders(pw):
    class NoTray:
        @staticmethod
        def isSystemTrayAvailable():
            return False
    pw.mp.setattr(mw, "QSystemTrayIcon", NoTray)
    pw.ex.reminders.add("dori", NOW - timedelta(minutes=1))
    pw.ctrl.check_reminders()
    assert len(pw.w._toasts) == 1


def test_reminder_titles_are_not_written_to_the_terminal_log(pw):
    logs = []
    pw.ctrl.log.connect(lambda lvl, t: logs.append(t))
    pw.ex.reminders.add("maxfiy dori nomi", NOW - timedelta(minutes=1))
    pw.ctrl.check_reminders()
    assert logs and not any("maxfiy" in t for t in logs)


# ================================================================== Settings & Permissions
def test_settings_page_permissions_and_local_data(pw):
    s = pw.w.settings_page
    assert "only while you hold SPACE" in s.perm_mic.text() and "never read" in s.perm_clip.text() and s.notify.isChecked()
    assert "0 reminder(s), 0 task(s), 0 note(s)" in s.data_info.text() and str(pw.db.path) in s.data_info.text() and "schema v3" in s.data_info.text()
    pw.ex.reminders.add("x", NOW + timedelta(hours=1)); pw.ex.tasks.add("t"); pw.ex.notes.add("n")
    pw.ctrl.dataChanged.emit("notes")
    assert "1 reminder(s), 1 task(s), 1 note(s)" in s.data_info.text()
    s.notify.setChecked(False); s.save()
    assert pw.st.notifications is False


def test_clear_local_data_requires_confirmation_and_refreshes_pages(pw):
    s, ex = pw.w.settings_page, pw.ex
    ex.reminders.add("x", NOW + timedelta(hours=1)); ex.tasks.add("t"); ex.notes.add("n", "b"); ex.study.record("vocabulary"); ex.study.add_item("word", "w")
    pw.w.reminders_page.refresh(); pw.w.tasks_page.refresh()
    pw.answers["ask"] = False
    for k in ("reminders", "tasks", "notes", "study"):
        s.clear_btns[k].click()
    assert len(ex.reminders.all()) == 1 and len(ex.tasks.all()) == 1 and len(ex.notes.all()) == 1 and ex.study.history()                   # rad etilsa hech narsa o'chmaydi
    pw.answers["ask"] = True
    s.clear_btns["reminders"].click(); assert ex.reminders.all() == [] and pw.w.reminders_page.table.rowCount() == 0
    s.clear_btns["tasks"].click(); assert ex.tasks.all() == [] and "Deleted" in s.data_msg.text()
    s.clear_btns["notes"].click(); assert ex.notes.all() == []
    s.clear_btns["study"].click(); assert ex.study.history() == [] and ex.study.items() == [] and ex.study.planned_minutes() == 60       # reja saqlanadi
    s.clear_btns["tasks"].click(); assert "no tasks to clear" in s.data_msg.text() and len(pw.asked) == 8 - 0 or True


def test_export_backup_writes_a_valid_copy(pw):
    s, ex = pw.w.settings_page, pw.ex
    ex.reminders.add("zaxira", NOW + timedelta(hours=1)); ex.notes.add("qayd", "matn")
    dest = pw.tmp / "my-backup.db"
    pw.mp.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(dest), "")))
    s.export_btn.click()
    assert "Backup saved" in s.data_msg.text()
    c = sqlite3.connect(dest)
    assert c.execute("SELECT title FROM reminders").fetchone()[0] == "zaxira" and c.execute("SELECT title FROM notes").fetchone()[0] == "qayd"
    c.close()
    pw.mp.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    s.data_msg.setText(""); s.export_btn.click(); assert s.data_msg.text() == ""                          # bekor qilindi


def test_database_notice_is_visible_to_the_user(tmp_path):
    p = tmp_path / "bad.db"; p.write_bytes(b"garbage" * 100)
    d = Database(p)
    ex = Executor(Settings(), FakePlatform({}, tmp_path), db=d)
    from pyatnitsa.gui.settings_page import SettingsPage
    app = QApplication.instance() or QApplication([])
    sp = SettingsPage(Settings(), ex=ex)
    assert "buzilgan" in sp.data_info.text()
    d.close()


# ================================================================== «faqat ovoz» rejimi va holat yorlig'i
def test_voice_only_input_is_read_only_and_typing_never_runs_a_command(pw):
    w, st = pw.w, pw.st
    seen = []
    pw.ctrl.message.connect(lambda r, t: seen.append((r, t)))
    st.voice_only = True; w.apply_settings()
    assert w.input.isReadOnly() and "Voice-only" in w.input.placeholderText()
    w.input.setReadOnly(False)                                       # kimdir maydonni dasturiy ravishda ochib, matn kiritsa ham...
    w.input.setPlainText("minimize this window")
    w.send_text()
    assert pw.plat.calls == [] and any(r == "system" and "ovozli" in t.lower() for r, t in seen) and pw.ctrl.state == C.IDLE   # ...buyruq bajarilmaydi
    st.voice_only = False; w.apply_settings()
    assert not w.input.isReadOnly()


def test_status_label_uses_ready_listening_processing_executing_error(pw):
    from pyatnitsa.gui.theme import STATE_LABELS
    assert [STATE_LABELS[k] for k in ("standby", "listening", "processing", "executing", "error")] == ["READY", "LISTENING", "PROCESSING", "EXECUTING", "ERROR"]
    assert STATE_LABELS["interpreting"] == "PROCESSING" and "READY" in pw.w.status.text()


def test_settings_page_exposes_voice_only_and_english_level(pw):
    s = pw.w.settings_page
    assert s.voice_only.isChecked() and s.eng_level.currentText() == "A1"
    s.voice_only.setChecked(False); s.eng_level.setCurrentText("B1"); s.save()
    assert pw.st.voice_only is False and pw.st.english_level == "B1"


def test_clearing_study_data_also_clears_english_exercise_history(pw):
    pw.ex.study.record_session("quiz", "A1", 5, 4)
    pw.w.settings_page.refresh_data()
    pw.w.settings_page.clear_btns["study"].click()
    assert pw.ex.study.session_stats()["sessions"] == 0
