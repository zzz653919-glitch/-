"""Audio quvuri: qurilma tanlash, yozish, sifat tahlili, tayyorlash, dvigatellar va xatolar (haqiqiy kod; faqat PortAudio / Google soxta)."""
import sys
import threading
import types

import numpy as np
import pytest

from pyatnitsa import audio, stt
from pyatnitsa.audio import AudioError, NotUnderstood, Recording
from pyatnitsa.settings import Settings


def rec_from(sig, rate=16000) -> Recording:
    return Recording(np.clip(sig, -32768, 32767).astype("<i2").tobytes(), rate)


def speech(rate=16000, secs=3.0, amp=3000.0, noise=20.0, start=1.0, end=2.0, seed=1):
    t = np.arange(int(rate * secs)) / rate
    rng = np.random.default_rng(seed)
    voice = np.where((t > start) & (t < end), amp * np.sin(2 * np.pi * 220 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t)), 0.0)
    return voice + rng.normal(0, noise, t.size)


# ------------------------------------------------------------------ sifat tahlili
def test_normal_speech_is_ok_and_detected():
    q = audio.analyze(rec_from(speech()))
    assert q.verdict == "ok" and 0.8 < q.speech_s < 1.6 and not q.quiet and q.peak_db > -30


@pytest.mark.parametrize("sig,verdict", [
    (np.zeros(48000), "silent"),                                    # mikrofon o'chiq / noto'g'ri qurilma
    (np.random.default_rng(2).normal(0, 20, 48000), "no_speech"),   # faqat shovqin
    (np.zeros(1000) + 500, "too_short"),
])
def test_unusable_audio_is_classified(sig, verdict):
    assert audio.analyze(rec_from(sig)).verdict == verdict


def test_quiet_speech_is_flagged_and_boosted():
    x, q = audio.preprocess(rec_from(speech(amp=300.0, noise=4.0)))
    assert q.verdict == "ok" and q.quiet and q.gain_db > 10
    assert 8000 < np.abs(x).max() < 20000 and q.gain_db <= 30.1       # +30 dB cheklovi bilan kuchaytirilgan (300 -> ~9500)


def test_preprocess_trims_edges_but_keeps_internal_pause():
    r = 16000
    t = np.arange(r * 6) / r
    sig = np.where(((t > 1.0) & (t < 1.8)) | ((t > 2.4) & (t < 3.2)), 3000 * np.sin(2 * np.pi * 200 * t), 0.0) + np.random.default_rng(3).normal(0, 15, t.size)
    x, q = audio.preprocess(rec_from(sig))
    assert 2.6 < len(x) / 16000 < 3.4          # 6 s dan ~3,1 s: 2,2 s nutq+pauza + chetlarda ~0,9 s (kengaytma va qo'shimcha); chetdagi jimlik kesilgan
    mid = x[int(1.4 * 16000): int(1.6 * 16000)]   # asl 2,0–2,2 s = ichki pauza
    assert len(mid) and np.abs(mid).max() < np.abs(x).max() * 0.2     # pauza bor, lekin nutq kesilmagan
    assert np.abs(x[: int(0.2 * 16000)]).max() < np.abs(x).max() * 0.2


def test_clipping_is_detected():
    assert audio.analyze(rec_from(np.sign(speech(amp=40000.0)) * 32767)).clipped


@pytest.mark.parametrize("src", [16000, 44100, 48000])
def test_resample_to_16k_preserves_duration_and_tone(src):
    t = np.arange(src) / src
    x = audio.resample(np.sin(2 * np.pi * 440 * t).astype(np.float32) * 10000, src, 16000)
    assert abs(len(x) - 16000) <= 2
    spec = np.abs(np.fft.rfft(x)); assert abs(int(np.argmax(spec)) - 440) <= 2


def test_level_meter_is_visible_for_quiet_input():
    assert audio.rms_to_level(1) == 0.0 and audio.rms_to_level(300) > 0.25 and audio.rms_to_level(6000) > 0.8


