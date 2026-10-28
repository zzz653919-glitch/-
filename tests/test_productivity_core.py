"""Mahalliy ombor (SQLite), migratsiyalar, eslatma/vazifa/qayd/o'quv do'konlari. Haqiqiy SQLite fayllari vaqtinchalik papkalarda."""
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from pyatnitsa import db as dbmod
from pyatnitsa.db import Database, SCHEMA_VERSION
from pyatnitsa.notes import NoteExists, NoteStore
from pyatnitsa.reminders import ReminderStore, describe_recur
from pyatnitsa.study import Activity, StudyStore
from pyatnitsa.tasks import TaskStore
from pyatnitsa.timeparse import next_occurrence

NOW = datetime(2026, 10, 28, 15, 0)          # chorshanba


@pytest.fixture
def path(tmp_path):
    return tmp_path / "productivity.db"


@pytest.fixture
def db(path):
    d = Database(path, now=lambda: NOW)
    yield d
    d.close()


# ------------------------------------------------------------------ baza va migratsiyalar
def test_fresh_database_has_current_schema(db):
    assert db.user_version() == SCHEMA_VERSION and db.persistent and db.notice == ""
    tables = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"reminders", "tasks", "notes", "study_activities", "study_log", "study_items", "meta"} <= tables


def make_v1(path: Path):
    c = sqlite3.connect(path)
    for stmt in [s.strip() for s in dbmod._V1.split(";\n") if s.strip()]:
        c.execute(stmt)
    c.execute("INSERT INTO reminders(id,title,due,created) VALUES('r1','dori ichish','2026-10-29T09:00','2026-10-28T10:00')")
    c.execute("INSERT INTO notes(id,title,body,tags,created,updated) VALUES('n1','Bozor','non, sut','[\"uy\"]','2026-10-01T10:00:00','2026-10-02T10:00:00')")
    c.execute("PRAGMA user_version=1")
    c.commit(); c.close()


def test_migration_v1_to_v2_preserves_data_and_makes_a_backup(path):
    make_v1(path)
    d = Database(path, now=lambda: NOW)
    assert d.user_version() == 2 and d.persistent and "yangilandi" in d.notice
    assert [r["title"] for r in d.query("SELECT title FROM reminders")] == ["dori ichish"]
    n = NoteStore(d, lambda: NOW).get("n1")
    assert n.title == "Bozor" and n.body == "non, sut" and n.tags == ["uy"] and n.category == ""          # yangi ustun standart qiymat bilan
    assert d.query("SELECT COUNT(*) FROM tasks")[0][0] == 0                                              # yangi jadvallar yaratildi
    assert len(d.backups) == 1 and d.backups[0].exists()
    old = sqlite3.connect(d.backups[0])
    assert old.execute("PRAGMA user_version").fetchone()[0] == 1 and old.execute("SELECT title FROM reminders").fetchone()[0] == "dori ichish"
    old.close(); d.close()


def test_failed_migration_leaves_the_file_untouched(path, monkeypatch):
    make_v1(path)

    def boom(conn):
        conn.execute("CREATE TABLE half_done(x)")
        raise RuntimeError("migration bug")
    monkeypatch.setitem(dbmod.MIGRATIONS, 2, boom)
    d = Database(path, now=lambda: NOW)
    assert not d.persistent and "fayl o'zgartirilmadi" in d.notice                  # ilova qulamaydi, vaqtincha xotirada ishlaydi
    d.close()
    raw = sqlite3.connect(path)
    assert raw.execute("PRAGMA user_version").fetchone()[0] == 1
    assert raw.execute("SELECT COUNT(*) FROM reminders").fetchone()[0] == 1
    assert raw.execute("SELECT name FROM sqlite_master WHERE name='half_done'").fetchone() is None     # tranzaksiya bekor qilindi
    raw.close()


