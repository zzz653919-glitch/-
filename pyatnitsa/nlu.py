"""Ko'p tilli (uz / ru / en va aralash) buyruq tushunish qatlami.

Bosqichlar:  1) normallashtirish (kirill -> lotin, apostrof, belgilar)  2) tillarni aniqlash (lug'at va qo'shimchalar bo'yicha)
3) maqsad (intent) ballari   4) parametrlarni ajratish (so'rov, miqdor, ob'ektlar)   5) xavfsizlik va ruxsat tekshiruvi
6) ishonchli bo'lsa — buyruqlar ro'yxati; aks holda aniqlashtiruvchi savol.

Matn hech qachon shell/eval/exec'ga berilmaydi: natija faqat `commands.ALLOWED_ACTIONS` ichidagi `Command` lardir.
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field

from .commands import Command, ParseResult, basic, extract_amount, normalize
from .i18n import T, app_title

MAX_COMMANDS = 4
ACCEPT = 0.70        # shundan yuqori ishonchda bajarishga tayyor
CLARIFY_MIN = 0.40   # shundan past — «tushunmadim»
TIE_GAP = 0.15       # ikki variant shunchalik yaqin bo'lsa — so'raymiz

# --------------------------------------------------------------------------- lug'at
# concept -> {til: "forma forma* ..."};  '*' = prefiks (o'zak). «any» — til belgisi bermaydigan nomlar (Chrome, RAM ...)
LEX_SRC: dict[str, dict[str, str]] = {
    "OPEN": dict(uz="och oching ochib ochgin ochvor ochay ochish ochsang tushir*", ru="откр* запуст* запуск*", en="open launch start run"),
    "SEARCH": dict(uz="qidir* izla* top topib", ru="найд* найт* поищ* поиск* погугл*", en="search find lookup"),
    "SHOW": dict(uz="korsat* ayt ayting ber bering chiqar*", ru="покаж* показ* скаж* выведи* расскаж* дай", en="show display tell give list"),
    "CHECK": dict(uz="tekshir* analiz*", ru="провер* посмотр* анализ*", en="check test analyze analyse inspect look"),
    "CREATE": dict(uz="yarat* tuz* hosil", ru="созда* сформир* сделай", en="create make generate build save"),
    "SPEEDUP": dict(uz="tezlashtir* tezlat* optimalla* tozala*", ru="ускор* оптимиз* очист*", en="speed speedup optimize optimise clean boost"),
    "HOWMUCH": dict(uz="qancha necha", ru="сколько", en="much long"),
    "PERCENT": dict(any="foiz* protsent* процент* percent*"),
    "HOW": dict(uz="qanday", ru="как", en="how whats"),
    "WHICH": dict(uz="qaysi", ru="какие какой какая какое каких", en="which what"),
    "MANY": dict(uz="kop* eng", ru="много больше больш* самые самый", en="most many more"),
    "USE": dict(uz="ishlat* band*", ru="использ* занят* занима* нагруж*", en="using use used busy consum*"),
    "RUN": dict(uz="ishlay* ishlagan ishlab", ru="работает работа* аптайм", en="running uptime"),
    "TIME": dict(uz="vaqt* soat*", ru="время времени врем* час часов", en="time clock"),
    "DATE": dict(uz="sana*", ru="дата числ*", en="date"),
    "WEATHER": dict(uz="havo obhavo", ru="погод*", en="weather forecast"),
    "DOLLAR": dict(any="dollar* usd dolar* доллар* бакс*"),
    "KURS": dict(any="kurs* курс* valyut* валют* rate exchange"),
    "SOM": dict(any="som soms sum"),
    "PC": dict(any="kompyuter* komputer* noutbuk* notebook* laptop* computer* pc pk компьютер* tizim* sistem* system*"),
    "CPU": dict(any="cpu protsessor* prosessor* procesor* processor* процессор*"),
    "RAM": dict(any="ram operativ* оператив* tezkor xotira* памят* memory"),
    "DISK": dict(any="disk* диск* ssd hdd drive*"),
    "FREE": dict(uz="bosh qoldi qolgan", ru="свободн* осталось остал*", en="free left remaining available"),
    "SPACE": dict(uz="joy joyi joylar", ru="место места мест*", en="space storage"),
    "TEMP": dict(any="harorat* temperatur* issiq* температур* градус* нагрев* temp temps heat"),
    "GPU": dict(any="gpu videokart* videoplata* видеокарт* graphics"),
    "BATT": dict(any="batare* akkumulyator* аккумулятор* zaryad* заряд* battery batt charging charge"),
    "PROCS": dict(any="dastur* jarayon* ilova* программ* приложен* процесс* process* program* app apps application*"),
    "STATE": dict(uz="holat* sogliq* ahvol*", ru="состояни* здоров* статус", en="state status health* condition"),
    "REPORT": dict(any="hisobot* отчет* отчёт* report*"),
    "DIAG": dict(any="diagnos* диагност*"),
    "FULL": dict(uz="toliq*", ru="полн*", en="full complete detailed"),
    "ADMIN": dict(any="sfc dism chkdsk scannow"),
    "GOOGLE": dict(any="google* googl* гугл*"),
    "CHROME": dict(any="chrome* chrom* хром* hrom* krom*"),
    "BROWSER": dict(any="brauzer* brouzer* browser* brauser* браузер*"),
    "NEW": dict(uz="yangi", ru="новое новый новую новом", en="new"),
    "WINDOW": dict(uz="oyna*", ru="окно окна окне окну", en="window*"),
    "DOWNLOADS": dict(any="download* daunlod* yuklamalar* yuklanma* загруз*"),
    "DESKTOP": dict(any="desktop* dekstop* dasktop*"),
    "DOCUMENTS": dict(any="document* dokument* hujjat* документ*"),
    "FOLDER": dict(any="papk* folder* katalog* directoriya*"),
    "CALC": dict(any="kalkulyator* calculator* kalkulator* calc* калькулятор*"),
    "NOTEPAD": dict(any="notepad* noutpad* bloknot* блокнот*"),
    "EXPLORER": dict(any="explorer* provodnik* проводник*"),
    "YOUTUBE": dict(any="youtube* yutub* yutyub* ютуб*"),
    "UNSUP": dict(any="telegram* whatsapp* vatsap* viber* instagram* facebook* spotify* zoom* skype* discord* steam* word excel powerpoint* outlook*"),
    # xavfli amallar (tilidan qat'i nazar rad etiladi)
    "DANGER": dict(any=("ochir* udal* delet* remov* erase wipe format* restart reboot shutdown poweroff perezagruz* perezapus* viklyuch* otklyuch* "
                        "kochir* perenes* pereimen* rename move copy skopir* yubor* otprav* send ornat* ustanov* install* parol* password "
                        "zakro* close yop yopib yoping yopish kill ozgartir* izmen* change modify edit tahrir* tashla* vibros* sotri "
                        "korzin* recycle trash del rm sleep hibernate uninstal* cmd powershell pwsh bash sudo regedit eval exec wscript cscript mshta")),
    # til belgisi beruvchi, lekin ma'nosiz so'zlar (ularni qidiruv so'rovidan ham chiqaramiz)
    "FUNC": dict(uz="ni ga da dan ning ishga iltimos menga meni men uchun haqida boyicha ekan ekanini internetda malumot* va hamda keyin tez tezroq hozir",
                 ru="мне пожалуйста для про на в во по из потом затем быстро срочно сейчас pozhaluysta pojaluysta", en="the please to my me of for about on and then quickly now fast asap pls plz"),
    "GREET": dict(any="pyatnitsa пятница friday hey ok salom привет здравствуй hello hi"),
}
CONJ = {"va", "hamda", "keyin", "potom", "zatem", "and", "then", "i"}      # «и» -> «i» (translit)
VERBS = {"OPEN", "SEARCH", "SHOW", "CHECK", "CREATE", "SPEEDUP"}
APP_OBJ = ["CHROME", "BROWSER", "CALC", "NOTEPAD", "EXPLORER", "YOUTUBE", "DOWNLOADS", "DESKTOP", "DOCUMENTS"]
APP_ID = {"CHROME": "chrome", "BROWSER": "browser", "CALC": "calculator", "NOTEPAD": "notepad", "EXPLORER": "explorer",
          "YOUTUBE": "youtube", "DOWNLOADS": "downloads", "DESKTOP": "desktop", "DOCUMENTS": "documents"}
BIGRAMS = [("ish", "stol", "DESKTOP"), ("rabo", "stol", "DESKTOP"), ("fayl", "menej", "EXPLORER"), ("file", "manag", "EXPLORER"),
           ("grafik", "kart", "GPU"), ("video", "card", "GPU"), ("turn", "off", "DANGER"), ("shut", "down", "DANGER"),
           ("log", "off", "DANGER"), ("qayta", "ishga", "DANGER"), ("qayta", "yoq", "DANGER"), ("qayta", "yukla", "DANGER"), ("sign", "out", "DANGER"), ("tizim", "fayl", "ADMIN"), ("sistemn", "fayl", "ADMIN"),
           ("system", "file", "ADMIN"), ("system", "restore", "DANGER")]

EXACT: dict[str, tuple[str, str]] = {}
PREFIX: list[tuple[str, str, str]] = []
for _c, _langs in LEX_SRC.items():
    for _lang, _words in _langs.items():
        for _w in _words.split():
            _star = _w.endswith("*")
            _form = normalize(_w.rstrip("*"))
            if _star and len(_form) >= 4:
                PREFIX.append((_form, _c, _lang))
            else:
                EXACT[_form] = (_c, _lang)
PREFIX.sort(key=lambda x: -len(x[0]))
_FUZZ_POOL = [f for f in EXACT if len(f) >= 5] + [p[0] for p in PREFIX if len(p[0]) >= 5]
_POOL_MAP = {**{f: EXACT[f] for f in EXACT if len(f) >= 5}, **{p[0]: (p[1], p[2]) for p in PREFIX if len(p[0]) >= 5}}
_NO_FUZZ = {"DANGER"}        # xavfli so'zlarga yaqin (taxminiy) moslashtirish qilinmaydi

UZ_PIECES = ["larimizni", "larimni", "imizni", "ingizni", "asini", "asida", "asiga", "lari", "larni", "larga", "larda", "lardan", "imiz", "ingiz",
             "imni", "ning", "dagi", "lar", "dan", "ini", "asi", "ni", "ga", "ka", "qa", "da", "im", "ing", "si"]
RU_PIECES = ["ami", "ov", "om", "ah", "ey", "oy", "ye", "ya", "yu", "iy", "ogo", "ki", "ku", "ke", "ok"]
_ALL_SUFFIX = sorted(set(UZ_PIECES + RU_PIECES + ["a", "u", "e", "y", "i"]), key=len, reverse=True)


def _decompose(tail: str, pieces: list[str]) -> bool:
    if not tail:
        return True
    return any(tail.startswith(p) and _decompose(tail[len(p):], pieces) for p in pieces)


def _tail_lang(tail: str) -> str | None:
    if not tail:
        return None
    if _decompose(tail, UZ_PIECES) or (len(tail) > 1 and tail[0] in "ai" and _decompose(tail[1:], UZ_PIECES)):
        return "uz"
    if _decompose(tail, RU_PIECES):
        return "ru"
    return None


def _strip(word: str, depth: int = 2):
    if depth == 0:
        return
    for suf in _ALL_SUFFIX:
        if word.endswith(suf) and len(word) - len(suf) >= 3:
            stem = word[: -len(suf)]
            yield stem
            yield from _strip(stem, depth - 1)


@dataclass
class Tok:
    raw: str
    norm: str
    concept: str | None = None
    langs: tuple[str, ...] = ()
    fuzzy: bool = False


def resolve(word: str) -> tuple[str, tuple[str, ...], bool] | None:
    """Bitta normallashtirilgan so'zni tushunchaga bog'laydi: (concept, til-dalillari, taxminiymi)."""
    if not word:
        return None
    if word in EXACT:
        c, l = EXACT[word]
        return c, (() if l == "any" else (l,)), False
    for stem, c, l in PREFIX:                      # eng uzun o'zak birinchi
        if word.startswith(stem):
            ev = [] if l == "any" else [l]
            tl = _tail_lang(word[len(stem):])
            return c, tuple(ev + ([tl] if tl else [])), False
    for stem in _strip(word):                      # qo'shimchalarni olib tashlab
        if stem in EXACT:
            c, l = EXACT[stem]
            tl = _tail_lang(word[len(stem):])
            return c, tuple(([] if l == "any" else [l]) + ([tl] if tl else [])), False
        for st, c, l in PREFIX:
            if stem.startswith(st):
                tl = _tail_lang(word[len(st):])
                return c, tuple(([] if l == "any" else [l]) + ([tl] if tl else [])), False
    for w in [word, *_strip(word)]:                # imlo xatolari (qo'shimchasiz variantlar ham)
        if len(w) < 5:
            continue
        for cand in difflib.get_close_matches(w, _FUZZ_POOL, n=1, cutoff=0.82):
            c, l = _POOL_MAP[cand]
            if c not in _NO_FUZZ:
                return c, (() if l == "any" else (l,)), True
        for st, c, l in PREFIX:
            if len(st) >= 5 and c not in _NO_FUZZ and len(w) >= len(st) - 1 \
                    and difflib.SequenceMatcher(None, w[: len(st)], st).ratio() >= 0.8:
                return c, (() if l == "any" else (l,)), True
    return None


# --------------------------------------------------------------------------- tahlil
@dataclass
class Clause:
    toks: list[Tok]
    verbs: set[str] = field(default_factory=set)
    inherited: set[str] = field(default_factory=set)

    def has(self, *concepts: str) -> bool:
        return any(t.concept in concepts for t in self.toks)

    @property
    def concepts(self) -> set[str]:
        return {t.concept for t in self.toks if t.concept}

    @property
    def fuzzy_count(self) -> int:
        return sum(t.fuzzy for t in self.toks)

    def all_verbs(self) -> set[str]:
        return self.verbs | self.inherited


def _tokenize(segment: str) -> list[Tok]:
    raws = re.findall(r"[^\W_]+(?:'[^\W_]+)*", basic(segment))
    toks = [Tok(r, normalize(r)) for r in raws]
    toks = [t for t in toks if t.norm]
    i = 0
    out: list[Tok] = []
    while i < len(toks):                                         # ikki so'zli iboralar
        if i + 1 < len(toks):
            a, b = toks[i].norm, toks[i + 1].norm
            hit = next((c for p1, p2, c in BIGRAMS if a.startswith(p1) and b.startswith(p2)), None)
            if hit:
                out.append(Tok(f"{toks[i].raw} {toks[i + 1].raw}", a + b, hit, ()))
                i += 2
                continue
        t = toks[i]
        r = resolve(t.norm)
        if r:
            t.concept, t.langs, t.fuzzy = r
        out.append(t)
        i += 1
    return out


CONJ_LANG = {"va": "uz", "hamda": "uz", "keyin": "uz", "potom": "ru", "zatem": "ru", "and": "en", "then": "en"}


def split_clauses(text: str, evidence: list[str] | None = None) -> list[list[Tok]]:
    segments = re.split(r"(?<!\d)[,.]|[,.](?!\d)|[;!?\n]", text)
    clauses: list[list[Tok]] = []
    for seg in segments:
        cur: list[Tok] = []
        for t in _tokenize(seg):
            if t.norm in CONJ and t.concept in (None, "FUNC"):
                lg = CONJ_LANG.get(t.norm) or ("ru" if t.raw == "и" else None)
                if lg and evidence is not None:
                    evidence.append(lg)
                if cur:
                    clauses.append(cur)
                cur = []
            else:
                cur.append(t)
        if cur:
            clauses.append(cur)
    return clauses


def detect_langs(toks: list[Tok], raw_text: str) -> tuple[str, set[str]]:
    count = {"uz": 0, "ru": 0, "en": 0}
    for t in toks:
        for l in t.langs:
            count[l] += 1
    found = {l for l, n in count.items() if n}
    if not found:                                                # dalil yo'q: yozuv turi bo'yicha
        if re.search(r"[ўқғҳ]", raw_text.lower()):
            return "uz", {"uz"}
        cyr = len(re.findall(r"[а-яё]", raw_text.lower()))
        return ("ru", {"ru"}) if cyr and cyr >= len(re.findall(r"[a-z]", raw_text.lower())) else ("uz", set())
    if count["uz"]:
        return "uz", found                                       # uz bor yoki aralash -> o'zbekcha javob
    return ("ru" if count["ru"] >= count["en"] else "en"), found


# --------------------------------------------------------------------------- nomzodlar
@dataclass
class Cand:
    score: float
    commands: list[Command]
    kind: str
    hint: str = ""               # aniqlashtiruvchi savol kaliti (bo'sh bo'lsa «did_you_mean»)
    title: str = ""


def ask(action: str, args: dict, lang: str) -> str:
    key = "ask.open_app" if action == "open_app" else f"ask.{action}"
    kw = dict(args)
    if action == "open_app":
        kw["title"] = app_title(args["app"], lang)
    if action == "search":
        kw["q"] = args["query"]
    if action == "convert_usd":
        kw["amount"] = f"{args['amount']:g}"
    return T(key, lang, **kw)


def mk(action: str, lang: str, **args) -> Command:
    return Command(action, args, ask(action, args, lang), intent=INTENT_OF(action, args))


def INTENT_OF(action: str, args: dict) -> str:
    if action == "open_app":
        return "open_folder" if args.get("app") in ("downloads", "desktop", "documents") else "open_app"
    return {"new_window": "open_app", "search": "web_search", "rate_usd": "get_exchange_rate", "convert_usd": "get_exchange_rate",
            "weather": "get_weather", "time": "get_system_info", "health_uptime": "get_system_info",
            "health_report": "get_pc_health"}.get(action, "get_pc_health")


def _query(cl: Clause) -> str:
    skip = {"SEARCH", "GOOGLE", "FUNC", "GREET", "SHOW"}
    words = [t.raw.strip("'") for t in cl.toks if t.concept not in skip and t.norm not in CONJ]
    return " ".join(w for w in words if w)[:200]


def _build(cl: Clause, lang: str) -> list[Cand]:
    c = cl.concepts
    verbs = cl.all_verbs()
    cands: list[Cand] = []
    qwords = c & {"HOWMUCH", "HOW", "WHICH", "MANY", "USE"}
    ask_like = bool(verbs & {"SHOW", "CHECK"} or qwords)
    fz = 0.05 * cl.fuzzy_count

    # ---- ochish
    objs = [o for o in APP_OBJ if o in c]
    if "CHROME" in objs and "BROWSER" in objs:
        objs.remove("BROWSER")
    new_win = "NEW" in c and ("WINDOW" in c) and ({"BROWSER", "CHROME"} & c or "NEW" in c)
    if "GOOGLE" in c and not objs and "SEARCH" not in verbs and not new_win and "OPEN" in verbs:
        objs = ["BROWSER"]
    if new_win and "OPEN" in verbs:
        cands.append(Cand(0.92 - fz, [mk("new_window", lang)], "open"))
    elif objs and "OPEN" in verbs and "SEARCH" not in verbs:
        cands.append(Cand(0.92 - fz, [mk("open_app", lang, app=APP_ID[o]) for o in objs], "open"))
    elif "OPEN" in verbs and not objs and "UNSUP" not in c and not (c & {"SEARCH"}) and len(cl.toks) <= 4:
        cands.append(Cand(0.45, [], "open", hint="cl.open"))
    elif (objs or "GOOGLE" in c) and not (verbs - {"OPEN"}) and not qwords and len(cl.concepts - {"FUNC", "GREET", "FOLDER"}) <= 2:
        title = app_title(APP_ID[objs[0]], lang) if objs else "Google"
        pair = ({"CHROME", "BROWSER", "GOOGLE"} & (set(objs) | c))
        cands.append(Cand(0.5, [], "object", hint="cl.open_or_search" if pair else "cl.object", title=title))

    # ---- qidiruv
    if "SEARCH" in verbs:
        q = _query(cl)
        if len(q) >= 2:
            s = 0.8 + (0.2 if "GOOGLE" in c else 0)
            cands.append(Cand(min(1.0, s) - fz, [mk("search", lang, query=q)], "search"))
        else:
            cands.append(Cand(0.45, [], "search", hint="cl.search"))

    # ---- valyuta
    if "DOLLAR" in c:
        amount = extract_amount(" ".join(t.raw for t in cl.toks))
        if amount and (c & {"SOM", "HOWMUCH"}):
            cands.append(Cand(0.9 - fz, [mk("convert_usd", lang, amount=amount)], "money"))
        elif "KURS" in c:
            cands.append(Cand(0.7 + (0.1 if verbs & {"SHOW", "CHECK"} else 0) + (0.1 if "HOWMUCH" in c else 0) - fz, [mk("rate_usd", lang)], "money"))
        elif "HOWMUCH" in c:
            cands.append(Cand(0.75 - fz, [mk("rate_usd", lang)], "money"))
        elif verbs & {"SHOW", "CHECK"}:
            cands.append(Cand(0.6, [mk("rate_usd", lang)], "money"))
        else:
            cands.append(Cand(0.4, [], "money", hint="cl.money"))

    # ---- ob-havo / vaqt
    if "WEATHER" in c:
        cands.append(Cand(0.6 + (0.3 if ask_like else 0) - fz, [mk("weather", lang)], "weather"))
    pc_up = "PC" in c and "RUN" in c
    if (c & {"TIME", "DATE"}) and not pc_up:
        cands.append(Cand(0.72 + (0.2 if ask_like else 0) - fz, [mk("time", lang)], "time"))

    cands += _health(cl, lang, verbs, qwords, fz)
    return cands


def _health(cl: Clause, lang: str, verbs: set[str], qwords: set[str], fz: float) -> list[Cand]:
    c = cl.concepts
    action_word = bool(verbs & {"SHOW", "CHECK"} or qwords or "HOW" in c)
    base = 0.6 + (0.3 if action_word else 0.0) - fz
    order: list[str] = []
    if "REPORT" in c and (verbs & {"CREATE", "SHOW", "CHECK"} or c & {"PC", "STATE", "DIAG"}):
        return [Cand(0.92 - fz, [mk("health_report", lang)], "health")]
    if "ADMIN" in c:
        return [Cand(0.9, [mk("admin_info", lang)], "health")]
    if "DIAG" in c or ("FULL" in c and (verbs & {"CHECK"} or "PC" in c)):
        return [Cand(0.92 - fz, [mk("health_full", lang)], "health")]
    other_objs = c & ({"CPU", "RAM", "DISK", "GPU", "BATT", "PROCS", "TEMP"} | set(APP_OBJ))
    if "SPEEDUP" in verbs and not other_objs:
        return [Cand(0.9 - fz, [mk("speedup_advice", lang)], "health")]
    which_use = bool(c & {"WHICH", "MANY"} and "USE" in c and c & {"RAM", "CPU"})
    if ("PROCS" in c and (c & {"RAM", "CPU"} or qwords or "SHOW" in verbs) or which_use) and "OPEN" not in verbs:
        ram, cpu = "RAM" in c, "CPU" in c
        by = "ram" if ram and not cpu else "cpu" if cpu and not ram else "both"
        return [Cand(0.9 - fz if (qwords or ram or cpu) else 0.65, [mk("health_top", lang, by=by)], "health")]
    if "PC" in c and "RUN" in c and (c & {"TIME", "HOWMUCH"}):
        return [Cand(0.9 - fz, [mk("health_uptime", lang)], "health")]
    if "BATT" in c:
        return [Cand(base, [mk("health_battery", lang)], "health")]
    if "TEMP" in c:
        return [Cand(base + (0.05 if c & {"CPU", "GPU"} else 0), [mk("health_temps", lang)], "health")]
    if "GPU" in c:
        return [Cand(base, [mk("health_gpu", lang)], "health")]
    disk = "DISK" in c or ("SPACE" in c and (c & {"FREE", "HOWMUCH"}))
    targets = [a for a, on in (("health_cpu", "CPU" in c), ("health_ram", "RAM" in c), ("health_disk", disk)) if on]
    # tartib: gapdagi paydo bo'lish tartibi
    pos = {"health_cpu": "CPU", "health_ram": "RAM", "health_disk": "DISK"}
    first = {}
    for i, t in enumerate(cl.toks):
        first.setdefault(t.concept, i)
    targets.sort(key=lambda a: first.get(pos[a], first.get("SPACE", 99)))
    if targets:
        return [Cand(base, [mk(a, lang) for a in targets], "health")]
    if "STATE" in c or ("PC" in c and verbs & {"CHECK"}):
        return [Cand(max(base, 0.8 - fz) if "STATE" in c and "PC" in c else base if "STATE" in c or action_word else 0.55,
                     [mk("health_status", lang)], "health")]
    if "PC" in c and len(c - {"FUNC", "GREET"}) == 1:
        return [Cand(0.45, [], "health", hint="cl.health")]
    return []


# --------------------------------------------------------------------------- yuqori daraja
def _inherit(clauses: list[Clause]) -> None:
    for i, cl in enumerate(clauses):
        if cl.verbs or not (cl.concepts - {"FUNC", "GREET"}):
            continue
        nxt = next((clauses[j].verbs for j in range(i + 1, len(clauses)) if clauses[j].verbs), None)
        prv = next((clauses[j].verbs for j in range(i - 1, -1, -1) if clauses[j].verbs), None)
        cl.inherited = set(nxt or prv or ())


def _merge_search_fragments(clauses: list[list[Tok]]) -> list[list[Tok]]:
    """«Python va java qidir»: bo'sh (tushunchasiz) bo'lak qidiruv bo'lagiga qo'shiladi."""
    out: list[list[Tok]] = []
    for toks in clauses:
        has_search = any(t.concept == "SEARCH" for t in toks)
        if out and has_search and not any(t.concept for t in out[-1] if t.concept not in ("FUNC", "GREET")):
            out[-1] = out[-1] + toks
        else:
            out.append(toks)
    return out


def _merge_incomplete_open(clauses: list[list[Tok]]) -> list[list[Tok]]:
    """«Papkani och, Downloads»: ob'ektsiz «ochish» bo'lagi yonidagi ob'ektli bo'lak bilan birlashtiriladi."""
    def concepts(toks): return {t.concept for t in toks if t.concept}
    def incomplete(toks): c = concepts(toks); return "OPEN" in c and "FOLDER" in c and not (c & set(APP_OBJ) | {"GOOGLE"} & c)
    def objects_only(toks): c = concepts(toks); return bool(c & set(APP_OBJ)) and not (c & VERBS)
    out: list[list[Tok]] = []
    i = 0
    while i < len(clauses):
        cur = clauses[i]
        if incomplete(cur) and i + 1 < len(clauses) and objects_only(clauses[i + 1]):
            out.append(cur + clauses[i + 1]); i += 2
        elif objects_only(cur) and i + 1 < len(clauses) and incomplete(clauses[i + 1]):
            out.append(cur + clauses[i + 1]); i += 2
        else:
            out.append(cur); i += 1
    return out


MODS = {"HOWMUCH", "HOW", "WHICH", "MANY", "USE", "PERCENT"}


def _drop_filler(clauses: list[list[Tok]]) -> list[list[Tok]]:
    """Faqat «iltimos», «salom» kabi so'zlardan iborat bo'laklar tashlanadi."""
    kept = [c for c in clauses if not all(t.concept in ("FUNC", "GREET") for t in c)]
    return kept or clauses


def _merge_verb_only(clauses: list[list[Tok]]) -> list[list[Tok]]:
    """«Google Chrome kerak, ochib ber»: ob'ektsiz fe'l bo'lagi fe'lsiz ob'ekt bo'lagiga qo'shiladi."""
    def cs(toks): return {t.concept for t in toks if t.concept} - {"FUNC", "GREET"}
    def verb_only(toks): c = cs(toks); return bool(c & VERBS) and c <= VERBS
    def objects(toks): c = cs(toks); return bool(c) and not (c & VERBS)
    out: list[list[Tok]] = []
    i = 0
    while i < len(clauses):
        cur = clauses[i]
        if verb_only(cur) and out and objects(out[-1]):
            out[-1] = out[-1] + cur
        elif verb_only(cur) and i + 1 < len(clauses) and objects(clauses[i + 1]):
            out.append(cur + clauses[i + 1]); i += 1
        else:
            out.append(cur)
        i += 1
    return out


