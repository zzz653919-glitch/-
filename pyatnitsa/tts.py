"""Ovozli javob (uz / ru / en). 1) edge-tts (internet kerak) 2) pyttsx3 tizim ovozi (oflayn).

Faqat HAQIQATAN mavjud ovozdan foydalaniladi: tizim ovozlari ro'yxatidan mos til qidiriladi; topilmasa, javob jim qoladi va sabab ko'rsatiladi
(noto'g'ri tilda o'qib talaffuzni buzmaymiz). `pending` — ovoz tayyorlanmoqda; `speaking` — ovoz haqiqatan chalinmoqda."""
from __future__ import annotations

import asyncio
import logging
import re
import shutil
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal

from .i18n import T, voice_name
from .settings import Settings

log = logging.getLogger(__name__)
MAX_SPEECH_CHARS = 1800
LANG_LABEL = {"uz": "Uzbek", "ru": "Russian", "en": "English"}


def prepare_speech(text: str) -> str:
    """Chatdagi matndan ovozga mos matn: kod bloklari, havolalar va markdown belgilari o'qilmaydi."""
    t = re.sub(r"```.*?```", " ", text, flags=re.S)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"^\s{0,3}(#{1,6}|[-*•]|\d+[.)])\s+", "", t, flags=re.M)
    t = re.sub(r"[*_#>~|]+", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:MAX_SPEECH_CHARS]


def edge_rate(pct: int) -> str:
    pct = max(-50, min(50, int(pct)))
    return f"{pct:+d}%"


class Speaker(QObject):
    _ready = Signal(str, int)
    _started = Signal(int)
    _done = Signal(int)
    note = Signal(str)
    speakingChanged = Signal(bool)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._gen = 0
        self._tmp = Path(tempfile.mkdtemp(prefix="pyatnitsa-tts-"))
        self._noted: set[str] = set()
        self.speaking = False          # ovoz haqiqatan chalinmoqda
        self.pending = False           # ovoz tayyorlanmoqda (sintez)
        self._closed = False
        self._player = self._out = None
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
            self._player, self._out = QMediaPlayer(self), QAudioOutput(self)
            self._player.setAudioOutput(self._out)
            self._player.playbackStateChanged.connect(self._on_state)
            self._player.errorOccurred.connect(lambda *a: self._finish(self._gen))
            self._out.setVolume(settings.volume)
        except Exception:  # noqa: BLE001
            log.warning("QtMultimedia mavjud emas; faqat tizim ovozi ishlatiladi")
        self._ready.connect(self._play)
        self._started.connect(lambda g: g == self._gen and self._set_speaking(True))
        self._done.connect(self._finish)

    # ---- holat
    def _set_speaking(self, on: bool) -> None:
        if on:
            self.pending = False
        if self.speaking != on:
            self.speaking = on
            self.speakingChanged.emit(on)

    def _finish(self, gen: int) -> None:
        if gen == self._gen:
            self.pending = False
            self._set_speaking(False)

    def _on_state(self, state) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.PlayingState:
            self._set_speaking(True)
        elif state == QMediaPlayer.StoppedState:
            self._finish(self._gen)

    def set_volume(self, v: float) -> None:
        self.settings.volume = v
        if self._out:
            self._out.setVolume(v)

    def stop(self) -> None:
        """Ovozni darhol to'xtatadi (foydalanuvchi tugmasi yoki mikrofonni yoqish)."""
        self._gen += 1
        self.pending = False
        if self._player:
            self._player.stop()
        self._set_speaking(False)

    def say(self, text: str, lang: str = "uz") -> None:
        text = prepare_speech(text)
        if not self.settings.voice_enabled or not text:
            return
        self.stop()
        self.pending = True
        threading.Thread(target=self._work, args=(text, self._gen, lang), daemon=True).start()

    # ---- fon oqimi
    def _work(self, text: str, gen: int, lang: str) -> None:
        if self.settings.tts_engine == "auto" and self._player:
            try:
                import edge_tts
                path = self._tmp / f"s{gen}.mp3"
                asyncio.run(edge_tts.Communicate(text, voice_name(self.settings.voice_gender, lang), rate=edge_rate(self.settings.voice_rate)).save(str(path)))
                if not self._closed:
                    self._ready.emit(str(path), gen)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("edge-tts ishlamadi (%s), tizim ovoziga o'tildi", type(e).__name__)
        if gen != self._gen or self._closed:
            return
        self._system_voice(text, gen, lang)
        if not self._closed:
            self._done.emit(gen)

    def _tell(self, lang: str) -> None:
        if lang not in self._noted:
            self._noted.add(lang)
            self.note.emit(T("tts.no_voice", lang, language=LANG_LABEL.get(lang, lang)))

    def _system_voice(self, text: str, gen: int, lang: str) -> None:
        try:
            try:
                import pythoncom
                pythoncom.CoInitialize()
            except Exception:  # noqa: BLE001
                pass
            import pyttsx3
            engine = pyttsx3.init()
            hints = {"uz": ("uz", "uzbek"), "ru": ("ru-", "russian", "irina", "pavel"), "en": ("en-", "english", "zira", "david")}[lang]
            male = {"ru": ("pavel",), "en": ("david", "mark")}.get(lang, ())
            found = [v for v in engine.getProperty("voices")
                     if any(h in (str(getattr(v, "id", "")) + str(getattr(v, "languages", "")) + str(v.name)).lower() for h in hints)]
            if not found:                                   # tekshirilgan ovoz yo'q: noto'g'ri tilda o'qimaymiz
                self._tell(lang)
                return
            pick = [v for v in found if any(m in str(v.name).lower() for m in male)] if self.settings.voice_gender == "male" else []
            engine.setProperty("voice", (pick or found)[0].id)
            engine.setProperty("volume", self.settings.volume)
            engine.setProperty("rate", int(200 * (1 + self.settings.voice_rate / 100)))
            if gen == self._gen and not self._closed:
                self._started.emit(gen)
                engine.say(text)
                engine.runAndWait()
        except Exception as e:  # noqa: BLE001
            log.warning("Tizim ovozi ishlamadi: %s", type(e).__name__)
            self._tell(lang)

    def _play(self, path: str, gen: int) -> None:
        if gen != self._gen or not self._player:
            return
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def close(self) -> None:
        self._closed = True
        self.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)
