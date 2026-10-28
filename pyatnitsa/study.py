"""Ingliz tili o'quv rejalashtiruvchisi (tashkil etish vositasi; kurs yoki lug'at tizimining o'rnini bosmaydi).

Faqat foydalanuvchi AYTGAN/BELGILAGAN faoliyat yoziladi: "o'rgandim" yoki "dars tugadi" deb o'zboshimchalik bilan hisoblanmaydi, hech qanday IELTS bahosi
yoki muddat va'da qilinmaydi. Streak — haqiqiy yozilgan kunlar bo'yicha. Standart reja (60 daqiqa): lug'at 15, grammatika 15, tinglash 15, o'qish 10,
yozish/takrorlash 5 — hammasi tahrirlanadi."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .db import Database

D_FMT, DT_FMT = "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"
DEFAULT_PLAN = [("vocabulary", "Vocabulary", 15, "vocabulary"), ("grammar", "Grammar", 15, "grammar"), ("listening", "Listening", 15, "listening"),
                ("reading", "Reading", 10, "reading"), ("writing", "Writing / review", 5, "writing")]
ITEM_KINDS = ("word", "grammar")


@dataclass
class Activity:
    id: str
    name: str
    minutes: int
    category: str = ""


@dataclass
class LogEntry:
    id: int
    day: str
    activity_id: str
    activity_name: str
    minutes: int
    recorded_at: str
    note: str = ""


@dataclass
class StudyItem:
    id: str
    kind: str
    text: str
    note: str = ""
    added: str = ""
    reviews: int = 0
    last_review: str = ""


class StudyStore:
    def __init__(self, db: Database, now=datetime.now):
        self.db, self.now = db, now
        self._ensure_default_plan()

    # ---- reja
    def _ensure_default_plan(self) -> None:
        if not self.db.query("SELECT 1 FROM study_activities LIMIT 1") and self.db.query("SELECT value FROM meta WHERE key='study_plan_customized'") == []:
            self.reset_plan()

    def reset_plan(self) -> None:
        with self.db.transaction() as c:
            c.execute("DELETE FROM study_activities")
            for i, (aid, name, mins, cat) in enumerate(DEFAULT_PLAN):
                c.execute("INSERT INTO study_activities(id,name,minutes,category,position) VALUES(?,?,?,?,?)", (aid, name, mins, cat, i))
            c.execute("DELETE FROM meta WHERE key='study_plan_customized'")

    def plan(self) -> list[Activity]:
        return [Activity(r["id"], r["name"], r["minutes"], r["category"]) for r in self.db.query("SELECT * FROM study_activities ORDER BY position, rowid")]

    def set_plan(self, activities: list[Activity]) -> None:
        """Rejani to'liq almashtiradi (nom/daqiqa/kategoriya). Eski yozuvlar (log) o'zgarmaydi."""
        clean, seen = [], set()
        for a in activities:
            name = " ".join(str(a.name).split())[:40]
            mins = int(a.minutes)
            if not name or not 1 <= mins <= 600:
                raise ValueError("activity")
            aid = a.id or uuid.uuid4().hex[:8]
            if aid in seen:
                raise ValueError("duplicate id")
            seen.add(aid)
            clean.append((aid, name, mins, " ".join(str(a.category).split())[:30]))
        with self.db.transaction() as c:
            c.execute("DELETE FROM study_activities")
            for i, (aid, name, mins, cat) in enumerate(clean):
                c.execute("INSERT INTO study_activities(id,name,minutes,category,position) VALUES(?,?,?,?,?)", (aid, name, mins, cat, i))
            c.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('study_plan_customized','1')")

    def planned_minutes(self) -> int:
        return sum(a.minutes for a in self.plan())

    # ---- sozlamalar
    def get_setting(self, key: str, default: str = "") -> str:
        rows = self.db.query("SELECT value FROM meta WHERE key=?", ("study_" + key,))
        return rows[0][0] if rows else default

    def set_setting(self, key: str, value: str) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", ("study_" + key, value))

    # ---- yozuvlar (faqat foydalanuvchi belgilaganda)
    def record(self, activity_id: str, day: date | None = None, minutes: int | None = None, note: str = "") -> tuple[LogEntry, bool]:
        """-> (yozuv, yangi_yaratildimi). Shu kun va faoliyat uchun yozuv bo'lsa, ikkinchi marta hisoblanmaydi (takroriy bosish himoyasi)."""
        day = day or self.now().date()
        act = next((a for a in self.plan() if a.id == activity_id), None)
        if act is None:
            raise ValueError("activity")
        mins = act.minutes if minutes is None else int(minutes)
        if not 0 < mins <= 600:
            raise ValueError("minutes")
        with self.db._lock:
            old = self.db.query("SELECT * FROM study_log WHERE day=? AND activity_id=?", (day.strftime(D_FMT), activity_id))
            if old:
                return _log(old[0]), False
            self.db.execute("INSERT INTO study_log(day,activity_id,activity_name,minutes,recorded_at,note) VALUES(?,?,?,?,?,?)",
                            (day.strftime(D_FMT), activity_id, act.name, mins, self.now().strftime(DT_FMT), str(note)[:300]))
            return _log(self.db.query("SELECT * FROM study_log WHERE day=? AND activity_id=?", (day.strftime(D_FMT), activity_id))[0]), True

    def unrecord(self, activity_id: str, day: date | None = None) -> bool:
        """Foydalanuvchi belgini qaytarib olsa (xato bosgan bo'lsa), o'sha yozuv o'chadi."""
        day = day or self.now().date()
        return self.db.execute("DELETE FROM study_log WHERE day=? AND activity_id=?", (day.strftime(D_FMT), activity_id)) > 0

    def done_ids(self, day: date | None = None) -> set[str]:
        day = day or self.now().date()
        return {r["activity_id"] for r in self.db.query("SELECT activity_id FROM study_log WHERE day=?", (day.strftime(D_FMT),))}

    def history(self, limit: int = 200) -> list[LogEntry]:
        return [_log(r) for r in self.db.query("SELECT * FROM study_log ORDER BY day DESC, recorded_at DESC, id DESC LIMIT ?", (limit,))]

    def minutes_on(self, day: date) -> int:
        return self.db.query("SELECT COALESCE(SUM(minutes),0) FROM study_log WHERE day=?", (day.strftime(D_FMT),))[0][0]

    def week_minutes(self, today: date | None = None) -> list[tuple[date, int]]:
        today = today or self.now().date()
        start = today - timedelta(days=today.weekday())
        return [(start + timedelta(days=i), self.minutes_on(start + timedelta(days=i))) for i in range(7)]

    def study_days(self) -> set[date]:
        return {datetime.strptime(r["day"], D_FMT).date() for r in self.db.query("SELECT DISTINCT day FROM study_log")}

    def streak(self, today: date | None = None) -> tuple[int, int]:
        """(joriy, eng uzun). Joriy streak: oxirgi yozilgan kundan orqaga ketma-ket kunlar; bugun hali yozilmagan bo'lsa ham
        kecha tugaganlari saqlanadi (kun tugamaguncha uzilmaydi). Faqat HAQIQIY yozuvlar sanaladi."""
        today = today or self.now().date()
        days = self.study_days()
        cur, d = 0, today if today in days else today - timedelta(days=1)
        while d in days:
            cur += 1
            d -= timedelta(days=1)
        best = run = 0
        prev = None
        for d in sorted(days):
            run = run + 1 if prev and d - prev == timedelta(days=1) else 1
            best = max(best, run)
            prev = d
        return cur, best

    # ---- qiyin so'zlar va grammatika mavzulari
    def add_item(self, kind: str, text: str, note: str = "") -> tuple[StudyItem, bool]:
        text = " ".join(str(text).split())[:120]
        if kind not in ITEM_KINDS or not text:
            raise ValueError("item")
        with self.db._lock:
            old = self.db.query("SELECT * FROM study_items WHERE kind=? AND lower(text)=lower(?)", (kind, text))
            if old:
                return _item(old[0]), False
            iid = uuid.uuid4().hex[:8]
            self.db.execute("INSERT INTO study_items(id,kind,text,note,added) VALUES(?,?,?,?,?)", (iid, kind, text, str(note)[:300], self.now().strftime(DT_FMT)))
            return _item(self.db.query("SELECT * FROM study_items WHERE id=?", (iid,))[0]), True

    def items(self, kind: str = "") -> list[StudyItem]:
        q, p = ("SELECT * FROM study_items WHERE kind=? ORDER BY added DESC", (kind,)) if kind else ("SELECT * FROM study_items ORDER BY added DESC", ())
        return [_item(r) for r in self.db.query(q, p)]

    def mark_reviewed(self, iid: str) -> StudyItem | None:
        """Foydalanuvchi takrorlaganini belgilaydi (bu "o'rganildi" degani EMAS — faqat takrorlashlar soni)."""
        self.db.execute("UPDATE study_items SET reviews=reviews+1, last_review=? WHERE id=?", (self.now().strftime(DT_FMT), iid))
        rows = self.db.query("SELECT * FROM study_items WHERE id=?", (iid,))
        return _item(rows[0]) if rows else None

    def delete_item(self, iid: str) -> bool:
        return self.db.execute("DELETE FROM study_items WHERE id=?", (iid,)) > 0

    # ---- mashq sessiyalari (viktorina/talaffuz/tinglash): faqat HAQIQATDA yakunlangan sessiyalar yoziladi
    def record_session(self, kind: str, level: str, total: int, correct: int) -> None:
        now = self.now()
        self.db.execute("INSERT INTO english_sessions(kind,level,total,correct,finished_at,day) VALUES(?,?,?,?,?,?)",
                        (kind, level, int(total), int(correct), now.strftime(DT_FMT), now.date().isoformat()))

    def sessions(self, limit: int = 20) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT kind,level,total,correct,finished_at,day FROM english_sessions ORDER BY id DESC LIMIT ?", (limit,))]

    def session_stats(self) -> dict:
        r = self.db.query("SELECT COUNT(*), COALESCE(SUM(total),0), COALESCE(SUM(correct),0) FROM english_sessions")[0]
        return {"sessions": r[0], "questions": r[1], "correct": r[2]}

    def clear_progress(self) -> int:
        """Yozilgan tarix, mashq sessiyalari va qiyin so'zlar o'chadi (reja saqlanadi)."""
        return self.db.clear("study_log", "study_items", "english_sessions")

    def clear_all(self) -> int:
        n = self.db.clear("study_log", "study_items", "study_activities", "english_sessions")
        self.db.execute("DELETE FROM meta WHERE key LIKE 'study_%'")
        self.reset_plan()
        return n


def _log(r) -> LogEntry:
    return LogEntry(r["id"], r["day"], r["activity_id"], r["activity_name"], r["minutes"], r["recorded_at"], r["note"])


def _item(r) -> StudyItem:
    return StudyItem(r["id"], r["kind"], r["text"], r["note"], r["added"], r["reviews"], r["last_review"])
