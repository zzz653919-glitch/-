"""Niyat yo'naltiruvchisi: oddiy suhbat va kompyuter buyruqlarini ajratadi. Mahalliy va qoidalarga asoslangan (AI'ga yuborishdan oldin).

Kategoriyalar:  GENERAL_CONVERSATION · QUESTION_ANSWERING · COMPUTER_COMMAND · CURRENT_INFORMATION · CLARIFICATION_REQUIRED
Xavfsizlik: faqat COMPUTER_COMMAND / qo'llab-quvvatlanadigan CURRENT_INFORMATION mavjud tasdiqlangan buyruq tizimiga (nlu → executor) boradi.
Suhbat kategoriyalari AI'ga boradi va AI javobi hech qachon buyruq sifatida talqin qilinmaydi.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import commands
from .commands import ParseResult, normalize

GENERAL_CONVERSATION = "GENERAL_CONVERSATION"
QUESTION_ANSWERING = "QUESTION_ANSWERING"
COMPUTER_COMMAND = "COMPUTER_COMMAND"
CURRENT_INFORMATION = "CURRENT_INFORMATION"
CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
CATEGORIES = (GENERAL_CONVERSATION, QUESTION_ANSWERING, COMPUTER_COMMAND, CURRENT_INFORMATION, CLARIFICATION_REQUIRED)

_INFO_ACTIONS = {"rate_usd", "convert_usd", "weather", "time", "health_status", "health_cpu", "health_ram", "health_disk", "health_temps",
                 "health_gpu", "health_battery", "health_uptime", "health_full", "health_report", "health_top", "speedup_advice", "admin_info"}


@dataclass
class Route:
    category: str
    reason: str
    lang: str = "uz"
    live_unsupported: bool = False      # jonli ma'lumot kerak, lekin ilovada manba yo'q
    parse: ParseResult | None = None

    @property
    def to_ai(self) -> bool:
        return self.category in (GENERAL_CONVERSATION, QUESTION_ANSWERING) or (self.category == CURRENT_INFORMATION and self.live_unsupported)


# ----------------------------------------------------------------------------- til
_EN = set("the is are was were what why how who when where which can could would should please you your my me i do does did not this that it a an of to in on "
          "for with and hello hi hey thanks thank explain tell help give example learn english about from have has will yes no good morning "
          "remind reminder reminders tomorrow today tonight task tasks note notes study plan finished completed mark add create show called named vocabulary grammar "
          "listening reading writing progress overdue homework week every day at am pm minutes hours later find open latest video file files".split())
_UZ = set("men sen siz biz u bu shu va ham lekin uchun bilan nima nega qanday qaysi kim qachon qayer qayerda bor yoq yoqmi ha yaxshi rahmat salom iltimos ber ayt "
          "tushuntir misol haqida menga sizga bugun hozir uni buni nechta qancha kerak mumkin boladi bolsa yaxshimisan qil qilib ol ham hali endi nimaga "
          "oldingi gapimizni davom ettir menimcha bilasanmi aytib yordam o'rgan organ "
          "eslat eslatma eslatmalarni vazifa vazifam vazifamni vazifalarimni qayd qaydlar ertaga soat keyin bajarildi belgila tugatdim ingliz tili reja rejamni "
          "dori ichish ichishni topib och top qidir".split())


def detect_language(text: str) -> str:
    """uz | ru | en (yozuv turi va keng tarqalgan so'zlar bo'yicha). Aralash/noaniq holatda o'zbekcha."""
    low = text.lower()
    cyr = len(re.findall(r"[а-яё]", low))
    lat = len(re.findall(r"[a-z]", low))
    if re.search(r"[ўқғҳ]", low):
        return "uz"
    words = re.findall(r"[a-z']+", normalize_keep_apostrophe(low))
    en = sum(w in _EN for w in words)
    uz = sum(w.replace("'", "") in _UZ or w in _UZ for w in words)
    uz += sum(1 for w in words if len(w) > 5 and w.rstrip("'").endswith(("ishni", "imni", "ingni", "larni", "lari", "ning", "dan", "ishga")) and w not in _EN)   # o'zbekcha qo'shimchalar
    if cyr and (not lat or cyr >= lat):
        return "uz" if uz else "ru"        # kirill ustun; lotincha o'zbekcha so'zlar bo'lsa — aralash (o'zbekcha)
    if cyr and lat:
        return "uz"                        # aralash
    return "en" if en > uz else "uz"


def normalize_keep_apostrophe(s: str) -> str:
    for c in "ʻʼ’‘`´′ʹ":
        s = s.replace(c, "'")
    return s


