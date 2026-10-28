"""«File Access» sahifasi: ruxsat berish/bekor qilish, qidirish, ochish, xato xabarlari, maket. Dialoglar monkeypatch bilan almashtirilgan."""
import os
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QFileDialog

from pyatnitsa import controller as C, files as fs, health
from pyatnitsa.ai_chat import ChatService
from pyatnitsa.executor import Executor
from pyatnitsa.gui.main_window import MainWindow
from pyatnitsa.gui.theme import STYLE
from pyatnitsa.settings import Settings
from test_controller import FakeRecorder, FakeSpeaker
from test_conversation import FakeClient
from test_executor import FakePlatform
from test_files import build_tree
from test_ui import pump


@pytest.fixture
def fw(tmp_path):
    app = QApplication.instance() or QApplication([])
    if not app.styleSheet():
        app.setStyleSheet(STYLE)
    FakeRecorder.instances.clear()
    tree = build_tree(tmp_path)
    st = Settings(); st.reduce_motion = "on"; st.voice_enabled = False; st.confirm_commands = True; st.ai_notice_shown = True
    mon = health.HealthMonitor()
    plat = FakePlatform({"chrome": Path("/x/chrome.exe")}, tree)
    fa = fs.FileAccess(st, save=False)
    client = FakeClient()
    ctrl = C.Controller(st, Executor(st, plat, mon, files=fa), FakeSpeaker(), FakeRecorder, lambda r, l: "x", post_roll_ms=0, ai=ChatService(st, client))
    w = MainWindow(st, ctrl, mon, ctrl.speaker)
    w.show(); w.activateWindow(); app.processEvents()
    w.navs["files"].click(); app.processEvents()
    yield app, w, ctrl, plat, fa, tree, st
    app.removeEventFilter(w); w.files_page.stop(); w.bridge.stop(join=True); mon.stop(); ctrl.shutdown()
    w.hide(); w.deleteLater(); app.processEvents()


def grant(page, tree):
    page._pick_folder = lambda start="": str(tree)
    page.add_btn.click()


def rows(page):
    return [[page.table.item(r, c).text() for c in range(5)] for r in range(page.table.rowCount())]


