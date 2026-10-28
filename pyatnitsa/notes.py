"""Qaydlar: yaratish, qidirish, tahrirlash, kategoriya va teglar, qadash. SQLite (`db.py`).
Mavjud sarlavha ustiga yozish faqat foydalanuvchi aniq tanlagandan keyin (`replace=True`); aks holda `NoteExists`."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .db import Database
from .files import _tokens, _variants

FMT = "%Y-%m-%dT%H:%M:%S"
MAX_BODY = 50_000


class NoteExists(Exception):
    def __init__(self, note: "Note"):
        super().__init__(note.title)
        self.note = note


@dataclass
class Note:
    id: str
    title: str
    body: str = ""
    tags: list[str] = field(default_factory=list)
    pinned: bool = False
    created: str = ""
    updated: str = ""
    category: str = ""


def _clean_tags(tags) -> list[str]:
    out: list[str] = []
    for t in tags or []:
        t = " ".join(str(t).split())[:30].lstrip("#")
        if t and t.lower() not in [x.lower() for x in out]:
            out.append(t)
    return out[:20]


def _row(r) -> Note:
    try:
        tags = json.loads(r["tags"])
    except ValueError:
        tags = []
    return Note(r["id"], r["title"], r["body"], _clean_tags(tags), bool(r["pinned"]), r["created"], r["updated"], r["category"])


class NoteStore:
    def __init__(self, db: Database, now=datetime.now):
        self.db, self.now = db, now

    def get(self, nid: str) -> Note | None:
        rows = self.db.query("SELECT * FROM notes WHERE id=?", (nid,))
        return _row(rows[0]) if rows else None

    def find_title(self, title: str) -> Note | None:
        rows = self.db.query("SELECT * FROM notes WHERE lower(title)=lower(?)", (" ".join(title.split()),))
        return _row(rows[0]) if rows else None

    def add(self, title: str, body: str = "", tags=None, category: str = "", replace: bool = False) -> Note:
        title = " ".join(str(title).split())[:120]
        if not title:
            raise ValueError("title")
        stamp = self.now().strftime(FMT)
        with self.db._lock:
            same = self.find_title(title)
            if same is not None and not replace:
                raise NoteExists(same)
            if same is not None:
                self.db.execute("UPDATE notes SET body=?, tags=?, category=?, updated=? WHERE id=?",
                                (str(body)[:MAX_BODY], json.dumps(_clean_tags(tags), ensure_ascii=False), " ".join(category.split())[:40], stamp, same.id))
                return self.get(same.id)
            nid = uuid.uuid4().hex[:8]
            self.db.execute("INSERT INTO notes(id,title,body,tags,pinned,created,updated,category) VALUES(?,?,?,?,0,?,?,?)",
                            (nid, title, str(body)[:MAX_BODY], json.dumps(_clean_tags(tags), ensure_ascii=False), stamp, stamp, " ".join(category.split())[:40]))
            return self.get(nid)

    def add_auto(self, title: str, body: str = "", tags=None, category: str = "") -> tuple[Note, str]:
        """Mavjud qayd ustiga yozmaydi: nom band bo'lsa «(2)», «(3)» ... qo'shiladi. -> (qayd, asl_nom_band_bo'lsa_asl_nom_aks_holda_"")."""
        base, k = " ".join(str(title).split())[:110], 1
        t = base
        while True:
            try:
                return self.add(t, body, tags, category), (base if k > 1 else "")
            except NoteExists:
                k += 1
                t = f"{base} ({k})"

    def update(self, nid: str, title: str | None = None, body: str | None = None, tags=None, pinned: bool | None = None, category: str | None = None) -> Note | None:
        with self.db._lock:
            n = self.get(nid)
            if n is None:
                return None
            if title is not None:
                t = " ".join(title.split())[:120]
                if not t:
                    raise ValueError("title")
                other = self.find_title(t)
                if other is not None and other.id != nid:
                    raise NoteExists(other)                      # boshqa qayd ustiga yozilmaydi
                self.db.execute("UPDATE notes SET title=? WHERE id=?", (t, nid))
            if body is not None:
                self.db.execute("UPDATE notes SET body=? WHERE id=?", (str(body)[:MAX_BODY], nid))
            if tags is not None:
                self.db.execute("UPDATE notes SET tags=? WHERE id=?", (json.dumps(_clean_tags(tags), ensure_ascii=False), nid))
            if pinned is not None:
                self.db.execute("UPDATE notes SET pinned=? WHERE id=?", (1 if pinned else 0, nid))
            if category is not None:
                self.db.execute("UPDATE notes SET category=? WHERE id=?", (" ".join(category.split())[:40], nid))
            self.db.execute("UPDATE notes SET updated=? WHERE id=?", (self.now().strftime(FMT), nid))
            return self.get(nid)

    def delete(self, nid: str) -> bool:
        return self.db.execute("DELETE FROM notes WHERE id=?", (nid,)) > 0

    def clear(self) -> int:
        return self.db.clear("notes")

    def all(self) -> list[Note]:
        return [_row(r) for r in self.db.query("SELECT * FROM notes ORDER BY pinned DESC, updated DESC")]

    def tags(self) -> list[str]:
        seen: dict[str, str] = {}
        for n in self.all():
            for t in n.tags:
                seen.setdefault(t.lower(), t)
        return sorted(seen.values(), key=str.lower)

    def categories(self) -> list[str]:
        return sorted({n.category for n in self.all() if n.category}, key=str.lower)

    def search(self, query: str = "", tag: str = "", category: str = "") -> list[Note]:
        toks = _tokens(query)
        out = []
        for n in self.all():
            if tag and tag.lower() not in [t.lower() for t in n.tags]:
                continue
            if category and n.category.lower() != category.lower():
                continue
            hay = " ".join(_tokens(n.title + " " + n.body + " " + " ".join(n.tags) + " " + n.category))
            if all(any(v in hay for v in _variants(t)) for t in toks):
                out.append(n)
        return out
