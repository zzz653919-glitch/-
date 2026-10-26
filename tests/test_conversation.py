"""AI suhbat + buyruq yo'naltirishi boshqaruvchi darajasida (soxta AI mijoz; haqiqiy boshqaruvchi, router, NLU, ijrochi)."""
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from pyatnitsa import ai_chat, audio, controller as C, stt
from pyatnitsa.ai_chat import AIError, ChatService, Reply
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings
from test_controller import FakeRecorder, FakeSpeaker
from test_executor import FakePlatform


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeClient:
    model = "claude-fake"

    def __init__(self, script=None, key=True):
        self.calls, self.script, self.key = [], list(script or []), key
        self.cancelled, self.gate = threading.Event(), None

    def key_status(self): return self.key, "env:ANTHROPIC_API_KEY" if self.key else ""
    def cancel(self): self.cancelled.set()

    def stream_reply(self, messages, system, on_text, on_first=None):
        self.cancelled.clear()
        self.calls.append((list(messages), system))
        step = self.script.pop(0) if self.script else ("ok", ["Yaxshi, ", "rahmat!"])
        if step[0] == "error":
            raise AIError(step[1], step[2] if len(step) > 2 else "", step[3] if len(step) > 3 else None)
        if step[0] == "slow":                                   # birinchi token oldidan kutadi (THINKING)
            t = time.time()
            while not self.cancelled.is_set() and time.time() - t < 5 and not (self.gate and self.gate.is_set()):
                time.sleep(0.01)
            if self.cancelled.is_set():
                return Reply("", cancelled=True)
            step = ("ok", step[1])
        got = []
        for i, c in enumerate(step[1]):
            if self.cancelled.is_set():
                return Reply("".join(got), cancelled=True)
            if i == 0 and on_first:
                on_first()
            got.append(c); on_text(c)
            if step[0] == "drip":
                time.sleep(0.15)
        return Reply("".join(got), "end_turn", self.model, 0.1)


def make(app, tmp_path, script=None, voice=False, key=True, confirm=False, transcribe=None):
    st = Settings(); st.confirm_commands = confirm; st.voice_enabled = voice; st.ai_notice_shown = True
    plat = FakePlatform({"chrome": Path("/x/chrome.exe")}, tmp_path)
    client = FakeClient(script, key)
    ai = ChatService(st, client)
    ex = Executor(st, plat, fetch=lambda u: [{"Rate": "12000", "Date": "26.10.2026"}])
    c = C.Controller(st, ex, FakeSpeaker(), FakeRecorder, transcribe or (lambda r, l: "Python nima?"), post_roll_ms=0, ai=ai)
    ev, msgs, states = [], [], []
    c.aiStream.connect(lambda k, t: ev.append((k, t))); c.message.connect(lambda r, t: msgs.append((r, t))); c.stateChanged.connect(lambda k, _l: states.append(k))
    FakeRecorder.instances.clear()
    return c, plat, client, ev, msgs, states


def wait(cond, t=5):
    end = time.time() + t
    while time.time() < end and not cond():
        QCoreApplication.processEvents(); time.sleep(0.01)
    assert cond()


# ------------------------------------------------------------------ oddiy suhbat
def test_question_goes_to_ai_streams_and_updates_history(app, tmp_path):
    c, plat, client, ev, msgs, states = make(app, tmp_path, [("drip", ["Python — ", "dasturlash ", "tili."])])
    c.submit_text("Python nima?")
    assert c.state == C.THINKING and c.core_state() == "thinking"
    wait(lambda: c.state == C.IDLE)
    assert [k for k, _ in ev][:3] == ["thinking_on", "thinking_off", "start"] and [t for k, t in ev if k == "delta"] == ["Python — ", "dasturlash ", "tili."]
    assert ev[-1] == ("end", "Python — dasturlash tili.")
    assert states == [C.INTERPRETING, C.THINKING, C.STREAMING, C.IDLE] and plat.calls == []
    assert c.ai.history.messages() == [{"role": "user", "content": "Python nima?"}, {"role": "assistant", "content": "Python — dasturlash tili."}]
    assert ("user", "Python nima?") in msgs
    sys_prompt = client.calls[0][1]
    assert "Uzbek" in sys_prompt and "start of the conversation" in sys_prompt


