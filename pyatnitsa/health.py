"""PC Health Monitor: faqat o'qish rejimi. Olinmagan ko'rsatkich `None` bo'lib qoladi (taxmin yo'q).

Hech narsa o'zgartirilmaydi, jarayonlar yopilmaydi, fayllar mazmuni o'qilmaydi. Tashqi vositalar
(PowerShell, nvidia-smi) faqat qat'iy, oldindan yozilgan argumentlar bilan, shell'siz chaqiriladi.
"""
from __future__ import annotations

import json
import logging
import platform
import shutil
import subprocess
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import psutil

log = logging.getLogger(__name__)
NA = "Ma'lumot mavjud emas"
HISTORY_LEN = 120

LEVELS = {"good": "Yaxshi", "warn": "Diqqat talab qiladi", "high": "Yuqori yuklanish", "na": NA}


@dataclass
class DiskInfo:
    mount: str
    total: int
    used: int
    free: int
    percent: float


@dataclass
class GpuInfo:
    name: str
    util: float | None = None
    temp: float | None = None
    mem_used_mb: float | None = None
    mem_total_mb: float | None = None
    note: str = ""


@dataclass
class BatteryInfo:
    percent: float
    plugged: bool | None
    secs_left: int | None


@dataclass
class Snapshot:
    taken: float
    cpu_percent: float
    cpu_count: int | None
    cpu_freq_mhz: float | None
    cpu_temp: float | None
    cpu_temp_note: str
    ram_total: int
    ram_used: int
    ram_available: int
    ram_percent: float
    disks: list[DiskInfo]
    disk_read_bps: float | None
    disk_write_bps: float | None
    gpus: list[GpuInfo] | None            # None = aniqlab bo'lmadi
    battery: BatteryInfo | None           # None = batareya yo'q
    os_name: str
    uptime_s: float
    events: list[dict] | None             # None = olib bo'lmadi


@dataclass
class Assessment:
    level: str = "good"
    reasons: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return LEVELS[self.level]

    def raise_to(self, level: str, reason: str) -> None:
        order = ["good", "warn", "high"]
        if order.index(level) > order.index(self.level if self.level in order else "good"):
            self.level = level
        self.reasons.append(reason)


# ------------------------------------------------------------------ yordamchi
def gb(n: float) -> str:
    return f"{n / 1024**3:.1f} GB"


def fmt_uptime(secs: float) -> str:
    s = int(secs)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    parts = ([f"{d} kun"] if d else []) + ([f"{h} soat"] if h else []) + [f"{m} daqiqa"]
    return " ".join(parts)


def _run(args: list[str], timeout: float = 8.0) -> subprocess.CompletedProcess | None:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                              creationflags=flags, shell=False, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None


def _powershell(script: str, timeout: float = 10.0) -> subprocess.CompletedProcess | None:
    if sys.platform != "win32":
        return None
    return _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], timeout)


def os_description() -> str:
    if sys.platform == "win32":
        try:
            build = sys.getwindowsversion().build
            ver = "11" if build >= 22000 else platform.release()
            return f"Windows {ver} (build {build})"
        except Exception:  # noqa: BLE001
            pass
    return f"{platform.system()} {platform.release()}"


class _Cache:
    """Sekin manbalar uchun TTL kesh."""
    def __init__(self, ttl: float, fn: Callable):
        self.ttl, self.fn, self.at, self.val = ttl, fn, 0.0, None

    def get(self, force: bool = False):
        if force or time.monotonic() - self.at > self.ttl:
            try:
                self.val = self.fn()
            except Exception:  # noqa: BLE001
                log.exception("Sensor o'qilmadi")
                self.val = None
            self.at = time.monotonic()
        return self.val