# ------------------------------------------------------------------ gap tugashini aniqlash
def feed(det, pattern):
    for rms, secs in pattern:
        for _ in range(int(secs / 0.05)):
            if det.update(rms, 0.05):
                return True
    return False


def test_endpoint_waits_for_real_silence_and_ignores_short_pauses():
    det = audio.EndpointDetector(silence_s=1.5)
    assert not feed(det, [(20, 0.6), (3000, 1.0), (20, 1.0), (3000, 1.0), (20, 1.0)])      # 1 s pauza kesmaydi
    assert feed(det, [(20, 1.0)])                                                           # 2 s jimlikdan keyin tugaydi


def test_endpoint_never_fires_without_speech():
    assert not feed(audio.EndpointDetector(silence_s=1.0), [(20, 10.0)])


# ------------------------------------------------------------------ soxta sounddevice
class FakePortAudioError(Exception):
    pass


def install_fake_sd(monkeypatch, devices, default=0, fail_rates=(), fail_text=None, chunks=None):
    state = types.SimpleNamespace(opened=[], closed=0, streams=[])

    class Stream:
        def __init__(self, samplerate, device, channels, dtype, latency, blocksize, callback):
            if fail_text:
                raise FakePortAudioError(fail_text)
            if samplerate in fail_rates:
                raise FakePortAudioError("Invalid sample rate [PaErrorCode -9997]")
            self.cb, self.rate = callback, samplerate
            state.opened.append((samplerate, device, channels, dtype)); state.streams.append(self)

        def start(self):
            for c in (chunks or []):
                self.cb(c.astype("<i2").tobytes(), len(c), None, None)

        def stop(self): pass
        def close(self): state.closed += 1

    mod = types.ModuleType("sounddevice")
    mod.default = types.SimpleNamespace(device=(default, 0))
    mod.query_hostapis = lambda: [{"name": "MME"}, {"name": "Windows WASAPI"}]
    mod.query_devices = lambda *a, **k: devices
    mod.RawInputStream = Stream
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return state


def dev(name, hostapi=0, ch=1, rate=44100.0):
    return {"name": name, "hostapi": hostapi, "max_input_channels": ch, "default_samplerate": rate}


def test_device_listing_dedups_and_prefers_mme_over_wasapi(monkeypatch):
    install_fake_sd(monkeypatch, [dev("Speakers", ch=0), dev("USB Mic", 1, rate=48000.0), dev("USB Mic", 0), dev("Webcam Mic", 0)], default=2)
    assert audio.list_input_devices() == ["USB Mic", "Webcam Mic"]
    d = audio.resolve_device("USB Mic", audio.list_devices())
    assert d.hostapi == "MME" and d.index == 2


def test_recorder_opens_16k_records_all_audio_and_releases(monkeypatch):
    chunks = [np.full(800, 1000), np.full(800, 2000), np.full(800, 3000)]
    st = install_fake_sd(monkeypatch, [dev("USB Mic")], chunks=chunks)
    r = audio.Recorder("USB Mic")
    levels = []
    r.on_level = levels.append
    r.start()
    assert st.opened[0][0] == 16000 and st.opened[0][2] == 1 and st.opened[0][3] == "int16"
    rec = r.stop()
    assert rec.rate == 16000 and rec.device == "USB Mic" and len(rec.data) == 2400 * 2          # hech narsa kesilmagan
    assert st.closed == 1 and len(levels) == 3 and all(0 <= l <= 1 for l in levels)
    r2 = audio.Recorder(); r2.start(); r2.stop()                                                  # mikrofon bo'shatilgan: qayta ochiladi


def test_recorder_falls_back_to_native_rate(monkeypatch):
    st = install_fake_sd(monkeypatch, [dev("Mic", rate=48000.0)], fail_rates=(16000,))
    r = audio.Recorder(); r.start()
    assert r.rate == 48000
    r.stop()


def test_second_recording_is_refused_while_first_is_active(monkeypatch):
    install_fake_sd(monkeypatch, [dev("Mic")])
    a, b = audio.Recorder(), audio.Recorder()
    a.start()
    with pytest.raises(AudioError) as e:
        b.start()
    assert e.value.key == "mic.busy"
    a.stop()
    b.start(); b.stop()