def test_corrupt_database_is_quarantined_not_deleted(path):
    path.write_bytes(b"this is not a sqlite database" * 50)
    d = Database(path, now=lambda: NOW)
    assert d.persistent and "buzilgan" in d.notice and d.user_version() == SCHEMA_VERSION
    saved = list(path.parent.glob("productivity.db.corrupt-*"))
    assert len(saved) == 1 and saved[0].read_bytes().startswith(b"this is not")
    d.close()


def test_database_from_a_newer_app_version_is_not_modified(path):
    c = sqlite3.connect(path); c.execute("CREATE TABLE future(x)"); c.execute("PRAGMA user_version=99"); c.commit(); c.close()
    before = path.read_bytes()
    d = Database(path, now=lambda: NOW)
    assert not d.persistent and "yangiroq" in d.notice
    ReminderStore(d, lambda: NOW).add("x", NOW + timedelta(hours=1))                # xotirada ishlaydi
    d.close()
    assert path.read_bytes() == before


def test_only_the_last_backups_are_kept(path):
    make_v1(path)
    t = [NOW]
    d = Database(path, now=lambda: t[0])
    d.close()
    for i in range(8):                                                              # sun'iy eski zaxiralar
        (path.parent / f"{path.name}.bak-v1-2026010{i + 1}-000000").write_bytes(b"x")
    make_v1(path.with_name("other.db"))
    c = sqlite3.connect(path); c.execute("PRAGMA user_version=1"); c.commit(); c.close()
    Database(path, now=lambda: NOW).close()
    assert len(list(path.parent.glob(f"{path.name}.bak-*"))) <= dbmod.KEEP_BACKUPS


def test_clear_only_known_tables(db):
    db.execute("INSERT INTO meta(key,value) VALUES('k','v')")
    with pytest.raises(ValueError):
        db.clear("meta")
    with pytest.raises(ValueError):
        db.clear("reminders; DROP TABLE tasks")


def test_data_survives_restart(path):
    d = Database(path, now=lambda: NOW)
    ReminderStore(d, lambda: NOW).add("dori", NOW + timedelta(hours=2), {"type": "daily", "n": 1})
    TaskStore(d, lambda: NOW).add("Python homework", due=NOW.date(), priority="high")
    NoteStore(d, lambda: NOW).add("English Vocabulary", "words", ["en"], "study")
    StudyStore(d, lambda: NOW).record("vocabulary")
    d.close()
    d2 = Database(path, now=lambda: NOW)
    assert [r.title for r in ReminderStore(d2, lambda: NOW).all()] == ["dori"] and ReminderStore(d2, lambda: NOW).all()[0].recur == {"type": "daily", "n": 1}
    assert TaskStore(d2, lambda: NOW).all()[0].priority == "high"
    assert NoteStore(d2, lambda: NOW).all()[0].category == "study"
    assert StudyStore(d2, lambda: NOW).minutes_on(NOW.date()) == 15
    d2.close()


# ------------------------------------------------------------------ eslatmalar
@pytest.fixture
def rem(db):
    return ReminderStore(db, lambda: NOW)


def test_reminder_crud_postpone_and_duplicates(rem):
    a, created = rem.add_unique("Dori ichish", NOW + timedelta(hours=1))
    b, created2 = rem.add_unique("dori ichish", NOW + timedelta(hours=1))
    assert created and not created2 and a.id == b.id and len(rem.all()) == 1                # tasodifiy takror qo'shilmaydi
    assert rem.update(a.id, title="Dori va vitamin").title == "Dori va vitamin"
    moved = rem.postpone(a.id, minutes=30)
    assert moved.due_dt == datetime(2026, 10, 28, 15, 30)
    assert rem.postpone(a.id, to=datetime(2026, 10, 29, 9, 0)).due == "2026-10-29T09:00"
    assert rem.complete(a.id).done and rem.active() == []
    assert not rem.reopen(a.id).done
    assert rem.delete(a.id) and rem.get(a.id) is None and not rem.delete(a.id)
    with pytest.raises(ValueError):
        rem.add("   ", NOW)


