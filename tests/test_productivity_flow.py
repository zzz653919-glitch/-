"""Eslatma · vazifa · qayd · ingliz tili rejasi: buyruqlarni tushunish (uz/ru/en), ijro, aniqlashtirish, rejalashtiruvchi, qayta ishga tushirish.
Haqiqiy boshqaruvchi, NLU, ijrochi va SQLite; Windows qatlami va AI mijoz soxta."""
import time
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from pyatnitsa import commands, controller as C, stt
from pyatnitsa.ai_chat import ChatService
from pyatnitsa.db import Database
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings
from test_controller import FakeRecorder, FakeSpeaker
from test_conversation import FakeClient
from test_executor import FakePlatform

NOW = datetime(2026, 10, 28, 15, 0)


@pytest.fixture(autouse=True)
def fixed_now():
    commands.set_context(now=lambda: NOW)
    yield
    commands.set_context()


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def P(text):
    r = commands.parse(text)
    return r, (r.commands[0] if r.commands else None)


# ================================================================== tushunish
@pytest.mark.parametrize("text,title,due,recur", [
    ("Remind me to study English at 7 PM.", "study English", "2026-10-28T19:00", None),
    ("Ertaga soat 16:00 da vazifamni eslat.", "vazifamni", "2026-10-29T16:00", None),
    ("Har kuni soat 19:00 da ingliz tilini o‘rganishni eslat.", "ingliz tilini o‘rganishni", "2026-10-28T19:00", {"type": "daily", "n": 1}),
    ("remind me in 10 minutes to call mom", "call mom", "2026-10-28T15:10", None),
    ("10 daqiqadan keyin onamga qo'ng'iroq qilishni eslat", "onamga qo'ng'iroq qilishni", "2026-10-28T15:10", None),
    ("напомни завтра в 18:30 позвонить маме", "позвонить маме", "2026-10-29T18:30", None),
    ("напомни через 2 часа выпить воды", "выпить воды", "2026-10-28T17:00", None),
    ("Remind me tomorrow at 6pm to buy milk", "buy milk", "2026-10-29T18:00", None),
    ("Pyatnitsa, remind me every Monday at 9am to review the plan", "review plan", "2026-11-02T09:00", {"type": "weekly", "n": 1, "weekday": 0}),
    ("remind me every 30 minutes to drink water", "drink water", "2026-10-28T15:30", {"type": "interval", "n": 30}),
    ("Eslatma qo'y: hisobotni yuborish ertaga 10 ertalab", "hisobotni yuborish", "2026-10-29T10:00", None),     # matn ichidagi «yubor» faqat ma'lumot
])
def test_reminder_commands(text, title, due, recur):
    r, c = P(text)
    assert r.kind == "ok" and c.action == "reminder_add", (text, r)
    assert (c.args["title"], c.args["due"], c.args["recur"]) == (title, due, recur)
    assert c.needs_confirm is True                                                          # nutq xatosini ushlash uchun tasdiqlanadi


@pytest.mark.parametrize("text,key", [
    ("Ertaga soat 9 da dori ichishni eslat", "Soat 9"), ("dori ichishni eslat", "Qachon"), ("Ertaga Python darsimni eslat.", "Qachon"), ("bugun soat 8 ertalab dori ichishni eslat", "o'tib ketgan"),
    ("Eslat", "Nimani"), ("remind me to call mom", "When"), ("remind me tomorrow at 9 to call mom", "9 o'clock"), ("напомни в 7 позвонить", "7 часов"),
])
def test_ambiguous_reminders_ask_instead_of_guessing(text, key):
    r, c = P(text)
    assert r.kind == "clarify" and not r.commands and r.draft and key in r.message, (text, r.message)


