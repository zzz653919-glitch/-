"""Eslatma · vazifa · qayd · ingliz tili rejasi buyruqlarini tushunish (o'zbekcha · ruscha · inglizcha).
  Eslatma:  «Ertaga soat 16:00 da vazifamni eslat» · «Remind me to study English at 7 PM» · «Har kuni soat 19:00 da ingliz tilini o'rganishni eslat»
  Vazifa:   «Add a task to finish my Python homework» · «Bugungi vazifalarimni ko'rsat» · «Mark my English homework as completed» · «Show my overdue tasks»
  Qayd:     «Create a note called English Vocabulary» · «Yangi qayd: bozor ro'yxati» · «qayd qidir bozor»
  O'quv:    «Start my English study plan» · «Ingliz tili rejamni ko'rsat» · «Lug'at mashg'ulotini tugatdim» · «Show my study progress»
Eslatma/vazifa/qayd MATNI — ma'lumot: buyruq sifatida talqin qilinmaydi (ichida «o'chir» bo'lsa ham faqat matn bo'lib saqlanadi). Xavfli fe'l buyruq qismida
bo'lsa hamma narsa rad etiladi. Noaniq vaqt (9 — ertalabmi?) TAXMIN QILINMAYDI: `draft` bilan aniqlashtiriladi. Vazifa/eslatmani O'CHIRISH ovoz bilan
mumkin emas (faqat interfeysda, tasdiq bilan)."""
from __future__ import annotations

import re
from datetime import datetime

from . import nlu
from .commands import Command, ParseResult, normalize
from .i18n import T
from .reminders import describe_recur
from .timeparse import parse_when

# ---------------------------------------------------------------- so'zlar (normalizatsiya qilingan: lotin, kichik harf)
REM_VERB_PRE = ("eslat", "xotirlat", "napomn", "napominay", "remind")
REM_NOUN_PRE = ("eslatma", "reminder", "napominani")
TASK_NOUN_PRE = ("vazifa", "topshiriq", "zadach", "zadani")
TASK_NOUN_EX = {"task", "tasks", "todo", "todos"}
NOTE_NOUN_PRE = ("qayd", "zametk")
NOTE_NOUN_EX = {"note", "notes", "memo", "memos"}
ADD_PRE = ("qoy", "qosh", "yarat", "tuz", "yoz", "saqla", "postav", "sozdaj", "sozdai", "sozday", "sdelay", "zavedi", "dobav", "zapish", "zapomn", "napish", "create", "add", "make", "save", "write", "new", "yangi", "noviy", "novuyu", "take")
SHOW_PRE = ("korsat", "ayt", "ber", "chiqar", "royxat", "pokaj", "pokaz", "skaji", "show", "list", "display", "tell", "give", "see", "nima", "qanday", "kakie", "chto", "what", "which")
FIND_PRE = ("qidir", "izla", "top", "nayd", "nayt", "poish", "poisk", "find", "search", "lookup")
DONE_PRE = ("bajarildi", "bajarilgan", "tugadi", "tugatildi", "tugallan", "yakunlan", "vipoln", "vypoln", "zaversh", "gotov", "complet", "done", "finished")
MARK_PRE = ("belgila", "otmet", "mark", "tick", "check")
SELF_DONE_PRE = ("tugatdim", "bajardim", "yakunladim", "zakonchil", "sdelal", "vypolnil", "vipolnil", "finished", "completed", "done", "did", "tugat", "bajar")
ENGLISH_PRE = ("ingliz", "english", "angliy", "inglish")
STUDY_WORD_PRE = ("study", "oquv", "organ", "dars", "mashg", "zanyat", "urok", "izuchen", "obuch", "lesson", "learning")
PLAN_PRE = ("reja", "plan", "schedule", "jadval", "raspisan")
PROGRESS_PRE = ("progress", "streak", "statistik", "natija", "taraqqiyot", "seriya", "uspeh", "serii", "serija")
ACTIVITY = {"vocabulary": ("lugat", "vocab", "slovar", "leksik", "slov", "soz"), "grammar": ("grammat",), "listening": ("tingla", "listen", "audir", "auditsi"),
            "reading": ("oqish", "read", "chten", "chita"), "writing": ("writ", "pism", "yozish", "takror", "review", "povtor")}
