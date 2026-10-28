"""Mahalliy SQLite ombori (`%APPDATA%\\Pyatnitsa\\productivity.db`): eslatmalar, vazifalar, qaydlar, ingliz tili rejasi.

Ishonchlilik:
  * Versiyalangan migratsiyalar (`PRAGMA user_version`). Mavjud ma'lumotli bazani yangilashdan OLDIN to'liq zaxira nusxa olinadi (`*.bak-vN-vaqt`, oxirgi 5 ta).
  * Migratsiya bitta tranzaksiyada: xato bo'lsa hech narsa o'zgarmaydi (baza avvalgi holatda qoladi).
  * Buzilgan baza `.corrupt-vaqt` ga ko'chiriladi (ma'lumot o'chirilmaydi) va bo'sh baza yaratiladi; foydalanuvchiga `notice` orqali aytiladi.
  * Ilovadan yangiroq versiyali baza o'zgartirilmaydi (xotirada vaqtinchalik bazaga o'tiladi).
Ma'lumotlar faqat shu kompyuterda; hech qayerga yuborilmaydi.
"""
from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2
KEEP_BACKUPS = 5

# --- migratsiyalar: har biri `(sqlite3.Connection)` oladi va bitta tranzaksiya ichida bajariladi ---
_V1 = """
CREATE TABLE reminders (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, due TEXT NOT NULL, recur TEXT, done INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL DEFAULT '', last_fired TEXT NOT NULL DEFAULT '', completions INTEGER NOT NULL DEFAULT 0, notified INTEGER NOT NULL DEFAULT 0);
CREATE INDEX idx_reminders_due ON reminders(due);
CREATE TABLE notes (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]', pinned INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT '');
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""
_V2 = """
ALTER TABLE notes ADD COLUMN category TEXT NOT NULL DEFAULT '';
ALTER TABLE reminders ADD COLUMN source_key TEXT;
CREATE UNIQUE INDEX idx_reminders_source ON reminders(source_key) WHERE source_key IS NOT NULL;
CREATE TABLE tasks (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
    status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','doing','done')),
    category TEXT NOT NULL DEFAULT '', created TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '');
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE TABLE study_activities (id TEXT PRIMARY KEY, name TEXT NOT NULL, minutes INTEGER NOT NULL, category TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0);
CREATE TABLE study_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, activity_id TEXT NOT NULL, activity_name TEXT NOT NULL, minutes INTEGER NOT NULL,
    recorded_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', UNIQUE(day, activity_id));
CREATE INDEX idx_study_day ON study_log(day);
CREATE TABLE study_items (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('word','grammar')), text TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
    added TEXT NOT NULL DEFAULT '', reviews INTEGER NOT NULL DEFAULT 0, last_review TEXT NOT NULL DEFAULT '');
"""


# Yangi (bo'sh) baza uchun to'liq joriy sxema — migratsiya yo'lidan MUSTAQIL (migratsiyadagi xato yangi/xotiradagi bazani buzmasin).
# Migratsiya natijasi bilan bir xilligi testda tekshiriladi.
_FRESH = """
CREATE TABLE reminders (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, due TEXT NOT NULL, recur TEXT, done INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL DEFAULT '', last_fired TEXT NOT NULL DEFAULT '', completions INTEGER NOT NULL DEFAULT 0, notified INTEGER NOT NULL DEFAULT 0, source_key TEXT);
CREATE INDEX idx_reminders_due ON reminders(due);
CREATE UNIQUE INDEX idx_reminders_source ON reminders(source_key) WHERE source_key IS NOT NULL;
CREATE TABLE notes (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '[]', pinned INTEGER NOT NULL DEFAULT 0,
    created TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '');
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE tasks (
    id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', due TEXT NOT NULL DEFAULT '',
    priority TEXT NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
    status TEXT NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','doing','done')),
    category TEXT NOT NULL DEFAULT '', created TEXT NOT NULL DEFAULT '', updated TEXT NOT NULL DEFAULT '', completed_at TEXT NOT NULL DEFAULT '');
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE TABLE study_activities (id TEXT PRIMARY KEY, name TEXT NOT NULL, minutes INTEGER NOT NULL, category TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL DEFAULT 0);
CREATE TABLE study_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, day TEXT NOT NULL, activity_id TEXT NOT NULL, activity_name TEXT NOT NULL, minutes INTEGER NOT NULL,
    recorded_at TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', UNIQUE(day, activity_id));
CREATE INDEX idx_study_day ON study_log(day);
CREATE TABLE study_items (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL CHECK (kind IN ('word','grammar')), text TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
    added TEXT NOT NULL DEFAULT '', reviews INTEGER NOT NULL DEFAULT 0, last_review TEXT NOT NULL DEFAULT '');
