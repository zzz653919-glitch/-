from pathlib import Path

from pyatnitsa import apps, services
from pyatnitsa.commands import Command, parse
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings


class FakePlatform(apps.Platform):
    def __init__(self, exes=None, tmp=None):
        self.calls, self.exes, self.tmp = [], exes or {}, tmp

    def find_executable(self, app_id):
        return self.exes.get(app_id)

    def folder_path(self, app_id):
        return self.tmp

    def start_exe(self, path):
        self.calls.append(("exe", str(path)))

    def open_folder(self, path):
        self.calls.append(("folder", str(path)))

    def open_url(self, url):
        self.calls.append(("url", url))

    def open_new_window(self, url):
        self.calls.append(("new", url))

    def open_file(self, path):
        if getattr(self, "open_error", None):
            raise self.open_error
        self.calls.append(("file", str(path)))

    def start_player(self, player, path):
        if getattr(self, "open_error", None):
            raise self.open_error
        self.calls.append(("player", str(player), str(path)))


def make(tmp_path, **kw):
    plat = FakePlatform({"chrome": Path("/x/chrome.exe")}, tmp_path)
    return Executor(Settings(), plat, **kw), plat


def run(ex, text):
    r = parse(text)
    assert r.kind == "ok"
    return ex.execute(r.command)


def test_chrome_and_downloads(tmp_path):
    ex, plat = make(tmp_path)
    assert run(ex, "Chrome'ni och").ok
    assert run(ex, "Downloads papkasini och").ok
    assert plat.calls == [("exe", "/x/chrome.exe"), ("folder", str(tmp_path))]


def test_missing_program_opens_nothing_else(tmp_path):
    ex, plat = make(tmp_path)
    r = run(ex, "Notepad'ni och")
    assert not r.ok and "topilmadi" in r.message and plat.calls == []


def test_disabled_app_not_launched(tmp_path):
    ex, plat = make(tmp_path)
    ex.settings.allowed_apps = {"chrome": False}
    assert not run(ex, "Chrome'ni och").ok and plat.calls == []


def test_unknown_action_rejected(tmp_path):
    ex, plat = make(tmp_path)
    r = ex.execute(Command("run_shell", {"cmd": "del *"}))
    assert not r.ok and plat.calls == []


def test_search_url_is_encoded(tmp_path):
    ex, plat = make(tmp_path)
    run(ex, "Google'da Python darslarini qidir")
    assert plat.calls == [("url", "https://www.google.com/search?q=python+darslarini")]


def test_dollar_rate_with_source_and_date(tmp_path):
    ex, _ = make(tmp_path, fetch=lambda url: [{"Rate": "12650.5", "Date": "26.10.2026"}])
    r = run(ex, "Dollar kursini ko'rsat")
    assert r.ok and "12 650,5" in r.message and "26.10.2026" in r.message and "Markaziy bank" in r.message
    assert "1 265 050" in run(ex, "100 dollar necha so'm?").message


def test_no_internet_is_reported_not_invented(tmp_path):
    def boom(url):
        raise services.NetworkError("offline")
    ex, _ = make(tmp_path, fetch=boom)
    for t in ("Dollar kursini ko'rsat", "Bugungi ob-havoni ko'rsat"):
        r = run(ex, t)
        assert not r.ok and "Internet" in r.message and not any(ch.isdigit() for ch in r.message)


def test_weather(tmp_path):
    def fetch(url):
        if "geocoding" in url:
            return {"results": [{"name": "Tashkent", "latitude": 41.3, "longitude": 69.2}]}
        return {"current": {"temperature_2m": 18.4, "apparent_temperature": 17, "relative_humidity_2m": 40,
                            "weather_code": 2, "wind_speed_10m": 9, "time": "2026-10-26T12:00"}}
    ex, _ = make(tmp_path, fetch=fetch)
    r = run(ex, "Bugungi ob-havoni ko'rsat")
    assert "+18°C" in r.message and "Open-Meteo" in r.message


def test_health_commands_use_real_measurements(tmp_path):
    ex, _ = make(tmp_path)
    for t in ("RAM holatini ko'rsat", "Protsessorni tekshir", "Diskda qancha bo'sh joy bor?", "Haroratlarni ko'rsat",
              "Kompyuterim holati qanday?", "To'liq diagnostika qil", "Kompyuterni tezlashtir",
              "Qaysi dastur ko'p RAM ishlatyapti?"):
        r = run(ex, t)
        assert r.ok and r.message, t
    assert "%" in run(ex, "RAM holatini ko'rsat").message


def test_health_report_writes_only_own_folder(tmp_path):
    ex, _ = make(tmp_path)
    r = run(ex, "Kompyuter holati hisobotini yarat")
    assert r.ok and "Hisobot saqlandi" in r.message
    path = Path(r.message.rsplit("saqlandi: ", 1)[1])
    assert path.is_file() and "reports" in path.parts


def test_speedup_changes_nothing(tmp_path):
    ex, plat = make(tmp_path)
    r = run(ex, "Kompyuterni tezlashtir")
    assert "o'zgartirmadim" in r.message and plat.calls == []
