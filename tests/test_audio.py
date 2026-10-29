import pytest

from pyatnitsa import audio

REC = audio.Recording(b"\0" * 64000, 16000)      # 2 soniya


def test_auto_mode_asks_three_languages_and_returns_all_candidates(monkeypatch):
    asked = []
    def fake(rec, lang):
        asked.append(lang)
        return [audio.Heard({"uz-UZ": "och xrom", "ru-RU": "открой хром", "en-US": "open chrome"}[lang], lang, 0.7)]
    monkeypatch.setattr(audio, "_recognize_one", fake)
    heard = audio.transcribe(REC, "auto")
    assert sorted(asked) == sorted(audio.AUTO_LANGS) and {h.lang for h in heard} == set(audio.AUTO_LANGS)
    assert [h.text for h in audio.transcribe(REC, "ru-RU")] == ["открой хром"] and asked[-1] == "ru-RU"


def test_text_is_returned_as_recognized_not_rewritten(monkeypatch):
    monkeypatch.setattr(audio, "_recognize_one", lambda rec, lang: [audio.Heard("Chrome, Google, Downloads, RAM, CPU, Telegram", lang, 0.9)])
    assert audio.transcribe(REC, "uz-UZ")[0].text == "Chrome, Google, Downloads, RAM, CPU, Telegram"


def test_too_short_recording_is_not_understood():
    with pytest.raises(audio.NotUnderstood):
        audio.transcribe(audio.Recording(b"\0" * 100, 16000), "auto")


def test_nothing_recognized_vs_no_internet(monkeypatch):
    import speech_recognition as sr
    monkeypatch.setattr(audio, "_recognize_one", lambda rec, lang: [])
    with pytest.raises(audio.NotUnderstood):
        audio.transcribe(REC, "auto")
    def offline(rec, lang): raise sr.RequestError("offline")
    monkeypatch.setattr(audio, "_recognize_one", offline)
    with pytest.raises(audio.AudioError) as e:
        audio.transcribe(REC, "auto")
    assert "Internet" in str(e.value)


def test_partial_network_failure_still_uses_available_languages(monkeypatch):
    import speech_recognition as sr
    def mixed(rec, lang):
        if lang == "uz-UZ":
            raise sr.RequestError("x")
        return [audio.Heard("open chrome", lang, 0.8)]
    monkeypatch.setattr(audio, "_recognize_one", mixed)
    assert len(audio.transcribe(REC, "auto")) == 2
