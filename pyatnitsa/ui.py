"""Asosiy oyna: Yordamchi (orb + chat) va Kompyuter holati (PC Health Monitor) bo'limlari, sozlamalar."""
from __future__ import annotations

import html
import time

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QSlider, QStackedWidget,
                               QTextBrowser, QTextEdit, QVBoxLayout, QWidget)

from . import APP_NAME, apps, audio, controller as C, health
from .i18n import T
from .settings import STT_LANGUAGES, TTS_ENGINES, Settings, set_autostart
from .widgets import ChatInput, OrbWidget, Sparkline

STYLE = """
* { font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 14px; color: #e6e9ef; }
QMainWindow, QDialog, QWidget#root { background: #0d0f14; }
QFrame#card { background: #14171f; border: 1px solid #232734; border-radius: 14px; }
QLabel#title { font-size: 26px; font-weight: 700; letter-spacing: 6px; }
QLabel#state { font-size: 22px; font-weight: 600; }
QLabel#muted, QLabel#hint { color: #8b93a7; }
QLabel#hint { font-size: 12px; }
QLabel#big { font-size: 34px; font-weight: 700; }
QLabel#cardTitle { color: #8b93a7; font-size: 12px; letter-spacing: 2px; font-weight: 600; }
QPushButton { background: #1b1f2a; border: 1px solid #2a3040; border-radius: 10px; padding: 9px 16px; }
QPushButton:hover { background: #232938; border-color: #3a4256; }
QPushButton#primary { background: #0e7490; border-color: #22d3ee; font-weight: 600; }
QPushButton#primary:hover { background: #0891b2; }
QPushButton#rec { background: #7f1d1d; border-color: #f87171; font-weight: 600; }
QPushButton#tab { background: transparent; border: none; border-bottom: 2px solid transparent; border-radius: 0; padding: 8px 14px; color: #8b93a7; }
QPushButton#tab:checked { color: #fff; border-bottom: 2px solid #22d3ee; }
QTextBrowser, QPlainTextEdit, QLineEdit, QComboBox, QListWidget { background: #11141b; border: 1px solid #232734; border-radius: 10px; padding: 8px; selection-background-color: #0e7490; }
QComboBox QAbstractItemView { background: #14171f; }
QProgressBar { background: #1b1f2a; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }
QProgressBar::chunk { background: #22d3ee; border-radius: 4px; }
QSlider::groove:horizontal { height: 6px; background: #232734; border-radius: 3px; }
QSlider::handle:horizontal { background: #22d3ee; width: 16px; margin: -6px 0; border-radius: 8px; }
QSlider::sub-page:horizontal { background: #0e7490; border-radius: 3px; }
QCheckBox::indicator { width: 18px; height: 18px; }
"""
CHIP = {"good": "#34d399", "warn": "#fbbf24", "high": "#f87171", "na": "#6b7280"}
GRAPH_COLOR = {"good": "#22d3ee", "warn": "#fbbf24", "high": "#f87171", "na": "#6b7280"}


def chip_html(level: str) -> str:
    return f"<span style='color:{CHIP[level]}; font-weight:600'>● {health.LEVELS[level]}</span>"


def card(title: str) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame(); f.setObjectName("card")
    lay = QVBoxLayout(f); lay.setContentsMargins(16, 14, 16, 14); lay.setSpacing(6)
    t = QLabel(title); t.setObjectName("cardTitle"); lay.addWidget(t)
    return f, lay


