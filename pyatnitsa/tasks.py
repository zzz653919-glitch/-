"""Vazifalar: sarlavha, tavsif, muddat, ustuvorlik (past/o'rta/yuqori), holat (bajarilishi kerak / jarayonda / bajarilgan), kategoriya.
Qidirish, filtrlash, kunlik va haftalik ko'rinish, progress. SQLite (`db.py`)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .db import Database
from .files import _tokens, _variants

PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "doing", "done")
DT_FMT, D_FMT = "%Y-%m-%dT%H:%M", "%Y-%m-%d"


@dataclass
class Task:
    id: str
    title: str
    description: str = ""
    due: str = ""                             # "" | YYYY-MM-DD | YYYY-MM-DDTHH:MM
    priority: str = "medium"
    status: str = "todo"
    category: str = ""
    created: str = ""
    updated: str = ""
    completed_at: str = ""

    @property
    def has_due(self) -> bool:
        return bool(self.due)

    @property
    def due_date(self) -> date | None:
        return datetime.strptime(self.due[:10], D_FMT).date() if self.due else None

    def due_dt(self) -> datetime | None:
        if not self.due:
            return None
        return datetime.strptime(self.due, DT_FMT) if len(self.due) > 10 else datetime.strptime(self.due, D_FMT).replace(hour=23, minute=59)

    def overdue(self, now: datetime) -> bool:
        """Bajarilmagan va muddati o'tgan. Faqat sana berilgan bo'lsa, o'sha kun tugagandan keyin kechikkan hisoblanadi."""
        if self.status == "done" or not self.due:
            return False
        if len(self.due) > 10:
            return datetime.strptime(self.due, DT_FMT) < now
        return self.due_date < now.date()


def fmt_due(due: datetime | date | None) -> str:
    if due is None:
        return ""
    if isinstance(due, datetime):
        return due.strftime(DT_FMT)
    return due.strftime(D_FMT)


def _row(r) -> Task:
    return Task(r["id"], r["title"], r["description"], r["due"], r["priority"], r["status"], r["category"], r["created"], r["updated"], r["completed_at"])


class TaskStore:
    def __init__(self, db: Database, now=datetime.now):
        self.db, self.now = db, now

    def add_unique(self, title: str, description: str = "", due: datetime | date | None = None, priority: str = "medium", status: str = "todo",
                   category: str = "") -> tuple[Task, bool]:
        title = " ".join(str(title).split())[:200]
        if not title:
            raise ValueError("title")
        if priority not in PRIORITIES or status not in STATUSES:
            raise ValueError("priority/status")
        d = fmt_due(due)
        with self.db._lock:
            same = self.db.query("SELECT * FROM tasks WHERE status!='done' AND lower(title)=lower(?) AND due=?", (title, d))
            if same:
                return _row(same[0]), False          # tasodifan ikki marta bosish/aytish takror yaratmaydi
            tid, stamp = uuid.uuid4().hex[:8], self.now().strftime(DT_FMT)
            self.db.execute("INSERT INTO tasks(id,title,description,due,priority,status,category,created,updated,completed_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (tid, title, str(description)[:5000], d, priority, status, " ".join(str(category).split())[:40], stamp, stamp, stamp if status == "done" else ""))
            return self.get(tid), True

    def add(self, *a, **kw) -> Task:
        return self.add_unique(*a, **kw)[0]

    def get(self, tid: str) -> Task | None:
        rows = self.db.query("SELECT * FROM tasks WHERE id=?", (tid,))
        return _row(rows[0]) if rows else None

    def update(self, tid: str, **fields) -> Task | None:
        cur = self.get(tid)
        if cur is None:
            return None
        sets, vals = [], []
        for k, v in fields.items():
            if k == "title":
                v = " ".join(str(v).split())[:200]
                if not v:
                    raise ValueError("title")
            elif k == "description":
                v = str(v)[:5000]
            elif k == "due":
                v = fmt_due(v) if not isinstance(v, str) else v
            elif k == "priority":
                if v not in PRIORITIES:
                    raise ValueError("priority")
            elif k == "status":
                if v not in STATUSES:
                    raise ValueError("status")
                sets.append("completed_at=?"); vals.append(self.now().strftime(DT_FMT) if v == "done" and cur.status != "done" else ("" if v != "done" else cur.completed_at))
            elif k == "category":
                v = " ".join(str(v).split())[:40]
            else:
                raise ValueError(k)
            sets.append(f"{k}=?"); vals.append(v)
        sets.append("updated=?"); vals.append(self.now().strftime(DT_FMT))
        self.db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", (*vals, tid))
        return self.get(tid)

    def set_status(self, tid: str, status: str) -> Task | None:
        return self.update(tid, status=status)

    def complete(self, tid: str) -> Task | None:
        return self.set_status(tid, "done")

    def delete(self, tid: str) -> bool:
        return self.db.execute("DELETE FROM tasks WHERE id=?", (tid,)) > 0

    def clear(self) -> int:
        return self.db.clear("tasks")

    # ---- so'rovlar
    def all(self) -> list[Task]:
        pr = {"high": 0, "medium": 1, "low": 2}
        return sorted((_row(r) for r in self.db.query("SELECT * FROM tasks")),
                      key=lambda t: (t.status == "done", t.due or "9999", pr[t.priority], t.title.lower()))

    def categories(self) -> list[str]:
        return sorted({t.category for t in self.all() if t.category}, key=str.lower)

    def view(self, name: str = "all", now: datetime | None = None) -> list[Task]:
        """all | today | week | overdue | active."""
        now = now or self.now()
        today, out = now.date(), []
        for t in self.all():
            dd = t.due_date
            if name == "all":
                out.append(t)
            elif name == "active" and t.status != "done":
                out.append(t)
            elif name == "overdue" and t.overdue(now):
                out.append(t)
            elif name == "today" and dd == today:
                out.append(t)
            elif name == "week" and dd and today <= dd <= today + timedelta(days=6):
                out.append(t)
        return out

    def search(self, text: str = "", status: str = "", category: str = "", priority: str = "", view: str = "all", now: datetime | None = None) -> list[Task]:
        toks = _tokens(text)
        out = []
        for t in self.view(view, now):
            if status and t.status != status or category and t.category.lower() != category.lower() or priority and t.priority != priority:
                continue
            hay = " ".join(_tokens(t.title + " " + t.description + " " + t.category))
            if all(any(v in hay for v in _variants(k)) for k in toks):
                out.append(t)
        return out

    def find_active(self, query: str) -> list[Task]:
        """Ovoz bilan «bajarildi» belgilash uchun: sarlavhada barcha so'zlar bor faol vazifalar."""
        return self.search(query, view="active") if _tokens(query) else []

    @staticmethod
    def progress(tasks: list[Task]) -> tuple[int, int]:
        """(bajarilgan, jami) — ko'rsatilgan ro'yxat bo'yicha."""
        return sum(1 for t in tasks if t.status == "done"), len(tasks)
