"""Holat mashinasi: Kutmoqda -> Tinglayapti -> Tekshirilmoqda -> (Tasdiq) -> Bajarilmoqda -> Tayyor.

Ovozli va matnli buyruqlar BIR XIL `_handle_text` yo'lidan o'tadi: tahlil, rad etish, tasdiq, ijro.
Mikrofon faqat toggle_listening() bilan ochiladi; boshqa hech qanday joyda tinglash yo'q.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import QObject, QTimer, Signal

from . import audio, commands
from .executor import Executor, Result
from .settings import Settings

log = logging.getLogger(__name__)

IDLE, LISTENING, CHECKING, CONFIRM, RUNNING, DONE = "idle", "listening", "checking", "confirm", "running", "done"
LABELS = {IDLE: "Kutmoqda", LISTENING: "Tinglayapti", CHECKING: "Buyruq tekshirilmoqda",
          CONFIRM: "Tasdiq kutilmoqda", RUNNING: "Bajarilmoqda", DONE: "Tayyor"}


class Controller(QObject):
    stateChanged = Signal(str, str)        # kalit, o'zbekcha nomi
    message = Signal(str, str)             # rol: user | assistant | system, matn
    level = Signal(float)
    confirmChanged = Signal(bool, str)     # kerakmi, savol matni
    _transcribed = Signal(object, object)  # matn, xato
    _executed = Signal(object)
    _level_in = Signal(float)

    def __init__(self, settings: Settings, executor: Executor, speaker, recorder_factory=None, transcribe=None):
        super().__init__()
        self.settings, self.executor, self.speaker = settings, executor, speaker
        self._recorder_factory = recorder_factory or (lambda: audio.Recorder(settings.microphone))
        self._transcribe = transcribe or audio.transcribe
        self.state = IDLE
        self.is_active = lambda: True      # ilova oynasi ochiq va faolmi (UI o'rnatadi)
        self._recorder = None
        self._pending: commands.Command | None = None
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
        self.confirmChanged.emit(state == CONFIRM, self._pending.confirm_text + "?" if self._pending else "")
        if state == DONE:
            self._idle.start()

    def _reply(self, text: str, ok: bool = True, spoken: str | None = None) -> None:
        self.message.emit("assistant", text)
        self.speaker.say(spoken or text)
        self._set(DONE)

    @property
    def busy(self) -> bool:
        return self.state in (CHECKING, RUNNING)

    # ------------------------------------------------------------ mikrofon
    def _guard(self) -> bool:
        """Buyruqlar faqat ilova oynasi ochiq va faol bo'lgandagina qabul qilinadi/bajariladi."""
        if self.is_active():
            return True
        self.message.emit("system", "Ilova oynasi faol emas, shuning uchun buyruq qabul qilinmadi. Ilovaga qaytib, qayta urinib ko'ring.")
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

    def _on_transcribed(self, text, err) -> None:
        if err is not None:
            if isinstance(err, audio.NotUnderstood):
                self._reply(commands.UNKNOWN_MSG)
            elif isinstance(err, audio.AudioError):
                self._reply(str(err))
            else:
                log.error("Nutqni tanishda xato", exc_info=err)
                self._reply(f"Nutqni tanishda xatolik: {err}")
            return
        self._handle_text(text, "voice")

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
        if res.kind != "ok":
            self._reply(res.message)         # tushunarsiz/xavfli: hech narsa bajarilmaydi
            return
        if self.settings.confirm_commands:
            self._pending = res.command
            self.message.emit("assistant", res.command.confirm_text + "? Tasdiqlash: Enter yoki «Ha», bekor qilish: Esc.")
            self._set(CONFIRM)
        else:
            self._run(res.command)

    def confirm(self) -> None:
        if self.state == CONFIRM and self._pending:
            if not self._guard():
                self.cancel(silent=True)
                return
            cmd, self._pending = self._pending, None
            self._run(cmd)

    def cancel(self, silent: bool = False) -> None:
        if self.state == CONFIRM:
            self._pending = None
            if silent:
                self._set(IDLE)
            else:
                self._reply("Bekor qilindi. Hech narsa bajarilmadi.")

    def _run(self, cmd: commands.Command) -> None:
        self._set(RUNNING)

        def work():
            try:
                self._executed.emit(self.executor.execute(cmd))
            except Exception as e:  # noqa: BLE001
                log.exception("Ijro xatosi")
                self._executed.emit(Result(False, f"Xatolik yuz berdi: {e}"))

        threading.Thread(target=work, daemon=True).start()

    def _on_executed(self, res: Result) -> None:
        self._reply(res.message, res.ok, res.spoken)

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
