import time

import pytest
from PySide6.QtCore import QCoreApplication, QObject, Signal
from PySide6.QtWidgets import QApplication

from pyatnitsa import audio, controller as C
from pyatnitsa.executor import Executor, Result
from pyatnitsa.settings import Settings
from test_executor import FakePlatform


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class FakeSpeaker(QObject):
    note = Signal(str)
    speakingChanged = Signal(bool)
    speaking = False

    def __init__(self): super().__init__(); self.said = []
    def say(self, t, lang="uz"): self.said.append(t); self.langs = getattr(self, 'langs', []) + [lang]
    def stop(self): pass
    def close(self): pass
    def set_volume(self, v): pass


class FakeRecorder:
    instances = []
    device, rate = "Fake Mic", 16000
    def __init__(self): self.on_level = None; self.on_endpoint = None; self.started = self.stopped = False; FakeRecorder.instances.append(self)
    def start(self): self.started = True
    def stop(self): self.stopped = True; return audio.Recording(b"\0" * 32000, 16000)


def make(app, text="Chrome'ni och", confirm=True, err=None, tmp=None):
    from pathlib import Path
    st = Settings(); st.confirm_commands = confirm
    plat = FakePlatform({"chrome": Path("/x/chrome.exe")}, tmp)
    def tr(rec, lang):
        if err: raise err
        return text
    FakeRecorder.instances.clear()
    c = C.Controller(st, Executor(st, plat), FakeSpeaker(), FakeRecorder, tr, post_roll_ms=0)
    return c, plat


def wait(app, cond, t=3):
    end = time.time() + t
    while time.time() < end and not cond():
        QCoreApplication.processEvents(); time.sleep(0.01)
    assert cond()


def test_space_starts_and_stops_listening(app):
    c, plat = make(app)
    assert c.state == C.IDLE and not FakeRecorder.instances       # Space bosilmaguncha mikrofon ochilmagan
    c.toggle_listening()
    assert c.state == C.LISTENING and FakeRecorder.instances[0].started
    c.toggle_listening()
    assert FakeRecorder.instances[0].stopped
    wait(app, lambda: c.state == C.CONFIRM)
    assert plat.calls == []                                        # tasdiqsiz bajarilmaydi
    c.confirm()
    wait(app, lambda: c.state == C.DONE)
    assert plat.calls == [("exe", "/x/chrome.exe")]


def test_cancel_runs_nothing(app):
    c, plat = make(app)
    c.submit_text("Chrome'ni och"); assert c.state == C.CONFIRM
    c.cancel(); assert c.state == C.DONE and plat.calls == []


def test_text_and_voice_share_same_rules(app):
    c, plat = make(app)
    for text in ("Faylni o'chir", "tushunarsiz gap"):
        c.submit_text(text)
        assert c.state == C.DONE and plat.calls == []


def test_voice_dangerous_blocked(app):
    c, plat = make(app, text="Kompyuterni o'chir")
    c.toggle_listening(); c.toggle_listening()
    wait(app, lambda: c.state == C.DONE)
    assert plat.calls == [] and "xavfli" in c.speaker.said[-1]


def test_unknown_voice_says_repeat(app):
    c, plat = make(app, text="abrakadabra")
    c.toggle_listening(); c.toggle_listening()
    wait(app, lambda: c.state == C.DONE)
    assert "abrakadabra" in c.speaker.said[-1] and "aniqlay olmadim" in c.speaker.said[-1] and plat.calls == []   # nima eshitilgani aytiladi


def test_recognition_error_does_not_crash(app):
    c, _ = make(app, err=audio.AudioError("Internetni tekshiring"))
    c.toggle_listening(); c.toggle_listening()
    wait(app, lambda: c.state == C.DONE)
    assert "Internet" in c.speaker.said[-1]
    c.toggle_listening(); assert c.state == C.LISTENING            # xatodan keyin yana ishlaydi


