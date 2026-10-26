import time

import pytest
from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pyatnitsa import controller as C, health
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings
from pyatnitsa.ui import STYLE, MainWindow
from test_controller import FakeRecorder, FakeSpeaker
from test_executor import FakePlatform


@pytest.fixture
def win():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLE)
    st = Settings()
    mon = health.HealthMonitor()
    plat = FakePlatform()
    ctrl = C.Controller(st, Executor(st, plat, mon), FakeSpeaker(), FakeRecorder, lambda r, l: "Hozirgi vaqtni ayt")
    w = MainWindow(st, ctrl, mon, ctrl.speaker)
    w.show(); w.activateWindow(); app.processEvents()
    yield w, ctrl
    app.removeEventFilter(w); mon.stop(); ctrl.shutdown(); w.close_for_test = True


def test_enter_sends_shift_enter_newline(win):
    w, ctrl = win
    w.input.setFocus()
    QTest.keyClicks(w.input, "salom")
    QTest.keyClick(w.input, Qt.Key_Return, Qt.ShiftModifier)
    QTest.keyClicks(w.input, "dunyo")
    assert w.input.toPlainText() == "salom\ndunyo"
    w.input.clear(); QTest.keyClicks(w.input, "Hozirgi vaqtni ayt"); QTest.keyClick(w.input, Qt.Key_Return)
    assert w.input.toPlainText() == "" and ctrl.state == C.CONFIRM
    assert any(r == "user" and "vaqt" in t for r, t in w.log)


def test_text_command_without_microphone(win):
    w, ctrl = win
    FakeRecorder.instances.clear()
    w.input.setPlainText("Hozirgi vaqtni ayt"); w.send_text()
    ctrl.confirm()
    end = time.time() + 3
    while ctrl.state != C.DONE and time.time() < end:
        QCoreApplication.processEvents(); time.sleep(0.01)
    assert not FakeRecorder.instances and "soat" in w.log[-1][1]


def test_space_toggles_only_outside_text_input(win):
    w, ctrl = win
    w.input.setFocus(); QTest.keyClick(w.input, Qt.Key_Space)
    assert ctrl.state == C.IDLE and " " in w.input.toPlainText()    # yozayotganda Space mikrofonni yoqmaydi
    w.mic_btn.setFocus(); w.stack.setFocus()
    QTest.keyClick(w, Qt.Key_Space)
    assert ctrl.state == C.LISTENING
    QTest.keyClick(w, Qt.Key_Space)
    assert ctrl.state != C.LISTENING


def test_health_page_renders_real_data(win):
    w, _ = win
    w.show_page(1)
    w.health_page.monitor.sample()
    w.health_page.refresh()
    assert "%" in w.health_page.cpu_big.text() and "%" in w.health_page.ram_big.text()
    assert "Batareya" in w.health_page.bat_body.text()
