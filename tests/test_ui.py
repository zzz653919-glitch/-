import time

import pytest
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pyatnitsa import controller as C, health
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings
from pyatnitsa.ui import STYLE, MainWindow
from test_controller import FakeRecorder, FakeSpeaker
from test_executor import FakePlatform


def pump(app, cond=None, t=3.0):
    end = time.time() + t
    while time.time() < end and not (cond and cond()):
        app.processEvents(); time.sleep(0.01)
    return bool(cond and cond())


@pytest.fixture
def win(tmp_path):
    from pathlib import Path
    app = QApplication.instance() or QApplication([])
    if not app.styleSheet():
        app.setStyleSheet(STYLE)
    FakeRecorder.instances.clear()
    st = Settings(); st.reduce_motion = "on"
    mon = health.HealthMonitor()
    plat = FakePlatform({"chrome": Path("/x/chrome.exe")}, tmp_path)
    ctrl = C.Controller(st, Executor(st, plat, mon), FakeSpeaker(), FakeRecorder, lambda r, l: "Chrome'ni och", post_roll_ms=0)
    w = MainWindow(st, ctrl, mon, ctrl.speaker)
    w.show(); w.activateWindow(); app.processEvents()
    yield app, w, ctrl, plat
    app.removeEventFilter(w); w.bridge.stop(join=True); mon.stop(); ctrl.shutdown()
    w.hide(); w.deleteLater(); app.processEvents()


def test_all_six_pages_open_and_nav_shows_active_page(win):
    app, w, *_ = win
    for key in ("assistant", "history", "monitor", "diagnostics", "settings", "about"):
        w.navs[key].click(); app.processEvents()
        assert w.stack.currentWidget() is w.pages[key]
        assert [k for k, b in w.navs.items() if b.isChecked()] == [key]


def test_right_panel_hidden_on_monitoring_page_only(win):
    app, w, *_ = win
    w.navs["history"].click(); assert not w.rightbar.isHidden()
    w.navs["monitor"].click(); assert w.rightbar.isHidden()
    w.navs["assistant"].click(); assert not w.rightbar.isHidden()


def test_enter_sends_shift_enter_newline_and_bubbles_have_roles_and_time(win):
    app, w, ctrl, plat = win
    w.input.setFocus()
    QTest.keyClicks(w.input, "salom"); QTest.keyClick(w.input, Qt.Key_Return, Qt.ShiftModifier); QTest.keyClicks(w.input, "dunyo")
    assert w.input.toPlainText() == "salom\ndunyo"
    w.input.clear(); QTest.keyClicks(w.input, "Open Chrome"); QTest.keyClick(w.input, Qt.Key_Return)
    assert w.input.toPlainText() == "" and ctrl.state == C.CONFIRM
    roles = [row.bubble.role for row in w.chat._bubbles]
    assert roles[:3] == ["user", "assistant", "assistant"] or "user" in roles and "assistant" in roles
    assert any(":" in lab.text() for lab in w.chat.findChildren(type(w.title)) if "YOU" in lab.text())


def test_space_in_empty_input_toggles_mic_but_never_types_a_space(win):
    app, w, ctrl, _ = win
    w.input.setFocus()
    QTest.keyClick(w.input, Qt.Key_Space)
    assert ctrl.state == C.LISTENING and w.input.toPlainText() == ""
    assert w.core.state == "listening" and "LISTENING" in w.status.text() and w.voice.active and "LIVE" in w.mic_pill.text()
    QTest.keyClick(w.input, Qt.Key_Space)
    assert pump(app, lambda: ctrl.state == C.CONFIRM)


def test_space_inside_text_is_a_normal_space(win):
    app, w, ctrl, _ = win
    w.input.setFocus(); QTest.keyClicks(w.input, "open chrome")
    assert w.input.toPlainText() == "open chrome" and ctrl.state == C.IDLE and not FakeRecorder.instances


def test_space_outside_inputs_toggles_mic(win):
    app, w, ctrl, _ = win
    w.navs["about"].click(); w.stack.setFocus()
    QTest.keyClick(w.stack, Qt.Key_Space)
    assert ctrl.state == C.LISTENING
    QTest.keyClick(w.stack, Qt.Key_Space)
    assert pump(app, lambda: ctrl.state != C.LISTENING)