@pytest.mark.parametrize("text,action,sub", [
    ("Add a task to finish my Python homework", "task_add", {"title": "finish Python homework", "priority": "medium"}),
    ("Add a task to finish my Python homework by tomorrow, high priority", "task_add", {"title": "finish Python homework", "due": "2026-10-29", "priority": "high"}),
    ("Vazifa qo'sh: Python uy ishini tugatish", "task_add", {"title": "Python uy ishini tugatish"}),
    ("Добавь задачу: сделать домашку по английскому завтра", "task_add", {"title": "сделать домашку по английскому завтра", "due": "2026-10-29"}),
    ("add task: call the bank tomorrow at 5pm", "task_add", {"due": "2026-10-29T17:00"}),
    ("Bugungi vazifalarimni ko‘rsat.", "tasks_show", {"scope": "today"}),
    ("Show my overdue tasks", "tasks_show", {"scope": "overdue"}),
    ("покажи просроченные задачи", "tasks_show", {"scope": "overdue"}),
    ("show my tasks for this week", "tasks_show", {"scope": "week"}),
    ("Mark my English homework as completed", "task_complete", {"query": "English homework"}),
    ("Python uy vazifasini bajarildi deb belgila", "task_complete", {"query": "Python uy"}),
    ("Create a note called English Vocabulary", "note_add", {"title": "English Vocabulary", "body": ""}),
    ("Yangi qayd: bozor ro'yxati non sut", "note_add", {"title": "bozor ro'yxati non sut"}),
    ("note: buy milk", "note_add", {"title": "buy milk"}),
    ("создай заметку: купить хлеб", "note_add", {"title": "купить хлеб"}),
    ("qayd qidir bozor", "notes_show", {"query": "bozor"}),
    ("find notes about milk", "notes_show", {"query": "milk"}),
    ("Start my English study plan", "study_show", {}),
    ("Ingliz tili o'quv rejamni boshla", "study_show", {}),
    ("Начни мой план изучения английского", "study_show", {}),
    ("I finished English vocabulary", "study_done", {"activity": "vocabulary"}),
    ("Lug'at mashg'ulotini tugatdim", "study_done", {"activity": "vocabulary"}),
    ("show my study progress", "study_progress", {}),
    ("Eslatmalarni ko'rsat", "reminders_show", {"scope": "all"}),
    ("Show today's reminders", "reminders_show", {"scope": "today"}),
    ("покажи просроченные напоминания", "reminders_show", {"scope": "overdue"}),
])
def test_task_note_study_commands(text, action, sub):
    r, c = P(text)
    assert r.kind == "ok" and c.action == action, (text, r)
    for k, v in sub.items():
        assert c.args.get(k) == v, (text, k, c.args)


@pytest.mark.parametrize("text", ["Vazifani o'chir", "delete my tasks", "Eslatmani o'chir", "qaydlarni o'chir", "удали заметку", "Remove the reminder",
                                  "Mark my homework as completed and delete it", "delete the files and remind me tomorrow at 5pm to rest", "Eslatma qo'y va faylni o'chir"])
def test_destructive_words_in_the_command_part_are_blocked(text):
    r, c = P(text)
    assert r.kind == "blocked" and not r.commands, (text, r)


def test_destructive_words_inside_the_text_are_just_data():
    r, c = P("Add a task: delete old downloads")                    # vazifa matni — ma'lumot, hech narsa o'chirilmaydi
    assert r.kind == "ok" and c.action == "task_add" and c.args["title"] == "delete old downloads"
    r, c = P("Create a note called delete me")
    assert r.kind == "ok" and c.args["title"] == "delete me"


@pytest.mark.parametrize("text", ["Notepad'ni och", "Chrome'ni och", "Python nima?", "Salom", "Kalkulyatorni och", "Python haqida qidir", "Google'da Python darslarini qidir",
                                  "Dollar kursini ko'rsat", "Kompyuter holati qanday?", "Downloads papkasini och", "Fayl menejerini och", "Hujjatlarimni ochgin"])
def test_existing_commands_are_not_hijacked(text):
    r, c = P(text)
    assert not (c and c.action in {"reminder_add", "reminders_show", "task_add", "tasks_show", "task_complete", "note_add", "notes_show", "study_show", "study_done", "study_progress"}), (text, c)


@pytest.mark.parametrize("text,key", [("pauza", "play_pause"), ("keyingi qo'shiq", "next"), ("ovozni oshir", "vol_up"), ("next track", "next"), ("volume down", "vol_down"),
                                      ("громче", "vol_up"), ("следующий трек", "next"), ("mute", "mute"), ("oldingi qo'shiq", "prev"), ("pause", "play_pause")])
def test_media_commands(text, key):
    r, c = P(text)
    assert r.kind == "ok" and c.action == "media" and c.args["key"] == key and c.needs_confirm is False