# ------------------------------------------------------------------ sensorlar
def read_cpu_temp() -> tuple[float | None, str]:
    """(harorat, izoh). Qiymat faqat haqiqiy sensordan olinadi."""
    sensors = getattr(psutil, "sensors_temperatures", None)
    if sensors:
        try:
            data = sensors()
            for key in ("coretemp", "k10temp", "zenpower", "cpu_thermal", "cpu-thermal"):
                if data.get(key):
                    vals = [t.current for t in data[key] if t.current is not None]
                    if vals:
                        return max(vals), ""
        except Exception:  # noqa: BLE001
            pass
    if sys.platform == "win32":
        for ns in ("root/LibreHardwareMonitor", "root/OpenHardwareMonitor"):
            cp = _powershell(
                f"Get-CimInstance -Namespace {ns} -ClassName Sensor -ErrorAction Stop | "
                "Where-Object {$_.SensorType -eq 'Temperature' -and $_.Name -like '*CPU*'} | "
                "Select-Object -ExpandProperty Value | ConvertTo-Json -Compress")
            if cp and cp.returncode == 0 and cp.stdout.strip():
                try:
                    v = json.loads(cp.stdout)
                    vals = [float(x) for x in (v if isinstance(v, list) else [v])]
                    if vals:
                        return max(vals), ""
                except (ValueError, TypeError):
                    pass
        cp = _powershell(
            "Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop | "
            "Select-Object -ExpandProperty CurrentTemperature | ConvertTo-Json -Compress")
        if cp and cp.returncode == 0 and cp.stdout.strip():
            try:
                v = json.loads(cp.stdout)
                vals = [(float(x) / 10.0) - 273.15 for x in (v if isinstance(v, list) else [v])]
                vals = [t for t in vals if 0 < t < 125]
                if vals:
                    return max(vals), ""
            except (ValueError, TypeError):
                pass
        return None, ("Windows protsessor haroratini standart holatda bermaydi. "
                      "LibreHardwareMonitor ishga tushirilsa, o'qish mumkin.")
    return None, "Bu tizimda protsessor harorati sensori topilmadi."


def _nvidia_smi() -> str | None:
    path = shutil.which("nvidia-smi")
    if path:
        return path
    for p in (r"C:\Windows\System32\nvidia-smi.exe", r"C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"):
        if Path(p).is_file():
            return p
    return None


def _num(s: str) -> float | None:
    try:
        return float(s)
    except ValueError:
        return None      # "[N/A]", "[Not Supported]" va h.k.


def read_gpus() -> list[GpuInfo] | None:
    smi = _nvidia_smi()
    if smi:
        cp = _run([smi, "--query-gpu=name,utilization.gpu,temperature.gpu,memory.used,memory.total",
                   "--format=csv,noheader,nounits"], timeout=6)
        if cp and cp.returncode == 0 and cp.stdout.strip():
            gpus = []
            for line in cp.stdout.strip().splitlines():
                f = [x.strip() for x in line.split(",")]
                if len(f) >= 5:
                    gpus.append(GpuInfo(f[0], _num(f[1]), _num(f[2]), _num(f[3]), _num(f[4])))
            if gpus:
                return gpus
    cp = _powershell("Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name | ConvertTo-Json -Compress")
    if cp and cp.returncode == 0 and cp.stdout.strip():
        try:
            v = json.loads(cp.stdout)
            names = v if isinstance(v, list) else [v]
            return [GpuInfo(str(n), note="Yuklanish/harorat/xotira ko'rsatkichlarini bu videokartadan o'qib bo'lmadi "
                                         "(faqat NVIDIA nvidia-smi orqali qo'llab-quvvatlanadi).") for n in names]
        except ValueError:
            pass
    return None


def read_events() -> list[dict] | None:
    """Oxirgi 24 soatdagi System jurnalidagi Critical/Error yozuvlari (faqat manba, ID va vaqt)."""
    cp = _powershell(
        "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;StartTime=(Get-Date).AddDays(-1)} "
        "-MaxEvents 5 -ErrorAction Stop | Select-Object @{n='t';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm')}},"
        "@{n='src';e={$_.ProviderName}},@{n='id';e={$_.Id}} | ConvertTo-Json -Compress", timeout=15)
    if cp is None:
        return None
    if cp.returncode != 0:
        return [] if "No events were found" in (cp.stderr or "") else None
    try:
        v = json.loads(cp.stdout or "[]")
    except ValueError:
        return None
    return v if isinstance(v, list) else [v]


