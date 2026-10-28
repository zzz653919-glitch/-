"""Asosiy oyna: chap navigatsiya | markaz (AI Core, suhbat, terminal) | o'ng jonli monitoring. Barcha boshqaruvlar haqiqiy funksiyalarga ulangan."""
from __future__ import annotations

import html

from PySide6.QtCore import QEasingCurve, QEvent, QPropertyAnimation, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import (QApplication, QComboBox, QFrame, QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
                               QLineEdit, QMainWindow, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea, QSlider, QSpinBox, QStackedWidget,
                               QSystemTrayIcon, QTextEdit, QVBoxLayout, QWidget)

from .. import APP_NAME, __version__, controller as C, health, motion
from ..settings import Settings, set_autostart
from .chat import ChatView
from .core_widget import AICore
from .dashboard_page import DashboardPage
from .files_page import FilesPage
from .notes_page import NotesPage
from .reminders_page import RemindersPage
from .study_page import StudyPage
from .tasks_page import TasksPage
from .icons import icon
from .monitor_view import MetricsView, MonitorBridge
from .pages import AboutPage, DiagnosticsPage, HistoryPage, page_header
from .settings_page import SettingsPage
from .terminal import TerminalPanel
from .theme import C as COL, LEVEL_COLORS, STATE_COLORS, STATE_LABELS
from .widgets import ChatInput, VoiceBars

STATE_HINT = {
    "standby": "Press SPACE to speak, or type a command",
    "listening": "Microphone is live — press SPACE again when you finish",
    "processing": "Converting speech to text…",
    "interpreting": "Analyzing the command…",
    "thinking": "Thinking — waiting for the AI model…",
    "speaking": "Speaking the answer — press SPACE to interrupt",
    "confirm": "Waiting for your confirmation — Enter to run, Esc to cancel",
    "executing": "Executing the command…",
    "responding": "Writing the answer…",
    "error": "Something went wrong — details are in the conversation and terminal",
}
PAGES = [("dashboard", "Home"), ("assistant", "AI Assistant"), ("files", "File Finder"), ("reminders", "Reminders"), ("tasks", "Tasks"), ("notes", "Notes"),
         ("study", "English Study"), ("history", "Command History"), ("monitor", "System Monitoring"), ("diagnostics", "Diagnostics"),
         ("settings", "Settings & Permissions"), ("about", "About")]
DATA_PAGES = ("dashboard", "reminders", "tasks", "notes", "study")


class Backdrop(QWidget):
    """Qora-grafit fon: yumshoq cyan nur va juda xira to'r (o'lchamga qarab bir marta chiziladi)."""

    def __init__(self):
        super().__init__()
        self.setObjectName("root")
        self._pm: QPixmap | None = None

    def resizeEvent(self, e):
        self._pm = None
        super().resizeEvent(e)

    def paintEvent(self, e):
        if self._pm is None or self._pm.size() != self.size():
            pm = QPixmap(self.size()); p = QPainter(pm)
            g = QLinearGradient(0, 0, 0, self.height()); g.setColorAt(0, QColor(COL["bg1"])); g.setColorAt(1, QColor(COL["bg0"]))
            p.fillRect(pm.rect(), g)
            r = QRadialGradient(self.width() * 0.5, self.height() * 0.28, max(self.width(), self.height()) * 0.55)
            r.setColorAt(0, QColor(0, 229, 255, 26)); r.setColorAt(0.6, QColor(41, 121, 255, 10)); r.setColorAt(1, QColor(0, 0, 0, 0))
            p.fillRect(pm.rect(), r)
            p.setPen(QPen(QColor(120, 170, 255, 9), 1))
            for x in range(0, self.width(), 48):
                p.drawLine(x, 0, x, self.height())
            for y in range(0, self.height(), 48):
                p.drawLine(0, y, self.width(), y)
            p.end(); self._pm = pm
        QPainter(self).drawPixmap(0, 0, self._pm)


