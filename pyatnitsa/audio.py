"""Mikrofon: yozish, sifat tahlili va tayyorlash (normallashtirish, jimlikni kesish, 16 kHz).

Mikrofon faqat Space/tugma bosilganda ochiladi; yozuv xotirada, diskka saqlanmaydi va hech qachon jurnalga yozilmaydi.
Xatolar turlarga ajratiladi (`VoiceError.key`), shunda «buyruqni tushunmadim» o'rniga aniq sabab ko'rsatiladi.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger("pyatnitsa.voice")

TARGET_RATE = 16000
MAX_SECONDS = 30
MIN_SECONDS = 0.3
MIN_SPEECH_S = 0.25
MIN_CONFIDENCE = 0.40          # Google ishonchi shundan past bo'lsa — «takrorlang» (buyruq bajarilmaydi)
FRAME_S = 0.02

_MIC_LOCK = threading.Lock()   # bir vaqtda faqat bitta yozuv (boshqaruvchi YOKI mikrofon testi)


class VoiceError(Exception):
    """Foydalanuvchiga ko'rsatiladigan aniq xato. `key` — i18n kaliti, `detail` — texnik tafsilot."""
    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key, self.detail = key, detail


class AudioError(VoiceError):
    """Mikrofon / audio qurilma muammosi yoki nutq xizmatining ishlamasligi (haqiqiy xato)."""


class NotUnderstood(VoiceError):
    """Nutq aniqlanmadi / jim / juda past (xato emas — foydalanuvchi qayta aytishi kerak)."""


# ----------------------------------------------------------------------------- yordamchi (numpy)
def _np():
    import numpy as np
    return np


def to_db(x: float, ref: float = 32768.0) -> float:
    return 20.0 * math.log10(max(x, 1e-9) / ref)


def rms_to_level(rms: float) -> float:
    """Int16 RMS -> 0..1 (dBFS shkalasi: -60 dB = 0, -20 dB = 1) — past ovozli mikrofonda ham ko'rinadi."""
    return max(0.0, min(1.0, (to_db(rms) + 60.0) / 40.0))


# ----------------------------------------------------------------------------- qurilmalar
_HOSTAPI_RANK = {"MME": 0, "Windows DirectSound": 1, "Windows WASAPI": 2, "Windows WDM-KS": 3}


@dataclass
class DeviceInfo:
    index: int
    name: str
    hostapi: str
    channels: int
    default_rate: float
    is_default: bool = False


def list_devices() -> list[DeviceInfo]:
    """Barcha kirish qurilmalari. PortAudio topilmasa AudioError."""
    try:
        import sounddevice as sd
    except Exception as e:  # noqa: BLE001
        raise AudioError("mic.lib_missing", str(e)) from e
    try:
        apis = sd.query_hostapis()
        default_in = sd.default.device[0]
        out = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                out.append(DeviceInfo(i, d["name"], apis[d["hostapi"]]["name"], int(d["max_input_channels"]), float(d["default_samplerate"]), i == default_in))
        return out
    except Exception as e:  # noqa: BLE001
        raise AudioError("mic.open_failed", f"device query failed: {e}") from e


def list_input_devices() -> list[str]:
    """Interfeys uchun nomlar (takrorlarsiz, standart qurilma birinchi). Xato bo'lsa bo'sh ro'yxat."""
    try:
        devs = sorted(list_devices(), key=lambda d: (not d.is_default, d.index))
    except AudioError:
        return []
    names: list[str] = []
    for d in devs:
        if d.name not in names:
            names.append(d.name)
    return names


def resolve_device(name: str | None, devices: list[DeviceInfo]) -> DeviceInfo | None:
    """Nom bo'yicha qurilma; bir nom bir necha host API'da bo'lsa, eng mos keladigani (MME > DirectSound > WASAPI) tanlanadi."""
    if not devices:
        return None
    if name:
        same = [d for d in devices if d.name == name]
        if same:
            return min(same, key=lambda d: (_HOSTAPI_RANK.get(d.hostapi, 9), d.index))
        log.warning("Tanlangan mikrofon topilmadi (%s); standart ishlatiladi", name)
    default = [d for d in devices if d.is_default]
    return default[0] if default else min(devices, key=lambda d: (_HOSTAPI_RANK.get(d.hostapi, 9), d.index))


