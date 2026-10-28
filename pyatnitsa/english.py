"""Ingliz tili mashqlari: lug'at viktorinasi, talaffuz tekshiruvi, tinglash mashqi, so'z tarjimasi.

Hamma narsa lokal (tashqi xizmatsiz). Mashq faqat foydalanuvchi so'raganda boshlanadi; har bir javob alohida ovozli buyruq (Space ushlab turib).
Natija faqat HAQIQATDA yakunlangan mashq uchun yoziladi. Bu IELTS yoki boshqa imtihon balini baholamaydi.
Talaffuz tekshiruvi nutqni tanish dvigatelining natijasiga tayanadi: dvigatel noaniq so'zni «tuzatib» yuborishi mumkin, shuning uchun bu taxminiy baho.
"""
from __future__ import annotations

import difflib
import random
import re
from dataclasses import dataclass, field

from .commands import normalize
from .i18n import T

LEVELS = ("A1", "A2", "B1")
DEFAULT_LEVEL = "A1"
MAX_QUESTIONS = 20

# so'z: (inglizcha, o'zbekcha, ruscha)
VOCAB: dict[str, list[tuple[str, str, str]]] = {
    "A1": [
        ("apple", "olma", "яблоко"), ("book", "kitob", "книга"), ("water", "suv", "вода"), ("house", "uy", "дом"), ("friend", "do'st", "друг"),
        ("family", "oila", "семья"), ("school", "maktab", "школа"), ("teacher", "o'qituvchi", "учитель"), ("city", "shahar", "город"),
        ("car", "mashina", "машина"), ("dog", "it", "собака"), ("cat", "mushuk", "кошка"), ("food", "ovqat", "еда"), ("bread", "non", "хлеб"),
        ("milk", "sut", "молоко"), ("morning", "ertalab", "утро"), ("night", "tun", "ночь"), ("day", "kun", "день"), ("big", "katta", "большой"),
        ("small", "kichik", "маленький"), ("happy", "xursand", "счастливый"), ("good", "yaxshi", "хороший"), ("bad", "yomon", "плохой"),
        ("new", "yangi", "новый"), ("old", "eski", "старый"), ("eat", "yemoq", "есть"), ("drink", "ichmoq", "пить"), ("read", "o'qimoq", "читать"),
        ("write", "yozmoq", "писать"), ("speak", "gapirmoq", "говорить"), ("sleep", "uxlamoq", "спать"), ("mother", "ona", "мама"),
        ("father", "ota", "папа"), ("brother", "aka yoki uka", "брат"), ("sister", "opa yoki singil", "сестра"), ("red", "qizil", "красный"),
        ("blue", "ko'k", "синий"), ("green", "yashil", "зелёный"), ("today", "bugun", "сегодня"), ("tomorrow", "ertaga", "завтра"),
    ],
    "A2": [
        ("improve", "yaxshilamoq", "улучшать"), ("travel", "sayohat qilmoq", "путешествовать"), ("weather", "ob-havo", "погода"),
        ("hungry", "och", "голодный"), ("cheap", "arzon", "дешёвый"), ("expensive", "qimmat", "дорогой"), ("borrow", "qarzga olmoq", "занимать"),
        ("remember", "eslamoq", "помнить"), ("forget", "unutmoq", "забывать"), ("choose", "tanlamoq", "выбирать"), ("invite", "taklif qilmoq", "приглашать"),
        ("visit", "tashrif buyurmoq", "посещать"), ("ticket", "chipta", "билет"), ("hospital", "kasalxona", "больница"), ("neighbour", "qo'shni", "сосед"),
        ("during", "davomida", "во время"), ("always", "doim", "всегда"), ("never", "hech qachon", "никогда"), ("often", "tez-tez", "часто"),
        ("early", "erta", "рано"), ("late", "kech", "поздно"),
    ],
    "B1": [
        ("achieve", "erishmoq", "достигать"), ("advantage", "afzallik", "преимущество"), ("opportunity", "imkoniyat", "возможность"),
        ("experience", "tajriba", "опыт"), ("develop", "rivojlantirmoq", "развивать"), ("decide", "qaror qilmoq", "решать"),
        ("suggest", "taklif etmoq", "предлагать"), ("recommend", "tavsiya qilmoq", "рекомендовать"), ("environment", "atrof-muhit", "окружающая среда"),
        ("knowledge", "bilim", "знание"), ("avoid", "oldini olmoq", "избегать"), ("compare", "solishtirmoq", "сравнивать"),
        ("discuss", "muhokama qilmoq", "обсуждать"), ("require", "talab qilmoq", "требовать"), ("society", "jamiyat", "общество"),
        ("benefit", "foyda", "польза"), ("reduce", "kamaytirmoq", "уменьшать"), ("increase", "oshirmoq", "увеличивать"),
        ("useful", "foydali", "полезный"), ("successful", "muvaffaqiyatli", "успешный"),
    ],
}
BANK = {w[0]: w for lvl in LEVELS for w in VOCAB[lvl]}