# ------------------------------------------------------------------ monitor
class HealthMonitor:
    def __init__(self):
        self._lock = threading.Lock()
        self._temp = _Cache(15, read_cpu_temp)
        self._gpu = _Cache(8, read_gpus)
        self._events = _Cache(300, read_events)
        self._last_io: tuple[float, object] | None = None
        self.cpu_history: deque[float] = deque(maxlen=HISTORY_LEN)
        self.ram_history: deque[float] = deque(maxlen=HISTORY_LEN)
        self.gpu_history: deque[float] = deque(maxlen=HISTORY_LEN)
        self.latest: Snapshot | None = None
        self.version = 0
        self.interval = 3.0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.on_update: Callable[[], None] | None = None
        psutil.cpu_percent(None)   # birinchi chaqiruv 0 qaytaradi; hisoblagichni boshlab qo'yamiz

    # ---- o'lchash
    def sample(self, force_slow: bool = False) -> Snapshot:
        with self._lock:
            if self.latest is None:
                time.sleep(0.25)
            cpu = psutil.cpu_percent(None)
            vm = psutil.virtual_memory()
            try:
                freq = psutil.cpu_freq()
                freq_mhz = freq.current if freq and freq.current else None
            except Exception:  # noqa: BLE001
                freq_mhz = None
            temp, note = self._temp.get(force_slow) or (None, "Ma'lumot olinmadi.")
            rb = wb = None
            try:
                io, now = psutil.disk_io_counters(), time.monotonic()
                if io and self._last_io:
                    dt = now - self._last_io[0]
                    prev = self._last_io[1]
                    if dt > 0:
                        rb, wb = (io.read_bytes - prev.read_bytes) / dt, (io.write_bytes - prev.write_bytes) / dt
                if io:
                    self._last_io = (now, io)
            except Exception:  # noqa: BLE001
                pass
            batt = None
            try:
                b = psutil.sensors_battery()
                if b is not None:
                    batt = BatteryInfo(b.percent, b.power_plugged,
                                       b.secsleft if isinstance(b.secsleft, int) and b.secsleft >= 0 else None)
            except Exception:  # noqa: BLE001
                pass
            snap = Snapshot(
                taken=time.time(), cpu_percent=cpu, cpu_count=psutil.cpu_count(logical=True),
                cpu_freq_mhz=freq_mhz, cpu_temp=temp, cpu_temp_note=note,
                ram_total=vm.total, ram_used=vm.total - vm.available, ram_available=vm.available,
                ram_percent=vm.percent, disks=self._disks(), disk_read_bps=rb, disk_write_bps=wb,
                gpus=self._gpu.get(force_slow), battery=batt, os_name=os_description(),
                uptime_s=time.time() - psutil.boot_time(), events=self._events.get(force_slow))
            self.latest = snap
            self.cpu_history.append(cpu)
            self.ram_history.append(vm.percent)
            if snap.gpus and snap.gpus[0].util is not None:
                self.gpu_history.append(snap.gpus[0].util)
            self.version += 1
            return snap

    @staticmethod
    def _disks() -> list[DiskInfo]:
        out, seen = [], set()
        try:
            parts = psutil.disk_partitions(all=False)
        except Exception:  # noqa: BLE001
            return out
        for p in parts:
            if "cdrom" in p.opts or p.fstype == "" or p.mountpoint in seen:
                continue
            seen.add(p.mountpoint)
            try:
                u = psutil.disk_usage(p.mountpoint)
            except (PermissionError, OSError):
                continue
            if u.total >= 1024**3:   # kichik tizim bo'limlari (masalan, faqat o'qish uchun) chiqarilmaydi
                out.append(DiskInfo(p.mountpoint, u.total, u.used, u.free, u.percent))
        return out

    def top_processes(self, n: int = 5) -> tuple[list[tuple[str, float]], list[tuple[str, int]]]:
        """(CPU% bo'yicha, RSS bo'yicha) — faqat jarayon NOMLARI, nomi bo'yicha jamlangan."""
        procs = []
        for p in psutil.process_iter(["name"]):
            try:
                p.cpu_percent(None)
                procs.append(p)
            except (psutil.Error, OSError):
                pass
        time.sleep(0.5)
        cpu: dict[str, float] = {}
        mem: dict[str, int] = {}
        ncpu = psutil.cpu_count(logical=True) or 1
        for p in procs:
            try:
                name = p.info.get("name") or "?"
                cpu[name] = cpu.get(name, 0.0) + p.cpu_percent(None) / ncpu
                mem[name] = mem.get(name, 0) + p.memory_info().rss
            except (psutil.Error, OSError):
                continue
        for skip in ("System Idle Process", "Idle"):
            cpu.pop(skip, None)
        return (sorted(cpu.items(), key=lambda x: -x[1])[:n], sorted(mem.items(), key=lambda x: -x[1])[:n])

    # ---- fon oqimi (faqat panel ochiq bo'lganda ishlaydi)
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="health-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()

    def refresh_now(self) -> None:
        self._wake.set()

    def _loop(self) -> None:
        force = True
        while not self._stop.is_set():
            try:
                self.sample(force_slow=force)
                force = False
                if self.on_update:
                    self.on_update()
            except Exception:  # noqa: BLE001
                log.exception("Monitoring xatosi")
            if self._wake.wait(self.interval):
                force = not self._stop.is_set()
                self._wake.clear()