HIGH_PRE, LOW_PRE = ("muhim", "yuqori", "high", "urgent", "srochn", "vajn", "vazhn", "important"), ("past", "low", "nizk", "unimportant")
FILLER = {"me", "menga", "mne", "to", "that", "ki", "deb", "chto", "about", "uchun", "haqida", "please", "iltimos", "pozhaluysta", "a", "the", "o", "pro", "my", "mening", "moi", "moy", "moya",
          "ni", "ga", "da", "va", "and", "i", "need", "want", "can", "you", "could", "set", "kerak", "bir", "yangi", "new", "create", "add", "make", "write", "save", "take", "as", "is", "are",
          "qoy", "qosh", "yarat", "tuz", "yoz", "saqla", "postav", "sozdaj", "dobav", "zapishi", "napishi", "for", "on", "at", "in", "of", "mazmuni", "matni", "text", "priority", "ustuvorlik",
          "called", "named", "titled", "nomli", "nomi", "nomini", "nazvaniem", "imenem", "nazvannuyu",
          "by", "until", "before", "due", "till", "gacha", "muddati", "srok", "this", "bu", "shu", "eto", "etu", "eta", "next", "keyingi", "kelasi", "is", "be", "s", "so"}
GREET = {"pyatnitsa", "friday", "hey", "salom", "privet", "hello", "hi", "ok"}
SCOPE_WORDS = {"overdue": ("kechik", "overdue", "prosroch"), "today": ("bugun", "today", "segodn"), "week": ("hafta", "week", "nedel"),
               "upcoming": ("yaqin", "upcoming", "blijay", "bliz", "kelgusi"), "done": ("bajarilgan", "completed", "vypoln", "vipoln"), "all": ("barcha", "hamma", "all", "vse", "butun")}
NAME_MARKERS = {"called", "named", "titled", "nomli", "nomi", "nomini", "nazvaniem", "imenem", "nazvannuyu"}


def _norm_words(text: str) -> tuple[list[str], list[str]]:
    raw = re.findall(r"\S+", text)
    return raw, [normalize(w).replace(" ", "") for w in raw]


def _sw(t: str, pre: tuple[str, ...]) -> bool:
    return t.startswith(pre)


def _is_task_noun(t: str) -> bool:
    return _sw(t, TASK_NOUN_PRE) or t in TASK_NOUN_EX


def _is_note_noun(t: str) -> bool:
    return _sw(t, NOTE_NOUN_PRE) or t in NOTE_NOUN_EX


def _is_rem_verb(t: str) -> bool:
    return _sw(t, REM_VERB_PRE) and not _sw(t, ("reminder", "eslatma"))


def _scope(nw: list[str], default: str) -> str:
    for name in ("overdue", "today", "week", "done", "upcoming", "all"):
        if any(_sw(t, SCOPE_WORDS[name]) for t in nw):
            return name
    return default


def _is_trigger(t: str) -> bool:
    return (_sw(t, REM_VERB_PRE + REM_NOUN_PRE + TASK_NOUN_PRE + NOTE_NOUN_PRE + MARK_PRE + DONE_PRE + ADD_PRE) or t in TASK_NOUN_EX or t in NOTE_NOUN_EX)


def _danger(words: list[str], full_text: str, strict: bool = False):
    """(xavfli_fe'l_bormi, til, tillar). Xavf BUYRUQ so'zlarida tekshiriladi (sarlavha/matn — ma'lumot) VA eslatma/vazifa/qayd buyrug'i yo'q
    boshqa bo'lakda («... va faylni o'chir»). `strict` — matn ichida ham tekshiriladi (masalan «bajarildi deb belgila ... o'chir»)."""
    from .router import detect_language
    _c, _l, found = nlu.analyze(full_text)
    lang = detect_language(full_text)
    clauses, _l2, _f2 = nlu.analyze(" ".join(words) or full_text)
    bad = any(cl.has("DANGER") for cl in clauses)
    if not bad:
        whole, _l3, _f3 = nlu.analyze(full_text)
        for cl in whole:
            if cl.has("DANGER") and (strict or not any(_is_trigger(normalize(t.raw).replace(" ", "")) for t in cl.toks)):
                bad = True
    return bad, lang, sorted(set(found) | {lang})