PRONUNCIATION = {
    "A1": ["My name is Anna.", "I like to read books.", "Where is the bus station?", "The weather is good today.", "She drinks water every morning."],
    "A2": ["I would like to improve my English.", "We are going to travel next summer.", "Can you tell me the way to the hospital?"],
    "B1": ["It is important to develop good study habits.", "I recommend that you compare the two options.", "Knowledge is a great advantage."],
}

# (jumla, savol, [variantlar], to'g'ri variant indeksi)
LISTENING = {
    "A1": [
        ("The book is on the table.", "Where is the book?", ["on the table", "in the bag", "under the chair"], 0),
        ("My sister has a red car.", "What colour is the car?", ["blue", "red", "green"], 1),
        ("I drink milk every morning.", "When does he drink milk?", ["at night", "in the morning", "in the evening"], 1),
        ("We have two cats and one dog.", "How many cats are there?", ["one", "three", "two"], 2),
        ("Tom goes to school by bus.", "How does Tom go to school?", ["by bus", "by car", "on foot"], 0),
    ],
    "A2": [
        ("I was late because the bus was very slow.", "Why was he late?", ["he forgot the time", "the bus was slow", "he was ill"], 1),
        ("The ticket was cheap, so we bought three.", "How many tickets did they buy?", ["two", "four", "three"], 2),
    ],
    "B1": [
        ("The meeting was moved to Friday because the manager is travelling on Thursday.", "Why was the meeting moved?", ["the manager is travelling", "the room was busy", "it was a holiday"], 0),
    ],
}

STOP_WORDS = {"stop", "cancel", "exit", "quit", "bekor", "toxtat", "toxtating", "chiq", "chiqish", "stoy", "otmena", "hvatit", "xvatit", "ostanovi", "ostanovis"}
REPEAT_WORDS = {"repeat", "again", "qaytar", "qayta", "qaytadan", "povtori", "povtorit", "esche"}
_NUM = {"1": 1, "one": 1, "bir": 1, "birinchi": 1, "odin": 1, "pervyy": 1, "first": 1, "a": 1,
        "2": 2, "two": 2, "ikki": 2, "ikkinchi": 2, "dva": 2, "vtoroy": 2, "second": 2, "b": 2, "bi": 2,
        "3": 3, "three": 3, "uch": 3, "uchinchi": 3, "tri": 3, "tretiy": 3, "third": 3, "c": 3, "si": 3}


def norm_level(text: str, default: str = DEFAULT_LEVEL) -> str:
    m = re.search(r"\b(a1|a2|b1)\b", normalize(text))
    return m.group(1).upper() if m else default


def words_of(text: str) -> list[str]:
    return [w for w in normalize(text).split() if w]


def lookup(word: str):
    """(en, uz, ru) yoki None — lokal lug'atdan."""
    key = normalize(word).strip()
    return BANK.get(key)


def pronunciation_score(target: str, heard: str) -> tuple[float, list[str]]:
    t, h = words_of(target), words_of(heard)
    if not t or not h:
        return 0.0, t
    sm = difflib.SequenceMatcher(None, t, h)
    matched = sum(b.size for b in sm.get_matching_blocks())
    ok = set()
    for b in sm.get_matching_blocks():
        ok.update(range(b.a, b.a + b.size))
    missed = [t[i] for i in range(len(t)) if i not in ok]
    return matched / len(t), missed