def test_core_state_follows_controller_and_confirm_bar(win):
    app, w, ctrl, plat = win
    assert w.core.state == "standby" and "STANDBY" in w.status.text() and "MIC OFF" in w.mic_pill.text()
    ctrl.submit_text("Open Chrome")
    assert w.core.state == "confirm" and not w.confirm_box.isHidden() and "Open" in w.confirm_lbl.text()
    QTest.keyClick(w.stack, Qt.Key_Escape)
    assert plat.calls == [] and w.confirm_box.isHidden()
    ctrl.submit_text("Open Chrome"); QTest.keyClick(w.input, Qt.Key_Return)      # fokusdagi maydondagi bo'sh Enter = tasdiqlash
    assert pump(app, lambda: plat.calls != [])
    assert pump(app, lambda: ctrl.state == C.DONE) and w.core.state == "responding"


def test_terminal_history_and_exec_status_show_real_events(win):
    app, w, ctrl, plat = win
    ctrl.settings.confirm_commands = False
    ctrl.submit_text("Open Chrome"); pump(app, lambda: ctrl.state == C.DONE)
    text = w.terminal.view.toPlainText()
    for expect in ("[SYSTEM] Assistant initialized", "[AI] Intent identified: OPEN_APPLICATION", "[EXECUTION]", "[SUCCESS]"):
        assert expect in text
    assert "Google Chrome" in w.exec_text.text()
    assert w.history.count() == 1 and w.history.table.item(0, 4).text() == "Executed" and w.history.table.item(0, 3).text() == "OPEN_APPLICATION"
    ctrl.submit_text("blah blah"); pump(app, lambda: ctrl.state == C.DONE)
    assert w.history.count() == 2 and w.history.table.item(0, 4).text() == "Not understood"


def test_history_reuse_puts_text_in_input_without_executing(win):
    app, w, ctrl, plat = win
    ctrl.settings.confirm_commands = False
    ctrl.submit_text("Open Chrome"); pump(app, lambda: ctrl.state == C.DONE); plat.calls.clear()
    w.navs["history"].click(); w.history.table.selectRow(0); w.history.use.click()
    assert w.stack.currentWidget() is w.pages["assistant"] and w.input.toPlainText() == "Open Chrome" and plat.calls == []


def test_clear_conversation_keeps_history(win):
    app, w, ctrl, _ = win
    ctrl.settings.confirm_commands = False
    ctrl.submit_text("Open Chrome"); pump(app, lambda: ctrl.state == C.DONE)
    assert w.chat.count() > 0
    w.clear_chat()
    assert w.chat.count() == 0 and not w.chat._empty.isHidden() and w.history.count() == 1


def test_long_messages_do_not_break_layout(win):
    app, w, *_ = win
    w.chat.add("assistant", "x" * 600 + "\n" + "word " * 200)
    app.processEvents()
    row = w.chat._bubbles[-1]
    assert row.bubble.width() <= w.chat.viewport().width()
    assert w.chat.horizontalScrollBar().maximum() == 0


def test_monitoring_shows_real_values_and_marks_missing_sensors(win):
    app, w, *_ = win
    w.monitor.sample(force_slow=True); w.metrics.refresh(); w.monitor_view.refresh()
    s = w.monitor.latest
    assert f"{s.cpu_percent:.0f}%" == w.metrics.cpu.value.text() and f"{s.ram_percent:.0f}%" == w.metrics.ram.value.text()
    if s.cpu_temp is None:
        assert "Unavailable" in w.metrics.cpu.sub.text()
    if not s.gpus:
        assert w.metrics.gpu.value.text() == "Unavailable"
    elif s.gpus[0].util is None:
        assert w.metrics.gpu.value.text() == "Not supported"
    if s.battery is None:
        assert w.metrics.batt.value.text() == "No battery"
    assert s.uptime_s > 0 and health.fmt_uptime(s.uptime_s, "en") == w.metrics.up.value.text()


