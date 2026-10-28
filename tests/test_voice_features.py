"""Ovozli boshqaruv xususiyatlari: oyna/skrinshot/clipboard/veb/YouTube/VS Code/interfeys/ingliz mashqlari, ovozli tasdiq, "faqat ovoz" rejimi.
Mikrofon va nutqni tanish SOXTA (FakeRecorder/transcribe); Windows qatlami soxta. Haqiqiy mikrofon sinovi emas."""
import random
import time
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from pyatnitsa import commands, controller as C, desktop, english, services, stt
from pyatnitsa.ai_chat import ChatService
from pyatnitsa.db import Database
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings
from test_controller import FakeRecorder, FakeSpeaker
from test_conversation import FakeClient
from test_executor import FakePlatform

NOW = datetime(2026, 10, 28, 15, 0)


@pytest.fixture(autouse=True)
def fixed_now():
    commands.set_context(now=lambda: NOW)
    yield
    commands.set_context()


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class Env:
    pass


def make(tmp_path, confirm=True, voice_only=True, net=None, exes=None, voice=False):
    e = Env()
    e.st = Settings(); e.st.confirm_commands = confirm; e.st.voice_enabled = voice; e.st.ai_notice_shown = True; e.st.voice_only = voice_only
    e.plat = FakePlatform({"chrome": Path("/x/chrome.exe"), **(exes or {})}, tmp_path)
    e.db = Database(tmp_path / "p.db", now=lambda: NOW)
    e.ex = Executor(e.st, e.plat, now=lambda: NOW, db=e.db, net=net or (lambda: ("1.1.1.1", 23)))
    e.client = FakeClient()
    e.spk = FakeSpeaker()
    e.says, e.langs = [], []

    def transcribe(rec, lang):
        e.langs.append(lang)
        v = e.says.pop(0)
        return v
    FakeRecorder.instances.clear()
    e.c = C.Controller(e.st, e.ex, e.spk, FakeRecorder, transcribe, post_roll_ms=0, ai=ChatService(e.st, e.client))
    e.msgs, e.logs, e.nav, e.changed, e.records = [], [], [], [], []
    e.c.message.connect(lambda r, t: e.msgs.append((r, t)))
    e.c.log.connect(lambda lv, t: e.logs.append(t))
    e.c.navigate.connect(e.nav.append)
    e.c.dataChanged.connect(e.changed.append)
    e.c.record.connect(e.records.append)
    return e


def wait(cond, t=4.0):
    end = time.time() + t
    while time.time() < end and not cond():
        QCoreApplication.processEvents(); time.sleep(0.005)
    assert cond()


def speak(e, text):
    """Haqiqiy yo'l: Space bosiladi -> yozuv -> qo'yib yuboriladi -> nutqni tanish -> tahlil -> ijro."""
    e.says.append(text)
    e.c.space_pressed()
    assert e.c.state == C.LISTENING
    e.c.space_released(force=True)
    wait(lambda: e.c.state in (C.DONE, C.IDLE, C.CONFIRM))


def confirm_yes(e):
    speak(e, "yes")


def last(e):
    return [t for r, t in e.msgs if r == "assistant"][-1]