def test_overdue_upcoming_today(rem):
    rem.add("kecha", NOW - timedelta(days=1)); rem.add("bir soat oldin", NOW - timedelta(hours=1))
    rem.add("bugun kechqurun", NOW.replace(hour=20)); rem.add("ertaga", NOW + timedelta(days=1))
    assert [r.title for r in rem.overdue()] == ["kecha", "bir soat oldin"]
    assert [r.title for r in rem.today()] == ["bir soat oldin", "bugun kechqurun"]
    assert [r.title for r in rem.upcoming()] == ["bugun kechqurun", "ertaga"]


def test_recurring_reminder_advances_on_complete_and_when_fired(db):
    t = [NOW]
    rem = ReminderStore(db, lambda: t[0])
    r = rem.add("Ingliz tili", datetime(2026, 10, 28, 19, 0), {"type": "daily", "n": 1})
    assert rem.fire_due(NOW) == []                                                   # hali vaqti kelmagan
    t[0] = datetime(2026, 10, 28, 19, 1)
    assert [x.id for x in rem.fire_due()] == [r.id]
    assert rem.get(r.id).due == "2026-10-29T19:00" and not rem.get(r.id).done          # keyingi kunga o'tdi, qayta chiqmaydi
    assert rem.fire_due() == []
    rem.complete(r.id)
    assert rem.get(r.id).due == "2026-10-30T19:00" and rem.get(r.id).completions == 1


def test_one_time_reminder_fires_once_stays_overdue_until_completed(rem):
    r = rem.add("hisobot", NOW - timedelta(minutes=5))
    assert [x.id for x in rem.fire_due()] == [r.id] and rem.fire_due() == []
    assert [x.id for x in rem.overdue()] == [r.id]
    rem.complete(r.id)
    assert rem.overdue() == []


def test_missed_reminders_fire_after_restart(path):
    d = Database(path, now=lambda: NOW)
    ReminderStore(d, lambda: NOW).add("ilova o'chiq edi", NOW + timedelta(hours=1))
    d.close()
    later = NOW + timedelta(hours=3)
    d2 = Database(path, now=lambda: later)
    rs = ReminderStore(d2, lambda: later)
    assert [r.title for r in rs.fire_due()] == ["ilova o'chiq edi"] and rs.fire_due() == []
    d2.close()


def test_source_key_makes_system_reminders_idempotent(rem):
    a, c1 = rem.add_unique("Study", NOW + timedelta(hours=1), {"type": "daily", "n": 1}, source_key="study-daily")
    b, c2 = rem.add_unique("Study (boshqa nom)", NOW + timedelta(hours=2), None, source_key="study-daily")
    assert c1 and not c2 and a.id == b.id and len(rem.all()) == 1
    assert rem.delete_by_source("study-daily") and rem.all() == []


@pytest.mark.parametrize("recur,start,expect", [
    ({"type": "daily", "n": 1}, datetime(2026, 10, 28, 9, 0), datetime(2026, 10, 29, 9, 0)),
    ({"type": "weekly", "n": 1}, datetime(2026, 10, 28, 9, 0), datetime(2026, 11, 4, 9, 0)),
    ({"type": "monthly", "n": 1}, datetime(2026, 1, 31, 9, 0), datetime(2026, 2, 28, 9, 0)),          # oy oxiri qisqartiriladi
    ({"type": "weekdays", "n": 1}, datetime(2026, 10, 30, 9, 0), datetime(2026, 11, 2, 9, 0)),        # juma -> dushanba
    ({"type": "interval", "n": 90}, datetime(2026, 10, 28, 14, 0), datetime(2026, 10, 28, 15, 30)),
])
def test_next_occurrence(recur, start, expect):
    after = start if recur["type"] != "interval" else NOW
    assert next_occurrence(start, recur, after) == expect


