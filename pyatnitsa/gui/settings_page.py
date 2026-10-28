"""Sozlamalar sahifasi (oldingi dialog o'rniga): saqlash bosilganda qo'llanadi."""
from __future__ import annotations

import copy
import html
import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFileDialog, QSlider, QSpinBox, QProgressBar, QCheckBox, QComboBox, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .. import ai_chat, apps, audio, credentials, stt, voice_test
from ..i18n import T, app_title, has
from ..settings import STT_LANGUAGES, TTS_ENGINES, Settings
from . import common
from .pages import page_header


class SettingsPage(QWidget):
    saved = Signal()
    clearHistory = Signal()
    clearChat = Signal()
    openFilesPage = Signal()
    dataCleared = Signal(str)

    _level = Signal(float)
    _status = Signal(str)
    _activity = Signal(bool)
    _test_done = Signal(object)
    _ai_test_done = Signal(object)

    def __init__(self, settings: Settings, can_test=lambda: (True, ""), ai=None, ex=None):
        super().__init__()
        self.s = settings
        self._can_test = can_test
        self._ai = ai
        self._ex = ex
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
        self.test_state = QLabel(); self.test_state.setObjectName("sub"); self.test_state.setTextFormat(Qt.RichText)
        self.dev_btn = QPushButton("List input devices"); self.dev_btn.clicked.connect(self.show_devices)
        self.dev_out = QLabel(); self.dev_out.setObjectName("sub"); self.dev_out.setWordWrap(True); self.dev_out.setTextFormat(Qt.RichText)
        self.dev_out.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(tl); form.addRow(self.dev_btn); form.addRow(self.dev_out)
        form.addRow(self.test_btn); form.addRow(self.test_state); form.addRow(self.test_level); form.addRow(self.test_out)
        self._level.connect(lambda v: self.test_level.setValue(int(v * 100)))
        self._status.connect(self._set_status); self._activity.connect(self._set_activity)
        self._state, self._speech = "idle", False
        self._set_status("idle")
        self._test_done.connect(self._show_report)
        # ---- Ruxsatlar (aniq va halol: nima qachon ishlatiladi)
        pl = QLabel("PERMISSIONS"); pl.setObjectName("section"); form.addRow(pl)
        self.perm_mic = QLabel("Microphone: opens only while you hold SPACE (or press the microphone button) and closes when you release it. There is no background listening; recordings are never saved.")
        self.perm_clip = QLabel("Clipboard: never read or changed by Пятница.")
        self.perm_net = QLabel("Network: only what you use — the AI service (when enabled and a key is set), exchange rate and weather commands, and web searches you ask for. Notes, tasks, reminders and study data stay on this computer.")
        for lb in (self.perm_mic, self.perm_clip, self.perm_net):
            lb.setObjectName("sub"); lb.setWordWrap(True); form.addRow(lb)
        self.notify = QCheckBox("Show desktop notifications for reminders (Windows system tray; in-app banners always appear)")
        form.addRow("", self.notify)
        # ---- Mahalliy ma'lumotlar
        dl = QLabel("LOCAL DATA"); dl.setObjectName("section"); form.addRow(dl)
        self.data_info = QLabel(); self.data_info.setObjectName("sub"); self.data_info.setWordWrap(True); self.data_info.setTextFormat(Qt.PlainText)
        self.data_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form.addRow(self.data_info)
        self.data_msg = QLabel(); self.data_msg.setObjectName("sub"); self.data_msg.setWordWrap(True); self.data_msg.setTextFormat(Qt.PlainText)
        self.clear_btns = {}
        for key, label in (("reminders", "Clear all reminders…"), ("tasks", "Clear all tasks…"), ("notes", "Clear all notes…"), ("study", "Clear study progress…")):
            b = QPushButton(label); b.clicked.connect(lambda _=False, k=key: self.clear_data(k)); self.clear_btns[key] = b; form.addRow(b)
        self.export_btn = QPushButton("Export a backup copy of my data…"); self.export_btn.clicked.connect(self.export_backup); form.addRow(self.export_btn)
        form.addRow(self.data_msg)
        self.refresh_data()
        # ---- File Access (qisqa ko'rinish; boshqarish — «File Finder» sahifasida)
        fl = QLabel("FILE ACCESS"); fl.setObjectName("section"); form.addRow(fl)
        self.files_info = QLabel(); self.files_info.setObjectName("sub"); self.files_info.setWordWrap(True); self.files_info.setTextFormat(Qt.PlainText)
        self.files_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.files_btn = QPushButton("Manage in File Access…"); self.files_btn.clicked.connect(self.openFilesPage.emit)
        form.addRow(self.files_info); form.addRow(self.files_btn)
        self.refresh_files()
        # ---- AI Chat
        al = QLabel("AI CHAT"); al.setObjectName("section"); form.addRow(al)
        self.ai_on = QCheckBox("Enable AI conversation (questions, explanations, follow-ups)")
        self.ai_model = QComboBox(); self.ai_model.setEditable(True)
        for m in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
            self.ai_model.addItem(m)
        self.ai_effort = QComboBox(); [self.ai_effort.addItem(t, v) for t, v in (("Low — fastest (recommended for chat)", "low"), ("Medium", "medium"), ("High — deeper, slower", "high"))]
        self.ai_ctx = QSpinBox(); self.ai_ctx.setRange(2, 60); self.ai_ctx.setSuffix(" messages")
        self.ai_tokens = QSpinBox(); self.ai_tokens.setRange(256, 32000); self.ai_tokens.setSingleStep(256)
        self.ai_timeout = QSpinBox(); self.ai_timeout.setRange(10, 300); self.ai_timeout.setSuffix(" s")
        self.ai_fb = QCheckBox("Server-side fallback when a request is declined (Opus models only)")
        self.ai_key = QLineEdit(); self.ai_key.setEchoMode(QLineEdit.Password); self.ai_key.setPlaceholderText("Paste API key here, then press “Save key”")
        self.ai_key_status = QLabel(); self.ai_key_status.setObjectName("sub"); self.ai_key_status.setWordWrap(True); self.ai_key_status.setTextFormat(Qt.RichText)
        kb = QHBoxLayout(); sk = QPushButton("Save key"); sk.clicked.connect(self._save_key); rk = QPushButton("Remove saved key"); rk.clicked.connect(self._remove_key)
        kb.addWidget(sk); kb.addWidget(rk); kb.addStretch(1)
        self.ai_test_btn = QPushButton("Test AI connection"); self.ai_test_btn.clicked.connect(self._test_ai)
        self.ai_test_out = QLabel("Sends one tiny test message to the provider using your key."); self.ai_test_out.setObjectName("sub"); self.ai_test_out.setWordWrap(True)
        self.ai_test_out.setTextFormat(Qt.RichText)
        priv = QLabel("Privacy: with AI chat on, the TEXT of your conversation messages is sent to Anthropic. Microphone audio and computer commands are not sent to the AI. "
                      "History is kept in memory only and is cleared with the Clear button.")
        priv.setObjectName("dim"); priv.setWordWrap(True)
        form.addRow("", self.ai_on); form.addRow("Model", self.ai_model); form.addRow("Thinking effort", self.ai_effort); form.addRow("Context size", self.ai_ctx)
        form.addRow("Max answer length", self.ai_tokens); form.addRow("Timeout", self.ai_timeout); form.addRow("", self.ai_fb)
        form.addRow("API key", self.ai_key); form.addRow("", kb); form.addRow("", self.ai_key_status); form.addRow(self.ai_test_btn); form.addRow(self.ai_test_out); form.addRow(priv)
        self.rate = QSlider(Qt.Horizontal); self.rate.setRange(-50, 50); self.rate.setSingleStep(5)
        self.rate_lbl = QLabel(); self.rate.valueChanged.connect(lambda v: self.rate_lbl.setText(f"{v:+d}%"))
        rr = QHBoxLayout(); rr.addWidget(self.rate, 1); rr.addWidget(self.rate_lbl)
        form.addRow("Speech rate", rr)
        self._ai_test_done.connect(self._show_ai_test)
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
        self.auto.setChecked(s.autostart); self.city.setText(s.city); self.notify.setChecked(s.notifications)
        self.ai_on.setChecked(s.ai_enabled); self.ai_model.setCurrentText(s.ai_model or ai_chat.DEFAULT_MODEL)
        self.ai_effort.setCurrentIndex(max(0, self.ai_effort.findData(s.ai_effort))); self.ai_ctx.setValue(s.ai_context_messages)
        self.ai_tokens.setValue(s.ai_max_tokens); self.ai_timeout.setValue(s.ai_timeout_s); self.ai_fb.setChecked(s.ai_fallback)
        self.rate.setValue(s.voice_rate); self.rate_lbl.setText(f"{s.voice_rate:+d}%"); self._refresh_key_status()
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
        s.ai_enabled, s.ai_effort, s.ai_context_messages = self.ai_on.isChecked(), self.ai_effort.currentData(), self.ai_ctx.value()
        model = self.ai_model.currentText().strip()
        s.ai_model = "" if model == ai_chat.DEFAULT_MODEL else model
        s.ai_max_tokens, s.ai_timeout_s, s.ai_fallback, s.voice_rate = self.ai_tokens.value(), self.ai_timeout.value(), self.ai_fb.isChecked(), self.rate.value()
        s.notifications = self.notify.isChecked()
        s.allowed_apps = {self.apps.item(i).data(Qt.UserRole): self.apps.item(i).checkState() == Qt.Checked for i in range(self.apps.count())}
        return s

    def save(self) -> None:
        self.collect(self.s)
        self.saved.emit()

    # ---- AI kalit va ulanish testi
    def _refresh_key_status(self) -> None:
        key, source = credentials.get_api_key()
        if key:
            where = {"file": "the private secrets file", }.get(source, f"environment variable {source.split(':', 1)[-1]}")
            self.ai_key_status.setText(f"<span style='color:#2ee6a6'>● API key configured</span> — from {where}. The key is never shown or logged.")
        else:
            self.ai_key_status.setText("<span style='color:#ffb020'>● No API key configured.</span> Get one at console.anthropic.com, paste it above and press “Save key”, "
                                       "or set the ANTHROPIC_API_KEY environment variable and restart.")

    def _save_key(self) -> None:
        try:
            credentials.save_api_key(self.ai_key.text())
        except ValueError as e:
            self.ai_key_status.setText(f"<span style='color:#ff4d6d'>{html.escape(str(e))}</span>")
            return
        self.ai_key.clear()
        self._refresh_key_status()

    def _remove_key(self) -> None:
        credentials.clear_api_key()
        self._refresh_key_status()

    def _test_ai(self) -> None:
        trial = self.collect(copy.copy(self.s))
        self.ai_test_btn.setEnabled(False); self.ai_test_out.setText("Contacting the AI service…")

        def work():
            try:
                rep = ai_chat.ChatClient(trial).test_connection()
                self._ai_test_done.emit(("ok", f"Connected · model {rep.model or trial.ai_model or ai_chat.DEFAULT_MODEL} · {rep.seconds:.1f}s"))
            except ai_chat.AIError as e:
                self._ai_test_done.emit((e.kind, T(f"ai.err.{e.kind}", "en", detail=e.detail[:200], wait="")))
            except Exception as e:  # noqa: BLE001
                self._ai_test_done.emit(("unknown", f"{type(e).__name__}: {credentials.redact(str(e))[:200]}"))
        threading.Thread(target=work, name="ai-test", daemon=True).start()

    def _show_ai_test(self, res) -> None:
        self.ai_test_btn.setEnabled(True)
        kind, msg = res
        color = "#2ee6a6" if kind == "ok" else "#ff4d6d"
        self.ai_test_out.setText(f"<span style='color:{color}'>{html.escape(msg)}</span>")

    # ---- mahalliy ma'lumotlar: hisob, tozalash, zaxira
    def refresh_data(self) -> None:
        if self._ex is None:
            self.data_info.setText("Local data store is not available.")
            for b in (*self.clear_btns.values(), self.export_btn):
                b.setEnabled(False)
            return
        db, c = self._ex.db, self._ex.db.counts()
        where = str(db.path) if db.path else "memory only (not saved)"
        self.data_info.setText(f"Stored locally: {c['reminders']} reminder(s), {c['tasks']} task(s), {c['notes']} note(s), {c['study_log']} study record(s), {c['study_items']} study item(s).\n"
                               f"Database: {where} (schema v{db.user_version()}). A backup copy is made automatically before any upgrade of the database."
                               + (f"\n{db.notice}" if db.notice else ""))

    def clear_data(self, key: str) -> None:
        if self._ex is None:
            return
        ex = self._ex
        label, n, run = {"reminders": ("reminders", len(ex.reminders.all()), ex.reminders.clear), "tasks": ("tasks", len(ex.tasks.all()), ex.tasks.clear),
                         "notes": ("notes", len(ex.notes.all()), ex.notes.clear), "study": ("study records and difficult-word items", len(ex.study.history(100000)) + len(ex.study.items()), ex.study.clear_progress)}[key]
        if n == 0:
            common.status_style(self.data_msg, f"There are no {label} to clear.", "neutral")
            return
        if not common.ask(self, "Clear local data", f"Permanently delete {n} {label}?\n\nThis cannot be undone. Consider exporting a backup first.", yes="Delete everything"):
            return
        run()
        common.status_style(self.data_msg, f"Deleted: {label}.", "ok")
        self.refresh_data()
        self.dataCleared.emit(key if key != "study" else "study")

    def export_backup(self) -> None:
        if self._ex is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export backup", "pyatnitsa-backup.db", "SQLite database (*.db)")
        if not path:
            return
        try:
            self._ex.db.backup_to(path)
        except Exception as e:  # noqa: BLE001
            common.status_style(self.data_msg, f"Backup failed: {type(e).__name__}: {e}", "err")
            return
        common.status_style(self.data_msg, f"Backup saved: {path}", "ok")

    def refresh_files(self) -> None:
        roots = self.s.file_roots
        self.files_info.setText("Пятница can access only these locations (nothing else on this computer):\n" + "\n".join(f"• {r}" for r in roots) if roots
                                else "No folders are authorized. Пятница cannot search or open any of your files until you add a folder.")

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
        self._speech = False

        def work():
            try:
                rep = voice_test.run_mic_test(trial, 4.0, self._level.emit, self._stop_test,
                                              on_status=self._status.emit, on_activity=self._activity.emit)
            except Exception as e:  # noqa: BLE001
                rep = voice_test.MicReport(error_key="stt.failed", error_detail=f"{type(e).__name__}: {e}")
            self._test_done.emit(rep)
        threading.Thread(target=work, name="mic-test", daemon=True).start()

    _STATE_COLOR = {"idle": "#8aa0bd", "recording": "#ff4d6d", "processing": "#ffb020"}

    def _set_status(self, state: str) -> None:
        self._state = state
        self._render_status()

    def _set_activity(self, on: bool) -> None:
        self._speech = on
        self._render_status()

    def _render_status(self) -> None:
        label = {"idle": "Idle", "recording": "Recording", "processing": "Processing"}.get(self._state, self._state)
        speech = ""
        if self._state == "recording":
            speech = "  ·  <span style='color:%s'>%s</span>" % (("#2ee6a6", "speech detected") if self._speech else ("#8aa0bd", "no speech"))
        self.test_state.setText(f"Status: <span style='color:{self._STATE_COLOR.get(self._state, '#8aa0bd')}'>● {label}</span>{speech}")

    def show_devices(self) -> None:
        """Barcha kirish qurilmalari indeks bilan; loopback / Stereo Mix belgilanadi (u mikrofon emas, ilova uni tanlamaydi)."""
        try:
            rows = voice_test.device_table(self.mic.currentData())
        except audio.AudioError as e:
            msg = T(e.key, "en", detail=e.detail[:200]) if has(e.key) else e.key
            self.dev_out.setText(f"<span style='color:#ff4d6d'>{html.escape(msg)}</span>")
            return
        if not rows:
            self.dev_out.setText("<span style='color:#ff4d6d'>No input devices found. Check Windows → Settings → System → Sound → Input.</span>")
            return
        out = ["<table cellspacing='4'><tr style='color:#8aa0bd'><td>#</td><td>Device</td><td>API</td><td>Ch</td><td></td></tr>"]
        for r in rows:
            loop = r["kind"] == "loopback"
            note = []
            if r["default"]:
                note.append("Windows default")
            if r["used"]:
                note.append("IN USE")
            if loop:
                note.append("LOOPBACK — not a microphone, never used")
            color = "#ff4d6d" if loop else ("#2ee6a6" if r["used"] else "#e8f1ff")
            out.append(f"<tr style='color:{color}'><td>{r['index']}</td><td>{html.escape(r['name'])}</td><td>{html.escape(r['hostapi'])}</td>"
                       f"<td>{r['channels']}</td><td>{html.escape(' · '.join(note))}</td></tr>")
        out.append("</table>")
        used = next((r for r in rows if r["used"]), None)
        if used is None:
            out.append("<span style='color:#ff4d6d'>No physical microphone found (only loopback devices).</span>")
        elif used["warning"] in ("default_loopback", "selected_loopback"):
            out.append("<span style='color:#ffb020'>The Windows default / selected input is a loopback device — the app uses the microphone above instead.</span>")
        self.dev_out.setText("".join(out))

    def _show_report(self, r: "voice_test.MicReport") -> None:
        self.test_btn.setEnabled(True); self.test_btn.setText("Test microphone (4 s)"); self.test_level.setValue(0)
        rows = []
        def row(k, v, color="#e8f1ff"):
            rows.append(f"<tr><td style='color:#8aa0bd;padding-right:12px'>{k}</td><td style='color:{color}'>{html.escape(str(v))}</td></tr>")
        if r.device:
            idx = f"#{r.device_index} · " if r.device_index is not None else ""
            row("Device", f"{idx}{r.device} · {r.rate} Hz · 16-bit · stream opened in {r.open_ms:.0f} ms")
            if r.default_device and r.default_device != r.device:
                row("Windows default", r.default_device, "#ffb020")
            if r.warning in ("default_loopback", "selected_loopback"):
                row("Warning", "the Windows default / selected input is a loopback (system-audio) device, not a microphone — it was skipped", "#ffb020")
        q = r.quality
        if q:
            row("Recorded", f"{r.seconds:.1f} s · speech detected: {q.speech_s:.1f} s · live activity {r.activity * 100:.0f}%")
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
