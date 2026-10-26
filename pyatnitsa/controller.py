"""Holat mashinasi: Kutmoqda -> Tinglayapti -> Tekshirilmoqda -> (Tasdiq) -> Bajarilmoqda -> Tayyor.

Ovozli va matnli buyruqlar BIR XIL `_handle_text` yo'lidan o'tadi: tushunish (nlu), rad etish/aniqlashtirish, ruxsat tekshiruvi,
tasdiq, ijro. Mikrofon faqat toggle_listening() bilan ochiladi; buyruqlar faqat ilova oynasi faol bo'lganda qabul qilinadi.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from . import audio, commands
from .executor import Executor, Result
from .i18n import T
from .settings import Settings

log = logging.getLogger(__name__)

IDLE, LISTENING, CHECKING, CONFIRM, RUNNING, DONE = "idle", "listening", "checking", "confirm", "running", "done"
LABELS = {IDLE: "Kutmoqda", LISTENING: "Tinglayapti", CHECKING: "Buyruq tekshirilmoqda",
          CONFIRM: "Tasdiq kutilmoqda", RUNNING: "Bajarilmoqda", DONE: "Tayyor"}
_OPEN_ACTIONS = {"open_app", "new_window", "search", "time", "admin_info"}   # natijaning o'zi xabar — alohida «tekshiryapman» kerak emas


def _ack_key(action: str) -> str | None:
    if action in _OPEN_ACTIONS:
        return None
    return {"rate_usd": "ack.rate_usd", "convert_usd": "ack.convert_usd", "weather": "ack.weather"}.get(action, "ack.health")


class Controller(QObject):
    stateChanged = Signal(str, str)        # kalit, o'zbekcha nomi
    message = Signal(str, str)             # rol: user | assistant | system, matn
    level = Signal(float)
    confirmChanged = Signal(bool, str)     # kerakmi, savol matni
    _transcribed = Signal(object, object)  # nomzodlar, xato
    _executed = Signal(object)
    _level_in = Signal(float)

    def __init__(self, settings: Settings, executor: Executor, speaker, recorder_factory=None, transcribe=None):
        super().__init__()
        self.settings, self.executor, self.speaker = settings, executor, speaker
        self._recorder_factory = recorder_factory or (lambda: audio.Recorder(settings.microphone))
        self._transcribe = transcribe or audio.transcribe
        self.state = IDLE
        self.lang = "uz"                    # oxirgi buyruq tili (javob tili)
        self.is_active = lambda: True      # ilova oynasi ochiq va faolmi (UI o'rnatadi)
        self._recorder = None
        self._pending: list[commands.Command] = []
        self._limit = QTimer(self, singleShot=True, interval=audio.MAX_SECONDS * 1000)
        self._limit.timeout.connect(self._auto_stop)
        self._idle = QTimer(self, singleShot=True, interval=2000)
        self._idle.timeout.connect(lambda: self.state == DONE and self._set(IDLE))
        self._transcribed.connect(self._on_transcribed)
        self._executed.connect(self._on_executed)
        self._level_in.connect(self.level)

    # ------------------------------------------------------------ holat
    def _set(self, state: str) -> None:
        self.state = state
        self.stateChanged.emit(state, LABELS[state])
        self.confirmChanged.emit(state == CONFIRM, self._ask_text() if self._pending else "")
        if state == DONE:
            self._idle.start()

    def _ask_text(self) -> str:
        asks = [c.confirm_text for c in self._pending]
        if len(asks) == 1:
            return asks[0] + "?"
        return T("plan", self.lang, n=len(asks), items="; ".join(f"{i}) {a}" for i, a in enumerate(asks, 1))) + "?"

    def _reply(self, text: str, ok: bool = True, spoken: str | None = None) -> None:
        self.message.emit("assistant", text)
        self.speaker.say(spoken or text, self.lang)
        self._set(DONE)

    @property
    def busy(self) -> bool:
        return self.state in (CHECKING, RUNNING)

    # ------------------------------------------------------------ mikrofon
    def _guard(self) -> bool:
        """Buyruqlar faqat ilova oynasi ochiq va faol bo'lgandagina qabul qilinadi/bajariladi."""
        if self.is_active():
            return True
        self.message.emit("system", T("inactive", self.lang))
        return False

    def toggle_listening(self) -> None:
        if self.state == LISTENING:
            self._stop_listening()
        elif not self.busy and self._guard():
            if self.state == CONFIRM:
                self.cancel(silent=True)
            self._start_listening()

    def _start_listening(self) -> None:
        self.speaker.stop()
        try:
            rec = self._recorder_factory()
            rec.on_level = self._level_in.emit
            rec.start()
        except audio.AudioError as e:
            self.message.emit("system", str(e))
            self._set(IDLE)
            return
        except Exception as e:  # noqa: BLE001
            log.exception("Mikrofon xatosi")
            self.message.emit("system", f"Mikrofonda kutilmagan xato: {e}")
            self._set(IDLE)
            return
        self._recorder = rec
        self._limit.start()
        self._set(LISTENING)

    def _stop_listening(self) -> None:
        self._limit.stop()
        rec, self._recorder = self._recorder, None
        self._set(CHECKING)
        self.level.emit(0.0)
        try:
            recording = rec.stop()
        except Exception as e:  # noqa: BLE001
            log.exception("Yozuvni to'xtatishda xato")
            self._reply(f"Mikrofonni to'xtatishda xato: {e}")
            return
        lang = self.settings.stt_language

        def work():
            try:
                self._transcribed.emit(self._transcribe(recording, lang), None)
            except Exception as e:  # noqa: BLE001
                self._transcribed.emit(None, e)

        threading.Thread(target=work, daemon=True).start()

    def _auto_stop(self) -> None:
        if self.state == LISTENING:
            self.message.emit("system", f"{audio.MAX_SECONDS} soniya o'tdi, tinglash avtomatik to'xtatildi.")
            self._stop_listening()

    def _on_transcribed(self, heard, err) -> None:
        if err is not None:
            if isinstance(err, audio.NotUnderstood):
                self._reply(T("unknown", self.lang))
            elif isinstance(err, audio.AudioError):
                self._reply(str(err))
            else:
                log.error("Nutqni tanishda xato", exc_info=err)
                self._reply(f"Nutqni tanishda xatolik: {err}")
            return
        self._handle_text(self.choose_transcript(heard), "voice")

    @staticmethod
    def choose_transcript(heard) -> str:
        """Bir necha tilda tanilgan nomzodlardan buyruq sifatida eng mazmunlisini tanlaydi (matn o'zgartirilmaydi)."""
        if isinstance(heard, str):
            return heard
        best, best_score = "", -1.0
        for h in heard:
            r = commands.parse(h.text)
            base = {"ok": r.confidence, "blocked": 0.95, "clarify": r.confidence * 0.5}.get(r.kind, 0.0)
            score = base + 0.2 * h.conf
            if score > best_score:
                best, best_score = h.text, score
        return best

    # ------------------------------------------------------------ matn (ikkala manba uchun umumiy)
    def submit_text(self, text: str) -> None:
        text = text.strip()
        if not text or self.state == LISTENING or self.busy or not self._guard():
            return
        if self.state == CONFIRM:
            self.cancel(silent=True)
        self._handle_text(text, "text")

    def _handle_text(self, text: str, source: str) -> None:
        self._set(CHECKING)
        self.message.emit("user", text)
        res = commands.parse(text)
        self.lang = res.lang
        if res.kind != "ok":
            self._reply(res.message)         # tushunarsiz / aniqlashtirish / xavfli: hech narsa bajarilmaydi
            return
        for c in res.commands:               # ruxsat tekshiruvi tasdiqdan oldin
            denied = self.executor.check_allowed(c, self.lang)
            if denied:
                self._reply(denied)
                return
        if self.settings.confirm_commands:
            self._pending = list(res.commands)
            self.message.emit("assistant", self._ask_text() + " " + T("confirm_hint", self.lang))
            self._set(CONFIRM)
        else:
            self._run(list(res.commands))

    def confirm(self) -> None:
        if self.state == CONFIRM and self._pending:
            if not self._guard():
                self.cancel(silent=True)
                return
            cmds, self._pending = self._pending, []
            self._run(cmds)

    def cancel(self, silent: bool = False) -> None:
        if self.state == CONFIRM:
            self._pending = []
            if silent:
                self._set(IDLE)
            else:
                self._reply(T("cancelled", self.lang))

    def _run(self, cmds: list[commands.Command]) -> None:
        self._set(RUNNING)
        lang = self.lang
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
            self._executed.emit(results)

        threading.Thread(target=work, daemon=True).start()

    def _on_executed(self, results: list[Result]) -> None:
        text = "\n\n".join(r.message for r in results)
        spoken = " ".join((r.spoken or r.message.splitlines()[0]) for r in results)[:500]
        self._reply(text, all(r.ok for r in results), spoken)

    # ------------------------------------------------------------ yopish
    def shutdown(self) -> None:
        self._limit.stop()
        if self._recorder:
            try:
                self._recorder.stop()
            except Exception:  # noqa: BLE001
                pass
            self._recorder = None
        self.speaker.stop()
