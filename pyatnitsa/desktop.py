"""Ish stoli bilan ishlash: clipboard o'qish, skrinshot, parol/kalitga o'xshash matnni aniqlash.

Faqat foydalanuvchi ovozli buyruq bilan so'raganda va tasdiqlagandan keyin chaqiriladi (boshqaruvchi chaqiradi). Hech narsa o'z-o'zidan o'qilmaydi.
Clipboard matni jurnalga YOZILMAYDI va hech qayerga yuborilmaydi (AI'ga faqat alohida tasdiqdan keyin, boshqaruvchi orqali).
Qt'ga bog'liq funksiyalar asosiy (GUI) oqimda chaqiriladi.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

MAX_AI_CHARS = 6000
MAX_SHOW_CHARS = 1500

_SECRET_PATTERNS = [re.compile(p, re.I) for p in (
    r"\bsk-[A-Za-z0-9_\-]{16,}", r"\bAKIA[0-9A-Z]{16}\b", r"\bgh[pousr]_[A-Za-z0-9]{20,}", r"\bxox[abprs]-[A-Za-z0-9-]{10,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}",
    r"\b(pass(word|wd)?|parol|пароль|secret|api[_ -]?key|token|apikey|access[_ -]?key|credential)s?\b\s*[:=]\s*\S{4,}",
)]


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def looks_secret(text: str) -> bool:
    """Parol, API kaliti, token, maxfiy kalit yoki bank kartasi raqamiga o'xshaydimi (ehtiyotkor taxmin)."""
    t = text or ""
    if any(p.search(t) for p in _SECRET_PATTERNS):
        return True
    for m in re.finditer(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)", t):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return True
    s = t.strip()
    if 20 <= len(s) <= 200 and " " not in s and "\n" not in s and re.search(r"[a-z]", s) and re.search(r"[A-Z]", s) and re.search(r"\d", s):
        return True                                      # bitta uzun aralash-belgili «so'z» — odatda token
    return False


def read_clipboard() -> str | None:
    """Clipboard'dagi MATN (yo'q bo'lsa None). Rasm/fayllar o'qilmaydi."""
    from PySide6.QtGui import QGuiApplication
    cb = QGuiApplication.clipboard()
    if cb is None:
        return None
    md = cb.mimeData()
    if md is None or not md.hasText():
        return None
    return cb.text()


def screenshots_dir(pictures: Path | None = None) -> Path:
    base = pictures or (Path.home() / "Pictures")
    return base / "Pyatnitsa"


def take_screenshot(dest_dir: Path, now: datetime) -> Path:
    """Asosiy ekranni PNG qilib saqlaydi. Fayl haqiqatan yozilmasa OSError. Mavjud faylning ustiga yozilmaydi."""
    from PySide6.QtGui import QGuiApplication
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        raise OSError("ekran topilmadi")
    pix = screen.grabWindow(0)
    if pix.isNull():
        raise OSError("ekran tasviri olinmadi")
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"screenshot-{now.strftime('%Y%m%d-%H%M%S')}.png"
    n = 1
    while path.exists():
        n += 1
        path = dest_dir / f"screenshot-{now.strftime('%Y%m%d-%H%M%S')}-{n}.png"
    if not pix.save(str(path), "PNG") or not path.is_file() or path.stat().st_size == 0:
        raise OSError("fayl yozilmadi")
    return path
