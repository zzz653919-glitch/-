"""Sana/vaqt iboralarini tushunish (o'zbekcha · ruscha · inglizcha): «10 daqiqadan keyin», «ertaga soat 9 da», «через 2 часа»,
«every Monday at 18:30», «15 may». Noaniq bo'lsa (9 — ertalabmi, kechqurunmi? vaqt yo'q? o'tib ketgan vaqt?) TAXMIN QILMAYDI:
`When.ask` to'ldiriladi va chaqiruvchi foydalanuvchidan so'raydi.

Barcha vaqtlar mahalliy (timezone'siz). `now` tashqaridan beriladi (testlar uchun).
"""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .commands import normalize

_NUM_WORDS = {
    "bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "toqqiz": 9, "on": 10, "yigirma": 20, "ottiz": 30,
    "odin": 1, "dva": 2, "tri": 3, "chetire": 4, "pyat": 5, "shest": 6, "sem": 7, "vosem": 8, "devyat": 9, "desyat": 10, "dvadtsat": 20, "tridtsat": 30,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "thirty": 30,
    "a": 1, "an": 1,
}
MONTHS = [("yanv", "jan"), ("fevr", "feb"), ("mart", "mar"), ("aprel", "apr"), ("may", "may"), ("iyun", "jun"), ("iyul", "jul"), ("avgust", "aug"),
          ("sent", "sep"), ("okt", "oct"), ("noyab", "nov"), ("dek", "dec")]
WEEKDAYS = [("dushanba", "ponedel", "monday"), ("seshanba", "vtorn", "tuesday"), ("chorshanba", "sred", "wednesday"), ("payshanba", "chetverg", "thursday"),
            ("juma", "pyatnits", "friday"), ("shanba", "subbot", "saturday"), ("yakshanba", "voskres", "sunday")]
TODAY, TOMORROW, DAYAFTER = {"bugun", "today", "todays", "segodnya", "segodnia"}, {"ertaga", "tomorrow", "zavtra"}, {"indinga", "poslezavtra"}
MORNING, AFTERNOON, EVENING, NIGHT = ("ertalab", "tongda", "morning", "utra", "utrom", "ertalabki"), ("kunduz", "afternoon", "dnya", "dnem", "kunduzi"), \
    ("kechqurun", "kechki", "evening", "vechera", "vecherom", "kechqurunki", "kech"), ("tunda", "tungi", "night", "nochi", "nochyu")
NOON, MIDNIGHT = {"tushda", "tush", "noon", "polden", "poludn"}, {"tunyarim", "midnight", "polnoch"}
UNIT_MIN = ("daqiq", "minut", "minute", "min")
UNIT_HOUR = ("soat", "chas", "hour", "hr")
UNIT_DAY = ("kun", "den", "dn", "day")
UNIT_WEEK = ("hafta", "nedel", "week")
AFTER = {"keyin", "ichida", "cherez", "in", "after", "later", "dan"}


@dataclass
class When:
    due: datetime | None = None
    recur: dict | None = None
    ask: str = ""                          # "" | time | ampm | past | date
    hour: int | None = None                # ampm so'ralganda: noaniq soat
    consumed: set[int] = field(default_factory=set)
    relative: bool = False
    day: date | None = None                # faqat sana aniqlangan bo'lsa ham to'ldiriladi (vazifa muddati uchun)
    has_clock: bool = False


def _words(text: str) -> tuple[list[str], list[str]]:
    raw = re.findall(r"\S+", text)
    return raw, [normalize(w).replace(" ", "") for w in raw]


def _num(tok: str) -> int | None:
    if tok.isdigit():
        return int(tok)
    return _NUM_WORDS.get(tok)


def _starts(tok: str, pre: tuple[str, ...]) -> bool:
    return tok.startswith(pre)


def _month_of(tok: str) -> int | None:
    for i, (uz, en) in enumerate(MONTHS, 1):
        if tok.startswith(uz) or (tok.startswith(en) and len(tok) >= 3):
            return i
    return None


def _weekday_of(tok: str) -> int | None:
    for i, forms in enumerate(WEEKDAYS):
        if any(tok.startswith(f) for f in forms):
            return i
    return None


def _add_months(d: datetime, n: int) -> datetime:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))


