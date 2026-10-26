"""Ixtiyoriy global Space tugmasi (standart: o'chiq). Faqat foydalanuvchi sozlamada yoqsa ishlaydi."""
from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


class GlobalHotkey(QObject):
    pressed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handle = None
        self._last = 0.0

    @property
    def enabled(self) -> bool:
        return self._handle is not None

    def set_enabled(self, on: bool) -> tuple[bool, str]:
        if on == self.enabled:
            return True, ""
        try:
            import keyboard
        except Exception:  # noqa: BLE001
            return False, "Global tugma uchun `keyboard` kutubxonasi (faqat Windows) o'rnatilmagan."
        try:
            if on:
                self._handle = keyboard.add_hotkey("space", self._fire, suppress=False)
            else:
                keyboard.remove_hotkey(self._handle)
                self._handle = None
            return True, ""
        except Exception as e:  # noqa: BLE001
            log.exception("Global tugma o'zgarmadi")
            self._handle = None
            return False, f"Global Space tugmasini sozlab bo'lmadi: {e}"

    def _fire(self) -> None:
        now = time.monotonic()
        if now - self._last > 0.4:      # tugmani ushlab turishdagi takrorlanishlarni e'tiborsiz qoldirish
            self._last = now
            self.pressed.emit()
