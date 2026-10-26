"""Tizim diagnostikasi: har bir qator HAQIQIY tekshiruv natijasi. Tekshirilmagan komponent «sog'lom» deb belgilanmaydi.

Holatlar: operational | warning | unavailable | error. Tekshiruvlar faqat o'qiydi (hech narsa o'zgartirilmaydi).
Ma'lumot olinmasa — «unavailable»; tekshiruvning o'zi xato bersa — «error».
"""
from __future__ import annotations

import socket
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import __version__, health

STATUS_LABELS = {"operational": "Operational", "warning": "Warning", "unavailable": "Unavailable", "error": "Error"}


@dataclass
class Check:
    key: str
    title: str
    status: str
    detail: str
    at: float = field(default_factory=time.time)

    @property
    def label(self) -> str:
        return STATUS_LABELS[self.status]


def _safe(key: str, title: str, fn: Callable[[], Check]) -> Check:
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        return Check(key, title, "error", f"Check failed: {e}")


def check_cpu(s: health.Snapshot) -> Check:
    st = "warning" if s.cpu_percent >= 90 else "operational"
    return Check("cpu", "CPU load", st, f"{s.cpu_percent:.0f}% in use" + (f" · {s.cpu_count} logical cores" if s.cpu_count else ""))


def check_memory(s: health.Snapshot) -> Check:
    st = "warning" if s.ram_percent >= 90 else "operational"
    return Check("ram", "Memory", st, f"{s.ram_percent:.0f}% used · {health.gb(s.ram_available)} free of {health.gb(s.ram_total)}")


def check_disk(s: health.Snapshot) -> Check:
    if not s.disks:
        return Check("disk", "Disk space", "unavailable", "No readable disks were reported")
    low = min(s.disks, key=lambda d: d.free)
    st = "error" if low.free < 2 * 1024**3 else "warning" if (low.percent >= 90 or low.free < 15 * 1024**3) else "operational"
    return Check("disk", "Disk space", st, f"Lowest free space: {low.mount} — {health.gb(low.free)} free ({100 - low.percent:.0f}%)")


def check_network(s: health.Snapshot, connect: Callable = socket.create_connection) -> Check:
    if s.net_active is None:
        return Check("net", "Network", "unavailable", "Network adapters could not be read")
    if not s.net_active:
        return Check("net", "Network", "unavailable", "No active network adapter")
    for host, port in (("1.1.1.1", 443), ("www.google.com", 443)):
        try:
            connect((host, port), timeout=3).close()
            return Check("net", "Network", "operational", f"Adapter {s.net_iface or '—'} active; internet reachable ({host}:{port})")
        except OSError:
            continue
    return Check("net", "Network", "warning", f"Adapter {s.net_iface or '—'} is active, but the internet could not be reached")


def check_application(settings_path: Path | None = None, data_dir: Path | None = None) -> Check:
    from .settings import Settings, data_dir as default_dir
    d = data_dir or default_dir()
    try:
        with tempfile.NamedTemporaryFile(dir=d, delete=True):
            pass
    except OSError as e:
        return Check("app", "Application", "error", f"Data folder is not writable: {e}")
    return Check("app", "Application", "operational",
                 f"v{__version__} · Python {sys.version.split()[0]} · data folder writable ({d})")


def check_microphone(list_devices: Callable[[], list[str]] | None = None) -> Check:
    if list_devices is None:
        from .audio import list_input_devices as list_devices
    names = list_devices()
    if not names:
        return Check("mic", "Microphone", "unavailable", "No input device found (or the audio library is missing)")
    return Check("mic", "Microphone", "operational", f"{len(names)} input device(s) found: {names[0]}" + (" …" if len(names) > 1 else ""))


def check_speech(import_fn: Callable[[str], object] | None = None, connect: Callable = socket.create_connection) -> Check:
    import importlib
    imp = import_fn or importlib.import_module
    try:
        sr = imp("speech_recognition")
    except Exception as e:  # noqa: BLE001
        return Check("stt", "Speech recognition", "unavailable", f"SpeechRecognition library is not installed ({e})")
    ver = getattr(sr, "__version__", "?")
    try:
        connect(("www.google.com", 443), timeout=3).close()
    except OSError:
        return Check("stt", "Speech recognition", "warning", f"Library v{ver} is installed, but the online service is not reachable")
    return Check("stt", "Speech recognition", "operational", f"Library v{ver} installed; online service reachable (an actual recognition was not tested)")


def check_voice_output(import_fn: Callable[[str], object] | None = None) -> Check:
    import importlib
    imp = import_fn or importlib.import_module
    found = []
    for mod in ("edge_tts", "pyttsx3"):
        try:
            imp(mod)
            found.append(mod)
        except Exception:  # noqa: BLE001
            pass
    if not found:
        return Check("tts", "Voice output", "unavailable", "Neither edge-tts nor pyttsx3 is installed")
    return Check("tts", "Voice output", "operational", "Available engines: " + ", ".join(found) + " (audio playback was not tested)")


def check_gpu(s: health.Snapshot) -> Check:
    if not s.gpus:
        return Check("gpu", "GPU sensors", "unavailable", "No graphics adapter detected")
    g = s.gpus[0]
    if g.util is None and g.temp is None:
        return Check("gpu", "GPU sensors", "warning", f"{g.name}: detected, but load/temperature are not supported on this card")
    parts = [x for x in (f"load {g.util:.0f}%" if g.util is not None else "", f"temp {g.temp:.0f}°C" if g.temp is not None else "") if x]
    return Check("gpu", "GPU sensors", "operational", f"{g.name}: " + ", ".join(parts))


def check_cpu_temperature(s: health.Snapshot) -> Check:
    if s.cpu_temp is None:
        return Check("cput", "CPU temperature", "unavailable", health.T(s.cpu_temp_note, "en"))
    return Check("cput", "CPU temperature", "warning" if s.cpu_temp >= 85 else "operational", f"{s.cpu_temp:.0f}°C")


def check_battery(s: health.Snapshot) -> Check:
    if s.battery is None:
        return Check("batt", "Battery", "unavailable", "No battery detected (desktop computer?)")
    st = "warning" if s.battery.plugged is False and s.battery.percent <= 20 else "operational"
    return Check("batt", "Battery", st, health._batt_text(s, "en"))


def run_all(monitor: health.HealthMonitor, connect: Callable = socket.create_connection) -> list[Check]:
    """Hamma tekshiruvlarni ketma-ket bajaradi (fon oqimida chaqiring: tarmoq kutishi mumkin)."""
    try:
        snap = monitor.sample(force_slow=True)
    except Exception as e:  # noqa: BLE001
        return [Check("sample", "System sampling", "error", f"Could not read system metrics: {e}")]
    return [
        _safe("cpu", "CPU load", lambda: check_cpu(snap)),
        _safe("ram", "Memory", lambda: check_memory(snap)),
        _safe("disk", "Disk space", lambda: check_disk(snap)),
        _safe("net", "Network", lambda: check_network(snap, connect)),
        _safe("app", "Application", check_application),
        _safe("mic", "Microphone", check_microphone),
        _safe("stt", "Speech recognition", lambda: check_speech(connect=connect)),
        _safe("tts", "Voice output", check_voice_output),
        _safe("gpu", "GPU sensors", lambda: check_gpu(snap)),
        _safe("cput", "CPU temperature", lambda: check_cpu_temperature(snap)),
        _safe("batt", "Battery", lambda: check_battery(snap)),
    ]


def summarize(checks: list[Check]) -> dict[str, int]:
    out = {k: 0 for k in STATUS_LABELS}
    for c in checks:
        out[c.status] += 1
    return out
