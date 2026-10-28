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

STT_LANGUAGES = [("Auto (Uzbek + Russian + English)", "auto"), ("Uzbek (O'zbekcha)", "uz-UZ"), ("Russian (Русский)", "ru-RU"), ("English", "en-US")]
TTS_ENGINES = [("Auto (online voice, then system voice)", "auto"),
               ("System voice only (offline)", "system")]


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
    stt_language: str = "auto"
    stt_engine: str = "google"             # google | whisper (oflayn, ixtiyoriy)
    whisper_model: str = "base"            # tiny | base | small
    auto_stop_silence: bool = False        # jimlikdan keyin avtomatik to'xtatish (ixtiyoriy)
    microphone: str | None = None          # qurilma nomi; None = tizim standarti
    voice_enabled: bool = True
    voice_gender: str = "male"             # male | female
    tts_engine: str = "auto"
    volume: float = 0.8
    ai_enabled: bool = True                # suhbat AI (kalit sozlanmasa, aniq ko'rsatma beriladi)
    ai_model: str = ""                     # bo'sh = standart (claude-opus-5-5)
    ai_effort: str = "low"                 # low | medium | high  (suhbat uchun tez javob)
    ai_max_tokens: int = 4096
    ai_timeout_s: int = 60
    ai_context_messages: int = 16
    ai_fallback: bool = True               # Opus'da rad etilganda serverdagi qayta urinish
    ai_notice_shown: bool = False
    voice_rate: int = 0                    # -50..+50 (%)
    reduce_motion: str = "system"          # system | on | off
    show_terminal: bool = True
    confirm_commands: bool = True          # har bir buyruq bajarilishidan oldin tasdiq
    autostart: bool = False                # standart: o'chiq
    city: str = "Tashkent"
    allowed_apps: dict[str, bool] = field(default_factory=dict)
    file_roots: list[str] = field(default_factory=list)   # foydalanuvchi AYNAN ruxsat bergan papkalar/disklar (qolgan hech narsaga kirilmaydi)
    video_player: str = ""                 # ixtiyoriy: videolarni ochadigan dastur (.exe); bo'sh = Windows standarti
    notifications: bool = True             # eslatma bildirishnomalari (oyna ichida va tizim trayida)

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
            elif isinstance(default, list):
                ok = isinstance(val, list) and all(isinstance(v, str) and v.strip() for v in val)
                val = list(dict.fromkeys(val)) if ok else val
            elif isinstance(default, dict):
                ok = isinstance(val, dict) and all(
                    isinstance(k, str) and isinstance(v, bool) for k, v in val.items())
            else:
                ok = isinstance(val, str)
            if ok:
                setattr(s, key, val)
        s.volume = min(1.0, max(0.0, s.volume))
        if s.stt_engine not in ("google", "whisper"):
            s.stt_engine = "google"
        if s.whisper_model not in ("tiny", "base", "small"):
            s.whisper_model = "base"
        s.ai_effort = s.ai_effort if s.ai_effort in ("low", "medium", "high") else "low"
        s.ai_max_tokens = min(32000, max(256, int(s.ai_max_tokens)))
        s.ai_timeout_s = min(300, max(10, int(s.ai_timeout_s)))
        s.ai_context_messages = min(60, max(2, int(s.ai_context_messages)))
        s.voice_rate = min(50, max(-50, int(s.voice_rate)))
        if s.reduce_motion not in ("system", "on", "off"):
            s.reduce_motion = "system"
        if s.voice_gender not in ("male", "female"):
            s.voice_gender = "male"
        if s.tts_engine not in {v for _, v in TTS_ENGINES}:
            s.tts_engine = "auto"
        if s.stt_language not in {v for _, v in STT_LANGUAGES}:
            s.stt_language = "auto"
        s.city = s.city.strip()[:80] or "Tashkent"
        s.video_player = s.video_player.strip()
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
