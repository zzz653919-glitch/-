"""Kompyuter, oyna, skrinshot, clipboard, veb/YouTube, interfeys va ingliz tili buyruqlarini tushunish (uz · ru · en).

Bu modul faqat OVOZDAN (yoki ichki oqimdan) kelgan, taniladigan matnni `ALLOWED_ACTIONS` ichidagi qat'iy buyruqlarga aylantiradi.
Shell, eval yoki erkin matn bajarilmaydi. Xavfli fe'l (o'chirish, yuborish, o'rnatish, ...) bo'lsa hammasi rad etiladi.
Eslatma/vazifa/qayd matni «ma'lumot» hisoblanadi: ularga tegishli gaplar bu yerda qayta ishlanmaydi (taskintent.py ularni oladi).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from . import english, nlu
from .commands import Command, ParseResult, extract_amount, normalize
from .i18n import T

# ---- so'z ildizlari (kirill -> lotin transliteratsiyadan keyingi shakllar)
TASKISH = ("vazif", "task", "zadach", "eslat", "remind", "napomn", "qayd", "zametk", "note", "memo", "reminder", "todo")
OPEN_V = ("open", "och", "ochib", "ochish", "otkro", "zapust", "ishga", "launch", "start", "kir", "kiring", "kirish", "go", "visit", "zayd", "zaydi", "perejd", "otkry")
SEARCH_V = ("search", "find", "lookup", "look", "qidir", "izla", "nayd", "naydi", "najd", "poisk", "poish", "top", "topib", "gugl", "pogugl", "google")
SHOW_V = ("show", "korsat", "pokaj", "pokaz", "display", "list", "mavjud", "available", "spisok", "dostup", "qanday", "qanaqa", "kakie", "what", "which")
WEBISH = ("web", "internet", "internetda", "internete", "onlayn", "online", "veb", "tarmoq", "sayt", "website", "site")
FILLER = {"the", "a", "an", "my", "me", "to", "for", "of", "in", "on", "at", "and", "then", "please", "pls", "plz", "now", "this", "that", "it", "is",
          "ni", "ga", "da", "dan", "ning", "uchun", "haqida", "boyicha", "iltimos", "menga", "meni", "men", "va", "hamda", "keyin", "bu", "shu", "mening",
          "mne", "pozhaluysta", "dlya", "na", "v", "vo", "po", "i", "iz", "etot", "eto", "moy", "moyu", "moi", "ob", "pro", "o", "zatem", "potom",
          "pyatnitsa", "friday", "hey", "hi", "ok", "privet"}
SITE_RE = re.compile(r"(?<![\w@./-])((?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,24}))(?![\w-])", re.I)
SECRET_TLD_BLOCK = {"exe", "bat", "cmd", "msi", "scr", "ps1", "vbs", "js", "jar", "zip", "rar"}      # fayl kengaytmasi «sayt» deb ochilmasin


def _words(raw: str) -> list[str]:
    return re.findall(r"[^\s]+", raw)


def _nw(raw: str) -> list[str]:
    return [normalize(w).replace(" ", "") for w in _words(raw) if normalize(w)]


def _has(nw: list[str], prefixes) -> bool:
    return any(t.startswith(tuple(prefixes)) for t in nw)


def _hasx(nw: list[str], exact) -> bool:
    return any(t in exact for t in nw)


_EN_MARK = {"take", "screenshot", "clipboard", "copied", "window", "minimize", "maximize", "next", "previous", "switch", "read", "explain", "summarize", "show", "open", "start",
            "ask", "questions", "vocabulary", "pronunciation", "test", "listening", "exercise", "level", "translate", "word", "dark", "mode", "settings", "panel", "close",
            "available", "commands", "microphone", "status", "website", "lesson", "english", "check", "connection", "computer", "specifications", "harder", "easier", "search", "web",
            "find", "information", "give", "short", "yes", "set", "make", "my", "the", "this", "me", "please", "volume", "folder", "music"}


def _lang(raw: str, nlu_lang: str) -> str:
    """Javob tili. nlu so'zlarni bilmasa o'zbekchaga tushadi — toza inglizcha gap uchun inglizchani tanlaymiz."""
    from .router import detect_language
    lang = detect_language(raw)
    if lang == "uz":
        words = re.findall(r"[a-z']+", raw.lower())
        if words and not re.search(r"[^\x00-\x7f]", raw.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')) and sum(w in _EN_MARK for w in words) >= max(1, (len(words) + 1) // 2):
            return "en"
    return lang if lang != "uz" else (nlu_lang if nlu_lang in ("ru", "en") else "uz")


def _analyze(raw: str, drop: tuple = ()):
    """(xavfli, til, topilgan tillar). `drop` — shu ildizlar bilan boshlanuvchi so'zlar xavf tekshiruvidan chiqariladi (masalan «nusxalangan»)."""
    kept = [w for w in _words(raw) if not (drop and normalize(w).replace(" ", "").startswith(tuple(drop)))]
    clauses, lang, found = nlu.analyze(" ".join(kept))
    return any(cl.has("DANGER") for cl in clauses), _lang(raw, lang), sorted(found)