@pytest.mark.parametrize("text", ["Davom et", "Продолжай", "Continue my previous question", "Oldingi savolimni davom ettir", "next question please, why is the sky blue"])
def test_conversation_phrases_are_not_media(text):
    assert not (P(text)[1] and P(text)[1].action == "media")


def test_windows_settings_app_is_understood():
    for t in ("Open Windows settings", "Windows sozlamalarini och", "открой настройки Windows", "open system settings"):
        r, c = P(t)
        assert r.kind == "ok" and c.action == "open_app" and c.args["app"] == "winsettings", t
    for t in ("Open Settings", "Sozlamalarni och", "открой настройки"):          # Windows yoki ilova sozlamalari? — aniqlashtiriladi, taxmin qilinmaydi
        r = commands.parse(t)
        assert r.kind == "clarify" and r.draft, t


# ================================================================== ijrochi va boshqaruvchi
class Env:
    pass


def make(tmp_path, confirm=True, db_path=None):
    e = Env()
    e.now = [NOW]
    e.st = Settings(); e.st.confirm_commands = confirm; e.st.voice_enabled = False; e.st.ai_notice_shown = True
    e.plat = FakePlatform({"chrome": Path("/x/chrome.exe")}, tmp_path)
    e.dbpath = db_path or tmp_path / "p.db"
    e.db = Database(e.dbpath, now=lambda: e.now[0])
    e.ex = Executor(e.st, e.plat, now=lambda: e.now[0], db=e.db)
    e.client = FakeClient()
    e.spk = FakeSpeaker()
    e.c = C.Controller(e.st, e.ex, e.spk, FakeRecorder, lambda r, l: "x", post_roll_ms=0, ai=ChatService(e.st, e.client))
    e.msgs, e.states, e.changed, e.nav, e.fired, e.asks = [], [], [], [], [], []
    e.c.message.connect(lambda r, t: e.msgs.append((r, t)))
    e.c.stateChanged.connect(lambda k, _l: e.states.append(k))
    e.c.dataChanged.connect(e.changed.append)
    e.c.navigate.connect(e.nav.append)
    e.c.reminderFired.connect(e.fired.append)
    e.c.confirmChanged.connect(lambda on, ask: e.asks.append(ask) if on else None)
    FakeRecorder.instances.clear()
    return e


def wait(cond, t=4.0):
    end = time.time() + t
    while time.time() < end and not cond():
        QCoreApplication.processEvents(); time.sleep(0.005)
    assert cond()


def say(e, text):
    e.c.submit_text(text)
    wait(lambda: e.c.state in (C.DONE, C.IDLE, C.CONFIRM))


def confirm(e):
    assert e.c.state == C.CONFIRM
    e.c.confirm()
    wait(lambda: e.c.state in (C.DONE, C.IDLE))


def last(e):
    return [t for r, t in e.msgs if r == "assistant"][-1]


def test_reminder_is_confirmed_saved_and_survives_restart(app, tmp_path):
    e = make(tmp_path)
    say(e, "Ertaga soat 16:00 da vazifamni eslat.")
    assert e.c.state == C.CONFIRM and "vazifamni" in e.asks[-1] and "29.10.2026 16:00" in e.asks[-1] and e.ex.reminders.all() == []     # tasdiqlanguncha saqlanmaydi
    confirm(e)
    assert "saqlandi" in last(e) and e.changed == ["reminders"]
    got = e.ex.reminders.all()
    assert [(r.title, r.due) for r in got] == [("vazifamni", "2026-10-29T16:00")]
    e.c.shutdown(); e.db.close()
    e2 = make(tmp_path / "again" if False else tmp_path, db_path=e.dbpath)                    # xuddi shu baza fayli bilan qayta ishga tushirish
    assert [(r.title, r.due) for r in e2.ex.reminders.all()] == [("vazifamni", "2026-10-29T16:00")]


def test_repeating_the_same_reminder_does_not_create_a_duplicate(app, tmp_path):
    e = make(tmp_path, confirm=False)
    say(e, "remind me tomorrow at 6pm to buy milk"); say(e, "remind me tomorrow at 6pm to buy milk")
    assert len(e.ex.reminders.all()) == 1 and "already exists" in last(e)


