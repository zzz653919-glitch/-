import pytest

from pyatnitsa.commands import parse


@pytest.mark.parametrize("text,action,args", [
    ("Google Chrome'ni och", "open_app", {"app": "chrome"}),
    ("Chrome'ni och", "open_app", {"app": "chrome"}),
    ("Хром ни открой", "open_app", {"app": "chrome"}),
    ("Brauzerni och", "open_app", {"app": "browser"}),
    ("Downloads papkasini och", "open_app", {"app": "downloads"}),
    ("Desktop papkasini och", "open_app", {"app": "desktop"}),
    ("Documents papkasini och", "open_app", {"app": "documents"}),
    ("Kalkulyatorni och", "open_app", {"app": "calculator"}),
    ("Notepad'ni och", "open_app", {"app": "notepad"}),
    ("Fayl menejerini och", "open_app", {"app": "explorer"}),
    ("YouTube'ni och", "open_app", {"app": "youtube"}),
    ("Yangi brauzer oynasini och", "new_window", {}),
    ("Google'da Python darslarini qidir", "search", {"query": "python darslarini"}),
    ("Google'da HTML haqida ma'lumot qidir", "search", {"query": "html"}),
    ("Dollar kursini ko'rsat", "rate_usd", {}),
    ("100 dollar necha so'm?", "convert_usd", {"amount": 100.0}),
    ("yuz dollar necha som", "convert_usd", {"amount": 100.0}),
    ("Bugungi ob-havoni ko'rsat", "weather", {}),
    ("Hozirgi vaqtni ayt", "time", {}),
    ("Kompyuterim holati qanday?", "health_status", {}),
    ("Kompyuterimning holatini tekshir", "health_status", {}),
    ("To'liq diagnostika qil", "health_full", {}),
    ("Protsessorni tekshir", "health_cpu", {}),
    ("Protsessor haroratini tekshir", "health_temps", {}),
    ("RAM holatini ko'rsat", "health_ram", {}),
    ("RAM qancha bandligini ko'rsat", "health_ram", {}),
    ("Diskimda qancha joy qoldi?", "health_disk", {}),
    ("Diskda qancha bo'sh joy bor?", "health_disk", {}),
    ("Qaysi dastur ko'p RAM ishlatyapti?", "health_top", {"by": "ram"}),
    ("Kompyuterimda qaysi dasturlar ko'p resurs ishlatyapti?", "health_top", {"by": "both"}),
    ("Haroratlarni ko'rsat", "health_temps", {}),
    ("Kompyuter holati hisobotini yarat", "health_report", {}),
    ("Kompyuterni tezlashtir", "speedup_advice", {}),
])
def test_known_commands(text, action, args):
    r = parse(text)
    assert r.kind == "ok", (text, r)
    assert (r.command.action, r.command.args) == (action, args)


@pytest.mark.parametrize("text", [
    "Kompyuterni o'chir", "Faylni o'chir", "Downloads papkasidagi fayllarni o'chir", "Kompyuterni qayta ishga tushir",
    "Faylni ko'chir", "Faylning nomini o'zgartir", "Xabar yubor", "Dastur o'rnat", "Parolni ko'rsat",
    "Chrome'ni och va Downloads'ni o'chir", "Delete all files", "shutdown",
])
def test_dangerous_is_blocked(text):
    r = parse(text)
    assert r.kind == "blocked" and r.command is None


@pytest.mark.parametrize("text", ["", "   ", "blah blah", "Salom", "Ochish", "rm -rf /", "powershell -c calc", "cmd /c del x"])
def test_unknown_does_nothing(text):
    r = parse(text)
    assert r.kind == "unknown" and r.command is None and "tushunmadim" in r.message


def test_multiple_commands_ambiguous():
    assert parse("Chrome'ni och va Notepad'ni och").kind == "ambiguous"


def test_clarifying_question_for_partial_commands():
    assert "Qaysi dastur" in parse("biror narsani och").message
    assert "qaysi qismini" in parse("kompyuter haqida").message


def test_search_query_never_becomes_a_command():
    r = parse("Google'da calc.exe && del C:\\ qidir")
    assert r.kind == "blocked" or r.command.action == "search"   # xavfli so'z bo'lsa rad, aks holda faqat URL parametri
