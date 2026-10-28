"""Tasdiqlangan buyruqni bajarish. Faqat `_actions` ichidagi qat'iy funksiyalar chaqiriladi; javoblar uz / ru / en."""
from __future__ import annotations

import logging
import threading
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import apps, files as fs, health, services
from .db import Database
from .notes import NoteStore
from .reminders import FMT as REM_FMT, ReminderStore, describe_recur
from .study import StudyStore
from .tasks import TaskStore
from . import english
from .commands import ALLOWED_ACTIONS, Command
from .i18n import T, app_title
from .settings import Settings, data_dir

log = logging.getLogger(__name__)

MAX_SHOWN = 50


@dataclass
class Result:
    ok: bool
    message: str
    spoken: str | None = None      # ovozda aytiladigan qisqa variant
    files: list | None = None      # fayl qidirish/ro'yxat natijasi (FileEntry) — tanlash va ochish uchun
    then: str = ""                 # "open" — foydalanuvchi ochishni so'ragan: topilgach tanlash/tasdiq kerak
    fuzzy: bool = False            # aniq nom topilmadi, o'xshashlar — hech qachon avtomatik ochilmaydi
    changed: str = ""              # "reminders" | "tasks" | "notes" | "study" — interfeys ro'yxatni yangilasin
    nav: str = ""                  # interfeysda ochiladigan sahifa kaliti (masalan "study")
    ui: str = ""                   # asosiy oqimda bajariladigan amal: "screenshot" | "clipboard:read|explain|summarize" | "mic_status"
    lesson: tuple | None = None    # ("quiz"|"pronunciation"|"listening", daraja, soni) — boshqaruvchi mashqni boshlaydi
    ai_prompt: str = ""            # AI'ga yuboriladigan savol (masalan, lug'atda yo'q so'z tarjimasi)


@dataclass
class FileIssue:
    kind: str                      # no_roots | scope_denied | ask_name
    message: str
    hint: Path | None = None       # scope_denied: ruxsat so'raladigan papka


def fmt_num(x: float, digits: int = 2) -> str:
    s = f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s.rstrip("0").rstrip(",") if "," in s else s