def _merge_modifiers(clauses: list[list[Tok]]) -> list[list[Tok]]:
    """«Diskda joy qolganmi, qancha»: faqat so'roq so'zlaridan iborat bo'lak qo'shni bo'lakka qo'shiladi."""
    def only_mods(toks):
        c = {t.concept for t in toks if t.concept} - {"FUNC", "GREET"}
        return bool(c) and c <= MODS
    out: list[list[Tok]] = []
    pending: list[Tok] = []
    for toks in clauses:
        if only_mods(toks):
            if out:
                out[-1] = out[-1] + toks
            else:
                pending += toks
        else:
            out.append(pending + toks if pending else toks)
            pending = []
    return out or ([pending] if pending else [])


def analyze(text: str):
    """Qadamma-qadam natija (testlar va nosozliklarni topish uchun)."""
    text = (text or "").strip()[:500]
    evidence: list[str] = []
    parts = _merge_modifiers(_merge_verb_only(_merge_incomplete_open(_merge_search_fragments(_drop_filler(split_clauses(text, evidence))))))
    clauses = [Clause(toks) for toks in parts]
    for cl in clauses:
        cl.verbs = {t.concept for t in cl.toks if t.concept in VERBS}
    _inherit(clauses)
    all_toks = [t for cl in clauses for t in cl.toks] + [Tok("", "", None, (e,)) for e in evidence]
    lang, found = detect_langs(all_toks, text)
    return clauses, lang, found