class NavButton(QPushButton):
    def __init__(self, key: str, text: str):
        super().__init__(text)
        self.key, self.full_text = key, text
        self.setObjectName("nav"); self.setCheckable(True); self.setFocusPolicy(Qt.NoFocus); self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(text); self.setIconSize(self.iconSize().expandedTo(self.iconSize()))
        self.set_active(False)

    def set_active(self, on: bool) -> None:
        self.setIcon(icon(self.key, COL["cyan"] if on else COL["muted"], 22))

    def set_compact(self, compact: bool) -> None:
        self.setText("" if compact else self.full_text)


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings, ctrl: C.Controller, monitor: health.HealthMonitor, speaker):
        super().__init__()
        self.settings, self.ctrl, self.speaker, self.monitor = settings, ctrl, speaker, monitor
        self.reduced = motion.reduced(settings.reduce_motion)
        self._started = False
        self._compact = False
        self.setWindowTitle(APP_NAME); self.resize(1360, 860); self.setMinimumSize(980, 660)
        ctrl.is_active = lambda: self.isVisible() and not self.isMinimized() and self.isActiveWindow()
        self.bridge = MonitorBridge(monitor)

        root = Backdrop(); self.setCentralWidget(root)
        h = QHBoxLayout(root); h.setContentsMargins(0, 0, 0, 0); h.setSpacing(0)
        h.addWidget(self._build_sidebar())
        center = QWidget(); cv = QVBoxLayout(center); cv.setContentsMargins(0, 0, 0, 0); cv.setSpacing(0)
        self.toast_area = QVBoxLayout(); self.toast_area.setContentsMargins(26, 10, 22, 0); self.toast_area.setSpacing(6)
        cv.addLayout(self.toast_area)
        self.stack = QStackedWidget(); cv.addWidget(self.stack, 1)
        h.addWidget(center, 1)
        self._toasts: list[QFrame] = []
        self._tray = None
        self._build_pages()
        h.addWidget(self._build_rightbar())

        self._wire()
        self.show_page("dashboard", animate=False)
        self._tick = QTimer(self, interval=60_000)              # sana, "kechikkan" belgilari va hisoblar yangilanib turadi
        self._tick.timeout.connect(lambda: self._refresh_page(self.current))
        self._tick.start()
        self._on_state()
        QApplication.instance().installEventFilter(self)
        ctrl.log_event("info", "SYSTEM", "Assistant initialized")

    # ======================================================================= qurilish
    def _build_sidebar(self) -> QFrame:
        self.sidebar = QFrame(); self.sidebar.setObjectName("sidebar"); self.sidebar.setFixedWidth(214)
        v = QVBoxLayout(self.sidebar); v.setContentsMargins(0, 18, 0, 14); v.setSpacing(2)
        self.brand = QLabel("AI CONTROL SYSTEM"); self.brand.setObjectName("section"); self.brand.setContentsMargins(18, 0, 0, 12); v.addWidget(self.brand)
        self.navs: dict[str, NavButton] = {}
        for key, text in PAGES:
            b = NavButton(key, text); b.clicked.connect(lambda _=False, k=key: self.show_page(k)); v.addWidget(b); self.navs[key] = b
        v.addStretch(1)
        self.ver = QLabel(f"v{__version__}"); self.ver.setObjectName("dim"); self.ver.setContentsMargins(18, 0, 0, 0); v.addWidget(self.ver)
        return self.sidebar

    def _build_pages(self) -> None:
        self.pages: dict[str, QWidget] = {}
        self.history = HistoryPage()
        self.diag = DiagnosticsPage(self.monitor, on_event=self.ctrl.log_event)
        self.settings_page = SettingsPage(self.settings, can_test=self._can_test_mic, ai=self.ctrl.ai, ex=self.ctrl.executor)
        ex = self.ctrl.executor
        self.dashboard = DashboardPage(ex); self.reminders_page = RemindersPage(ex); self.tasks_page = TasksPage(ex); self.notes_page = NotesPage(ex); self.study_page = StudyPage(ex)
        self.data_pages = {"dashboard": self.dashboard, "reminders": self.reminders_page, "tasks": self.tasks_page, "notes": self.notes_page, "study": self.study_page}
        self.files_page = FilesPage(self.ctrl.executor.files, self.ctrl.executor.platform, self.settings, open_cb=self.ctrl.open_path, log_cb=self.ctrl.log_event)
        self.monitor_view = MetricsView(self.bridge, compact=False)
        mon = QWidget(); ml = QVBoxLayout(mon); ml.setContentsMargins(0, 0, 0, 0); ml.setSpacing(12)
        ml.addLayout(page_header("SYSTEM MONITORING", "Live values read from this computer. “Unavailable / Not supported” means the sensor or driver does not provide it."))
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setWidget(self.monitor_view); ml.addWidget(sa, 1)
        for key, widget in (("dashboard", self.dashboard), ("assistant", self._build_assistant()), ("files", self.files_page), ("reminders", self.reminders_page),
                            ("tasks", self.tasks_page), ("notes", self.notes_page), ("study", self.study_page), ("history", self.history), ("monitor", mon),
                            ("diagnostics", self.diag), ("settings", self.settings_page), ("about", AboutPage())):
            host = QWidget(); hl = QVBoxLayout(host); hl.setContentsMargins(26, 20, 22, 18); hl.addWidget(widget)
            self.stack.addWidget(host); self.pages[key] = host

    def _build_assistant(self) -> QWidget:
        page = QWidget(); lay = QVBoxLayout(page); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        # ---- markaz: AI Core + holat
        hero = QFrame(); hero.setObjectName("panelHi"); hv = QVBoxLayout(hero); hv.setContentsMargins(18, 10, 18, 12); hv.setSpacing(4)
        self.core = AICore(reduced=self.reduced); hv.addWidget(self.core, 1)
        self.title = QLabel(APP_NAME); self.title.setObjectName("title"); self.title.setAlignment(Qt.AlignCenter); hv.addWidget(self.title)
        self.status = QLabel("STANDBY"); self.status.setObjectName("status"); self.status.setAlignment(Qt.AlignCenter); hv.addWidget(self.status)
        self.hint = QLabel(); self.hint.setObjectName("sub"); self.hint.setAlignment(Qt.AlignCenter); self.hint.setWordWrap(True); hv.addWidget(self.hint)
        row = QHBoxLayout(); row.setSpacing(12)
        self.mic_pill = QLabel(); self.mic_pill.setMinimumWidth(116); row.addWidget(self.mic_pill)
        self.voice = VoiceBars(reduced=self.reduced); row.addWidget(self.voice, 1)
        self.mic_btn = QPushButton("  Start listening"); self.mic_btn.setObjectName("primary"); self.mic_btn.setIcon(icon("mic", COL["cyan"], 18))
        self.mic_btn.setFocusPolicy(Qt.NoFocus); self.mic_btn.setToolTip("Same as pressing SPACE"); row.addWidget(self.mic_btn)
        vol = QSlider(Qt.Horizontal); vol.setRange(0, 100); vol.setValue(int(self.settings.volume * 100)); vol.setFixedWidth(110); vol.setFocusPolicy(Qt.NoFocus)
        vol.setToolTip("Voice volume"); self.vol = vol; row.addWidget(QLabel("🔊")); row.addWidget(vol)
        hv.addLayout(row)
        er = QHBoxLayout(); er.setSpacing(8)
        self.exec_label = QLabel("LAST ACTION"); self.exec_label.setObjectName("section"); er.addWidget(self.exec_label)
        self.exec_text = QLabel("No command executed yet"); self.exec_text.setObjectName("sub"); self.exec_text.setTextFormat(Qt.RichText); er.addWidget(self.exec_text, 1)
        self.busy = QProgressBar(); self.busy.setRange(0, 0); self.busy.setFixedWidth(120); self.busy.hide(); er.addWidget(self.busy)
        hv.addLayout(er)
        lay.addWidget(hero, 7)

        # ---- tasdiqlash paneli
        self.confirm_box = QFrame(); self.confirm_box.setObjectName("panelHi"); cb = QHBoxLayout(self.confirm_box); cb.setContentsMargins(14, 8, 14, 8)
        self.confirm_lbl = QLabel(); self.confirm_lbl.setWordWrap(True); cb.addWidget(self.confirm_lbl, 1)
        yes = QPushButton("Run  ⏎"); yes.setObjectName("primary"); yes.setFocusPolicy(Qt.NoFocus); yes.clicked.connect(self.ctrl.confirm)
        no = QPushButton("Cancel  Esc"); no.setFocusPolicy(Qt.NoFocus); no.clicked.connect(lambda: self.ctrl.cancel())
        cb.addWidget(yes); cb.addWidget(no); self.confirm_box.hide(); lay.addWidget(self.confirm_box)

        # ---- suhbat
        chat = QFrame(); chat.setObjectName("panel"); cl = QVBoxLayout(chat); cl.setContentsMargins(12, 8, 12, 12); cl.setSpacing(8)
        head = QHBoxLayout(); t = QLabel("CONVERSATION"); t.setObjectName("section"); head.addWidget(t); head.addStretch(1)
        self.voice_stop = QPushButton("Stop voice"); self.voice_stop.setObjectName("ghost"); self.voice_stop.setIcon(icon("mic", COL["muted"], 16))
        self.voice_stop.setFocusPolicy(Qt.NoFocus); self.voice_stop.setToolTip("Stop the spoken answer"); self.voice_stop.hide(); head.addWidget(self.voice_stop)
        self.term_btn = QPushButton("Terminal"); self.term_btn.setObjectName("ghost"); self.term_btn.setCheckable(True); self.term_btn.setFocusPolicy(Qt.NoFocus)
        self.term_btn.setChecked(self.settings.show_terminal); self.term_btn.clicked.connect(self._toggle_terminal); head.addWidget(self.term_btn)
        clr = QPushButton("Clear"); clr.setObjectName("ghost"); clr.setIcon(icon("trash", COL["muted"], 16)); clr.setFocusPolicy(Qt.NoFocus)
        clr.setToolTip("Remove the current conversation (command history is kept)"); clr.clicked.connect(self.clear_chat); head.addWidget(clr)
        cl.addLayout(head)
        self.chat = ChatView(); cl.addWidget(self.chat, 1)
        inp = QHBoxLayout(); inp.setSpacing(8)
        self.input = ChatInput(); inp.addWidget(self.input, 1)
        self.send_btn = QPushButton(" Send"); self.send_btn.setObjectName("primary"); self.send_btn.setIcon(icon("send", COL["cyan"], 18)); self.send_btn.setFocusPolicy(Qt.NoFocus)
        self.stop_btn = QPushButton(" Stop"); self.stop_btn.setObjectName("rec"); self.stop_btn.setFocusPolicy(Qt.NoFocus); self.stop_btn.hide()
        self.stop_btn.setToolTip("Stop generating the answer"); self.retry_btn = QPushButton(" Retry"); self.retry_btn.setFocusPolicy(Qt.NoFocus); self.retry_btn.hide()
        self.retry_btn.setToolTip("Try the last failed request again")
        inp.addWidget(self.retry_btn, 0, Qt.AlignBottom); inp.addWidget(self.stop_btn, 0, Qt.AlignBottom)
        inp.addWidget(self.send_btn, 0, Qt.AlignBottom); cl.addLayout(inp)
        lay.addWidget(chat, 5)

        self.terminal = TerminalPanel(); self.terminal.setMinimumHeight(110); self.terminal.setMaximumHeight(190)
        self.terminal.setVisible(self.settings.show_terminal); lay.addWidget(self.terminal, 2)
        self.input.setFocus()
        return page

    def _build_rightbar(self) -> QFrame:
        self.rightbar = QFrame(); self.rightbar.setObjectName("rightbar"); self.rightbar.setFixedWidth(318)
        v = QVBoxLayout(self.rightbar); v.setContentsMargins(14, 18, 10, 12); v.setSpacing(8)
        t = QLabel("SYSTEM STATUS"); t.setObjectName("section"); v.addWidget(t)
        self.metrics = MetricsView(self.bridge, compact=True)
        sa = QScrollArea(); sa.setWidgetResizable(True); sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); sa.setWidget(self.metrics)
        v.addWidget(sa, 1)
        self.updated_lbl = QLabel("Live · reading local sensors"); self.updated_lbl.setObjectName("dim"); v.addWidget(self.updated_lbl)
        return self.rightbar

    # ======================================================================= ulanishlar
    def _wire(self) -> None:
        c = self.ctrl
        c.stateChanged.connect(lambda *_: self._on_state())
        c.message.connect(self.add_message)
        c.level.connect(self._on_level)
        c.log.connect(self._on_log)
        c.record.connect(self.history.add)
        c.confirmChanged.connect(self._on_confirm)
        self.speaker.note.connect(lambda m: self.add_message("system", m))
        self.speaker.speakingChanged.connect(lambda _on: self._on_state())
        self.mic_btn.clicked.connect(c.toggle_listening)
        self.send_btn.clicked.connect(self.send_text)
        self.input.sendRequested.connect(self.send_text)
        self.input.micToggleRequested.connect(c.space_pressed)
        self.input.micReleased.connect(c.space_released)
        self.vol.valueChanged.connect(self._on_volume)
        self.stop_btn.clicked.connect(c.cancel_ai)
        self.retry_btn.clicked.connect(c.retry)
        self.voice_stop.clicked.connect(c.stop_speaking)
        c.aiStream.connect(self._on_ai_stream)
        c.retryChanged.connect(lambda _on: self._sync_buttons())
        c.fileAccessNeeded.connect(self._on_file_access_needed)
        c.dataChanged.connect(self._on_data_changed)
        c.navigate.connect(lambda key: self.show_page(key) if key in self.pages else None)
        c.reminderFired.connect(self._on_reminder)
        for page in self.data_pages.values():
            page.changed.connect(c.dataChanged.emit)
        self.settings_page.dataCleared.connect(c.dataChanged.emit)
        c.dataChanged.connect(lambda _k: self.settings_page.refresh_data())
        self.dashboard.openPage.connect(self._dash_open)
        self.dashboard.openNote.connect(lambda nid: (self.show_page("notes"), self.notes_page.select(nid)))
        c.message.connect(self._mirror_to_files_page)
        self.files_page.accessChanged.connect(c.forget_files)
        self.files_page.accessChanged.connect(self.settings_page.refresh_files)
        self.settings_page.openFilesPage.connect(lambda: self.show_page("files"))
        self.history.reuse.connect(self._reuse_command)
        self.history.cleared.connect(lambda: c.log_event("info", "SYSTEM", "Command history cleared"))
        self.settings_page.saved.connect(self.apply_settings)
        self.settings_page.clearHistory.connect(self.history.clear)
        self.settings_page.clearChat.connect(self.clear_chat)
        self.bridge.updated.connect(lambda: self.updated_lbl.setText("Live · updated " + __import__("time").strftime("%H:%M:%S")))

    # ======================================================================= fayllar
    def _on_file_access_needed(self, kind: str, hint: str, retry_text: str) -> None:
        """Buyruq ruxsat berilmagan papkani so'radi: «File Access» sahifasi ochiladi va aniq ruxsat so'raladi. Berilsa buyruq qayta bajariladi."""
        self.show_page("files")
        self.files_page.request_grant(hint, lambda: self.ctrl.submit_text(retry_text))

    def _mirror_to_files_page(self, role: str, text: str) -> None:
        if role == "assistant" and getattr(self, "current", "") == "files" and text:
            self.files_page.set_status(text.splitlines()[0][:300])

    # ======================================================================= ma'lumot sahifalari va eslatma bildirishnomalari
    def _refresh_page(self, key: str) -> None:
        page = self.data_pages.get(key)
        if page is not None:
            page.refresh()

    def _on_data_changed(self, kind: str) -> None:
        """Bir joyda o'zgargan ma'lumot (ovoz, jadval, dashboard) hamma tegishli sahifada yangilanadi."""
        for page in self.data_pages.values():
            if kind in page.watches:
                page.refresh()

    def _dash_open(self, target: str) -> None:
        if target == "notes:new":
            self.show_page("notes"); self.notes_page.create()
        elif target in self.pages:
            self.show_page(target)

    def _on_reminder(self, r) -> None:
        """Eslatma vaqti keldi: oyna ichida banner (+ tizim trayi, ixtiyoriy ovoz). Sarlavha jurnalga yozilmaydi."""
        from ..i18n import T
        lang = self.ctrl.lang
        text = T("rem.fired", lang, title=r.title)
        while len(self._toasts) >= 3:
            self._drop_toast(self._toasts[0])
        toast = QFrame(); toast.setObjectName("toast")
        row = QHBoxLayout(toast); row.setContentsMargins(14, 8, 12, 8)
        lbl = QLabel(text); lbl.setTextFormat(Qt.PlainText); lbl.setWordWrap(True)
        row.addWidget(lbl, 1)
        if not r.recur:                                              # takrorlanuvchi eslatma allaqachon keyingi vaqtga o'tgan
            done = QPushButton("Done"); done.setObjectName("primary")
            snooze = QPushButton("Snooze 10 min")
            done.clicked.connect(lambda: (self.ctrl.executor.reminders.complete(r.id), self.ctrl.dataChanged.emit("reminders"), self._drop_toast(toast)))
            snooze.clicked.connect(lambda: (self.ctrl.executor.reminders.postpone(r.id, minutes=10), self.ctrl.dataChanged.emit("reminders"), self._drop_toast(toast)))
            row.addWidget(done); row.addWidget(snooze)
        dismiss = QPushButton("Dismiss"); dismiss.clicked.connect(lambda: self._drop_toast(toast)); row.addWidget(dismiss)
        self.toast_area.addWidget(toast); self._toasts.append(toast)
        self.add_message("system", text)
        if self.settings.notifications:
            self._tray_notify(r.title)
        self.speaker.say(text, lang)

    def _drop_toast(self, toast: QFrame) -> None:
        if toast in self._toasts:
            self._toasts.remove(toast)
        toast.setParent(None); toast.deleteLater()

    def _tray_notify(self, title: str) -> None:
        """Windows bildirishnomasi (tizim trayi). Qo'llab-quvvatlanmasa (yoki Windows «Focus assist» yoqilgan bo'lsa) — oyna ichidagi banner baribir ko'rinadi."""
        if self._tray is None:
            self._tray = False
            if QSystemTrayIcon.isSystemTrayAvailable():
                self._tray = QSystemTrayIcon(icon("reminders", COL["cyan"], 32), self)
                self._tray.setToolTip(APP_NAME); self._tray.show()
        if self._tray:
            self._tray.showMessage(APP_NAME, title, QSystemTrayIcon.Information, 10000)

    # ======================================================================= sahifalar
    def show_page(self, key: str, animate: bool = True) -> None:
        for k, b in self.navs.items():
            b.setChecked(k == key); b.set_active(k == key)
        page = self.pages[key]
        if getattr(self, "current", "") == "notes" and key != "notes":
            self.notes_page.flush()                                  # saqlanmagan qayd o'zgarishi yo'qolmasin
        self.stack.setCurrentWidget(page)
        self.current = key
        self._refresh_page(key)
        self.rightbar.setVisible(key != "monitor" and self._right_fits())
        if animate and not self.reduced:
            eff = QGraphicsOpacityEffect(page); page.setGraphicsEffect(eff)
            anim = QPropertyAnimation(eff, b"opacity", page); anim.setDuration(170); anim.setStartValue(0.0); anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic); anim.finished.connect(lambda: page.setGraphicsEffect(None)); anim.start(); self._anim = anim
        if key == "assistant":
            self.input.setFocus()
        self.current = key

    def _right_fits(self) -> bool:
        return self.width() >= 1100

    def resizeEvent(self, e):
        super().resizeEvent(e)
        compact = self.width() < 1240
        if compact != self._compact:
            self._compact = compact
            self.sidebar.setFixedWidth(66 if compact else 214)
            for b in self.navs.values():
                b.set_compact(compact)
            self.brand.setVisible(not compact); self.ver.setVisible(not compact)
        self.rightbar.setVisible(getattr(self, "current", "assistant") != "monitor" and self._right_fits())
        if hasattr(self, "terminal"):                       # past oynada suhbatga joy berish uchun terminal vaqtincha yashiriladi
            self.terminal.setVisible(self.settings.show_terminal and self.height() >= 780)

    # ======================================================================= holat va hodisalar
    def _on_state(self) -> None:
        st = self.ctrl.core_state()
        col = STATE_COLORS[st]
        self.core.set_state(st)
        self.status.setText(STATE_LABELS[st]); self.status.setStyleSheet(f"color:{col};")
        self.hint.setText(STATE_HINT[st])
        listening = st == "listening"
        self.voice.set_active(listening)
        if listening:
            self.mic_pill.setText("●  MIC LIVE"); self.mic_pill.setStyleSheet(f"color:{COL['err']}; font-weight:700; letter-spacing:2px;")
            eff = QGraphicsDropShadowEffect(self.mic_pill); eff.setColor(QColor(COL["err"])); eff.setBlurRadius(18); eff.setOffset(0, 0); self.mic_pill.setGraphicsEffect(eff)
        else:
            self.mic_pill.setText("○  MIC OFF"); self.mic_pill.setStyleSheet(f"color:{COL['dim']}; letter-spacing:2px;"); self.mic_pill.setGraphicsEffect(None)
        self.mic_btn.setText("  Stop listening" if listening else "  Start listening")
        self.mic_btn.setObjectName("rec" if listening else "primary")
        self.mic_btn.setIcon(icon("mic", COL["err"] if listening else COL["cyan"], 18))
        self.mic_btn.style().unpolish(self.mic_btn); self.mic_btn.style().polish(self.mic_btn)
        self.busy.setVisible(st in ("executing", "processing", "interpreting"))
        self.exec_label.setText("EXECUTING" if st == "executing" else "LAST ACTION")
        self.setWindowTitle(f"{APP_NAME} — {STATE_LABELS[st]}")
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        busy = self.ctrl.ai_busy
        self.stop_btn.setVisible(busy)
        self.send_btn.setEnabled(not busy)
        self.retry_btn.setVisible(self.ctrl.can_retry())
        self.voice_stop.setVisible(bool(getattr(self.speaker, "speaking", False)))
        self.stop_btn.setIcon(icon("trash", COL["err"], 16))
        self.retry_btn.setIcon(icon("play", COL["cyan"], 16))

    def _on_ai_stream(self, kind: str, text: str) -> None:
        if kind == "thinking_on":
            self.chat.thinking_on("Thinking", animate=not self.reduced)
        elif kind == "thinking_off":
            self.chat.thinking_off()
        elif kind == "start":
            self.chat.disable_retries()
            self.chat.stream_start()
        elif kind == "delta":
            self.chat.stream_delta(text)
        elif kind == "end":
            self.chat.stream_end(text)
        elif kind == "stopped":
            if text.strip() or self.chat.stream_text().strip():
                self.chat.stream_end(text if text.strip() else None, suffix="  (stopped)")
            else:
                self.chat.stream_discard()
                self.add_message("system", "Generation stopped.")
        elif kind == "error":
            if self.chat.has_stream():
                self.chat.stream_end(None)
            self.chat.disable_retries()
            self.chat.add("assistant", text, error=True, on_retry=self.ctrl.retry)
        self._sync_buttons()

    def _on_level(self, v: float) -> None:
        self.core.set_level(v)
        self.voice.push(v)

    def _on_log(self, level: str, line: str) -> None:
        self.terminal.add(level, line)
        tag = line[1:line.index("]")] if line.startswith("[") and "]" in line else ""
        if tag in ("EXECUTION", "SUCCESS", "ERROR"):
            col = LEVEL_COLORS["active" if tag == "EXECUTION" else "success" if tag == "SUCCESS" else "error"]
            self.exec_text.setText(f"<span style='color:{col}'>{html.escape(line.partition('] ')[2])}</span>")

    def _on_confirm(self, need: bool, text: str) -> None:
        self.confirm_box.setVisible(need)
        self.confirm_lbl.setText(f"<b style='color:{COL['violet']}'>CONFIRM</b> &nbsp;{html.escape(text)}")

    def _on_volume(self, x: int) -> None:
        self.speaker.set_volume(x / 100)
        self.settings.save()

    # ======================================================================= chat
    def add_message(self, role: str, text: str) -> None:
        self.chat.add(role, text)

    def send_text(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            if self.ctrl.state == C.CONFIRM:
                self.ctrl.confirm()
            return
        if self.ctrl.busy or self.ctrl.ai_busy or self.ctrl.state == C.LISTENING:
            self.add_message("system", "Busy right now — please wait a moment or stop listening first.")
            return
        self.input.clear()
        self.ctrl.submit_text(text)

    def clear_chat(self) -> None:
        self.ctrl.clear_conversation()             # AI kontekstini ham tozalaydi (buyruqlar tarixi saqlanadi)
        self.chat.clear()
        self.ctrl.log_event("info", "SYSTEM", "Conversation cleared")
        self._sync_buttons()

    def _reuse_command(self, text: str) -> None:
        self.show_page("assistant")
        self.input.setPlainText(text); self.input.setFocus()
        c = self.input.textCursor(); c.movePosition(c.MoveOperation.End); self.input.setTextCursor(c)

    def _toggle_terminal(self) -> None:
        self.settings.show_terminal = self.term_btn.isChecked()
        self.terminal.setVisible(self.settings.show_terminal)
        self.settings.save()

    # ======================================================================= tugmalar
    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.KeyPress and QApplication.activeWindow() is self:
            key = ev.key()
            fw = QApplication.focusWidget()
            if isinstance(fw, ChatInput):
                typing = True                                   # ChatInput Space ni o'zi hal qiladi (bo'sh maydonda — mikrofon)
            else:
                typing = isinstance(fw, (QLineEdit, QTextEdit, QComboBox, QSpinBox)) or (isinstance(fw, QPlainTextEdit) and not fw.isReadOnly())
            if key == Qt.Key_Space and not typing and not isinstance(fw, QPushButton):
                if not ev.isAutoRepeat():
                    self.ctrl.space_pressed()
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter) and not typing and self.ctrl.state == C.CONFIRM:
                self.ctrl.confirm(); return True
            if key == Qt.Key_Escape and self.ctrl.state == C.CONFIRM:
                self.ctrl.cancel(); return True
        if ev.type() == QEvent.KeyRelease and ev.key() == Qt.Key_Space and not ev.isAutoRepeat() and QApplication.activeWindow() is self:
            self.ctrl.space_released()                          # ChatInput o'zining micReleased'ini yuboradi; takror chaqiruv zararsiz (_held)
        elif ev.type() == QEvent.WindowDeactivate and obj is self:
            self.ctrl.space_released(force=True)                # oyna faolligini yo'qotdi: qo'yib yuborish hodisasi kelmaydi — mikrofon ochiq qolmasin
        return super().eventFilter(obj, ev)

    # ======================================================================= sozlamalar
    def _can_test_mic(self) -> tuple[bool, str]:
        if self.ctrl.state not in (C.IDLE, C.DONE):
            return False, "The assistant is busy (listening or working). Finish the current command first."
        return True, ""

    def apply_settings(self) -> None:
        s = self.settings
        ok, err = set_autostart(s.autostart)
        if not ok:
            s.autostart = False
            self.add_message("system", err)
        self.speaker.set_volume(s.volume)
        self.reduced = motion.reduced(s.reduce_motion)
        self.core.set_reduced(self.reduced); self.voice.reduced = self.reduced
        self.terminal.setVisible(s.show_terminal); self.term_btn.setChecked(s.show_terminal)
        if self.ctrl.ai:
            self.ctrl.ai.apply_settings()
        s.save()
        self.ctrl.log_event("success", "SYSTEM", "Settings saved")
        self.add_message("system", "Settings saved.")

    # ======================================================================= hayot tsikli
    def showEvent(self, e):
        super().showEvent(e)
        if not self._started:
            self._started = True
            self.bridge.start()                # jonli monitoring faqat oyna ochiq bo'lganda ishlaydi

    def changeEvent(self, e):
        if e.type() == QEvent.WindowStateChange and self._started:
            (self.bridge.stop if self.isMinimized() else self.bridge.start)()
        super().changeEvent(e)

    def closeEvent(self, e):
        try:
            QApplication.instance().removeEventFilter(self)
            self.notes_page.flush()
            self.ctrl.shutdown(); self.bridge.stop(join=True); self.speaker.close(); self.settings.save()
        finally:
            super().closeEvent(e)
            QApplication.instance().quit()