def _blocked(lang: str, found) -> ParseResult:
    return ParseResult("blocked", message=T("blocked", lang), lang=lang, langs=found, confidence=1.0)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def _strip(s: str) -> str:
    return re.sub(r"^(?:that|to|ki|deb|chto)\s+", "", s.strip(" :;,.-–—\"'«»"), flags=re.I).strip()


def parse(text: str, now: datetime | None = None, prior: ParseResult | None = None) -> ParseResult | None:
    now = now or datetime.now()
    raw_text = (text or "").strip()[:600]
    if not raw_text:
        return None
    raw, nw = _norm_words(raw_text)
    if any(t.startswith(("google", "gugl", "youtube", "yutub")) for t in nw):
        return None
    if any(_is_rem_verb(t) for t in nw):
        return _reminder_add(raw_text, raw, nw, now)
    for fn in (_study, _task, _note, _reminder_noun):
        r = fn(raw_text, raw, nw, now)
        if r is not None:
            return r
    return None


# ================================================================ ESLATMA
def _reminder_add(raw_text, raw, nw, now) -> ParseResult | None:
    w = parse_when(raw_text, now)
    verbs = {i for i, t in enumerate(nw) if _is_rem_verb(t)}
    nouns = {i for i, t in enumerate(nw) if _sw(t, REM_NOUN_PRE)}
    addv = {i for i, t in enumerate(nw) if _sw(t, ADD_PRE)}
    trigger = verbs | nouns | addv | w.consumed
    bad, lang, found = _danger([raw[i] for i in sorted(trigger)], raw_text)
    if bad:
        return _blocked(lang, found)
    title_words = [raw[i] for i in range(len(raw)) if i not in trigger and nw[i] not in FILLER and nw[i] not in GREET]
    title = _strip(" ".join(title_words))
    if not title:
        return ParseResult("clarify", message=T("rem.ask_title", lang), lang=lang, langs=found, draft=raw_text, confidence=0.7)
    if w.ask:
        key = {"time": "rem.ask_time", "ampm": "rem.ask_ampm", "past": "rem.ask_past", "date": "rem.ask_date"}[w.ask]
        msg = T(key, lang, h=w.hour if w.hour is not None else "", when=_fmt(w.due) if w.due else "")
        return ParseResult("clarify", message=msg, lang=lang, langs=found, draft=raw_text, confidence=0.7)
    when_txt = _fmt(w.due) + ("" if not w.recur else f" · {describe_recur(w.recur, lang)}")
    cmd = Command("reminder_add", {"title": title[:200], "due": w.due.strftime("%Y-%m-%dT%H:%M"), "recur": w.recur},
                  T("rem.ask.add", lang, title=title[:80], when=when_txt), intent="add_reminder")
    return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)


def _reminder_noun(raw_text, raw, nw, now) -> ParseResult | None:
    nouns = [i for i, t in enumerate(nw) if _sw(t, REM_NOUN_PRE)]
    if not nouns:
        return None
    w = parse_when(raw_text, now)
    has_time = bool(w.due or w.ask in ("ampm", "past", "date") or w.recur)
    addv = any(_sw(t, ADD_PRE) for t in nw)
    showv = any(_sw(t, SHOW_PRE + FIND_PRE) for t in nw)
    if addv or (has_time and not showv) or ":" in raw_text:
        return _reminder_add(raw_text, raw, nw, now)
    bad, lang, found = _danger(raw, raw_text)
    if bad:
        return _blocked(lang, found)
    scope = _scope(nw, "all")
    scope = scope if scope in ("all", "today", "overdue", "upcoming") else "all"
    cmd = Command("reminders_show", {"scope": scope}, T("rem.ask.show", lang, scope=T(f"rem.scope.{scope}", lang)), intent="show_reminders", needs_confirm=False)
    return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)