def _ok(cmd: Command, lang: str, found: list[str], conf: float = 0.9) -> ParseResult:
    return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=conf)


def _clarify(msg_key: str, raw: str, lang: str, found: list[str]) -> ParseResult:
    return ParseResult("clarify", message=T(msg_key, lang), lang=lang, langs=found, confidence=0.5, draft=raw)


def _query(raw: str, strip: tuple) -> str:
    out = []
    for w in _words(raw):
        n = normalize(w).replace(" ", "")
        if not n or n in FILLER or n.startswith(strip):
            continue
        out.append(w.strip("'\"“”«».,!?;:"))
    return " ".join(x for x in out if x)[:200]


# ============================================================================ asosiy kirish
def parse(text: str, prior: ParseResult | None = None) -> ParseResult | None:
    raw = (text or "").strip()[:400]
    nw = _nw(raw)
    if not nw or _has(nw, TASKISH):
        return None
    if _has(nw, YT_N) is False and _word_question(nw):
        _bad, lang, found = _analyze(raw)
        return ParseResult("unknown", lang=lang, langs=found, confidence=0.2)          # «Explain this English word» — AI suhbatiga (Microsoft Word emas)
    for fn in (_english, _window, _screenshot, _clipboard, _ui, _web, _computer):
        r = fn(raw, nw)
        if r is not None:
            return r
    return None


def _word_question(nw: list[str]) -> bool:
    return _hasx(nw, ("word", "soz", "slovo", "slova", "sozni", "sozning")) and _has(nw, ("explain", "tushuntir", "obyasn", "mean", "anglat", "oznach", "define", "meaning", "ma'no", "mano", "znachen", "use", "ishlat", "pronounce")) \
        and not _has(nw, OPEN_V)


def _blocked(raw: str, drop: tuple = ()) -> ParseResult | None:
    bad, lang, found = _analyze(raw, drop)
    if bad:
        return ParseResult("blocked", message=T("blocked", lang), lang=lang, langs=found, confidence=1.0)
    return None


# ============================================================================ oyna boshqaruvi
WIN_NOUN = ("window", "oyna", "okno", "okna", "okn")
MIN_V = ("minimi", "kichray", "yigib", "yigish", "sverni", "svern", "skroy", "minimaliz")
MAX_V = ("maximi", "maksimi", "kattalash", "razvern", "razverni", "razvor", "fullscreen")
NEXT_V = ("next", "keyingi", "sleduyush", "dalshe")
PREV_V = ("previous", "oldingi", "predydush", "predidush", "prev")
SWITCH_V = ("switch", "almashtir", "otish", "pereklyuch", "perejd", "pereid", "go")


def _window(raw: str, nw: list[str]) -> ParseResult | None:
    if not _has(nw, WIN_NOUN) or _has(nw, ("youtube", "yutub")):
        return None
    op = ""
    if _has(nw, MIN_V):
        op = "minimize"
    elif _has(nw, MAX_V):
        op = "maximize"
    elif _has(nw, PREV_V):
        op = "prev"
    elif _has(nw, NEXT_V) or (_has(nw, SWITCH_V) and not _has(nw, ("new", "yangi"))):
        op = "next"
    if not op:
        return None
    blocked = _blocked(raw)
    if blocked:
        return blocked
    _bad, lang, found = _analyze(raw)
    cmd = Command("window", {"op": op}, T("ask.window", lang, what=T(f"win.{op}", lang)), intent="window_control", needs_confirm=False)
    return _ok(cmd, lang, found)