# ====================================================================== Kompyuter holati
class HealthPage(QWidget):
    updated = Signal()

    def __init__(self, monitor: health.HealthMonitor):
        super().__init__()
        self.monitor = monitor
        monitor.on_update = self.updated.emit
        self.updated.connect(self.refresh)
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(12)

        bar = QHBoxLayout()
        self.overall = QLabel(); self.last = QLabel(); self.last.setObjectName("muted")
        bar.addWidget(self.overall); bar.addWidget(self.last); bar.addStretch()
        bar.addWidget(QLabel("Yangilanish:"))
        self.interval = QComboBox()
        for sec in (2, 3, 5):
            self.interval.addItem(f"{sec} soniya", sec)
        self.interval.setCurrentIndex(1)
        self.interval.currentIndexChanged.connect(lambda: setattr(monitor, "interval", float(self.interval.currentData())))
        bar.addWidget(self.interval)
        btn = QPushButton("Hozir tekshirish"); btn.setObjectName("primary"); btn.clicked.connect(monitor.refresh_now)
        btn.setFocusPolicy(Qt.NoFocus); bar.addWidget(btn)
        root.addLayout(bar)

        grid = QGridLayout(); grid.setSpacing(12); root.addLayout(grid, 1)
        self.cpu_f, cl = card("CPU (PROTSESSOR)")
        self.cpu_big = QLabel("—"); self.cpu_big.setObjectName("big"); self.cpu_chip = QLabel(); self.cpu_sub = QLabel(); self.cpu_sub.setWordWrap(True)
        self.cpu_graph = Sparkline(); self.cpu_why = QLabel(); self.cpu_why.setWordWrap(True)
        for w in (self.cpu_big, self.cpu_chip, self.cpu_graph, self.cpu_sub, self.cpu_why): cl.addWidget(w)

        self.ram_f, rl = card("RAM (TEZKOR XOTIRA)")
        self.ram_big = QLabel("—"); self.ram_big.setObjectName("big"); self.ram_chip = QLabel(); self.ram_sub = QLabel(); self.ram_sub.setWordWrap(True)
        self.ram_graph = Sparkline("#a78bfa"); self.ram_why = QLabel(); self.ram_why.setWordWrap(True)
        for w in (self.ram_big, self.ram_chip, self.ram_graph, self.ram_sub, self.ram_why): rl.addWidget(w)

        self.disk_f, dl = card("DISK")
        self.disk_chip = QLabel(); self.disk_body = QLabel(); self.disk_body.setWordWrap(True); self.disk_why = QLabel(); self.disk_why.setWordWrap(True)
        self.disk_bars: list[QProgressBar] = []; self.disk_box = QVBoxLayout()
        for w in (self.disk_chip,): dl.addWidget(w)
        dl.addLayout(self.disk_box); dl.addWidget(self.disk_body); dl.addWidget(self.disk_why); dl.addStretch()

        self.gpu_f, gl = card("GPU (VIDEOKARTA)")
        self.gpu_chip = QLabel(); self.gpu_body = QLabel(); self.gpu_body.setWordWrap(True); self.gpu_why = QLabel(); self.gpu_why.setWordWrap(True)
        for w in (self.gpu_chip, self.gpu_body, self.gpu_why): gl.addWidget(w)
        gl.addStretch()

        self.bat_f, bl = card("BATAREYA")
        self.bat_big = QLabel("—"); self.bat_big.setObjectName("big"); self.bat_chip = QLabel(); self.bat_body = QLabel(); self.bat_body.setWordWrap(True)
        self.bat_why = QLabel(); self.bat_why.setWordWrap(True)
        for w in (self.bat_big, self.bat_chip, self.bat_body, self.bat_why): bl.addWidget(w)
        bl.addStretch()

        self.sys_f, sl = card("TIZIM HOLATI")
        self.sys_body = QLabel(); self.sys_body.setWordWrap(True); self.sys_body.setTextFormat(Qt.RichText)
        sl.addWidget(self.sys_body); sl.addStretch()

        for i, f in enumerate((self.cpu_f, self.ram_f, self.disk_f, self.gpu_f, self.bat_f, self.sys_f)):
            grid.addWidget(f, i // 3, i % 3)
        for c in range(3): grid.setColumnStretch(c, 1)
        for r in range(2): grid.setRowStretch(r, 1)
        self.note = QLabel("Faqat o'qish rejimi: hech narsa o'zgartirilmaydi. «Ma'lumot mavjud emas» — qurilma yoki drayver bu ko'rsatkichni bermaydi.")
        self.note.setObjectName("hint"); self.note.setWordWrap(True); root.addWidget(self.note)

    def showEvent(self, e):
        self.monitor.start(); super().showEvent(e)

    def hideEvent(self, e):
        self.monitor.stop(); super().hideEvent(e)

    @staticmethod
    def _why(a: health.Assessment) -> str:
        return "".join(f"<div style='color:{CHIP[a.level]}'>• {html.escape(r)}</div>" for r in a.reasons)

    def refresh(self) -> None:
        s = self.monitor.latest
        if not s:
            return
        a = health.assess(s)
        ov = health.overall(a)
        self.overall.setText(f"<span style='font-size:18px'>Umumiy holat: {chip_html(ov)}</span>")
        self.last.setText(f"Yangilandi: {time.strftime('%H:%M:%S', time.localtime(s.taken))}")
        # CPU
        self.cpu_big.setText(f"{s.cpu_percent:.0f}%"); self.cpu_chip.setText(chip_html(a["cpu"].level))
        temp = f"{s.cpu_temp:.0f}°C" if s.cpu_temp is not None else health.NA
        freq = f" · {s.cpu_freq_mhz / 1000:.2f} GHz" if s.cpu_freq_mhz else ""
        self.cpu_sub.setText(f"Harorat: {temp} · Yadrolar: {s.cpu_count or '—'}{freq}")
        self.cpu_graph.set_values(self.monitor.cpu_history, GRAPH_COLOR[a["cpu"].level]); self.cpu_why.setText(self._why(a["cpu"]))
        if s.cpu_temp is None:
            self.cpu_sub.setToolTip(T(s.cpu_temp_note, 'uz'))
        # RAM
        self.ram_big.setText(f"{s.ram_percent:.0f}%"); self.ram_chip.setText(chip_html(a["ram"].level))
        self.ram_sub.setText(f"Jami {health.gb(s.ram_total)} · ishlatilgan {health.gb(s.ram_used)} · bo'sh {health.gb(s.ram_available)}")
        self.ram_graph.set_values(self.monitor.ram_history, GRAPH_COLOR[a["ram"].level] if a["ram"].level != "good" else "#a78bfa")
        self.ram_why.setText(self._why(a["ram"]))
        # Disk
        self.disk_chip.setText(chip_html(a["disk"].level))
        while len(self.disk_bars) < len(s.disks):
            bar = QProgressBar(); bar.setRange(0, 100); self.disk_bars.append(bar); self.disk_box.addWidget(bar)
        for i, bar in enumerate(self.disk_bars):
            bar.setVisible(i < len(s.disks))
            if i < len(s.disks):
                bar.setValue(int(s.disks[i].percent))
        lines = [f"<b>{html.escape(d.mount)}</b> {health.gb(d.used)} / {health.gb(d.total)} · bo'sh <b>{health.gb(d.free)}</b>" for d in s.disks]
        io = (f"<br><span style='color:#8b93a7'>O'qish {s.disk_read_bps / 1e6:.1f} · yozish {s.disk_write_bps / 1e6:.1f} MB/s</span>"
              if s.disk_read_bps is not None else f"<br><span style='color:#8b93a7'>Disk faolligi: {health.NA}</span>")
        self.disk_body.setText("<br>".join(lines) + io if lines else health.NA); self.disk_why.setText(self._why(a["disk"]))
        # GPU
        self.gpu_chip.setText(chip_html(a["gpu"].level))
        if s.gpus:
            rows = []
            for g in s.gpus:
                rows.append(f"<b>{html.escape(g.name)}</b><br>Yuklanish: {f'{g.util:.0f}%' if g.util is not None else health.NA}"
                            f" · Harorat: {f'{g.temp:.0f}°C' if g.temp is not None else health.NA}<br>Xotira: "
                            + (f"{g.mem_used_mb:.0f} / {g.mem_total_mb:.0f} MB" if g.mem_used_mb is not None and g.mem_total_mb else health.NA)
                            + (f"<br><span style='color:#8b93a7'>{html.escape(g.note)}</span>" if g.note else ""))
            self.gpu_body.setText("<br><br>".join(rows))
        else:
            self.gpu_body.setText(f"Videokarta: {health.NA}")
        self.gpu_why.setText(self._why(a["gpu"]))
        # Batareya
        if s.battery is None:
            self.bat_big.setText("—"); self.bat_chip.setText(""); self.bat_body.setText("Batareya mavjud emas")
        else:
            self.bat_big.setText(f"{s.battery.percent:.0f}%"); self.bat_chip.setText(chip_html(a["battery"].level))
            self.bat_body.setText({True: "Quvvat olmoqda", False: "Quvvat olmayapti (batareyada)", None: "Quvvat holati noma'lum"}[s.battery.plugged])
        self.bat_why.setText(self._why(a["battery"]))
        # Tizim
        ev = (f"<span style='color:#8b93a7'>{health.NA}</span>" if s.events is None else
              "Oxirgi 24 soatda jiddiy xatolar yo'q" if not s.events else
              "<br>".join(f"{html.escape(str(e.get('t')))} · {html.escape(str(e.get('src')))} (#{e.get('id')})" for e in s.events))
        self.sys_body.setText(f"<b>{html.escape(s.os_name)}</b><br>Ishlagan vaqt: {health.fmt_uptime(s.uptime_s)}<br>"
                              f"CPU {s.cpu_percent:.0f}% · RAM {s.ram_percent:.0f}% · "
                              f"Disk {max((d.percent for d in s.disks), default=0):.0f}% (eng band)<br><br>"
                              f"<span style='color:#8b93a7'>TIZIM XATOLARI (System jurnali)</span><br>{ev}")


# ====================================================================== Sozlamalar
class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, on_clear, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sozlamalar"); self.setMinimumWidth(520)
        self.s = settings
        form = QFormLayout()
        self.lang = QComboBox(); [self.lang.addItem(n, v) for n, v in STT_LANGUAGES]
        self.lang.setCurrentIndex(max(0, self.lang.findData(settings.stt_language)))
        self.mic = QComboBox(); self.mic.addItem("Tizim standarti", None)
        for name in audio.list_input_devices():
            self.mic.addItem(name, name)
        self.mic.setCurrentIndex(max(0, self.mic.findData(settings.microphone)))
        self.voice = QCheckBox("Ovozli javobni yoqish"); self.voice.setChecked(settings.voice_enabled)
        self.tts = QComboBox(); [self.tts.addItem(n, v) for n, v in TTS_ENGINES]
        self.tts.setCurrentIndex(max(0, self.tts.findData(settings.tts_engine)))
        self.confirm = QCheckBox("Har bir buyruqdan oldin tasdiq so'rash (tavsiya etiladi)"); self.confirm.setChecked(settings.confirm_commands)
        self.auto = QCheckBox("Windows ishga tushganda avtomatik ochish"); self.auto.setChecked(settings.autostart)
        self.city = QLineEdit(settings.city)
        form.addRow("Ovoz tanish tili:", self.lang); form.addRow("Mikrofon:", self.mic); form.addRow("", self.voice)
        form.addRow("Ovoz mexanizmi:", self.tts); form.addRow("Ob-havo shahri:", self.city)
        form.addRow("", self.confirm); form.addRow("", self.auto)
        self.apps = QListWidget(); self.apps.setMaximumHeight(190)
        for spec in apps.APPS.values():
            it = QListWidgetItem(spec.title); it.setData(Qt.UserRole, spec.id)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if settings.is_app_allowed(spec.id) else Qt.Unchecked)
            self.apps.addItem(it)
        clear = QPushButton("Buyruqlar tarixini tozalash"); clear.clicked.connect(on_clear)
        box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        box.accepted.connect(self.accept); box.rejected.connect(self.reject)
        lay = QVBoxLayout(self); lay.addLayout(form)
        lay.addWidget(QLabel("Ruxsat etilgan dasturlar (belgisi olib tashlansa, buyruq bajarilmaydi):")); lay.addWidget(self.apps)
        lay.addWidget(clear); lay.addWidget(box)

    def apply(self) -> None:
        s = self.s
        s.stt_language, s.microphone = self.lang.currentData(), self.mic.currentData()
        s.voice_enabled, s.tts_engine = self.voice.isChecked(), self.tts.currentData()
        s.confirm_commands, s.autostart = self.confirm.isChecked(), self.auto.isChecked()
        s.city = self.city.text().strip()[:80] or "Tashkent"
        s.allowed_apps = {self.apps.item(i).data(Qt.UserRole): self.apps.item(i).checkState() == Qt.Checked
                          for i in range(self.apps.count())}