def test_follow_up_keeps_context_and_language_hint(app, tmp_path):
    c, _, client, *_ = make(app, tmp_path, [("ok", ["Python — dasturlash tili."]), ("ok", ["Guido van Rossum."]), ("ok", ["print('salom')"])])
    for q in ("Python nima?", "Uni kim yaratgan?", "Misol ham ber."):
        c.submit_text(q); wait(lambda: c.state == C.IDLE)
    last = client.calls[2][0]
    assert [m["content"] for m in last] == ["Python nima?", "Python — dasturlash tili.", "Uni kim yaratgan?", "Guido van Rossum.", "Misol ham ber."]
    assert "start of the conversation" not in client.calls[1][1]


def test_language_follows_the_user_each_turn(app, tmp_path):
    c, _, client, *_ = make(app, tmp_path)
    for q in ("Почему небо голубое?", "Why is the sky blue?", "Nega osmon ko'k?"):
        c.submit_text(q); wait(lambda: c.state == C.IDLE)
    hints = [call[1] for call in client.calls]
    assert "looks like: Russian" in hints[0] and "looks like: English" in hints[1] and "Uzbek" in hints[2].split("looks like:")[1]


def test_context_limit_setting_is_respected(app, tmp_path):
    c, _, client, *_ = make(app, tmp_path)
    c.settings.ai_context_messages = 4
    for i in range(6):
        c.submit_text(f"Savol {i}?"); wait(lambda: c.state == C.IDLE)
    assert len(client.calls[-1][0]) <= 4 and client.calls[-1][0][-1]["content"] == "Savol 5?"


# ------------------------------------------------------------------ suhbat va buyruqni ajratish
def test_commands_never_reach_the_ai_and_conversation_never_runs_commands(app, tmp_path):
    c, plat, client, ev, *_ = make(app, tmp_path)
    c.submit_text("Chrome'ni och"); wait(lambda: c.state in (C.DONE, C.IDLE) and plat.calls)
    assert client.calls == [] and plat.calls == [("exe", "/x/chrome.exe")]
    plat.calls.clear()
    c.submit_text("Nega Chrome ochilmayapti?"); wait(lambda: c.state == C.IDLE)
    assert len(client.calls) == 1 and plat.calls == []                         # tushuntiriladi, ochilmaydi
    c.submit_text("Faylni o'chir"); wait(lambda: c.state in (C.DONE, C.IDLE))
    assert len(client.calls) == 1 and plat.calls == []                         # xavfli buyruq AI'ga ham bormaydi


def test_info_commands_use_validated_sources_not_the_ai(app, tmp_path):
    c, plat, client, ev, msgs, _ = make(app, tmp_path)
    c.submit_text("Dollar kursi qancha?"); wait(lambda: c.state == C.DONE)
    assert client.calls == [] and any("12 000" in t for _, t in msgs)


def test_live_data_questions_go_to_ai_with_a_no_live_data_instruction(app, tmp_path):
    c, _, client, *_ = make(app, tmp_path)
    c.submit_text("Bugungi yangiliklar nima?"); wait(lambda: c.state == C.IDLE)
    assert "needs live data you cannot access" in client.calls[0][1]


def test_ai_text_is_never_executed_as_a_command(app, tmp_path):
    evil = ["Albatta! Mana buyruq: `rm -rf /`\nOpen Chrome\nChrome'ni och\npowershell -c del *"]
    c, plat, client, *_ = make(app, tmp_path, [("ok", evil)])
    c.submit_text("Menga yordam ber"); wait(lambda: c.state == C.IDLE)
    assert plat.calls == [] and c._pending == [] and c.state == C.IDLE


def test_incomplete_command_asks_for_clarification_instead_of_chatting(app, tmp_path):
    c, plat, client, ev, msgs, _ = make(app, tmp_path)
    c.submit_text("Chrome"); wait(lambda: c.state == C.DONE)
    assert client.calls == [] and "Chrome" in msgs[-1][1] and plat.calls == []


# ------------------------------------------------------------------ ovozli suhbat
def test_voice_question_is_recognized_shown_and_answered(app, tmp_path):
    c, plat, client, ev, msgs, states = make(app, tmp_path, [("ok", ["Python — dasturlash tili."])])
    c.toggle_listening(); assert c.core_state() == "listening"
    c.toggle_listening(); wait(lambda: c.state == C.IDLE)
    assert states[:5] == [C.LISTENING, C.CHECKING, C.INTERPRETING, C.THINKING, C.STREAMING] and ("user", "Python nima?") in msgs
    assert client.calls and ev[-1][0] == "end" and len(FakeRecorder.instances) == 1


