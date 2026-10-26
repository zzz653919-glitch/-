"""Sozlamalar: JSON faylda saqlanadi, noto'g'ri qiymatlar xavfsiz standartga qaytadi."""
from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import APP_ID

log = logging.getLogger(__name__)

STT_LANGUAGES = [("O'zbekcha", "uz-UZ"), ("Русский", "ru-RU"), ("English", "en-US")]
TTS_ENGINES = [("Avto (internet ovozi, keyin tizim ovozi)", "auto"),
               ("Faqat tizim ovozi (oflayn)", "system")]


def data_dir() -> Path:
    override = os.environ.get("PYATNITSA_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / APP_ID
    else:
        base = Path.home() / ".config" / APP_ID.lower()
    base.mkdir(parents=True, exist_ok=True)
    return base


@dataclass
class Settings:
    stt_language: str = "uz-UZ"
    microphone: str | None = None          # qurilma nomi; None = tizim standarti
    voice_enabled: bool = True
    tts_engine: str = "auto"
    volume: float = 0.8
    confirm_commands: bool = True          # har bir buyruq bajarilishidan oldin tasdiq
    autostart: bool = False                # standart: o'chiq
    global_space: bool = False             # standart: o'chiq
    city: str = "Tashkent"
    allowed_apps: dict[str, bool] = field(default_factory=dict)

    # ---- saqlash / yuklash -------------------------------------------------
    @staticmethod
    def path() -> Path:
        return data_dir() / "settings.json"

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        s = cls()
        path = path or cls.path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return s
        except Exception:
            log.exception("Sozlamalar o'qilmadi, standartlar ishlatiladi")
            return s
        if not isinstance(raw, dict):
            return s
        defaults = asdict(s)
        for key, default in defaults.items():
            if key not in raw:
                continue
            val = raw[key]
            if key == "microphone":
                ok = val is None or isinstance(val, str)
            elif isinstance(default, bool):
                ok = isinstance(val, bool)
            elif isinstance(default, float):
                ok = isinstance(val, (int, float)) and not isinstance(val, bool)
                val = float(val) if ok else val
            elif isinstance(default, dict):
                ok = isinstance(val, dict) and all(
                    isinstance(k, str) and isinstance(v, bool) for k, v in val.items())
            else:
                ok = isinstance(val, str)
            if ok:
                setattr(s, key, val)
        s.volume = min(1.0, max(0.0, s.volume))
        if s.tts_engine not in {v for _, v in TTS_ENGINES}:
            s.tts_engine = "auto"
        if s.stt_language not in {v for _, v in STT_LANGUAGES}:
            s.stt_language = "uz-UZ"
        s.city = s.city.strip()[:80] or "Tashkent"
        return s

    def save(self, path: Path | None = None) -> None:
        path = path or self.path()
        try:
            fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(asdict(self), f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except Exception:
            log.exception("Sozlamalar saqlanmadi")

    def is_app_allowed(self, app_id: str) -> bool:
        return self.allowed_apps.get(app_id, True)


def set_autostart(enabled: bool) -> tuple[bool, str]:
    """Windows'da HKCU\\...\\Run orqali avtomatik ochilish. Faqat foydalanuvchi yoqsa."""
    if sys.platform != "win32":
        return False, "Avtomatik ochilish faqat Windows'da ishlaydi."
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                             r"Software\Microsoft\Windows\CurrentVersion\Run",
                             0, winreg.KEY_SET_VALUE)
        with key:
            if enabled:
                exe = Path(sys.executable)
                pyw = exe.with_name("pythonw.exe")
                runner = pyw if pyw.exists() else exe
                main = Path(__file__).resolve().parent.parent / "main.py"
                winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, f'"{runner}" "{main}"')
            else:
                try:
                    winreg.DeleteValue(key, APP_ID)
                except FileNotFoundError:
                    pass
        return True, ""
    except Exception as e:  # noqa: BLE001
        log.exception("Autostart o'zgarmadi")
        return False, f"Avtomatik ochilishni sozlab bo'lmadi: {e}"