def test_diagnostics_page_runs_real_checks_off_the_gui_thread(win, monkeypatch):
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: (_ for _ in ()).throw(OSError("blocked in test")))
    app, w, *_ = win
    assert "Not run" in w.diag.summary.text() and not w.diag.empty.isHidden()
    w.diag.run()
    assert not w.diag.run_btn.isEnabled()                      # GUI qotmaydi: tugma darhol qaytdi
    assert pump(app, lambda: w.diag.last, t=20)
    titles = [c.title for c in w.diag.last]
    for expect in ("CPU load", "Memory", "Disk space", "Network", "Application", "Microphone", "Speech recognition", "GPU sensors", "CPU temperature"):
        assert expect in titles
    assert all(c.status in ("operational", "warning", "unavailable", "error") for c in w.diag.last)


def test_settings_page_saves_values_and_applies_them(win, monkeypatch):
    app, w, ctrl, _ = win
    monkeypatch.setattr("pyatnitsa.gui.main_window.set_autostart", lambda on: (True, ""))
    sp = w.settings_page
    sp.engine.setCurrentIndex(sp.engine.findData("whisper")); sp.autostop.setChecked(True); sp.city.setText("Samarkand")
    sp.apps.item(0).setCheckState(Qt.Unchecked); sp.terminal.setChecked(False)
    sp.save_btn.click()
    st = w.settings
    assert st.stt_engine == "whisper" and st.auto_stop_silence and st.city == "Samarkand" and st.allowed_apps["chrome"] is False
    assert w.terminal.isHidden() and not st.show_terminal


def test_mic_test_shows_recognized_text_and_interpretation_without_executing(win, monkeypatch, tmp_path):
    import numpy as np
    from pyatnitsa import audio, stt, voice_test
    app, w, ctrl, plat = win
    class Rec(FakeRecorder):
        def stop(self):
            t = np.arange(32000) / 16000
            sig = 3000 * np.sin(2 * np.pi * 220 * t) * ((t > 0.5) & (t < 1.5)) + np.random.default_rng(0).normal(0, 20, t.size)
            return audio.Recording(sig.astype("<i2").tobytes(), 16000, "Fake Mic")
    orig = voice_test.run_mic_test
    monkeypatch.setattr(voice_test, "run_mic_test", lambda s, secs, on_level, stop: orig(s, 0.2, on_level, stop, recorder_factory=Rec,
                        recognizer=lambda rec, s: stt.Outcome([stt.Heard("Open Chrome", "en-US", 0.9)], audio.analyze(rec), "fake", "auto")))
    w.navs["settings"].click(); w.settings_page.test_btn.click()
    assert not w.settings_page.test_btn.isEnabled()
    assert pump(app, lambda: w.settings_page.test_btn.isEnabled(), t=10)
    out = w.settings_page.test_out.text()
    assert "Open Chrome" in out and "OPEN_APPLICATION" in out and "not executed" in out and "Fake Mic" in out
    assert plat.calls == []


def test_mic_test_refused_while_listening(win):
    app, w, ctrl, _ = win
    ctrl.toggle_listening()
    w.settings_page.test_btn.click()
    assert "busy" in w.settings_page.test_out.text().lower() and w.settings_page.test_btn.isEnabled()
    ctrl.toggle_listening(); pump(app, lambda: ctrl.state != C.LISTENING)


def test_layout_adapts_at_small_and_large_sizes(win):
    app, w, *_ = win
    w.resize(1000, 680); app.processEvents()
    assert w.sidebar.width() == 66 and w.navs["history"].text() == "" and w.rightbar.isHidden()
    w.resize(1500, 950); app.processEvents()
    assert w.sidebar.width() == 214 and w.navs["history"].text() == "Command History" and not w.rightbar.isHidden()
    w.showMaximized(); app.processEvents(); w.showNormal()
    assert w.core.width() >= 190 and w.core.geometry().right() < w.rightbar.geometry().left() + w.sidebar.width() + 2000


def test_reduced_motion_stops_core_timer(win):
    app, w, *_ = win
    assert w.reduced and not w.core._timer.isActive()
    w.settings.reduce_motion = "off"; w.settings.save = lambda *a, **k: None
    import pyatnitsa.gui.main_window as mw
    mw.set_autostart = lambda on: (True, "")
    w.apply_settings()
    assert not w.reduced and w.core._timer.isActive()                 # animatsiyalar qaytadi
    w.settings.reduce_motion = "on"; w.apply_settings()
    assert w.reduced and not w.core._timer.isActive()
