"""AI kalitini xavfsiz boshqarish: muhit o'zgaruvchisi (afzal) yoki foydalanuvchining shaxsiy `secrets.env` fayli.
Kalit hech qachon manba kodiga, sozlamalar JSON'iga yoki jurnalga yozilmaydi; jurnal filtri uni yashiradi."""
from __future__ import annotations

import logging
import os
import re
import stat
from pathlib import Path

from .settings import data_dir

ENV_NAMES = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
FILE_KEY = "ANTHROPIC_API_KEY"
_KEY_SHAPE = re.compile(r"sk-[A-Za-z0-9_\-]{8,}")


def secrets_path() -> Path:
    return data_dir() / "secrets.env"


def _read_file() -> dict[str, str]:
    try:
        text = secrets_path().read_text(encoding="utf-8")
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip("'\"")
    return out


def get_api_key() -> tuple[str | None, str]:
    """(kalit, manba). Manba: «env:NOM», «file» yoki «»."""
    for name in ENV_NAMES:
        v = os.environ.get(name, "").strip()
        if v:
            return v, f"env:{name}"
    v = _read_file().get(FILE_KEY, "").strip()
    return (v, "file") if v else (None, "")


def looks_valid(key: str) -> bool:
    return 20 <= len(key) <= 400 and not re.search(r"\s", key)


def save_api_key(key: str) -> None:
    """Faylga yozadi (faqat joriy foydalanuvchi o'qiy oladigan qilib). Kalitni qaytarmaydi va yozmaydi."""
    key = key.strip()
    if not looks_valid(key):
        raise ValueError("The key looks invalid (too short or contains spaces).")
    p = secrets_path()
    p.write_text(f"# Pyatnitsa secrets - do not share this file\n{FILE_KEY}={key}\n", encoding="utf-8")
    try:
        os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def clear_api_key() -> None:
    try:
        secrets_path().unlink()
    except FileNotFoundError:
        pass


def redact(text: str) -> str:
    """Matn ichidagi kalitni (haqiqiy yoki sk-... ko'rinishidagi) yashiradi."""
    key, _ = get_api_key()
    if key:
        text = text.replace(key, "***")
    return _KEY_SHAPE.sub("sk-***", text)


class RedactFilter(logging.Filter):
    """Barcha jurnal yozuvlaridan kalitni olib tashlaydi."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:  # noqa: BLE001
            pass
        return True
