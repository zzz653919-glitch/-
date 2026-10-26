"""Jonli PC monitoringi: HealthMonitor (fon oqimi) -> Qt signali -> kartalar. Qiymatlar faqat haqiqiy o'lchovlardan; bo'lmasa «Unavailable / Not supported»."""
from __future__ import annotations

import html
import threading
import time

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from .. import health
from .theme import C, level_color
from .widgets import Sparkline

UNAVAILABLE, NOT_SUPPORTED = "Unavailable", "Not supported"


class MonitorBridge(QObject):
    """HealthMonitor oqimidan (boshqa thread) kelgan yangilanishni GUI thread'iga xavfsiz uzatadi."""
    updated = Signal()

    def __init__(self, monitor: health.HealthMonitor):
        super().__init__()
        self.monitor = monitor
        self._lock = threading.Lock()
        self._alive = False

    def _emit(self) -> None:                 # fon oqimidan chaqiriladi
        with self._lock:
            if self._alive:
                self.updated.emit()

    def start(self) -> None:
        with self._lock:
            self._alive = True
        self.monitor.on_update = self._emit
        self.monitor.start()

    def stop(self, join: bool = False) -> None:
        """Qaytgandan keyin hech qanday signal yuborilmaydi (oyna o'chirilgan bo'lsa ham xavfsiz)."""
        with self._lock:
            self._alive = False
        self.monitor.on_update = None
        self.monitor.stop()
        if join:
            self.monitor.join(1.0)


def rate(bps: float | None) -> str:
    if bps is None:
        return "—"
    for unit, div in (("MB/s", 1e6), ("KB/s", 1e3)):
        if bps >= div:
            return f"{bps / div:.1f} {unit}"
    return f"{bps:.0f} B/s"


class Card(QFrame):
    def __init__(self, title: str, graph: bool = False, color: str = C["cyan"], wide: bool = False):
        super().__init__()
        self.setObjectName("card")
        lay = QVBoxLayout(self); lay.setContentsMargins(12, 9, 12, 10); lay.setSpacing(4)
        self.title = QLabel(title); self.title.setObjectName("section"); lay.addWidget(self.title)
        self.value = QLabel("—"); self.value.setObjectName("big"); lay.addWidget(self.value)
        self.bar = QProgressBar(); self.bar.setRange(0, 100); self.bar.setTextVisible(False); lay.addWidget(self.bar)
        self.graph = Sparkline(color) if graph else None
        if self.graph:
            self.graph.setMinimumHeight(64 if wide else 34)
            lay.addWidget(self.graph)
        self.sub = QLabel(""); self.sub.setObjectName("sub"); self.sub.setWordWrap(True); self.sub.setTextFormat(Qt.RichText)
        lay.addWidget(self.sub)
        self.why = QLabel(""); self.why.setWordWrap(True); self.why.setTextFormat(Qt.RichText); self.why.hide()
        lay.addWidget(self.why)

    def set(self, value: str, percent: float | None, level: str, sub: str = "", history=None, why: list[str] | None = None) -> None:
        col = level_color(level)
        self.value.setText(value)
        self.value.setStyleSheet(f"color: {C['dim'] if level == 'na' else col if level != 'good' else C['text']};")
        self.bar.setVisible(percent is not None)
        if percent is not None:
            self.bar.setValue(int(max(0, min(100, percent))))
            self.bar.setProperty("level", level)
            self.bar.style().unpolish(self.bar); self.bar.style().polish(self.bar)
        if self.graph is not None:
            self.graph.setVisible(level != "na")
            self.graph.set_values(history or [], col if level in ("warn", "high") else None)
        self.sub.setText(sub)
        self.why.setVisible(bool(why))
        self.why.setText("".join(f"<div style='color:{col}'>• {html.escape(r)}</div>" for r in (why or [])))


class DiskCard(Card):
    def __init__(self, wide: bool = False):
        super().__init__("DISK")
        self._rows: list[tuple[QLabel, QProgressBar]] = []
        self._box = QVBoxLayout(); self._box.setSpacing(3)
        self.layout().insertLayout(2, self._box)
        self.value.hide()
        self.bar.hide()

    def set_disks(self, disks, a: health.Assessment, io: str) -> None:
        while len(self._rows) < min(len(disks), 4):
            lab, bar = QLabel(), QProgressBar(); bar.setRange(0, 100); bar.setTextVisible(False)
            self._box.addWidget(lab); self._box.addWidget(bar); self._rows.append((lab, bar))
        for i, (lab, bar) in enumerate(self._rows):
            on = i < len(disks)
            lab.setVisible(on); bar.setVisible(on)
            if on:
                d = disks[i]
                lvl = "high" if d.percent >= 95 else "warn" if d.percent >= 85 else "good"
                lab.setText(f"<b>{html.escape(d.mount)}</b> &nbsp;{d.percent:.0f}% · {health.gb(d.free)} free of {health.gb(d.total)}")
                bar.setValue(int(d.percent)); bar.setProperty("level", lvl); bar.style().unpolish(bar); bar.style().polish(bar)
        if not disks:
            self.sub.setText(f"<span style='color:{C['dim']}'>{UNAVAILABLE}</span>")
        else:
            self.sub.setText(f"<span style='color:{C['dim']}'>{io}</span>")
        self.why.setVisible(bool(a.reasons))
        self.why.setText("".join(f"<div style='color:{level_color(a.level)}'>• {html.escape(r)}</div>" for r in a.reasons))


