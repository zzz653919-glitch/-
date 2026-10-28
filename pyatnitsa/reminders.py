"""Eslatmalar: bir martalik va takrorlanuvchi; tahrirlash, kechiktirish, bajarildi, o'chirish; kechikkanlar. SQLite (`db.py`), ilova qayta ishga tushganda saqlanadi.
Takrorlanishdan himoya: bir xil sarlavha + vaqtli faol eslatma ikkinchi marta qo'shilmaydi (`add_unique`)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from .db import Database
from .timeparse import next_occurrence

FMT = "%Y-%m-%dT%H:%M"
RECUR_TYPES = ("interval", "daily", "weekly", "monthly", "weekdays")


@dataclass
class Reminder:
    id: str
    title: str
    due: str                                  # mahalliy vaqt, FMT
    recur: dict | None = None
    done: bool = False
    created: str = ""
    last_fired: str = ""
    completions: int = 0
    notified: bool = False
    source_key: str | None = None             # tizim eslatmalari uchun (masalan o'quv rejasi); foydalanuvchi eslatmalarida None

    @property
    def due_dt(self) -> datetime:
        return datetime.strptime(self.due, FMT)


def valid_recur(r) -> dict | None:
    if not isinstance(r, dict) or r.get("type") not in RECUR_TYPES:
        return None
    try:
        out = {"type": r["type"], "n": max(1, min(100000, int(r.get("n", 1) or 1)))}
    except (TypeError, ValueError):
        return None
    if isinstance(r.get("weekday"), int) and 0 <= r["weekday"] <= 6:
        out["weekday"] = r["weekday"]
    return out


def _row(r) -> Reminder:
    return Reminder(r["id"], r["title"], r["due"], json.loads(r["recur"]) if r["recur"] else None, bool(r["done"]), r["created"], r["last_fired"],
                    r["completions"], bool(r["notified"]), r["source_key"])


class ReminderStore:
    def __init__(self, db: Database, now=datetime.now):
        self.db, self.now = db, now

    # ---- CRUD
    def add_unique(self, title: str, due: datetime, recur: dict | None = None, source_key: str | None = None) -> tuple[Reminder, bool]:
        """-> (eslatma, yangi_yaratildimi). Aynan shunday faol eslatma bor bo'lsa, yangisi yaratilmaydi."""
        title = " ".join(str(title).split())[:200]
        if not title:
            raise ValueError("title")
        recur = valid_recur(recur)
        with self.db._lock:
            if source_key:
                row = self.db.query("SELECT * FROM reminders WHERE source_key=?", (source_key,))
                if row:
                    return _row(row[0]), False
            row = self.db.query("SELECT * FROM reminders WHERE done=0 AND lower(title)=lower(?) AND due=? AND ifnull(source_key,'')=ifnull(?,'')", (title, due.strftime(FMT), source_key))
            if row:
                return _row(row[0]), False
            rid = uuid.uuid4().hex[:8]
            self.db.execute("INSERT INTO reminders(id,title,due,recur,created,source_key) VALUES(?,?,?,?,?,?)",
                            (rid, title, due.strftime(FMT), json.dumps(recur) if recur else None, self.now().strftime(FMT), source_key))
            return self.get(rid), True

    def add(self, title: str, due: datetime, recur: dict | None = None) -> Reminder:
        return self.add_unique(title, due, recur)[0]

    def get(self, rid: str) -> Reminder | None:
        rows = self.db.query("SELECT * FROM reminders WHERE id=?", (rid,))
        return _row(rows[0]) if rows else None

    def by_source(self, source_key: str) -> Reminder | None:
        rows = self.db.query("SELECT * FROM reminders WHERE source_key=?", (source_key,))
        return _row(rows[0]) if rows else None

    def update(self, rid: str, title: str | None = None, due: datetime | None = None, recur: dict | None | bool = False) -> Reminder | None:
        with self.db._lock:
            r = self.get(rid)
            if r is None:
                return None
            if title is not None:
                t = " ".join(title.split())[:200]
                if not t:
                    raise ValueError("title")
                self.db.execute("UPDATE reminders SET title=? WHERE id=?", (t, rid))
            if due is not None:
                self.db.execute("UPDATE reminders SET due=?, notified=0, done=0 WHERE id=?", (due.strftime(FMT), rid))
            if recur is not False:
                v = valid_recur(recur)
                self.db.execute("UPDATE reminders SET recur=? WHERE id=?", (json.dumps(v) if v else None, rid))
            return self.get(rid)

    def postpone(self, rid: str, minutes: int | None = None, to: datetime | None = None) -> Reminder | None:
        """Hozirdan (yoki `to` ga) kechiktirish. Takrorlanuvchi eslatmaning takrori saqlanadi."""
        r = self.get(rid)
        if r is None:
            return None
        target = to or (self.now() + timedelta(minutes=minutes or 10)).replace(second=0, microsecond=0)
        return self.update(rid, due=target)

    def complete(self, rid: str) -> Reminder | None:
        """Bir martalik — bajarildi; takrorlanuvchi — keyingi navbatga o'tadi."""
        with self.db._lock:
            r = self.get(rid)
            if r is None:
                return None
            nxt = next_occurrence(r.due_dt, r.recur, self.now()) if r.recur else None
            if nxt:
                self.db.execute("UPDATE reminders SET due=?, notified=0, completions=completions+1 WHERE id=?", (nxt.strftime(FMT), rid))
            else:
                self.db.execute("UPDATE reminders SET done=1, completions=completions+1 WHERE id=?", (rid,))
            return self.get(rid)

    def reopen(self, rid: str) -> Reminder | None:
        self.db.execute("UPDATE reminders SET done=0, notified=0 WHERE id=?", (rid,))
        return self.get(rid)

    def delete(self, rid: str) -> bool:
        return self.db.execute("DELETE FROM reminders WHERE id=?", (rid,)) > 0

    def delete_by_source(self, source_key: str) -> bool:
        return self.db.execute("DELETE FROM reminders WHERE source_key=?", (source_key,)) > 0

    def clear(self) -> int:
        return self.db.clear("reminders")

    # ---- so'rovlar
    def all(self) -> list[Reminder]:
        return [_row(r) for r in self.db.query("SELECT * FROM reminders ORDER BY done, due")]

    def active(self) -> list[Reminder]:
        return [r for r in self.all() if not r.done]

    def overdue(self, now: datetime | None = None) -> list[Reminder]:
        now = now or self.now()
        return [r for r in self.active() if r.due_dt < now]

    def upcoming(self, now: datetime | None = None, limit: int = 50) -> list[Reminder]:
        now = now or self.now()
        return [r for r in self.active() if r.due_dt >= now][:limit]

    def today(self, now: datetime | None = None) -> list[Reminder]:
        now = now or self.now()
        return [r for r in self.active() if r.due_dt.date() == now.date()]

    def fire_due(self, now: datetime | None = None) -> list[Reminder]:
        """Vaqti kelgan (yoki ilova o'chiq paytida o'tib ketgan) eslatmalar — har biri BIR marta. Takrorlanuvchi keyingi vaqtga o'tadi."""
        now = now or self.now()
        fired: list[Reminder] = []
        with self.db._lock:
            for r in self.active():
                if r.notified or r.due_dt > now:
                    continue
                fired.append(r)
                nxt = next_occurrence(r.due_dt, r.recur, now) if r.recur else None
                if nxt:
                    self.db.execute("UPDATE reminders SET due=?, notified=0, last_fired=? WHERE id=?", (nxt.strftime(FMT), now.strftime(FMT), r.id))
                else:
                    self.db.execute("UPDATE reminders SET notified=1, last_fired=? WHERE id=?", (now.strftime(FMT), r.id))
        return fired


def describe_recur(recur: dict | None, lang: str = "uz") -> str:
    if not recur:
        return {"uz": "bir marta", "ru": "один раз", "en": "once"}.get(lang, "once")
    t, n = recur["type"], recur.get("n", 1)
    names = {
        "uz": {"daily": "har kuni", "weekly": "har hafta", "monthly": "har oy", "weekdays": "ish kunlari", "interval": f"har {n} daqiqada"},
        "ru": {"daily": "каждый день", "weekly": "каждую неделю", "monthly": "каждый месяц", "weekdays": "по будням", "interval": f"каждые {n} мин"},
        "en": {"daily": "every day", "weekly": "every week", "monthly": "every month", "weekdays": "weekdays", "interval": f"every {n} min"},
    }
    return names.get(lang, names["en"])[t]