def parse(text: str) -> ParseResult:
    clauses, lang, found = analyze(text)
    res = ParseResult("unknown", message=T("unknown", lang), lang=lang, langs=sorted(found))
    if not clauses:
        return res
    # ---- xavfsizlik: xavfli so'z bo'lsa (qidiruv matnining ichidagisidan tashqari) hammasi rad etiladi
    for cl in clauses:
        if cl.has("DANGER") and "SEARCH" not in cl.verbs:
            return ParseResult("blocked", message=T("blocked", lang), lang=lang, langs=sorted(found), confidence=1.0)
    for cl in clauses:
        if cl.has("UNSUP") and not cl.has(*APP_OBJ) and "SEARCH" not in cl.verbs:
            name = next(t.raw for t in cl.toks if t.concept == "UNSUP")
            return ParseResult("blocked", message=T("unsupported", lang, name=name.capitalize()), lang=lang, langs=sorted(found), confidence=1.0)
    commands: list[Command] = []
    conf = 1.0
    weak: ParseResult | None = None
    for cl in clauses:
        meaningful = cl.concepts - {"FUNC", "GREET"}
        if not meaningful:
            if any(t.concept is None for t in cl.toks) and len(clauses) > 1:
                part = " ".join(t.raw for t in cl.toks)
                return ParseResult("clarify", message=T("cl.part", lang, part=part), lang=lang, langs=sorted(found))
            continue
        cands = sorted(_build(cl, lang), key=lambda x: -x.score)
        is_weak = not cl.verbs and meaningful <= {"PC", "RUN"} and len(clauses) > 1
        if is_weak and (not cands or cands[0].hint == "cl.health"):
            weak = ParseResult("clarify", message=T("cl.health", lang), lang=lang, langs=sorted(found))
            continue                       # kompyuter haqidagi tavsif: boshqa bo'lakda buyruq bo'lsa, shuni bajaramiz
        if not cands or cands[0].score < CLARIFY_MIN:
            return ParseResult("unknown", message=T("unknown", lang), lang=lang, langs=sorted(found))
        top = cands[0]
        if top.score < ACCEPT or not top.commands:
            msg = T(top.hint, lang, title=top.title) if top.hint else T("cl.did_you_mean", lang, ask=top.commands[0].confirm_text)
            return ParseResult("clarify", message=msg, lang=lang, langs=sorted(found), confidence=top.score)
        rivals = [x for x in cands[1:] if x.commands and x.score >= 0.6 and top.score - x.score < TIE_GAP and x.kind != top.kind]
        if rivals:
            msg = T("cl.two", lang, a=top.commands[0].confirm_text, b=rivals[0].commands[0].confirm_text)
            return ParseResult("clarify", message=msg, lang=lang, langs=sorted(found), confidence=top.score)
        conf = min(conf, top.score)
        commands += top.commands
    if not commands:
        return weak or res
    seen, uniq = set(), []
    for c in commands:                                   # takroriy amallarni olib tashlash
        key = (c.action, tuple(sorted(map(str, c.args.items()))))
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    if len(uniq) > MAX_COMMANDS:
        return ParseResult("clarify", message=T("too_many", lang, n=MAX_COMMANDS), lang=lang, langs=sorted(found))
    return ParseResult("ok", command=uniq[0], commands=uniq, lang=lang, langs=sorted(found), confidence=conf)