def next_occurrence(due: datetime, recur: dict | None, after: datetime) -> datetime | None:
    """Takrorlanuvchi eslatmaning `after` dan keyingi navbatdagi vaqti."""
    if not recur:
        return None
    t, n = recur.get("type"), max(1, int(recur.get("n", 1)))
    cur = due
    for _ in range(100000):
        if t == "interval":
            cur += timedelta(minutes=n)
        elif t == "daily":
            cur += timedelta(days=n)
        elif t == "weekly":
            cur += timedelta(weeks=n)
        elif t == "monthly":
            cur = _add_months(cur, n)
        elif t == "weekdays":
            cur += timedelta(days=1)
            while cur.weekday() >= 5:
                cur += timedelta(days=1)
        else:
            return None
        if cur > after:
            return cur
    return None


def _recurrence(raw: list[str], nw: list[str], consumed: set[int], now: datetime) -> dict | None:
    n = len(nw)
    for i, t in enumerate(nw):
        nxt = nw[i + 1] if i + 1 < n else ""
        two = f"{t} {nxt}"
        if t in ("har", "kajdiy", "kajduyu", "kajdoe", "kajdie", "kajdye", "every") or t.startswith("ejed") or t.startswith("ejen") or t.startswith("ejem"):
            if t.startswith("eje"):                                    # ejednevno / ejenedelno / ejemesyachno
                kind = "daily" if "dnev" in t else "weekly" if "nedel" in t else "monthly" if "mesyach" in t else None
                if kind:
                    consumed.add(i); return {"type": kind, "n": 1}
                continue
            if nxt in ("kuni", "kun", "den", "day", "kundalik"):
                consumed.update({i, i + 1}); return {"type": "daily", "n": 1}
            if nxt.startswith(("hafta", "nedel", "week")):
                consumed.update({i, i + 1}); return {"type": "weekly", "n": 1}
            if nxt.startswith(("oy", "mesyac", "month")) and nxt not in ("oyna",):
                consumed.update({i, i + 1}); return {"type": "monthly", "n": 1}
            wd = _weekday_of(nxt) if nxt else None
            if wd is not None:
                consumed.update({i, i + 1}); return {"type": "weekly", "n": 1, "weekday": wd}
            k = _num(nxt) if nxt else None
            if k and i + 2 < n and _starts(nw[i + 2], UNIT_MIN + UNIT_HOUR):
                mins = k * (60 if _starts(nw[i + 2], UNIT_HOUR) else 1)
                consumed.update({i, i + 1, i + 2}); return {"type": "interval", "n": mins}
            if nxt.startswith(("daqiq", "minut")):
                consumed.update({i, i + 1}); return {"type": "interval", "n": 1}
            if nxt.startswith(("soat", "chas", "hour")):
                consumed.update({i, i + 1}); return {"type": "interval", "n": 60}
        if t in ("daily", "kundalik"):
            consumed.add(i); return {"type": "daily", "n": 1}
        if t == "weekly":
            consumed.add(i); return {"type": "weekly", "n": 1}
        if t == "monthly":
            consumed.add(i); return {"type": "monthly", "n": 1}
        if two in ("ish kunlari", "po budnyam", "every weekday") or t in ("budnyam", "weekdays"):
            consumed.update({i, i + 1} if t not in ("budnyam", "weekdays") else {i}); return {"type": "weekdays", "n": 1}
        if t == "kunda" or t == "kuniga":
            consumed.add(i); return {"type": "daily", "n": 1}
    return None


