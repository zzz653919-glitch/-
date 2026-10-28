"""Holat mashinasi:  STANDBY → LISTENING → PROCESSING (audio → matn) → INTERPRETING (matn → amal) → (CONFIRM) → EXECUTING → RESPONDING/ERROR.

Ovozli va matnli buyruqlar BIR XIL `_handle_text` yo'lidan o'tadi: tushunish (nlu), rad etish/aniqlashtirish, ruxsat tekshiruvi,
tasdiq, ijro. Mikrofon faqat toggle_listening() bilan ochiladi; buyruqlar faqat ilova oynasi faol bo'lganda qabul qilinadi.
Nutqni tanish va tahlil fon oqimida bajariladi (GUI qotmaydi).
"""
from __future__ import annotations

import logging
import threading
import time

from PySide6.QtCore import QObject, QTimer, Signal

from . import ai_chat, audio, commands, desktop, english, fileintent, files as fs, router, stt
from .ai_chat import AIError
from .audio import VoiceError
from .executor import Executor, Result
from .i18n import T, has
from .settings import Settings

log = logging.getLogger("pyatnitsa.voice")

IDLE, LISTENING, CHECKING, INTERPRETING, CONFIRM, RUNNING, DONE = "idle", "listening", "checking", "interpreting", "confirm", "running", "done"
THINKING, STREAMING = "thinking", "streaming"
LABELS = {IDLE: "Kutmoqda", LISTENING: "Tinglayapti", CHECKING: "Nutq matnga aylantirilmoqda", INTERPRETING: "Buyruq tahlil qilinmoqda",
          CONFIRM: "Tasdiq kutilmoqda", RUNNING: "Bajarilmoqda", DONE: "Tayyor",
          THINKING: "AI o'ylamoqda", STREAMING: "AI javob bermoqda"}
_OPEN_ACTIONS = {"open_app", "new_window", "search", "time", "admin_info", "open_file", "reminder_add", "reminders_show", "note_add", "notes_show", "task_add", "tasks_show",
                 "task_complete", "study_show", "study_done", "study_progress", "media",
                 "window", "screenshot", "clipboard", "ui", "youtube_search", "open_site", "english"}   # natijaning o'zi xabar — alohida «tekshiryapman» kerak emas
_REAL_FAILURES = ("mic.", "stt.network", "stt.failed", "stt.lib_missing", "stt.whisper")   # bular ERROR holati; qolganlari («nutq yo'q» va h.k.) oddiy javob

INTENT_NAMES = {"open_app": "OPEN_APPLICATION", "open_folder": "OPEN_FOLDER", "web_search": "WEB_SEARCH",
                "get_exchange_rate": "GET_EXCHANGE_RATE", "get_pc_health": "GET_PC_HEALTH", "get_system_info": "GET_SYSTEM_INFO",
                "get_weather": "GET_WEATHER", "find_file": "FIND_FILE", "open_file": "OPEN_FILE", "list_files": "LIST_FILES",
                "add_reminder": "ADD_REMINDER", "show_reminders": "SHOW_REMINDERS", "add_task": "ADD_TASK", "show_tasks": "SHOW_TASKS", "complete_task": "COMPLETE_TASK",
                "add_note": "ADD_NOTE", "show_notes": "SHOW_NOTES", "study_plan": "STUDY_PLAN", "study_done": "STUDY_DONE", "study_progress": "STUDY_PROGRESS", "media_control": "MEDIA_CONTROL",
                "window_control": "WINDOW_CONTROL", "screenshot": "TAKE_SCREENSHOT", "clipboard": "CLIPBOARD", "ui_control": "UI_CONTROL", "open_site": "OPEN_WEBSITE",
                "net_check": "CHECK_INTERNET", "english": "ENGLISH_LEARNING"}


def _ack_key(action: str) -> str | None:
    if action in _OPEN_ACTIONS:
        return None
    if action in commands.FILE_ACTIONS:
        return "ack.files"
    return {"rate_usd": "ack.rate_usd", "convert_usd": "ack.convert_usd", "weather": "ack.weather"}.get(action, "ack.health")


def as_candidates(heard) -> list[stt.Heard]:
    """Dvigatel natijasini (str | Outcome | list) Heard ro'yxatiga keltiradi."""
    if isinstance(heard, str):
        return [stt.Heard(heard, "auto", None)]
    if isinstance(heard, stt.Outcome):
        return list(heard.candidates)
    return list(heard)