# ================================================================== buyruq tushunish (uz · ru · en, turli ifodalar)
@pytest.mark.parametrize("text,action,sub", [
    # kompyuter va ilovalar
    ("Open VS Code", "open_app", {"app": "vscode"}), ("VS Code ni och", "open_app", {"app": "vscode"}), ("открой VS Code", "open_app", {"app": "vscode"}),
    ("Open Chrome", "open_app", {"app": "chrome"}), ("Chrome'ni och", "open_app", {"app": "chrome"}), ("Открой Chrome", "open_app", {"app": "chrome"}),
    ("Brauzerni ishga tushir", "open_app", {"app": "browser"}), ("YouTube'ga kir", "open_app", {"app": "youtube"}), ("Open YouTube", "open_app", {"app": "youtube"}),
    ("Open Downloads", "open_app", {"app": "downloads"}), ("Open my music folder", "open_app", {"app": "music"}), ("открой папку музыка", "open_app", {"app": "music"}),
    ("Open Windows settings", "open_app", {"app": "winsettings"}),
    ("minimize this window", "window", {"op": "minimize"}), ("oynani kichraytir", "window", {"op": "minimize"}), ("сверни окно", "window", {"op": "minimize"}),
    ("switch to the next window", "window", {"op": "next"}), ("keyingi oynaga o'ting", "window", {"op": "next"}), ("следующее окно", "window", {"op": "next"}),
    ("maximize the window", "window", {"op": "maximize"}), ("previous window", "window", {"op": "prev"}),
    ("turn the volume up", "media", {"key": "vol_up"}), ("mute the sound", "media", {"key": "mute"}), ("ovozni oshir", "media", {"key": "vol_up"}), ("громче", "media", {"key": "vol_up"}),
    # internet va qidiruv
    ("Search the web for Python tutorials", "search", {"query": "python tutorials"}), ("Find information about Django", "search", {"query": "django"}),
    ("internetda Python darslarini qidir", "search", {"query": "python darslarini"}), ("найди в интернете Django", "search", {"query": "django"}),
    ("Open YouTube and search for English lessons", "youtube_search", {"query": "English lessons"}), ("YouTube'da English lessons ni qidir", "youtube_search", {"query": "English lessons"}),
    ("найди на ютубе уроки английского", "youtube_search", {"query": "уроки английского"}),
    ("Open the website kun.uz", "open_site", {"host": "kun.uz"}), ("open example.com", "open_site", {"host": "example.com"}),
    # kompyuter ma'lumoti
    ("Show my CPU usage", "health_cpu", {}), ("Check available RAM", "health_ram", {}), ("How much disk space is free?", "health_disk", {}), ("Show my battery status", "health_battery", {}),
    ("Check my internet connection", "net_check", {}), ("internetni tekshir", "net_check", {}), ("проверь интернет", "net_check", {}),
    ("Show my computer specifications", "specs", {}), ("kompyuter xususiyatlarini ko'rsat", "specs", {}),
    # skrinshot / clipboard
    ("Take a screenshot", "screenshot", {}), ("skrinshot ol", "screenshot", {}), ("сделай скриншот", "screenshot", {}),
    ("Read my clipboard", "clipboard", {"mode": "read"}), ("buferni o'qi", "clipboard", {"mode": "read"}), ("прочитай буфер обмена", "clipboard", {"mode": "read"}),
    ("Explain the copied Python code", "clipboard", {"mode": "explain"}), ("Summarize the copied text", "clipboard", {"mode": "summarize"}),
    ("nusxalangan matnni qisqartir", "clipboard", {"mode": "summarize"}), ("Explain this Python error", "clipboard", {"mode": "explain"}),
    # interfeys
    ("Show available commands", "ui", {"op": "commands"}), ("buyruqlar ro'yxatini ko'rsat", "ui", {"op": "commands"}), ("покажи список команд", "ui", {"op": "commands"}),
    ("Switch to dark mode", "ui", {"op": "dark_mode", "theme": "dark"}), ("Show microphone status", "ui", {"op": "mic_status"}), ("mikrofon holatini ko'rsat", "ui", {"op": "mic_status"}),
    ("open the app settings", "ui", {"op": "settings_open"}), ("Close the settings panel", "ui", {"op": "settings_close"}), ("sozlamalar panelini yop", "ui", {"op": "settings_close"}),
    # ingliz tili
    ("Start my English lesson", "english", {"op": "lesson"}), ("ingliz tili darsini boshla", "english", {"op": "lesson"}), ("начни урок английского", "english", {"op": "lesson"}),
    ("Ask me ten A1 vocabulary questions", "english", {"op": "quiz", "n": 10, "level": "A1"}), ("5 ta A2 lug'at savoli ber", "english", {"op": "quiz", "n": 5, "level": "A2"}),
    ("Test my pronunciation", "english", {"op": "pronunciation"}), ("talaffuzimni tekshir", "english", {"op": "pronunciation"}), ("проверь моё произношение", "english", {"op": "pronunciation"}),
    ("Give me a short listening exercise", "english", {"op": "listening"}),
    ("Translate the word ‘improve’", "english", {"op": "translate", "word": "improve"}),
    ("Set my English level to A2", "english", {"op": "level", "level": "A2"}), ("make the English lessons harder", "english", {"op": "level", "shift": 1}),
    ("Show my English learning progress", "study_progress", {}),
    # fayllar, eslatma, vazifa, qayd (mavjud funksiyalar buzilmagan)
    ("Find my latest video", "find_files", {}), ("Find PDF files in Downloads", "find_files", {"folder": "downloads"}),
    ("Remind me to study English at 7 PM", "reminder_add", {}), ("Add a task to finish my website", "task_add", {}), ("Create a note called English Vocabulary", "note_add", {}),
    ("What tasks do I have today?", "tasks_show", {}), ("Pause the current video", "media", {"key": "play_pause"}), ("Skip to the next track", "media", {"key": "next"}),
])
def test_phrases_map_to_the_intended_action(text, action, sub):
    r = commands.parse(text)
    assert r.kind == "ok" and r.commands[0].action == action, (text, r.kind, [c.action for c in r.commands], r.message)
    for k, v in sub.items():
        assert r.commands[0].args.get(k) == v, (text, r.commands[0].args)