def test_stt_failure_keeps_the_recording_for_retry(app, tmp_path):
    attempts = []
    def tr(rec, lang):
        attempts.append(rec)
        if len(attempts) == 1:
            raise audio.AudioError("stt.network", "offline")
        return "Python nima?"
    c, _, client, ev, msgs, _ = make(app, tmp_path, transcribe=tr)
    rt = []; c.retryChanged.connect(rt.append)
    c.toggle_listening(); c.toggle_listening(); wait(lambda: c.state == C.DONE)
    assert c.can_retry() and rt[-1] is True and c.core_state() == "error"
    c.retry(); wait(lambda: c.state == C.IDLE)
    assert attempts[0] is attempts[1] and client.calls and not c.can_retry()          # aynan o'sha yozuv qayta taniladi


# ------------------------------------------------------------------ sozlanmagan / o'chirilgan / xatolar
def test_missing_key_explains_setup_and_does_not_start_a_request(app, tmp_path):
    c, _, client, ev, msgs, _ = make(app, tmp_path, key=False)
    c.submit_text("Python nima?"); wait(lambda: c.state == C.DONE)
    assert "ANTHROPIC_API_KEY" in msgs[-1][1] and "console.anthropic.com" in msgs[-1][1] and client.calls == [] and c.core_state() == "error"
    c.submit_text("Chrome'ni och"); wait(lambda: c.state in (C.DONE,)); assert client.calls == []     # buyruqlar kalitsiz ham ishlaydi


def test_ai_disabled_in_settings(app, tmp_path):
    c, _, client, _, msgs, _ = make(app, tmp_path)
    c.settings.ai_enabled = False
    c.submit_text("Python nima?"); wait(lambda: c.state in (C.DONE, C.IDLE))
    assert "o'chirilgan" in msgs[-1][1] and client.calls == []


@pytest.mark.parametrize("q,kind,word", [
    ("Python nima?", "rate_limit", "chegarasiga"), ("Что такое Python?", "network", "интернет"), ("What is Python?", "timeout", "did not respond"),
    ("Python nima?", "auth", "kalit"), ("Python nima?", "server", "band"),
])
def test_ai_errors_are_shown_in_the_users_language_with_retry(app, tmp_path, q, kind, word):
    c, _, client, ev, msgs, _ = make(app, tmp_path, [("error", kind, "x", 7.0 if kind == "rate_limit" else None)])
    c.submit_text(q); wait(lambda: c.state == C.DONE)
    kinds = [k for k, _ in ev]
    assert "error" in kinds and "thinking_off" in kinds and c.can_retry() and c.core_state() == "error" and len(c.ai.history) == 0
    assert word in [t for k, t in ev if k == "error"][0]
    if kind == "rate_limit":
        assert "(7 s)" in [t for k, t in ev if k == "error"][0]


def test_retry_resends_without_duplicating_the_question(app, tmp_path):
    c, _, client, ev, *_ = make(app, tmp_path, [("error", "network", "down"), ("ok", ["Python — tili."])])
    c.submit_text("Python nima?"); wait(lambda: c.state == C.DONE)
    c.retry(); wait(lambda: c.state == C.IDLE)
    assert [m["content"] for m in client.calls[1][0]] == ["Python nima?"] and len(c.ai.history) == 2 and not c.can_retry()


def test_unexpected_exceptions_do_not_crash_the_app(app, tmp_path):
    class Boom(FakeClient):
        def stream_reply(self, *a, **k): raise RuntimeError("kutilmagan")
    c, *_ = make(app, tmp_path)
    c.ai.client = Boom()
    c.submit_text("Python nima?"); wait(lambda: c.state == C.DONE)
    assert c.core_state() == "error" and c.can_retry()


# ------------------------------------------------------------------ bekor qilish, Space, tozalash
def test_cancel_while_thinking_stops_quickly_and_removes_the_question(app, tmp_path):
    c, _, client, ev, *_ = make(app, tmp_path, [("slow", ["javob"])])
    c.submit_text("Python nima?"); assert c.ai_busy
    c.cancel_ai(); wait(lambda: c.state == C.IDLE)
    assert ("stopped", "") in ev and len(c.ai.history) == 0 and c.last_ok


