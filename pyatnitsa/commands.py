"""Matnni (ovozdan yoki klaviaturadan) oldindan belgilangan xavfsiz buyruqlarga aylantirish.

Matn hech qachon shell'ga, eval/exec'ga yoki fayl yo'liga berilmaydi: faqat quyidagi
ro'yxatdagi `action` nomlaridan biri tanlanadi. Tushunilmagan matn -> hech narsa bajarilmaydi.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

UNKNOWN_MSG = "Buyruqni tushunmadim, qaytadan ayting."
BLOCKED_MSG = ("Bu amal xavfli, shuning uchun bu dasturda ruxsat etilmagan: fayllarni o'chirish, "
               "ko'chirish, nomini o'zgartirish, kompyuterni o'chirish/qayta yoqish, xabar yuborish "
               "yoki dastur o'rnatish mumkin emas.")
AMBIGUOUS_MSG = "Bir vaqtda bir nechta buyruq eshitildi. Iltimos, faqat bittasini ayting."

_APOS = "ʻʼ’‘`´′ʹ"
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g",
    "ҳ": "h",
}


@dataclass
class Command:
    action: str
    args: dict = field(default_factory=dict)
    confirm_text: str = ""


@dataclass
class ParseResult:
    kind: str                       # ok | unknown | ambiguous | blocked
    command: Command | None = None
    message: str = ""


def basic(text: str) -> str:
    t = unicodedata.normalize("NFKC", text).lower().strip()
    for c in _APOS:
        t = t.replace(c, "'")
    return re.sub(r"[\x00-\x1f]", " ", t)


def normalize(text: str) -> str:
    """Kichik harf, kirill -> lotin, apostroflar tushiriladi (o'chir -> ochir)."""
    t = "".join(_CYR.get(ch, ch) for ch in basic(text)).replace("'", "")
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------- raqamlar
_UNITS = {"bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5, "olti": 6, "yetti": 7,
          "sakkiz": 8, "toqqiz": 9, "on": 10, "yigirma": 20, "ottiz": 30, "qirq": 40,
          "ellik": 50, "oltmish": 60, "yetmish": 70, "sakson": 80, "toqson": 90}


def _number_words(n: str) -> float | None:
    total = cur = 0
    seen = False
    for tok in n.split():
        if tok in _UNITS:
            cur += _UNITS[tok]; seen = True
        elif tok == "yuz":
            cur = (cur or 1) * 100; seen = True
        elif tok == "ming":
            total += (cur or 1) * 1000; cur = 0; seen = True
    return float(total + cur) if seen else None


def extract_amount(text: str) -> float | None:
    m = re.search(r"\d[\d\s ]*(?:[.,]\d+)?", basic(text))
    val: float | None = None
    if m:
        raw = re.sub(r"\s", "", m.group()).replace(",", ".")
        try:
            val = float(raw)
        except ValueError:
            val = None
    if val is None:
        val = _number_words(normalize(text))
    if val is None or not (0 < val <= 1e9):
        return None
    return val


# ---------------------------------------------------------------- naqshlar
_OPEN = re.compile(r"\b(och|oching|ochib|ochgin|ishga tushir\w*|otkroy\w*|otkrit\w*|open|zapusti\w*)\b")
_SEARCH = re.compile(r"\b(qidir\w*|izla\w*|poisk\w*|naydi|search)\b")

_DANGEROUS = [re.compile(p) for p in (
    r"\b(ochir\w*|udali\w*|delete|remove)\b", r"\b(restart|reboot|shutdown|perezagruz\w*|vikluch\w*)\b",
    r"qayta ishga tushir", r"\b(kochir\w*|nomini|ozgartir\w*|yubor\w*|ornat\w*|install\w*)\b",
    r"\b(parol\w*|password|format\w*)\b")]

_APPS = [  # (app_id, naqsh, tasdiq matni)
    ("chrome", r"chrome|xrom|hrom|krom", "Google Chrome ochilsinmi"),
    ("downloads", r"download|yuklam|yuklab olin|zagruzk|daunload", "Downloads papkasi ochilsinmi"),
    ("desktop", r"desktop|dekstop|ish stol|rabochiy stol", "Desktop papkasi ochilsinmi"),
    ("documents", r"document|dokument|hujjat", "Documents papkasi ochilsinmi"),
    ("calculator", r"kalkulyator|kalkulator|calculator", "Kalkulyator ochilsinmi"),
    ("notepad", r"notepad|noutpad|bloknot", "Notepad ochilsinmi"),
    ("explorer", r"fayl\s*menej\w*|explorer|provodnik", "Fayl menejeri ochilsinmi"),
    ("youtube", r"youtube|yutub|yutyub", "YouTube ochilsinmi"),
]
_PC = r"kompyuter\w*|noutbuk\w*|tizim\w*"
_CPU = r"protsessor\w*|prosessor\w*|procesor\w*|\bcpu\b"
_RAM = r"\bram\w*|operativ\w*|tezkor xotira\w*"
_DISK = r"\bdisk\w*|bosh joy|joy qold\w*"
_TEMP = r"harorat\w*|temperatur\w*|issiq\w*"
_GPU = r"\bgpu\b|videokarta\w*|grafik\w* karta|videoplata"
_BATT = r"batareya\w*|akkumulyator\w*|zaryad\w*|battery"
_PROC = r"dastur\w*|jarayon\w*"
_has = lambda pat, n: re.search(pat, n) is not None  # noqa: E731


def _dangerous(n: str) -> bool:
    return any(p.search(n) for p in _DANGEROUS)


def _match_apps(n: str, raw: str) -> list[Command]:
    out = []
    if not _OPEN.search(n):
        return out
    if _has(r"yangi", n) and _has(r"oyna|brauzer", n):
        return [Command("new_window", {}, "Yangi brauzer oynasi ochilsinmi")]
    for app_id, pat, ask in _APPS:
        if _has(pat, n):
            out.append(Command("open_app", {"app": app_id}, ask))
    if not out and _has(r"brauzer|browser", n):
        out.append(Command("open_app", {"app": "browser"}, "Brauzer ochilsinmi"))
    return out


def _match_search(n: str, raw: str) -> list[Command]:
    if not _SEARCH.search(n):
        return []
    q = raw
    q = re.sub(r"\b(qidir\w*|izla\w*|поиск\w*|найди|search)\b", " ", q)
    q = re.sub(r"\b(google|gugl|гугл)\w*|\bda\b|\bdan\b|\bhaqida\b|\bboyicha\b|\bma'lumot\w*|\bsahifa\w*|\bhttps?://\S+",
               " ", q)
    q = re.sub(r"\s+", " ", q).strip(" .,!?;:'\"")[:200]
    if len(q) < 2:
        return []
    return [Command("search", {"query": q}, f"Google'da «{q}» qidirilsinmi")]


def _match_info(n: str, raw: str) -> list[Command]:
    out = []
    if _has(r"dollar|usd|доллар|dolar", n):
        amount = extract_amount(raw)
        if amount and _has(r"necha|som|qancha", n):
            out.append(Command("convert_usd", {"amount": amount}, f"{amount:g} dollar so'mga hisoblansinmi"))
        elif _has(r"kurs", n):
            out.append(Command("rate_usd", {}, "Dollar kursi ko'rsatilsinmi"))
    if _has(r"ob\s*havo|pogoda|weather", n):
        out.append(Command("weather", {}, "Ob-havo ko'rsatilsinmi"))
    uptime = _has(_PC, n) and _has(r"qancha vaqt|ishlayapti|ishlagan|uptime", n)
    if uptime:
        out.append(Command("health_uptime", {}, "Kompyuter ishlagan vaqt ko'rsatilsinmi"))
    elif _has(r"\bvaqt\w*|\bsoat\w*", n) and not _has(r"ishlayapti", n):
        out.append(Command("time", {}, "Hozirgi vaqt aytilsinmi"))
    return out


_HEALTH_ORDER = [  # (action, shart, tasdiq matni)
    ("health_report", lambda n: _has(r"hisobot\w*", n) and _has(_PC + r"|holat\w*|diagnostika", n),
     "Kompyuter holati hisoboti yaratilsinmi (faqat dasturning o'z papkasiga yangi fayl yoziladi)"),
    ("admin_info", lambda n: _has(r"\bsfc\b|chkdsk|\bdism\b|tizim fayllar\w* tekshir", n),
     "Administrator talab qiladigan tekshiruv haqida ma'lumot berilsinmi"),
    ("health_full", lambda n: _has(r"diagnostika|toliq tekshir\w*", n), "To'liq diagnostika (faqat o'qish) qilinsinmi"),
    ("speedup_advice", lambda n: _has(r"tezlashtir\w*|tezlat\w*|optimalla\w*|tozala\w*", n) and _has(_PC, n) or _has(r"tezlashtir\w*", n),
     "Kompyuterni tahlil qilib, tavsiyalar berilsinmi (hech narsa o'zgartirilmaydi)"),
    ("health_top", lambda n: _has(_PROC, n) and _has(r"qaysi|kop|eng|resurs|ishlat\w*", n),
     "Eng ko'p resurs ishlatayotgan dasturlar ko'rsatilsinmi"),
    ("health_battery", lambda n: _has(_BATT, n), "Batareya holati ko'rsatilsinmi"),
    ("health_gpu", lambda n: _has(_GPU, n), "Videokarta holati ko'rsatilsinmi"),
    ("health_temps", lambda n: _has(_TEMP, n), "Haroratlar ko'rsatilsinmi"),
    ("health_disk", lambda n: _has(_DISK, n), "Disk holati ko'rsatilsinmi"),
    ("health_ram", lambda n: _has(_RAM, n), "RAM holati ko'rsatilsinmi"),
    ("health_cpu", lambda n: _has(_CPU, n), "Protsessor holati ko'rsatilsinmi"),
    ("health_status", lambda n: _has(_PC, n) and _has(r"holat\w*|soglig\w*|qanday|tekshir\w*", n),
     "Kompyuter holati ko'rsatilsinmi"),
]


def _match_health(n: str, raw: str) -> list[Command]:
    for action, cond, ask in _HEALTH_ORDER:
        if cond(n):
            args = {}
            if action == "health_top":
                ram, cpu = _has(_RAM, n), _has(_CPU, n)
                args["by"] = "ram" if ram and not cpu else "cpu" if cpu and not ram else "both"
            return [Command(action, args, ask)]
    return []


def parse(text: str) -> ParseResult:
    """Bitta ruxsat etilgan buyruq, yoki tushunarli rad etish sababi."""
    text = (text or "").strip()[:500]
    n, raw = normalize(text), basic(text)
    if not n:
        return ParseResult("unknown", message=suggest(text))
    if _dangerous(n):
        return ParseResult("blocked", message=BLOCKED_MSG)
    found: list[Command] = []
    for matcher in (_match_apps, _match_search, _match_info, _match_health):
        found += matcher(n, raw)
    if not found:
        return ParseResult("unknown", message=suggest(text))
    if len(found) > 1:
        return ParseResult("ambiguous", message=AMBIGUOUS_MSG)
    return ParseResult("ok", found[0])


def suggest(text: str) -> str:
    """Tushunilmagan buyruq uchun aniqlashtiruvchi savol."""
    n = normalize(text)
    if _has(_OPEN.pattern, n):
        hint = "Qaysi dastur yoki papkani ochay? (Chrome, Notepad, Kalkulyator, Downloads, Desktop, Documents, Fayl menejeri, YouTube)"
    elif _SEARCH.search(n):
        hint = "Google'da nimani qidiray? Masalan: «Google'da Python darslarini qidir»."
    elif _has(r"dollar|kurs|valyuta", n):
        hint = "Dollar kursini ko'rsataymi yoki «100 dollar necha so'm?» deb hisoblaymi?"
    elif _has(f"{_PC}|{_CPU}|{_RAM}|{_DISK}|{_TEMP}|{_GPU}|{_BATT}|{_PROC}|holat|diagnostika", n):
        hint = ("Kompyuterning qaysi qismini tekshiray: CPU, RAM, disk, harorat, videokarta, batareya "
                "yoki to'liq diagnostika?")
    else:
        return UNKNOWN_MSG
    return f"{UNKNOWN_MSG[:-len(' qaytadan ayting.')]}. {hint}"
