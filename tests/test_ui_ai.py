"""Interfeysdagi AI suhbat: oqim, Thinking, To'xtatish, Qayta urinish, Tozalash, ovoz tugmalari, Sozlamalar (kalit, ulanish testi)."""
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from mock_anthropic import MockAnthropic
from pyatnitsa import controller as C, credentials, health
from pyatnitsa.ai_chat import ChatService
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings
from pyatnitsa.ui import STYLE, MainWindow
from test_controller import FakeRecorder, FakeSpeaker
from test_conversation import FakeClient
from test_executor import FakePlatform
from test_ui import pump


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PYATNITSA_HOME", str(tmp_path))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False); monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    app = QApplication.instance() or QApplication([])
    if not app.styleSheet():
        app.setStyleSheet(STYLE)
    FakeRecorder.instances.clear()
    st = Settings(); st.reduce_motion = "on"; st.voice_enabled = False; st.ai_notice_shown = True; st.confirm_commands = False
    mon = health.HealthMonitor()
    client = FakeClient()
    spk = FakeSpeaker()
    ctrl = C.Controller(st, Executor(st, FakePlatform({"chrome": Path("/x/chrome.exe")}, tmp_path), mon), spk, FakeRecorder, lambda r, l: "Python nima?",
                        post_roll_ms=0, ai=ChatService(st, client))
    w = MainWindow(st, ctrl, mon, spk)
    w.show(); w.activateWindow(); app.processEvents()
    w.show_page('assistant', animate=False); app.processEvents()
    yield app, w, ctrl, client, spk
    app.removeEventFilter(w); w.bridge.stop(join=True); mon.stop(); ctrl.shutdown(); w.hide(); w.deleteLater(); app.processEvents()


def bubbles(w, role=None):
    return [r.bubble for r in w.chat._bubbles if role is None or r.bubble.role == role]


def test_typing_a_question_streams_into_one_assistant_bubble(env):
    app, w, ctrl, client, _ = env
    client.script = [("drip", ["Python — ", "dasturlash ", "tili."])]
    w.input.setFocus(); QTest.keyClicks(w.input, "Python nima?"); QTest.keyClick(w.input, Qt.Key_Return)
    assert ctrl.state == C.THINKING and w.core.state == "thinking" and "THINKING" in w.status.text()
    assert any("Thinking" in b._body.text() for b in bubbles(w, "system"))                  # «Thinking…» ko'rsatkichi
    assert w.stop_btn.isVisibleTo(w) and not w.send_btn.isEnabled()
    assert pump(app, lambda: ctrl.state == C.IDLE)
    ai = bubbles(w, "assistant")
    assert len(ai) == 1 and ai[0]._body.text().replace("​", "") == "Python — dasturlash tili."
    assert not any("Thinking" in b._body.text() for b in bubbles(w, "system"))              # tugagach yo'qoladi
    assert not w.stop_btn.isVisibleTo(w) and w.send_btn.isEnabled() and bubbles(w, "user")[0]._body.text() == "Python nima?"


def test_core_shows_responding_while_streaming(env):
    app, w, ctrl, client, _ = env
    client.script = [("drip", ["Bir ", "ikki ", "uch ", "to'rt "])]
    ctrl.submit_text("Python nima?")
    assert pump(app, lambda: ctrl.state == C.STREAMING) and w.core.state == "responding" and "RESPONDING" in w.status.text()
    assert pump(app, lambda: ctrl.state == C.IDLE)


def test_stop_button_cancels_and_keeps_the_partial_text(env):
    app, w, ctrl, client, _ = env
    client.script = [("drip", ["Bir ", "ikki ", "uch ", "to'rt ", "besh "])]
    ctrl.submit_text("Menga hikoya ayt"); assert pump(app, lambda: w.chat.stream_text() != "" and ctrl.state == C.STREAMING)
    w.stop_btn.click(); assert pump(app, lambda: ctrl.state == C.IDLE)
    txt = bubbles(w, "assistant")[-1]._body.text()
    assert "(stopped)" in txt and txt.startswith("Bir") and not w.stop_btn.isVisibleTo(w)


