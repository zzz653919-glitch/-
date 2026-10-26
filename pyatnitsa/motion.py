"""Animatsiyalarni kamaytirish: sozlama yoki Windows'ning «animatsiyalarni o'chirish» tanlovi bo'yicha."""
from __future__ import annotations

import sys


def system_prefers_reduced_motion() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes
        flag = wintypes.BOOL(True)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(flag), 0)   # SPI_GETCLIENTAREAANIMATION
        return bool(ok) and not flag.value
    except Exception:  # noqa: BLE001
        return False


def reduced(setting: str) -> bool:
    return setting == "on" or (setting == "system" and system_prefers_reduced_motion())