# ------------------------------------------------------------------ baholash
def assess(s: Snapshot) -> dict[str, Assessment]:
    r: dict[str, Assessment] = {k: Assessment() for k in ("cpu", "ram", "disk", "gpu", "battery")}
    c = r["cpu"]
    if s.cpu_percent >= 90:
        c.raise_to("high", f"CPU {s.cpu_percent:.0f}% band. Bu bir lahzalik bo'lishi yoki fonda og'ir dastur ishlayotganini bildirishi mumkin.")
    elif s.cpu_percent >= 70:
        c.raise_to("warn", f"CPU {s.cpu_percent:.0f}% band — odatdagidan yuqori.")
    if s.cpu_temp is not None:
        if s.cpu_temp >= 90:
            c.raise_to("high", f"Protsessor harorati {s.cpu_temp:.0f}°C. Sovutish tizimi yoki yuklanish bilan bog'liq bo'lishi mumkin (aniq sabab noma'lum).")
        elif s.cpu_temp >= 80:
            c.raise_to("warn", f"Protsessor harorati {s.cpu_temp:.0f}°C — yuqoriroq.")
    m = r["ram"]
    if s.ram_percent >= 90:
        m.raise_to("high", f"RAM {s.ram_percent:.0f}% band, bo'sh joyi {gb(s.ram_available)}. Ochiq dasturlar ko'pligi sabab bo'lishi mumkin.")
    elif s.ram_percent >= 75:
        m.raise_to("warn", f"RAM {s.ram_percent:.0f}% band.")
    d = r["disk"]
    if not s.disks:
        d.level = "na"
    for disk in s.disks:
        if disk.percent >= 95 or disk.free < 5 * 1024**3:
            d.raise_to("high", f"{disk.mount} diskida bo'sh joy juda kam: {gb(disk.free)} ({100 - disk.percent:.0f}%).")
        elif disk.percent >= 85 or disk.free < 15 * 1024**3:
            d.raise_to("warn", f"{disk.mount} diskida bo'sh joy kamayib bormoqda: {gb(disk.free)}.")
    g = r["gpu"]
    if s.gpus is None or not any(x.util is not None or x.temp is not None for x in s.gpus):
        g.level = "na"
    else:
        for x in s.gpus:
            if x.temp is not None and x.temp >= 85:
                g.raise_to("high", f"Videokarta harorati {x.temp:.0f}°C.")
            elif x.temp is not None and x.temp >= 75:
                g.raise_to("warn", f"Videokarta harorati {x.temp:.0f}°C — yuqoriroq.")
            if x.util is not None and x.util >= 95:
                g.raise_to("high", f"Videokarta {x.util:.0f}% yuklangan.")
            if x.mem_used_mb and x.mem_total_mb and x.mem_used_mb / x.mem_total_mb >= 0.9:
                g.raise_to("warn", "Videokarta xotirasi 90% dan ko'p band.")
    b = r["battery"]
    if s.battery is None:
        b.level = "na"
    elif s.battery.plugged is False and s.battery.percent <= 10:
        b.raise_to("high", f"Batareya {s.battery.percent:.0f}% va quvvat olmayapti.")
    elif s.battery.plugged is False and s.battery.percent <= 20:
        b.raise_to("warn", f"Batareya {s.battery.percent:.0f}% — tez orada zaryadlash kerak.")
    return r


