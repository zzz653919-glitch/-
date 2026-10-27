"""Konsol mikrofon diagnostikasi:  python -m pyatnitsa.mic_check [--list] [--device NOM_YOKI_INDEKS] [--seconds 4] [--no-stt]

Qurilmalarni indeks bilan ko'rsatadi (loopback / Stereo Mix belgilanadi), tanlangan mikrofondan qisqa yozuv oladi, jonli darajani
va «nutq faol» holatini chiqaradi, so'ng tanigan matnni ko'rsatadi. Yozuv diskka saqlanmaydi; hech qanday buyruq bajarilmaydi.
"""
from __future__ import annotations

import argparse
import sys

from . import audio, voice_test
from .settings import Settings


def _print_devices(selected: str | None) -> list[dict]:
    try:
        rows = voice_test.device_table(selected)
    except audio.AudioError as e:
        print(f"XATO: {e.key}: {e.detail}")
        print("  PortAudio / sounddevice ishlamayapti yoki hech qanday audio qurilma yo'q.")
        return []
    if not rows:
        print("Kirish qurilmalari topilmadi (Windows → Sozlamalar → Tizim → Tovush → Kirish).")
        return rows
    print(f"{'IDX':>3}  {'TUR':<10} {'API':<20} {'KANAL':>5} {'Hz':>6}  NOM")
    for r in rows:
        flags = ("  <- Windows standarti" if r["default"] else "") + ("  <- ISHLATILADI" if r["used"] else "")
        kind = "LOOPBACK!" if r["kind"] == "loopback" else "mikrofon"
        print(f"{r['index']:>3}  {kind:<10} {r['hostapi'][:20]:<20} {r['channels']:>5} {r['rate']:>6}  {r['name']}{flags}")
        if r["kind"] == "loopback":
            print(f"{'':>3}  ^ bu mikrofon EMAS: kompyuter ichidagi tovushni yozadi, ovozingizni emas — ilova uni tanlamaydi.")
    used = next((r for r in rows if r["used"]), None)
    if used and used["warning"]:
        print(f"\nOGOHLANTIRISH: {used['warning']} — Windows standart/tanlangan qurilma mikrofon emas edi; '{used['name']}' ishlatiladi.")
    if used is None:
        print("\nXATO: jismoniy mikrofon topilmadi (faqat loopback qurilmalar bor).")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m pyatnitsa.mic_check", description=__doc__.splitlines()[0])
    ap.add_argument("--list", action="store_true", help="faqat qurilmalar ro'yxati")
    ap.add_argument("--device", help="qurilma nomi yoki indeksi (standart: Sozlamalardagi)")
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--no-stt", action="store_true", help="faqat daraja va nutq faolligi, tanishsiz")
    args = ap.parse_args(argv)

    settings = Settings.load()
    selected = settings.microphone
    if args.device:
        try:
            rows = voice_test.device_table(None)
        except audio.AudioError as e:
            print(f"XATO: {e.key}: {e.detail}")
            return 2
        by_idx = {str(r["index"]): r["name"] for r in rows}
        selected = by_idx.get(args.device, args.device)
        settings.microphone = selected
    rows = _print_devices(selected)
    if args.list or not rows:
        return 0 if rows else 2
    print(f"\nStandart til: {settings.stt_language}, dvigatel: {settings.stt_engine}. {args.seconds:.0f} soniya yozaman — gapiring (masalan «Google Chrome och»).")

    state = {"act": False}

    def level(v: float) -> None:
        bar = "#" * int(v * 30)
        sys.stdout.write(f"\r  daraja [{bar:<30}] {'NUTQ FAOL ' if state['act'] else 'jim       '}")
        sys.stdout.flush()

    def activity(flag: bool) -> None:
        state["act"] = flag

    rec_factory = None
    recognizer = False if args.no_stt else None
    rep = voice_test.run_mic_test(settings, args.seconds, level, None, rec_factory, recognizer,
                                  on_status=lambda s: print(f"\n[{s.upper()}]") if s != "recording" else print("[RECORDING]"),
                                  on_activity=activity)
    print()
    return _report(rep)


def _report(r: voice_test.MicReport) -> int:
    from .i18n import T, has
    if r.device:
        print(f"Qurilma: {r.device} (index {r.device_index}) · {r.rate} Hz · oqim ochilishi {r.open_ms:.0f} ms")
        if r.default_device and r.default_device != r.device:
            print(f"  Windows standarti: {r.default_device}")
    q = r.quality
    if q:
        print(f"Yozuv: {r.seconds:.1f} s · nutq faol: {r.activity * 100:.0f}% · peak {q.peak_db:.0f} dBFS · shovqin {q.noise_db:.0f} dBFS · hukm: {q.verdict}")
        if q.verdict == "silent":
            print("  -> mikrofon deyarli hech narsa yozmadi: u o'chirilgan, noto'g'ri qurilma, yoki Windows → Maxfiylik → Mikrofon ruxsati yopiq.")
        elif q.quiet:
            print("  -> ovoz juda past: mikrofonga yaqinroq gapiring yoki Windows'da kirish ovozini oshiring (Tovush → Kirish → Hajm).")
        if q.clipped:
            print("  -> signal kesilmoqda (clipping): kirish ovozini pasaytiring.")
    if r.error_key:
        msg = T(r.error_key, "uz", detail=r.error_detail[:200]) if has(r.error_key) else r.error_key
        print(f"NATIJA: {r.error_key} — {msg}")
        return 1
    if r.text is not None:
        print(f"Tanilgan matn: “{r.text}”   ({r.engine}, til: {r.language})")
        print(f"Tushunilgan amal: {r.interpretation}  (bajarilmaydi)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