def test_files_page_exists_with_all_controls_and_navigation(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    assert w.navs["files"].text() == "File Finder" and w.stack.currentWidget() is w.pages["files"]
    p = w.files_page
    for widget in (p.roots, p.add_btn, p.std_btn, p.rm_btn, p.query, p.kind, p.search_btn, p.table, p.open_btn, p.status, p.perm):
        assert widget is not None
    assert [p.kind.itemText(i) for i in range(p.kind.count())][:5] == ["All files", "Videos", "Images", "Audio", "Documents"]
    for key in list(w.navs):                                                                           # barcha sahifalar
        w.navs[key].click(); app.processEvents()
        assert w.stack.currentWidget() is w.pages[key]


def test_initial_state_without_permission(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    assert "No folders authorized" in p.perm.text() and not p.search_btn.isEnabled() and not p.rm_btn.isEnabled() and not p.open_btn.isEnabled()
    assert p.roots.count() == 0


def test_add_folder_authorizes_remembers_and_shows_it(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    seen, logs = [], []
    p.accessChanged.connect(lambda: seen.append(1))
    ctrl.log.connect(lambda lvl, t: logs.append(t))
    grant(p, tree)
    assert p.roots.count() == 1 and str(Path(os.path.realpath(tree))) in p.roots.item(0).text() and "1 location authorized" in p.perm.text()
    assert st.file_roots == [str(Path(os.path.realpath(tree)))] and seen == [1] and p.search_btn.isEnabled() and "Access granted" in p.status.text()
    assert any("[SECURITY] File access granted" in t for t in logs)                       # terminalga haqiqiy hodisa yoziladi


def test_protected_duplicate_and_cancelled_choices_show_clear_errors(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    if os.name != "nt":
        p._pick_folder = lambda start="": "/etc"; p.add_btn.click()
        assert "protected system location" in p.status.text() and st.file_roots == []
    grant(p, tree); grant(p, tree)
    assert "already authorized" in p.status.text() and p.roots.count() == 1
    p._pick_folder = lambda start="": ""; p.add_btn.click()                       # dialog bekor qilindi — o'zgarmaydi
    assert p.roots.count() == 1
    p._pick_folder = lambda start="": str(tree / "missing"); p.add_btn.click()
    assert "does not exist" in p.status.text()


def test_drive_level_authorization_needs_an_extra_confirmation(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    asked = []
    p._confirm = lambda title, text: asked.append(title) or False
    p._pick_folder = lambda start="": os.path.abspath(os.sep)
    p.add_btn.click()
    assert asked and "whole drive" in asked[0] and st.file_roots == [] and "not granted" in p.status.text()


def test_standard_folder_menu_adds_known_folders(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    assert [a.text() for a in p.std_btn.menu().actions()] == ["Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos"]
    p.add_standard("downloads")
    assert p.roots.count() == 1
    plat.tmp = tree / "nope"
    p.add_standard("music")
    assert "not found" in p.status.text()


def test_search_shows_name_location_type_and_open_file_works(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    grant(p, tree)
    p.query.setText("holiday"); p.search_btn.click()
    assert pump(app, lambda: p.table.rowCount() == 2, t=5)
    r = rows(p)
    assert {x[0] for x in r} == {"holiday_2025.mp4", "holiday_old.mkv"} and all(str(tree) in x[2] for x in r) and {x[1] for x in r} == {"video"}
    assert not p.open_btn.isEnabled()
    p.table.selectRow(0)
    assert p.open_btn.isEnabled()
    chosen = Path(p.selected_path())
    p.open_btn.click()
    assert pump(app, lambda: plat.calls, t=5)
    assert plat.calls == [("file", str(Path(os.path.realpath(chosen))))]
    pump(app, lambda: ctrl.state in (C.DONE, C.IDLE))
    assert "yuborildi" in w.files_page.status.text() and chosen.name in w.files_page.status.text()      # natija sahifada ham ko'rinadi (tasdiqlangani emas — so'rov yuborilgani)


def test_type_filter_and_empty_query(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    grant(p, tree)
    p.kind.setCurrentIndex(p.kind.findData("audio")); p.search_btn.click()
    assert pump(app, lambda: p.table.rowCount() == 1, t=5) and rows(p)[0][0] == "song.mp3"
    p.kind.setCurrentIndex(p.kind.findData("video")); p.query.setText("")
    p.query.returnPressed.emit()
    assert pump(app, lambda: p.table.rowCount() >= 6, t=5) and {x[1] for x in rows(p)} == {"video"}


def test_nothing_found_message(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    grant(p, tree)
    p.query.setText("nosuchfile123"); p.search_btn.click()
    assert pump(app, lambda: p.table.isHidden() and "Nothing found" in p.empty.text(), t=5)
    assert "0 result" in p.status.text()


def test_search_without_permission_is_refused(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    p.search()
    assert "No folders are authorized" in p.status.text() and p.table.rowCount() == 0


def test_cancel_button_stops_a_running_search(fw, monkeypatch):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    grant(p, tree)
    started = threading.Event()

    def slow(q, roots=None, cancel=None, **kw):
        started.set()
        cancel.wait(5)
        return fs.SearchOutcome(cancelled=cancel.is_set())
    monkeypatch.setattr(fa, "search", slow)
    p.search_btn.click()
    assert started.wait(3) and not p.cancel_btn.isHidden() and not p.search_btn.isEnabled()
    p.cancel_btn.click()
    assert pump(app, lambda: p.cancel_btn.isHidden() and "cancelled" in p.status.text(), t=5)


def test_remove_access_revokes_immediately(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    grant(p, tree)
    p.query.setText("holiday"); p.search_btn.click()
    assert pump(app, lambda: p.table.rowCount() == 2, t=5)
    p.table.selectRow(0)
    stale = p.selected_path()
    assert not p.rm_btn.isEnabled()
    p.roots.setCurrentRow(0)
    assert p.rm_btn.isEnabled()
    p.rm_btn.click()
    assert st.file_roots == [] and p.roots.count() == 0 and p.table.rowCount() == 0 and "revoked" in p.status.text() and not p.search_btn.isEnabled()
    assert "No folders authorized" in p.perm.text()
    ctrl.open_path(stale)                                   # eski natijadan ochishga urinish endi rad etiladi
    pump(app, lambda: ctrl.state in (C.DONE, C.IDLE))
    assert plat.calls == [] and ctrl._choices == []


def test_command_without_permission_opens_the_page_and_asks_then_reruns(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    w.navs["assistant"].click()
    asked = []
    p._confirm = lambda title, text: asked.append(text) or True
    ctrl.submit_text("Downloads papkasidan videoni top")
    assert pump(app, lambda: st.file_roots, t=5)
    assert asked and str(tree) in asked[0] and "Only this folder" in asked[0] and w.current == "files"
    assert pump(app, lambda: any("example.mp4" in b.bubble._body.text() for b in w.chat._bubbles), t=5)       # buyruq ruxsatdan keyin qayta bajarildi
    assert plat.calls == []


def test_declining_the_permission_dialog_searches_nothing(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    p._confirm = lambda title, text: False
    ctrl.submit_text("Downloads papkasidan videoni top")
    pump(app, lambda: w.current == "files", t=3)
    assert st.file_roots == [] and "not granted" in p.status.text() and not any("example.mp4" in b.bubble._body.text() for b in w.chat._bubbles)


def test_first_use_without_a_hint_offers_a_folder_picker(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    plat.tmp = None
    calls = []
    p._confirm = lambda title, text: calls.append(title) or True
    p._pick_folder = lambda start="": str(tree)
    ctrl.submit_text("Find the video named example.mp4")
    assert pump(app, lambda: st.file_roots, t=5) and calls == ["Choose a folder"]


def test_file_names_are_displayed_as_plain_text(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    (tree / "<b>BOLD<i>.mp4").write_bytes(b"x")
    grant(p, tree)
    ctrl.submit_text("Find the video named BOLD")
    assert pump(app, lambda: any("<b>BOLD<i>.mp4" in b.bubble._body.text() for b in w.chat._bubbles), t=5)
    body = next(b.bubble._body for b in w.chat._bubbles if "<b>BOLD<i>.mp4" in b.bubble._body.text())
    assert body.textFormat() == Qt.PlainText
    p.query.setText("BOLD"); p.search_btn.click()
    assert pump(app, lambda: p.table.rowCount() == 1, t=5) and p.table.item(0, 0).text() == "<b>BOLD<i>.mp4"


def test_video_player_choice_is_saved_and_can_be_reset(fw, monkeypatch, tmp_path):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    exe = tmp_path / "player.exe"; exe.write_bytes(b"x")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(exe), "")))
    p.player_btn.click()
    assert st.video_player == str(exe) and str(exe) in p.player_lbl.text()
    txt = tmp_path / "x.txt"; txt.write_text("x")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(txt), "")))
    p.player_btn.click()
    assert st.video_player == str(exe) and "program" in p.status.text()
    p.player_reset.click()
    assert st.video_player == "" and p.player_lbl.text() == "Windows default"


def test_roots_from_a_previous_session_are_shown_and_unavailable_ones_are_marked(fw, tmp_path):
    app, w, ctrl, plat, fa, tree, st = fw
    st.file_roots[:] = [str(tree), str(tmp_path / "gone")]
    w.files_page.refresh()
    assert w.files_page.roots.count() == 2 and "unavailable" in w.files_page.roots.item(1).text() and "1 location authorized" in w.files_page.perm.text()


def test_layout_is_responsive_on_the_files_page(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    p = w.files_page
    grant(p, tree); p.query.setText("e"); p.search_btn.click()
    assert pump(app, lambda: p.table.rowCount() > 0, t=5)
    for size in ((980, 660), (1400, 900), (1920, 1080)):
        w.resize(*size); app.processEvents()
        assert p.table.isVisible() and p.open_btn.isVisible() and p.add_btn.isVisible() and p.table.height() > 40 and p.width() > 500
    w.showMaximized(); app.processEvents(); w.showNormal(); app.processEvents()


def test_settings_page_shows_authorized_locations_and_links_to_file_access(fw):
    app, w, ctrl, plat, fa, tree, st = fw
    sp = w.settings_page
    assert "No folders are authorized" in sp.files_info.text()
    grant(w.files_page, tree)
    assert str(Path(os.path.realpath(tree))) in sp.files_info.text() and "only these locations" in sp.files_info.text()
    w.navs["settings"].click(); app.processEvents()
    sp.files_btn.click(); app.processEvents()
    assert w.current == "files"
    w.files_page.roots.setCurrentRow(0); w.files_page.rm_btn.click()
    assert "No folders are authorized" in sp.files_info.text()
