"""Mikrofon diagnostikasi: qurilma tanlash (loopback/Stereo Mix), kanallar, hold-to-talk Space, jonli faollik, konsol vositasi.
Hammasi soxta sounddevice / soxta yozuvchi bilan — HAQIQIY mikrofon sinovi EMAS (u foydalanuvchi noutbukida bajariladi)."""
import time

import numpy as np
import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pyatnitsa import audio, controller as C, mic_check, voice_test
from pyatnitsa.audio import AudioError
from test_audio import dev, install_fake_sd
from test_controller import FakeRecorder, make as make_ctrl, wait
from test_ui import pump, win  # noqa: F401  (win — fixture)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


# ------------------------------------------------------------------ loopback / Stereo Mix aniqlash
@pytest.mark.parametrize("name,loop", [
    ("Stereo Mix (Realtek High Definition Audio)", True), ("Стерео микшер (Realtek High Definition Audio)", True), ("What U Hear", True),
    ("Monitor of Built-in Audio Analog Stereo", True), ("Speakers (Realtek(R) Audio) [Loopback]", True), ("CABLE Output (VB-Audio Virtual Cable)", True),
    ("Microphone Array (Intel® Smart Sound Technology)", False), ("Микрофон (Realtek High Definition Audio)", False),
    ("Headset Microphone (USB Audio)", False), ("Webcam C920 Mic", False),
])
def test_loopback_names_are_recognized(name, loop):
    assert audio.is_loopback_name(name) is loop


def test_loopback_devices_are_hidden_from_the_picker(monkeypatch):
    install_fake_sd(monkeypatch, [dev("Stereo Mix (Realtek)"), dev("Microphone Array"), dev("Monitor of Speakers")], default=0)
    assert audio.list_input_devices() == ["Microphone Array"]
    assert [d.kind for d in audio.list_devices()] == ["loopback", "microphone", "loopback"]


def test_default_loopback_is_skipped_and_physical_mic_used_with_warning(monkeypatch):
    """Asosiy gumon: Windows standart kirishi = Stereo Mix -> ilova faqat kompyuter ichki tovushini eshitadi."""
    st = install_fake_sd(monkeypatch, [dev("Stereo Mix (Realtek)"), dev("Microphone Array (Realtek)")], default=0)
    r = audio.Recorder(None); r.start()
    assert st.opened[0][1] == 1 and r.device == "Microphone Array (Realtek)" and r.warning == "default_loopback" and r.device_index == 1
    r.stop()


def test_selected_loopback_in_old_settings_is_ignored(monkeypatch):
    install_fake_sd(monkeypatch, [dev("Stereo Mix (Realtek)"), dev("USB Mic")], default=1)
    r = audio.Recorder("Stereo Mix (Realtek)"); r.start()
    assert r.device == "USB Mic" and r.warning == "selected_loopback"
    r.stop()


def test_only_loopback_devices_is_a_specific_error_and_releases_the_lock(monkeypatch):
    install_fake_sd(monkeypatch, [dev("Stereo Mix (Realtek)")], default=0)
    with pytest.raises(AudioError) as e:
        audio.Recorder().start()
    assert e.value.key == "mic.loopback_only" and "Stereo Mix" in e.value.detail
    install_fake_sd(monkeypatch, [dev("Mic")]); audio.Recorder().start(); audio._MIC_LOCK.release()


def test_physical_pick_prefers_microphone_names_over_unknown_devices():
    ds = [audio.DeviceInfo(0, "Line In (Realtek)", "MME", 2, 44100.0), audio.DeviceInfo(1, "Microphone (Realtek)", "MME", 2, 44100.0)]
    d, warn = audio.choose_device("Stereo Mix", ds + [audio.DeviceInfo(2, "Stereo Mix (Realtek)", "MME", 2, 44100.0)])
    assert d.index == 1 and warn == "missing"


# ------------------------------------------------------------------ kanallar
def test_dead_channel_is_dropped_instead_of_halving_the_level():
    st = np.zeros((1600, 2)); st[:, 0] = 2000                       # chap kanal jonli, o'ng kanal o'lik
    mono, rms = audio.downmix(st.astype("<i2").tobytes(), 2)
    out = np.frombuffer(mono, dtype="<i2")
    assert len(out) == 1600 and abs(int(out.mean()) - 2000) <= 1 and rms[1] == 0


