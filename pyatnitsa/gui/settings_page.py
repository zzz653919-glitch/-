"""Sozlamalar sahifasi (oldingi dialog o'rniga): saqlash bosilganda qo'llanadi."""
from __future__ import annotations

import copy
import html
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QProgressBar, QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import apps, audio, stt, voice_test
from ..i18n import T, app_title, has
from ..settings import STT_LANGUAGES, TTS_ENGINES, Settings
from .pages import page_header
from .theme import C


class SettingsPage(QWidget):
    saved = Signal()
    clearHistory = Signal()
    clearChat = Signal()

    _level = Signal(float)
    _test_done = Signal(object)

    def __init__(self, settings: Settings, can_test=lambda: (True, "")):
        super().__init__()
        self.s = settings
        self._can_test = can_test
        self._stop_test = threading.Event()
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        top = QHBoxLayout(); top.addLayout(page_header("SETTINGS", "Changes are applied when you press Save."), 1)
        self.save_btn = QPushButton("Save"); self.save_btn.setObjectName("primary"); self.save_btn.clicked.connect(self.save)
        top.addWidget(self.save_btn, 0, Qt.AlignTop); lay.addLayout(top)
        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        host = QFrame(); host.setObjectName("panel"); form = QFormLayout(host); form.setContentsMargins(20, 16, 20, 16); form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        scroll.setWidget(host); lay.addWidget(scroll, 1)

        self.lang = QComboBox(); [self.lang.addItem(n, v) for n, v in STT_LANGUAGES]
        self.mic = QComboBox()
        self.voice = QCheckBox("Spoken replies"); self.gender = QComboBox(); self.gender.addItem("Male voice", "male"); self.gender.addItem("Female voice", "female")
        self.engine = QComboBox(); self.engine.addItem("Google (online, fast)", "google"); self.engine.addItem("Whisper (offline, better Uzbek — optional install)", "whisper")
        self.whisper = QComboBox(); [self.whisper.addItem(n, n) for n in stt.WHISPER_SIZES]
        self.autostop = QCheckBox("Stop listening automatically after ~2 s of silence (SPACE still works)")
        self.tts = QComboBox(); [self.tts.addItem(n, v) for n, v in TTS_ENGINES]
        self.confirm = QCheckBox("Ask for confirmation before every command (recommended)")
        self.motion = QComboBox(); self.motion.addItem("Follow Windows setting", "system"); self.motion.addItem("Reduce motion", "on"); self.motion.addItem("Full animations", "off")
        self.terminal = QCheckBox("Show command terminal on the Assistant page")
        self.auto = QCheckBox("Start with Windows"); self.city = QLineEdit()
        form.addRow("Speech language", self.lang); form.addRow("Speech engine", self.engine); form.addRow("Whisper model", self.whisper)
        form.addRow("Microphone", self.mic); form.addRow("", self.autostop); form.addRow("", self.voice); form.addRow("Voice", self.gender)
        form.addRow("Voice engine", self.tts); form.addRow("Weather city", self.city); form.addRow("Animations", self.motion)
        form.addRow("", self.terminal); form.addRow("", self.confirm); form.addRow("", self.auto)
        # ---- mikrofon testi: yozadi, sifatni o'lchaydi, tanigan matn va tushunilgan amalni ko'rsatadi (hech narsa bajarilmaydi)
        self.test_btn = QPushButton("Test microphone (4 s)"); self.test_btn.setObjectName("primary"); self.test_btn.clicked.connect(self.run_test)
        self.test_level = QProgressBar(); self.test_level.setRange(0, 100); self.test_level.setTextVisible(False)
        self.test_out = QLabel("Press the button, then say a command such as “Open Chrome”. The result is only displayed — nothing is executed.")
        self.test_out.setObjectName("sub"); self.test_out.setWordWrap(True); self.test_out.setTextFormat(Qt.RichText)
        self.test_out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        tl = QLabel("MICROPHONE TEST"); tl.setObjectName("section")
        form.addRow(tl); form.addRow(self.test_btn); form.addRow(self.test_level); form.addRow(self.test_out)
        self._level.connect(lambda v: self.test_level.setValue(int(v * 100)))
        self._test_done.connect(self._show_report)
        hint = QLabel("Allowed actions (unchecked = refused):"); hint.setObjectName("sub"); form.addRow(hint)
        self.apps = QListWidget(); self.apps.setMinimumHeight(190)
        for spec in apps.APPS.values():
            it = QListWidgetItem(app_title(spec.id, "en")); it.setData(Qt.UserRole, spec.id); it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            self.apps.addItem(it)
        form.addRow(self.apps)
        btns = QHBoxLayout()
        for text, sig in (("Clear command history", self.clearHistory), ("Clear conversation", self.clearChat)):
            b = QPushButton(text); b.clicked.connect(sig.emit); btns.addWidget(b)
        btns.addStretch(1); form.addRow(btns)
        self.load()

    def load(self) -> None:
        s = self.s
        self.mic.clear(); self.mic.addItem("System default", None)
        for name in audio.list_input_devices():
            self.mic.addItem(name, name)
        self.engine.setCurrentIndex(max(0, self.engine.findData(s.stt_engine))); self.whisper.setCurrentIndex(max(0, self.whisper.findData(s.whisper_model)))
        self.autostop.setChecked(s.auto_stop_silence)
        self.lang.setCurrentIndex(max(0, self.lang.findData(s.stt_language))); self.mic.setCurrentIndex(max(0, self.mic.findData(s.microphone)))
        self.voice.setChecked(s.voice_enabled); self.gender.setCurrentIndex(max(0, self.gender.findData(s.voice_gender)))
        self.tts.setCurrentIndex(max(0, self.tts.findData(s.tts_engine))); self.confirm.setChecked(s.confirm_commands)
        self.motion.setCurrentIndex(max(0, self.motion.findData(s.reduce_motion))); self.terminal.setChecked(s.show_terminal)
        self.auto.setChecked(s.autostart); self.city.setText(s.city)
        for i in range(self.apps.count()):
            it = self.apps.item(i)
            it.setCheckState(Qt.Checked if s.is_app_allowed(it.data(Qt.UserRole)) else Qt.Unchecked)

    def collect(self, s: Settings) -> Settings:
        """Formadagi qiymatlarni `s` ga yozadi (saqlamaydi)."""
        s.stt_language, s.microphone = self.lang.currentData(), self.mic.currentData()
        s.stt_engine, s.whisper_model, s.auto_stop_silence = self.engine.currentData(), self.whisper.currentData(), self.autostop.isChecked()
        s.voice_enabled, s.voice_gender, s.tts_engine = self.voice.isChecked(), self.gender.currentData(), self.tts.currentData()
        s.confirm_commands, s.autostart = self.confirm.isChecked(), self.auto.isChecked()
        s.reduce_motion, s.show_terminal = self.motion.currentData(), self.terminal.isChecked()
        s.city = self.city.text().strip()[:80] or "Tashkent"
        s.allowed_apps = {self.apps.item(i).data(Qt.UserRole): self.apps.item(i).checkState() == Qt.Checked for i in range(self.apps.count())}
        return s

    def save(self) -> None:
        self.collect(self.s)
        self.saved.emit()

    # ---- mikrofon testi
    def run_test(self) -> None:
        ok, why = self._can_test()
        if not ok:
            self.test_out.setText(f"<span style='color:#ffb020'>{html.escape(why)}</span>")
            return
        trial = self.collect(copy.copy(self.s))             # hozirgi (hali saqlanmagan) tanlovlar bilan sinaydi
        self.test_btn.setEnabled(False); self.test_btn.setText("Recording… speak now")
        self.test_out.setText("Recording for 4 seconds…")
        self._stop_test.clear()

        def work():
            try:
                rep = voice_test.run_mic_test(trial, 4.0, self._level.emit, self._stop_test)
            except Exception as e:  # noqa: BLE001
                rep = voice_test.MicReport(error_key="stt.failed", error_detail=f"{type(e).__name__}: {e}")
            self._test_done.emit(rep)
        threading.Thread(target=work, name="mic-test", daemon=True).start()

    def _show_report(self, r: "voice_test.MicReport") -> None:
        self.test_btn.setEnabled(True); self.test_btn.setText("Test microphone (4 s)"); self.test_level.setValue(0)
        rows = []
        def row(k, v, color="#e8f1ff"):
            rows.append(f"<tr><td style='color:#8aa0bd;padding-right:12px'>{k}</td><td style='color:{color}'>{html.escape(str(v))}</td></tr>")
        if r.device:
            row("Device", f"{r.device} · {r.rate} Hz · mono 16-bit")
        q = r.quality
        if q:
            row("Recorded", f"{r.seconds:.1f} s · speech detected: {q.speech_s:.1f} s")
            lvl_ok = q.peak_db > -36
            row("Level", f"peak {q.peak_db:.0f} dBFS · noise {q.noise_db:.0f} dBFS" + ("" if lvl_ok else "  — quiet (will be boosted)"), "#e8f1ff" if lvl_ok else "#ffb020")
            if q.clipped:
                row("Clipping", "the signal clips — lower the input volume", "#ffb020")
        if r.error_key:
            msg = T(r.error_key, "en", detail=r.error_detail[:200]) if has(r.error_key) else r.error_key
            row("Result", msg, "#ff4d6d" if r.error_key.startswith(("mic.", "stt.network", "stt.failed")) else "#ffb020")
        else:
            row("Engine", f"{r.engine} · language: {r.language}")
            row("Recognized", f"“{r.text}”", "#2ee6a6")
            others = [f"{h.lang}: {h.text}" for h in r.candidates if h.text != r.text][:3]
            if others:
                row("Alternatives", " | ".join(others), "#8aa0bd")
            row("Interpreted as", r.interpretation + "  (not executed)", "#00e5ff")
        self.test_out.setText("<table>" + "".join(rows) + "</table>")
