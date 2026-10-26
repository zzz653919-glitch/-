"""Internetdan o'zgaruvchan ma'lumot olish: faqat JSON sonlari o'qiladi, matn ko'rsatma sifatida talqin qilinmaydi."""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request

UA = {"User-Agent": "Pyatnitsa/1.0 (desktop assistant)", "Accept": "application/json"}
MAX_BYTES = 1_000_000


class NetworkError(Exception):
    """Internet yo'q yoki manba javob bermadi."""


class DataError(Exception):
    """Manba kutilgan ma'lumotni qaytarmadi."""


def get_json(url: str, timeout: float = 8.0):
    if not url.startswith("https://"):
        raise ValueError("Faqat https")
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read(MAX_BYTES).decode("utf-8"))
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as e:
        raise NetworkError(str(e)) from e
    except ValueError as e:
        raise DataError("Manba noto'g'ri formatda javob berdi") from e


CBU_URL = "https://cbu.uz/oz/arkhiv-kursov-valyut/json/USD/"


def usd_rate(fetch=get_json) -> tuple[float, str]:
    """(1 USD = X so'm, sana) — O'zbekiston Markaziy banki."""
    data = fetch(CBU_URL)
    try:
        item = data[0]
        rate = float(str(item["Rate"]).replace(",", "."))
        date = str(item["Date"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise DataError("Kurs ma'lumoti topilmadi") from e
    if rate <= 0:
        raise DataError("Noto'g'ri kurs")
    return rate, date


WEATHER_CODES = {
    0: "ochiq osmon", 1: "asosan ochiq", 2: "qisman bulutli", 3: "bulutli", 45: "tuman", 48: "qirovli tuman",
    51: "mayda yomg'ir", 53: "mayda yomg'ir", 55: "mayda yomg'ir", 56: "muzlovchi yomg'ir", 57: "muzlovchi yomg'ir",
    61: "yengil yomg'ir", 63: "yomg'ir", 65: "kuchli yomg'ir", 66: "muzlovchi yomg'ir", 67: "muzlovchi yomg'ir",
    71: "yengil qor", 73: "qor", 75: "kuchli qor", 77: "qor donalari", 80: "yomg'ir jalasi", 81: "yomg'ir jalasi",
    82: "kuchli jala", 85: "qor jalasi", 86: "kuchli qor jalasi", 95: "momaqaldiroq", 96: "do'l bilan momaqaldiroq",
    99: "kuchli do'l bilan momaqaldiroq",
}


def weather(city: str, fetch=get_json) -> dict:
    q = urllib.parse.urlencode({"name": city, "count": 1, "language": "en"})
    geo = fetch(f"https://geocoding-api.open-meteo.com/v1/search?{q}")
    try:
        place = geo["results"][0]
        lat, lon, name = float(place["latitude"]), float(place["longitude"]), str(place["name"])
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise DataError(f"«{city}» shahri topilmadi") from e
    q = urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto",
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m"})
    cur = fetch(f"https://api.open-meteo.com/v1/forecast?{q}").get("current")
    try:
        return {"city": name, "temp": float(cur["temperature_2m"]), "feels": float(cur["apparent_temperature"]),
                "humidity": float(cur["relative_humidity_2m"]), "wind": float(cur["wind_speed_10m"]),
                "code": int(cur["weather_code"]), "time": str(cur["time"])}
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise DataError("Ob-havo ma'lumoti topilmadi") from e