# ============================================================================ skrinshot
def _screenshot(raw: str, nw: list[str]) -> ParseResult | None:
    shot = _has(nw, ("screenshot", "skrinshot", "skrin", "screencap", "screencapture")) or (
        _has(nw, ("ekran", "screen", "monitor")) and _has(nw, ("surat", "rasm", "snimok", "snimk", "capture", "shot", "tushir", "foto", "photo", "picture", "image")))
    if not shot:
        return None
    blocked = _blocked(raw)
    if blocked:
        return blocked
    _bad, lang, found = _analyze(raw)
    cmd = Command("screenshot", {}, T("ask.screenshot", lang), intent="screenshot")
    return _ok(cmd, lang, found)


# ============================================================================ clipboard
CLIP_N = ("clipboard", "bufer", "buffer")
COPIED = ("copied", "nusxalangan", "nusxalab", "nusxa", "skopirovan", "kopirovan", "selected", "tanlangan", "vydelen", "vybran", "highlighted")
THIS_N = ("error", "xato", "oshibk", "code", "kod", "text", "matn", "tekst", "traceback", "message")
EXPLAIN_V = ("explain", "tushuntir", "tushunt", "obyasn", "obyasni", "izohla", "izoh", "analyze", "analiz")
SUMM_V = ("summar", "qisqacha", "qisqart", "xulosa", "kratk", "rezyum", "pereskaj", "pereskaz", "sokrati", "tldr")
READ_V = ("read", "oqi", "oqib", "prochit", "prochti", "show", "korsat", "pokaj", "pokaz", "what", "nima", "chto")
CLIP_DROP = ("nusxa", "kopir", "skopir", "copy", "copied", "paste", "vstav", "tanlangan", "selected")


def _clipboard(raw: str, nw: list[str]) -> ParseResult | None:
    clip = _has(nw, CLIP_N)
    copied = _has(nw, COPIED)
    this_thing = _has(nw, ("this", "bu", "shu", "etot", "etu", "eto")) and _has(nw, THIS_N)
    mode = ""
    if _has(nw, SUMM_V):
        mode = "summarize"
    elif _has(nw, EXPLAIN_V):
        mode = "explain"
    elif _has(nw, READ_V) and clip:
        mode = "read"
    if not mode or not (clip or copied or (this_thing and mode in ("explain", "summarize"))):
        return None
    if mode in ("explain", "summarize") and not (clip or copied or this_thing):
        return None
    blocked = _blocked(raw, CLIP_DROP)
    if blocked:
        return blocked
    _bad, lang, found = _analyze(raw, CLIP_DROP)
    cmd = Command("clipboard", {"mode": mode}, T(f"ask.clip.{mode}", lang), intent="clipboard", needs_confirm=True, force_confirm=True)
    return _ok(cmd, lang, found, 0.85)


# ============================================================================ interfeys
DARK_N = ("dark", "qorongi", "qorong", "temn", "tyomn", "tyomnu", "tyemn", "night")
LIGHT_N = ("light", "yorug", "svetl", "yorugh")
MODE_N = ("mode", "rejim", "tema", "theme", "rezhim", "mavzu")
CMD_N = ("command", "buyruq", "komand", "buyruqlar")
MIC_N = ("mic", "mikrofon", "microphone")
STATUS_N = ("status", "holat", "sostoyan", "state", "ishlay", "working", "tayyor")
WINS_N = ("windows", "vindovs", "vindous", "system", "sistem", "tizim", "kompyuter", "computer", "pc", "vindows")
APP_N = ("pyatnitsa", "app", "application", "assistant", "assistent", "asistent", "ilova", "ilovan", "prilozhen", "interface", "interfeys", "yordamchi", "friday")
SETTINGS_N = ("setting", "sozlama", "nastroyk", "parametr")
PANEL_N = ("panel", "page", "sahifa", "oyna", "okno", "window", "stranic", "razdel", "bolim")
CLOSE_V = ("close", "yop", "zakro", "hide", "yashir", "skroy", "back", "orqaga", "qayt", "nazad", "exit", "chiq")