class Executor:
    def __init__(self, settings: Settings, platform: apps.Platform | None = None,
                 monitor: health.HealthMonitor | None = None, fetch=services.get_json, now=datetime.now, files: fs.FileAccess | None = None,
                 db: Database | None = None, net=services.internet_check):
        self.net = net
        self.settings, self.platform = settings, platform or apps.Platform()
        self.monitor = monitor or health.HealthMonitor()
        self.fetch, self.now = fetch, now
        self.files = files or fs.FileAccess(settings)
        self._db, self._stores = db, {}
        self.cancel_event = threading.Event()          # qidiruvni to'xtatish (yopilish / foydalanuvchi bekor qilishi)
        h = self._health
        self._actions = {
            "find_files": self._find_files, "list_files": self._list_files, "open_file": self._open_file,
            "reminder_add": self._reminder_add, "reminders_show": self._reminders_show, "note_add": self._note_add, "notes_show": self._notes_show,
            "task_add": self._task_add, "tasks_show": self._tasks_show, "task_complete": self._task_complete,
            "study_show": self._study_show, "study_done": self._study_done, "study_progress": self._study_progress,
            "media": self._media,
            "window": self._window, "screenshot": self._screenshot, "clipboard": self._clipboard, "ui": self._ui,
            "youtube_search": self._youtube_search, "open_site": self._open_site, "net_check": self._net_check, "specs": self._specs, "english": self._english,
            "open_app": self._open_app, "new_window": self._new_window, "search": self._search,
            "rate_usd": self._rate, "convert_usd": self._convert, "weather": self._weather, "time": self._time,
            "health_status": lambda c, l: h(l, health.status_text),
            "health_cpu": lambda c, l: h(l, health.cpu_text),
            "health_ram": lambda c, l: h(l, health.ram_text),
            "health_disk": lambda c, l: h(l, health.disk_text),
            "health_temps": lambda c, l: h(l, health.temps_text),
            "health_gpu": lambda c, l: h(l, health._gpu_text),
            "health_battery": lambda c, l: h(l, health._batt_text),
            "health_uptime": lambda c, l: h(l, health.uptime_text),
            "health_full": lambda c, l: h(l, health.full_report, spoken=health.status_text),
            "health_report": self._report, "health_top": self._top, "speedup_advice": self._speedup,
            "admin_info": lambda c, l: Result(True, T("admin.ok", l), T("admin.say", l)),
        }
        assert set(self._actions) == set(ALLOWED_ACTIONS)

    # ---- ruxsat tekshiruvi (tasdiq so'ralmasdan oldin ham chaqiriladi)
    def check_allowed(self, cmd: Command, lang: str = "uz") -> str | None:
        """None — ruxsat bor; aks holda foydalanuvchiga tushuntirish."""
        if cmd.action not in self._actions:
            return T("not_allowed", lang)
        if cmd.action == "open_app":
            app_id = cmd.args.get("app", "")
            if app_id not in apps.APPS:
                return T("not_allowed", lang)
            if not self.settings.is_app_allowed(app_id):
                return T("disabled", lang, title=app_title(app_id, lang))
        elif cmd.action in ("new_window", "search"):
            key = "new_window" if cmd.action == "new_window" else "search"
            if not self.settings.is_app_allowed(key):
                return T("disabled", lang, title=app_title(key, lang))
        return None

    # ---- mahalliy ma'lumotlar (SQLite) — birinchi ishlatilganda ochiladi
    @property
    def db(self) -> Database:
        if self._db is None:
            self._db = Database(data_dir() / "productivity.db", now=self.now)
        return self._db

    def _store(self, name: str, cls):
        if name not in self._stores:
            self._stores[name] = cls(self.db, self.now)
        return self._stores[name]

    reminders = property(lambda self: self._store("reminders", ReminderStore))
    tasks = property(lambda self: self._store("tasks", TaskStore))
    notes = property(lambda self: self._store("notes", NoteStore))
    study = property(lambda self: self._store("study", StudyStore))

    # ---- fayl buyruqlari: bajarishdan oldingi tekshiruv (ruxsat yo'q / nom kerak)
    @property
    def last_results(self) -> list[fs.FileEntry]:
        return list(self.files.recent.values())

    def file_issue(self, cmd: Command, lang: str = "uz") -> FileIssue | None:
        if cmd.action not in ("find_files", "list_files"):
            return None
        alias = cmd.args.get("folder") or ""
        if not self.files.roots():
            return FileIssue("no_roots", T("files.no_roots", lang), self.platform.folder_path(alias) if alias else None)
        if alias:
            kp = self.platform.folder_path(alias)
            if not self.files.scope(kp):
                return FileIssue("scope_denied", T("files.scope_denied", lang, folder=T(f"files.folder.{alias}", lang)), kp)
        a = cmd.args
        if cmd.action == "find_files" and a.get("bare"):
            has_recent = bool(self.files.recent)
            if (a.get("ref") and not has_recent and not a.get("latest")) or (a.get("then") == "open" and not a.get("ref") and not alias and not a.get("latest")):
                return FileIssue("ask_name", T("files.ask_name", lang))
        return None

    def _scope(self, alias: str) -> list[Path] | None:
        """None — hamma ruxsat etilgan ildizlar; ro'yxat — taniqli papka bo'yicha cheklangan ildizlar."""
        return self.files.scope(self.platform.folder_path(alias)) if alias else None

    def execute(self, cmd: Command, lang: str = "uz") -> Result:
        denied = self.check_allowed(cmd, lang)
        if denied:
            return Result(False, denied)
        try:
            return self._actions[cmd.action](cmd, lang)
        except services.NetworkError:
            log.warning("Tarmoq xatosi: %s", cmd.action, exc_info=True)
            return Result(False, T("no_net", lang))
        except services.DataError as e:
            return Result(False, T("data_err", lang, err=e))
        except Exception as e:  # noqa: BLE001
            log.exception("Buyruq xatosi: %s", cmd.action)
            return Result(False, T("error", lang, err=e))

    # ---- ochish: xabar faqat amal haqiqatan boshlangandan keyin beriladi
    def _open_app(self, cmd: Command, lang: str) -> Result:
        app_id = cmd.args["app"]
        spec, title = apps.APPS[app_id], app_title(app_id, lang)
        try:
            if spec.kind == "exe":
                path = self.platform.find_executable(app_id)
                if not path:
                    return Result(False, T("open.notfound", lang, title=title))
                self.platform.start_exe(path)
            elif spec.kind == "uri":
                self.platform.open_uri(app_id)
            elif spec.kind == "folder":
                path = self.platform.folder_path(app_id)
                if not path or not path.is_dir():
                    return Result(False, T("open.notfound", lang, title=title))
                self.platform.open_folder(path)
            else:
                self.platform.open_url(apps.URLS[app_id])
        except Exception as e:  # noqa: BLE001
            log.warning("Ochilmadi: %s", app_id, exc_info=True)
            return Result(False, T("open.failed", lang, title=title, err=e))
        return Result(True, T("open.ok", lang, title=title))

    def _new_window(self, cmd: Command, lang: str) -> Result:
        title = app_title("new_window", lang)
        try:
            self.platform.open_new_window(apps.URLS["browser"])
        except Exception as e:  # noqa: BLE001
            return Result(False, T("open.failed", lang, title=title, err=e))
        return Result(True, T("open.ok", lang, title=title))

    def _search(self, cmd: Command, lang: str) -> Result:
        q = str(cmd.args.get("query", "")).strip()
        if not q:
            return Result(False, T("cl.search", lang))
        try:
            self.platform.open_url("https://www.google.com/search?" + urllib.parse.urlencode({"q": q}))
        except Exception as e:  # noqa: BLE001
            return Result(False, T("open.failed", lang, title="Google", err=e))
        return Result(True, T("search.ok", lang, q=q))

    # ---- ma'lumot
    def _rate(self, cmd: Command, lang: str) -> Result:
        rate, date = services.usd_rate(self.fetch)
        kw = dict(rate=fmt_num(rate), date=date)
        return Result(True, T("rate.ok", lang, **kw), T("rate.say", lang, **kw))

    def _convert(self, cmd: Command, lang: str) -> Result:
        amount = float(cmd.args["amount"])
        rate, date = services.usd_rate(self.fetch)
        kw = dict(amount=fmt_num(amount), total=fmt_num(amount * rate), rate=fmt_num(rate), date=date)
        return Result(True, T("conv.ok", lang, **kw), T("conv.say", lang, **{**kw, "total": fmt_num(amount * rate, 0)}))

    def _weather(self, cmd: Command, lang: str) -> Result:
        w = services.weather(self.settings.city, self.fetch)
        desc = services.WEATHER_CODES.get(w["code"], "")
        kw = dict(city=w["city"], temp=w["temp"], feels=w["feels"], desc=desc, hum=w["humidity"], wind=w["wind"], time=w["time"].replace("T", " "))
        return Result(True, T("weather.ok", lang, **kw), T("weather.say", lang, **kw))

    def _time(self, cmd: Command, lang: str) -> Result:
        n = self.now()
        return Result(True, T("time.ok", lang, hm=f"{n:%H:%M}", date=f"{n:%d.%m.%Y}"), T("time.say", lang, h=f"{n:%H}", m=f"{n:%M}"))

    # ---- kompyuter holati (faqat o'qish)
    def _health(self, lang: str, fmt, spoken=None) -> Result:
        snap = self.monitor.sample(force_slow=True)
        return Result(True, fmt(snap, lang), (spoken or fmt)(snap, lang)[:300])

    def _report(self, cmd: Command, lang: str) -> Result:
        snap = self.monitor.sample(force_slow=True)
        text = health.full_report(snap, lang)
        path = health.save_report(text, data_dir() / "reports")
        return Result(True, f"{text}\n\n{T('rep.saved', lang, path=path)}",
                      T("rep.say", lang, line=health.status_text(snap, lang).splitlines()[0]))

    def _top(self, cmd: Command, lang: str) -> Result:
        by = cmd.args.get("by", "both")
        cpu, mem = self.monitor.top_processes()
        lines = []
        if by in ("ram", "both"):
            lines.append(T("top.ram", lang, items=", ".join(f"{n} ({health.gb(m)})" for n, m in mem)))
        if by in ("cpu", "both"):
            lines.append(T("top.cpu", lang, items=", ".join(f"{n} ({p:.1f}%)" for n, p in cpu)))
        lines.append(T("top.foot", lang))
        return Result(True, "\n".join(lines), lines[0])

    def _speedup(self, cmd: Command, lang: str) -> Result:
        snap = self.monitor.sample(force_slow=True)
        cpu, mem = self.monitor.top_processes()
        return Result(True, health.advice(snap, mem, cpu, lang), T("adv.say", lang))

    # ---- fayllar (faqat ruxsat etilgan papkalar; faqat o'qish)
    @staticmethod
    def _line(i: int, e: fs.FileEntry, lang: str) -> str:
        what = T(f"files.kind.{e.kind}", lang)
        size = "" if e.kind == "folder" else f", {fs.fmt_size(e.size)}"
        snip = f"\n    ↳ {e.snippet}" if e.snippet else ""
        return f"{i}) {e.display} — {what}{size}, {fs.fmt_date(e.mtime)}\n    {fs.safe_display(str(e.path), 260)}{snip}"

    def _find_files(self, cmd: Command, lang: str) -> Result:
        a = cmd.args
        alias = a.get("folder") or ""
        where = T(f"files.folder.{alias}", lang) if alias else T("files.folder.all", lang)
        kinds = [k for k in a.get("kinds", []) if k in fs.KINDS]
        what = ", ".join(T(f"files.kind.{k}", lang) for k in kinds) or T("files.kind.file", lang)
        if a.get("query"):
            what += f" «{fs.safe_display(a['query'], 80)}»"
        if a.get("lang"):
            what += f" [{a['lang']}]"
        if a.get("contains"):
            what += f" ⊃ «{fs.safe_display(a['contains'], 60)}»"
        out = fs.SearchOutcome()
        if a.get("bare") and a.get("ref") and self.files.recent and not a.get("latest"):        # «shu fayl», «so'ragan videom»: oxirgi natijalarga ishora (yangi taxmin yo'q)
            entries = [e for e in self.last_results if not kinds or e.kind in kinds]
            if not entries:
                return Result(False, T("files.ask_name", lang))
        else:
            roots = self._scope(alias)
            if alias and not roots:
                return Result(False, T("files.scope_denied", lang, folder=T(f"files.folder.{alias}", lang)))
            q = fs.Query(a.get("query", ""), frozenset(kinds), frozenset(a.get("exts", [])), a.get("lang", ""), a.get("contains", ""), bool(a.get("latest")),
                         1 if a.get("latest") else MAX_SHOWN, min_size=a.get("min_size"), max_size=a.get("max_size"), after=a.get("after"))
            out = self.files.search(q, roots, cancel=self.cancel_event)
            entries = out.entries
            if a.get("then") == "open" and a.get("query") and not out.fuzzy:
                # aniq nom ("example.mp4" yoki nomi aynan shu) bitta faylga to'g'ri kelsa — u tanlanadi; aks holda foydalanuvchidan so'raladi
                want_name = {f"{a['query']}.{x}".lower() for x in a.get("exts", [])}
                want_stem = " ".join(fs._tokens(a["query"]))
                exact = [e for e in entries if e.name.lower() in want_name or " ".join(fs._tokens(e.path.stem)) == want_stem]
                if len(exact) == 1:
                    entries = exact
        then = a.get("then", "show")
        notes = []
        if out.denied:
            notes.append(T("files.denied_n", lang, n=out.denied))
        if out.truncated:
            notes.append(T("files.truncated", lang))
        if a.get("lang"):
            notes.append(T("files.lang_note", lang))
        if a.get("contains"):
            notes.append(T("files.content_note", lang, n=out.content_checked))
        if not entries:
            return Result(then != "open", "\n".join([T("files.none", lang, where=where, what=what)] + notes), T("files.say.none", lang, what=what), files=[], then=then)
        head = T("files.fuzzy", lang) if out.fuzzy else T("files.found", lang, where=where, n=len(entries), what=what)
        body = "\n".join(self._line(i, e, lang) for i, e in enumerate(entries, 1))
        spoken = T("files.say.found", lang, n=len(entries), what=what, name=fs.safe_display(entries[0].path.stem, 60))
        return Result(True, "\n".join([head, body] + notes), spoken, files=entries, then=then, fuzzy=out.fuzzy)

    def _list_files(self, cmd: Command, lang: str) -> Result:
        alias = cmd.args.get("folder") or ""
        roots = self._scope(alias) if alias else self.files.roots()
        if not roots:
            return Result(False, T("files.no_roots", lang))
        parts, shown, total_n, denied, seen = [], [], 0, 0, set()
        for r in roots:
            if fs._norm(r) in seen:
                continue
            seen.add(fs._norm(r))
            items, total, den = self.files.list_dir(r, limit=max(5, 40 - len(shown)))
            denied += den
            total_n += total
            if not items:
                parts.append(T("files.list.empty", lang, where=fs.safe_display(str(r), 200)))
                continue
            lines = [T("files.list.header", lang, where=fs.safe_display(str(r), 200))]
            for e in items:
                shown.append(e)
                lines.append(self._line(len(shown), e, lang))
            if total > len(items):
                lines.append(T("files.list.more", lang, n=total - len(items)))
            parts.append("\n".join(lines))
        self.files._remember(shown)
        if denied:
            parts.append(T("files.denied_n", lang, n=denied))
        return Result(True, "\n\n".join(parts), T("files.list.say", lang, n=total_n), files=shown)

    def _open_file(self, cmd: Command, lang: str) -> Result:
        path = Path(str(cmd.args.get("path", "")))
        name = fs.safe_display(path.name)
        real, why = self.files.check_openable(path)
        if real is None:
            return Result(False, T(f"files.open.{why}", lang, name=name, ext=path.suffix.lstrip(".").lower()[:10]))
        player = (self.settings.video_player or "").strip()
        try:
            if real.is_dir():
                self.platform.open_folder(real)
                how = T("files.how.default", lang)
            elif fs.open_mode(real) == "notepad":
                self.platform.open_in_notepad(real)                  # kod fayli: faqat matn sifatida ko'rish
                how = T("files.how.notepad", lang)
            elif player and fs.KIND_OF_EXT.get(real.suffix.lower().lstrip(".")) == "video":
                pp = Path(player)
                if pp.is_file() and pp.suffix.lower() == ".exe":
                    self.platform.start_player(pp, real)           # shell'siz; fayl yo'li alohida argument
                    how = T("files.how.player", lang, player=pp.name)
                else:
                    self.platform.open_file(real)
                    how = T("files.how.player_missing", lang, player=fs.safe_display(player, 80))
            else:
                self.platform.open_file(real)
                how = T("files.how.default", lang)
        except OSError as e:
            if getattr(e, "winerror", None) == 1155:
                return Result(False, T("files.open.no_app", lang, name=name))
            log.warning("Fayl ochilmadi: %s", real.suffix, exc_info=True)
            return Result(False, T("files.open.failed", lang, name=name, err=e))
        return Result(True, T("files.open.sent", lang, name=name, how=how), T("files.open.sent", lang, name=name, how=how)[:200])

    # ---- eslatmalar
    def _when_text(self, due: datetime, recur: dict | None, lang: str) -> str:
        return due.strftime("%d.%m.%Y %H:%M") + (f" · {describe_recur(recur, lang)}" if recur else "")

    def _reminder_add(self, cmd: Command, lang: str) -> Result:
        a = cmd.args
        due = datetime.strptime(a["due"], REM_FMT)
        if due <= self.now() and not a.get("recur"):
            return Result(False, T("rem.ask_past", lang, when=due.strftime("%d.%m.%Y %H:%M")))
        r, created = self.reminders.add_unique(a["title"], due, a.get("recur"))
        when = self._when_text(r.due_dt, r.recur, lang)
        msg = T("rem.added" if created else "rem.exists", lang, title=r.title, when=when)
        return Result(True, msg, msg, changed="reminders")

    def _reminders_show(self, cmd: Command, lang: str) -> Result:
        scope = cmd.args.get("scope", "all")
        now = self.now()
        if scope == "today":                                 # bugungi + kechikkanlar (ular ham e'tibor talab qiladi)
            items = list({r.id: r for r in self.reminders.overdue(now) + [r for r in self.reminders.today(now) if r.due_dt >= now]}.values())
        else:
            items = {"overdue": lambda: self.reminders.overdue(now), "upcoming": lambda: self.reminders.upcoming(now, 20), "all": self.reminders.active}[scope]()
        label = T(f"rem.scope.{scope}", lang)
        if not items:
            msg = T("rem.none", lang, scope=label)
            return Result(True, msg, msg)
        lines = [T("rem.list.header", lang, scope=label, n=len(items))]
        for i, r in enumerate(items, 1):
            mark = f"  [{T('rem.overdue_mark', lang)}]" if r.due_dt < now else ""
            lines.append(f"{i}) {r.due_dt:%d.%m.%Y %H:%M} — {fs.safe_display(r.title, 160)} ({describe_recur(r.recur, lang)}){mark}")
        return Result(True, "\n".join(lines), T("rem.say.list", lang, n=len(items), title=fs.safe_display(items[0].title, 60)))

    # ---- vazifalar
    def _task_line(self, i: int, t, lang: str, now: datetime) -> str:
        due = f" — {t.due.replace('T', ' ')}" if t.due else ""
        over = f"  [{T('rem.overdue_mark', lang)}]" if t.overdue(now) else ""
        return f"{i}) [{T('task.pri.' + t.priority, lang)}] {fs.safe_display(t.title, 140)}{due} — {T('task.st.' + t.status, lang)}{over}"

    def _task_add(self, cmd: Command, lang: str) -> Result:
        a = cmd.args
        due = None
        if a.get("due"):
            due = datetime.strptime(a["due"], "%Y-%m-%dT%H:%M") if len(a["due"]) > 10 else datetime.strptime(a["due"], "%Y-%m-%d").date()
        t, created = self.tasks.add_unique(a["title"], a.get("description", ""), due, a.get("priority", "medium"), category=a.get("category", ""))
        msg = T("task.added" if created else "task.exists", lang, title=t.title, due=t.due.replace("T", " ") or "—", pri=T("task.pri." + t.priority, lang))
        return Result(True, msg, msg, changed="tasks")

    def _tasks_show(self, cmd: Command, lang: str) -> Result:
        scope, q = cmd.args.get("scope", "active"), cmd.args.get("query", "")
        now = self.now()
        view = {"today": "today", "week": "week", "overdue": "overdue", "all": "all", "active": "active", "done": "all"}[scope]
        items = self.tasks.search(q, status="done" if scope == "done" else "", view=view, now=now)
        extra = []
        if scope == "today":
            extra = [t for t in self.tasks.view("overdue", now) if t.id not in {x.id for x in items}]
        label = T(f"task.scope.{scope}", lang)
        if not items and not extra:
            msg = T("task.none", lang, scope=label)
            return Result(True, msg, msg)
        done, total = self.tasks.progress(items)
        lines = [T("task.list.header", lang, scope=label, n=len(items), done=done)]
        lines += [self._task_line(i, t, lang, now) for i, t in enumerate(items, 1)]
        if extra:
            lines.append(T("task.overdue_header", lang, n=len(extra)))
            lines += [self._task_line(i, t, lang, now) for i, t in enumerate(extra, 1)]
        return Result(True, "\n".join(lines), T("task.say.list", lang, n=len(items), extra=len(extra)))

    def _task_complete(self, cmd: Command, lang: str) -> Result:
        q = cmd.args.get("query", "")
        found = self.tasks.find_active(q)
        if not found:
            return Result(False, T("task.no_match", lang, q=fs.safe_display(q, 60)))
        if len(found) > 1:                                    # taxmin qilinmaydi: aniqroq nom so'raladi
            names = "; ".join(f"«{fs.safe_display(t.title, 50)}»" for t in found[:5])
            return Result(False, T("task.ambiguous", lang, names=names))
        t = self.tasks.complete(found[0].id)
        msg = T("task.completed", lang, title=fs.safe_display(t.title, 100))
        return Result(True, msg, msg, changed="tasks")

    # ---- qaydlar
    def _note_add(self, cmd: Command, lang: str) -> Result:
        note, old = self.notes.add_auto(cmd.args["title"], cmd.args.get("body", ""), category=cmd.args.get("category", ""))   # mavjud qayd ustiga HECH QACHON yozilmaydi
        msg = T("note.added", lang, title=note.title) if not old else T("note.added_dup", lang, old=old, title=note.title)
        return Result(True, msg, msg, changed="notes")

    def _notes_show(self, cmd: Command, lang: str) -> Result:
        q = cmd.args.get("query", "")
        found = self.notes.search(q)[:20]
        label = q or T("note.all", lang)
        if not found:
            msg = T("note.none", lang, q=label)
            return Result(True, msg, msg)
        lines = [T("note.list.header", lang, q=label, n=len(found))]
        for i, n in enumerate(found, 1):
            snippet = " ".join(n.body.split())[:90]
            tags = f"  #{' #'.join(n.tags)}" if n.tags else ""
            lines.append(f"{i}) {'★ ' if n.pinned else ''}{fs.safe_display(n.title, 80)} — {fs.safe_display(snippet, 90)}{tags}")
        return Result(True, "\n".join(lines), T("note.list.header", lang, q=label, n=len(found)))

    # ---- ingliz tili rejasi (faqat foydalanuvchi aytgan/belgilagan faoliyat yoziladi)
    def _study_summary(self, lang: str) -> str:
        today = self.now().date()
        cur, best = self.study.streak(today)
        return T("study.summary", lang, rec=self.study.minutes_on(today), plan=self.study.planned_minutes(), streak=cur, best=best)

    def _study_show(self, cmd: Command, lang: str) -> Result:
        done = self.study.done_ids()
        lines = [T("study.header", lang)]
        for a in self.study.plan():
            lines.append(f"{'☑' if a.id in done else '☐'} {fs.safe_display(a.name, 40)} — {a.minutes} {T('study.min', lang)}")
        lines += ["", self._study_summary(lang), T("study.disclaimer", lang)]
        return Result(True, "\n".join(lines), T("study.say.show", lang, n=len(self.study.plan()), mins=self.study.planned_minutes()), nav="study")

    def _study_done(self, cmd: Command, lang: str) -> Result:
        aid = cmd.args.get("activity", "")
        if not any(a.id == aid for a in self.study.plan()):
            return Result(False, T("study.no_activity", lang))
        entry, created = self.study.record(aid, minutes=cmd.args.get("minutes"))
        head = T("study.recorded" if created else "study.already", lang, name=entry.activity_name, mins=entry.minutes)
        msg = head + "\n" + self._study_summary(lang)
        return Result(True, msg, head, changed="study")

    def _study_progress(self, cmd: Command, lang: str) -> Result:
        week = self.study.week_minutes(self.now().date())
        lines = [self._study_summary(lang), T("study.week", lang, mins=sum(m for _d, m in week), days=sum(1 for _d, m in week if m))]
        st = self.study.session_stats()
        if st["sessions"]:
            lines.append(T("eng.progress", lang, s=st["sessions"], q=st["questions"], c=st["correct"]))
        lines.append(T("study.disclaimer", lang))
        return Result(True, "\n".join(lines), lines[0])

    # ---- media (tugma yuboriladi; dastur javob berganini bilib bo'lmaydi — shuning uchun «bajarildi» deb aytilmaydi)
    def _media(self, cmd: Command, lang: str) -> Result:
        key = cmd.args.get("key", "")
        what = T(f"media.{key}", lang)
        try:
            self.platform.media_key(key)
        except (OSError, ValueError) as e:
            return Result(False, T("media.failed", lang, err=e))
        msg = T("media.sent", lang, what=what)
        return Result(True, msg, msg[:160])

    # ---- oyna, skrinshot, clipboard, interfeys
    def _window(self, cmd: Command, lang: str) -> Result:
        op = cmd.args.get("op", "")
        what = T(f"win.{op}", lang)
        try:
            self.platform.window_op(op)
        except (OSError, ValueError) as e:
            return Result(False, T("win.failed", lang, err=e))
        msg = T("win.sent", lang, what=what)
        return Result(True, msg, msg.split(".")[0][:160])

    def _screenshot(self, cmd: Command, lang: str) -> Result:
        return Result(True, T("shot.pending", lang), ui="screenshot")      # Qt oynasi bilan ishlash asosiy oqimda (boshqaruvchida)

    def _clipboard(self, cmd: Command, lang: str) -> Result:
        mode = cmd.args.get("mode", "read")
        if mode not in ("read", "explain", "summarize"):
            return Result(False, T("not_allowed", lang))
        return Result(True, "", ui=f"clipboard:{mode}")

    def _ui(self, cmd: Command, lang: str) -> Result:
        op = cmd.args.get("op", "")
        if op == "settings_open":
            return Result(True, T("ui.settings", lang), nav="settings")
        if op == "settings_close":
            return Result(True, T("ui.closed", lang), nav="assistant")
        if op == "dark_mode":
            return Result(True, T("ui.dark" if cmd.args.get("theme", "dark") == "dark" else "ui.light", lang))
        if op == "commands":
            return Result(True, T("ui.commands", lang), T("ui.commands", lang).split("\n")[0])
        if op == "mic_status":
            return Result(True, "", ui="mic_status")
        return Result(False, T("not_allowed", lang))

    # ---- veb
    def _youtube_search(self, cmd: Command, lang: str) -> Result:
        q = " ".join(str(cmd.args.get("query", "")).split())[:200]
        if not q:
            return Result(False, T("cl.yt", lang))
        try:
            self.platform.open_url("https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q}))
        except Exception as e:  # noqa: BLE001
            return Result(False, T("open.failed", lang, title="YouTube", err=e))
        return Result(True, T("yt.ok", lang, q=q))

    def _open_site(self, cmd: Command, lang: str) -> Result:
        from .sysintent import _valid_host
        host = str(cmd.args.get("host", "")).lower()
        if not _valid_host(host):
            return Result(False, T("site.bad", lang, what=host[:60]))
        try:
            self.platform.open_url(f"https://{host}/")
        except Exception as e:  # noqa: BLE001
            return Result(False, T("open.failed", lang, title=host, err=e))
        return Result(True, T("site.ok", lang, host=host))

    # ---- kompyuter
    def _net_check(self, cmd: Command, lang: str) -> Result:
        try:
            host, ms = self.net()
        except services.NetworkError as e:
            msg = T("net.fail", lang, err=str(e)[:80])
            return Result(False, msg)
        return Result(True, T("net.ok", lang, host=host, ms=ms))

    def _specs(self, cmd: Command, lang: str) -> Result:
        s = self.monitor.sample(force_slow=True)
        na = T("specs.na", lang)
        cpu = health.cpu_name() or na
        threads = s.cpu_count or "?"
        disks = "; ".join(f"{d.mount} {health.gb(d.total)}" for d in s.disks[:6]) or na
        gpus = ", ".join(g.name for g in (s.gpus or []) if g.name) or na
        lines = [T("specs.title", lang), f"• {T('specs.os', lang)}: {s.os_name}", f"• {T('specs.cpu', lang)}: {cpu} ({threads} {T('specs.cores', lang).split('/')[-1]})",
                 f"• {T('specs.ram', lang)}: {health.gb(s.ram_total)}", f"• {T('specs.disk', lang)}: {disks}", f"• {T('specs.gpu', lang)}: {gpus}"]
        return Result(True, "\n".join(lines), T("specs.title", lang) + ": " + s.os_name + ", " + health.gb(s.ram_total) + " RAM")

    # ---- ingliz tili
    def _english(self, cmd: Command, lang: str) -> Result:
        a = cmd.args
        op = a.get("op", "")
        level = a.get("level") or self.settings.english_level
        if level not in english.LEVELS:
            level = english.DEFAULT_LEVEL
        if op == "lesson":
            plan = ", ".join(f"{x.name} {x.minutes}" for x in self.study.plan())
            return Result(True, T("eng.lesson", lang, level=self.settings.english_level, plan=plan), nav="study")
        if op in ("quiz", "pronunciation", "listening"):
            return Result(True, "", lesson=(op, level, int(a.get("n", 10))))
        if op == "translate":
            word = str(a.get("word", "")).strip()
            hit = english.lookup(word)
            if hit:
                lvl = next(l for l in english.LEVELS if hit in english.VOCAB[l])
                msg = T("eng.translate", lang, w=hit[0], uz=hit[1], ru=hit[2], lvl=lvl)
                return Result(True, msg, msg)
            return Result(True, T("eng.notfound", lang, w=word), ai_prompt=T("eng.p.translate", lang, w=word, language=T("lang.name", lang)))
        if op == "level":
            cur = self.settings.english_level
            if a.get("level") in english.LEVELS:
                new = a["level"]
            else:
                i = english.LEVELS.index(cur if cur in english.LEVELS else english.DEFAULT_LEVEL) + int(a.get("shift", 0))
                if not 0 <= i < len(english.LEVELS):
                    return Result(False, T("eng.level.limit", lang, level=cur))
                new = english.LEVELS[i]
            if new == cur:
                return Result(True, T("eng.level.same", lang, level=cur))
            self.settings.english_level = new
            self.settings.save()
            return Result(True, T("eng.level.set", lang, level=new), changed="study")
        return Result(False, T("not_allowed", lang))