def test_error_bubble_has_a_working_retry_button(env):
    app, w, ctrl, client, _ = env
    client.script = [("error", "network", "down"), ("ok", ["Qayta urinish ishladi."])]
    ctrl.submit_text("Python nima?"); assert pump(app, lambda: ctrl.state == C.DONE)
    err = [b for b in bubbles(w, "assistant") if b.objectName() == "bubbleErr"]
    assert len(err) == 1 and "ulanib bo'lmadi" in err[0]._body.text() and err[0].retry_btn.isEnabled()
    assert w.retry_btn.isVisibleTo(w) and w.core.state == "error"                           # xato holati haqiqiy
    err[0].retry_btn.click()
    assert pump(app, lambda: ctrl.state == C.IDLE)
    assert bubbles(w, "assistant")[-1]._body.text() == "Qayta urinish ishladi." and not w.retry_btn.isVisibleTo(w)
    assert all(not (b.retry_btn and b.retry_btn.isVisible()) for b in bubbles(w, "assistant") if getattr(b, "retry_btn", None))


def test_clear_button_clears_chat_and_ai_context(env):
    app, w, ctrl, client, _ = env
    ctrl.submit_text("Python nima?"); pump(app, lambda: ctrl.state == C.IDLE)
    assert len(ctrl.ai.history) == 2 and w.chat.count() > 0
    w.clear_chat()
    assert len(ctrl.ai.history) == 0 and w.chat.count() == 0 and not w.chat._empty.isHidden()
    ctrl.submit_text("Yangi mavzu?"); pump(app, lambda: ctrl.state == C.IDLE)
    assert [m["content"] for m in client.calls[-1][0]] == ["Yangi mavzu?"]                    # eski kontekst yo'q


def test_voice_stop_button_follows_real_speaking_state(env):
    app, w, ctrl, client, spk = env
    assert not w.voice_stop.isVisibleTo(w)
    spk.speaking = True; spk.speakingChanged.emit(True); app.processEvents()
    assert w.voice_stop.isVisibleTo(w) and w.core.state in ("speaking", "standby")
    stopped = []; spk.stop = lambda: stopped.append(1)
    w.voice_stop.click(); assert stopped
    spk.speaking = False; spk.speakingChanged.emit(False); app.processEvents()
    assert not w.voice_stop.isVisibleTo(w)


def test_speaking_state_is_shown_on_the_core_after_the_answer(env):
    app, w, ctrl, client, spk = env
    ctrl.settings.voice_enabled = True
    ctrl.submit_text("Python nima?"); assert pump(app, lambda: ctrl.state == C.DONE)
    spk.speaking = True; spk.speakingChanged.emit(True); app.processEvents()
    assert w.core.state == "speaking" and "SPEAKING" in w.status.text()


def test_voice_conversation_flow_in_the_gui(env):
    app, w, ctrl, client, _ = env
    w.input.setFocus(); QTest.keyClick(w.input, Qt.Key_Space)
    assert w.core.state == "listening"
    QTest.keyClick(w.input, Qt.Key_Space)
    assert pump(app, lambda: ctrl.state == C.IDLE)
    assert bubbles(w, "user")[0]._body.text() == "Python nima?" and bubbles(w, "assistant")                # tanilgan matn ko'rinadi, javob keladi


