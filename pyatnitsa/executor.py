"""Tasdiqlangan buyruqni bajarish. Faqat `_ACTIONS` ichidagi qat'iy funksiyalar chaqiriladi."""
from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from datetime import datetime

from . import apps, health, services
from .commands import Command
from .settings import Settings, data_dir

log = logging.getLogger(__name__)
NO_NET = "Internet bilan aloqa yo'q yoki manba javob bermadi, shuning uchun ma'lumot olinmadi. Hech narsa o'ylab topilmadi."


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
        self._actions = {
            "open_app": self._open_app, "new_window": self._new_window, "search": self._search,
            "rate_usd": self._rate, "convert_usd": self._convert, "weather": self._weather, "time": self._time,
            "health_status": lambda c: self._health(c, health.status_text),
            "health_cpu": lambda c: self._health(c, health.cpu_text),
            "health_ram": lambda c: self._health(c, health.ram_text),
            "health_disk": lambda c: self._health(c, health.disk_text),
            "health_temps": lambda c: self._health(c, health.temps_text),
            "health_gpu": lambda c: self._health(c, health._gpu_text),
            "health_battery": lambda c: self._health(c, health._batt_text),
            "health_uptime": lambda c: self._health(c, lambda s: f"Kompyuter {health.fmt_uptime(s.uptime_s)} dan beri ishlayapti."),
            "health_full": lambda c: self._health(c, health.full_report, spoken=health.status_text),
            "health_report": self._report, "health_top": self._top, "speedup_advice": self._speedup,
            "admin_info": self._admin_info,
        }

    def execute(self, cmd: Command) -> Result:
        fn = self._actions.get(cmd.action)
        if fn is None:
            return Result(False, "Bu amal ruxsat etilgan ro'yxatda yo'q, bajarilmadi.")
        try:
            return fn(cmd)
        except services.NetworkError:
            log.warning("Tarmoq xatosi: %s", cmd.action, exc_info=True)
            return Result(False, NO_NET)
        except services.DataError as e:
            return Result(False, f"Manbadan ma'lumot olinmadi: {e}.")
        except Exception as e:  # noqa: BLE001
            log.exception("Buyruq xatosi: %s", cmd.action)
            return Result(False, f"Xatolik yuz berdi, buyruq bajarilmadi: {e}")

    # ---- ochish
    def _allowed(self, app_id: str) -> bool:
        return app_id in apps.APPS and self.settings.is_app_allowed(app_id)

    def _open_app(self, cmd: Command) -> Result:
        app_id = cmd.args.get("app", "")
        if not self._allowed(app_id):
            return Result(False, "Bu dastur ruxsat etilgan ro'yxatda yo'q yoki o'chirilgan (Sozlamalar ichida yoqish mumkin).")
        spec = apps.APPS[app_id]
        if spec.kind == "exe":
            path = self.platform.find_executable(app_id)
            if not path:
                return Result(False, f"{spec.title} kompyuterdan topilmadi, shuning uchun ochilmadi.")
            self.platform.start_exe(path)
        elif spec.kind == "folder":
            path = self.platform.folder_path(app_id)
            if not path or not path.is_dir():
                return Result(False, f"{spec.title} topilmadi.")
            self.platform.open_folder(path)
        else:
            self.platform.open_url(apps.URLS[app_id])
        return Result(True, f"{spec.title} ochildi.")

    def _new_window(self, cmd: Command) -> Result:
        if not self._allowed("new_window"):
            return Result(False, "Bu amal o'chirilgan.")
        self.platform.open_new_window(apps.URLS["browser"])
        return Result(True, "Yangi brauzer oynasi ochildi.")

    def _search(self, cmd: Command) -> Result:
        q = str(cmd.args.get("query", "")).strip()
        if not self._allowed("search") or not q:
            return Result(False, "Qidiruv bajarilmadi.")
        self.platform.open_url("https://www.google.com/search?" + urllib.parse.urlencode({"q": q}))
        return Result(True, f"Google'da «{q}» qidirilmoqda.")

    # ---- ma'lumot
    def _rate(self, cmd: Command) -> Result:
        rate, date = services.usd_rate(self.fetch)
        return Result(True, f"1 AQSh dollari = {fmt_num(rate)} so'm.\nManba: O'zbekiston Markaziy banki (cbu.uz), sana: {date}.",
                      f"Bir dollar {fmt_num(rate)} so'm. Manba: Markaziy bank, {date}.")

    def _convert(self, cmd: Command) -> Result:
        amount = float(cmd.args["amount"])
        rate, date = services.usd_rate(self.fetch)
        return Result(True, f"{fmt_num(amount)} dollar = {fmt_num(amount * rate)} so'm (1 dollar = {fmt_num(rate)} so'm).\n"
                            f"Manba: O'zbekiston Markaziy banki (cbu.uz), sana: {date}.",
                      f"{fmt_num(amount)} dollar {fmt_num(amount * rate, 0)} so'm. Manba: Markaziy bank, {date}.")

    def _weather(self, cmd: Command) -> Result:
        w = services.weather(self.settings.city, self.fetch)
        desc = services.WEATHER_CODES.get(w["code"], "")
        msg = (f"{w['city']}: hozir {w['temp']:+.0f}°C (his qilinishi {w['feels']:+.0f}°C), {desc}, namlik {w['humidity']:.0f}%, "
               f"shamol {w['wind']:.0f} km/soat.\nManba: Open-Meteo, vaqt: {w['time'].replace('T', ' ')}.")
        return Result(True, msg, f"{w['city']}da hozir {w['temp']:.0f} daraja, {desc}.")

    def _time(self, cmd: Command) -> Result:
        n = self.now()
        return Result(True, f"Hozir soat {n:%H:%M}. Sana: {n:%d.%m.%Y}.", f"Hozir soat {n:%H} {n:%M}.")

    # ---- kompyuter holati (faqat o'qish)
    def _health(self, cmd: Command, fmt, spoken=None) -> Result:
        snap = self.monitor.sample(force_slow=True)
        text = fmt(snap)
        return Result(True, text, (spoken or fmt)(snap)[:300])

    def _report(self, cmd: Command) -> Result:
        snap = self.monitor.sample(force_slow=True)
        text = health.full_report(snap)
        path = health.save_report(text, data_dir() / "reports")
        return Result(True, f"{text}\n\nHisobot saqlandi: {path}", f"Hisobot tayyor va saqlandi. {health.status_text(snap).splitlines()[0]}")

    def _top(self, cmd: Command) -> Result:
        by = cmd.args.get("by", "both")
        cpu, mem = self.monitor.top_processes()
        lines = []
        if by in ("ram", "both"):
            lines.append("Eng ko'p RAM ishlatayotgan dasturlar: " + ", ".join(f"{n} ({health.gb(m)})" for n, m in mem) + ".")
        if by in ("cpu", "both"):
            lines.append("Eng ko'p CPU ishlatayotgan dasturlar: " + ", ".join(f"{n} ({p:.1f}%)" for n, p in cpu) + ".")
        lines.append("Faqat jarayon nomlari ko'rsatildi; hech qanday dastur yopilmadi.")
        return Result(True, "\n".join(lines), lines[0])

    def _speedup(self, cmd: Command) -> Result:
        snap = self.monitor.sample(force_slow=True)
        cpu, mem = self.monitor.top_processes()
        text = health.advice(snap, mem, cpu)
        return Result(True, text, "Tahlil tayyor. Tavsiyalarni chatda ko'ring; men hech narsani o'zgartirmadim.")

    def _admin_info(self, cmd: Command) -> Result:
        return Result(True, "Windows tizim fayllarini tekshirish (sfc /scannow, DISM, chkdsk) administrator huquqini talab qiladi, "
                            "shuning uchun men uni avtomatik bajarmayman. Xohlasangiz, o'zingiz «Buyruqlar qatori»ni administrator "
                            "sifatida ochib, qo'lda ishga tushiring.", "Bu tekshiruv administrator huquqini talab qiladi, avtomatik bajarmayman.")
