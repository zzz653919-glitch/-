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
    device_index: int | None = None
    default_device: str = ""            # Windows'ning standart kirish qurilmasi
    warning: str = ""                   # default_loopback | selected_loopback | missing | ""
    open_ms: float = 0.0                # oqimni ochish uchun ketgan vaqt
    activity: float = 0.0               # yozuv davomida «nutq faol» bo'lgan vaqt ulushi (0..1)
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


def _run_mic_test(settings, seconds: float = 4.0, on_level: Callable[[float], None] | None = None, stop: threading.Event | None = None,
                 recorder_factory=None, recognizer=None, on_status: Callable[[str], None] | None = None,
                 on_activity: Callable[[bool], None] | None = None) -> MicReport:
    """Foydalanuvchi aniq bosganda qisqa yozuv. Holatlar: recording -> processing -> idle. Yozuv diskka saqlanmaydi."""
    status = on_status or (lambda _s: None)
    rep = MicReport(engine=settings.stt_engine, language=settings.stt_language)
    rec = (recorder_factory or (lambda: audio.Recorder(settings.microphone)))()
    rec.on_level = on_level
    act = {"on": False, "t": time.monotonic(), "sum": 0.0}

    def activity(flag: bool) -> None:                # ActivityMeter o'zgarishlarni yuboradi; ulushni shu yerda yig'amiz
        now = time.monotonic()
        if act["on"]:
            act["sum"] += now - act["t"]
        act["on"], act["t"] = flag, now
        if on_activity:
            on_activity(flag)
    rec.on_activity = activity
    try:
        rec.start()
    except VoiceError as e:
        rep.error_key, rep.error_detail = e.key, e.detail
        status("idle")
        return rep
    status("recording")
    rep.device, rep.rate = getattr(rec, "device", ""), getattr(rec, "rate", 0)
    rep.device_index, rep.warning, rep.open_ms = getattr(rec, "device_index", None), getattr(rec, "warning", ""), getattr(rec, "open_ms", 0.0)
    rep.default_device = audio.default_input_name()
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < seconds and not (stop and stop.is_set()):
            time.sleep(0.03)
    finally:
        recording = rec.stop()                       # mikrofon tanishdan OLDIN bo'shatiladi
        status("processing")
    total = time.monotonic() - t0
    if act["on"]:
        act["sum"] += time.monotonic() - act["t"]
    rep.activity = min(1.0, act["sum"] / total) if total > 0 else 0.0
    activity(False)
    rep.seconds = recording.seconds
    rep.quality = audio.analyze(recording)
    if recognizer is False:                          # faqat daraja/faollik (konsol: --no-stt)
        return rep
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


def run_mic_test(settings, seconds: float = 4.0, on_level=None, stop=None, recorder_factory=None, recognizer=None, on_status=None, on_activity=None) -> MicReport:
    try:
        return _run_mic_test(settings, seconds, on_level, stop, recorder_factory, recognizer, on_status, on_activity)
    finally:
        if on_status:
            on_status("idle")


def device_table(selected: str | None = None) -> list[dict]:
    """Barcha kirish qurilmalari: indeks, nom, host API, kanallar, tur (microphone | loopback), standartmi, ishlatiladimi.
    PortAudio ishlamasa AudioError ko'tariladi (chaqiruvchi ko'rsatadi)."""
    devices = audio.list_devices()
    using, warn = audio.choose_device(selected or None, devices)
    return [{"index": d.index, "name": d.name, "hostapi": d.hostapi, "channels": d.channels, "rate": int(d.default_rate),
             "kind": d.kind, "default": d.is_default, "used": using is not None and d.index == using.index, "warning": warn if (using is not None and d.index == using.index) else ""}
            for d in devices]