def test_bare_settings_is_ambiguous_and_asks_then_follows_the_answer():
    for t in ("Open Settings", "Sozlamalarni och", "открой настройки"):
        r = commands.parse(t)
        assert r.kind == "clarify" and r.draft == t and ("Windows" in r.message), t
    assert commands.parse("Open Settings app").commands[0].args == {"op": "settings_open"}
    assert commands.parse("Open Settings Windows").commands[0].args == {"app": "winsettings"}


@pytest.mark.parametrize("text", [
    "send the copied text to John", "delete the copied file", "copy my passwords", "nusxalangan matnni yubor", "удали скопированный файл",
    "install Chrome", "format the disk", "shut down the computer", "close the window and delete everything", "open cmd", "run powershell",
    "upload my clipboard", "share the screenshot", "minimize the window and delete files",
])
def test_dangerous_requests_are_blocked_everywhere(text):
    r = commands.parse(text)
    assert r.kind in ("blocked", "unknown", "clarify") and not r.commands, (text, r.kind)


@pytest.mark.parametrize("text", ["open file.exe.com", "open 127.0.0.1", "open localhost", "open http://192.168.0.1/", "open xn--e1afmkfd.xn--p1ai"])
def test_unsafe_websites_are_never_opened(text):
    r = commands.parse(text)
    assert not (r.commands and r.commands[0].action == "open_site"), (text, r.commands)


@pytest.mark.parametrize("text", ["Remind me to open the video at 7 PM", "Add a task to take a screenshot", "Create a note: minimize the window", "Remind me to read my clipboard tomorrow at 9 am"])
def test_reminder_task_and_note_text_is_data_not_a_command(text):
    r = commands.parse(text)
    assert r.kind == "ok" and r.commands[0].action in ("reminder_add", "task_add", "note_add"), (text, r.commands)


@pytest.mark.parametrize("text", ["Explain this English word", "What does the word improve mean", "Translate this sentence into Uzbek", "Help me write a prompt for Claude"])
def test_conversation_requests_are_not_commands(text):
    r = commands.parse(text)
    assert not r.commands, (text, r.commands)


# ================================================================== ishga tushganda va ovoz bo'lmaganda hech narsa bajarilmaydi
def test_nothing_happens_when_the_app_starts_or_no_voice_command_is_given(app, tmp_path):
    e = make(tmp_path)
    end = time.time() + 0.4
    while time.time() < end:
        QCoreApplication.processEvents(); time.sleep(0.01)
    assert not FakeRecorder.instances and e.plat.calls == [] and e.msgs == [] and e.spk.said == [] and e.client.calls == []
    assert e.c.state == C.IDLE and e.ex.reminders.all() == [] and e.ex.tasks.all() == [] and e.ex.notes.all() == []
    e.c.start_scheduler(); e.c.check_reminders()
    assert e.msgs == [] and e.plat.calls == []


def test_voice_only_mode_rejects_typed_commands_but_voice_works(app, tmp_path):
    e = make(tmp_path, confirm=False)
    e.c.submit_typed("minimize this window")
    assert e.plat.calls == [] and any("Voice-only" in t or "ovozli" in t.lower() for r, t in e.msgs if r == "system")
    assert any("rejected" in x for x in e.logs)
    speak(e, "minimize this window")
    assert e.plat.calls == [("window", "minimize")]
    e.st.voice_only = False
    e.c.submit_typed("next window")
    wait(lambda: ("window", "next") in e.plat.calls)


def test_releasing_space_stops_recording_and_processes_the_speech(app, tmp_path):
    e = make(tmp_path, confirm=False)
    e.says.append("switch to the next window")
    e.c.space_pressed()
    rec = FakeRecorder.instances[0]
    assert rec.started and not rec.stopped and e.plat.calls == []                          # bosib turilganda hech narsa bajarilmaydi
    time.sleep(C.Controller.HOLD_MIN_S + 0.05)
    e.c.space_released()
    assert rec.stopped
    wait(lambda: e.plat.calls)
    assert e.plat.calls == [("window", "next")]