class MetricsView(QWidget):
    """compact=True — o'ng panel (bir ustun); False — System Monitoring sahifasi (katta kartalar, grid)."""

    def __init__(self, bridge: MonitorBridge, compact: bool = True):
        super().__init__()
        self.bridge, self.compact = bridge, compact
        wide = not compact
        self.cpu = Card("CPU", graph=True, color=C["cyan"], wide=wide)
        self.ram = Card("RAM", graph=True, color=C["violet"], wide=wide)
        self.disk = DiskCard(wide)
        self.gpu = Card("GPU", graph=wide, color=C["blue"], wide=wide)
        self.batt = Card("BATTERY")
        self.net = Card("NETWORK")
        self.up = Card("UPTIME")
        cards = [self.cpu, self.ram, self.disk, self.gpu, self.batt, self.net, self.up]
        self.sysinfo = None
        if wide:
            self.sysinfo = Card("SYSTEM EVENTS")
            self.sysinfo.value.hide(); self.sysinfo.bar.hide()
            cards.append(self.sysinfo)
            g = QGridLayout(self); g.setSpacing(12); g.setContentsMargins(0, 0, 0, 0)
            for i, c in enumerate(cards):
                g.addWidget(c, i // 3, i % 3)
            for col in range(3):
                g.setColumnStretch(col, 1)
        else:
            v = QVBoxLayout(self); v.setSpacing(8); v.setContentsMargins(0, 0, 0, 0)
            for c in cards:
                v.addWidget(c)
            v.addStretch(1)
        self.empty()
        bridge.updated.connect(self.refresh)

    def empty(self) -> None:
        for c in (self.cpu, self.ram, self.gpu, self.batt, self.net, self.up):
            c.set("…", None, "na", "Waiting for the first measurement")
        self.disk.sub.setText(f"<span style='color:{C['dim']}'>Waiting for the first measurement</span>")

    def refresh(self) -> None:
        mon = self.bridge.monitor
        s = mon.latest
        if s is None:
            return
        a = health.assess(s, "en")
        na = lambda t: f"<span style='color:{C['dim']}'>{t}</span>"  # noqa: E731
        # CPU
        temp = f"{s.cpu_temp:.0f}°C" if s.cpu_temp is not None else na(f"{UNAVAILABLE}")
        freq = f" · {s.cpu_freq_mhz / 1000:.2f} GHz" if s.cpu_freq_mhz else ""
        self.cpu.set(f"{s.cpu_percent:.0f}%", s.cpu_percent, a["cpu"].level, f"Temp: {temp} · {s.cpu_count or '—'} cores{freq}", mon.cpu_history,
                     None if self.compact else a["cpu"].reasons)
        if s.cpu_temp is None:
            self.cpu.sub.setToolTip(health.T(s.cpu_temp_note, "en"))
        # RAM
        self.ram.set(f"{s.ram_percent:.0f}%", s.ram_percent, a["ram"].level,
                     f"{health.gb(s.ram_used)} used / {health.gb(s.ram_total)} · {health.gb(s.ram_available)} free", mon.ram_history,
                     None if self.compact else a["ram"].reasons)
        # Disk
        io = (f"I/O  read {rate(s.disk_read_bps)} · write {rate(s.disk_write_bps)}" if s.disk_read_bps is not None else f"I/O activity: {UNAVAILABLE}")
        self.disk.set_disks(s.disks, a["disk"] if not self.compact else health.Assessment(a["disk"].level), io)
        # GPU
        if not s.gpus:
            self.gpu.set(UNAVAILABLE, None, "na", na("No graphics adapter detected"))
        else:
            g = s.gpus[0]
            if g.util is None and g.temp is None:
                self.gpu.set(NOT_SUPPORTED, None, "na", f"{html.escape(g.name)}<br>" + na("Load / temperature / memory are not exposed for this card"))
            else:
                mem = f"{g.mem_used_mb:.0f}/{g.mem_total_mb:.0f} MB" if g.mem_used_mb is not None and g.mem_total_mb else UNAVAILABLE
                t = f"{g.temp:.0f}°C" if g.temp is not None else UNAVAILABLE
                self.gpu.set(f"{g.util:.0f}%" if g.util is not None else UNAVAILABLE, g.util, a["gpu"].level,
                             f"{html.escape(g.name)}<br>Temp: {t} · VRAM: {mem}", mon.gpu_history, None if self.compact else a["gpu"].reasons)
        # Battery
        if s.battery is None:
            self.batt.set("No battery", None, "na", na("Not applicable on this computer"))
        else:
            state = {True: "Charging", False: "On battery", None: "Charging state unknown"}[s.battery.plugged]
            self.batt.set(f"{s.battery.percent:.0f}%", s.battery.percent, a["battery"].level if a["battery"].level != "good" else "good", state)
        # Network (adapter holati va haqiqiy trafik; internetga chiqish diagnostikada tekshiriladi)
        if s.net_active is None:
            self.net.set(UNAVAILABLE, None, "na", na("Network adapters could not be read"))
        elif not s.net_active:
            self.net.set("Offline", None, "warn", "No active network adapter")
        else:
            self.net.set("Adapter active", None, "good", f"{html.escape(s.net_iface or '')}<br>↓ {rate(s.net_down_bps)} &nbsp; ↑ {rate(s.net_up_bps)}")
        # Uptime
        self.up.set(health.fmt_uptime(s.uptime_s, "en"), None, "good", html.escape(s.os_name))
        if self.sysinfo is not None:
            if s.events is None:
                ev = na(f"System log: {UNAVAILABLE}")
            elif not s.events:
                ev = "No critical/error events in the System log (last 24 h)"
            else:
                ev = "<br>".join(f"{html.escape(str(e.get('t')))} · {html.escape(str(e.get('src')))} (#{e.get('id')})" for e in s.events)
            self.sysinfo.sub.setText(ev)
