"""Ovozli javob (o'zbekcha). 1) edge-tts (uz-UZ, internet kerak) 2) pyttsx3 tizim ovozi (oflayn)."""
from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
import threading
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal

from .i18n import voice_name
from .settings import Settings

log = logging.getLogger(__name__)


class Speaker(QObject):
    _ready = Signal(str, int)
    note = Signal(str)
    speakingChanged = Signal(bool)
    _done = Signal(int)

    def __init__(self, settings: Settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._gen = 0
        self._tmp = Path(tempfile.mkdtemp(prefix="pyatnitsa-tts-"))
        self._noted = False
        self.speaking = False
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
        self._done.connect(self._finish)

    def set_volume(self, v: float) -> None:
        self.settings.volume = v
        if self._out:
            self._out.setVolume(v)

    def _set_speaking(self, on: bool) -> None:
        if self.speaking != on:
            self.speaking = on
            self.speakingChanged.emit(on)

    def _finish(self, gen: int) -> None:
        if gen == self._gen:
            self._set_speaking(False)

    def _on_state(self, state) -> None:
        from PySide6.QtMultimedia import QMediaPlayer
        if state == QMediaPlayer.StoppedState:
            self._set_speaking(False)

    def stop(self) -> None:
        self._gen += 1
        if self._player:
            self._player.stop()
        self._set_speaking(False)

    def say(self, text: str, lang: str = "uz") -> None:
        if not self.settings.voice_enabled or not text.strip():
            return
        self.stop()
        self._set_speaking(True)
        threading.Thread(target=self._work, args=(text[:600], self._gen, lang), daemon=True).start()

    # ---- fon oqimi
    def _work(self, text: str, gen: int, lang: str = "uz") -> None:
        if self.settings.tts_engine == "auto" and self._player:
            try:
                import edge_tts
                path = self._tmp / f"s{gen}.mp3"
                asyncio.run(edge_tts.Communicate(text, voice_name(self.settings.voice_gender, lang)).save(str(path)))
                if not self._closed:
                    self._ready.emit(str(path), gen)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("edge-tts ishlamadi (%s), tizim ovoziga o'tildi", e)
        if gen != self._gen:
            return
        self._system_voice(text, lang)
        if not self._closed:
            self._done.emit(gen)

    def _system_voice(self, text: str, lang: str = "uz") -> None:
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
            pick = [v for v in found if any(m in str(v.name).lower() for m in male)] if self.settings.voice_gender == "male" else []
            uz = (pick or found or [None])[0]
            if uz:
                engine.setProperty("voice", uz.id)
            elif lang == "uz" and not self._noted:
                self._noted = True
                self.note.emit("Tizimda o'zbek ovozi topilmadi — javoblar standart ovozda o'qiladi (talaffuz to'g'ri bo'lmasligi mumkin). "
                               "Internet bo'lsa, «Avto» ovoz rejimi o'zbekcha ovozdan foydalanadi.")
            engine.setProperty("volume", self.settings.volume)
            engine.say(text)
            engine.runAndWait()
        except Exception as e:  # noqa: BLE001
            log.warning("Tizim ovozi ishlamadi: %s", e)
            if not self._noted:
                self._noted = True
                self.note.emit("Ovozli javob ishlamadi (ovoz mexanizmi topilmadi). Javoblar matn ko'rinishida chiqadi.")

    def _play(self, path: str, gen: int) -> None:
        if gen != self._gen or not self._player:
            return
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.play()

    def close(self) -> None:
        self._closed = True
        self.stop()
        shutil.rmtree(self._tmp, ignore_errors=True)