# ================================================================ VAZIFA
def _task(raw_text, raw, nw, now) -> ParseResult | None:
    nouns = {i for i, t in enumerate(nw) if _is_task_noun(t)}
    done_w = {i for i, t in enumerate(nw) if _sw(t, DONE_PRE)}
    mark_w = {i for i, t in enumerate(nw) if _sw(t, MARK_PRE)}
    addv = {i for i, t in enumerate(nw) if _sw(t, ADD_PRE)}
    showv = {i for i, t in enumerate(nw) if _sw(t, SHOW_PRE + FIND_PRE)}
    if any(_sw(t, ENGLISH_PRE) for t in nw) and any(_sw(t, PLAN_PRE) for t in nw):
        return None                                                      # o'quv rejasi — _study hal qiladi
    # ---- bajarildi deb belgilash: «Mark my English homework as completed»
    if done_w and (mark_w or nouns) and not (addv and nouns):
        cmdw = nouns | done_w | mark_w
        bad, lang, found = _danger([raw[i] for i in sorted(cmdw)], raw_text, strict=True)
        if bad:
            return _blocked(lang, found)
        q = " ".join(raw[i] for i in range(len(raw)) if i not in cmdw and nw[i] not in FILLER and nw[i] not in GREET).strip(" :;,.-")
        if not q:
            return ParseResult("clarify", message=T("task.ask_which", lang), lang=lang, langs=found, draft=raw_text, confidence=0.7)
        cmd = Command("task_complete", {"query": q[:120]}, T("task.ask.complete", lang, q=q[:60]), intent="complete_task")
        return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)
    if not nouns:
        return None
    # ---- qo'shish
    if addv or ":" in raw_text and not (showv and not addv):
        w = parse_when(raw_text, now)
        if w.ask in ("ampm", "past", "date") and (w.hour is not None or w.ask != "ampm"):
            bad, lang, found = _danger([raw[i] for i in sorted(nouns | addv | w.consumed)], raw_text)
            if bad:
                return _blocked(lang, found)
            key = {"ampm": "rem.ask_ampm", "past": "rem.ask_past", "date": "rem.ask_date"}[w.ask]
            return ParseResult("clarify", message=T(key, lang, h=w.hour if w.hour is not None else "", when=_fmt(w.due) if w.due else ""), lang=lang, langs=found, draft=raw_text, confidence=0.7)
        pri = "high" if any(_sw(t, HIGH_PRE) for t in nw) else "low" if any(_sw(t, LOW_PRE) for t in nw) else "medium"
        pri_idx = {i for i, t in enumerate(nw) if _sw(t, HIGH_PRE + LOW_PRE)}
        trigger = nouns | addv | w.consumed | pri_idx
        bad, lang, found = _danger([raw[i] for i in sorted(trigger)], raw_text)
        if bad:
            return _blocked(lang, found)
        colon = raw_text.find(":")
        title = _strip(raw_text[colon + 1:]) if colon >= 0 else _strip(" ".join(raw[i] for i in range(len(raw)) if i not in trigger and nw[i] not in FILLER and nw[i] not in GREET))
        if not title:
            return ParseResult("clarify", message=T("task.ask_title", lang), lang=lang, langs=found, draft=raw_text, confidence=0.7)
        due = w.due.strftime("%Y-%m-%dT%H:%M") if w.due else (w.day.strftime("%Y-%m-%d") if w.day else "")
        extra = f" · {due.replace('T', ' ')}" if due else ""
        cmd = Command("task_add", {"title": title[:200], "due": due, "priority": pri}, T("task.ask.add", lang, title=title[:80], extra=extra), intent="add_task")
        return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)
    # ---- ko'rsatish
    bad, lang, found = _danger(raw, raw_text)
    if bad:
        return _blocked(lang, found)
    scope = _scope(nw, "active")
    skip = FILLER | GREET
    q = " ".join(raw[i] for i in range(len(raw)) if i not in nouns and nw[i] not in skip and not _sw(nw[i], SHOW_PRE + FIND_PRE) and not any(_sw(nw[i], p) for p in SCOPE_WORDS.values())).strip(" :;,.-")
    cmd = Command("tasks_show", {"scope": scope, "query": q[:80]}, T("task.ask.show", lang, scope=T(f"task.scope.{scope}", lang)), intent="show_tasks", needs_confirm=False)
    return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)