def overall(a: dict[str, Assessment]) -> str:
    levels = [x.level for x in a.values()]
    return "high" if "high" in levels else "warn" if "warn" in levels else "good"


# ------------------------------------------------------------------ matnli hisobotlar
def _batt_text(s: Snapshot) -> str:
    if s.battery is None:
        return "Batareya mavjud emas."
    state = {True: "quvvat olmoqda", False: "quvvat olmayapti", None: "quvvat holati noma'lum"}[s.battery.plugged]
    left = f", taxminan {fmt_uptime(s.battery.secs_left)} qoldi" if s.battery.secs_left and not s.battery.plugged else ""
    return f"Batareya {s.battery.percent:.0f}%, {state}{left}."


def _gpu_text(s: Snapshot) -> str:
    if not s.gpus:
        return f"Videokarta: {NA}."
    lines = []
    for g in s.gpus:
        parts = [g.name]
        parts.append(f"yuklanish {g.util:.0f}%" if g.util is not None else f"yuklanish: {NA}")
        parts.append(f"harorat {g.temp:.0f}°C" if g.temp is not None else f"harorat: {NA}")
        parts.append(f"xotira {g.mem_used_mb:.0f}/{g.mem_total_mb:.0f} MB" if g.mem_used_mb is not None and g.mem_total_mb
                     else f"xotira: {NA}")
        lines.append("Videokarta: " + ", ".join(parts) + ".")
    return "\n".join(lines)


def cpu_text(s: Snapshot) -> str:
    t = f", harorati {s.cpu_temp:.0f}°C" if s.cpu_temp is not None else f". Harorat: {NA}"
    return f"CPU {s.cpu_percent:.0f}% ishlayapti{t}."


def ram_text(s: Snapshot) -> str:
    return (f"RAM {s.ram_percent:.0f}% band: jami {gb(s.ram_total)}, ishlatilgan {gb(s.ram_used)}, "
            f"bo'sh {gb(s.ram_available)}.")


def disk_text(s: Snapshot) -> str:
    if not s.disks:
        return f"Disk: {NA}."
    return "\n".join(f"Disk {d.mount}: jami {gb(d.total)}, ishlatilgan {gb(d.used)} ({d.percent:.0f}%), "
                     f"bo'sh {gb(d.free)}." for d in s.disks)


def temps_text(s: Snapshot) -> str:
    cpu = f"Protsessor harorati {s.cpu_temp:.0f}°C." if s.cpu_temp is not None else f"Protsessor harorati: {NA}. {s.cpu_temp_note}"
    gpu = "Videokarta harorati: " + (
        ", ".join(f"{g.name} {g.temp:.0f}°C" for g in (s.gpus or []) if g.temp is not None) or NA) + "."
    return f"{cpu}\n{gpu}"


def status_text(s: Snapshot) -> str:
    a = assess(s)
    head = f"CPU {s.cpu_percent:.0f}% ishlayapti, RAM {s.ram_percent:.0f}% band"
    if s.disks:
        low = min(s.disks, key=lambda d: d.free)
        head += f". Eng kam bo'sh joyli disk ({low.mount}): {gb(low.free)} bo'sh"
    head += f". Umumiy holat: {LEVELS[overall(a)]}."
    reasons = [x for v in a.values() for x in v.reasons]
    return head + ("\n" + "\n".join("• " + x for x in reasons) if reasons else "")