# ----------------------------------------------------------------------------- belgilar (normallashtirilgan lotin yozuvida)
_WHY_HOWTO = [re.compile(p) for p in (
    r"\b(nega|nimaga|nima uchun|nimadan)\b", r"\b(why|how come)\b", r"\b(pochemu|zachem|otchego)\b",
    r"\bqanday qilib\b", r"\bqanday \w*(aman|ayman|sam|asam|ish kerak|ish mumkin|ilad)\b", r"\bqanday \w+ (kerak|mumkin|boladi)\b", r"\bhow (to|do|can|should|would) (i|we|you)?\b", r"\bhow to\b",
    r"\bkak (mne |nam |mozhno |ya )?\w*(at|it|et|ut|yt)\b(?! kompyuter)", r"\bkak (ya )?(mogu|nuzhno|sdelat|ustanovit|otkrit|udalit|vklyuchit)",
    r"\bochish yoli\b", r"\bnima qilishim kerak\b", r"\bchto delat\b", r"\bwhat should i\b")]
_PROBLEM = [re.compile(p) for p in (
    r"\b(ochilmay\w*|ishlamay\w*|chiqmay\w*|yuklanmay\w*|qotib\w*|osilib\w*|xato\w*|muammo\w*|sekin)\b", r"\b(ne otkriva\w*|ne rabota\w*|ne zapuska\w*|zavis\w*|oshibk\w*|tormoz\w*)\b",
    r"\b(not working|doesn t|does not|won t|will not|cant|can t|cannot|isn t working|error|crash\w*|freez\w*|stuck|broken|slow)\b")]
_EXPLAIN = [re.compile(p) for p in (
    r"\b(nima bu|nima degani|nimani anglatadi|manosi|ma nosi|farqi|tushuntir\w*|izohla\w*|aytib ber\w*|gapirib ber\w*|hikoya\w*|maslahat\w*|yordam ber\w*|oyla\w*|fikr\w*)\b",
    r"\b(chto takoe|chto znachit|raznitsa|obyasni\w*|rasskaj\w*|rasskaz\w*|posovetuy\w*|pomogi\w*|pomoch)\b",
    r"\b(what is|what are|what does|what s|who is|who was|explain\w*|describe|difference|meaning|tell me|help me|advice|suggest\w*|teach me|story)\b",
    r"\b(\w+ nima|nima \w+|kim \w+|\w+ kim)\b")]
_GREETING = re.compile(r"^(salom|assalomu|assalom|hello|hi|hey|privet|zdravstv\w*|zdravstvuyte|dobry\w*|good (morning|evening|day)|hayr|xayr|rahmat|spasibo|thanks|thank you|"
                       r"yaxshimisan|yaxshimisiz|qalaysan|qalaysiz|kak dela|how are you|nima gap|ishlaring)\b")
_CONTINUE = re.compile(r"\b(oldingi|davom ett\w*|davom et\w*|yana|ham ber|misol ber\w*|misol ham|uni |buni |ob\w*|prodolzh\w*|dalshe|eshche|esche|continue|go on|more|another|example|primer)\b")
_QWORD = re.compile(r"\b(nima|nega|nimaga|kim|qachon|qayerda|qayer|qanday|qanaqa|qaysi|nechta|necha|qancha|pochemu|zachem|chto|kto|kogda|gde|kak|kakoy\w*|skolko|"
                    r"what|why|how|who|when|where|which|is|are|can|could|does|do)\b")
_MARKET = re.compile(r"\b(evro|euro|rubl\w*|bitcoin|bitkoin\w*|btc|akciy\w*|aksiya\w*|stock\w*|ethereum|nasdaq)\b")
_PRICEY = re.compile(r"\b(kurs\w*|narx\w*|price\w*|rate|qancha|how much|skolko|cena|stoit|tushdi|osdi|necha)\b")
_LIVE = [re.compile(p) for p in (
    r"\b(yangilik\w*|news|novosti|lenta)\b",
    r"\b(hozirgi|current|segodnyashn\w*|sejchas|seychas|latest|oxirgi|poslednie)\b.*\b(prezident|president|narx|price|cena|kurs|natija|score|chempion\w*)\b",
    r"\b(prezident\w*|president)\b.*\b(hozir|current|seychas|sejchas|bugun)\b", r"\b(match|o yin|game)\b.*\b(natija|score|schet|schyot|result)\b",
    r"\b(who won|who is winning|kim yutdi|kto vyigral|kto viigral)\b")]


def _is_live(n: str) -> bool:
    return any(p.search(n) for p in _LIVE) or bool(_MARKET.search(n) and _PRICEY.search(n))


def _solid_concept(text: str) -> bool:
    """Gapda taxminiy (imlo tuzatish) bo'lmagan, aniq buyruq so'zi/ob'ekti bormi? Faqat taxminiy moslik asosida «aniqlashtirish» so'ralmaydi."""
    from . import nlu
    clauses, _, _ = nlu.analyze(text)
    return any(t.concept not in (None, "FUNC", "GREET") and not t.fuzzy for c in clauses for t in c.toks)