def test_invalid_recurrence_is_dropped(rem):
    r = rem.add("x", NOW + timedelta(hours=1), {"type": "bogus"})
    assert r.recur is None and describe_recur(None, "en") == "once" and describe_recur({"type": "daily", "n": 1}, "uz") == "har kuni"


# ------------------------------------------------------------------ vazifalar
@pytest.fixture
def tasks(db):
    return TaskStore(db, lambda: NOW)


def test_task_fields_validation_and_status_flow(tasks):
    t = tasks.add("Python homework", "3-mashq", NOW.replace(hour=20), "high", category="study")
    assert (t.priority, t.status, t.category, t.description) == ("high", "todo", "study", "3-mashq") and t.due == "2026-10-28T20:00"
    assert tasks.set_status(t.id, "doing").status == "doing"
    done = tasks.complete(t.id)
    assert done.status == "done" and done.completed_at
    assert tasks.set_status(t.id, "todo").completed_at == ""                         # qaytarilsa, bajarilgan vaqt tozalanadi
    with pytest.raises(ValueError):
        tasks.add("x", priority="urgent")
    with pytest.raises(ValueError):
        tasks.update(t.id, status="finished")
    with pytest.raises(ValueError):
        tasks.update(t.id, title="  ")
    with pytest.raises(ValueError):
        tasks.update(t.id, bogus=1)


def test_duplicate_task_is_not_created_twice(tasks):
    a, c1 = tasks.add_unique("English homework", due=NOW.date())
    b, c2 = tasks.add_unique("english HOMEWORK", due=NOW.date())
    assert c1 and not c2 and a.id == b.id and len(tasks.all()) == 1
    tasks.complete(a.id)
    assert tasks.add_unique("English homework", due=NOW.date())[1]                    # bajarilgan bo'lsa, yangisi yaratiladi


def test_task_views_overdue_search_and_progress(tasks):
    tasks.add("kechagi", due=NOW.date() - timedelta(days=1), priority="high")
    tasks.add("bugungi sana", due=NOW.date())
    tasks.add("bugun 10:00 (o'tgan)", due=NOW.replace(hour=10))
    tasks.add("bugun 20:00", due=NOW.replace(hour=20), category="study")
    tasks.add("shu hafta", due=NOW.date() + timedelta(days=3))
    tasks.add("keyingi hafta", due=NOW.date() + timedelta(days=9))
    tasks.add("muddatsiz")
    names = lambda v: sorted(t.title for t in tasks.view(v, NOW))
    assert names("overdue") == ["bugun 10:00 (o'tgan)", "kechagi"]                    # faqat sana berilgan bugungi vazifa bugun kechikmaydi
    assert names("today") == ["bugun 10:00 (o'tgan)", "bugun 20:00", "bugungi sana"]
    assert names("week") == ["bugun 10:00 (o'tgan)", "bugun 20:00", "bugungi sana", "shu hafta"]
    assert [t.title for t in tasks.search(category="study")] == ["bugun 20:00"] and [t.title for t in tasks.search("kechagi")] == ["kechagi"]
    assert [t.title for t in tasks.search(priority="high")] == ["kechagi"]
    tasks.complete(tasks.search("kechagi")[0].id)
    assert tasks.progress(tasks.all()) == (1, 7) and tasks.progress(tasks.search("zzz")) == (0, 0)
    assert [t.title for t in tasks.search(status="done")] == ["kechagi"] and tasks.categories() == ["study"]
    assert tasks.all()[-1].status == "done"                                           # bajarilganlar oxirida


def test_date_only_task_is_overdue_the_next_day(db):
    ts = TaskStore(db, lambda: NOW)
    t = ts.add("sana", due=NOW.date())
    assert not t.overdue(NOW) and t.overdue(NOW + timedelta(days=1))


