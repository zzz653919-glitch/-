"""Tasdiqlangan buyruqni bajarish. Faqat `_actions` ichidagi qat'iy funksiyalar chaqiriladi; javoblar uz / ru / en."""
from __future__ import annotations

import logging
import threading
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import apps, files as fs, health, services
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
                 monitor: health.HealthMonitor | None = None, fetch=services.get_json, now=datetime.now, files: fs.FileAccess | None = None):
        self.settings, self.platform = settings, platform or apps.Platform()
        self.monitor = monitor or health.HealthMonitor()
        self.fetch, self.now = fetch, now
        self.files = files or fs.FileAccess(settings)
        self.cancel_event = threading.Event()          # qidiruvni to'xtatish (yopilish / foydalanuvchi bekor qilishi)
        h = self._health
        self._actions = {
            "find_files": self._find_files, "list_files": self._list_files, "open_file": self._open_file,
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
            if (a.get("ref") and not has_recent) or (a.get("then") == "open" and not a.get("ref") and not alias and not a.get("latest")):
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
        return f"{i}) {e.display} — {what}{size}, {fs.fmt_date(e.mtime)}\n    {fs.safe_display(str(e.path), 260)}"

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
        out = fs.SearchOutcome()
        if a.get("bare") and a.get("ref") and self.files.recent:        # «shu fayl», «so'ragan videom»: oxirgi natijalarga ishora (yangi taxmin yo'q)
            entries = [e for e in self.last_results if not kinds or e.kind in kinds]
            if not entries:
                return Result(False, T("files.ask_name", lang))
        else:
            roots = self._scope(alias)
            if alias and not roots:
                return Result(False, T("files.scope_denied", lang, folder=T(f"files.folder.{alias}", lang)))
            q = fs.Query(a.get("query", ""), frozenset(kinds), frozenset(a.get("exts", [])), a.get("lang", ""), bool(a.get("latest")), 1 if a.get("latest") else MAX_SHOWN)
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