class Controller(QObject):
    stateChanged = Signal(str, str)        # kalit, nomi
    message = Signal(str, str)             # rol: user | assistant | system, matn
    level = Signal(float)
    confirmChanged = Signal(bool, str)     # kerakmi, savol matni
    log = Signal(str, str)                 # daraja (info|active|success|warn|error), "[TEG] matn" — faqat HAQIQIY hodisalar
    record = Signal(dict)                  # tugallangan buyruq yozuvi (tarix sahifasi uchun)
    aiStream = Signal(str, str)            # thinking_on | thinking_off | start | delta | end | stopped | error  (+ matn)
    retryChanged = Signal(bool)
    dataChanged = Signal(str)                  # "reminders" | "tasks" | "notes" | "study" — sahifalar ro'yxatni yangilaydi
    navigate = Signal(str)                     # natija sahifa ochishni so'raydi (masalan "study")
    reminderFired = Signal(object)             # vaqti kelgan eslatma (Reminder) — oyna bildirishnoma ko'rsatadi
    fileAccessNeeded = Signal(str, str, str)   # no_roots | scope_denied, papka (bo'lishi mumkin), qayta yuboriladigan matn — oyna ruxsat so'raydi
    _ai_first = Signal(int)
    _ai_delta = Signal(int, str)
    _ai_done = Signal(int, object)
    _ai_err = Signal(int, object)
    _voice_done = Signal(object, object, object, object)   # matn, ParseResult, tanlangan Heard, xato
    _stage = Signal(str)
    _executed = Signal(object)
    _level_in = Signal(float)
    _endpoint = Signal()

    def __init__(self, settings: Settings, executor: Executor, speaker, recorder_factory=None, transcribe=None, post_roll_ms: int = 250, ai=None):
        super().__init__()
        self.settings, self.executor, self.speaker, self.ai = settings, executor, speaker, ai
        self._recorder_factory = recorder_factory or self._default_recorder
        self._transcribe = transcribe or (lambda rec, lang: stt.recognize(rec, self.settings))
        self.post_roll_ms = post_roll_ms
        self.state = IDLE
        self.lang = "uz"                    # oxirgi buyruq tili (javob tili)
        self.last_ok = True                 # oxirgi javob muvaffaqiyatlimi (yadro ERROR holati uchun)
        self.is_active = lambda: True      # ilova oynasi ochiq va faolmi (UI o'rnatadi)
        self._recorder = None
        self._stopping = False
        self._warned: set[str] = set()
        self._held, self._hold_t0 = False, 0.0           # Space bosib turilgan (hold-to-talk)
        self._closed = False
        self._t0 = 0.0
        self._ai_rid = 0
        self._ai_parts: list[str] = []
        self._ai_streaming = False
        self._retry: tuple | None = None
        self._last_recording = None
        self._pending: list[commands.Command] = []
        self._awaiting: list[commands.Command] = []   # tasdiq savoli berilgan; javob (ha/yo'q) KEYINGI ovozli gapda kutilmoqda
        self._lesson = None                           # faol ingliz tili mashqi (viktorina / talaffuz / tinglash)
        self._stt_lang = ""                           # mashq vaqtida nutqni tanish tili (masalan en-US talaffuz uchun)
        self._draft = ""                              # aniqlashtirish kutilmoqda: keyingi javob shu matnga qo'shiladi
        self._draft_tries = 0
        self._rem_timer = QTimer(self, interval=15000)
        self._rem_timer.timeout.connect(self.check_reminders)
        self._choices: list[fs.FileEntry] = []        # oxirgi fayl ro'yxati: «2», «birinchisini och», «ochib ber» shundan tanlaydi
        self._cur: dict | None = None
        self._limit = QTimer(self, singleShot=True, interval=audio.MAX_SECONDS * 1000)
        self._limit.timeout.connect(self._auto_stop)
        self._idle = QTimer(self, singleShot=True, interval=2000)
        self._idle.timeout.connect(self._idle_tick)
        self._voice_done.connect(self._on_voice_done)
        self._ai_first.connect(self._on_ai_first)
        self._ai_delta.connect(self._on_ai_delta)
        self._ai_done.connect(self._on_ai_done)
        self._ai_err.connect(self._on_ai_error)
        self._stage.connect(self._on_stage)
        self._executed.connect(self._on_executed)
        self._level_in.connect(self.level)
        self._endpoint.connect(self._on_endpoint)

    def _default_recorder(self):
        det = audio.EndpointDetector() if self.settings.auto_stop_silence else None
        return audio.Recorder(self.settings.microphone, det)

    # ------------------------------------------------------------ holat
    def _set(self, state: str) -> None:
        self.state = state
        self.stateChanged.emit(state, LABELS[state])
        self.confirmChanged.emit(state == CONFIRM, self._ask_text() if self._pending else "")
        if state == DONE:
            self._idle.start(2000 if self.last_ok else 3500)

    def _idle_tick(self) -> None:
        if self.state != DONE:
            return
        if getattr(self.speaker, "speaking", False):      # javob hali aytilmoqda — RESPONDING davom etadi
            self._idle.start(400)
        else:
            self._set(IDLE)

    def core_state(self) -> str:
        """AI yadrosi uchun HAQIQIY holat."""
        s = self.state
        base = {LISTENING: "listening", CHECKING: "processing", INTERPRETING: "interpreting", CONFIRM: "confirm", RUNNING: "executing",
                THINKING: "thinking", STREAMING: "responding"}
        if s in base:
            return base[s]
        if s == DONE:
            if not self.last_ok:
                return "error"
            return "speaking" if getattr(self.speaker, "speaking", False) else "responding"
        return "standby"

    def log_event(self, level: str, tag: str, text: str) -> None:
        log.info("[%s] %s", tag, text)
        self.log.emit(level, f"[{tag}] {text}")

    def _finish_record(self, outcome: str, summary: str = "") -> None:
        if self._cur is not None:
            self._cur.update(outcome=outcome, summary=summary[:300])
            self.record.emit(self._cur)
            self._cur = None

    def _ask_text(self) -> str:
        asks = [c.confirm_text for c in self._pending]
        if len(asks) == 1:
            return asks[0] + "?"
        return T("plan", self.lang, n=len(asks), items="; ".join(f"{i}) {a}" for i, a in enumerate(asks, 1))) + "?"

    def _reply(self, text: str, ok: bool = True, spoken: str | None = None) -> None:
        self.last_ok = ok
        self.message.emit("assistant", text)
        self.speaker.say(spoken or text, self.lang)
        self._set(DONE)

    @property
    def busy(self) -> bool:
        return self.state in (CHECKING, INTERPRETING, RUNNING)

    @property
    def ai_busy(self) -> bool:
        return self.state in (THINKING, STREAMING)

    def can_retry(self) -> bool:
        return self._retry is not None and not self.busy and not self.ai_busy and self.state != LISTENING

    # ------------------------------------------------------------ xato matnlari
    def error_text(self, err: BaseException) -> str:
        if isinstance(err, VoiceError) and has(err.key):
            return T(err.key, self.lang, detail=(err.detail or "")[:160])
        return str(err)

    # ------------------------------------------------------------ mikrofon
    def _guard(self) -> bool:
        """Buyruqlar faqat ilova oynasi ochiq va faol bo'lgandagina qabul qilinadi/bajariladi."""
        if self.is_active():
            return True
        self.message.emit("system", T("inactive", self.lang))
        return False

    def toggle_listening(self) -> None:
        if self.state == LISTENING:
            if not self._stopping:
                self._begin_stop()
        elif self.ai_busy and self._guard():           # AI gapirayotganda Space: javobni to'xtatib, tinglashni boshlaydi
            self.cancel_ai()
            self._start_listening()
        elif not self.busy and not self._stopping and self._guard():
            if self.state == CONFIRM:                    # tasdiq savoliga OVOZ bilan javob berish: kutilayotgan amal saqlanadi, bekor qilinmaydi
                self._awaiting, self._pending = list(self._pending), []
            self._start_listening()

    HOLD_MIN_S = 0.35            # shundan uzoq bosib turilsa — hold-to-talk; qisqa bosish — avvalgidek yoqish/o'chirish

    def space_pressed(self) -> None:
        """Space (yoki mikrofon tugmasi) BOSILDI. Tinglash boshlanadi; qo'yib yuborilganda to'xtashi uchun bosilganlik eslab qolinadi."""
        was_listening = self.state == LISTENING
        self.toggle_listening()
        self._held = self.state == LISTENING and not was_listening
        self._hold_t0 = time.monotonic()

    def space_released(self, force: bool = False) -> None:
        """Space QO'YIB YUBORILDI: bosib turilgan bo'lsa yozuv to'xtaydi va gap qayta ishlanadi. Qisqa bosish (<HOLD_MIN_S)
        tinglashni davom ettiradi (ikkinchi bosish to'xtatadi). `force` — oyna faolligini yo'qotganda (qo'yib yuborish hodisasi kelmaydi)."""
        if not self._held:
            return
        self._held = False
        if self.state == LISTENING and not self._stopping and (force or time.monotonic() - self._hold_t0 >= self.HOLD_MIN_S):
            self._begin_stop()

    def _warn_device(self, rec) -> None:
        """Windows standart kirishi (yoki tanlangan qurilma) Stereo Mix / loopback bo'lsa — jim emas, aniq xabar (har turi bir marta)."""
        key = getattr(rec, "warning", "")
        if key in ("default_loopback", "selected_loopback") and key not in self._warned:
            self._warned.add(key)
            using = getattr(rec, "device", "")
            name = self.settings.microphone if key == "selected_loopback" else audio.default_input_name()
            self.message.emit("system", T(f"mic.warn.{key}", self.lang, name=name or "?", using=using))
            self.log_event("warn", "VOICE", f"Input device warning: {key} ({name}); using '{using}'")

    def _start_listening(self) -> None:
        self.speaker.stop()
        try:
            rec = self._recorder_factory()
            rec.on_level = self._level_in.emit
            if hasattr(rec, "on_endpoint"):
                rec.on_endpoint = self._endpoint.emit
            rec.start()                       # ochilmaguncha LISTENING ko'rsatilmaydi
        except VoiceError as e:
            self._start_failed(e.key, self.error_text(e), str(e))
            return
        except Exception as e:  # noqa: BLE001
            log.exception("Mikrofon xatosi")
            self._start_failed("mic.open_failed", T("mic.open_failed", self.lang, detail=str(e)[:160]), str(e))
            return
        self._recorder = rec
        self._warn_device(rec)
        self._t0 = time.monotonic()
        self._limit.start()
        self.last_ok = True
        dev = getattr(rec, "device", "") or "default device"
        self.log_event("info", "VOICE", f"Listening activated (microphone: {dev}, {getattr(rec, 'rate', '?')} Hz)")
        self._set(LISTENING)

    def _drop_awaiting(self, why: str = "Confirmation was not received") -> None:
        if self._awaiting:
            self._awaiting = []
            self.log_event("info", "SYSTEM", why + "; nothing was executed")
            self._finish_record("cancelled", why)

    def _start_failed(self, key: str, text: str, raw: str) -> None:
        self._drop_awaiting("Microphone could not be started")
        self.log_event("error", "ERROR", f"Microphone unavailable: {raw[:200]}")
        self.message.emit("system", text)
        self.last_ok = False
        self._set(DONE)

    def _begin_stop(self) -> None:
        """Space qayta bosildi: oxirgi bo'g'in kesilmasligi uchun qisqa «post-roll» dan keyin to'xtatiladi (hali LISTENING)."""
        self._stopping = True
        if self.post_roll_ms > 0:
            QTimer.singleShot(self.post_roll_ms, self._stop_listening)
        else:
            self._stop_listening()

    def _on_endpoint(self) -> None:
        if self.state == LISTENING and not self._stopping and not self._held:      # Space bosib turilganda to'xtatuvchi — faqat qo'yib yuborish
            self.log_event("info", "VOICE", "End of speech detected (silence); stopping automatically")
            self._stop_listening_now()

    def _auto_stop(self) -> None:
        if self.state == LISTENING:
            self.message.emit("system", f"{audio.MAX_SECONDS} soniya o'tdi, tinglash avtomatik to'xtatildi.")
            self._stop_listening_now()

    def _stop_listening_now(self) -> None:
        self._stopping = True
        self._stop_listening()

    def _stop_listening(self) -> None:
        self._stopping = False
        self._held = False
        if self.state != LISTENING or self._recorder is None:
            return
        self._limit.stop()
        rec, self._recorder = self._recorder, None
        self.level.emit(0.0)
        try:
            recording = rec.stop()               # mikrofon BU YERDA bo'shatiladi — audio xotirada qoladi
        except Exception as e:  # noqa: BLE001
            log.exception("Yozuvni to'xtatishda xato")
            self.log_event("error", "ERROR", f"Could not stop recording: {e}")
            self.message.emit("system", self.error_text(e) if isinstance(e, VoiceError) else f"Mikrofonni to'xtatishda xato: {e}")
            self.last_ok = False
            self._set(DONE)
            return
        secs = getattr(recording, "seconds", 0.0)
        self.log_event("info", "VOICE", f"Listening stopped ({secs:.1f}s recorded); converting speech to text")
        self._last_recording = recording            # faqat xotirada; muvaffaqiyatsiz bo'lsa «Retry» uchun
        self._run_stt(recording)

    def _run_stt(self, recording) -> None:
        self._set(CHECKING)
        lang = self._stt_lang or self.settings.stt_language
        engine = self.settings.stt_engine

        def work():
            try:
                out = self._transcribe(recording, lang)
                if self._closed:
                    return
                self._stage.emit("interpreting")             # nutq matnga aylandi; endi tahlil
                cands = as_candidates(out)
                chosen = self.pick_candidate(cands)
                res = commands.parse(chosen.text)
                if not self._closed:
                    self._voice_done.emit(chosen.text, res, chosen, None)
            except Exception as e:  # noqa: BLE001
                if not isinstance(e, VoiceError):
                    log.exception("Ovoz oqimi xatosi")
                if not self._closed:
                    self._voice_done.emit(None, None, None, e)

        threading.Thread(target=work, name=f"stt-{engine}", daemon=True).start()

    def _on_stage(self, stage: str) -> None:
        if stage == "interpreting" and self.state == CHECKING:
            self._set(INTERPRETING)

    @staticmethod
    def pick_candidate(cands: list[stt.Heard]) -> stt.Heard:
        """Nomzodlardan buyruq sifatida eng mazmunlisini tanlaydi (matn o'zgartirilmaydi)."""
        best, best_score = cands[0], -1.0
        for h in cands:
            r = commands.parse(h.text)
            base = {"ok": r.confidence, "blocked": 0.95, "clarify": r.confidence * 0.5}.get(r.kind, 0.0)
            score = base + 0.2 * (h.conf if h.conf is not None else 0.5)
            if score > best_score:
                best, best_score = h, score
        return best

    @staticmethod
    def choose_transcript(heard) -> str:
        return Controller.pick_candidate(as_candidates(heard)).text

    def _on_voice_done(self, text, res, chosen, err) -> None:
        if err is not None:
            self._voice_failed(err)
            return
        self.log_event("info", "VOICE", f"Speech recognized: {text}")
        self._last_recording = None
        self._set_retry(None)
        if chosen is not None and chosen.conf is not None and chosen.conf < audio.MIN_CONFIDENCE and res.kind != "blocked":
            self._drop_awaiting("Speech was unclear")
            self.message.emit("user", text)               # nima eshitilgani ko'rinsin, lekin bajarilmaydi
            self.log_event("warn", "VOICE", f"Low recognition confidence ({chosen.conf:.2f}); asking the user to repeat")
            self._reply(T("voice.unclear", self.lang, text=text))
            self._cur = {"time": time.time(), "source": "voice", "text": text, "intents": [], "outcome": "", "summary": ""}
            self._finish_record("unknown", "Low confidence")
            return
        self._handle_text(text, "voice", res)

    def _set_retry(self, ctx: tuple | None) -> None:
        self._retry = ctx
        self.retryChanged.emit(ctx is not None)

    def _voice_failed(self, err: BaseException) -> None:
        self._drop_awaiting("Speech was not recognized")
        if self._last_recording is not None:
            self._set_retry(("stt",))                # xabar yo'qolmasin: o'sha yozuvni qayta tanish mumkin
        if isinstance(err, VoiceError):
            real = err.key.startswith(_REAL_FAILURES)
            self.log_event("error" if real else "warn", "ERROR" if real else "VOICE", f"{err.key}: {(err.detail or self.error_text(err))[:200]}")
            self._reply(self.error_text(err), ok=not real)
        else:
            self.log_event("error", "ERROR", f"Speech processing error: {type(err).__name__}: {err}")
            self._reply(T("stt.failed", self.lang, detail=f"{type(err).__name__}: {err}"[:160]), ok=False)

    # ------------------------------------------------------------ matn (ikkala manba uchun umumiy)
    def submit_typed(self, text: str) -> None:
        """Klaviaturadan kiritilgan matn (interfeysdan). «Faqat ovoz» rejimida buyruq sifatida QABUL QILINMAYDI."""
        if self.settings.voice_only:
            if text.strip():
                self.log_event("warn", "SECURITY", "Typed command rejected: voice-only mode is on")
                self.message.emit("system", T("voice_only", self.lang))
            return
        self.submit_text(text)

    def submit_text(self, text: str) -> None:
        text = text.strip()
        if not text or self.state == LISTENING or self.busy or self._stopping or not self._guard():
            return
        if self.ai_busy:
            self.message.emit("system", T("ai.busy", self.lang))
            return
        if self.state == CONFIRM:
            self.cancel(silent=True)
        self._handle_text(text, "text")

    def _handle_text(self, text: str, source: str, res: commands.ParseResult | None = None) -> None:
        self.last_ok = True
        self._set_retry(None)
        if self.state != INTERPRETING:           # ovozli oqimda allaqachon INTERPRETING
            self._set(INTERPRETING)
        self.message.emit("user", text)
        if self._awaiting:                            # ovozli tasdiq: «ha» bajaradi, «yo'q» bekor qiladi, boshqa gap — yangi buyruq (eskisi bekor)
            awaiting, self._awaiting = self._awaiting, []
            answer = commands.yes_no(text)
            if answer == "yes":
                self.log_event("info", "SYSTEM", "Confirmed by voice")
                self._pending = awaiting
                self._run(awaiting)
                return
            if answer == "no":
                self.log_event("info", "SYSTEM", "Cancelled by voice; nothing was executed")
                self._finish_record("cancelled", "Cancelled by voice")
                self._reply(T("cancelled", self.lang))
                return
            self._finish_record("cancelled", "Replaced by a new command")
        self._cur = {"time": time.time(), "source": source, "text": text, "intents": [], "outcome": "", "summary": ""}
        if source == "text":
            self.log_event("info", "TEXT", "Command received")
        if self._lesson is not None and self._lesson_turn(text, res):
            return
        if self._choices:                             # oxirgi fayl ro'yxatidan tanlash: «2», «birinchisini och», «bekor»
            ch = fileintent.parse_choice(text, len(self._choices))
            if ch is not None:
                self._handle_choice(ch)
                return
        res = self._continue_draft(text, res)
        route = router.route(text, res, has_history=bool(self.ai and len(self.ai.history)))
        self.log_event("info", "AI", f"Routed: {route.category} ({route.reason})")
        if route.to_ai:
            self._start_ai(text, route, res)
            return
        self.lang = res.lang
        if res.kind != "ok":
            tag, level, outcome = {"blocked": ("SECURITY", "warn", "blocked"), "clarify": ("AI", "info", "clarify")}.get(res.kind, ("AI", "info", "unknown"))
            what = {"blocked": "Command blocked (not allowed)", "clarify": "Clarification requested",
                    "unknown": "Recognized text, but no supported intent identified"}[outcome]
            self.log_event(level, tag, what)
            msg = T("heard_unknown", res.lang, text=text) if res.kind == "unknown" else res.message
            self._reply(msg)         # tushunarsiz / aniqlashtirish / xavfli: hech narsa bajarilmaydi
            self._finish_record(outcome, msg)
            return
        names = [INTENT_NAMES.get(c.intent, c.intent.upper()) for c in res.commands]
        self._cur["intents"] = names
        for c, n in zip(res.commands, names):
            params = ", ".join(f"{k}={v}" for k, v in c.args.items())
            self.log_event("info", "AI", f"Intent identified: {n}" + (f" ({params})" if params else "")
                           + f" · confidence {res.confidence:.2f} · lang {'+'.join(res.langs) or res.lang}")
        for c in res.commands:               # ruxsat tekshiruvi tasdiqdan oldin
            denied = self.executor.check_allowed(c, self.lang)
            if denied:
                self.log_event("warn", "SECURITY", "Action disabled in settings")
                self._reply(denied)
                self._finish_record("denied", denied)
                return
        for c in res.commands:               # fayl buyruqlari: ruxsat etilgan papka yo'q / nom kerak — qidirishdan oldin
            issue = self.executor.file_issue(c, self.lang)
            if issue:
                self.log_event("warn", "SECURITY", f"File access: {issue.kind}")
                self._reply(issue.message)
                self._finish_record("denied", issue.message)
                if issue.kind in ("no_roots", "scope_denied"):
                    self.fileAccessNeeded.emit(issue.kind, str(issue.hint or ""), text)
                return
        force = any(c.force_confirm for c in res.commands)
        if (self.settings.confirm_commands and any(c.needs_confirm for c in res.commands)) or force:
            self._pending = list(res.commands)
            self.message.emit("assistant", self._ask_text() + " " + T("confirm_hint", self.lang))
            self.log_event("active", "AI", f"Awaiting user confirmation ({len(res.commands)} action{'s' if len(res.commands) > 1 else ''})")
            self._set(CONFIRM)
        else:
            self._run(list(res.commands))

    def confirm(self) -> None:
        if self.state == CONFIRM and self._pending:
            if not self._guard():
                self.cancel(silent=True)
                return
            cmds, self._pending = self._pending, []
            self.log_event("info", "SYSTEM", "Confirmed by user")
            self._run(cmds)

    def cancel(self, silent: bool = False) -> None:
        if self.state == CONFIRM:
            self._pending = []
            self.log_event("info", "SYSTEM", "Cancelled by user; nothing was executed")
            self._finish_record("cancelled", "Cancelled by user")
            if silent:
                self._set(IDLE)
            else:
                self._reply(T("cancelled", self.lang))

    def _run(self, cmds: list[commands.Command]) -> None:
        self._set(RUNNING)
        lang = self.lang
        for c in cmds:
            self.log_event("active", "EXECUTION", c.confirm_text)
        for key in dict.fromkeys(k for k in (_ack_key(c.action) for c in cmds) if k):   # takrorsiz «tekshiryapman»
            self.message.emit("assistant", T(key, lang))

        def work():
            results: list[Result] = []
            for c in cmds:
                try:
                    results.append(self.executor.execute(c, lang))
                except Exception as e:  # noqa: BLE001
                    log.exception("Ijro xatosi")
                    results.append(Result(False, T("error", lang, err=e)))
            if not self._closed:
                self._executed.emit(results)

        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ AI suhbat (faqat MATN; undan hech narsa bajarilmaydi)
    def _ai_error_text(self, e: AIError, lang: str) -> str:
        wait = f" ({int(e.retry_after)} s)" if e.retry_after else ""
        return T(f"ai.err.{e.kind}", lang, detail=(e.detail or "")[:200], wait=wait)

    def _start_ai(self, text: str, route: router.Route, res: commands.ParseResult | None = None, show_user: bool = False) -> None:
        self.lang = route.lang
        ok, why = self.ai.available() if self.ai else (False, "disabled")
        if not ok:
            plain_unknown = not (why == "no_key" or (res is not None and res.kind != "unknown") or route.category == router.QUESTION_ANSWERING)
            if why == "no_key" or (res is not None and res.kind != "unknown") or route.category == router.QUESTION_ANSWERING:
                msg = T("ai.disabled" if why == "disabled" else "ai.err.no_key", route.lang)
            else:
                msg = T("heard_unknown", route.lang, text=text)
            self.log_event("warn", "AI", "AI chat unavailable: " + ("disabled in settings" if why == "disabled" else "no API key configured"))
            self._reply(msg, ok=(why == "disabled" or why == ""))
            self._finish_record("unknown" if plain_unknown else "ai_failed", msg)
            return
        if not self.settings.ai_notice_shown:
            self.settings.ai_notice_shown = True
            self.settings.save()
            self.message.emit("system", T("ai.notice", route.lang, provider="Anthropic"))
        self._ai_rid += 1
        rid = self._ai_rid
        self.ai.apply_settings()
        self.ai.history.add_user(text)
        self._ai_parts, self._ai_streaming = [], False
        self._ai_ctx = (text, route)
        system = ai_chat.build_system_prompt(route.lang, has_history=len(self.ai.history) > 1, live_unsupported=route.live_unsupported)
        msgs = self.ai.history.messages()
        self.log_event("active", "AI", f"Request sent to Anthropic · model {self.ai.client.model} · {len(msgs)} context message(s)")
        self.aiStream.emit("thinking_on", "")
        self._set(THINKING)

        def work():
            try:
                reply = self.ai.client.stream_reply(msgs, system, lambda t: self._ai_delta.emit(rid, t), lambda: self._ai_first.emit(rid))
                if not self._closed:
                    self._ai_done.emit(rid, reply)
            except Exception as e:  # noqa: BLE001
                if not self._closed:
                    self._ai_err.emit(rid, e if isinstance(e, AIError) else ai_chat.map_error(e))

        threading.Thread(target=work, name="ai-chat", daemon=True).start()

    def _on_ai_first(self, rid: int) -> None:
        if rid != self._ai_rid or self.state != THINKING:
            return
        self._ai_streaming = True
        self.aiStream.emit("thinking_off", "")
        self.aiStream.emit("start", "")
        self.log_event("info", "AI", "Response streaming")
        self._set(STREAMING)

    def _on_ai_delta(self, rid: int, chunk: str) -> None:
        if rid != self._ai_rid:
            return
        self._ai_parts.append(chunk)
        self.aiStream.emit("delta", chunk)

    def _on_ai_done(self, rid: int, reply: ai_chat.Reply) -> None:
        if rid != self._ai_rid:
            return
        text = reply.text
        if self._ai_streaming is False:
            self.aiStream.emit("thinking_off", "")
        if reply.cancelled:
            if text.strip():
                self.ai.history.add_assistant(text)
            else:
                self.ai.history.pop_last_user()
            self.aiStream.emit("stopped", text)
            self.log_event("info", "AI", "Generation stopped by the user")
            self._finish_record("cancelled", "Stopped by user")
            self.last_ok = True
            self._set(IDLE)
            return
        self.ai.history.add_assistant(text)
        if not self._ai_streaming:                     # oqim bo'lmagan (juda qisqa) javob
            self.aiStream.emit("start", "")
            self.aiStream.emit("delta", text)
        self.aiStream.emit("end", text)
        if reply.truncated:
            self.message.emit("system", T("ai.truncated", self.lang))
        self.log_event("success", "AI", f"Response complete · {len(text)} chars · {reply.seconds:.1f}s · stop={reply.stop_reason}"
                       + (" · served by fallback model" if reply.fallback_used else ""))
        self._finish_record("answered", text[:160])
        self.last_ok = True
        self._set_retry(None)
        if self.settings.voice_enabled:
            self.speaker.say(text, router.detect_language(text))
            self._set(DONE)
        else:
            self._set(IDLE)

    def _on_ai_error(self, rid: int, e: AIError) -> None:
        if rid != self._ai_rid:
            return
        self.ai.history.pop_last_user()                # qayta urinishda qayta qo'shiladi
        self.aiStream.emit("thinking_off", "")
        msg = self._ai_error_text(e, self.lang)
        self.log_event("error", "ERROR", f"AI request failed ({e.kind}): {(e.detail or '')[:160]}")
        self.aiStream.emit("error", msg)
        self._set_retry(("ai",) + self._ai_ctx)
        self._finish_record("ai_failed", msg)
        self.last_ok = False
        if self.settings.voice_enabled:
            self.speaker.say(msg.split(".")[0] + ".", self.lang)
        self._set(DONE)

    def cancel_ai(self) -> None:
        """Javob yaratilishini DARHOL to'xtatadi (qisman javob saqlanadi). Eski so'rovning kech signallari e'tiborsiz qoldiriladi."""
        if not (self.ai_busy and self.ai):
            return
        self._ai_rid += 1                              # kech kelgan done/delta/error signallari endi hisobga olinmaydi
        self.ai.cancel()
        text = "".join(self._ai_parts)
        self.aiStream.emit("thinking_off", "")
        if text.strip():
            self.ai.history.add_assistant(text)
        else:
            self.ai.history.pop_last_user()
        self.aiStream.emit("stopped", text)
        self.log_event("info", "AI", "Generation stopped by the user")
        self._finish_record("cancelled", "Stopped by user")
        self.last_ok = True
        self._set(IDLE)

    def stop_speaking(self) -> None:
        self.speaker.stop()
        self.log_event("info", "SPEECH", "Speech stopped by the user")
        if self.state == DONE:
            self._set(IDLE)

    def retry(self) -> None:
        """Muvaffaqiyatsiz AI so'rovini yoki nutq tanishni qayta bajaradi."""
        if not self.can_retry() or not self._guard():
            return
        ctx = self._retry
        self._set_retry(None)
        if ctx[0] == "ai":
            self.log_event("info", "AI", "Retrying the last request")
            self._start_ai(ctx[1], ctx[2], None)
        elif ctx[0] == "stt" and self._last_recording is not None:
            self.log_event("info", "VOICE", "Retrying speech recognition on the same recording")
            self._run_stt(self._last_recording)

    def clear_conversation(self) -> None:
        """Chatdagi suhbatni va AI kontekstini tozalaydi (buyruqlar tarixi saqlanadi)."""
        self.cancel_ai()
        if self.ai:
            self.ai.history.clear()
        self._last_recording = None
        self._set_retry(None)
        self.log_event("info", "SYSTEM", "Conversation context cleared")

    # ------------------------------------------------------------ aniqlashtirishning davomi va eslatma rejalashtiruvchisi
    def _continue_draft(self, text: str, res: commands.ParseResult | None) -> commands.ParseResult:
        """«9 ertalabmi, kechqurunmi?» -> «ertalab»: javob avvalgi so'rovga qo'shib qayta tahlil qilinadi. Tegishli bo'lmasa — yangi buyruq."""
        draft, tries = self._draft, self._draft_tries
        self._draft, self._draft_tries = "", 0
        if draft:
            cancel = fileintent.parse_choice(text, 1)
            if cancel is not None and cancel.kind == "cancel":
                return commands.ParseResult("unknown", message=T("files.choice_cancelled", self.lang), lang=self.lang)
            alone = res or commands.parse(text)
            if alone.kind in ("ok", "blocked"):               # mustaqil buyruq (yoki xavfli) — javob emas: o'zi ishlanadi
                res = alone
            else:
                combined = commands.parse(f"{draft} {text}")
                if combined.kind == "ok" or (combined.kind == "clarify" and combined.draft and tries < 3):
                    res = combined
        res = res or commands.parse(text)
        if res.kind == "clarify" and res.draft:
            self._draft, self._draft_tries = res.draft, (tries + 1 if draft else 0)
        return res

    def start_scheduler(self) -> None:
        """Eslatmalarni tekshirishni boshlaydi (oyna yaratilgandan keyin). Ilova o'chiq paytida o'tib ketganlar birinchi tekshiruvda bir marta chiqadi."""
        self._rem_timer.start()
        QTimer.singleShot(0, self.check_reminders)

    def check_reminders(self) -> None:
        if self._closed:
            return
        try:
            for r in self.executor.reminders.fire_due():
                self.log_event("active", "REMINDER", "Reminder time reached")     # sarlavha jurnalga yozilmaydi (shaxsiy ma'lumot)
                self.reminderFired.emit(r)
            self.dataChanged.emit("reminders")
        except Exception:  # noqa: BLE001 - baza xatosi ilovani qulatmasin
            log.exception("Eslatmalarni tekshirishda xato")

    # ------------------------------------------------------------ fayllar
    def _handle_choice(self, ch: fileintent.Choice) -> None:
        """«2», «birinchisini och», «ochib ber», «bekor»: ro'yxatdagi faylni tanlash. Tanlangan fayl nomi o'qib beriladi va tasdiqlanadi."""
        lang = self.lang
        self._cur["intents"] = ["OPEN_FILE"]
        if ch.kind == "cancel":
            self._choices = []
            self.log_event("info", "SYSTEM", "File selection cancelled; nothing was opened")
            self._reply(T("files.choice_cancelled", lang))
            self._finish_record("cancelled", "File selection cancelled")
            return
        n = len(self._choices)
        idx = 0 if (ch.index is None and n == 1) else ch.index
        if idx is None or not 0 <= idx < n:
            msg = T("files.bad_choice", lang, n=n)
            self._reply(msg)
            self._finish_record("clarify", msg)
            return
        entry = self._choices[idx]
        self.log_event("info", "AI", f"File chosen from the list: #{idx + 1}")
        if not entry.openable:
            msg = T("files.open.type_blocked", lang, name=entry.display, ext=entry.ext[:10])
            self._reply(msg, ok=False)
            self._finish_record("failed", msg)
            return
        self._prepare_open(entry, forced=True)

    def _prepare_open(self, entry: fs.FileEntry, forced: bool) -> None:
        """Faylni ochishdan oldin: nomi va joyi ko'rsatiladi (noaniq so'rovda ovoz bilan o'qib beriladi) va tasdiq so'raladi."""
        lang = self.lang
        ask = T("files.ask.open", lang, name=entry.display, folder=fs.safe_display(str(entry.parent), 120))
        cmd = commands.Command("open_file", {"path": str(entry.path)}, ask, intent="open_file", needs_confirm=True, force_confirm=forced)
        self._choices = []
        if not (self.settings.confirm_commands or forced):
            self._run([cmd])
            return
        self._pending = [cmd]
        self.message.emit("assistant", self._ask_text() + " " + T("confirm_hint", lang))
        if forced:
            self.speaker.say(T("files.say.confirm", lang, name=entry.display), lang)
        self.log_event("active", "AI", "Awaiting user confirmation (1 action)")
        self._set(CONFIRM)

    def _after_files(self, r: Result) -> bool:
        """Fayl natijasidan keyin: ro'yxatni eslab qoladi; ochish so'ralgan bo'lsa — bitta aniq fayl -> tasdiq, ko'p/o'xshash -> tanlash. True = oqimni o'zi davom ettirdi."""
        lang = self.lang
        entries = list(r.files or [])
        self._choices = entries
        if r.then != "open" or not entries:
            return False
        if len(entries) == 1 and not r.fuzzy:
            e = entries[0]
            if not e.openable:
                msg = T("files.open.type_blocked", lang, name=e.display, ext=e.ext[:10])
                self._finish_record("failed", msg)
                self._reply(msg, ok=False)
                return True
            self.message.emit("assistant", r.message)
            self._prepare_open(e, forced=False)
            return True
        self._finish_record("clarify", T("files.choose", lang, n=len(entries)))
        self._reply(r.message + "\n\n" + T("files.choose", lang, n=len(entries)), True, T("files.say.choose", lang, n=len(entries)))
        return True

    def open_path(self, path: str) -> None:
        """«File Access» sahifasidagi «Open File» tugmasi: foydalanuvchining aniq harakati. Baribir ijrochi tekshiruvlaridan o'tadi."""
        if self.busy or self.state == LISTENING or self.ai_busy or not self._guard():
            return
        self.last_ok = True
        name = fs.safe_display(path.replace("\\", "/").rsplit("/", 1)[-1])
        self._cur = {"time": time.time(), "source": "ui", "text": f"Open file: {name}", "intents": ["OPEN_FILE"], "outcome": "", "summary": ""}
        self._run([commands.Command("open_file", {"path": path}, T("files.ask.open", self.lang, name=name, folder="…"), intent="open_file")])

    def forget_files(self) -> None:
        """Ruxsat bekor qilinganda: ro'yxat va tanlash holati tozalanadi."""
        self._choices = []
        self.executor.files.recent.clear()

    def _on_executed(self, results: list[Result]) -> None:
        for r in results:
            first = r.message.splitlines()[0] if r.message else ""
            self.log_event("success" if r.ok else "error", "SUCCESS" if r.ok else "ERROR", first)
        for r in results:
            if r.ui == "screenshot":
                try:
                    path = desktop.take_screenshot(desktop.screenshots_dir(), self.executor.now())
                    r.message, r.spoken, r.ok = T("shot.ok", self.lang, path=path), T("shot.ok_say", self.lang), True
                except Exception as e:  # noqa: BLE001
                    log.warning("Skrinshot olinmadi", exc_info=True)
                    r.message, r.spoken, r.ok = T("shot.fail", self.lang, err=str(e)[:120]), None, False
            elif r.ui == "mic_status":
                r.message = self._mic_status_text()
        if len(results) == 1 and results[0].ui.startswith("clipboard:"):
            self._clipboard(results[0].ui.split(":", 1)[1])
            return
        if len(results) == 1 and results[0].lesson:
            self._start_lesson(*results[0].lesson)
            return
        if len(results) == 1 and results[0].ai_prompt and results[0].ok:
            self.message.emit("assistant", results[0].message)
            self._start_ai(results[0].ai_prompt, router.Route(router.GENERAL_CONVERSATION, "english-translate", self.lang), None)
            return
        ok_all = all(r.ok for r in results)
        for r in results:
            if r.changed:
                self.dataChanged.emit(r.changed)
            if r.nav:
                self.navigate.emit(r.nav)
        if len(results) == 1 and results[0].files is not None and self._after_files(results[0]):
            return
        self._finish_record("executed" if ok_all else "failed", results[0].message.splitlines()[0] if results and results[0].message else "")
        text = "\n\n".join(r.message for r in results)
        spoken = " ".join((r.spoken or r.message.splitlines()[0]) for r in results)[:500]
        self._reply(text, ok_all, spoken)

    # ------------------------------------------------------------ mikrofon holati, clipboard
    def _mic_status_text(self) -> str:
        state = "listening" if self.state == LISTENING else "idle"        # bu buyruqning o'zi bajarilayotgan paytda ham mikrofon tayyor (faqat Space bilan yoqiladi)
        if state == "idle" and not self.last_ok:
            state = "error"
        dev = self.settings.microphone or T("mic.default", self.lang)
        return T("ui.mic", self.lang, state=T(f"mic.state.{state}", self.lang), dev=dev)

    def _clipboard(self, mode: str) -> None:
        """Foydalanuvchi buyruq berib, TASDIQLAGANIDAN keyin clipboard matnini o'qiydi. Matn jurnalga yozilmaydi; AI'ga faqat explain/summarize'da yuboriladi."""
        self.log_event("info", "CLIPBOARD", f"Clipboard read ({mode}) after user confirmation; content is not logged")
        try:
            text = desktop.read_clipboard()
        except Exception:  # noqa: BLE001
            log.warning("Clipboard o'qilmadi", exc_info=True)
            text = None
        lang = self.lang
        if not text or not text.strip():
            self._reply(T("clip.empty", lang), ok=False)
            self._finish_record("failed", "Clipboard empty")
            return
        if desktop.looks_secret(text):
            self.log_event("warn", "SECURITY", "Clipboard text looks like a secret; neither shown nor sent")
            self._reply(T("clip.secret", lang), ok=False)
            self._finish_record("blocked", "Clipboard looks like a secret")
            return
        if mode == "read":
            shown = text[:desktop.MAX_SHOW_CHARS] + (T("clip.cut", lang) if len(text) > desktop.MAX_SHOW_CHARS else "")
            self._reply(T("clip.show", lang, n=len(text), text=shown), spoken=T("clip.say", lang))
            self._finish_record("executed", "Clipboard shown")
            return
        if len(text) > desktop.MAX_AI_CHARS:
            self._reply(T("clip.too_long", lang, n=len(text), max=desktop.MAX_AI_CHARS), ok=False)
            self._finish_record("failed", "Clipboard too long")
            return
        prompt = T(f"clip.p.{mode}", lang, text=text, language=T("lang.name", lang))
        self.message.emit("assistant", T("clip.sending", lang, n=len(text)))
        self._start_ai(prompt, router.Route(router.GENERAL_CONVERSATION, "clipboard", lang), None)

    # ------------------------------------------------------------ ingliz tili mashqlari (har javob — alohida ovozli buyruq)
    def _start_lesson(self, kind: str, level: str, n: int) -> None:
        self._lesson = english.make_lesson(kind, level, self.lang, n)
        self.log_event("info", "ENGLISH", f"Exercise started: {kind} ({level})")
        self._deliver_turn(self._lesson.start())

    def _lesson_turn(self, text: str, res: commands.ParseResult | None) -> bool:
        """True — gap mashq javobi sifatida qabul qilindi. Aniq boshqa buyruq bo'lsa (javob tushunarsiz) mashq tugaydi va buyruq bajariladi."""
        turn = self._lesson.answer(text)
        if getattr(turn, "unclear", False) and self._lesson.kind != "pronunciation":
            r = res or commands.parse(text)
            if r.kind == "ok":
                self.log_event("info", "ENGLISH", "Exercise ended: another command was heard")
                self._lesson, self._stt_lang = None, ""
                return False
        self._deliver_turn(turn)
        return True

    def _deliver_turn(self, turn: english.Turn) -> None:
        self._stt_lang = "" if turn.done else (turn.stt_lang or "")
        text = turn.text
        if turn.done:
            text += self._finish_lesson(turn)
        self.lang = self._lesson.lang if self._lesson else self.lang
        self.last_ok = True
        if turn.speak:                                 # tinglash: inglizcha gap faqat ovozda aytiladi, matnda ko'rsatilmaydi
            if self.settings.voice_enabled:
                self.message.emit("assistant", text)
                self.speaker.say(turn.speak, "en")
                self._set(DONE)
            else:
                self._reply(text + "\n\n" + T("eng.listen.silent", self.lang, text=turn.speak))
        else:
            self._reply(text)
        self._finish_record("executed", "English exercise")
        if turn.done:
            self._lesson = None

    def _finish_lesson(self, turn: english.Turn) -> str:
        extra = ""
        if turn.saved:
            try:
                st = self.executor.study
                st.record_session(turn.kind, turn.level, turn.total or 0, turn.correct or 0)
                extra += "\n" + T("eng.saved", self.lang)
                if turn.kind == "quiz" and turn.wrong_words:
                    added = sum(1 for w in turn.wrong_words if st.add_item("word", w, "quiz")[1])
                    if added:
                        extra += " " + T("eng.added", self.lang, n=added)
                self.dataChanged.emit("study")
            except Exception:  # noqa: BLE001
                log.warning("Mashq natijasi yozilmadi", exc_info=True)
        self._stt_lang = ""
        return extra

    # ------------------------------------------------------------ yopish
    def shutdown(self) -> None:
        self._closed = True
        self._rem_timer.stop()
        ev = getattr(self.executor, "cancel_event", None)
        if ev is not None:
            ev.set()                                  # davom etayotgan fayl qidiruvi to'xtaydi
        if self.ai:
            self.ai.cancel()
        self._limit.stop(); self._idle.stop()
        if self._recorder:
            try:
                self._recorder.stop()
            except Exception:  # noqa: BLE001
                pass
            self._recorder = None
        self.speaker.stop()