def test_find_active_matches_all_words_and_ignores_completed(tasks):
    a = tasks.add("English homework unit 3"); tasks.add("Python homework"); b = tasks.add("English speaking practice")
    assert sorted(t.title for t in tasks.find_active("english")) == ["English homework unit 3", "English speaking practice"]
    assert [t.title for t in tasks.find_active("English homework")] == ["English homework unit 3"]
    tasks.complete(a.id)
    assert [t.title for t in tasks.find_active("english homework")] == [] and tasks.find_active("   ") == []


# ------------------------------------------------------------------ qaydlar
@pytest.fixture
def notes(db):
    return NoteStore(db, lambda: NOW)


def test_notes_create_edit_search_organize_delete(notes):
    a = notes.add("English Vocabulary", "serendipity, ubiquitous", ["en", "#words"], "study")
    notes.add("Bozor ro'yxati", "non, sut, tuxum", ["uy"])
    assert a.tags == ["en", "words"] and a.category == "study" and a.created == a.updated
    assert [n.title for n in notes.search("sut")] == ["Bozor ro'yxati"] and [n.title for n in notes.search("ubiquitous")] == ["English Vocabulary"]
    assert [n.title for n in notes.search(tag="words")] == ["English Vocabulary"] and [n.title for n in notes.search(category="study")] == ["English Vocabulary"]
    assert notes.tags() == ["en", "uy", "words"] and notes.categories() == ["study"]
    up = notes.update(a.id, body="yangi matn", pinned=True)
    assert up.body == "yangi matn" and notes.all()[0].id == a.id                      # qadalgan birinchi
    assert notes.delete(a.id) and notes.get(a.id) is None


def test_note_never_overwrites_without_explicit_replace(notes):
    a = notes.add("Reja", "eski")
    with pytest.raises(NoteExists) as e:
        notes.add("reja", "yangi")
    assert e.value.note.id == a.id and notes.get(a.id).body == "eski"
    assert notes.add("Reja", "yangi", replace=True).body == "yangi"
    b = notes.add("Boshqa")
    with pytest.raises(NoteExists):
        notes.update(b.id, title="REJA")                                              # qayta nomlash ham ustiga yozmaydi
    assert notes.get(b.id).title == "Boshqa"


def test_note_body_is_stored_verbatim_and_limited(notes):
    n = notes.add("Kod", "<script>alert(1)</script>\n  ```py\nprint('x')\n```")
    assert notes.get(n.id).body.startswith("<script>")
    assert len(notes.add("Katta", "x" * 100_000).body) == 50_000


# ------------------------------------------------------------------ ingliz tili rejasi
@pytest.fixture
def study(db):
    return StudyStore(db, lambda: NOW)


def test_default_plan_is_60_minutes_and_customizable(study):
    plan = study.plan()
    assert [(a.id, a.minutes) for a in plan] == [("vocabulary", 15), ("grammar", 15), ("listening", 15), ("reading", 10), ("writing", 5)] and study.planned_minutes() == 60
    study.set_plan([Activity("vocabulary", "Words", 20, "v"), Activity("", "Speaking club", 30, "speaking")])
    assert [a.name for a in study.plan()] == ["Words", "Speaking club"] and study.planned_minutes() == 50
    with pytest.raises(ValueError):
        study.set_plan([Activity("a", "", 10)])
    with pytest.raises(ValueError):
        study.set_plan([Activity("a", "x", 0)])
    with pytest.raises(ValueError):
        study.set_plan([Activity("a", "x", 5), Activity("a", "y", 5)])
    study.reset_plan()
    assert study.planned_minutes() == 60


def test_customized_plan_is_not_overwritten_on_restart(path):
    d = Database(path, now=lambda: NOW)
    StudyStore(d, lambda: NOW).set_plan([Activity("x", "Only this", 25)])
    d.close()
    d2 = Database(path, now=lambda: NOW)
    assert [a.name for a in StudyStore(d2, lambda: NOW).plan()] == ["Only this"]
    d2.close()