# ================================================================== ovozli tasdiq
def test_sensitive_action_asks_and_spoken_yes_executes(app, tmp_path, monkeypatch):
    e = make(tmp_path)
    shot = tmp_path / "pics" / "s.png"
    monkeypatch.setattr(desktop, "take_screenshot", lambda d, n: shot)
    speak(e, "Take a screenshot")
    assert e.c.state == C.CONFIRM and "screenshot" in e.c._ask_text().lower()
    assert not any("saved" in t for r, t in e.msgs)                                         # tasdiqlanguncha bajarilmaydi
    speak(e, "yes")
    assert "Screenshot saved" in last(e) and str(shot) in last(e)


def test_spoken_no_cancels_and_other_speech_replaces_the_pending_action(app, tmp_path, monkeypatch):
    e = make(tmp_path)
    called = []
    monkeypatch.setattr(desktop, "take_screenshot", lambda d, n: called.append(1) or tmp_path / "x.png")
    speak(e, "Take a screenshot"); speak(e, "no")
    assert called == [] and e.c.state == C.DONE
    speak(e, "Take a screenshot"); speak(e, "show my CPU usage")                             # boshqa buyruq — avvalgisini bekor qiladi, uni bajarmaydi
    assert called == [] and any(rec["outcome"] == "cancelled" for rec in e.records)
    speak(e, "yes")                                                                         # eski tasdiq endi amal qilmaydi
    assert called == []


def test_unclear_or_failed_speech_never_confirms_a_pending_action(app, tmp_path, monkeypatch):
    e = make(tmp_path)
    called = []
    monkeypatch.setattr(desktop, "take_screenshot", lambda d, n: called.append(1) or tmp_path / "x.png")
    speak(e, "Take a screenshot")
    e.c.space_pressed()
    e.says.append([stt.Heard("yes", "en-US", 0.2)])                                           # past ishonch — ham «ha» deb qabul qilinmaydi
    e.c.space_released(force=True)
    wait(lambda: e.c.state == C.DONE)
    assert called == [] and not e.c._awaiting and e.c.state == C.DONE and any(r == "user" and t == "yes" for r, t in e.msgs)
    assert not any(rec["outcome"] == "executed" for rec in e.records)


def test_enter_button_still_confirms_for_accessibility(app, tmp_path, monkeypatch):
    e = make(tmp_path)
    monkeypatch.setattr(desktop, "take_screenshot", lambda d, n: tmp_path / "ok.png")
    speak(e, "Take a screenshot")
    e.c.confirm()
    wait(lambda: e.c.state == C.DONE)
    assert "Screenshot saved" in last(e)


@pytest.mark.parametrize("word,expect", [("yes", "yes"), ("Ha", "yes"), ("xo'p", "yes"), ("да", "yes"), ("конечно", "yes"), ("okay", "yes"), ("no", "no"), ("yo'q", "no"),
                                         ("нет", "no"), ("bekor", "no"), ("cancel", "no"), ("yes delete everything now please", ""), ("open chrome", ""), ("", "")])
def test_yes_no_vocabulary(word, expect):
    assert commands.yes_no(word) == expect


# ================================================================== oyna, skrinshot
def test_window_command_reports_honestly(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "minimize this window")
    assert e.plat.calls == [("window", "minimize")] and "sent to Windows" in last(e) and "cannot verify" in last(e)
    e.plat.win_error = OSError("only on Windows")
    speak(e, "next window")
    assert "could not be sent" in last(e) and not e.c.last_ok


def test_screenshot_failure_is_not_reported_as_success(app, tmp_path, monkeypatch):
    e = make(tmp_path, confirm=False)
    monkeypatch.setattr(desktop, "take_screenshot", lambda d, n: (_ for _ in ()).throw(OSError("disk full")))
    speak(e, "Take a screenshot")
    assert "could not be taken" in last(e) and "saved" not in last(e) and not e.c.last_ok


def test_real_screenshot_file_is_written_offscreen(app, tmp_path):
    p = desktop.take_screenshot(tmp_path / "shots", NOW)
    assert p.is_file() and p.stat().st_size > 0 and p.suffix == ".png"
    p2 = desktop.take_screenshot(tmp_path / "shots", NOW)
    assert p2 != p and p.is_file()                                                          # mavjud fayl ustiga yozilmaydi