def test_ambiguous_time_is_clarified_then_completed_by_the_answer(app, tmp_path):
    e = make(tmp_path)
    say(e, "Ertaga soat 9 da dori ichishni eslat")
    assert e.c.state in (C.DONE, C.IDLE) and "ertalabmi" in last(e) and e.ex.reminders.all() == []             # SILENT scheduling yo'q
    say(e, "ertalab")                                                                                  # javob avvalgi so'rovga qo'shiladi
    assert e.c.state == C.CONFIRM and "29.10.2026 09:00" in e.asks[-1]
    confirm(e)
    assert [(r.title, r.due) for r in e.ex.reminders.all()] == [("dori ichishni", "2026-10-29T09:00")]


def test_missing_time_then_answer(app, tmp_path):
    e = make(tmp_path)
    say(e, "dori ichishni eslat"); assert "Qachon" in last(e)
    say(e, "10 daqiqadan keyin")
    assert e.c.state == C.CONFIRM and "28.10.2026 15:10" in e.asks[-1]
    e.c.cancel(silent=True)
    assert e.ex.reminders.all() == []


def test_unrelated_command_during_clarification_is_not_swallowed(app, tmp_path):
    e = make(tmp_path)
    say(e, "dori ichishni eslat")
    say(e, "Chrome'ni och")
    assert e.c.state == C.CONFIRM and "Chrome" in e.asks[-1]
    e.c.cancel(silent=True)
    say(e, "bekor"); assert e.c._draft == ""


def test_cancel_during_clarification_drops_the_draft(app, tmp_path):
    e = make(tmp_path)
    say(e, "dori ichishni eslat")
    say(e, "bekor")
    assert e.c._draft == "" and e.ex.reminders.all() == []
    say(e, "ertaga soat 9 ertalab")                                                                    # eski qoralama endi yo'q: bu yolg'iz gap tushunarsiz
    assert e.c.state != C.CONFIRM


def test_scheduler_fires_due_reminders_once_and_marks_overdue(app, tmp_path):
    e = make(tmp_path, confirm=False)
    e.ex.reminders.add("dori", NOW + timedelta(minutes=10))
    e.c.check_reminders()
    assert e.fired == []
    e.now[0] = NOW + timedelta(minutes=11)
    e.c.check_reminders(); e.c.check_reminders()
    assert [r.title for r in e.fired] == ["dori"]                                                      # BIR marta
    assert [r.title for r in e.ex.reminders.overdue()] == ["dori"]


def test_scheduler_survives_database_errors(app, tmp_path):
    e = make(tmp_path)
    e.db.close()
    e.c.check_reminders()                                                                              # istisno ko'tarilmaydi
    assert e.fired == []


def test_show_reminders_lists_overdue_and_today(app, tmp_path):
    e = make(tmp_path)
    e.ex.reminders.add("kechagi", NOW - timedelta(days=1)); e.ex.reminders.add("kechqurun", NOW.replace(hour=20)); e.ex.reminders.add("ertaga", NOW + timedelta(days=1))
    say(e, "Show today's reminders")
    t = last(e)
    assert "kechqurun" in t and "kechagi" in t and "OVERDUE" in t and "ertaga" not in t and C.CONFIRM not in e.states
    say(e, "покажи просроченные напоминания")
    assert "kechagi" in last(e) and "kechqurun" not in last(e)


def test_task_flow_add_show_complete(app, tmp_path):
    e = make(tmp_path)
    say(e, "Add a task to finish my Python homework by tomorrow, high priority"); confirm(e)
    say(e, "Add a task: English homework unit 3"); confirm(e)
    assert e.changed.count("tasks") == 2
    ts = {t.title: t for t in e.ex.tasks.all()}
    assert ts["finish Python homework"].priority == "high" and ts["finish Python homework"].due == "2026-10-29"
    say(e, "show my tasks")
    assert "finish Python homework" in last(e) and "English homework unit 3" in last(e)
    say(e, "Mark my English homework as completed")
    assert e.c.state == C.CONFIRM and "English homework" in e.asks[-1]
    confirm(e)
    assert e.ex.tasks.find_active("english homework") == [] and "completed" in last(e).lower() or "bajarilgan" in last(e)
    say(e, "Show my overdue tasks")
    assert "yo'q" in last(e) or "No tasks" in last(e) or "Задач нет" in last(e)