def test_both_channels_alive_are_averaged():
    st = np.zeros((800, 2)); st[:, 0], st[:, 1] = 1000, 3000
    mono, _ = audio.downmix(st.astype("<i2").tobytes(), 2)
    assert int(np.frombuffer(mono, dtype="<i2").mean()) == 2000


def test_two_channel_device_is_opened_with_two_channels_and_recorded_as_mono(monkeypatch):
    stereo = np.zeros((800, 2)); stereo[:, 1] = 1500
    flat = stereo.reshape(-1)
    st = install_fake_sd(monkeypatch, [dev("Mic Array", ch=2)], chunks=[flat, flat])
    r = audio.Recorder("Mic Array"); levels = []; r.on_level = levels.append; r.start()
    rec = r.stop()
    assert st.opened[0][2] == 2 and rec.seconds == pytest.approx(0.1, abs=0.001)
    assert abs(float(rec.samples().mean()) - 1500) < 2 and max(levels) > 0.3          # daraja o'lik kanalga tortilmaydi


def test_stereo_open_failure_falls_back_to_mono(monkeypatch):
    import sys
    st = install_fake_sd(monkeypatch, [dev("Mic", ch=2)])
    real = sys.modules["sounddevice"].RawInputStream

    def picky(**kw):
        if kw["channels"] == 2:
            raise RuntimeError("Invalid number of channels [PaErrorCode -9998]")
        return real(**kw)
    sys.modules["sounddevice"].RawInputStream = picky
    r = audio.Recorder("Mic"); r.start()
    assert st.opened[0][2] == 1
    r.stop()


def test_recorder_reports_stream_open_time(monkeypatch):
    install_fake_sd(monkeypatch, [dev("Mic")])
    r = audio.Recorder("Mic"); r.start(); r.stop()
    assert r.open_ms >= 0 and r.device_index == 0


# ------------------------------------------------------------------ jonli nutq faolligi
def test_activity_meter_follows_speech_and_adapts_to_constant_noise():
    m = audio.ActivityMeter()
    assert not any(m.update(40, 0.05) for _ in range(20))          # xona shovqini — faol emas
    assert m.update(2500, 0.05)                                    # nutq boshlandi
    for _ in range(10):
        m.update(2500, 0.05)
    assert m.active
    for _ in range(12):                                            # 0,3 s hang dan keyin jimlik
        m.update(40, 0.05)
    assert not m.active
    n = audio.ActivityMeter()
    for _ in range(40):
        n.update(400, 0.05)
    assert not n.active                                            # o'zgarmas shovqin (ventilyator) — nutq emas


def test_recorder_reports_activity_changes(monkeypatch):
    quiet, loud = np.full(800, 30), np.full(800, 3000)
    install_fake_sd(monkeypatch, [dev("Mic")], chunks=[quiet, quiet, loud, loud, quiet])
    r = audio.Recorder("Mic"); seen = []; r.on_activity = seen.append; r.start(); r.stop()
    assert seen[:1] == [True]


# ------------------------------------------------------------------ nutq chegarasi (VAD)
def _speech(depth, sec=1.5, amp=3000):
    t = np.arange(int(sec * 16000)) / 16000
    ph = 2 * np.pi * np.cumsum(120 + 20 * np.sin(2 * np.pi * 0.7 * t)) / 16000
    v = sum(np.sin(k * ph) / k for k in range(1, 12)); v /= np.max(np.abs(v))
    return amp * v * ((1 - depth) + depth * np.sin(2 * np.pi * 4 * t) ** 2)


def _rec(x):
    return audio.Recording(np.clip(x, -32768, 32767).astype("<i2").tobytes(), 16000)


@pytest.mark.parametrize("depth", [0.6, 0.92])
def test_speech_without_leading_silence_is_detected_for_hold_to_talk(depth):
    """Space bosib turib darrov gapirish: yozuvda jimlik chetlari yo'q. Faqat jimlikka asoslangan chegara buni «nutq yo'q» der edi."""
    assert audio.analyze(_rec(_speech(depth))).verdict == "ok"


def test_stationary_noise_is_not_speech_even_when_loud():
    rng = np.random.default_rng(7)
    lowpass = np.convolve(rng.normal(0, 1, 32000), np.ones(40) / 40, "same") * 4000
    for x in (rng.normal(0, 150, 32000), rng.normal(0, 800, 32000), lowpass):
        assert audio.analyze(_rec(x)).verdict == "no_speech"


