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


@dataclass
class Heard:
    text: str
    lang: str          # uz-UZ | ru-RU | en-US
    conf: float        # 0..1 (Google bergan bo'lsa; aks holda taxminiy 0.5)


AUTO_LANGS = ["uz-UZ", "ru-RU", "en-US"]


def _recognize_one(rec: Recording, lang: str) -> list[Heard]:
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    recognizer.operation_timeout = 12
    data = recognizer.recognize_google(sr.AudioData(rec.data, rec.rate, 2), language=lang, show_all=True)
    out: list[Heard] = []
    for alt in (data.get("alternative", []) if isinstance(data, dict) else [])[:3]:
        text = str(alt.get("transcript", "")).strip()
        if text:
            out.append(Heard(text, lang, float(alt.get("confidence", 0.5))))
    return out


def transcribe(rec: Recording, language: str = "auto") -> list[Heard]:
    """Google Web Speech (bir so'rovda bitta til). «auto» rejimida uch tilda parallel taniladi va nomzodlar qaytariladi;
    eng mosini tanlashni boshqaruvchi buyruq tushunish natijasiga qarab hal qiladi. Audio faqat shu paytda internetga yuboriladi."""
    if rec.seconds < MIN_SECONDS:
        raise NotUnderstood("Yozuv juda qisqa.")
    try:
        import speech_recognition as sr
    except Exception as e:  # noqa: BLE001
        raise AudioError("SpeechRecognition kutubxonasi topilmadi.") from e
    langs = AUTO_LANGS if language == "auto" else [language]
    results: list[Heard] = []
    net_errors = 0
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(langs)) as pool:
        futures = [pool.submit(_recognize_one, rec, l) for l in langs]
        for f in futures:
            try:
                results += f.result()
            except sr.RequestError:
                net_errors += 1
            except Exception:  # noqa: BLE001
                log.exception("Nutqni tanishda kutilmagan xato")
    if not results:
        if net_errors == len(langs):
            raise AudioError("Nutqni tanish xizmatiga ulanib bo'lmadi. Internetni tekshiring.")
        raise NotUnderstood("Nutq tanilmadi.")
    return results
