"""Ruxsat etilgan papkalarda xavfsiz fayl qidirish, ro'yxatlash va ochish (faqat O'QISH — hech narsa o'chirilmaydi/o'zgartirilmaydi).

Xavfsizlik qoidalari:
  * Faqat foydalanuvchi AYNAN ruxsat bergan papka/disklar (`Settings.file_roots`). Bittasiga ruxsat — butun kompyuterga ruxsat emas.
  * Qidiruv matni hech qachon yo'l sifatida ishlatilmaydi: u faqat fayl NOMI bilan solishtiriladi. Papka faqat ruxsat etilgan ildizlar
    yoki ularning ichidagi taniqli papkalar (Downloads ...) orqali tanlanadi.
  * Windows ruxsatlariga bo'ysunadi (PermissionError -> o'tkazib yuboriladi va sanaladi); himoyalangan tizim joylari (Windows, Program Files,
    ProgramData, AppData, ilovaning o'z ma'lumotlari, Корзина) ildiz sifatida qabul qilinmaydi va qidiruvda o'tkazib yuboriladi.
  * Symlink / junction orqali ildizdan tashqariga chiqilmaydi; maxfiy fayllar (.env, kalitlar, parollar bazasi) ko'rsatilmaydi.
  * Ochish: faqat xavfsiz kengaytmalar (video, rasm, audio, hujjat). .exe/.bat/.ps1/.lnk/makroli hujjatlar va h.k. hech qachon ochilmaydi.
  * Fayl nomi, papka nomi va metama'lumot — ishonchsiz MA'LUMOT: buyruq sifatida talqin qilinmaydi, ko'rsatishdan oldin tozalanadi.
"""
from __future__ import annotations

import heapq
import logging
import os
import sys
import threading
import time
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from .commands import normalize

log = logging.getLogger(__name__)

KIND_EXT: dict[str, frozenset[str]] = {
    "video": frozenset("mp4 mkv avi mov webm wmv flv m4v mpg mpeg 3gp".split()),
    "image": frozenset("jpg jpeg png gif bmp webp tif tiff heic".split()),
    "audio": frozenset("mp3 wav flac aac m4a ogg wma opus".split()),
    "document": frozenset("pdf txt rtf doc docx odt xls xlsx ods ppt pptx odp csv md".split()),
}
OPENABLE_EXT = frozenset().union(*KIND_EXT.values())
KIND_OF_EXT = {e: k for k, exts in KIND_EXT.items() for e in exts}
# Bu kengaytmalar ISHGA TUSHADI yoki skript/makro bajaradi — ular hech qachon ochilmaydi (ro'yxatda ko'rinishi mumkin)
RISKY_EXT = frozenset("exe bat cmd com msi msp scr ps1 psm1 vbs vbe js jse wsf wsh hta lnk url reg jar dll sys cpl pif gadget application "
                      "appx msix docm xlsm pptm dotm xlam svg html htm xhtml chm iso py pyw sh".split())
KINDS = ("video", "image", "audio", "document", "other")

SKIP_DIR_NAMES = frozenset({"$recycle.bin", "system volume information", "node_modules", ".git", "__pycache__", "$winreagent", "windows.old"})
SENSITIVE_NAMES = frozenset({"secrets.env", ".env", ".netrc", ".npmrc", "id_rsa", "id_ed25519", "id_ecdsa", "known_hosts", "authorized_keys",
                             "login data", "web data", "cookies", "ntuser.dat", "sam", "security", "credentials"})
SENSITIVE_EXT = frozenset("pem key pfx p12 kdbx ppk env keychain".split())

MAX_RESULTS = 200
MAX_ENTRIES = 400_000
BUDGET_S = 20.0
_FILE_ATTRIBUTE_HIDDEN, _FILE_ATTRIBUTE_SYSTEM, _FILE_ATTRIBUTE_REPARSE = 0x2, 0x4, 0x400


# ----------------------------------------------------------------------------- yo'l yordamchilari
def _norm(p) -> str:
    try:
        return os.path.normcase(os.path.realpath(str(p)))
    except (OSError, ValueError):
        return os.path.normcase(os.path.abspath(str(p)))


def _within(child: str, parent: str) -> bool:
    """child == parent yoki uning ichida (normallashtirilgan yo'llar)."""
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:                        # turli disklar
        return False