def test_completing_an_ambiguous_task_asks_for_a_clearer_name(app, tmp_path):
    e = make(tmp_path, confirm=False)
    e.ex.tasks.add("English homework"); e.ex.tasks.add("English speaking")
    say(e, "Mark my English as completed")
    assert "Several tasks match" in last(e) and len(e.ex.tasks.view("active")) == 2                       # taxmin qilinmadi
    say(e, "Mark my Chemistry as completed")
    assert "No active task" in last(e)


def test_voice_cannot_delete_tasks_or_reminders(app, tmp_path):
    e = make(tmp_path, confirm=False)
    t = e.ex.tasks.add("muhim vazifa"); r = e.ex.reminders.add("muhim eslatma", NOW + timedelta(hours=1))
    for text in ("vazifani o'chir", "delete my tasks", "eslatmani o'chir", "удали заметку"):
        say(e, text)
    assert e.ex.tasks.get(t.id) and e.ex.reminders.get(r.id) and e.client.calls == []


def test_notes_voice_flow_never_overwrites(app, tmp_path):
    e = make(tmp_path, confirm=False)
    say(e, "Create a note called English Vocabulary")
    say(e, "Create a note called English Vocabulary")
    assert sorted(n.title for n in e.ex.notes.all()) == ["English Vocabulary", "English Vocabulary (2)"] and "not overwritten" in last(e)
    e.ex.notes.update(e.ex.notes.find_title("English Vocabulary").id, body="serendipity")
    say(e, "find notes about serendipity")
    assert "English Vocabulary" in last(e) and "serendipity" in last(e)


def test_study_plan_flow_records_only_what_the_user_says(app, tmp_path):
    e = make(tmp_path)
    say(e, "Start my English study plan")
    t = last(e)
    assert "Vocabulary — 15" in t and t.count("☐") == 5 and "☑" not in t and "0/60" in t and e.nav == ["study"] and "IELTS" in t       # hech narsa bajarilgan emas
    assert e.ex.study.history() == []
    say(e, "I finished English vocabulary")
    assert e.c.state == C.CONFIRM
    confirm(e)
    assert "Recorded" in last(e) and "15/60" in last(e) and e.ex.study.minutes_on(NOW.date()) == 15 and e.changed[-1] == "study"
    say(e, "I finished English vocabulary"); confirm(e)
    assert "already recorded" in last(e) and e.ex.study.minutes_on(NOW.date()) == 15                       # ikki marta hisoblanmaydi
    say(e, "show my study progress")
    assert "streak: 1" in last(e) and "15/60" in last(e)


def test_media_key_is_sent_without_claiming_success(app, tmp_path):
    e = make(tmp_path)
    keys = []
    e.plat.media_key = keys.append
    say(e, "pauza")
    assert keys == ["play_pause"] and C.CONFIRM not in e.states
    assert "cannot verify" in last(e).lower() or "tekshira olmayman" in last(e)
    assert "bajarildi" not in last(e) and "succeeded" not in last(e).lower()
    e.plat.media_key = lambda k: (_ for _ in ()).throw(OSError("only Windows"))
    say(e, "keyingi qo'shiq")
    assert e.c.last_ok is False


def test_windows_settings_opens_through_the_fixed_uri_only(app, tmp_path):
    e = make(tmp_path)
    opened = []
    e.plat.open_uri = opened.append
    say(e, "Open Windows settings"); confirm(e)
    assert opened == ["winsettings"]
    with pytest.raises(ValueError):
        from pyatnitsa.apps import Platform
        Platform().open_uri("evil")


def test_none_of_these_commands_reach_the_ai(app, tmp_path):
    e = make(tmp_path, confirm=False)
    for t in ("remind me in 5 minutes to stretch", "Add a task: homework", "note: milk", "Start my English study plan", "Show my overdue tasks", "pauza"):
        say(e, t)
    assert e.client.calls == [] and len(e.c.ai.history) == 0


def test_voice_path_uses_the_same_pipeline(app, tmp_path):
    e = make(tmp_path)
    e.c._transcribe = lambda r, l: [stt.Heard("Ertaga soat 16:00 da vazifamni eslat", "uz-UZ", 0.9)]
    e.c.space_pressed(); e.c.space_released(force=True)
    wait(lambda: e.c.state == C.CONFIRM)
    assert ("user", "Ertaga soat 16:00 da vazifamni eslat") in e.msgs and "16:00" in e.asks[-1]
    e.c.cancel(silent=True)
