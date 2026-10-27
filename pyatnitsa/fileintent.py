"""Fayl buyruqlarini tushunish (o'zbekcha · ruscha · inglizcha · aralash): topish, ko'rsatish, ro'yxat, ochish, "eng yangi".

`parse()` faqat tayyor, tekshirilgan `Command` qaytaradi (find_files / list_files). Hech narsa bajarmaydi va yo'l YASAMAYDI:
fayl nomi/nom bo'lagi faqat qidiruv so'rovi (ma'lumot) bo'ladi. Xavfli fe'llar (o'chir, ko'chir, nomini o'zgartir, yubor ...) —
fayl nomi ichida bo'lmasa — hamma narsani rad etadi. Ochish alohida tasdiqlanadigan `open_file` buyrug'i bilan, ro'yxatdan tanlangandan keyin.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from . import nlu
from .commands import Command, ParseResult, normalize
from .files import KIND_EXT, OPENABLE_EXT, RISKY_EXT
from .i18n import T

# ----------------------------------------------------------------------------- so'z to'plamlari (normalizatsiya qilingan: lotin, kichik harf, apostrofsiz)
FIND_EX = {"top", "topib", "topish", "topgin", "topsang", "topingiz", "ishi", "ishite"}
FIND_PRE = ("qidir", "izla", "nayd", "nayt", "poish", "poisk", "find", "search", "locat", "lookup")
OPEN_EX = {"och", "ochib", "oching", "ochgin", "ochvor", "ochay", "ochaymi", "ochish", "qoy", "qoyib", "qoying", "qoyvor", "play", "open", "launch", "watch",
           "pusti", "pustit", "start", "playing"}
OPEN_PRE = ("otkr", "zapust", "vklyuch", "vosproizv", "posmotr", "smotr", "ijro")
SHOW_EX = {"ber", "bering", "royxat", "list", "show", "display", "spisok", "vivedi", "chiqar", "chiqaring", "showing", "see"}
SHOW_PRE = ("korsat", "pokaj", "pokaz", "chiqar", "vivod")
LATEST_WORDS = {"oxirgi", "oxirgisi", "songgi", "latest", "newest", "svejiy", "svejie", "noveyshiy", "noveyshee"}
KIND_PRE = {
    "video": ("video", "film", "kino", "klip", "rolik", "movie", "clip", "vidyo", "vidio"),
    "image": ("rasm", "surat", "foto", "photo", "image", "picture", "kartin", "izobraj", "snimok", "screenshot", "skrinshot"),
    "audio": ("musiq", "qoshiq", "audio", "muzik", "pesn", "music", "song"),
    "document": ("hujjat", "dokument", "document"),
}
FILE_PRE = ("fayl", "file")
FOLDER_PRE = ("papk", "folder", "katalog", "direct")
FILEMGR_PRE = ("menej", "manag", "explor", "provodn")
COMPUTER_PRE = ("kompyuter", "komputer", "noutbuk", "notebook", "laptop", "computer")
ALL_PRE = ("barcha", "hamma", "vse", "all", "every", "butun")
AUTH_PRE = ("ruxsat", "razresh", "authori", "allowed", "permit", "avtoriz")
REQ_PRE = ("requested", "soragan", "soradim", "sorag", "zaprosil", "zapros", "prosil", "asked")
PERSON_PRE = ("person", "people", "odam", "inson", "kishi", "chelovek", "lyud", "shaxs")
REF_WORDS = {"shu", "shuni", "bu", "buni", "osha", "this", "that", "those", "these", "etot", "etu", "eto", "etogo", "etoy", "tot", "togo", "toy", "tu", "ana", "it", "its", "uni", "ega"}
LANG_EX = {"ru": {"rus", "russian", "russkiy", "russkie", "russki", "russkom", "ruscha", "russkoe", "russkih"},
           "uz": {"uzbek", "uzbekcha", "ozbek", "ozbekcha", "uzbekskie", "uzbekskiy", "uzbekski"},
           "en": {"english", "inglizcha", "ingliz", "angliyskie", "angliyskiy", "angliyski", "angliyskom"}}
LANGWORD_PRE = ("til", "yazik", "language", "lang")
WEB_PRE = ("google", "gugl", "youtube", "yutub", "yutyub", "internet", "brauzer", "browser", "chrome", "chrom", "veb", "web", "sayt", "site", "onlayn", "online")
WEB_SUB = ("gugl", "google", "youtube", "yutub", "internet", "brauzer", "browser", "chrome")      # «Погугли», «Googleda» kabi shakllar ham
NOT_KIND_PRE = ("videokart", "videoplat", "videoadapt", "videopam")                                  # videokarta — qurilma, video fayl emas
ALIAS_EXACT = {"downloads": "downloads", "download": "downloads", "desktop": "desktop"}
ALIAS_PRE = {"downloads": ("download", "daunlod", "yuklama", "yuklab", "yuklan", "zagruz"), "desktop": ("desktop", "dekstop", "dasktop")}
AMBIG_ALIAS = {  # folder so'zi yonida bo'lsagina papka nomi (aks holda tur so'zi)
    "documents": {"documents", "dokumenti", "dokumentlar", "hujjatlar", "dokumentu"},
    "pictures": {"pictures", "rasmlar", "suratlar", "izobrajeniya", "kartinki", "fotografii"},
    "music": {"music", "musiqa", "musiqalar", "muzika", "muziki"},
    "videos": {"videos", "videolar", "video", "vidyo"},
}
STOP = set(("ni ga da dan ning dagi idagi iltimos menga meni men mening mani uchun haqida boyicha ekan va hamda keyin bor boladi borlari "
            "berilgan joy joyi joylar joylardan joylarda joyda mavjud mavjudlar ularni uni ular bilan kerak kerakli nomli nomi nomini nomlangan degan deb ayting ayt "
            "mne pozhaluysta dlya pro na v vo po iz potom zatem imenem nazvaniem nazvanie nazivaetsya moi moy moim moih moyom moego moya "
            "mesta mestah mestax dostupnie dostupnix dostupnih imeyushiesya "
            "the a an please to my me of for about on and then named called from in at with any some available i is are there want need can you could "
            "stored saved local locally pc").split())


def _starts(t: str, pre: tuple[str, ...]) -> bool:
    return t.startswith(pre)


_EXT_ALT = "|".join(sorted(OPENABLE_EXT | RISKY_EXT | {"zip", "rar", "7z", "tar", "gz"}, key=len, reverse=True))
FNAME_RE = re.compile(rf"(?<![\w.])([^\s\"'«»“”<>|:*?\\/]+)\.({_EXT_ALT})(?!\w)", re.IGNORECASE)
QUOTE_RE = re.compile(r"[\"«“]([^\"»”]{1,120})[\"»”]")
KNOWN_EXTS = OPENABLE_EXT | RISKY_EXT | {"zip", "rar", "7z", "tar", "gz"}
KIND_OF_EXT_SAFE = {e: k for k, exts in KIND_EXT.items() for e in exts}


@dataclass
class Choice:
    kind: str                 # pick | open | cancel
    index: int | None = None  # 0-based; None = "bitta"/"shu"


# ----------------------------------------------------------------------------- yordamchi
def _norm_tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t]


def _is_find(t: str) -> bool:
    return t in FIND_EX or _starts(t, FIND_PRE)


def _is_open(t: str) -> bool:
    return t in OPEN_EX or _starts(t, OPEN_PRE)


def _is_show(t: str) -> bool:
    return t in SHOW_EX or _starts(t, SHOW_PRE)


def _is_web(t: str) -> bool:
    return t.startswith(WEB_PRE) or any(w in t for w in WEB_SUB)


def _kind_of(t: str) -> str | None:
    if t.startswith(NOT_KIND_PRE):
        return None
    for k, pre in KIND_PRE.items():
        if _starts(t, pre):
            return k
    return None


def _lang_of(t: str) -> str | None:
    for l, words in LANG_EX.items():
        if t in words:
            return l
    return None


def kind_label(kind: str, lang: str) -> str:
    return T(f"files.kind.{kind}", lang)


def _describe(args: dict, lang: str) -> str:
    kinds = args.get("kinds") or []
    what = ", ".join(kind_label(k, lang) for k in kinds) if kinds else T("files.kind.file", lang)
    q = args.get("query") or ", ".join("." + e for e in args.get("exts", []))
    return f"{what}" + (f" «{q}»" if q else "")


# ----------------------------------------------------------------------------- asosiy tahlil
def parse(text: str, prior: ParseResult | None = None) -> ParseResult | None:
    """Fayl buyrug'i bo'lsa ParseResult (ok/clarify/blocked), aks holda None (oddiy NLU davom etadi)."""
    raw = (text or "").strip()[:500]
    if not raw:
        return None
    # --- nom ma'lumotlari: fayl nomlari va qo'shtirnoqdagi matn buyruq emas, MA'LUMOT
    data: list[str] = []
    exts: set[str] = set()

    def take_fname(m: re.Match) -> str:
        data.append(m.group(1))
        exts.add(m.group(2).lower())
        return " "

    work = FNAME_RE.sub(take_fname, raw)

    def take_quote(m: re.Match) -> str:
        data.append(m.group(1))
        return " "

    work = QUOTE_RE.sub(take_quote, work)
    if any(_is_web(t) for t in _norm_tokens(work)):
        return None                                   # Google / YouTube / brauzer: veb buyruq — NLU o'zining xavfsizlik qoidalari bilan hal qiladi
    # --- xavfsizlik: ma'lumot qismlarisiz qolgan matnda xavfli fe'l bo'lsa — hamma narsa rad etiladi
    try:
        clauses, lang, found = nlu.analyze(work)
    except Exception:  # noqa: BLE001
        return None
    if any(cl.has("DANGER") for cl in clauses):
        return ParseResult("blocked", message=T("blocked", lang), lang=lang, langs=sorted(found), confidence=1.0)

    toks = _norm_tokens(work)
    if not toks and not data:
        return None
    # --- papka nomlari
    fw = [i for i, t in enumerate(toks) if _starts(t, FOLDER_PRE)]
    alias, alias_idx = "", set()
    for i, t in enumerate(toks):
        a = ALIAS_EXACT.get(t) or next((k for k, pre in ALIAS_PRE.items() if _starts(t, pre)), None)
        if a:
            alias = a
            alias_idx.add(i)
            continue
        for k, words in AMBIG_ALIAS.items():
            if t in words and any(abs(i - j) == 1 for j in fw):
                alias = k
                alias_idx.add(i)
    for i in range(len(toks) - 1):                                      # «ish stoli», «рабочий стол»
        if toks[i] in ("ish", "rabochiy", "rabochaya") and toks[i + 1].startswith("stol"):
            alias = "desktop"
            alias_idx.update({i, i + 1})
    # --- tushunchalar
    joined = " ".join(toks)
    latest = bool(re.search(r"\beng (yangi|song|oxirgi)", joined) or re.search(r"\bsam(iy|oe|yy|ie|aya) (nov|svej|posled)", joined)
                  or "most recent" in joined or any(t in LATEST_WORDS or t.startswith("posledn") for t in toks))
    kinds: set[str] = set()
    f_find = f_open = f_show = filenoun = ref = req = person = False
    langf = ""
    query: list[str] = []
    for i, t in enumerate(toks):
        if i in alias_idx:
            continue
        if latest and (t in ("eng", "yangi", "samiy", "samoe", "samyy", "samie", "samaya", "noviy", "novoe", "novie", "novuyu", "svejiy", "most", "recent", "last")
                       or t.startswith(("yangisi", "songgi", "song", "oxirgi", "posledn", "svej", "novey"))
                       or t in LATEST_WORDS):
            continue
        if t in KNOWN_EXTS:
            exts.add(t)
            if t in KIND_OF_EXT_SAFE:
                kinds.add(KIND_OF_EXT_SAFE[t])
            continue
        if _is_find(t):
            f_find = True
        elif _is_open(t):
            f_open = True
        elif _is_show(t):
            f_show = True
        elif _kind_of(t):
            kinds.add(_kind_of(t))
        elif _starts(t, FILE_PRE):
            filenoun = True
        elif _starts(t, FOLDER_PRE + COMPUTER_PRE + ALL_PRE + AUTH_PRE + LANGWORD_PRE):
            pass
        elif _starts(t, REQ_PRE):
            req = True
        elif _starts(t, PERSON_PRE):
            person = True
        elif _lang_of(t):
            langf = _lang_of(t)
        elif t in REF_WORDS:
            ref = True
        elif t not in STOP:
            query.append(t)
    web = any(_is_web(t) for t in toks)
    indicator = bool(kinds or exts or filenoun or data)
    if web or not indicator or not (f_find or f_open or f_show or latest):
        return None
    if any(_starts(t, FILEMGR_PRE) for t in toks):                       # «Fayl menejerini och», «File Explorer» — bu ilova, fayl emas
        return None
    if filenoun and not (kinds or exts or data) and not (ref or req) and not (f_find or f_show or latest):
        return None                                                      # faqat «fayl» + «och»: nima ochilishi noma'lum — oddiy NLU qaror qiladi
    if not data and not (kinds or exts or filenoun):
        return None
    # --- ko'p bo'lakli gap: boshqa buyruq aralashgan bo'lsa fayl yo'liga o'tmaymiz (NLU qaror qiladi)
    if prior is not None and prior.kind == "ok" and len(prior.commands) > 1:
        return None
    qtext = " ".join(data + query).strip()[:200]
    has_name = bool(qtext)
    langs = sorted(found)
    # --- «Hujjatlarimni och», «Открой мои документы»: papkani ochish (NLU) — nom/ko'rsatkichsiz hujjat so'zi fayl qidiruvi emas
    if (prior is not None and prior.kind == "ok" and len(prior.commands) == 1 and prior.commands[0].action == "open_app" and not has_name
            and not exts and not latest and not langf and not (ref or req) and not filenoun and kinds <= {"document"}):
        return None
    # --- "o'sha odamning videosi": kim/qaysi — taxmin qilmaymiz
    if person and not has_name and (f_open or f_show):
        return ParseResult("clarify", message=T("files.cl.person", lang), lang=lang, langs=langs, confidence=0.6)

    if (f_show or f_find) and filenoun and not has_name and not kinds and not exts and not latest and not f_open and not (ref or req):
        args = {"folder": alias}
        cmd = Command("list_files", args, T("files.ask.list", lang, where=_where(alias, lang)), intent="list_files", needs_confirm=False)
        return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=langs, confidence=0.9)

    then = "open" if f_open else "show"
    args = {"query": qtext, "kinds": sorted(k for k in kinds if k), "exts": sorted(exts), "folder": alias, "lang": langf, "latest": latest,
            "then": then, "ref": bool(ref or req), "bare": not has_name and not exts}
    cmd = Command("find_files", args, T("files.ask.find", lang, what=_describe(args, lang), where=_where(alias, lang)),
                  intent="open_file" if then == "open" else "find_file", needs_confirm=False)
    return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=langs, confidence=0.9)


def _where(alias: str, lang: str) -> str:
    return T(f"files.folder.{alias}", lang) if alias else T("files.folder.all", lang)


# ----------------------------------------------------------------------------- ro'yxatdan tanlash ("2", "birinchisini och", "ochib ber", "bekor")
_ORD = [("birinchi", "perv", "first", "1st"), ("ikkinchi", "vtor", "second", "2nd"), ("uchinchi", "tret", "third", "3rd"),
        ("tortinchi", "chetvert", "fourth", "4th"), ("beshinchi", "pyat", "fifth", "5th"), ("oltinchi", "shest", "sixth", "6th"),
        ("yettinchi", "sedm", "seventh", "7th"), ("sakkizinchi", "vosm", "eighth", "8th"), ("toqqizinchi", "devyat", "ninth", "9th"),
        ("oninchi", "desyat", "tenth", "10th")]
_NUMW = {"bir": 1, "ikki": 2, "uch": 3, "tort": 4, "besh": 5, "olti": 6, "yetti": 7, "sakkiz": 8, "toqqiz": 9, "on": 10,
         "odin": 1, "dva": 2, "tri": 3, "chetire": 4, "shest": 6, "sem": 7, "vosem": 8, "devyat": 9, "desyat": 10,
         "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_CANCEL = {"bekor", "bekorqil", "cancel", "otmena", "otmeni", "stop", "yoq", "hechqaysi", "hech", "no", "net", "nevermind", "qolsin", "kerakemas"}
_CHOICE_FILLER = {"raqam", "raqamli", "nomer", "nomerom", "number", "no", "chisini", "ni", "ini", "isini", "sini", "one", "ones", "file", "fayl", "faylni", "video", "videoni",
                  "iltimos", "pozhaluysta", "please", "the", "a", "ber", "bering", "uni", "shuni", "ega", "it", "that", "this", "ega", "etot", "ga", "da", "va"}


def parse_choice(text: str, n: int) -> Choice | None:
    """Oxirgi ro'yxat mavjud bo'lganda qisqa javobni tushunadi. Boshqa har qanday matn -> None (oddiy buyruq sifatida ishlanadi)."""
    toks = _norm_tokens(text)
    if not toks or len(toks) > 7 or n <= 0:
        return None
    if all(t in _CANCEL for t in toks) or (len(toks) <= 2 and toks[0] in _CANCEL):
        return Choice("cancel")
    idx: int | None = None
    opens = False
    for t in toks:
        m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th|chi|inchi)?", t)
        if m:
            idx = int(m.group(1)) - 1; continue
        hit = next((i for i, forms in enumerate(_ORD) if any(t.startswith(f) for f in forms[:3]) or t == forms[3]), None)
        if hit is not None and not (t.startswith("pyat") and len(t) < 5):
            idx = hit; continue
        if t in _NUMW and idx is None:
            idx = _NUMW[t] - 1; continue
        if _is_open(t):
            opens = True; continue
        if t in _CHOICE_FILLER or t in STOP or t in REF_WORDS:
            continue
        return None                                 # tanish mumkin bo'lmagan so'z — bu tanlash emas
    if idx is None and not opens:
        return None
    return Choice("open" if opens else "pick", idx)