_WEAK = {"time", "rate_usd", "convert_usd", "weather", "health_status", "health_top", "health_uptime", "health_cpu", "health_ram", "health_disk"}


def _mostly_unrelated(text: str) -> bool:
    """«Yer Quyosh atrofida qancha VAQTda aylanadi?»: buyruq so'zi tasodifan uchragan, gapning asosi boshqa mavzu."""
    from . import nlu
    clauses, _, _ = nlu.analyze(text)
    toks = [t for c in clauses for t in c.toks]
    unknown = sum(1 for t in toks if t.concept is None)
    known = sum(1 for t in toks if t.concept not in (None, "FUNC", "GREET"))
    return unknown >= 3 and unknown > known


def _any(pats, n: str) -> bool:
    return any(p.search(n) for p in pats)


# ----------------------------------------------------------------------------- asosiy
def route(text: str, parsed: ParseResult | None = None, has_history: bool = False) -> Route:
    text = (text or "").strip()
    n = normalize(text)
    lang = detect_language(text)
    res = parsed if parsed is not None else commands.parse(text)
    qmark = "?" in text
    wordy = len(n.split())
    why = _any(_WHY_HOWTO, n)
    problem = _any(_PROBLEM, n)
    explain = _any(_EXPLAIN, n)
    qlike = qmark or bool(_QWORD.search(n))
    live = _is_live(n)

    if not n:
        return Route(CLARIFICATION_REQUIRED, "empty", lang, parse=res)

    # 1) «Nega ...», «qanday qilib ...», «how to ...»: tushuntirish so'raladi, buyruq emas (xavfli so'zlar bo'lsa ham hech narsa bajarilmaydi)
    if why:
        return Route(QUESTION_ANSWERING, "why/how-to question", lang, parse=res)
    # 2) tasdiqlangan buyruq (ochish, kurs, vaqt, ob-havo, kompyuter holati ...)
    if res.kind == "ok" and all(c.action in _WEAK for c in res.commands) and _mostly_unrelated(text):
        return Route(QUESTION_ANSWERING, "command word appears in an unrelated sentence", lang, parse=res)
    if res.kind == "ok":
        if problem and not explain and any(c.action not in _INFO_ACTIONS and c.action != "speedup_advice" for c in res.commands):
            return Route(QUESTION_ANSWERING, "problem statement mentions an app", lang, parse=res)
        info = all(c.action in _INFO_ACTIONS for c in res.commands)
        return Route(CURRENT_INFORMATION if info else COMPUTER_COMMAND, "validated command", lang, parse=res)
    if res.kind == "clarify" and getattr(res, "draft", ""):      # eslatma/vazifa/qayd: vaqt yoki nom yetishmaydi — javob shu so'rovga qo'shiladi (AI'ga yuborilmaydi)
        return Route(CLARIFICATION_REQUIRED, "needs more details", lang, parse=res)
    # 3) xavfli / ruxsat etilmagan buyruq — mavjud rad etish xabari (savol shaklida bo'lsa — tushuntirish; AI baribir hech narsa bajarmaydi)
    if res.kind == "blocked" and (qmark or explain):
        return Route(QUESTION_ANSWERING, "question about a risky action (explanation only)", lang, parse=res)
    if res.kind == "blocked":
        return Route(COMPUTER_COMMAND, "blocked by safety rules", lang, parse=res)
    # 4) salomlashish; jonli ma'lumot (manba yo'q), keyin muammo / tushuntirish / savol
    if _GREETING.search(n) and not live:
        return Route(GENERAL_CONVERSATION, "greeting / small talk", lang, parse=res)
    if live:
        return Route(CURRENT_INFORMATION, "needs live data (no source in the app)", lang, live_unsupported=True, parse=res)
    if problem or explain:
        return Route(QUESTION_ANSWERING, "problem or explanation request", lang, parse=res)
    if _GREETING.search(n):
        return Route(GENERAL_CONVERSATION, "greeting / small talk", lang, parse=res)
    if qlike:
        return Route(QUESTION_ANSWERING, "question", lang, parse=res)
    # 5) buyruqqa o'xshash, lekin to'liq emas
    if res.kind == "clarify" and wordy <= 4 and _solid_concept(text):
        return Route(CLARIFICATION_REQUIRED, "incomplete command", lang, parse=res)
    # 6) salomlashish, davom ettirish, boshqa gaplar
    if _GREETING.search(n) or _CONTINUE.search(n) or (has_history and wordy <= 6):
        return Route(GENERAL_CONVERSATION, "conversation", lang, parse=res)
    return Route(GENERAL_CONVERSATION, "statement", lang, parse=res)