def _ui(raw: str, nw: list[str]) -> ParseResult | None:
    op, drop = "", ()
    if _has(nw, DARK_N + LIGHT_N) and _has(nw, MODE_N):
        op = "dark_mode"
    elif _has(nw, CMD_N) and _has(nw, SHOW_V + ("help", "yordam", "pomosh")):
        op = "commands"
    elif _has(nw, MIC_N) and _has(nw, STATUS_N):
        op = "mic_status"
    elif _has(nw, SETTINGS_N):
        wins = _has(nw, WINS_N)
        app = _has(nw, APP_N)
        closing = _has(nw, CLOSE_V)
        if closing and not wins:
            op, drop = "settings_close", CLOSE_V
        elif app and not wins and _has(nw, OPEN_V + SHOW_V):
            op = "settings_open"
        elif wins:
            return None                                                   # Windows Sozlamalari — nlu.open_app("winsettings")
        elif _has(nw, OPEN_V) and len([t for t in nw if t not in FILLER]) <= 4:
            _bad, lang, found = _analyze(raw)
            return _clarify("cl.settings", raw, lang, found)
        else:
            return None
    if not op:
        return None
    blocked = _blocked(raw, drop)
    if blocked:
        return blocked
    _bad, lang, found = _analyze(raw, drop)
    args = {"op": op}
    if op == "dark_mode":
        args["theme"] = "light" if _has(nw, LIGHT_N) and not _has(nw, DARK_N) else "dark"
    key = {"dark_mode": "ask.ui.dark", "commands": "ask.ui.commands", "mic_status": "ask.ui.mic", "settings_open": "ask.ui.settings", "settings_close": "ask.ui.close"}[op]
    cmd = Command("ui", args, T(key, lang), intent="ui_control", needs_confirm=False)
    return _ok(cmd, lang, found)


# ============================================================================ veb va YouTube
YT_N = ("youtube", "yutub", "yutyub", "yutuba", "yutubda")
YT_STRIP = YT_N + SEARCH_V + OPEN_V + ("web", "internet", "onlayn", "online", "veb")


def _site_in(raw: str) -> str:
    for m in SITE_RE.finditer(raw):
        host = m.group(1).lower()
        tld = host.rsplit(".", 1)[-1]
        if tld in SECRET_TLD_BLOCK:
            continue
        return host
    return ""