def test_cancel_mid_stream_keeps_partial_answer_in_context(app, tmp_path):
    c, _, client, ev, *_ = make(app, tmp_path, [("drip", ["Bir ", "ikki ", "uch ", "to'rt ", "besh "])])
    c.submit_text("Menga bir hikoya aytib ber"); wait(lambda: any(k == "delta" for k, _ in ev) and c.state == C.STREAMING)
    c.cancel_ai(); wait(lambda: c.state == C.IDLE)
    stopped = [t for k, t in ev if k == "stopped"][0]
    assert 0 < len(stopped) < len("Bir ikki uch to'rt besh ") and c.ai.history.messages()[-1] == {"role": "assistant", "content": stopped}


def test_space_during_ai_answer_interrupts_it_and_starts_listening(app, tmp_path):
    c, _, client, ev, *_ = make(app, tmp_path, [("slow", ["javob"])])
    c.submit_text("Python nima?"); assert c.ai_busy
    c.toggle_listening()
    wait(lambda: c.state == C.LISTENING); assert FakeRecorder.instances and c.core_state() == "listening" and ("stopped", "") in ev


def test_new_text_is_refused_while_the_ai_is_busy(app, tmp_path):
    c, _, client, ev, msgs, _ = make(app, tmp_path, [("slow", ["javob"])])
    c.submit_text("Python nima?"); c.submit_text("Yana savol?")
    assert len(client.calls) <= 1 and any("javob bermoqda" in t for r, t in msgs if r == "system")
    c.cancel_ai(); wait(lambda: c.state == C.IDLE)


def test_clear_conversation_resets_context_and_cancels_generation(app, tmp_path):
    c, _, client, ev, *_ = make(app, tmp_path, [("ok", ["a"]), ("slow", ["b"])])
    c.submit_text("Birinchi savol?"); wait(lambda: c.state == C.IDLE)
    c.submit_text("Ikkinchi savol?"); assert c.ai_busy
    c.clear_conversation(); wait(lambda: c.state == C.IDLE)
    assert len(c.ai.history) == 0
    c.submit_text("Yangi savol?"); wait(lambda: c.state == C.IDLE)
    assert [m["content"] for m in client.calls[-1][0]] == ["Yangi savol?"]


# ------------------------------------------------------------------ ovozli javob holatlari va maxfiylik bildirishi
def test_answer_is_spoken_in_its_own_language_and_state_reflects_speaking(app, tmp_path):
    c, _, client, *_ = make(app, tmp_path, [("ok", ["Привет! Всё хорошо, спасибо."])], voice=True)
    c.submit_text("Привет, как дела?"); wait(lambda: c.state == C.DONE)
    assert c.speaker.said == ["Привет! Всё хорошо, спасибо."] and c.speaker.langs[-1] == "ru" and c.core_state() == "responding"
    c.speaker.speaking = True
    assert c.core_state() == "speaking"


def test_privacy_notice_is_shown_once_before_the_first_request(app, tmp_path):
    c, _, client, ev, msgs, _ = make(app, tmp_path)
    c.settings.ai_notice_shown = False; c.settings.save = lambda *a, **k: None
    c.submit_text("Python nima?"); wait(lambda: c.state == C.IDLE)
    notice = [t for r, t in msgs if r == "system" and "Anthropic" in t]
    assert len(notice) == 1 and "audio" in notice[0].lower() or "ovoz" in notice[0].lower() or "audio" in notice[0]
    c.submit_text("Yana?"); wait(lambda: c.state == C.IDLE)
    assert len([t for r, t in msgs if r == "system" and "Anthropic" in t]) == 1


def test_history_records_answered_and_failed_requests(app, tmp_path):
    c, *_ = make(app, tmp_path, [("ok", ["a"]), ("error", "network", "x")])
    rec = []; c.record.connect(rec.append)
    c.submit_text("Python nima?"); wait(lambda: c.state == C.IDLE)
    c.submit_text("Java nima?"); wait(lambda: c.state == C.DONE)
    assert [r["outcome"] for r in rec] == ["answered", "ai_failed"]
