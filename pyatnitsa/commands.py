"""Buyruq ma'lumot turlari va matn yordamchilari. Tushunish mantig'i — `nlu.py` da.

Matn hech qachon shell, eval yoki exec'ga berilmaydi: `parse()` faqat `ALLOWED_ACTIONS` ichidagi nomlarni qaytaradi.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

UNKNOWN_MSG = "Buyruqni tushunmadim, qaytadan ayting."
BLOCKED_MSG = ("Bu amal xavfli, shuning uchun bu dasturda ruxsat etilmagan: fayllarni o'chirish, ko'chirish, nomini o'zgartirish, "
               "kompyuterni o'chirish/qayta yoqish, dasturni yopish, xabar yuborish yoki dastur o'rnatish mumkin emas.")

ALLOWED_ACTIONS = frozenset({
    "open_app", "new_window", "search", "rate_usd", "convert_usd", "weather", "time",
    "health_status", "health_cpu", "health_ram", "health_disk", "health_temps", "health_gpu", "health_battery",
    "health_uptime", "health_full", "health_report", "health_top", "speedup_advice", "admin_info",
})

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
    intent: str = ""           # open_app | open_folder | web_search | get_exchange_rate | get_pc_health | get_system_info ...


@dataclass
class ParseResult:
    kind: str                  # ok | unknown | clarify | blocked
    command: Command | None = None
    message: str = ""
    commands: list[Command] = field(default_factory=list)
    lang: str = "uz"           # javob tili
    langs: list[str] = field(default_factory=list)   # gapda aniqlangan tillar
    confidence: float = 0.0


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


# ---------------------------------------------------------------- miqdor (raqam yoki so'z bilan: uz / ru / en)
_UNITS = {
    "bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "toqqiz": 9, "on": 10, "yigirma": 20,
    "ottiz": 30, "qirq": 40, "ellik": 50, "oltmish": 60, "yetmish": 70, "sakson": 80, "toqson": 90,
    "odin": 1, "dva": 2, "tri": 3, "chetire": 4, "pyat": 5, "shest": 6, "sem": 7, "vosem": 8, "devyat": 9, "desyat": 10,
    "dvadtsat": 20, "tridtsat": 30, "sorok": 40, "pyatdesyat": 50, "shestdesyat": 60, "semdesyat": 70, "vosemdesyat": 80, "devyanosto": 90,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_HUNDREDS = {"dvesti": 200, "trista": 300, "chetirista": 400, "pyatsot": 500}
_HUNDRED = {"yuz", "sto", "hundred"}
_THOUSAND = ("ming", "tisyach", "thousand")


def _number_words(n: str) -> float | None:
    total = cur = 0
    seen = False
    for tok in n.split():
        if tok in _UNITS:
            cur += _UNITS[tok]; seen = True
        elif tok in _HUNDREDS:
            cur += _HUNDREDS[tok]; seen = True
        elif tok in _HUNDRED:
            cur = (cur or 1) * 100; seen = True
        elif tok.startswith(_THOUSAND):
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


def parse(text: str) -> ParseResult:
    """Matn (ovoz yoki klaviatura) -> xavfsiz buyruqlar ro'yxati yoki aniqlashtiruvchi savol."""
    from . import nlu
    res = nlu.parse(text)
    assert all(c.action in ALLOWED_ACTIONS for c in res.commands)
    return res