# ================================================================ QAYD
def _note(raw_text, raw, nw, now) -> ParseResult | None:
    nouns = [i for i, t in enumerate(nw) if _is_note_noun(t)]
    if not nouns:
        return None
    colon = raw_text.find(":")
    head_text = raw_text[:colon] if colon >= 0 else raw_text
    hraw, hnw = _norm_words(head_text)
    marker = next((i for i, t in enumerate(hnw) if t in NAME_MARKERS), None)
    adding = any(_sw(t, ADD_PRE) for t in hnw) or (colon >= 0 and all(_is_note_noun(t) or t in FILLER or t in GREET for t in hnw))   # «note: buy milk»
    searching = any(_sw(t, FIND_PRE) for t in hnw)
    showing = any(_sw(t, SHOW_PRE) for t in hnw)
    if adding and not searching:
        head_cmd = [hraw[i] for i in range(len(hraw)) if marker is None or i <= marker]
        bad, lang, found = _danger(head_cmd, raw_text)
        if bad:
            return _blocked(lang, found)
        if marker is not None:                                              # «Create a note called English Vocabulary» — nom, matn bo'sh yoki ":" dan keyin
            title = _strip(" ".join(hraw[marker + 1:]))
            body = _strip(raw_text[colon + 1:]) if colon >= 0 else ""
            if not title:
                return ParseResult("clarify", message=T("note.ask_title", lang), lang=lang, langs=found, draft=raw_text, confidence=0.7)
            cmd = Command("note_add", {"title": title[:120], "body": body[:5000]}, T("note.ask.named", lang, title=title[:80]), intent="add_note")
            return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)
        if colon >= 0:
            body = raw_text[colon + 1:].strip()
        else:
            body = " ".join(raw[i] for i in range(len(raw)) if nw[i] not in FILLER and not _is_note_noun(nw[i]) and not _sw(nw[i], ADD_PRE + SHOW_PRE) and nw[i] not in GREET).strip(" :;,.-")
        if not body:
            return ParseResult("clarify", message=T("note.ask_body", lang), lang=lang, langs=found, draft=raw_text, confidence=0.7)
        title = " ".join(body.split()[:6])[:60]
        cmd = Command("note_add", {"title": title, "body": body[:5000]}, T("note.ask.add", lang, title=title), intent="add_note")
        return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.9)
    if searching or showing or not adding:
        bad, lang, found = _danger(raw, raw_text)
        if bad:
            return _blocked(lang, found)
        skip = FILLER | {"haqida", "about", "pro", "boyicha", "bilan", "with", "containing"} | GREET
        q = " ".join(raw[i] for i in range(len(raw)) if nw[i] not in skip and not _is_note_noun(nw[i]) and not _sw(nw[i], FIND_PRE + SHOW_PRE)).strip(" :;,.-")
        cmd = Command("notes_show", {"query": q[:100]}, T("note.ask.show", lang, q=q or T("note.all", lang)), intent="show_notes", needs_confirm=False)
        return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.85)
    return None


# ================================================================ INGLIZ TILI REJASI
def _study(raw_text, raw, nw, now) -> ParseResult | None:
    english = any(_sw(t, ENGLISH_PRE) for t in nw)
    plan = any(_sw(t, PLAN_PRE) for t in nw)
    studyctx = english or any(_sw(t, STUDY_WORD_PRE) for t in nw)
    act = next((a for a, pre in ACTIVITY.items() if any(_sw(t, pre) for t in nw)), None)
    done_self = any(_sw(t, SELF_DONE_PRE) or _sw(t, DONE_PRE) for t in nw)
    progress = any(_sw(t, PROGRESS_PRE) for t in nw)
    if any(_is_task_noun(t) or _is_note_noun(t) for t in nw):
        return None
    cmd = None
    if progress and studyctx:
        bad, lang, found = _danger(raw, raw_text)
        cmd = Command("study_progress", {}, T("study.ask.progress", "uz"), intent="study_progress", needs_confirm=False)
    elif act and done_self and (studyctx or len(nw) <= 6):
        bad, lang, found = _danger(raw, raw_text)
        cmd = Command("study_done", {"activity": act}, "", intent="study_done")
    elif plan and studyctx and (english or any(_sw(t, STUDY_WORD_PRE) for t in nw)):
        bad, lang, found = _danger(raw, raw_text)
        cmd = Command("study_show", {}, T("study.ask.show", "uz"), intent="study_plan", needs_confirm=False)
    if cmd is None:
        return None
    if bad:
        return _blocked(lang, found)
    if cmd.action == "study_progress":
        cmd.confirm_text = T("study.ask.progress", lang)
    elif cmd.action == "study_show":
        cmd.confirm_text = T("study.ask.show", lang)
    else:
        cmd.confirm_text = T("study.ask.done", lang, name=act.capitalize(), mins="")
    return ParseResult("ok", command=cmd, commands=[cmd], lang=lang, langs=found, confidence=0.88)