def full_report(s: Snapshot) -> str:
    a = assess(s)
    when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(s.taken))
    lines = [f"Kompyuter holati hisoboti — {when}", f"Tizim: {s.os_name}; ishlagan vaqt: {fmt_uptime(s.uptime_s)}",
             f"Umumiy holat: {LEVELS[overall(a)]}", "",
             f"[CPU — {a['cpu'].label}] {cpu_text(s)}"
             + (f" Yadrolar: {s.cpu_count}." if s.cpu_count else ""),
             f"[RAM — {a['ram'].label}] {ram_text(s)}",
             f"[Disk — {a['disk'].label}]", disk_text(s)]
    if s.disk_read_bps is not None and s.disk_write_bps is not None:
        lines.append(f"Disk tezligi: o'qish {s.disk_read_bps / 1e6:.1f} MB/s, yozish {s.disk_write_bps / 1e6:.1f} MB/s.")
    lines += [f"[GPU — {a['gpu'].label}]", _gpu_text(s), f"[Batareya — {a['battery'].label}] {_batt_text(s)}"]
    if s.cpu_temp is None:
        lines.append(f"Eslatma: {s.cpu_temp_note}")
    if s.events is None:
        lines.append(f"Oxirgi tizim xatolari: {NA}.")
    elif not s.events:
        lines.append("Oxirgi 24 soatda tizim jurnalida jiddiy xatolar topilmadi.")
    else:
        lines.append("Oxirgi 24 soatdagi tizim xatolari (manba, ID):")
        lines += [f"  {e.get('t')}  {e.get('src')}  #{e.get('id')}" for e in s.events]
    reasons = [x for v in a.values() for x in v.reasons]
    if reasons:
        lines += ["", "Diqqat talab qiladigan jihatlar (ehtimoliy sabablar, tashxis emas):"] + ["• " + x for x in reasons]
    lines.append("\nBu hisobot faqat o'lchangan qiymatlarga asoslangan; hech narsa o'zgartirilmadi.")
    return "\n".join(lines)


def advice(s: Snapshot, top_mem: list[tuple[str, int]], top_cpu: list[tuple[str, float]]) -> str:
    """«Tezlashtir» so'rovi: faqat tahlil va tavsiyalar, hech qanday amal bajarilmaydi."""
    a = assess(s)
    out = [status_text(s), "", "Tavsiyalar (ularni o'zingiz bajarasiz — men hech narsani o'zgartirmadim):"]
    tips = []
    if s.ram_percent >= 75 and top_mem:
        tips.append(f"RAM band: eng ko'p xotira ishlatayotganlar — " + ", ".join(f"{n} ({gb(m)})" for n, m in top_mem[:3])
                    + ". Keraksiz dastur/brauzer yorliqlarini yopish yordam berishi mumkin.")
    if s.cpu_percent >= 70 and top_cpu:
        tips.append("CPU band: " + ", ".join(f"{n} ({p:.0f}%)" for n, p in top_cpu[:3]) + " ko'proq ishlatmoqda.")
    if a["disk"].level in ("warn", "high"):
        tips.append("Disk to'lib bormoqda: Windows «Xotira» sozlamalari (Storage Sense) yoki Downloads papkasini ko'rib chiqing.")
    if s.uptime_s > 7 * 86400:
        tips.append(f"Kompyuter {fmt_uptime(s.uptime_s)} dan beri o'chirilmagan; qayta yoqish ba'zan yordam beradi.")
    if not tips:
        tips.append("O'lchovlarga ko'ra jiddiy muammo ko'rinmayapti; maxsus tezlashtirish talab qilinmaydi.")
    out += ["• " + t for t in tips]
    out.append("Tizimga ta'sir qiladigan har qanday amal (dastur yopish, fayl tozalash) uchun avval sizdan alohida rozilik so'raladi; "
               "hozirgi versiyada bunday avtomatik amallar yo'q.")
    return "\n".join(out)


def save_report(text: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / time.strftime("kompyuter-holati-%Y%m%d-%H%M%S.txt")
    path.write_text(text, encoding="utf-8")
    return path