"""


def _script(sql: str):
    def run(conn: sqlite3.Connection) -> None:
        for stmt in [s.strip() for s in sql.split(";\n") if s.strip()]:
            conn.execute(stmt)
    return run


MIGRATIONS = {1: _script(_V1), 2: _script(_V2)}      # versiya -> funksiya (1 dan SCHEMA_VERSION gacha)


class Database:
    def __init__(self, path: Path | str, now=datetime.now):
        self.path = Path(path) if str(path) != ":memory:" else None
        self.now = now
        self._lock = threading.RLock()
        self.version = 0                              # har bir o'zgarishda oshadi (interfeys yangilanishi uchun)
        self.notice = ""                              # foydalanuvchiga ko'rsatiladigan xabar (tiklash/migratsiya)
        self.persistent = True
        self.backups: list[Path] = []
        self._conn = self._open()

    # ------------------------------------------------------------------ ochish va migratsiya
    def _stamp(self) -> str:
        return self.now().strftime("%Y%m%d-%H%M%S")

    def _connect(self, target) -> sqlite3.Connection:
        conn = sqlite3.connect(str(target) if target != ":memory:" else ":memory:", check_same_thread=False, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _open(self) -> sqlite3.Connection:
        if self.path is None:
            return self._memory()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            log.exception("Ma'lumotlar papkasi yaratilmadi")
            return self._memory("Ma'lumotlar papkasiga yozib bo'lmadi: vaqtincha xotirada ishlayapti")
        if self.path.exists() and self.path.stat().st_size > 0 and not self._healthy():
            bad = self.path.with_name(f"{self.path.name}.corrupt-{self._stamp()}")
            try:
                shutil.move(str(self.path), str(bad))
                self.notice = f"Ma'lumotlar bazasi buzilgan edi; nusxasi saqlandi: {bad.name}. Yangi bo'sh baza yaratildi."
            except OSError:
                return self._memory("Buzilgan bazani ko'chirib bo'lmadi: vaqtincha xotirada ishlayapti")
        try:
            conn = self._connect(self.path)
            self._migrate(conn)
            return conn
        except _TooNew as e:
            return self._memory(str(e))
        except Exception as e:  # noqa: BLE001 - migratsiya yoki ochish xatosi ilovani qulatmaydi; asl fayl o'zgarmaydi
            log.exception("Bazani ochib bo'lmadi")
            return self._memory(f"Ma'lumotlar bazasi ochilmadi yoki yangilanmadi ({type(e).__name__}); fayl o'zgartirilmadi, vaqtincha xotirada ishlayapti")

    def _healthy(self) -> bool:
        try:
            c = sqlite3.connect(str(self.path), timeout=5)
            try:
                return c.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            finally:
                c.close()
        except sqlite3.Error:
            return False

    def _memory(self, notice: str = "") -> sqlite3.Connection:
        self.persistent = False
        if notice:
            self.notice = notice
        conn = self._connect(":memory:")
        self._migrate(conn, backup=False)
        return conn

    def _migrate(self, conn: sqlite3.Connection, backup: bool = True) -> None:
        cur = conn.execute("PRAGMA user_version").fetchone()[0]
        if cur > SCHEMA_VERSION:
            conn.close()
            raise _TooNew(f"Baza ilovaning yangiroq versiyasida yaratilgan (v{cur} > v{SCHEMA_VERSION}); o'zgartirilmadi, vaqtincha xotirada ishlayapti")
        if cur == SCHEMA_VERSION:
            return
        if cur == 0:                                   # yangi baza: to'liq joriy sxema (migratsiya yo'lisiz)
            conn.execute("BEGIN")
            try:
                _script(_FRESH)(conn)
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            return
        if backup and cur > 0 and self.path is not None:
            self._backup(conn, cur)
        for v in range(cur + 1, SCHEMA_VERSION + 1):
            try:
                conn.execute("BEGIN")
                MIGRATIONS[v](conn)
                conn.execute(f"PRAGMA user_version={v}")
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                log.exception("Migratsiya v%d bajarilmadi; baza o'zgarmadi", v)
                raise
        if cur > 0:
            self.notice = self.notice or f"Ma'lumotlar bazasi v{cur} dan v{SCHEMA_VERSION} ga yangilandi; mavjud ma'lumotlar saqlandi (zaxira: {self.backups[-1].name if self.backups else '—'})."

    def _backup(self, conn: sqlite3.Connection, version: int) -> None:
        dest = self.path.with_name(f"{self.path.name}.bak-v{version}-{self._stamp()}")
        out = sqlite3.connect(str(dest))
        try:
            conn.backup(out)                          # SQLite'ning o'z zaxira mexanizmi: izchil nusxa
        finally:
            out.close()
        self.backups.append(dest)
        old = sorted(self.path.parent.glob(f"{self.path.name}.bak-*"))
        for f in old[:-KEEP_BACKUPS]:
            try:
                f.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------ ishlatish
    @contextmanager
    def transaction(self):
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield self._conn
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            finally:
                self.version += 1

    def query(self, sql: str, params=()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def execute(self, sql: str, params=()) -> int:
        with self.transaction() as c:
            return c.execute(sql, params).rowcount

    def clear(self, *tables: str) -> int:
        """Berilgan jadvallardagi BARCHA yozuvlarni o'chiradi (foydalanuvchi sozlamalarda tasdiqlagandan keyin)."""
        allowed = {"reminders", "tasks", "notes", "study_log", "study_items", "study_activities"}
        n = 0
        with self.transaction() as c:
            for t in tables:
                if t not in allowed:
                    raise ValueError(t)
                n += c.execute(f"DELETE FROM {t}").rowcount
        return n

    def user_version(self) -> int:
        return self.query("PRAGMA user_version")[0][0]

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass


class _TooNew(Exception):
    pass