# ====================================================================== Asosiy oyna
class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, ctrl: C.Controller, monitor: health.HealthMonitor, speaker):
        super().__init__()
        self.settings, self.ctrl, self.speaker = settings, ctrl, speaker
        ctrl.is_active = lambda: self.isVisible() and not self.isMinimized() and self.isActiveWindow()
        self.log: list[tuple[str, str]] = []
        self.setWindowTitle(APP_NAME); self.resize(1120, 800); self.setMinimumSize(900, 680)
        root = QWidget(); root.setObjectName("root"); self.setCentralWidget(root)
        v = QVBoxLayout(root); v.setContentsMargins(24, 16, 24, 16); v.setSpacing(10)

        top = QHBoxLayout()
        t = QLabel(APP_NAME); t.setObjectName("title"); top.addWidget(t); top.addSpacing(24)
        self.tabs = []
        for i, name in enumerate(("Yordamchi", "Kompyuter holati")):
            b = QPushButton(name); b.setObjectName("tab"); b.setCheckable(True); b.setFocusPolicy(Qt.NoFocus)
            b.clicked.connect(lambda _=False, i=i: self.show_page(i)); top.addWidget(b); self.tabs.append(b)
        top.addStretch()
        self.mic_dot = QLabel(); top.addWidget(self.mic_dot)
        gear = QPushButton("⚙ Sozlamalar"); gear.setFocusPolicy(Qt.NoFocus); gear.clicked.connect(self.open_settings); top.addWidget(gear)
        v.addLayout(top)

        self.stack = QStackedWidget(); v.addWidget(self.stack, 1)
        self.stack.addWidget(self._assistant_page())
        self.health_page = HealthPage(monitor); self.stack.addWidget(self.health_page)
        self.hint = QLabel("Space — tinglashni boshlash/to'xtatish  ·  Enter — tasdiqlash  ·  Esc — bekor qilish  ·  Chatda Enter — yuborish, Shift+Enter — yangi qator")
        self.hint.setObjectName("hint"); v.addWidget(self.hint)

        ctrl.stateChanged.connect(self._on_state); ctrl.message.connect(self.add_message)
        ctrl.level.connect(self.orb.set_level); ctrl.confirmChanged.connect(self._on_confirm)
        speaker.note.connect(lambda m: self.add_message("system", m))
        QApplication.instance().installEventFilter(self)
        self.show_page(0); self._on_state(C.IDLE, C.LABELS[C.IDLE])
        self.add_message("assistant", "Salom! Men ПЯТНИЦА. Space bosib gapiring yoki pastdagi maydonga buyruq yozing. "
                                      "Men faqat sizning buyrug'ingiz bilan va ruxsat etilgan amallarnigina bajaraman.")

    # ---- sahifalar
    def _assistant_page(self) -> QWidget:
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(10)
        row = QHBoxLayout(); row.setSpacing(28)
        self.orb = OrbWidget(); self.orb.setFixedSize(250, 250); row.addWidget(self.orb)
        col = QVBoxLayout(); col.setSpacing(8)
        self.state_lbl = QLabel(); self.state_lbl.setObjectName("state"); col.addWidget(self.state_lbl)
        self.heard = QLabel("Buyruq kutilmoqda…"); self.heard.setObjectName("muted"); self.heard.setWordWrap(True); col.addWidget(self.heard)
        self.confirm_box = QFrame(); self.confirm_box.setObjectName("card"); cb = QHBoxLayout(self.confirm_box)
        self.confirm_lbl = QLabel(); self.confirm_lbl.setWordWrap(True); cb.addWidget(self.confirm_lbl, 1)
        yes = QPushButton("Ha, bajar"); yes.setObjectName("primary"); yes.clicked.connect(self.ctrl.confirm); yes.setFocusPolicy(Qt.NoFocus)
        no = QPushButton("Bekor qilish"); no.clicked.connect(lambda: self.ctrl.cancel()); no.setFocusPolicy(Qt.NoFocus)
        cb.addWidget(yes); cb.addWidget(no); self.confirm_box.hide(); col.addWidget(self.confirm_box)
        ctl = QHBoxLayout()
        self.mic_btn = QPushButton("🎤  Mikrofonni yoqish"); self.mic_btn.setObjectName("primary"); self.mic_btn.setFocusPolicy(Qt.NoFocus)
        self.mic_btn.clicked.connect(self.ctrl.toggle_listening); ctl.addWidget(self.mic_btn)
        ctl.addSpacing(16); ctl.addWidget(QLabel("🔊"))
        self.vol = QSlider(Qt.Horizontal); self.vol.setRange(0, 100); self.vol.setValue(int(self.settings.volume * 100)); self.vol.setFixedWidth(160)
        self.vol.setFocusPolicy(Qt.NoFocus)
        self.vol.valueChanged.connect(lambda x: (self.speaker.set_volume(x / 100), self.settings.save()))
        ctl.addWidget(self.vol); ctl.addStretch(); col.addLayout(ctl); col.addStretch()
        row.addLayout(col, 1); lay.addLayout(row)

        chat = QFrame(); chat.setObjectName("card"); cl = QVBoxLayout(chat); cl.setContentsMargins(12, 12, 12, 12)
        head = QHBoxLayout(); h = QLabel("SUHBAT TARIXI"); h.setObjectName("cardTitle"); head.addWidget(h); head.addStretch()
        clr = QPushButton("Tozalash"); clr.setFocusPolicy(Qt.NoFocus); clr.clicked.connect(self.clear_history); head.addWidget(clr); cl.addLayout(head)
        self.view = QTextBrowser(); self.view.setOpenLinks(False); cl.addWidget(self.view, 1)
        inp = QHBoxLayout(); self.input = ChatInput(); self.input.sendRequested.connect(self.send_text); inp.addWidget(self.input, 1)
        send = QPushButton("Yuborish ➤"); send.setObjectName("primary"); send.setFocusPolicy(Qt.NoFocus); send.clicked.connect(self.send_text)
        inp.addWidget(send, 0, Qt.AlignBottom); cl.addLayout(inp)
        lay.addWidget(chat, 1)
        return page

    def show_page(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        for k, b in enumerate(self.tabs):
            b.setChecked(k == i)

    # ---- chat
    def send_text(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            if self.ctrl.state == C.CONFIRM:
                self.ctrl.confirm()
            return
        if self.ctrl.busy or self.ctrl.state == C.LISTENING:
            self.add_message("system", "Hozir band — iltimos, bir oz kuting yoki tinglashni to'xtating.")
            return
        self.input.clear()
        self.ctrl.submit_text(text)

    def add_message(self, role: str, text: str) -> None:
        self.log.append((role, text))
        if role == "user":
            self.heard.setText(f"Buyruq: «{text}»")
        self._render()

    def _render(self) -> None:
        parts = []
        for role, text in self.log[-300:]:
            body = html.escape(text).replace("\n", "<br>")
            if role == "user":
                parts.append(f"<table align='right' width='78%' cellpadding='9' style='margin:6px 0'><tr><td bgcolor='#0e7490'>{body}</td></tr></table><br clear='all'>")
            elif role == "assistant":
                parts.append(f"<table width='78%' cellpadding='9' style='margin:6px 0'><tr><td bgcolor='#1b1f2a'><b style='color:#22d3ee'>ПЯТНИЦА</b><br>{body}</td></tr></table>")
            else:
                parts.append(f"<p style='color:#8b93a7; font-size:12px'>ⓘ {body}</p>")
        self.view.setHtml("".join(parts))
        self.view.verticalScrollBar().setValue(self.view.verticalScrollBar().maximum())

    def clear_history(self) -> None:
        self.log.clear(); self.heard.setText("Buyruq kutilmoqda…"); self._render()

    # ---- holat
    def _on_state(self, key: str, label: str) -> None:
        self.orb.set_mode(key); self.state_lbl.setText(label)
        rec = key == C.LISTENING
        self.mic_btn.setText("⏹  Tinglashni to'xtatish" if rec else "🎤  Mikrofonni yoqish")
        self.mic_btn.setObjectName("rec" if rec else "primary"); self.mic_btn.style().unpolish(self.mic_btn); self.mic_btn.style().polish(self.mic_btn)
        self.mic_dot.setText("<span style='color:#f87171; font-weight:600'>● MIKROFON YOQIQ</span>" if rec else "<span style='color:#6b7280'>○ Mikrofon o'chiq</span>")
        self.setWindowTitle(f"{APP_NAME} — {label}")

    def _on_confirm(self, need: bool, text: str) -> None:
        self.confirm_box.setVisible(need); self.confirm_lbl.setText(text)

    # ---- tugmalar
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and QApplication.activeWindow() is self:
            key = ev.key()
            typing = isinstance(QApplication.focusWidget(), (QLineEdit, QPlainTextEdit, QTextEdit, QComboBox))
            if key == Qt.Key_Space and not typing:
                if not ev.isAutoRepeat():
                    self.ctrl.toggle_listening()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter) and not typing and self.ctrl.state == C.CONFIRM:
                self.ctrl.confirm(); return True
            if key == Qt.Key_Escape and self.ctrl.state == C.CONFIRM:
                self.ctrl.cancel(); return True
        return super().eventFilter(obj, ev)

    # ---- sozlamalar
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.clear_history, self)
        if dlg.exec() != QDialog.Accepted:
            return
        dlg.apply()
        ok, err = set_autostart(self.settings.autostart)
        if not ok:
            self.settings.autostart = False; self.add_message("system", err)
        self.settings.save()
        self.add_message("system", "Sozlamalar saqlandi.")

    def closeEvent(self, e):
        try:
            QApplication.instance().removeEventFilter(self)
            self.ctrl.shutdown(); self.health_page.monitor.stop(); self.speaker.close()
            self.settings.save()
        finally:
            super().closeEvent(e)
            QApplication.instance().quit()