def test_no_confirm_mode(app):
    c, plat = make(app, confirm=False)
    c.submit_text("Chrome'ni och")
    wait(app, lambda: c.state == C.DONE)
    assert plat.calls


def test_new_text_replaces_pending_confirmation(app):
    c, plat = make(app)
    c.submit_text("Chrome'ni och"); c.submit_text("Hozirgi vaqtni ayt")
    assert c.state == C.CONFIRM and c._pending[0].action == "time" and plat.calls == []


def test_microphone_failure_reported(app):
    class Bad(FakeRecorder):
        def start(self): raise audio.AudioError("Mikrofonni ochib bo'lmadi")
    st = Settings()
    c = C.Controller(st, Executor(st, FakePlatform()), FakeSpeaker(), Bad, lambda r, l: "", post_roll_ms=0)
    msgs = []; c.message.connect(lambda r, t: msgs.append(t))
    c.toggle_listening()
    assert c.state == C.DONE and c.core_state() == "error" and "Mikrofon" in msgs[-1]


def test_nothing_happens_when_app_is_not_active(app):
    c, plat = make(app)
    c.is_active = lambda: False
    c.toggle_listening()
    assert c.state == C.IDLE and not FakeRecorder.instances
    c.submit_text("Chrome'ni och")
    assert c.state == C.IDLE and plat.calls == []


def test_confirm_refused_if_app_loses_focus(app):
    c, plat = make(app)
    c.submit_text("Chrome'ni och"); assert c.state == C.CONFIRM
    c.is_active = lambda: False
    c.confirm()
    assert c.state == C.IDLE and plat.calls == []


# ------------------------------------------------------------------ ovoz quvuri: holatlar, xato turlari, ishonch
def states_of(c):
    seen = []
    c.stateChanged.connect(lambda k, _l: seen.append(k))
    return seen


def test_voice_pipeline_goes_through_real_states_in_order(app, tmp_path):
    c, plat = make(app, "Chrome'ni och")
    seen = states_of(c)
    c.toggle_listening(); assert c.core_state() == "listening"
    c.toggle_listening()
    wait(app, lambda: c.state == C.CONFIRM)
    assert seen == [C.LISTENING, C.CHECKING, C.INTERPRETING, C.CONFIRM] and c.core_state() == "confirm"
    c.confirm(); wait(app, lambda: c.state == C.DONE)
    assert seen[-2:] == [C.RUNNING, C.DONE] and c.core_state() == "responding"


def test_recorder_is_released_before_recognition_and_listening_needs_successful_start(app, tmp_path):
    c, _ = make(app, "x")
    c.toggle_listening(); rec = FakeRecorder.instances[0]
    assert rec.started and not rec.stopped
    c.toggle_listening()
    assert rec.stopped                                # mikrofon matnga aylantirishdan OLDIN bo'shatilgan
    wait(app, lambda: c.state == C.DONE)


def test_post_roll_keeps_listening_briefly_after_second_space(app):
    from pathlib import Path
    st = Settings()
    c = C.Controller(st, Executor(st, FakePlatform()), FakeSpeaker(), FakeRecorder, lambda r, l: "x", post_roll_ms=120)
    FakeRecorder.instances.clear()
    c.toggle_listening(); c.toggle_listening()
    assert c.state == C.LISTENING and not FakeRecorder.instances[0].stopped       # hali yozmoqda (oxirgi bo'g'in)
    c.toggle_listening()                                                           # post-roll paytida qayta bosish ikkinchi to'xtatish emas
    wait(app, lambda: FakeRecorder.instances[0].stopped)
    assert c.state in (C.CHECKING, C.INTERPRETING, C.DONE)


def test_unrecognized_voice_text_is_shown_and_not_executed(app, tmp_path):
    c, plat = make(app, "uzum bodring pomidor")
    msgs = []; c.message.connect(lambda r, t: msgs.append((r, t)))
    c.toggle_listening(); c.toggle_listening(); wait(app, lambda: c.state == C.DONE)
    assert ("user", "uzum bodring pomidor") in msgs and "uzum bodring pomidor" in msgs[-1][1] and plat.calls == [] and c.last_ok


