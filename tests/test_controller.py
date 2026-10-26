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

    def __init__(self): super().__init__(); self.said = []
    def say(self, t): self.said.append(t)
    def stop(self): pass
    def close(self): pass
    def set_volume(self, v): pass


class FakeRecorder:
    instances = []
    def __init__(self): self.on_level = None; self.started = self.stopped = False; FakeRecorder.instances.append(self)
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
    c = C.Controller(st, Executor(st, plat), FakeSpeaker(), FakeRecorder, tr)
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
    assert "tushunmadim" in c.speaker.said[-1] and plat.calls == []


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
    assert c.state == C.CONFIRM and c._pending.action == "time" and plat.calls == []


def test_microphone_failure_reported(app):
    class Bad(FakeRecorder):
        def start(self): raise audio.AudioError("Mikrofonni ochib bo'lmadi")
    st = Settings()
    c = C.Controller(st, Executor(st, FakePlatform()), FakeSpeaker(), Bad, lambda r, l: "")
    msgs = []; c.message.connect(lambda r, t: msgs.append(t))
    c.toggle_listening()
    assert c.state == C.IDLE and "Mikrofon" in msgs[-1]
