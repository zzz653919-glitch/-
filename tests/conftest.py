import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["PYATNITSA_HOME"] = tempfile.mkdtemp(prefix="pyat-test-")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import gc

import pytest


@pytest.fixture(autouse=True)
def _dispose_qt_objects_on_main_thread(monkeypatch):
    """Testda yaratilgan har bir Controller test oxirida asosiy oqimda yopiladi va o'chiriladi.
    Aks holda uning QTimer'lari tsiklik axlatda qolib, GC ularni tasodifan boshqa oqimda yo'q qiladi:
    "Timers cannot be stopped from another thread" + segfault."""
    made = []
    try:
        from pyatnitsa import controller as ctl
        orig = ctl.Controller.__init__

        def tracked(self, *a, **kw):
            orig(self, *a, **kw)
            made.append(self)

        monkeypatch.setattr(ctl.Controller, "__init__", tracked)
    except Exception:  # noqa: BLE001 - PySide6 bo'lmasa ham testlar ishlayversin
        pass
    yield
    had_qt = bool(made)
    for c in made:
        try:
            c.shutdown()
            c.deleteLater()
        except Exception:  # noqa: BLE001 - allaqachon yopilgan bo'lishi mumkin
            pass
    made.clear()
    if not had_qt:
        return
    try:
        from PySide6.QtCore import QCoreApplication, QEvent
        app = QCoreApplication.instance()
        if app is not None:
            app.processEvents()
            app.sendPostedEvents(None, QEvent.DeferredDelete)
    except Exception:  # noqa: BLE001
        pass
    gc.collect()