# ================================================================== clipboard
def test_clipboard_read_requires_confirmation_shows_text_and_does_not_log_it(app, tmp_path, monkeypatch):
    e = make(tmp_path)
    monkeypatch.setattr(desktop, "read_clipboard", lambda: "print('salom dunyo')\n# private note")
    speak(e, "Read my clipboard")
    assert e.c.state == C.CONFIRM and not any("salom" in t for r, t in e.msgs if r == "assistant")      # tasdiqlanmaguncha o'qilmaydi
    speak(e, "yes")
    assert "salom dunyo" in last(e) and "Clipboard" in last(e)
    assert not any("salom" in x for x in e.logs) and not any("salom" in str(r) for r in e.records)       # jurnal va tarixda yo'q
    assert not any("salom" in s for s in e.spk.said) and e.client.calls == []                             # ovoz bilan o'qilmaydi, AI'ga bormaydi


def test_clipboard_is_asked_even_when_confirmations_are_off(app, tmp_path, monkeypatch):
    e = make(tmp_path, confirm=False)
    read = []
    monkeypatch.setattr(desktop, "read_clipboard", lambda: read.append(1) or "hello")
    speak(e, "Read my clipboard")
    assert e.c.state == C.CONFIRM and read == []


@pytest.mark.parametrize("secret", ["my password: hunter2hunter2", "sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123", "AKIAABCDEFGHIJKLMNOP", "4111 1111 1111 1111",
                                    "-----BEGIN PRIVATE KEY-----\nMIIE", "api_key = 12345678abcd", "Zx9Kq2LmN8pR4tVw7YbC3dFg5HjA"])
def test_secret_looking_clipboard_is_never_shown_or_sent(app, tmp_path, monkeypatch, secret):
    e = make(tmp_path)
    monkeypatch.setattr(desktop, "read_clipboard", lambda: secret)
    speak(e, "Read my clipboard"); speak(e, "yes")
    assert "looks like a password" in last(e) and secret not in last(e)
    speak(e, "Summarize the copied text"); speak(e, "yes")
    assert e.client.calls == [] and "looks like a password" in last(e)


def test_empty_and_oversized_clipboard_are_handled(app, tmp_path, monkeypatch):
    e = make(tmp_path)
    monkeypatch.setattr(desktop, "read_clipboard", lambda: None)
    speak(e, "Read my clipboard"); speak(e, "yes")
    assert "empty" in last(e)
    monkeypatch.setattr(desktop, "read_clipboard", lambda: "word " * 5000)
    speak(e, "Summarize the copied text"); speak(e, "yes")
    assert "too long" in last(e) and e.client.calls == []


def test_clipboard_text_goes_to_ai_only_after_explicit_confirmation(app, tmp_path, monkeypatch):
    e = make(tmp_path)
    monkeypatch.setattr(desktop, "read_clipboard", lambda: "def f(x):\n    return x +\n")
    speak(e, "Explain the copied Python code")
    assert e.c.state == C.CONFIRM and "SEND" in e.c._ask_text() and e.client.calls == []
    speak(e, "no")
    assert e.client.calls == []                                                             # rad etilsa hech narsa yuborilmaydi
    speak(e, "Explain the copied Python code"); e.says.append("yes")
    e.c.space_pressed(); e.c.space_released(force=True)
    wait(lambda: e.client.calls)
    sent = e.client.calls[0][0][-1]["content"]
    assert "def f(x)" in sent and any("Sending the copied text" in t for r, t in e.msgs)
    assert not any("def f" in x for x in e.logs)


def test_secret_detector_has_no_false_positive_on_normal_text():
    for t in ("Python classes are blueprints for objects.", "Meeting at 15:00 in room 204", "Salom, bugun ob-havo yaxshi", "print('hello')", "2026-10-28"):
        assert not desktop.looks_secret(t), t


# ================================================================== veb
def test_open_site_always_shows_the_exact_url_and_waits_for_confirmation(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "open the website kun.uz")
    assert e.c.state == C.CONFIRM and "https://kun.uz/" in e.c._ask_text() and e.plat.calls == []
    speak(e, "yes")
    assert ("url", "https://kun.uz/") in e.plat.calls and "kun.uz" in last(e)


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "intranet.local", "xn--e1afmkfd.xn--p1ai", "a b.com", "evil.com/../x", "user@evil.com", "", "-bad.com", "a" * 70 + ".com"])
def test_executor_refuses_unsafe_hosts_even_if_a_command_is_forged(app, tmp_path, host):
    e = make(tmp_path, confirm=False)
    r = e.ex.execute(commands.Command("open_site", {"host": host}))
    assert not r.ok and e.plat.calls == []