def test_chat_works_alongside_commands_in_one_conversation(env):
    app, w, ctrl, client, _ = env
    ctrl.submit_text("Python nima?"); pump(app, lambda: ctrl.state == C.IDLE)
    ctrl.submit_text("Chrome'ni och"); pump(app, lambda: ctrl.state in (C.DONE, C.IDLE) and ctrl.executor.platform.calls)
    ctrl.submit_text("Uni kim yaratgan?"); pump(app, lambda: ctrl.state == C.IDLE and len(client.calls) == 2)
    assert [m["content"] for m in client.calls[1][0]][:3] == ["Python nima?", "Yaxshi, rahmat!", "Uni kim yaratgan?"]    # buyruq kontekstga aralashmagan
    assert ctrl.executor.platform.calls == [("exe", "/x/chrome.exe")]


# ------------------------------------------------------------------ Sozlamalar
def test_settings_ai_section_roundtrip_and_key_is_stored_privately(env, monkeypatch):
    app, w, ctrl, client, _ = env
    monkeypatch.setattr("pyatnitsa.gui.main_window.set_autostart", lambda on: (True, ""))
    sp = w.settings_page
    assert "No API key" in sp.ai_key_status.text()
    sp.ai_key.setText("short"); sp._save_key(); assert "invalid" in sp.ai_key_status.text() and credentials.get_api_key()[0] is None
    KEY = "sk-ant-test-0123456789abcdefghij"
    sp.ai_key.setText(KEY); sp._save_key()
    assert credentials.get_api_key() == (KEY, "file") and sp.ai_key.text() == "" and "configured" in sp.ai_key_status.text() and KEY not in sp.ai_key_status.text()
    sp.ai_model.setCurrentText("claude-sonnet-5-5"); sp.ai_ctx.setValue(8); sp.ai_effort.setCurrentIndex(sp.ai_effort.findData("medium"))
    sp.ai_on.setChecked(True); sp.rate.setValue(15)
    sp.save_btn.click()
    s = w.settings
    assert (s.ai_model, s.ai_context_messages, s.ai_effort, s.voice_rate) == ("claude-sonnet-5-5", 8, "medium", 15) and ctrl.ai.history.max_messages == 8
    assert KEY not in Settings.path().read_text()
    sp._remove_key(); assert credentials.get_api_key() == (None, "")


def test_connection_test_talks_to_the_service_off_the_gui_thread(env, monkeypatch):
    app, w, ctrl, client, _ = env
    srv = MockAnthropic()
    try:
        monkeypatch.setenv("ANTHROPIC_BASE_URL", srv.url); monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-0123456789abcdefghij")
        srv.default = ("stream", {"chunks": ["OK"]})
        sp = w.settings_page; sp.ai_fb.setChecked(False)
        sp.ai_test_btn.click(); assert not sp.ai_test_btn.isEnabled()
        assert pump(app, lambda: sp.ai_test_btn.isEnabled(), t=10)
        assert "Connected" in sp.ai_test_out.text() and srv.requests
        srv.script = [("error", 401, "authentication_error", "invalid x-api-key", {})]
        sp.ai_test_btn.click(); assert pump(app, lambda: sp.ai_test_btn.isEnabled(), t=10)
        assert "rejected" in sp.ai_test_out.text() and "sk-ant" not in sp.ai_test_out.text()
    finally:
        srv.close()


def test_connection_test_without_a_key_explains_setup(env, monkeypatch):
    app, w, *_ = env
    sp = w.settings_page; sp.ai_test_btn.click()
    assert pump(app, lambda: sp.ai_test_btn.isEnabled(), t=10)
    assert "No API key" in sp.ai_test_out.text() or "no API key" in sp.ai_test_out.text().lower()


def test_stopping_before_the_first_token_leaves_no_empty_bubble(env):
    app, w, ctrl, client, _ = env
    client.script = [("slow", ["javob"])]
    ctrl.submit_text("Python nima?"); assert ctrl.state == C.THINKING
    w.stop_btn.click(); assert pump(app, lambda: ctrl.state == C.IDLE)
    assert not bubbles(w, "assistant") and any("stopped" in b._body.text() for b in bubbles(w, "system")) and len(ctrl.ai.history) == 0
