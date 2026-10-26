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

from . import audio, commands, stt
from .audio import VoiceError
from .executor import Executor, Result
from .i18n import T, has
from .settings import Settings

log = logging.getLogger("pyatnitsa.voice")

IDLE, LISTENING, CHECKING, INTERPRETING, CONFIRM, RUNNING, DONE = "idle", "listening", "checking", "interpreting", "confirm", "running", "done"
LABELS = {IDLE: "Kutmoqda", LISTENING: "Tinglayapti", CHECKING: "Nutq matnga aylantirilmoqda", INTERPRETING: "Buyruq tahlil qilinmoqda",
          CONFIRM: "Tasdiq kutilmoqda", RUNNING: "Bajarilmoqda", DONE: "Tayyor"}
_OPEN_ACTIONS = {"open_app", "new_window", "search", "time", "admin_info"}   # natijaning o'zi xabar — alohida «tekshiryapman» kerak emas
_REAL_FAILURES = ("mic.", "stt.network", "stt.failed", "stt.lib_missing", "stt.whisper")   # bular ERROR holati; qolganlari («nutq yo'q» va h.k.) oddiy javob

INTENT_NAMES = {"open_app": "OPEN_APPLICATION", "open_folder": "OPEN_FOLDER", "web_search": "WEB_SEARCH",
                "get_exchange_rate": "GET_EXCHANGE_RATE", "get_pc_health": "GET_PC_HEALTH", "get_system_info": "GET_SYSTEM_INFO",
                "get_weather": "GET_WEATHER"}


def _ack_key(action: str) -> str | None:
    if action in _OPEN_ACTIONS:
        return None
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
    _voice_done = Signal(object, object, object, object)   # matn, ParseResult, tanlangan Heard, xato
    _stage = Signal(str)
    _executed = Signal(object)
    _level_in = Signal(float)
    _endpoint = Signal()

    def __init__(self, settings: Settings, executor: Executor, speaker, recorder_factory=None, transcribe=None, post_roll_ms: int = 250):
        super().__init__()
        self.settings, self.executor, self.speaker = settings, executor, speaker
        self._recorder_factory = recorder_factory or self._default_recorder
        self._transcribe = transcribe or (lambda rec, lang: stt.recognize(rec, self.settings))
        self.post_roll_ms = post_roll_ms
        self.state = IDLE
        self.lang = "uz"                    # oxirgi buyruq tili (javob tili)
        self.last_ok = True                 # oxirgi javob muvaffaqiyatlimi (yadro ERROR holati uchun)
        self.is_active = lambda: True      # ilova oynasi ochiq va faolmi (UI o'rnatadi)
        self._recorder = None
        self._stopping = False
        self._closed = False
        self._t0 = 0.0
        self._pending: list[commands.Command] = []
        self._cur: dict | None = None
        self._limit = QTimer(self, singleShot=True, interval=audio.MAX_SECONDS * 1000)
        self._limit.timeout.connect(self._auto_stop)
        self._idle = QTimer(self, singleShot=True, interval=2000)
        self._idle.timeout.connect(self._idle_tick)
        self._voice_done.connect(self._on_voice_done)
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
        return {LISTENING: "listening", CHECKING: "processing", INTERPRETING: "interpreting", CONFIRM: "confirm", RUNNING: "executing"}.get(
            s, ("responding" if self.last_ok else "error") if s == DONE else "standby")

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
        elif not self.busy and not self._stopping and self._guard():
            if self.state == CONFIRM:
                self.cancel(silent=True)
            self._start_listening()

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
        self._t0 = time.monotonic()
        self._limit.start()
        self.last_ok = True
        dev = getattr(rec, "device", "") or "default device"
        self.log_event("info", "VOICE", f"Listening activated (microphone: {dev}, {getattr(rec, 'rate', '?')} Hz)")
        self._set(LISTENING)

    def _start_failed(self, key: str, text: str, raw: str) -> None:
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
        if self.state == LISTENING and not self._stopping:
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
        self._set(CHECKING)
        lang = self.settings.stt_language
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
        if chosen is not None and chosen.conf is not None and chosen.conf < audio.MIN_CONFIDENCE and res.kind != "blocked":
            self.message.emit("user", text)               # nima eshitilgani ko'rinsin, lekin bajarilmaydi
            self.log_event("warn", "VOICE", f"Low recognition confidence ({chosen.conf:.2f}); asking the user to repeat")
            self._reply(T("voice.unclear", self.lang, text=text))
            self._cur = {"time": time.time(), "source": "voice", "text": text, "intents": [], "outcome": "", "summary": ""}
            self._finish_record("unknown", "Low confidence")
            return
        self._handle_text(text, "voice", res)

    def _voice_failed(self, err: BaseException) -> None:
        if isinstance(err, VoiceError):
            real = err.key.startswith(_REAL_FAILURES)
            self.log_event("error" if real else "warn", "ERROR" if real else "VOICE", f"{err.key}: {(err.detail or self.error_text(err))[:200]}")
            self._reply(self.error_text(err), ok=not real)
        else:
            self.log_event("error", "ERROR", f"Speech processing error: {type(err).__name__}: {err}")
            self._reply(T("stt.failed", self.lang, detail=f"{type(err).__name__}: {err}"[:160]), ok=False)

    # ------------------------------------------------------------ matn (ikkala manba uchun umumiy)
    def submit_text(self, text: str) -> None:
        text = text.strip()
        if not text or self.state == LISTENING or self.busy or self._stopping or not self._guard():
            return
        if self.state == CONFIRM:
            self.cancel(silent=True)
        self._handle_text(text, "text")

    def _handle_text(self, text: str, source: str, res: commands.ParseResult | None = None) -> None:
        self.last_ok = True
        if self.state != INTERPRETING:           # ovozli oqimda allaqachon INTERPRETING
            self._set(INTERPRETING)
        self.message.emit("user", text)
        self._cur = {"time": time.time(), "source": source, "text": text, "intents": [], "outcome": "", "summary": ""}
        if source == "text":
            self.log_event("info", "TEXT", "Command received")
        res = res or commands.parse(text)
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
        if self.settings.confirm_commands:
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

    def _on_executed(self, results: list[Result]) -> None:
        for r in results:
            first = r.message.splitlines()[0] if r.message else ""
            self.log_event("success" if r.ok else "error", "SUCCESS" if r.ok else "ERROR", first)
        ok_all = all(r.ok for r in results)
        self._finish_record("executed" if ok_all else "failed", results[0].message.splitlines()[0] if results and results[0].message else "")
        text = "\n\n".join(r.message for r in results)
        spoken = " ".join((r.spoken or r.message.splitlines()[0]) for r in results)[:500]
        self._reply(text, ok_all, spoken)

    # ------------------------------------------------------------ yopish
    def shutdown(self) -> None:
        self._closed = True
        self._limit.stop(); self._idle.stop()
        if self._recorder:
            try:
                self._recorder.stop()
            except Exception:  # noqa: BLE001
                pass
            self._recorder = None
        self.speaker.stop()