def test_only_recorded_activity_counts_and_duplicates_are_ignored(study):
    assert study.minutes_on(NOW.date()) == 0 and study.streak() == (0, 0) and study.history() == [] and study.done_ids() == set()    # hech narsa yozilmasa, hech narsa yo'q
    e, created = study.record("vocabulary")
    e2, created2 = study.record("vocabulary", minutes=99)
    assert created and not created2 and e.id == e2.id and study.minutes_on(NOW.date()) == 15           # ikki marta hisoblanmaydi
    study.record("grammar", minutes=12, note="present perfect")
    assert study.minutes_on(NOW.date()) == 27 and study.done_ids() == {"vocabulary", "grammar"}
    assert study.unrecord("grammar") and study.minutes_on(NOW.date()) == 15 and not study.unrecord("grammar")
    with pytest.raises(ValueError):
        study.record("nonexistent")
    with pytest.raises(ValueError):
        study.record("reading", minutes=0)


def test_streak_counts_real_consecutive_days_only(study):
    d = NOW.date()
    study.record("vocabulary", d - timedelta(days=1)); study.record("vocabulary", d - timedelta(days=2)); study.record("vocabulary", d - timedelta(days=3))
    assert study.streak(d) == (3, 3)                                              # bugun hali yozilmagan: kecha tugagan streak saqlanadi
    study.record("grammar", d)
    assert study.streak(d) == (4, 4)
    assert study.streak(d + timedelta(days=2)) == (0, 4)                          # bir kun o'tkazib yuborilsa uziladi, eng uzuni saqlanadi
    study.record("vocabulary", d - timedelta(days=6)); study.record("vocabulary", d - timedelta(days=7))
    assert study.streak(d) == (4, 4)


def test_week_history_and_items(study):
    mon = NOW.date() - timedelta(days=2)
    study.record("vocabulary", mon); study.record("reading", NOW.date())
    week = dict(study.week_minutes())
    assert week[mon] == 15 and week[NOW.date()] == 10 and sum(week.values()) == 25
    assert [(h.day, h.activity_id) for h in study.history()] == [("2026-10-28", "reading"), ("2026-10-26", "vocabulary")]
    w, c1 = study.add_item("word", "ubiquitous", "hamma joyda")
    assert c1 and not study.add_item("word", "Ubiquitous")[1] and study.add_item("grammar", "Present Perfect")[1]
    assert [i.text for i in study.items("word")] == ["ubiquitous"] and len(study.items()) == 2
    assert study.mark_reviewed(w.id).reviews == 1 and study.mark_reviewed(w.id).reviews == 2      # takrorlash soni, "o'rganildi" emas
    with pytest.raises(ValueError):
        study.add_item("phrase", "x")
    assert study.delete_item(w.id) and len(study.items()) == 1


def test_clear_progress_keeps_plan_and_clear_all_resets(study):
    study.record("vocabulary"); study.add_item("word", "x")
    study.set_plan([Activity("only", "Only", 10)])
    study.clear_progress()
    assert study.history() == [] and study.items() == [] and [a.id for a in study.plan()] == ["only"]
    study.record("only"); study.clear_all()
    assert study.history() == [] and study.planned_minutes() == 60


def _schema(conn):
    out = {}
    for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        out[name] = sorted((r[1], r[2].upper(), r[3], r[4], r[5]) for r in conn.execute(f"PRAGMA table_info({name})").fetchall())
    idx = sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchall())
    return out, idx


def test_fresh_schema_is_identical_to_the_migrated_schema(path, tmp_path):
    fresh = Database(tmp_path / "fresh.db", now=lambda: NOW)
    make_v1(path)
    migrated = Database(path, now=lambda: NOW)
    assert _schema(fresh._conn) == _schema(migrated._conn)                      # ikki yo'l bir xil sxema beradi (drift yo'q)
    fresh.close(); migrated.close()
