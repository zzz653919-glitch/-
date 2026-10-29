"""Tasdiqlangan buyruqni bajarish. Faqat `_actions` ichidagi qat'iy funksiyalar chaqiriladi; javoblar uz / ru / en."""
from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from datetime import datetime

from . import apps, health, services
from .commands import ALLOWED_ACTIONS, Command
from .i18n import T, app_title
from .settings import Settings, data_dir

log = logging.getLogger(__name__)


@dataclass
class Result:
    ok: bool
    message: str
    spoken: str | None = None      # ovozda aytiladigan qisqa variant


def fmt_num(x: float, digits: int = 2) -> str:
    s = f"{x:,.{digits}f}".replace(",", " ").replace(".", ",")
    return s.rstrip("0").rstrip(",") if "," in s else s


class Executor:
    def __init__(self, settings: Settings, platform: apps.Platform | None = None,
                 monitor: health.HealthMonitor | None = None, fetch=services.get_json, now=datetime.now):
        self.settings, self.platform = settings, platform or apps.Platform()
        self.monitor = monitor or health.HealthMonitor()
        self.fetch, self.now = fetch, now
        h = self._health
        self._actions = {
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