# ------------------------------------------------------------------ Space: bosib turish
def test_hold_space_records_while_held_and_processes_on_release(app, tmp_path):
    c, plat = make_ctrl(app, tmp=tmp_path, confirm=False)
    c.HOLD_MIN_S = 0.05
    c.space_pressed()
    assert c.state == C.LISTENING and FakeRecorder.instances[0].started and not FakeRecorder.instances[0].stopped
    time.sleep(0.08)
    c.space_released()
    wait(app, lambda: c.state == C.DONE)
    assert FakeRecorder.instances[0].stopped and plat.calls == [("exe", "/x/chrome.exe")]


def test_quick_tap_keeps_listening_and_second_press_stops(app, tmp_path):
    c, plat = make_ctrl(app, tmp=tmp_path, confirm=False)
    c.space_pressed(); c.space_released()                         # < HOLD_MIN_S
    assert c.state == C.LISTENING and not FakeRecorder.instances[0].stopped
    c.space_pressed(); c.space_released()
    wait(app, lambda: c.state == C.DONE)
    assert FakeRecorder.instances[0].stopped


def test_window_deactivation_while_held_closes_the_microphone(app, tmp_path):
    c, _ = make_ctrl(app, tmp=tmp_path, confirm=False)
    c.space_pressed()
    c.space_released(force=True)                                  # qo'yib yuborish hodisasi kelmagan holat
    wait(app, lambda: c.state == C.DONE)
    assert FakeRecorder.instances[0].stopped


def test_release_without_a_held_key_does_nothing(app, tmp_path):
    c, _ = make_ctrl(app, tmp=tmp_path)
    c.space_released(); c.space_released(force=True)
    assert c.state == C.IDLE and FakeRecorder.instances == []


def test_silence_endpoint_cannot_cut_the_recording_while_space_is_held(app, tmp_path):
    c, _ = make_ctrl(app, tmp=tmp_path)
    c.space_pressed()
    c._on_endpoint()
    assert c.state == C.LISTENING and not FakeRecorder.instances[0].stopped
    c.space_released(force=True); wait(app, lambda: c.state != C.LISTENING)


def test_failed_mic_start_does_not_leave_a_held_flag(app, tmp_path):
    class Bad(FakeRecorder):
        def start(self): raise AudioError("mic.not_found")
    c, _ = make_ctrl(app, tmp=tmp_path)
    c._recorder_factory = Bad
    c.space_pressed()
    assert c.state != C.LISTENING and not c._held
    c.space_released(force=True)                                  # zararsiz


def test_real_key_press_and_release_on_the_window(win):
    app, w, ctrl, plat = win
    ctrl.HOLD_MIN_S = 0.05
    w.setFocus(); w.stack.setFocus()
    QTest.keyPress(w, Qt.Key_Space)
    assert ctrl.state == C.LISTENING and ctrl._held
    QTest.qWait(80)
    QTest.keyRelease(w, Qt.Key_Space)
    assert pump(app, lambda: ctrl.state != C.LISTENING) and FakeRecorder.instances[0].stopped


def test_empty_chat_input_space_also_holds_to_talk(win):
    app, w, ctrl, plat = win
    ctrl.HOLD_MIN_S = 0.05
    w.input.setFocus(); app.processEvents()
    QTest.keyPress(w.input, Qt.Key_Space)
    assert ctrl.state == C.LISTENING and w.input.toPlainText() == ""
    QTest.qWait(80)
    QTest.keyRelease(w.input, Qt.Key_Space)
    assert pump(app, lambda: ctrl.state != C.LISTENING)


def test_deactivating_the_window_while_holding_stops_recording(win):
    app, w, ctrl, plat = win
    ctrl.space_pressed()
    assert ctrl.state == C.LISTENING
    app.sendEvent(w, QEvent(QEvent.WindowDeactivate))
    assert pump(app, lambda: ctrl.state != C.LISTENING) and FakeRecorder.instances[0].stopped


# ------------------------------------------------------------------ diagnostika
class _Rec(FakeRecorder):
    device_index, warning, open_ms = 3, "default_loopback", 42.0

    def start(self):
        super().start()
        self.on_activity(True) if self.on_activity else None

    def stop(self):
        t = np.arange(32000) / 16000
        sig = 3000 * np.sin(2 * np.pi * 220 * t) * ((t > 0.3) & (t < 1.5)) + np.random.default_rng(0).normal(0, 20, t.size)
        self.stopped = True
        return audio.Recording(sig.astype("<i2").tobytes(), 16000, "Fake Mic")


