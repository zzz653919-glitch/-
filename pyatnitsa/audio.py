"""Mikrofon: faqat Space bosilganda ochiladi, qayta bosilganda yopiladi. Yozuv xotirada, diskka saqlanmaydi."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)
MAX_SECONDS = 30
MIN_SECONDS = 0.4


class AudioError(Exception):
    """Foydalanuvchiga ko'rsatiladigan tushunarli xato."""


class NotUnderstood(Exception):
    pass


@dataclass
class Recording:
    data: bytes
    rate: int

    @property
    def seconds(self) -> float:
        return len(self.data) / 2 / self.rate


def list_input_devices() -> list[str]:
    try:
        import sounddevice as sd
        names = []
        for d in sd.query_devices():
            if d["max_input_channels"] > 0 and d["name"] not in names:
                names.append(d["name"])
        return names
    except Exception:  # noqa: BLE001
        log.exception("Mikrofonlar ro'yxati olinmadi")
        return []


class Recorder:
    def __init__(self, device_name: str | None = None):
        self.device_name = device_name
        self._stream = None
        self._chunks: list[bytes] = []
        self._rate = 16000
        self._lock = threading.Lock()
        self.on_level: Callable[[float], None] | None = None

    @property
    def active(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        try:
            import sounddevice as sd
        except Exception as e:  # noqa: BLE001
            raise AudioError("Audio kutubxonasi (sounddevice) topilmadi. `pip install -r requirements.txt` ni bajaring.") from e
        device = None
        if self.device_name:
            for i, d in enumerate(sd.query_devices()):
                if d["max_input_channels"] > 0 and d["name"] == self.device_name:
                    device = i
                    break
        self._chunks = []

        def cb(indata, frames, time_info, status):  # audio oqimi
            self._chunks.append(bytes(indata))
            if self.on_level:
                try:
                    import numpy as np
                    arr = np.frombuffer(indata, dtype=np.int16).astype(np.float32)
                    self.on_level(min(1.0, float(np.sqrt(np.mean(arr ** 2))) / 5000.0))
                except Exception:  # noqa: BLE001
                    pass

        last_err: Exception | None = None
        for rate in (16000, 44100, 48000):
            try:
                stream = sd.RawInputStream(samplerate=rate, device=device, channels=1, dtype="int16", callback=cb)
                stream.start()
                self._stream, self._rate = stream, rate
                return
            except Exception as e:  # noqa: BLE001
                last_err = e
        log.error("Mikrofon ochilmadi: %s", last_err)
        raise AudioError("Mikrofonni ochib bo'lmadi. Mikrofon ulanganini va Windows'da ruxsat berilganini tekshiring "
                         "(Sozlamalar → Maxfiylik → Mikrofon).")

    def stop(self) -> Recording:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:  # noqa: BLE001
                log.exception("Mikrofonni yopishda xato")
        data = b"".join(self._chunks)
        self._chunks = []
        return Recording(data, self._rate)


def transcribe(rec: Recording, language: str) -> str:
    """Google Web Speech orqali matnga aylantiradi (audio faqat shu paytda internetga yuboriladi)."""
    if rec.seconds < MIN_SECONDS:
        raise NotUnderstood("Yozuv juda qisqa.")
    try:
        import speech_recognition as sr
    except Exception as e:  # noqa: BLE001
        raise AudioError("SpeechRecognition kutubxonasi topilmadi.") from e
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = 12
    try:
        return recognizer.recognize_google(sr.AudioData(rec.data, rec.rate, 2), language=language).strip()
    except sr.UnknownValueError as e:
        raise NotUnderstood("Nutq tanilmadi.") from e
    except sr.RequestError as e:
        raise AudioError("Nutqni tanish xizmatiga ulanib bo'lmadi. Internetni tekshiring.") from e