def _valid_host(host: str) -> bool:
    if not host or len(host) > 253 or host.startswith("xn--") or ".xn--" in host:
        return False
    if re.fullmatch(r"[\d.]+", host) or host in ("localhost",) or host.endswith((".local", ".internal", ".lan")):
        return False
    return all(re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?", p) for p in host.split("."))


def _web(raw: str, nw: list[str]) -> ParseResult | None:
    if _has(nw, YT_N):
        has_search = _has(nw, SEARCH_V)
        if has_search:
            blocked = _blocked(raw)
            if blocked:
                return blocked
            _bad, lang, found = _analyze(raw)
            q = _query(raw, YT_STRIP)
            if len(q) < 2:
                return _clarify("cl.yt", raw, lang, found)
            cmd = Command("youtube_search", {"query": q}, T("ask.yt", lang, q=q), intent="web_search")
            return _ok(cmd, lang, found)
        if _has(nw, OPEN_V) and len([t for t in nw if t not in FILLER and not t.startswith(YT_N)]) <= 2:
            blocked = _blocked(raw)
            if blocked:
                return blocked
            _bad, lang, found = _analyze(raw)
            cmd = Command("open_app", {"app": "youtube"}, "YouTube", intent="open_app")
            return _ok(cmd, lang, found)
        return None
    host = _site_in(raw)
    if _has(nw, OPEN_V) and (host or _has(nw, ("website", "site", "sayt", "veb"))) and not _has(nw, ("file", "fayl", "papk", "folder")):
        _bad, lang, found = _analyze(raw)
        if not host:
            return _clarify("cl.site", raw, lang, found)
        blocked = _blocked(raw)
        if blocked:
            return blocked
        if not _valid_host(host):
            return ParseResult("unknown", message=T("site.bad", lang, what=host), lang=lang, langs=found, confidence=0.3)
        url = f"https://{host}/"
        cmd = Command("open_site", {"host": host}, T("ask.site", lang, url=url), intent="open_site", needs_confirm=True, force_confirm=True)
        return _ok(cmd, lang, found)
    return None


# ============================================================================ kompyuter (internet, xususiyatlar, VS Code, papkalar)
NET_N = ("internet", "wifi", "wi", "connection", "network", "tarmoq", "aloqa", "ulanish", "ulanishi", "soedinen", "podklyuch", "set")
CHECK_V = ("check", "test", "tekshir", "prover", "working", "ishlay", "ping", "est", "ulangan", "connected", "bormi", "available")
SPEC_N = ("spec", "specification", "specs", "xususiyat", "xarakteristik", "harakteristik", "kharakteristik", "konfiguratsiy", "configuration", "spetsifikats")
PC_N = ("computer", "pc", "kompyuter", "laptop", "noutbuk", "komp", "compyuter", "ustroystv", "device", "machine")
VSC = ("vscode", "vs", "visual")
FOLDERS = {"music": ("music", "musiq", "muzik", "qoshiq", "muzyk"), "pictures": ("picture", "photo", "rasm", "surat", "foto", "kartin", "izobrazhen"),
           "videos": ("videos", "videolar", "videopapk", "videoteka", "videor")}
FOLDER_N = ("papk", "folder", "katalog", "direkt")


def _computer(raw: str, nw: list[str]) -> ParseResult | None:
    # ---- VS Code
    flat = " ".join(nw)
    if ("vscode" in nw or "vs code" in flat or "visual studio code" in flat or "vs kod" in flat or "vs kode" in flat or "vskod" in nw) and _has(nw, OPEN_V):
        blocked = _blocked(raw)
        if blocked:
            return blocked
        _bad, lang, found = _analyze(raw)
        cmd = Command("open_app", {"app": "vscode"}, "Visual Studio Code", intent="open_app")
        return _ok(cmd, lang, found)
    # ---- internet tekshiruvi (brauzer ochish bilan adashtirilmaydi: tekshirish fe'li shart)
    if _has(nw, NET_N) and _has(nw, CHECK_V) and not _has(nw, ("speed", "tezlik", "skorost")) and not _has(nw, OPEN_V):
        blocked = _blocked(raw)
        if blocked:
            return blocked
        _bad, lang, found = _analyze(raw)
        return _ok(Command("net_check", {}, T("ask.net", lang), intent="net_check", needs_confirm=False), lang, found)
    # ---- kompyuter xususiyatlari
    if _has(nw, SPEC_N) and (_has(nw, PC_N) or len(nw) <= 3):
        blocked = _blocked(raw)
        if blocked:
            return blocked
        _bad, lang, found = _analyze(raw)
        return _ok(Command("specs", {}, T("ask.specs", lang), intent="get_system_info", needs_confirm=False), lang, found)
    # ---- Music / Pictures / Videos papkalari
    if _has(nw, OPEN_V) and _has(nw, FOLDER_N):
        for fid, words in FOLDERS.items():
            if _has(nw, words):
                rest = [t for t in nw if t not in FILLER and not t.startswith(OPEN_V + FOLDER_N + words)]
                if rest:
                    return None                                           # «eng yangi video papkasidan ...» — fayl qidiruviga qoldiriladi
                blocked = _blocked(raw)
                if blocked:
                    return blocked
                _bad, lang, found = _analyze(raw)
                cmd = Command("open_app", {"app": fid}, {"music": "Music", "pictures": "Pictures", "videos": "Videos"}[fid], intent="open_folder")
                return _ok(cmd, lang, found)
    return None


# ============================================================================ ingliz tili
ENG_N = ("english", "ingliz", "angli", "inglis")
LESSON_N = ("lesson", "dars", "urok", "zanyat", "mashgulot", "class")
START_V = ("start", "begin", "boshla", "nachn", "nachni", "zapust", "launch", "open", "och")
QUIZ_N = ("question", "savol", "vopros", "quiz", "viktorin", "test")
VOCAB_N = ("vocab", "lugat", "luget", "slovar", "leksik", "word", "soz", "slov", "slova")
PRON_N = ("pronunc", "talaffuz", "proiznosh", "proiznos", "talafuz")
LISTEN_N = ("listening", "tinglash", "audirovan", "tinglab", "listen")
EXERCISE_N = ("exercise", "mashq", "uprajnen", "task", "zadan", "practice", "praktik")
TRANSL_V = ("translate", "tarjima", "perevedi", "perevod", "perevesti", "perevod")
LEVEL_N = ("level", "daraja", "uroven", "difficulty", "qiyinlik", "slojnost", "sloznost")
HARDER = ("harder", "qiyinroq", "murakkabroq", "slojnee", "trudnee", "tougher", "advanced")
EASIER = ("easier", "osonroq", "oddiyroq", "legche", "proshche", "simpler")


def _english(raw: str, nw: list[str]) -> ParseResult | None:
    eng = _has(nw, ENG_N)
    spec = ""
    if _has(nw, YT_N):
        return None
    if _has(nw, TRANSL_V) and _has(nw, ("word", "soz", "slovo", "slova")) and not _has(nw, ("sentence", "gap", "predlozh", "text", "matn")):
        spec = "translate"
    elif _has(nw, PRON_N):
        spec = "pronunciation"
    elif _has(nw, LISTEN_N) and (_has(nw, EXERCISE_N) or eng or _has(nw, ("give", "ber", "daj", "start", "boshla"))):
        spec = "listening"
    elif _has(nw, QUIZ_N) and (_has(nw, VOCAB_N) or eng or re.search(r"\b(a1|a2|b1)\b", normalize(raw))) and not _has(nw, ("task", "vazif")):
        spec = "quiz"
    elif _has(nw, LEVEL_N) and (eng or re.search(r"\b(a1|a2|b1)\b", normalize(raw)) or _has(nw, HARDER + EASIER)):
        spec = "level"
    elif (_has(nw, HARDER + EASIER)) and (eng or _has(nw, LESSON_N + QUIZ_N)):
        spec = "level"
    elif eng and _has(nw, LESSON_N) and _has(nw, START_V + ("give", "ber", "daj", "need", "kerak")) and not _has(nw, ("plan", "reja")):
        spec = "lesson"
    if not spec:
        return None
    blocked = _blocked(raw)
    if blocked:
        return blocked
    _bad, lang, found = _analyze(raw)
    level = english.norm_level(raw, "")
    args: dict = {"op": spec}
    if spec == "translate":
        m = re.search(r"[‘’'\"“”«»`]\s*([A-Za-z][A-Za-z' -]{0,40}?)\s*[‘’'\"“”«»`]", raw)
        word = m.group(1) if m else ""
        if not word:
            cand = [w.strip(".,!?;:'\"“”«»") for w in _words(raw)]
            cand = [w for w in cand if re.fullmatch(r"[A-Za-z][A-Za-z'-]*", w) and normalize(w) not in FILLER and not normalize(w).startswith(TRANSL_V + ("word", "english"))]
            word = cand[-1] if cand else ""
        if not word:
            return ParseResult("clarify", message={"uz": "Qaysi so'zni tarjima qilay?", "ru": "Какое слово перевести?", "en": "Which word should I translate?"}[lang if lang in ("uz", "ru", "en") else "uz"],
                               lang=lang, langs=found, confidence=0.5, draft=raw)
        args["word"] = word[:40]
        text = T("ask.eng.tr", lang, word=args["word"])
        needs = False
    elif spec == "level":
        if level:
            args["level"] = level
        elif _has(nw, HARDER):
            args["shift"] = 1
        elif _has(nw, EASIER):
            args["shift"] = -1
        else:
            return ParseResult("clarify", message={"uz": "Qaysi daraja: A1, A2 yoki B1?", "ru": "Какой уровень: A1, A2 или B1?", "en": "Which level: A1, A2 or B1?"}[lang if lang in ("uz", "ru", "en") else "uz"],
                               lang=lang, langs=found, confidence=0.5, draft=raw)
        text = T("ask.eng.level", lang, level=level or "")
        needs = False
    elif spec == "quiz":
        stripped = re.sub(r"\b[abAB][12]\b", " ", raw)
        n = extract_amount(stripped)
        args["n"] = int(n) if n and 1 <= n <= english.MAX_QUESTIONS else 10
        if level:
            args["level"] = level
        text = T("ask.eng.quiz", lang, n=args["n"], level=level or "")
        needs = False
    else:
        if level:
            args["level"] = level
        text = T({"lesson": "ask.eng.lesson", "pronunciation": "ask.eng.pron", "listening": "ask.eng.listen"}[spec], lang)
        needs = False
    cmd = Command("english", args, text, intent="english", needs_confirm=needs)
    return _ok(cmd, lang, found, 0.85)