@pytest.mark.parametrize("devices,fail,key", [
    ([], None, "mic.not_found"),
    ([dev("Mic")], "Error opening InputStream: Unanticipated host error [PaErrorCode -9999]: 'Undefined external error.'", "mic.permission"),
    ([dev("Mic")], "Invalid device [PaErrorCode -9996]", "mic.open_failed"),
])
def test_device_errors_get_specific_keys_and_release_the_lock(monkeypatch, devices, fail, key):
    install_fake_sd(monkeypatch, devices, fail_text=fail)
    with pytest.raises(AudioError) as e:
        audio.Recorder().start()
    assert e.value.key == key
    install_fake_sd(monkeypatch, [dev("Mic")])
    audio.Recorder().start() or None                      # qulf bo'sh: yangi yozuv ochiladi
    audio._MIC_LOCK.release()


def test_missing_portaudio_is_reported(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with pytest.raises(AudioError) as e:
        audio.Recorder().start()
    assert e.value.key == "mic.lib_missing"


# ------------------------------------------------------------------ dvigatellar
def settings(**kw):
    s = Settings(); [setattr(s, k, v) for k, v in kw.items()]; return s


class FakeEngine:
    name = "fake"; language = "auto"
    def __init__(self, result): self.result, self.calls = result, 0
    def transcribe(self, samples):
        self.calls += 1
        if isinstance(self.result, Exception): raise self.result
        return self.result


@pytest.mark.parametrize("sig,key", [(np.zeros(48000), "voice.silent"), (np.zeros(500) + 300, "voice.too_short")])
def test_unusable_audio_never_reaches_the_engine(sig, key):
    eng = FakeEngine([stt.Heard("och chrome", "uz-UZ", 0.9)])
    with pytest.raises(NotUnderstood) as e:
        stt.recognize(rec_from(sig), settings(), eng)
    assert e.value.key == key and eng.calls == 0


NOISE = np.random.default_rng(5).normal(0, 20, 48000)


def test_vad_no_speech_is_advisory_for_google_so_a_wrong_vad_cannot_block_real_speech():
    eng = FakeEngine([stt.Heard("och chrome", "uz-UZ", 0.9)])
    out = stt.recognize(rec_from(NOISE), settings(), eng)
    assert eng.calls == 1 and out.candidates[0].text == "och chrome" and out.quality.verdict == "no_speech"


def test_vad_no_speech_and_empty_recognition_reports_no_speech():
    eng = FakeEngine([])
    with pytest.raises(NotUnderstood) as e:
        stt.recognize(rec_from(NOISE), settings(), eng)
    assert e.value.key == "voice.no_speech" and eng.calls == 1


def test_vad_no_speech_never_reaches_whisper_which_hallucinates_on_noise():
    class FakeWhisper(FakeEngine):
        name = "whisper"
    eng = FakeWhisper([stt.Heard("Thank you.", "en", 0.9)])
    with pytest.raises(NotUnderstood) as e:
        stt.recognize(rec_from(NOISE), settings(), eng)
    assert e.value.key == "voice.no_speech" and eng.calls == 0


def test_good_audio_returns_candidates_and_quality():
    eng = FakeEngine([stt.Heard("Open Chrome", "en-US", 0.9)])
    out = stt.recognize(rec_from(speech()), settings(), eng)
    assert out.candidates[0].text == "Open Chrome" and out.engine == "fake" and out.quality.verdict == "ok"


def test_empty_result_distinguishes_quiet_from_plain_empty():
    with pytest.raises(NotUnderstood) as e:
        stt.recognize(rec_from(speech(amp=300.0, noise=4.0)), settings(), FakeEngine([]))
    assert e.value.key == "voice.too_quiet"
    with pytest.raises(NotUnderstood) as e:
        stt.recognize(rec_from(speech()), settings(), FakeEngine([]))
    assert e.value.key == "stt.empty"


def test_engine_failures_are_not_swallowed():
    with pytest.raises(AudioError) as e:
        stt.recognize(rec_from(speech()), settings(), FakeEngine(AudioError("stt.failed", "FLAC converter blocked")))
    assert e.value.key == "stt.failed" and "FLAC" in e.value.detail


def test_google_engine_auto_asks_three_languages_in_parallel(monkeypatch):
    asked = []
    def one(pcm, lang):
        asked.append(lang)
        return [stt.Heard({"uz-UZ": "och xrom", "ru-RU": "открой хром", "en-US": "open chrome"}[lang], lang, 0.7)]
    monkeypatch.setattr(stt.GoogleEngine, "_one", staticmethod(one))
    heard = stt.GoogleEngine("auto").transcribe(np.zeros(16000, dtype="<i2"))
    assert sorted(asked) == sorted(stt.AUTO_LANGS) and len(heard) == 3
    assert [h.lang for h in stt.GoogleEngine("ru-RU").transcribe(np.zeros(16000, dtype="<i2"))] == ["ru-RU"]


@pytest.mark.parametrize("exc,key", [
    ("RequestError:recognition connection failed: [Errno 11001] getaddrinfo failed", "stt.network"),
    ("RequestError:recognition request failed: Forbidden", "stt.failed"),
    ("OSError:FLAC conversion utility not available", "stt.failed"),
])
def test_google_errors_are_classified_not_hidden(monkeypatch, exc, key):
    import speech_recognition as sr
    kind, msg = exc.split(":", 1)
    err = sr.RequestError(msg) if kind == "RequestError" else OSError(msg)
    def one(pcm, lang): raise err
    monkeypatch.setattr(stt.GoogleEngine, "_one", staticmethod(one))
    with pytest.raises(AudioError) as e:
        stt.GoogleEngine("auto").transcribe(np.zeros(16000, dtype="<i2"))
    assert e.value.key == key


def test_partial_google_failure_still_returns_other_languages(monkeypatch):
    import speech_recognition as sr
    def one(pcm, lang):
        if lang == "uz-UZ": raise sr.RequestError("connection failed")
        return [stt.Heard("open chrome", lang, 0.8)]
    monkeypatch.setattr(stt.GoogleEngine, "_one", staticmethod(one))
    assert len(stt.GoogleEngine("auto").transcribe(np.zeros(16000, dtype="<i2"))) == 2


def test_clean_text_normalizes_without_rewriting_words():
    assert stt.clean_text("  Open   Chrome​ [Music] ") == "Open Chrome"
    assert stt.clean_text("Google Chrome och.") == "Google Chrome och."
    assert stt.clean_text("Thanks for watching!") == "" and stt.clean_text("[BLANK_AUDIO]") == ""
    assert stt.clean_text("RAM, CPU, Telegram") == "RAM, CPU, Telegram"


def test_whisper_engine_with_fake_model(monkeypatch):
    class Seg: text = " Открой браузер "; avg_logprob = -0.2
    class FakeModel:
        def detect_language(self, a): return ("ru", 0.9, [("ru", 0.9), ("uz", 0.05), ("en", 0.02), ("tr", 0.03)])
        def transcribe(self, a, language=None, **kw):
            assert language == "ru" and kw.get("vad_filter") and "Chrome" in kw["initial_prompt"]
            return [Seg()], types.SimpleNamespace(language="ru")
    monkeypatch.setitem(stt.WhisperEngine._models, "base", FakeModel())
    h = stt.WhisperEngine("auto", "base").transcribe(np.zeros(16000, dtype="<i2"))
    assert h[0].text == "Открой браузер" and h[0].lang == "ru" and 0.7 < h[0].conf <= 1.0


def test_whisper_missing_reports_install_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    stt.WhisperEngine._models.pop("tiny", None)
    with pytest.raises(AudioError) as e:
        stt.WhisperEngine("auto", "tiny").transcribe(np.zeros(16000, dtype="<i2"))
    assert e.value.key == "stt.whisper_missing" and not stt.WhisperEngine.available()