def protected_dirs() -> list[Path]:
    """Ildiz sifatida qabul qilinmaydigan va qidiruvda o'tkazib yuboriladigan joylar."""
    out: list[Path] = []
    if sys.platform == "win32":
        for var in ("SystemRoot", "windir", "ProgramFiles", "ProgramFiles(x86)", "ProgramW6432", "ProgramData", "APPDATA", "LOCALAPPDATA"):
            v = os.environ.get(var)
            if v:
                out.append(Path(v))
    else:
        out += [Path(p) for p in ("/proc", "/sys", "/dev", "/etc", "/boot", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/var", "/run", "/root")]
    try:
        from .settings import data_dir
        out.append(data_dir())                # ilovaning o'z ma'lumotlari (kalit fayli shu yerda)
    except Exception:  # noqa: BLE001
        pass
    return out


def root_problem(path: Path | str) -> str:
    """"" — ildiz bo'la oladi; aks holda sabab kaliti: missing | not_dir | protected | too_broad."""
    p = Path(path)
    try:
        if not p.exists():
            return "missing"
        if not p.is_dir():
            return "not_dir"
    except OSError:
        return "missing"
    n = _norm(p)
    if sys.platform != "win32" and n == os.path.normcase(os.sep):
        return "too_broad"                    # Linux/macOS'da "/" — butun tizim (Windows'da disk ildizi ataylab ruxsat etiladi)
    for prot in protected_dirs():
        if _within(n, _norm(prot)):
            return "protected"
    return ""


def safe_display(name: str, limit: int = 120) -> str:
    """Nomni ko'rsatishga tayyorlaydi: boshqaruv va bidi belgilar (kengaytmani yashiruvchi RLO va h.k.) olib tashlanadi."""
    s = "".join(ch for ch in str(name) if unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co"))
    s = s.strip() or "?"
    return s if len(s) <= limit else s[: limit - 1] + "…"


def is_sensitive(name: str) -> bool:
    n = name.lower()
    if n in SENSITIVE_NAMES:
        return True
    return (n.rsplit(".", 1)[-1] if "." in n else "") in SENSITIVE_EXT


def fmt_size(n: int | None) -> str:
    if n is None:
        return "—"
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            return f"{x:.0f} {unit}" if unit == "B" else f"{x:.1f} {unit}"
        x /= 1024
    return f"{n} B"


def fmt_date(ts: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "—"


# ----------------------------------------------------------------------------- ma'lumot turlari
@dataclass(frozen=True)
class FileEntry:
    path: Path
    name: str
    kind: str                    # video | image | audio | document | other | folder
    size: int | None
    mtime: float | None
    root: Path | None = None

    @property
    def ext(self) -> str:
        return self.path.suffix.lower().lstrip(".")

    @property
    def parent(self) -> Path:
        return self.path.parent

    @property
    def display(self) -> str:
        return safe_display(self.name)

    @property
    def openable(self) -> bool:
        return self.kind == "folder" or self.ext in OPENABLE_EXT


@dataclass
class Query:
    text: str = ""                                # nom bo'lagi (YO'L EMAS)
    kinds: frozenset[str] = frozenset()           # bo'sh = istalgan fayl
    exts: frozenset[str] = frozenset()
    lang: str = ""                                # uz | ru | en — fayl/papka NOMIga qarab taxmin
    latest: bool = False
    limit: int = 50


@dataclass
class SearchOutcome:
    entries: list[FileEntry] = field(default_factory=list)
    scanned: int = 0
    denied: int = 0                               # Windows ruxsat bermagan papkalar soni
    truncated: bool = False                       # vaqt/element/natija chegarasi tufayli to'liq emas
    fuzzy: bool = False                           # aniq mos kelish yo'q — o'xshash nomlar (avtomatik ochilmaydi)
    cancelled: bool = False
    elapsed: float = 0.0
    roots: list[Path] = field(default_factory=list)


# ----------------------------------------------------------------------------- nom moslashtirish
_SUFFIXES = ("larning", "larini", "larni", "larga", "lardan", "lari", "ning", "dagi", "idagi", "ini", "ni", "ga", "da", "dan", "lar", "si", "ing", "im", "ov", "om")


def _variants(tok: str) -> list[str]:
    out = [tok]
    for suf in _SUFFIXES:
        if tok.endswith(suf) and len(tok) - len(suf) >= 3:
            out.append(tok[: -len(suf)])
    return out


def _tokens(text: str) -> list[str]:
    return [t for t in normalize(text).split() if t]


def _score(qtokens: list[str], qjoined: str, name_n: str, stem_n: str) -> float:
    """0 = mos emas. Aniq nom 4, nom bo'lagi bilan boshlanadi 3, barcha so'zlar bor 2."""
    if not qtokens:
        return 1.0
    if qjoined == stem_n or qjoined == name_n:
        return 4.0
    if not all(any(v in name_n for v in _variants(t)) for t in qtokens):
        return 0.0
    return 3.0 if stem_n.startswith(qtokens[0]) else 2.0


def _fuzzy(qjoined: str, stem_n: str) -> float:
    if not qjoined or not stem_n:
        return 0.0
    return SequenceMatcher(None, qjoined, stem_n).ratio()


_LANG_ALIASES = {"ru": {"rus", "russian", "russkiy", "russkie", "ru"}, "uz": {"uzb", "uzbek", "ozbek", "uzbekcha", "ozbekcha", "uz"}, "en": {"eng", "english", "inglizcha", "en"}}
_UZ_ONLY_CYR = set("ўқғҳЎҚҒҲ")


def lang_hint(lang: str, *texts: str) -> bool:
    """Fayl/papka NOMIda til belgisi bormi (ruscha harflar, «rus», «uzbek», «english» ...). Media metama'lumotini O'QIMAYDI."""
    raw = " ".join(texts)
    if lang == "ru":
        cyr = [ch for ch in raw if "Ѐ" <= ch <= "ӿ"]
        if cyr and not (set(cyr) & _UZ_ONLY_CYR):
            return True
    if lang == "uz" and set(raw) & _UZ_ONLY_CYR:
        return True
    toks = set(_tokens(raw))
    return bool(toks & _LANG_ALIASES.get(lang, set()))


# ----------------------------------------------------------------------------- asosiy sinf
class FileAccess:
    """Ruxsat etilgan ildizlar + xavfsiz qidirish/ochish. `settings.file_roots` da saqlanadi (sessiyalar orasida eslab qolinadi)."""

    def __init__(self, settings, save: bool = True):
        self.settings, self._save = settings, save
        self._lock = threading.Lock()
        self.recent: dict[str, FileEntry] = {}      # oxirgi ro'yxatdagi fayllar: ochishga faqat shulardan ruxsat (norm yo'l -> yozuv)

    # ---- ruxsatlar
    def roots(self) -> list[Path]:
        with self._lock:
            return [Path(r) for r in self.settings.file_roots if root_problem(r) in ("",)]

    def stored(self) -> list[str]:
        with self._lock:
            return list(self.settings.file_roots)

    def add_root(self, path: Path | str) -> tuple[bool, str]:
        """-> (ok, sabab_kaliti). Foydalanuvchining aniq harakati (papka tanlash oynasi) bilan chaqiriladi."""
        p = Path(path)
        why = root_problem(p)
        if why:
            return False, why
        real = str(Path(os.path.realpath(p)))
        with self._lock:
            if any(_norm(r) == _norm(real) for r in self.settings.file_roots):
                return False, "exists"
            self.settings.file_roots.append(real)
        self._persist()
        log.info("Fayl ruxsati berildi: %s", real)
        return True, ""

    def remove_root(self, path: Path | str) -> bool:
        n = _norm(path)
        with self._lock:
            keep = [r for r in self.settings.file_roots if _norm(r) != n]
            changed = len(keep) != len(self.settings.file_roots)
            self.settings.file_roots[:] = keep
            if changed:
                self.recent = {k: v for k, v in self.recent.items() if any(_within(k, _norm(r)) for r in keep)}   # bekor qilingan joydagi eski natijalar ochilmaydi
        if changed:
            self._persist()
            log.info("Fayl ruxsati bekor qilindi: %s", path)
        return changed

    def _persist(self) -> None:
        if self._save:
            self.settings.save()

    def is_allowed(self, path: Path | str) -> bool:
        """Yo'l (symlink'lar hal qilingach) ruxsat etilgan ildiz ichidami va himoyalangan joyda emasmi."""
        n = _norm(path)
        if any(_within(n, _norm(p)) for p in protected_dirs()):
            return False
        return any(_within(n, _norm(r)) for r in self.roots())

    def scope(self, folder: Path | None) -> list[Path]:
        """Taniqli papka (Downloads ...) uchun qidiriladigan ildizlar: papka ruxsat etilgan ildiz ichida yoki ildizning o'zi shu papka ichida.
        Bo'sh ro'yxat = bu papkaga ruxsat berilmagan."""
        if folder is None:
            return []
        kn, out = _norm(folder), []
        for r in self.roots():
            rn = _norm(r)
            if _within(kn, rn):
                out.append(Path(folder))
            elif _within(rn, kn):
                out.append(r)
        seen, uniq = set(), []
        for p in out:
            if _norm(p) not in seen:
                seen.add(_norm(p)); uniq.append(p)
        return uniq

    # ---- qidirish
    def search(self, q: Query, roots: list[Path] | None = None, cancel: threading.Event | None = None,
               budget_s: float = BUDGET_S, max_entries: int = MAX_ENTRIES) -> SearchOutcome:
        out = SearchOutcome()
        t0 = time.monotonic()
        allowed = self.roots()
        if roots is None:
            roots = allowed
        else:                                        # so'ralgan ildizlar faqat ruxsat etilganlarning ichida bo'lishi mumkin
            roots = [r for r in roots if any(_within(_norm(r), _norm(a)) for a in allowed)]
        out.roots = list(roots)
        prot = [_norm(p) for p in protected_dirs()]
        qtokens, qjoined = _tokens(q.text), " ".join(_tokens(q.text))
        want_kinds = set(q.kinds) - {"folder"}
        hits: list[tuple[float, float, FileEntry]] = []
        fuzzy_pool: list[tuple[str, FileEntry]] = []
        heap: list[tuple[float, int, FileEntry]] = []
        counter = 0
        seen_dirs: set[str] = set()
        stack = [(r, r) for r in reversed(roots)]
        win = sys.platform == "win32"
        cap = max(q.limit, 1) if q.latest else MAX_RESULTS * 5
        while stack:
            if cancel is not None and cancel.is_set():
                out.cancelled = True
                break
            if out.scanned >= max_entries or time.monotonic() - t0 > budget_s:
                out.truncated = True
                break
            root, d = stack.pop()
            dn = _norm(d)
            if dn in seen_dirs:
                continue
            seen_dirs.add(dn)
            try:
                it = os.scandir(d)
            except (PermissionError, OSError):
                out.denied += 1
                continue
            with it:
                while True:
                    try:
                        entry = next(it)
                    except StopIteration:
                        break
                    except (PermissionError, OSError):
                        out.denied += 1
                        break
                    out.scanned += 1
                    if out.scanned > max_entries or (out.scanned % 256 == 0 and (time.monotonic() - t0 > budget_s or (cancel is not None and cancel.is_set()))):
                        out.cancelled = bool(cancel is not None and cancel.is_set())
                        out.truncated = out.truncated or not out.cancelled
                        stack.clear()
                        break
                    name = entry.name
                    low = name.lower()
                    try:
                        if entry.is_symlink():
                            continue                               # symlink orqali ildizdan chiqib ketmaslik uchun kuzatilmaydi
                        is_dir = entry.is_dir(follow_symlinks=False)
                        if win:
                            attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
                            if attrs & _FILE_ATTRIBUTE_REPARSE:
                                continue                           # junction / reparse point
                            if is_dir and attrs & (_FILE_ATTRIBUTE_HIDDEN | _FILE_ATTRIBUTE_SYSTEM):
                                continue
                    except OSError:
                        out.denied += 1
                        continue
                    if is_dir:
                        if low in SKIP_DIR_NAMES or low.startswith("$"):
                            continue
                        child = _norm(entry.path)
                        if any(_within(child, p) for p in prot):
                            continue
                        stack.append((root, Path(entry.path)))
                        continue
                    if is_sensitive(name):
                        continue
                    ext = low.rsplit(".", 1)[-1] if "." in low else ""
                    kind = KIND_OF_EXT.get(ext, "other")
                    if want_kinds and kind not in want_kinds:
                        continue
                    if q.exts and ext not in q.exts:
                        continue
                    if q.lang and not lang_hint(q.lang, name, Path(entry.path).parent.name):
                        continue
                    stem_n = " ".join(_tokens(name.rsplit(".", 1)[0] if "." in name else name))
                    score = _score(qtokens, qjoined, " ".join(_tokens(name)), stem_n)
                    try:
                        st = entry.stat(follow_symlinks=False)
                        size, mtime = st.st_size, st.st_mtime
                    except OSError:
                        size = mtime = None
                    fe = FileEntry(Path(entry.path), name, kind, size, mtime, root)
                    if score <= 0:
                        if qtokens and len(fuzzy_pool) < 20000:
                            fuzzy_pool.append((stem_n, fe))
                        continue
                    if q.latest:
                        counter += 1
                        item = (mtime or 0.0, counter, fe)
                        if len(heap) < cap:
                            heapq.heappush(heap, item)
                        else:
                            heapq.heappushpop(heap, item)
                    else:
                        hits.append((score, mtime or 0.0, fe))
                        if len(hits) > cap:
                            out.truncated = True
                            hits.sort(key=lambda h: (-h[0], -h[1]))
                            del hits[MAX_RESULTS:]
        if q.latest:
            entries = [fe for _m, _c, fe in sorted(heap, key=lambda h: -h[0])]
        else:
            hits.sort(key=lambda h: (-h[0], -h[1]))
            entries = [fe for _s, _m, fe in hits]
        if not entries and qtokens and fuzzy_pool and not out.cancelled:
            ranked = sorted(((_fuzzy(qjoined, s), fe) for s, fe in fuzzy_pool), key=lambda r: -r[0])
            entries = [fe for r, fe in ranked if r >= 0.72][:10]
            out.fuzzy = bool(entries)
        out.entries = entries[: max(q.limit, 1)]
        if len(entries) > len(out.entries):
            out.truncated = True
        out.elapsed = time.monotonic() - t0
        self._remember(out.entries)
        return out

    def list_dir(self, folder: Path, limit: int = 40) -> tuple[list[FileEntry], int, int]:
        """Papkaning bevosita ichi (papkalar avval). -> (yozuvlar, jami soni, ruxsat berilmagan). Faqat ruxsat etilgan joylarda."""
        if not self.is_allowed(folder):
            return [], 0, 0
        items: list[FileEntry] = []
        denied = 0
        try:
            with os.scandir(folder) as it:
                for e in it:
                    low = e.name.lower()
                    try:
                        if e.is_symlink() or is_sensitive(e.name):
                            continue
                        is_dir = e.is_dir(follow_symlinks=False)
                        if is_dir and (low in SKIP_DIR_NAMES or low.startswith("$") or any(_within(_norm(e.path), _norm(p)) for p in protected_dirs())):
                            continue
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        denied += 1
                        continue
                    ext = low.rsplit(".", 1)[-1] if "." in low else ""
                    items.append(FileEntry(Path(e.path), e.name, "folder" if is_dir else KIND_OF_EXT.get(ext, "other"), None if is_dir else st.st_size, st.st_mtime))
        except (PermissionError, OSError):
            return [], 0, 1
        items.sort(key=lambda x: (x.kind != "folder", x.name.lower()))
        shown = items[:limit]
        self._remember(shown)
        return shown, len(items), denied

    def _remember(self, entries: list[FileEntry]) -> None:
        with self._lock:
            self.recent = {_norm(e.path): e for e in entries}

    # ---- ochishdan oldingi tekshiruv
    def check_openable(self, path: Path | str) -> tuple[Path | None, str]:
        """-> (haqiqiy yo'l, "") yoki (None, sabab_kaliti): not_listed | not_allowed | missing | type_blocked | no_access."""
        if not self.is_allowed(path):
            return None, "not_allowed"                # ruxsat bekor qilingan, himoyalangan yoki umuman ruxsatsiz joy
        n = _norm(path)
        with self._lock:
            known = n in self.recent
        if not known:
            return None, "not_listed"                 # faqat ko'rsatilgan natijalardan ochiladi (NLU yo'l yasay olmaydi)
        p = Path(path)
        try:
            if p.is_symlink():
                return None, "not_allowed"
            if p.is_dir():
                return Path(os.path.realpath(p)), ""
            if not p.exists():
                return None, "missing"
            if not p.is_file():
                return None, "not_allowed"
        except OSError:
            return None, "no_access"
        ext = p.suffix.lower().lstrip(".")
        if is_sensitive(p.name):
            return None, "not_allowed"
        if ext not in OPENABLE_EXT:
            return None, "type_blocked"
        if not os.access(p, os.R_OK):
            return None, "no_access"
        return Path(os.path.realpath(p)), ""