@dataclass
class Turn:
    text: str
    done: bool = False
    correct: int | None = None      # tugaganda: to'g'ri javoblar soni
    total: int | None = None
    wrong_words: list[str] = field(default_factory=list)
    speak: str = ""                 # inglizcha ovozda aytiladigan matn (tinglash mashqi)
    stt_lang: str = ""              # keyingi javob uchun tanish tili (masalan en-US)
    kind: str = ""
    level: str = DEFAULT_LEVEL
    saved: bool = False             # mashq yakunlangan va natija yozilishi kerak
    unclear: bool = False           # javob tushunarsiz bo'ldi (mashq ichidagi buyruq emas bo'lishi mumkin)


def _cmd_word(text: str) -> str:
    w = words_of(text)
    if any(x in STOP_WORDS for x in w):
        return "stop"
    if any(x in REPEAT_WORDS for x in w) and len(w) <= 3:
        return "repeat"
    return ""


def pick_number(text: str, options: list[str], lang: str = "uz") -> int | None:
    """Javobdan variant raqamini (1..n) topadi: «ikkinchi», «2», «B» yoki variantning o'zi."""
    nw = words_of(text)
    for w in nw:
        n = _NUM.get(w)
        if n and n <= len(options):
            return n
    full = " ".join(nw)
    best, idx = 0.0, None
    for i, opt in enumerate(options, 1):
        o = " ".join(words_of(opt))
        if not o:
            continue
        sc = 1.0 if o in full or full == o else difflib.SequenceMatcher(None, o, full).ratio()
        if sc > best:
            best, idx = sc, i
    return idx if best >= 0.8 else None


class Quiz:
    """Ko'p variantli lug'at viktorinasi: inglizcha so'z -> tarjima. Javob: variant raqami yoki tarjimaning o'zi."""
    kind = "quiz"

    def __init__(self, level: str, n: int, lang: str, rng: random.Random | None = None):
        self.level, self.lang = level if level in LEVELS else DEFAULT_LEVEL, (lang if lang in ("uz", "ru", "en") else "uz")
        self.rng = rng or random.Random()
        pool = list(VOCAB[self.level])
        self.rng.shuffle(pool)
        self.n = max(1, min(int(n), MAX_QUESTIONS, len(pool)))
        self.items = pool[:self.n]
        self.i = 0
        self.correct = 0
        self.wrong: list[str] = []
        self.options: list[str] = []
        self.answer_idx = 0

    def _tr(self, w) -> str:
        return w[2] if self.lang == "ru" else w[1]

    def _ask(self) -> str:
        w = self.items[self.i]
        others = [self._tr(x) for x in VOCAB[self.level] if x[0] != w[0] and self._tr(x) != self._tr(w)]
        self.rng.shuffle(others)
        self.options = others[:2] + [self._tr(w)]
        self.rng.shuffle(self.options)
        self.answer_idx = self.options.index(self._tr(w)) + 1
        opts = "\n".join(f"{k}. {o}" for k, o in enumerate(self.options, 1))
        return T("eng.q", self.lang, i=self.i + 1, n=self.n, word=w[0]) + "\n" + opts

    def start(self) -> Turn:
        return Turn(T("eng.quiz.start", self.lang, n=self.n, level=self.level) + "\n\n" + self._ask(), kind=self.kind, level=self.level)

    def answer(self, text: str) -> Turn:
        c = _cmd_word(text)
        if c == "stop":
            return self._finish(T("eng.stopped", self.lang), stopped=True)
        if c == "repeat":
            return Turn(self._ask_again(), kind=self.kind, level=self.level)
        n = pick_number(text, self.options, self.lang)
        if n is None:
            return Turn(T("eng.unclear", self.lang) + "\n" + self._ask_again(), kind=self.kind, level=self.level, unclear=True)
        w = self.items[self.i]
        if n == self.answer_idx:
            self.correct += 1
            fb = T("eng.right", self.lang)
        else:
            self.wrong.append(w[0])
            fb = T("eng.wrong", self.lang, word=w[0], tr=self._tr(w))
        self.i += 1
        if self.i >= self.n:
            return self._finish(fb)
        return Turn(fb + "\n\n" + self._ask(), kind=self.kind, level=self.level)

    def _ask_again(self) -> str:
        w = self.items[self.i]
        opts = "\n".join(f"{k}. {o}" for k, o in enumerate(self.options, 1))
        return T("eng.q", self.lang, i=self.i + 1, n=self.n, word=w[0]) + "\n" + opts

    def _finish(self, prefix: str, stopped: bool = False) -> Turn:
        answered = self.i
        txt = prefix
        if answered:
            txt += "\n\n" + T("eng.result", self.lang, c=self.correct, n=answered)
            if self.wrong:
                txt += " " + T("eng.review", self.lang, words=", ".join(self.wrong))
        return Turn(txt, done=True, correct=self.correct, total=answered, wrong_words=list(self.wrong), kind=self.kind, level=self.level, saved=answered > 0)