def test_youtube_and_google_search_open_the_right_urls(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "Open YouTube and search for English lessons")
    speak(e, "Search the web for Python tutorials")
    urls = [c[1] for c in e.plat.calls if c[0] == "url"]
    assert urls == ["https://www.youtube.com/results?search_query=English+lessons", "https://www.google.com/search?q=python+tutorials"]


def test_youtube_without_a_query_asks_what_to_search(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "search on YouTube")
    assert "search for on YouTube" in last(e) and e.plat.calls == []
    speak(e, "guitar lessons")
    assert e.plat.calls and "guitar+lessons" in e.plat.calls[-1][1]


def test_browser_failure_is_reported(app, tmp_path):
    e = make(tmp_path, confirm=False)
    e.plat.open_url = lambda u: (_ for _ in ()).throw(OSError("no browser"))
    speak(e, "Search the web for cats")
    assert not e.c.last_ok and "no browser" in last(e)


# ================================================================== VS Code, papkalar
def test_vscode_opens_when_installed_and_fails_clearly_otherwise(app, tmp_path):
    e = make(tmp_path, confirm=False, exes={"vscode": Path("/x/Code.exe")})
    speak(e, "Open VS Code")
    assert e.plat.calls == [("exe", "/x/Code.exe")]
    e2 = make(tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path, confirm=False)
    speak(e2, "Open VS Code")
    assert e2.plat.calls == [] and not e2.c.last_ok


def test_open_music_folder_uses_the_known_folder(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "Open my music folder")
    assert e.plat.calls == [("folder", str(tmp_path))]


# ================================================================== kompyuter ma'lumoti (faqat so'ralganda)
def test_internet_check_reports_both_outcomes(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "Check my internet connection")
    assert "internet is working" in last(e) and "23 ms" in last(e)
    e2 = make(tmp_path, confirm=False, net=lambda: (_ for _ in ()).throw(services.NetworkError("timed out")))
    speak(e2, "Check my internet connection")
    assert "Could not reach the internet" in last(e2) and not e2.c.last_ok


def test_specs_are_shown_only_on_request(app, tmp_path):
    e = make(tmp_path, confirm=False)
    assert e.msgs == []
    speak(e, "Show my computer specifications")
    m = last(e)
    assert "Computer specifications" in m and "Memory" in m and "Processor" in m


# ================================================================== interfeys buyruqlari
def test_ui_commands(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "open the app settings"); assert e.nav == ["settings"]
    speak(e, "close the settings panel"); assert e.nav == ["settings", "assistant"]
    speak(e, "show available commands")
    assert "Available voice commands" in last(e) and "hold SPACE" in last(e) and "VS Code" in last(e)
    speak(e, "switch to dark mode"); assert "already in dark mode" in last(e)
    speak(e, "Show microphone status")
    assert "Ready" in last(e) and "does not listen at any other time" in last(e)
    speak(e, "Open Settings"); assert "Windows or the" in last(e) and e.nav == ["settings", "assistant"]
    speak(e, "app"); assert e.nav[-1] == "settings"


def test_mic_status_while_listening_is_listening(app, tmp_path):
    e = make(tmp_path)
    e.c.space_pressed()
    assert "Listening" in e.c._mic_status_text()
    e.c.space_released(force=True)
    wait(lambda: e.c.state in (C.DONE, C.IDLE, C.CONFIRM))


# ================================================================== ingliz tili mashqlari
def test_quiz_engine_is_deterministic_and_correct():
    q = english.Quiz("A1", 3, "uz", random.Random(1))
    t = q.start()
    assert "Question 1/3" in t.text or "Savol 1/3" in t.text
    results = []
    for _ in range(3):
        n = q.answer_idx
        wrong = 1 if n != 1 else 2
        results.append(q.answer(str(n if len(results) != 1 else wrong)))
    last_turn = results[-1]
    assert last_turn.done and last_turn.total == 3 and last_turn.correct == 2 and len(last_turn.wrong_words) == 1 and last_turn.saved


def test_quiz_options_are_unique_and_include_the_answer_for_every_word():
    for lvl in english.LEVELS:
        for lang in ("uz", "ru"):
            q = english.Quiz(lvl, english.MAX_QUESTIONS, lang, random.Random(3))
            q.start()
            for _ in range(q.n):
                assert len(set(q.options)) == 3 and q.options[q.answer_idx - 1] == q._tr(q.items[q.i])
                q.answer(str(q.answer_idx))
    assert english.Quiz("A1", 99, "uz").n <= english.MAX_QUESTIONS


