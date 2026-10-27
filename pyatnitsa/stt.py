"""Nutqni matnga aylantirish dvigatellari.

 • Google Web Speech (standart, internet kerak): bir so'rovda bitta til; «avto» rejimida uz-UZ, ru-RU, en-US parallel.
   CHEKLOV: uz-UZ modeli kamdan-kam aniq; aralash uz+ru gaplarni ishonchli tanimaydi.
 • Whisper (ixtiyoriy, oflayn, `pip install faster-whisper`): ko'p tilli, o'zbekchani Google'dan yaxshiroq tanish mumkin
   («small» model tavsiya etiladi; birinchi ishlatishda model yuklab olinadi).
Hech qanday xato yutilmaydi: har bir muvaffaqiyatsizlik aniq `VoiceError` kaliti bilan ko'tariladi.
"""
from __future__ import annotations

import logging
import re
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import audio
from .audio import AudioError, NotUnderstood, VoiceError

log = logging.getLogger("pyatnitsa.voice")

AUTO_LANGS = ["uz-UZ", "ru-RU", "en-US"]
WHISPER_SIZES = ["tiny", "base", "small"]
PROMPT = "Chrome, Google, Downloads, Desktop, Documents, Notepad, YouTube, RAM, CPU, GPU. Och, открой, open."


@dataclass
class Heard:
    text: str
    lang: str                       # uz-UZ | ru-RU | en-US (Whisper: uz | ru | en)
    conf: float | None = None       # 0..1 yoki None (dvigatel bermagan)


@dataclass
class Outcome:
    candidates: list[Heard]
    quality: audio.Quality
    engine: str
    language: str


_HALLUCINATIONS = ("subtitles by", "thanks for watching", "thank you for watching", "продолжение следует", "субтитры", "редактор субтитров",
                   "amara.org", "[blank_audio]", "(silence)", "[silence]", "♪")


def clean_text(s: str) -> str:
    """Bo'sh joylar, ko'rinmas belgilar va dvigatel artefaktlarini tozalaydi (so'zlarni o'zgartirmaydi)."""
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[​-‏‪-‮﻿]", "", s)
    s = re.sub(r"\[[^\]]{0,30}\]|\([^)]{0,30}\)", lambda m: "" if m.group(0).lower().strip("[]() ") in ("music", "noise", "silence", "blank_audio", "applause") else m.group(0), s)
    s = re.sub(r"\s+", " ", s).strip()
    if any(h in s.lower() for h in _HALLUCINATIONS):
        return ""
    return s


# ----------------------------------------------------------------------------- Google
class GoogleEngine:
    name = "google"

    def __init__(self, language: str = "auto"):
        self.language = language

    def langs(self) -> list[str]:
        return AUTO_LANGS if self.language == "auto" else [self.language]

    @staticmethod
    def _one(pcm: bytes, lang: str) -> list[Heard]:
        import speech_recognition as sr
        r = sr.Recognizer()
        r.operation_timeout = 12
        data = r.recognize_google(sr.AudioData(pcm, audio.TARGET_RATE, 2), language=lang, show_all=True)
        out = []
        for alt in (data.get("alternative", []) if isinstance(data, dict) else [])[:3]:
            text = clean_text(str(alt.get("transcript", "")))
            if text:
                conf = alt.get("confidence")
                out.append(Heard(text, lang, float(conf) if conf is not None else None))
        return out

    def transcribe(self, samples) -> list[Heard]:
        try:
            import speech_recognition as sr
        except Exception as e:  # noqa: BLE001
            raise AudioError("stt.lib_missing", str(e)) from e
        pcm = samples.tobytes()
        results: list[Heard] = []
        errors: list[tuple[str, Exception]] = []
        langs = self.langs()
        with ThreadPoolExecutor(max_workers=len(langs)) as pool:
            futs = {l: pool.submit(self._one, pcm, l) for l in langs}
            for l, f in futs.items():
                try:
                    results += f.result()
                except Exception as e:  # noqa: BLE001 — turi bo'yicha pastda ko'tariladi, YUTILMAYDI
                    errors.append((l, e))
                    log.warning("Google (%s) xatosi: %s: %s", l, type(e).__name__, e)
        if results:
            return results
        if errors and len(errors) == len(langs):
            raise self._classify(errors[0][1])
        return []

    @staticmethod
    def _classify(e: Exception) -> VoiceError:
        import speech_recognition as sr
        text = f"{type(e).__name__}: {e}"
        if isinstance(e, sr.RequestError):
            low = str(e).lower()
            if "connection failed" in low or "timed out" in low or "unreachable" in low or "name resolution" in low or "urlopen" in low:
                return AudioError("stt.network", text)
            return AudioError("stt.failed", text)          # masalan HTTP 403/429: xizmat rad etdi
        if isinstance(e, (TimeoutError, ConnectionError)):
            return AudioError("stt.network", text)
        return AudioError("stt.failed", text)               # FLAC konverteri, audioop va h.k.