def parse_when(text: str, now: datetime) -> When:
    raw, nw = _words(text)
    w = When()
    c = w.consumed
    n = len(nw)
    lower = [r.lower() for r in raw]

    w.recur = _recurrence(raw, nw, c, now)

    # ---- nisbiy vaqt: «10 daqiqadan keyin», «in 2 hours», «через полчаса», «yarim soatdan keyin»
    delta: timedelta | None = None
    for i, t in enumerate(nw):
        if i in c:
            continue
        if t == "polchasa" or (t == "half" and i + 1 < n and nw[i + 1].startswith(("hour", "an"))) or (t == "yarim" and i + 1 < n and nw[i + 1].startswith("soat")):
            if t == "polchasa" or t == "yarim" or t == "half":
                delta = timedelta(minutes=30)
                c.add(i)
                if t != "polchasa":
                    c.add(i + 1)
                    if t == "half" and i + 2 < n and nw[i + 2].startswith("hour"):
                        c.add(i + 2)
                break
        k = _num(t)
        if k is None or i + 1 >= n or i in c:
            continue
        unit = nw[i + 1]
        mult = (timedelta(minutes=k) if _starts(unit, UNIT_MIN) else timedelta(hours=k) if _starts(unit, UNIT_HOUR) and not (i > 0 and nw[i - 1] == "soat")
                else timedelta(days=k) if _starts(unit, UNIT_DAY) else timedelta(weeks=k) if _starts(unit, UNIT_WEEK) else None)
        if mult is None:
            continue
        around = {nw[j] for j in (i - 1, i + 2, i + 3) if 0 <= j < n}
        has_marker = bool(around & AFTER) or unit.endswith(("dan", "da")) or (i > 0 and nw[i - 1] in ("in", "cherez", "after"))
        if has_marker and not (i > 0 and nw[i - 1] in ("har", "every", "kazhdie", "kazhdye")):
            delta = mult
            c.update({i, i + 1})
            for j in (i - 1, i + 2):
                if 0 <= j < n and nw[j] in AFTER and nw[j] != "dan":
                    c.add(j)
            break
    if delta is not None:
        w.due = (now + delta).replace(second=0, microsecond=0) if delta >= timedelta(minutes=1) else now
        w.relative = True
        return w

    # ---- kun
    day = None                               # datetime.date
    for i, t in enumerate(nw):
        if i in c:
            continue
        if t in TODAY:
            day = now.date(); c.add(i)
        elif t in TOMORROW:
            day = (now + timedelta(days=1)).date(); c.add(i)
        elif t in DAYAFTER:
            day = (now + timedelta(days=2)).date(); c.add(i)
        elif t == "day" and i + 2 < n and nw[i + 1] == "after" and nw[i + 2] == "tomorrow":
            day = (now + timedelta(days=2)).date(); c.update({i, i + 1, i + 2})
    # sana: 15.05 / 15/05 / 15.05.2026 / 2026-05-15 / «15 may» / «may 15»
    for i, r in enumerate(lower):
        if i in c:
            continue
        m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", r.strip(".,"))
        m2 = re.fullmatch(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", r.strip(".,"))
        try:
            if m:
                day = datetime(int(m[1]), int(m[2]), int(m[3])).date(); c.add(i)
            elif m2 and 1 <= int(m2[2]) <= 12:
                y = int(m2[3]) if m2[3] else None
                y = y + 2000 if y is not None and y < 100 else y
                cand = datetime(y or now.year, int(m2[2]), int(m2[1])).date()
                if y is None and cand < now.date():
                    cand = cand.replace(year=now.year + 1)
                day = cand; c.add(i)
        except ValueError:
            w.ask = "date"; return w
    for i, t in enumerate(nw):
        if i in c:
            continue
        mo = _month_of(t) if not t.isdigit() else None
        if mo is None:
            continue
        d = None
        if i > 0 and nw[i - 1].isdigit() and (i - 1) not in c:
            d = int(nw[i - 1]); c.update({i - 1, i})
        elif i + 1 < n and nw[i + 1].isdigit() and (i + 1) not in c and int(nw[i + 1]) <= 31:
            d = int(nw[i + 1]); c.update({i, i + 1})
        if d:
            try:
                cand = datetime(now.year, mo, d).date()
            except ValueError:
                w.ask = "date"; return w
            if cand < now.date():
                cand = cand.replace(year=now.year + 1)
            day = cand
    wd_target = None
    for i, t in enumerate(nw):
        if i in c or (i == 0 and t.startswith("pyatnits")):                    # «Пятница, ...» — yordamchining ismi
            continue
        wd = _weekday_of(t)
        if wd is not None and not (i > 0 and nw[i - 1] in ("har", "every")):
            wd_target = wd; c.add(i)
            for j in (i - 1,):
                if j >= 0 and nw[j] in ("v", "vo", "on", "next", "kelasi", "keyingi"):
                    c.add(j)
    if wd_target is None and w.recur and w.recur.get("weekday") is not None:
        wd_target = w.recur["weekday"]

    # ---- soat
    hour = minute = None
    explicit_24 = False
    daypart = None
    ampm = None
    for i, r in enumerate(lower):
        if i in c:
            continue
        m = re.fullmatch(r"(\d{1,2}):(\d{2})(am|pm)?[,.]?", r)
        m3 = re.fullmatch(r"(\d{1,2})(am|pm)[,.]?", r)
        if m:
            hour, minute = int(m[1]), int(m[2])
            ampm = m[3]; explicit_24 = (hour >= 13 or hour == 0) and not ampm
            c.add(i)
            if i > 0 and nw[i - 1] in ("soat", "at", "v", "vo", "k", "around"):
                c.add(i - 1)
            if i + 1 < n and nw[i + 1] in ("da", "de", "oclock"):
                c.add(i + 1)
        elif m3:
            hour, minute, ampm = int(m3[1]), 0, m3[2]; c.add(i)
            if i > 0 and nw[i - 1] in ("soat", "at", "v", "vo", "k", "around"):
                c.add(i - 1)
        if hour is not None:
            break
    if hour is None:
        for i, t in enumerate(nw):
            if i in c or not t.isdigit() or int(t) > 24:
                continue
            prev = nw[i - 1] if i > 0 else ""
            nxt = nw[i + 1] if i + 1 < n else ""
            if prev in ("soat", "at", "v", "vo", "k", "around", "chasov") or nxt in ("da", "de", "oclock", "chasov", "chasa", "am", "pm") or nxt.startswith(("ertalab", "kech", "tush", "tun", "utra", "vecher", "nochi", "dnya", "morning", "evening", "night", "afternoon")):
                hour, minute = int(t), 0
                c.add(i)
                if prev in ("soat", "at", "v", "vo", "k", "around"):
                    c.add(i - 1)
                if nxt in ("da", "de", "oclock", "chasov", "chasa"):
                    c.add(i + 1)
                if nxt in ("am", "pm"):
                    ampm = nxt; c.add(i + 1)
                break
    for i, t in enumerate(nw):                    # kun qismi
        if i in c:
            continue
        if t == "tushdan" and i + 1 < n and nw[i + 1] == "keyin":
            daypart = "afternoon"; c.update({i, i + 1})
        elif t in NOON or t == "tushlik":
            if hour is None and t in NOON:
                hour, minute, explicit_24 = 12, 0, True
            c.add(i)
        elif t in MIDNIGHT or (t == "yarim" and i + 1 < n and nw[i + 1].startswith("kech")):
            hour, minute, explicit_24 = 0, 0, True; c.add(i)
            if t == "yarim":
                c.add(i + 1)
        elif _starts(t, MORNING):
            daypart = "morning"; c.add(i)
        elif _starts(t, AFTERNOON):
            daypart = daypart or "afternoon"; c.add(i)
        elif _starts(t, EVENING) and t != "kechasi":
            daypart = daypart or "evening"; c.add(i)
        elif _starts(t, NIGHT):
            daypart = daypart or "night"; c.add(i)

    if hour is None:
        if day is None and wd_target is not None:
            day = (now + timedelta(days=(wd_target - now.date().weekday()) % 7 or 7)).date()
        w.day = day
        if day is not None or wd_target is not None or w.recur:
            if w.recur and w.recur.get("type") in ("interval",):
                w.due = (now + timedelta(minutes=w.recur["n"])).replace(second=0, microsecond=0)
                return w
        w.ask = "time"
        return w
    if minute is None:
        minute = 0
    if hour > 24 or minute > 59:
        w.ask = "time"; return w
    if ampm == "pm" and hour < 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    elif ampm is None and daypart:
        if daypart == "morning" and hour == 12:
            hour = 0
        elif daypart in ("afternoon", "evening") and hour < 12:
            hour += 12
        elif daypart == "night":
            hour = hour if hour <= 5 else (hour + 12 if hour < 12 else 0)
    elif ampm is None and not explicit_24 and 1 <= hour <= 12:
        w.ask, w.hour = "ampm", hour                  # 9 — ertalabmi, kechqurunmi? Taxmin qilinmaydi
        return w
    hour %= 24

    if wd_target is not None:
        ahead = (wd_target - now.date().weekday()) % 7
        cand_today = datetime.combine(now.date(), datetime.min.time()).replace(hour=hour, minute=minute)
        if ahead == 0 and cand_today <= now:
            ahead = 7
        day = (now + timedelta(days=ahead)).date()
    if day is None:
        cand = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if hour == 0 and minute == 0 and cand <= now:                 # «yarim kecha» — keyingi yarim kecha
            day = (now + timedelta(days=1)).date()
        elif w.recur or cand > now:
            day = now.date() if cand > now else (now + timedelta(days=1)).date()
        else:
            w.due = cand
            w.ask = "past"                              # bugungi vaqt o'tib ketgan: ertaga deb taxmin qilinmaydi
            return w
    due = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
    w.day, w.has_clock = day, True
    if due <= now and not w.recur:
        w.due, w.ask = due, "past"
        return w
    if due <= now and w.recur:
        due = next_occurrence(due, w.recur, now) or due
    w.due = due
    return w