def test_answer_by_option_number_word_or_translation():
    opts = ["olma", "kitob", "suv"]
    for said, expect in (("2", 2), ("ikki", 2), ("two", 2), ("B", 2), ("kitob", 2), ("uchinchi", 3), ("третий", 3), ("hmm", None)):
        assert english.pick_number(said, opts) == expect, said


def test_pronunciation_scoring():
    assert english.pronunciation_score("My name is Anna.", "my name is anna")[0] == 1.0
    sc, missed = english.pronunciation_score("She drinks water every morning", "she drink water morning")
    assert 0.3 < sc < 0.85 and "every" in missed
    assert english.pronunciation_score("hello world", "")[0] == 0.0


def test_vocab_bank_is_consistent():
    seen = set()
    for lvl, items in english.VOCAB.items():
        for en_, uz, ru in items:
            assert en_ and uz and ru and en_ not in seen, en_
            seen.add(en_)
    assert english.lookup("Improve")[1] == "yaxshilamoq" and english.lookup("zzzz") is None


def start_quiz(e, n=3):
    speak(e, f"Ask me {n} A1 vocabulary questions")
    assert e.c._lesson is not None


def test_quiz_by_voice_records_only_the_finished_session_and_adds_wrong_words(app, tmp_path):
    e = make(tmp_path, confirm=False)
    start_quiz(e, 3)
    assert "Question 1/3" in last(e) or "Savol 1/3" in last(e)
    assert e.ex.study.session_stats()["sessions"] == 0
    speak(e, str(e.c._lesson.answer_idx))                                                   # to'g'ri
    wrong = 1 if e.c._lesson.answer_idx != 1 else 2
    word = e.c._lesson.items[e.c._lesson.i][0]
    speak(e, str(wrong))                                                                    # noto'g'ri
    assert e.ex.study.session_stats()["sessions"] == 0                                      # hali tugamagan: yozilmaydi
    speak(e, str(e.c._lesson.answer_idx))
    assert e.c._lesson is None and "2 out of 3" in last(e) and "saved to your local history" in last(e)
    st = e.ex.study.session_stats()
    assert st == {"sessions": 1, "questions": 3, "correct": 2}
    assert [i.text for i in e.ex.study.items("word")] == [word] and "study" in e.changed
    speak(e, "Show my English learning progress")
    assert "Exercise sessions: 1" in last(e)


def test_stopping_a_quiz_records_only_the_answered_questions(app, tmp_path):
    e = make(tmp_path, confirm=False)
    start_quiz(e, 5)
    speak(e, str(e.c._lesson.answer_idx)); speak(e, "stop")
    assert e.c._lesson is None and e.ex.study.session_stats() == {"sessions": 1, "questions": 1, "correct": 1}
    start_quiz(e, 5); speak(e, "stop")
    assert e.ex.study.session_stats()["sessions"] == 1                                      # javobsiz to'xtatilgan mashq yozilmaydi


def test_unclear_answer_repeats_the_question_and_other_commands_end_the_lesson(app, tmp_path):
    e = make(tmp_path, confirm=False)
    start_quiz(e, 3)
    speak(e, "blah blah")
    assert "option number" in last(e) and e.c._lesson is not None
    speak(e, "next window")
    assert e.c._lesson is None and e.plat.calls == [("window", "next")] and e.ex.study.session_stats()["sessions"] == 0


def test_level_can_be_changed_by_voice_and_is_used_and_persisted(app, tmp_path):
    e = make(tmp_path, confirm=False)
    assert e.st.english_level == "A1"
    speak(e, "Set my English level to B1")
    assert e.st.english_level == "B1" and "changed to B1" in last(e)
    speak(e, "Ask me 2 vocabulary questions")
    assert e.c._lesson.level == "B1"
    speak(e, "stop")
    speak(e, "make the English lessons easier"); assert e.st.english_level == "A2"
    speak(e, "make the English lessons harder"); assert e.st.english_level == "B1"
    speak(e, "make the English lessons harder"); assert "limit" in last(e) and e.st.english_level == "B1"


def test_translate_word_locally_and_through_ai_when_unknown(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "Translate the word ‘improve’")
    assert "yaxshilamoq" in last(e) and "улучшать" in last(e) and e.client.calls == []
    speak(e, "Translate the word ‘serendipity’")
    wait(lambda: e.client.calls)
    assert "serendipity" in e.client.calls[0][0][-1]["content"]