# ----------------------------------------------------------------------------- Whisper (ixtiyoriy)
class WhisperEngine:
    name = "whisper"
    _models: dict[str, object] = {}
    _lock = threading.Lock()

    def __init__(self, language: str = "auto", size: str = "base"):
        self.language, self.size = language, size if size in WHISPER_SIZES else "base"

    @staticmethod
    def available() -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def _model(self):
        with self._lock:
            if self.size not in self._models:
                try:
                    from faster_whisper import WhisperModel
                except Exception as e:  # noqa: BLE001
                    raise AudioError("stt.whisper_missing", str(e)) from e
                from .settings import data_dir
                try:
                    self._models[self.size] = WhisperModel(self.size, device="cpu", compute_type="int8", download_root=str(data_dir() / "models"))
                except Exception as e:  # noqa: BLE001
                    raise AudioError("stt.whisper_load", f"{type(e).__name__}: {e}") from e
            return self._models[self.size]

    def transcribe(self, samples) -> list[Heard]:
        import numpy as np
        model = self._model()
        audio_f = samples.astype(np.float32) / 32768.0
        lang = None if self.language == "auto" else self.language.split("-")[0]
        try:
            if lang is None:                                   # faqat uz / ru / en orasidan tanlash
                try:
                    best = detect_among(model, audio_f)
                    lang = best
                except Exception:  # noqa: BLE001
                    lang = None
            segs, info = model.transcribe(audio_f, language=lang, beam_size=5, vad_filter=True, initial_prompt=PROMPT, condition_on_previous_text=False)
            parts, probs = [], []
            for s in segs:
                parts.append(s.text)
                probs.append(float(np.exp(getattr(s, "avg_logprob", -1.0))))
        except VoiceError:
            raise
        except Exception as e:  # noqa: BLE001
            raise AudioError("stt.failed", f"whisper: {type(e).__name__}: {e}") from e
        text = clean_text(" ".join(parts))
        if not text:
            return []
        return [Heard(text, getattr(info, "language", lang) or "auto", min(1.0, sum(probs) / len(probs)) if probs else None)]


def detect_among(model, audio_f, allowed=("uz", "ru", "en")) -> str | None:
    """Whisper til ehtimollaridan faqat uz/ru/en ichidagi eng yuqorisini tanlaydi."""
    res = model.detect_language(audio_f)
    all_probs = res[2] if isinstance(res, tuple) and len(res) > 2 else []
    cand = [(p, l) for l, p in all_probs if l in allowed]
    return max(cand)[1] if cand else None


# ----------------------------------------------------------------------------- umumiy kirish nuqtasi
def make_engine(settings):
    if getattr(settings, "stt_engine", "google") == "whisper":
        return WhisperEngine(settings.stt_language, getattr(settings, "whisper_model", "base"))
    return GoogleEngine(settings.stt_language)


def recognize(rec: audio.Recording, settings, engine=None) -> Outcome:
    """Yozuv -> sifat tekshiruvi -> tayyorlash -> dvigatel. Bo'sh/jim/past ovozda dvigatelga hech narsa yuborilmaydi."""
    samples, q = audio.preprocess(rec)
    log.info("Audio: %s", q.summary())
    if q.verdict == "too_short":
        raise NotUnderstood("voice.too_short")
    if q.verdict == "silent":
        raise NotUnderstood("voice.silent")
    eng = engine or make_engine(settings)
    if q.verdict == "no_speech" and eng.name == "whisper":
        raise NotUnderstood("voice.no_speech")        # Whisper shovqinda gap «to'qib chiqaradi» — unga bunday audio berilmaydi
    lang = getattr(eng, "language", settings.stt_language)
    log.info("Recognition: engine=%s language=%s%s", eng.name, lang, " (VAD: nutq topilmadi — Google'ning o'ziga ham beriladi)" if q.verdict == "no_speech" else "")
    heard = eng.transcribe(samples)
    if not heard:
        raise NotUnderstood("voice.no_speech" if q.verdict == "no_speech" else "voice.too_quiet" if q.quiet else "stt.empty")
    log.info("Recognized (%d candidate%s): %s", len(heard), "s" if len(heard) != 1 else "", " | ".join(f"{h.lang}:{h.text[:80]}" for h in heard))
    return Outcome(heard, q, eng.name, lang)
