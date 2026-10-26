"""Ovozli javob: matnni tayyorlash, til/jins/tezlik, tekshirilmagan tilda jim qolish, to'xtatish (soxta edge_tts / pyttsx3)."""
import sys
import time
import types

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from pyatnitsa import tts
from pyatnitsa.settings import Settings


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait(cond, t=3):
    end = time.time() + t
    while time.time() < end and not cond():
        QCoreApplication.processEvents(); time.sleep(0.01)
    return cond()


def test_prepare_speech_drops_code_links_and_markdown():
    t = tts.prepare_speech("# Python\n\nPython — **dasturlash tili**.\n```python\nprint(1)\n```\n- misol: `x = 1`\nhttps://python.org")
    assert "print" not in t and "http" not in t and "**" not in t and "#" not in t and "dasturlash tili" in t and "x = 1" in t
    assert len(tts.prepare_speech("a " * 5000)) <= tts.MAX_SPEECH_CHARS


@pytest.mark.parametrize("pct,expect", [(0, "+0%"), (-20, "-20%"), (30, "+30%"), (99, "+50%"), (-99, "-50%")])
def test_speech_rate_format(pct, expect):
    assert tts.edge_rate(pct) == expect


class FakeEdge(types.ModuleType):
    calls: list = []

    def __init__(self):
        super().__init__("edge_tts")
        outer = self

        class Communicate:
            def __init__(self, text, voice, rate="+0%"):
                outer.calls.append((text, voice, rate))

            async def save(self, path):
                open(path, "wb").write(b"ID3")
        self.Communicate = Communicate


def make(app, monkeypatch, **kw):
    s = Settings(); s.tts_engine = "auto"; [setattr(s, k, v) for k, v in kw.items()]
    sp = tts.Speaker(s)
    played = []
    monkeypatch.setattr(sp, "_play", lambda path, gen: played.append((path, gen)))
    sp._ready.disconnect(); sp._ready.connect(sp._play)
    edge = FakeEdge(); edge.calls = []
    monkeypatch.setitem(sys.modules, "edge_tts", edge)
    return sp, edge, played


@pytest.mark.parametrize("gender,lang,voice", [("male", "uz", "uz-UZ-SardorNeural"), ("male", "ru", "ru-RU-DmitryNeural"), ("male", "en", "en-US-GuyNeural"),
                                              ("female", "uz", "uz-UZ-MadinaNeural"), ("female", "ru", "ru-RU-SvetlanaNeural"), ("female", "en", "en-US-JennyNeural")])
def test_voice_follows_language_and_gender_with_rate(app, monkeypatch, gender, lang, voice):
    sp, edge, played = make(app, monkeypatch, voice_gender=gender, voice_rate=-10)
    sp.say("Salom! **Qalaysiz**", lang)
    assert sp.pending and not sp.speaking                                       # tayyorlanmoqda, hali chalinmayapti
    assert wait(lambda: played)
    assert edge.calls == [("Salom! Qalaysiz", voice, "-10%")]
    sp.close()


def test_disabled_voice_and_empty_text_say_nothing(app, monkeypatch):
    sp, edge, played = make(app, monkeypatch, voice_enabled=False)
    sp.say("Salom", "uz"); sp2, edge2, played2 = make(app, monkeypatch)
    sp2.say("```code```", "uz")
    time.sleep(0.2); QCoreApplication.processEvents()
    assert edge.calls == [] and edge2.calls == [] and not sp.pending and not sp2.pending
    sp.close(); sp2.close()


def test_speaking_flags_and_signal(app, monkeypatch):
    sp, edge, played = make(app, monkeypatch)
    seen = []; sp.speakingChanged.connect(seen.append)
    sp.say("Salom", "uz"); assert wait(lambda: played)
    sp._set_speaking(True); assert sp.speaking and not sp.pending
    sp.stop(); assert not sp.speaking and not sp.pending and seen == [True, False]
    sp.close()


def test_stop_invalidates_pending_audio(app, monkeypatch):
    sp, edge, played = make(app, monkeypatch)
    sp.say("Uzun javob", "uz"); sp.stop()
    wait(lambda: played, 1)
    gens = {g for _, g in played}
    assert all(g != sp._gen for g in gens)                                       # to'xtatilgan javob chalinmaydi
    sp.close()


class FakeVoice:
    def __init__(self, id_, name, langs=()):
        self.id, self.name, self.languages = id_, name, list(langs)


def fake_pyttsx3(voices, log):
    mod = types.ModuleType("pyttsx3")

    class Engine:
        def getProperty(self, k): return voices
        def setProperty(self, k, v): log.append(("set", k, v))
        def say(self, t): log.append(("say", t))
        def runAndWait(self): log.append(("run",))
    mod.init = lambda: Engine()
    return mod


def system_only(app, monkeypatch, voices, **kw):
    s = Settings(); s.tts_engine = "system"; [setattr(s, k, v) for k, v in kw.items()]
    sp = tts.Speaker(s); log = []
    monkeypatch.setitem(sys.modules, "pyttsx3", fake_pyttsx3(voices, log))
    notes = []; sp.note.connect(notes.append)
    return sp, log, notes


def test_system_voice_picks_a_verified_male_voice_for_the_language(app, monkeypatch):
    voices = [FakeVoice("v1", "Microsoft Irina Desktop - Russian", ["ru-RU"]), FakeVoice("v2", "Microsoft Pavel - Russian", ["ru-RU"]), FakeVoice("v3", "Microsoft David - English (United States)", ["en-US"])]
    sp, log, notes = system_only(app, monkeypatch, voices, voice_gender="male", voice_rate=20, volume=0.5)
    sp.say("Привет", "ru")
    assert wait(lambda: ("run",) in log)
    assert ("set", "voice", "v2") in log and ("set", "rate", 240) in log and ("set", "volume", 0.5) in log and ("say", "Привет") in log and not notes
    sp.close()


def test_unsupported_language_is_not_spoken_and_is_explained_once(app, monkeypatch):
    voices = [FakeVoice("v3", "Microsoft David - English (United States)", ["en-US"])]
    sp, log, notes = system_only(app, monkeypatch, voices)
    sp.say("Salom, yaxshimisiz?", "uz"); assert wait(lambda: notes)
    assert not any(e[0] == "say" for e in log) and "Uzbek" in notes[0] and not sp.speaking
    sp.say("Yana bir gap", "uz"); time.sleep(0.3); QCoreApplication.processEvents()
    assert len(notes) == 1                                                       # bir marta tushuntiriladi
    sp.close()


def test_missing_speech_engine_is_reported_not_crashed(app, monkeypatch):
    s = Settings(); s.tts_engine = "system"; sp = tts.Speaker(s)
    monkeypatch.setitem(sys.modules, "pyttsx3", None)
    notes = []; sp.note.connect(notes.append)
    sp.say("Hello", "en"); assert wait(lambda: notes) and "English" in notes[0]
    sp.close()
