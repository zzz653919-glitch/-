"""Ruxsat etilgan dasturlar/papkalar ro'yxati va ularni xavfsiz ochuvchi Windows qatlami."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppSpec:
    id: str
    title: str
    kind: str          # exe | folder | url | browser


APPS: dict[str, AppSpec] = {a.id: a for a in (
    AppSpec("chrome", "Google Chrome", "exe"),
    AppSpec("browser", "Brauzer (standart)", "browser"),
    AppSpec("new_window", "Yangi brauzer oynasi", "browser"),
    AppSpec("downloads", "Downloads papkasi", "folder"),
    AppSpec("desktop", "Desktop papkasi", "folder"),
    AppSpec("documents", "Documents papkasi", "folder"),
    AppSpec("calculator", "Kalkulyator", "exe"),
    AppSpec("notepad", "Notepad", "exe"),
    AppSpec("explorer", "Fayl menejeri", "exe"),
    AppSpec("youtube", "YouTube", "url"),
    AppSpec("search", "Google'da qidiruv", "url"),
)}

URLS = {"youtube": "https://www.youtube.com/", "browser": "https://www.google.com/"}
_FOLDER_GUIDS = {  # Windows Known Folder ID
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
}
_FOLDER_NAMES = {"downloads": "Downloads", "desktop": "Desktop", "documents": "Documents"}


class Platform:
    """Barcha tashqi ta'sirlar shu yerda; testlarda almashtiriladi."""

    def folder_path(self, app_id: str) -> Path | None:
        if sys.platform == "win32" and app_id in _FOLDER_GUIDS:
            try:
                import ctypes
                from ctypes import wintypes
                import uuid
                buf = ctypes.c_wchar_p()
                guid = uuid.UUID(_FOLDER_GUIDS[app_id])
                class GUID(ctypes.Structure):
                    _fields_ = [("a", wintypes.DWORD), ("b", wintypes.WORD), ("c", wintypes.WORD),
                                ("d", ctypes.c_ubyte * 8)]
                g = GUID(guid.time_low, guid.time_mid, guid.time_hi_version, (ctypes.c_ubyte * 8)(*guid.bytes[8:]))
                if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(g), 0, None, ctypes.byref(buf)) == 0:
                    p = Path(buf.value)
                    ctypes.windll.ole32.CoTaskMemFree(buf)
                    return p
            except Exception:  # noqa: BLE001
                log.exception("Known folder aniqlanmadi")
        name = _FOLDER_NAMES.get(app_id)
        return Path.home() / name if name else None

    def find_executable(self, app_id: str) -> Path | None:
        sysroot = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        if app_id == "chrome":
            roots = [os.environ.get(v) for v in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData")]
            cands = [Path(r) / "Google" / "Chrome" / "Application" / "chrome.exe" for r in roots if r]
        elif app_id == "calculator":
            cands = [sysroot / "System32" / "calc.exe"]
        elif app_id == "notepad":
            cands = [sysroot / "System32" / "notepad.exe"]
        elif app_id == "explorer":
            cands = [sysroot / "explorer.exe"]
        else:
            return None
        return next((c for c in cands if c.is_file()), None)

    def start_exe(self, path: Path) -> None:
        subprocess.Popen([str(path)], shell=False, close_fds=True)   # argumentlarsiz, shell'siz

    def open_folder(self, path: Path) -> None:
        os.startfile(str(path))    # type: ignore[attr-defined]  # faqat Windows

    def open_url(self, url: str) -> None:
        p = urlparse(url)
        if p.scheme != "https" or not p.netloc:
            raise ValueError("Faqat https manzillar ochiladi")
        if not webbrowser.open(url):
            raise OSError("Brauzer ochilmadi")

    def open_new_window(self, url: str) -> None:
        if urlparse(url).scheme != "https":
            raise ValueError("Faqat https manzillar ochiladi")
        if not webbrowser.open_new(url):
            raise OSError("Brauzer ochilmadi")
