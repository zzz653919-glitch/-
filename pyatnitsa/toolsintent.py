"""Media boshqaruvi buyruqlarini tushunish (uz · ru · en).
  «pauza», «keyingi qo'shiq», «ovozni oshir», «next track», «volume down», «громче», «следующий трек»
Media tugmasi Windows'ga yuboriladi; dastur javob berganini bilib bo'lmaydi, shuning uchun «bajarildi» deb aytilmaydi.
Xavfli fe'l bo'lsa hamma narsa rad etiladi."""
from __future__ import annotations

import re

from . import nlu
from .commands import Command, ParseResult, normalize
from .i18n import T

PLAY_EX = {"pauza", "pause", "pauzaga", "pauzani", "pauzu", "play", "resume", "plei"}   # «davom et / продолжай» — suhbatni davom ettirish (AI), media emas
STOP_EX = {"stop", "toxtat", "toxtating", "toxtatib", "ostanovi", "ostanovit"}
NEXT_PRE, PREV_PRE = ("keyingi", "next", "sleduyush", "dalshe", "skip"), ("oldingi", "previous", "prev", "predidush", "predyduch")
MEDIA_NOUNS = ("qoshiq", "trek", "track", "song", "video", "musiq", "pesn", "klip", "media", "music", "muzik", "audio")
VOL_NOUN = ("ovoz", "volume", "zvuk", "gromkost", "sound")
UP_PRE, DOWN_PRE = ("oshir", "kotar", "balandla", "kopayt", "uvelich", "povys", "increas", "rais", "louder", "gromche", "up"), \
    ("kamayt", "pasayt", "pasay", "kichrayt", "umensh", "ponij", "tishe", "quieter", "softer", "decreas", "lower", "reduc", "down")
MUTE_EX = {"mute", "unmute", "ovozsiz", "bezzvuka", "jim"}


def _norm_words(text: str) -> list[str]:
    return [normalize(w).replace(" ", "") for w in re.findall(r"\S+", text) if normalize(w)]


def _danger(text: str):
    clauses, lang, found = nlu.analyze(text)
    return any(cl.has("DANGER") for cl in clauses), lang, sorted(found)


def parse(text: str, prior: ParseResult | None = None) -> ParseResult | None:
    raw = (text or "").strip()[:400]
    nw = _norm_words(raw)
    if not nw or any(t.startswith(("google", "gugl", "youtube", "yutub")) for t in nw):
        return None
    return _media(raw, nw)


def _media(raw: str, nw: list[str]) -> ParseResult | None:
    short = len(nw) <= 3
    has_media_noun = any(t.startswith(MEDIA_NOUNS) for t in nw)
    key = ""
    if any(t.startswith(VOL_NOUN) for t in nw) or any(t in ("gromche", "tishe", "louder", "quieter") for t in nw):
        if any(t in MUTE_EX for t in nw) or ("bez" in nw and any(t.startswith("zvuk") for t in nw)):
            key = "mute"
        elif any(t.startswith(UP_PRE) for t in nw):
            key = "vol_up"
        elif any(t.startswith(DOWN_PRE) for t in nw):
            key = "vol_down"
    elif any(t in MUTE_EX for t in nw) and short:
        key = "mute"
    if not key and (has_media_noun or short):
        if any(t.startswith(NEXT_PRE) for t in nw):
            key = "next"
        elif any(t.startswith(PREV_PRE) for t in nw):
            key = "prev"
        elif any(t in STOP_EX for t in nw) and (short or has_media_noun):
            key = "stop"
        elif any(t in PLAY_EX for t in nw) and (short or has_media_noun) and not any(t.startswith(("fayl", "file")) for t in nw):
            key = "play_pause"
    if not key:
        return None
    bad, lang, found = _danger(raw)
    if bad:
        return ParseResult("blocked", message=T("blocked", lang), lang=lang, langs=found, confidence=1.0)
    cmd = Command("media", {"key": key}, T("ask.media", lang, what=T(f"media.{key}", lang)), intent="media_control", needs_confirm=False)
    return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)