@pytest.mark.parametrize("key,real", [
    ("voice.no_speech", False), ("voice.silent", False), ("voice.too_quiet", False), ("stt.empty", False),
    ("stt.network", True), ("stt.failed", True), ("mic.permission", True),
])
def test_specific_voice_errors_have_specific_messages_and_correct_state(app, tmp_path, key, real):
    err = (audio.AudioError if real else audio.NotUnderstood)(key, "detail-x")
    c, plat = make(app, err=err)
    c.toggle_listening(); c.toggle_listening(); wait(app, lambda: c.state == C.DONE)
    msg = c.speaker.said[-1]
    assert "tushunmadim" not in msg and plat.calls == []                    # umumiy «tushunmadim» emas
    assert (c.core_state() == "error") == real


def test_unexpected_exception_is_reported_not_hidden(app, tmp_path):
    c, _ = make(app, err=RuntimeError("FLAC boom"))
    c.toggle_listening(); c.toggle_listening(); wait(app, lambda: c.state == C.DONE)
    assert "FLAC boom" in c.speaker.said[-1] and c.core_state() == "error"


def test_low_confidence_is_not_executed_even_if_it_parses(app, tmp_path):
    from pyatnitsa import stt
    c, plat = make(app, "x")
    c._transcribe = lambda rec, l: [stt.Heard("Chrome'ni och", "uz-UZ", 0.2)]
    c.settings.confirm_commands = False
    c.toggle_listening(); c.toggle_listening(); wait(app, lambda: c.state == C.DONE)
    assert plat.calls == [] and "Chrome'ni och" in c.speaker.said[-1]
    c._transcribe = lambda rec, l: [stt.Heard("Chrome'ni och", "uz-UZ", 0.9)]
    c.toggle_listening(); c.toggle_listening(); wait(app, lambda: plat.calls != [])
    assert plat.calls


def test_microphone_start_failure_is_error_state_with_specific_text(app, tmp_path):
    class NoMic(FakeRecorder):
        def start(self): raise audio.AudioError("mic.not_found")
    st = Settings()
    c = C.Controller(st, Executor(st, FakePlatform()), FakeSpeaker(), NoMic, lambda r, l: "", post_roll_ms=0)
    msgs = []; logs = []
    c.message.connect(lambda r, t: msgs.append(t)); c.log.connect(lambda lv, t: logs.append(t))
    c.toggle_listening()
    assert c.core_state() == "error" and "Mikrofon topilmadi" in msgs[-1] and any("Microphone unavailable" in l for l in logs)


def test_terminal_events_reflect_real_flow(app, tmp_path):
    c, plat = make(app, "Chrome'ni och")
    logs = []; c.log.connect(lambda lv, t: logs.append((lv, t)))
    c.toggle_listening(); c.toggle_listening(); wait(app, lambda: c.state == C.CONFIRM)
    c.confirm(); wait(app, lambda: c.state == C.DONE)
    text = "\n".join(t for _, t in logs)
    for expect in ("[VOICE] Listening activated", "[VOICE] Speech recognized", "Intent identified: OPEN_APPLICATION", "[EXECUTION]", "[SUCCESS]"):
        assert expect in text, expect
    assert text.index("Listening activated") < text.index("Speech recognized") < text.index("Intent identified") < text.index("[EXECUTION]") < text.index("[SUCCESS]")


def test_history_record_is_emitted_once_per_command(app, tmp_path):
    c, _ = make(app, "Chrome'ni och")
    rec = []; c.record.connect(rec.append)
    c.submit_text("Chrome'ni och"); c.confirm(); wait(app, lambda: c.state == C.DONE)
    c.submit_text("Faylni o'chir")
    assert [r["outcome"] for r in rec] == ["executed", "blocked"] and rec[0]["intents"] == ["OPEN_APPLICATION"]
