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
    AppSpec("winsettings", "Windows Sozlamalari", "uri"),
    AppSpec("vscode", "Visual Studio Code", "exe"),
    AppSpec("music", "Music papkasi", "folder"),
    AppSpec("pictures", "Pictures papkasi", "folder"),
    AppSpec("videos", "Videos papkasi", "folder"),
)}
URIS = {"winsettings": "ms-settings:"}                       # qat'iy: faqat shu URI sxemasi ochiladi
MEDIA_KEYS = {"play_pause": 0xB3, "next": 0xB0, "prev": 0xB1, "stop": 0xB2, "vol_up": 0xAF, "vol_down": 0xAE, "mute": 0xAD}   # Windows virtual-key kodlari

WINDOW_OPS = ("minimize", "maximize", "next", "prev")
URLS = {"youtube": "https://www.youtube.com/", "browser": "https://www.google.com/"}
_FOLDER_GUIDS = {  # Windows Known Folder ID
    "downloads": "{374DE290-123F-4565-9164-39C4925E467B}",
    "desktop": "{B4BFCC3A-DB2C-424C-B029-7FE99A87C641}",
    "documents": "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}",
    "pictures": "{33E28130-4E1E-4676-835A-98395C3BC3BB}",
    "music": "{4BD8D571-6D19-48D3-BE97-422220080E43}",
    "videos": "{18989B1D-99B5-49FC-B8E7-B2C0C5B20BD6}",
}
_FOLDER_NAMES = {"downloads": "Downloads", "desktop": "Desktop", "documents": "Documents", "pictures": "Pictures", "music": "Music", "videos": "Videos"}
KNOWN_FOLDERS = tuple(_FOLDER_NAMES)


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
        elif app_id == "vscode":
            local = os.environ.get("LocalAppData")
            roots = [Path(local) / "Programs" if local else None, *(Path(r) for r in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")) if r)]
            cands = [r / "Microsoft VS Code" / "Code.exe" for r in roots if r]
        else:
            return None
        return next((c for c in cands if c.is_file()), None)

    def start_exe(self, path: Path) -> None:
        """Argumentsiz, shell'siz ishga tushiradi; jarayon darhol xato bilan tugasa OSError ko'taradi."""
        proc = subprocess.Popen([str(path)], shell=False, close_fds=True)
        try:
            code = proc.wait(timeout=0.6)
        except subprocess.TimeoutExpired:
            return                                   # ishlab turibdi — yaxshi
        if code != 0:
            raise OSError(f"jarayon {code} kodi bilan tugadi")

    def open_folder(self, path: Path) -> None:
        os.startfile(str(path))    # type: ignore[attr-defined]  # faqat Windows

    def open_file(self, path: Path) -> None:
        """Faylni bog'langan ilovada OCHADI (dastur sifatida ISHGA TUSHIRMAYDI: chaqiruvchi kengaytmani oldindan tekshiradi).
        Windows ilovani ishga tushirish so'rovini qabul qilsa qaytadi; ilova haqiqatan ochilganini bu yerdan bilib bo'lmaydi."""
        if sys.platform != "win32":
            raise OSError("Fayllarni bog'langan ilovada ochish faqat Windows'da ishlaydi")
        os.startfile(str(path))    # type: ignore[attr-defined]

    def start_player(self, player: Path, path: Path) -> None:
        """Foydalanuvchi tanlagan pleyer bilan ochadi: shell'siz, argumentlar ro'yxat sifatida. Darhol xato bilan tugasa OSError."""
        proc = subprocess.Popen([str(player), str(path)], shell=False, close_fds=True)
        try:
            code = proc.wait(timeout=0.8)
        except subprocess.TimeoutExpired:
            return                                   # ishlab turibdi
        if code != 0:
            raise OSError(f"pleyer {code} kodi bilan tugadi")

    def open_uri(self, app_id: str) -> None:
        """Faqat `URIS` dagi qat'iy URI (masalan `ms-settings:`)."""
        uri = URIS.get(app_id)
        if not uri:
            raise ValueError("Ruxsat etilmagan URI")
        if sys.platform != "win32":
            raise OSError("Windows Sozlamalari faqat Windows'da ochiladi")
        os.startfile(uri)    # type: ignore[attr-defined]

    def media_key(self, name: str) -> None:
        """Windows media tugmasini bosadi (ijro/pauza, keyingi, oldingi, ovoz). Faol media dastur javob berganini BILIB BO'LMAYDI."""
        vk = MEDIA_KEYS.get(name)
        if vk is None:
            raise ValueError("Noma'lum media buyrug'i")
        if sys.platform != "win32":
            raise OSError("Media tugmalari faqat Windows'da ishlaydi")
        import ctypes
        user32 = ctypes.windll.user32
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)       # KEYEVENTF_KEYUP

    def window_op(self, op: str) -> None:
        """Faol oynani boshqaradi (kichraytirish/kattalashtirish) yoki oynalar orasida o'tadi (Alt+Tab). Shell yo'q, faqat Windows API."""
        if op not in WINDOW_OPS:
            raise ValueError("Noma'lum oyna buyrug'i")
        if sys.platform != "win32":
            raise OSError("Oynalarni boshqarish faqat Windows'da ishlaydi")
        import ctypes
        u = ctypes.windll.user32
        if op in ("minimize", "maximize"):
            hwnd = u.GetForegroundWindow()
            if not hwnd:
                raise OSError("Faol oyna topilmadi")
            u.ShowWindow(hwnd, 6 if op == "minimize" else 3)      # SW_MINIMIZE / SW_MAXIMIZE
            return
        keys = [0x12, 0x09] if op == "next" else [0x12, 0x10, 0x09]   # Alt+Tab / Alt+Shift+Tab
        for k in keys:
            u.keybd_event(k, 0, 0, 0)
        for k in reversed(keys):
            u.keybd_event(k, 0, 2, 0)

    def open_in_notepad(self, path: Path) -> None:
        """Kod/matn faylini Notepad'da ko'rish uchun ochadi (hech qachon ishga tushirmaydi)."""
        exe = self.find_executable("notepad")
        if not exe:
            raise OSError("Notepad topilmadi")
        proc = subprocess.Popen([str(exe), str(path)], shell=False, close_fds=True)
        try:
            code = proc.wait(timeout=0.6)
        except subprocess.TimeoutExpired:
            return
        if code != 0:
            raise OSError(f"Notepad {code} kodi bilan tugadi")

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