def test_pronunciation_uses_english_recognition_and_scores_honestly(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "Test my pronunciation")
    target = e.c._lesson.target
    assert target in last(e)
    speak(e, "completely different words here")
    assert "Match:" in last(e) and e.c._lesson is not None and e.langs == ["auto", "en-US"] and e.ex.study.session_stats()["sessions"] == 0
    speak(e, target)
    assert e.langs[-1] == "en-US" and "Good!" in last(e) and "approximate" in last(e)
    assert e.c._lesson is None and e.ex.study.session_stats() == {"sessions": 1, "questions": 1, "correct": 1}
    speak(e, "Show my CPU usage")
    assert e.langs[-1] == "auto"                                                            # mashqdan keyin til sozlamaga qaytadi


def test_pronunciation_gives_up_after_three_attempts_without_claiming_success(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "Test my pronunciation")
    for _ in range(3):
        speak(e, "no no no")                                                                 # «no» bu yerda javob, tasdiq emas
    assert e.c._lesson is None and e.ex.study.session_stats() == {"sessions": 1, "questions": 1, "correct": 0}


def test_listening_speaks_the_sentence_in_english_and_hides_it_until_answered(app, tmp_path):
    e = make(tmp_path, confirm=False, voice=True)
    speak(e, "Give me a short listening exercise")
    les = e.c._lesson
    assert e.spk.said[-1] == les.sentence and e.spk.langs[-1] == "en" and les.sentence not in last(e)
    speak(e, "repeat")
    assert e.spk.said.count(les.sentence) == 2
    speak(e, str(les.right + 1))
    assert "Correct!" in last(e) and les.sentence in last(e) and e.c._lesson is None
    assert e.ex.study.session_stats() == {"sessions": 1, "questions": 1, "correct": 1}


def test_listening_falls_back_to_text_when_voice_output_is_off(app, tmp_path):
    e = make(tmp_path, confirm=False, voice=False)
    speak(e, "Give me a short listening exercise")
    assert e.c._lesson.sentence in last(e) and "Voice output is off" in last(e)


def test_lesson_start_shows_the_plan_and_opens_the_study_page(app, tmp_path):
    e = make(tmp_path, confirm=False)
    speak(e, "Start my English lesson")
    assert "Your level: A1" in last(e) and "Vocabulary 15" in last(e) and e.nav == ["study"]
    assert e.ex.study.history() == []                                                       # darsni boshlash hech narsani «bajarilgan» deb yozmaydi


def test_english_sessions_survive_in_the_database_and_can_be_cleared(app, tmp_path):
    e = make(tmp_path, confirm=False)
    e.ex.study.record_session("quiz", "A1", 10, 7)
    assert e.db.counts()["english_sessions"] == 1 and e.ex.study.sessions()[0]["correct"] == 7
    e.ex.study.clear_progress()
    assert e.db.counts()["english_sessions"] == 0


# ================================================================== fon tovushi va noaniq nutq
def test_low_confidence_background_speech_is_not_executed(app, tmp_path):
    e = make(tmp_path, confirm=False)
    e.says.append([stt.Heard("minimize this window", "en-US", 0.2)])
    e.c.space_pressed(); e.c.space_released(force=True)
    wait(lambda: e.c.state == C.DONE)
    assert e.plat.calls == [] and e.c.state == C.DONE and any(r == "user" and t == "minimize this window" for r, t in e.msgs)       # nima eshitilgani ko'rinadi, lekin bajarilmaydi


def test_music_lyrics_or_random_speech_trigger_nothing(app, tmp_path):
    e = make(tmp_path, confirm=False)
    for text in ("we will we will rock you", "la la la la", "и снова наступает ночь", "bugun havo juda issiq ekan", "the quick brown fox jumps over the lazy dog"):
        speak(e, text)
        assert e.plat.calls == [], text
    assert e.ex.reminders.all() == [] and e.ex.tasks.all() == [] and e.ex.notes.all() == []


def test_unsupported_and_unclear_commands_fail_safely(app, tmp_path):
    e = make(tmp_path, confirm=False)
    for text in ("order me a pizza", "send an email to my boss", "buy a new laptop", "open Telegram", "delete my downloads folder"):
        speak(e, text)
        assert e.plat.calls == [] and e.ex.notes.all() == [], text


def test_open_the_selected_file_refers_to_the_last_listed_results_only():
    from pyatnitsa import fileintent as f
    for t in ("Open the selected file", "tanlangan faylni och", "открой выбранный файл"):
        assert f.parse_choice(t, 1) == f.Choice("open", None), t
    assert f.parse_choice("open the selected file and delete it", 3) is None