def test_mic_test_reports_status_sequence_device_index_and_warnings(monkeypatch):
    from pyatnitsa import stt
    from pyatnitsa.settings import Settings
    monkeypatch.setattr(audio, "default_input_name", lambda: "Stereo Mix (Realtek)")
    states = []
    rep = voice_test.run_mic_test(Settings(), 0.2, None, None, recorder_factory=_Rec,
                                  recognizer=lambda rec, s: stt.Outcome([stt.Heard("Open Chrome", "en-US", 0.9)], audio.analyze(rec), "fake", "auto"),
                                  on_status=states.append)
    assert states == ["recording", "processing", "idle"]
    assert rep.device_index == 3 and rep.open_ms == 42.0 and rep.warning == "default_loopback" and rep.default_device == "Stereo Mix (Realtek)"
    assert rep.text == "Open Chrome" and rep.activity >= 0.0


def test_mic_test_failure_still_ends_idle_with_specific_error():
    from pyatnitsa.settings import Settings

    class Bad(FakeRecorder):
        def start(self): raise AudioError("mic.permission", "-9999")
    states = []
    rep = voice_test.run_mic_test(Settings(), 0.1, None, None, recorder_factory=Bad, on_status=states.append)
    assert rep.error_key == "mic.permission" and states[-1] == "idle" and "recording" not in states


def test_mic_test_without_recognition_for_level_only_check():
    from pyatnitsa.settings import Settings
    rep = voice_test.run_mic_test(Settings(), 0.1, None, None, recorder_factory=_Rec, recognizer=False)
    assert rep.quality is not None and rep.text is None and not rep.error_key


def test_device_table_marks_default_used_and_loopback(monkeypatch):
    install_fake_sd(monkeypatch, [dev("Stereo Mix (Realtek)", ch=2), dev("Microphone Array", ch=2)], default=0)
    rows = voice_test.device_table(None)
    assert [(r["index"], r["kind"], r["default"], r["used"]) for r in rows] == [(0, "loopback", True, False), (1, "microphone", False, True)]
    assert rows[1]["warning"] == "default_loopback"


def test_settings_page_lists_devices_and_flags_loopback(win, monkeypatch):
    app, w, *_ = win
    install_fake_sd(monkeypatch, [dev("Stereo Mix (Realtek)"), dev("Microphone Array")], default=0)
    w.navs["settings"].click(); w.settings_page.dev_btn.click()
    t = w.settings_page.dev_out.text()
    assert "Stereo Mix" in t and "LOOPBACK" in t and "IN USE" in t and "Microphone Array" in t and "Windows default" in t


def test_settings_page_shows_clear_error_without_portaudio(win, monkeypatch):
    import sys
    app, w, *_ = win
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    w.settings_page.dev_btn.click()
    assert "PortAudio" in w.settings_page.dev_out.text()


def test_settings_page_status_label_follows_states(win):
    app, w, *_ = win
    sp = w.settings_page
    assert "Idle" in sp.test_state.text()
    sp._set_status("recording"); sp._set_activity(True)
    assert "Recording" in sp.test_state.text() and "speech detected" in sp.test_state.text()
    sp._set_status("processing"); assert "Processing" in sp.test_state.text()
    sp._set_status("idle"); assert "Idle" in sp.test_state.text()


# ------------------------------------------------------------------ konsol vositasi
def test_console_tool_lists_devices_and_flags_loopback(monkeypatch, capsys):
    install_fake_sd(monkeypatch, [dev("Stereo Mix (Realtek)"), dev("Microphone Array")], default=0)
    assert mic_check.main(["--list"]) == 0
    out = capsys.readouterr().out
    assert "LOOPBACK!" in out and "Stereo Mix" in out and "mikrofon EMAS" in out and "ISHLATILADI" in out and "OGOHLANTIRISH" in out


def test_console_tool_without_portaudio_reports_it(monkeypatch, capsys):
    import sys
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    assert mic_check.main(["--list"]) == 2
    assert "XATO" in capsys.readouterr().out


def test_console_tool_records_and_reports_without_stt(monkeypatch, capsys):
    t = np.arange(32000) / 16000
    loud = (3000 * np.sin(2 * np.pi * 220 * t)).astype("<i2")
    chunks = [loud[i:i + 800] for i in range(0, 32000, 800)]
    install_fake_sd(monkeypatch, [dev("Microphone Array")], chunks=chunks)
    assert mic_check.main(["--no-stt", "--seconds", "0.2", "--device", "0"]) == 0
    out = capsys.readouterr().out
    assert "Microphone Array" in out and "nutq faol" in out and "[PROCESSING]" in out