# ----------------------------------------------------------------------------- yozuv
@dataclass
class Recording:
    data: bytes                         # int16 mono
    rate: int
    device: str = ""
    started: float = 0.0
    stopped: float = 0.0
    overflows: int = 0

    @property
    def seconds(self) -> float:
        return len(self.data) / 2 / self.rate if self.rate else 0.0

    def samples(self):
        np = _np()
        return np.frombuffer(self.data[: len(self.data) // 2 * 2], dtype="<i2")


class EndpointDetector:
    """Gap tugaganini aniqlash (ixtiyoriy). Avval ~0,5 s shovqin darajasini o'lchaydi; kamida `min_speech_s` nutqdan keyin
    `silence_s` davomida jimlik bo'lsagina True. Qisqa pauzalar va shovqin nutqni kesmaydi."""

    def __init__(self, silence_s: float = 2.0, min_speech_s: float = 0.3, calibrate_s: float = 0.5):
        self.silence_s, self.min_speech_s, self.calibrate_s = silence_s, min_speech_s, calibrate_s
        self._t = self._speech = self._quiet = 0.0
        self._floor: list[float] = []
        self.threshold: float | None = None

    def update(self, rms: float, dt: float) -> bool:
        self._t += dt
        if self.threshold is None:
            self._floor.append(rms)
            if self._t >= self.calibrate_s:
                floor = sorted(self._floor)[len(self._floor) // 2]
                self.threshold = max(floor * 3.0, 150.0)
            return False
        if rms > self.threshold:
            self._speech += dt; self._quiet = 0.0
            return False
        self._quiet += dt
        return self._speech >= self.min_speech_s and self._quiet >= self.silence_s


class Recorder:
    def __init__(self, device_name: str | None = None, endpoint: EndpointDetector | None = None):
        self.device_name = device_name
        self.endpoint = endpoint
        self._stream = None
        self._chunks: list[bytes] = []
        self._rate = TARGET_RATE
        self._device = ""
        self._t0 = 0.0
        self._overflows = 0
        self._held = False
        self._ended = False
        self.on_level: Callable[[float], None] | None = None
        self.on_endpoint: Callable[[], None] | None = None

    @property
    def active(self) -> bool:
        return self._stream is not None

    @property
    def rate(self) -> int:
        return self._rate

    @property
    def device(self) -> str:
        return self._device

    def start(self) -> None:
        if not _MIC_LOCK.acquire(blocking=False):
            raise AudioError("mic.busy")
        self._held = True
        try:
            self._open()
        except BaseException:
            self._release()
            raise

    def _release(self) -> None:
        if self._held:
            self._held = False
            _MIC_LOCK.release()

    def _open(self) -> None:
        try:
            import sounddevice as sd
        except Exception as e:  # noqa: BLE001
            raise AudioError("mic.lib_missing", str(e)) from e
        devices = list_devices()
        if not devices:
            raise AudioError("mic.not_found")
        dev = resolve_device(self.device_name, devices)
        assert dev is not None
        np = _np()
        self._chunks, self._overflows, self._ended = [], 0, False

        def cb(indata, frames, time_info, status):      # PortAudio oqimi
            if status:
                self._overflows += 1
            raw = bytes(indata)
            self._chunks.append(raw)
            try:
                arr = np.frombuffer(raw, dtype="<i2").astype(np.float32)
                rms = float(np.sqrt(np.mean(arr * arr))) if arr.size else 0.0
                if self.on_level:
                    self.on_level(rms_to_level(rms))
                if self.endpoint and not self._ended and arr.size and self.endpoint.update(rms, arr.size / self._rate):
                    self._ended = True
                    if self.on_endpoint:
                        self.on_endpoint()
            except Exception:  # noqa: BLE001
                pass

        last: Exception | None = None
        rates = list(dict.fromkeys([TARGET_RATE, int(dev.default_rate), 44100, 48000]))
        for rate in rates:
            try:
                stream = sd.RawInputStream(samplerate=rate, device=dev.index, channels=1, dtype="int16", latency="high",
                                           blocksize=int(rate * 0.05), callback=cb)
                stream.start()
                self._stream, self._rate, self._device = stream, rate, dev.name
                self._t0 = time.time()
                log.info("Mikrofon ochildi: '%s' (index %d, %s), %d Hz, mono int16", dev.name, dev.index, dev.hostapi, rate)
                return
            except Exception as e:  # noqa: BLE001
                last = e
                log.warning("Mikrofon %d Hz da ochilmadi: %s", rate, e)
        text = str(last)
        if any(k in text for k in ("-9999", "Unanticipated host error", "Undefined external error", "access", "denied")):
            raise AudioError("mic.permission", text) from last
        raise AudioError("mic.open_failed", text) from last

    def stop(self) -> Recording:
        """Oqimni yopadi va mikrofonni bo'shatadi; yozilgan audio xotirada qaytariladi."""
        stream, self._stream = self._stream, None
        try:
            if stream is not None:
                try:
                    stream.stop(); stream.close()
                except Exception:  # noqa: BLE001
                    log.exception("Mikrofonni yopishda xato")
        finally:
            self._release()
        rec = Recording(b"".join(self._chunks), self._rate, self._device, self._t0, time.time(), self._overflows)
        self._chunks = []
        log.info("Yozuv tugadi: %.2f s, %d Hz, qurilma '%s', overflow=%d", rec.seconds, rec.rate, rec.device, rec.overflows)
        return rec


# ----------------------------------------------------------------------------- sifat tahlili va tayyorlash
@dataclass
class Quality:
    seconds: float = 0.0
    peak_db: float = -120.0
    rms_db: float = -120.0
    speech_s: float = 0.0
    noise_db: float = -120.0
    clipped: bool = False
    verdict: str = "ok"              # ok | too_short | silent | no_speech
    quiet: bool = False              # nutq bor, lekin juda past (kuchaytiriladi)
    gain_db: float = 0.0
    overflows: int = 0

    def summary(self) -> str:
        return (f"{self.seconds:.1f}s, peak {self.peak_db:.0f} dBFS, rms {self.rms_db:.0f} dBFS, noise {self.noise_db:.0f} dBFS, "
                f"speech {self.speech_s:.1f}s, gain {self.gain_db:+.0f} dB, verdict={self.verdict}{' (quiet)' if self.quiet else ''}")


def _frames_rms(x, rate: int):
    np = _np()
    n = max(1, int(rate * FRAME_S))
    cnt = len(x) // n
    if cnt == 0:
        return np.zeros(0, dtype=np.float32), n
    f = x[: cnt * n].reshape(cnt, n)
    return np.sqrt(np.mean(f * f, axis=1)), n


def _speech_mask(rms):
    np = _np()
    if rms.size == 0:
        return np.zeros(0, dtype=bool)
    floor = float(np.percentile(rms, 10))
    thr = max(floor * 3.0, 60.0)
    mask = rms > thr
    # qisqa pauzalar (<0,6 s) nutqning ichida deb hisoblanadi; ~100 ms kengaytiriladi
    idx = np.flatnonzero(mask)
    if idx.size:
        gap = int(0.6 / FRAME_S)
        for a, b in zip(idx[:-1], idx[1:]):
            if 1 < b - a <= gap:
                mask[a:b] = True
    k = int(0.1 / FRAME_S)
    if k:
        mask = np.convolve(mask.astype(np.int8), np.ones(2 * k + 1, dtype=np.int8), mode="same") > 0
    return mask


def analyze(rec: Recording) -> Quality:
    np = _np()
    x = rec.samples().astype(np.float32)
    q = Quality(seconds=rec.seconds, overflows=rec.overflows)
    if x.size == 0 or rec.seconds < MIN_SECONDS:
        q.verdict = "too_short"
        return q
    x = x - float(np.mean(x))
    peak, rms = float(np.max(np.abs(x))), float(np.sqrt(np.mean(x * x)))
    q.peak_db, q.rms_db, q.clipped = to_db(peak), to_db(rms), peak >= 32000
    fr, _ = _frames_rms(x, rec.rate)
    q.noise_db = to_db(float(np.percentile(fr, 10))) if fr.size else -120.0
    mask = _speech_mask(fr)
    q.speech_s = float(mask.sum()) * FRAME_S
    if peak < 8:                                  # ~ -72 dBFS: mikrofon deyarli hech narsa yozmadi (o'chirilgan / noto'g'ri qurilma)
        q.verdict = "silent"
    elif q.speech_s < MIN_SPEECH_S:
        q.verdict = "no_speech"
    q.quiet = q.verdict == "ok" and q.peak_db < -36.0
    return q


def preprocess(rec: Recording) -> tuple["object", Quality]:
    """-> (16 kHz mono int16 massiv, Quality). Nutqning ichidagi pauzalar saqlanadi; faqat chetlardagi jimlik kesiladi."""
    np = _np()
    q = analyze(rec)
    x = rec.samples().astype(np.float32)
    if x.size == 0:
        return x.astype(np.int16), q
    x = x - float(np.mean(x))
    fr, n = _frames_rms(x, rec.rate)
    mask = _speech_mask(fr)
    if mask.any():
        first, last = int(np.argmax(mask)), len(mask) - 1 - int(np.argmax(mask[::-1]))
        start = max(0, first * n - int(0.30 * rec.rate))
        end = min(len(x), (last + 1) * n + int(0.40 * rec.rate))
        x = x[start:end]
    peak = float(np.max(np.abs(x))) or 1.0
    if peak < 16000 and q.verdict == "ok":        # past ovozni ko'tarish (ko'pi bilan +30 dB)
        gain = min(0.89 * 32767 / peak, 31.6)
        x = x * gain
        q.gain_db = 20 * math.log10(gain)
    x = resample(x, rec.rate, TARGET_RATE)
    return np.clip(x, -32768, 32767).astype("<i2"), q


def resample(x, src: int, dst: int):
    """Yengil resampling (nutq uchun yetarli): butun karrali bo'lsa o'rtacha olish, aks holda chiziqli interpolyatsiya."""
    np = _np()
    if src == dst or x.size == 0:
        return x
    if src % dst == 0:
        k = src // dst
        m = (x.size // k) * k
        return x[:m].reshape(-1, k).mean(axis=1)
    if src > dst:                                  # past chastotali filtr sifatida qisqa oyna
        w = max(1, int(round(src / dst)))
        if w > 1:
            x = np.convolve(x, np.ones(w, dtype=np.float32) / w, mode="same")
    n = int(round(x.size * dst / src))
    return np.interp(np.linspace(0, x.size - 1, n), np.arange(x.size), x).astype(np.float32)
