"""ПЯТНИЦА — ishga tushirish nuqtasi."""
import logging
import logging.handlers
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from pyatnitsa import APP_NAME
from pyatnitsa.settings import Settings, data_dir


def main() -> int:
    handler = logging.handlers.RotatingFileHandler(data_dir() / "pyatnitsa.log", maxBytes=500_000, backupCount=2, encoding="utf-8")
    from pyatnitsa.credentials import RedactFilter            # jurnalga API kalit hech qachon tushmasligi uchun
    handler.addFilter(RedactFilter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    log = logging.getLogger("main")
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(True)

    def excepthook(et, ev, tb):       # dastur xatodan keyin yopilib qolmasin
        log.error("Kutilmagan xato", exc_info=(et, ev, tb))
        try:
            QMessageBox.warning(None, APP_NAME, f"Kutilmagan xato yuz berdi, lekin dastur ishlashda davom etadi.\n\n{ev}")
        except Exception:  # noqa: BLE001
            pass

    sys.excepthook = excepthook
    from pyatnitsa import health
    from pyatnitsa.ai_chat import ChatService
    from pyatnitsa.controller import Controller
    from pyatnitsa.executor import Executor
    from pyatnitsa.tts import Speaker
    from pyatnitsa.ui import STYLE, MainWindow

    app.setStyleSheet(STYLE)
    settings = Settings.load()
    monitor = health.HealthMonitor()
    speaker = Speaker(settings)
    ctrl = Controller(settings, Executor(settings, monitor=monitor), speaker, ai=ChatService(settings))
    win = MainWindow(settings, ctrl, monitor, speaker)
    win.show()
    ctrl.start_scheduler()                     # eslatmalarni tekshirish (faqat ilova ochiq paytida)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