class Pronunciation:
    kind = "pronunciation"

    def __init__(self, level: str, lang: str, rng: random.Random | None = None):
        self.level, self.lang = level if level in LEVELS else DEFAULT_LEVEL, (lang if lang in ("uz", "ru", "en") else "uz")
        self.rng = rng or random.Random()
        self.target = self.rng.choice(PRONUNCIATION[self.level])
        self.tries = 0
        self.best = 0.0

    def start(self) -> Turn:
        return Turn(T("eng.pron.start", self.lang, text=self.target), kind=self.kind, level=self.level, stt_lang="en-US")

    def answer(self, text: str) -> Turn:
        c = _cmd_word(text)
        if c == "stop":
            return Turn(T("eng.stopped", self.lang), done=True, kind=self.kind, level=self.level)
        if c == "repeat":
            return Turn(T("eng.pron.start", self.lang, text=self.target), kind=self.kind, level=self.level, stt_lang="en-US")
        self.tries += 1
        score, missed = pronunciation_score(self.target, text)
        self.best = max(self.best, score)
        pct = round(score * 100)
        if score >= 0.85:
            msg = T("eng.pron.good", self.lang, pct=pct, heard=text)
            return Turn(msg + "\n" + T("eng.pron.note", self.lang), done=True, correct=1, total=1, kind=self.kind, level=self.level, saved=True)
        msg = T("eng.pron.retry", self.lang, pct=pct, heard=text, missed=", ".join(missed) or "—")
        if self.tries >= 3:
            return Turn(msg + "\n" + T("eng.pron.end", self.lang), done=True, correct=0, total=1, wrong_words=missed, kind=self.kind, level=self.level, saved=True)
        return Turn(msg, kind=self.kind, level=self.level, stt_lang="en-US")


class Listening:
    kind = "listening"

    def __init__(self, level: str, lang: str, rng: random.Random | None = None):
        self.level, self.lang = level if level in LEVELS else DEFAULT_LEVEL, (lang if lang in ("uz", "ru", "en") else "uz")
        self.rng = rng or random.Random()
        self.sentence, self.question, self.options, self.right = self.rng.choice(LISTENING[self.level])
        self.plays = 0

    def _prompt(self, say: bool = True) -> Turn:
        opts = "\n".join(f"{k}. {o}" for k, o in enumerate(self.options, 1))
        self.plays += 1
        return Turn(T("eng.listen.q", self.lang, q=self.question) + "\n" + opts, kind=self.kind, level=self.level, speak=self.sentence if say else "")

    def start(self) -> Turn:
        t = self._prompt()
        t.text = T("eng.listen.start", self.lang) + "\n\n" + t.text
        return t

    def answer(self, text: str) -> Turn:
        c = _cmd_word(text)
        if c == "stop":
            return Turn(T("eng.stopped", self.lang), done=True, kind=self.kind, level=self.level)
        if c == "repeat":
            return self._prompt()
        n = pick_number(text, self.options, self.lang)
        if n is None:
            return Turn(T("eng.unclear", self.lang), kind=self.kind, level=self.level, unclear=True)
        ok = n == self.right + 1
        msg = T("eng.right", self.lang) if ok else T("eng.listen.wrong", self.lang, ans=self.options[self.right])
        return Turn(msg + "\n" + T("eng.listen.said", self.lang, text=self.sentence), done=True, correct=int(ok), total=1, kind=self.kind, level=self.level, saved=True)


def make_lesson(kind: str, level: str, lang: str, n: int = 10, rng: random.Random | None = None):
    if kind == "quiz":
        return Quiz(level, n, lang, rng)
    if kind == "pronunciation":
        return Pronunciation(level, lang, rng)
    if kind == "listening":
        return Listening(level, lang, rng)
    raise ValueError(kind)
