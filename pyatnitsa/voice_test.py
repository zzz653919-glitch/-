"""Settings ichidagi mikrofon testi: yozadi, sifatni o'lchaydi, tanigan matnni va tushunilgan amalni KO'RSATADI — hech narsa bajarmaydi."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from . import audio, commands, stt
from .audio import VoiceError


@dataclass
class MicReport:
    device: str = ""
    rate: int = 0
    seconds: float = 0.0
    quality: audio.Quality | None = None
    engine: str = ""
    language: str = ""
    text: str | None = None
    candidates: list[stt.Heard] = field(default_factory=list)
    interpretation: str = ""           # «OPEN_APPLICATION (app=chrome)» | «blocked» | «no intent» ...
    error_key: str = ""
    error_detail: str = ""


def run_mic_test(settings, seconds: float = 4.0, on_level: Callable[[float], None] | None = None, stop: threading.Event | None = None,
                 recorder_factory=None, recognizer=None) -> MicReport:
    rep = MicReport(engine=settings.stt_engine, language=settings.stt_language)
    rec = (recorder_factory or (lambda: audio.Recorder(settings.microphone)))()
    rec.on_level = on_level
    try:
        rec.start()
    except VoiceError as e:
        rep.error_key, rep.error_detail = e.key, e.detail
        return rep
    rep.device, rep.rate = getattr(rec, "device", ""), getattr(rec, "rate", 0)
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < seconds and not (stop and stop.is_set()):
            time.sleep(0.03)
    finally:
        recording = rec.stop()                       # mikrofon tanishdan OLDIN bo'shatiladi
    rep.seconds = recording.seconds
    rep.quality = audio.analyze(recording)
    try:
        out = (recognizer or stt.recognize)(recording, settings)
    except VoiceError as e:
        rep.error_key, rep.error_detail = e.key, e.detail
        return rep
    rep.candidates = list(out.candidates)
    from .controller import INTENT_NAMES, Controller
    best = Controller.pick_candidate(rep.candidates)
    rep.text = best.text
    res = commands.parse(best.text)
    if res.kind == "ok":
        rep.interpretation = ", ".join(f"{INTENT_NAMES.get(c.intent, c.intent.upper())} ({', '.join(f'{k}={v}' for k, v in c.args.items()) or '—'})" for c in res.commands)
    else:
        rep.interpretation = {"blocked": "blocked (not allowed)", "clarify": "needs clarification", "unknown": "no supported intent"}.get(res.kind, res.kind)
    return rep
