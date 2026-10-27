"""Fayl ruxsati, qidirish, tushunish va ijro: ruxsat etilgan papkalar, ruxsatsiz joylarga kirib bo'lmasligi, bekor qilingan ruxsat,
noaniq moslik, ochish (soxta Windows qatlami bilan — HAQIQIY ilova ochilishi sinalmagan)."""
import os
import sys
import threading
import time
from pathlib import Path

import pytest

from pyatnitsa import commands, fileintent, files as fs
from pyatnitsa.executor import Executor
from pyatnitsa.settings import Settings
from test_executor import FakePlatform


# ------------------------------------------------------------------ yordamchilar
def build_tree(base: Path) -> Path:
    """Downloads/ ... namunaviy tuzilma. Vaqtlar aniq belgilanadi (eng yangi testi uchun)."""
    d = base / "Downloads"
    (d / "nested" / "deep").mkdir(parents=True)
    now = time.time()
    spec = {
        "example.mp4": 2048, "holiday_2025.mp4": 4096, "holiday_old.mkv": 1024, "Лиза видео.mp4": 512, "русский фильм.avi": 256,
        "notes.pdf": 100, "setup.exe": 100, "song.mp3": 300, "photo.jpg": 400, "report.docm": 10,
        "nested/example_copy.mp4": 700, "nested/deep/newest_clip.webm": 800, "secrets.env": 5, "key.pem": 5,
    }
    for i, (rel, size) in enumerate(spec.items()):
        p = d / rel
        p.write_bytes(b"x" * size)
        os.utime(p, (now - 1000 + i * 10, now - 1000 + i * 10))
    os.utime(d / "nested" / "deep" / "newest_clip.webm", (now, now))
    return d


@pytest.fixture
def tree(tmp_path):
    return build_tree(tmp_path)


def access(tmp_path, *roots, save=False):
    st = Settings()
    fa = fs.FileAccess(st, save=save)
    for r in roots:
        ok, why = fa.add_root(r)
        assert ok, why
    return st, fa


def names(out):
    return [e.name for e in out.entries]


# ------------------------------------------------------------------ ruxsat: qo'shish, eslab qolish, bekor qilish
def test_roots_are_remembered_between_sessions(tmp_path, tree, monkeypatch):
    path = tmp_path / "settings.json"
    st = Settings()
    fa = fs.FileAccess(st, save=False)
    assert fa.add_root(tree) == (True, "")
    st.save(path)
    again = Settings.load(path)
    assert [fs._norm(r) for r in again.file_roots] == [fs._norm(tree)]
    assert fs.FileAccess(again, save=False).roots() == [Path(os.path.realpath(tree))]


def test_add_root_persists_through_the_real_save_path(tmp_path, tree, monkeypatch):
    monkeypatch.setattr(Settings, "path", staticmethod(lambda: tmp_path / "persist.json"))
    st = Settings()
    fs.FileAccess(st).add_root(tree)
    assert Settings.load().file_roots == [str(Path(os.path.realpath(tree)))]
    fs.FileAccess(Settings.load()).remove_root(tree)
    assert Settings.load().file_roots == []


def test_invalid_roots_in_settings_file_are_ignored(tmp_path):
    p = tmp_path / "s.json"
    p.write_text('{"file_roots": ["ok", 5, ""], "video_player": 7}', encoding="utf-8")
    s = Settings.load(p)
    assert s.file_roots == [] and s.video_player == ""


@pytest.mark.parametrize("make,why", [
    (lambda t: t / "nope", "missing"), (lambda t: t / "Downloads" / "example.mp4", "not_dir"),
    (lambda t: Path("/etc"), "protected"), (lambda t: Path("/usr/lib"), "protected"),
    (lambda t: Path(os.sep), "too_broad"),
])
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX tizim yo'llari")
def test_dangerous_or_invalid_roots_are_refused(tmp_path, tree, make, why):
    st, fa = access(tmp_path)
    assert fa.add_root(make(tmp_path)) == (False, why) and st.file_roots == []


def test_the_apps_own_data_folder_cannot_be_authorized():
    from pyatnitsa.settings import data_dir
    st, fa = access(None)
    assert fa.add_root(data_dir()) == (False, "protected")


def test_duplicate_root_is_reported(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    assert fa.add_root(tree) == (False, "exists") and len(st.file_roots) == 1


def test_access_to_one_folder_is_not_access_to_the_whole_computer(tmp_path, tree):
    other = tmp_path / "Private"; other.mkdir(); (other / "secret_video.mp4").write_bytes(b"x")
    st, fa = access(tmp_path, tree)
    assert not fa.is_allowed(other / "secret_video.mp4") and not fa.is_allowed(tmp_path)
    assert "secret_video.mp4" not in names(fa.search(fs.Query("secret")))
    assert fa.search(fs.Query("secret"), roots=[other]).entries == []          # ruxsatsiz ildizni so'rash ham natija bermaydi


def test_parent_traversal_does_not_escape_the_root(tmp_path, tree):
    (tmp_path / "outside.mp4").write_bytes(b"x")
    st, fa = access(tmp_path, tree)
    assert not fa.is_allowed(tree / ".." / "outside.mp4")
    assert fa.search(fs.Query("../outside")).entries == [] and fa.search(fs.Query("..\\..\\windows")).entries == []   # matn yo'l emas, faqat nom bo'lagi


@pytest.mark.skipif(not hasattr(os, "symlink") or sys.platform == "win32", reason="symlink")
def test_symlinks_cannot_escape_the_authorized_folder(tmp_path, tree):
    out = tmp_path / "Outside"; out.mkdir(); (out / "leak.mp4").write_bytes(b"x")
    os.symlink(out, tree / "link_dir"); os.symlink(out / "leak.mp4", tree / "link_file.mp4")
    st, fa = access(tmp_path, tree)
    assert "leak.mp4" not in names(fa.search(fs.Query("leak"))) and "link_file.mp4" not in names(fa.search(fs.Query("link")))
    assert not fa.is_allowed(tree / "link_dir" / "leak.mp4")


def test_revoking_access_takes_effect_immediately(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    hit = fa.search(fs.Query("example")).entries[0]
    assert fa.check_openable(hit.path)[1] == ""
    assert fa.remove_root(tree) is True and st.file_roots == []
    assert fa.recent == {}                                                    # bekor qilingan joydagi eski natijalar darhol o'chadi
    assert fa.search(fs.Query("example")).entries == [] and fa.roots() == []
    assert fa.check_openable(hit.path) == (None, "not_allowed")               # ochish rad etiladi
    assert fa.remove_root(tree) is False


def test_partial_revoke_keeps_the_other_folder(tmp_path, tree):
    other = tmp_path / "Videos"; other.mkdir(); (other / "clip.mp4").write_bytes(b"x")
    st, fa = access(tmp_path, tree, other)
    fa.remove_root(tree)
    assert names(fa.search(fs.Query())) == ["clip.mp4"]


# ------------------------------------------------------------------ qidirish
def test_search_by_partial_name_is_recursive_and_case_insensitive(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    assert set(names(fa.search(fs.Query("EXAMPLE")))) == {"example.mp4", "example_copy.mp4"}
    assert names(fa.search(fs.Query("example"))).index("example.mp4") < names(fa.search(fs.Query("example"))).index("example_copy.mp4")   # to'liq nom oldinda


def test_search_by_kind_and_extension(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    assert {e.kind for e in fa.search(fs.Query(kinds=frozenset({"video"}))).entries} == {"video"}
    assert names(fa.search(fs.Query(exts=frozenset({"pdf"})))) == ["notes.pdf"]
    assert names(fa.search(fs.Query(kinds=frozenset({"audio"})))) == ["song.mp3"]
    assert names(fa.search(fs.Query(kinds=frozenset({"image"})))) == ["photo.jpg"]
    assert names(fa.search(fs.Query(kinds=frozenset({"document"})))) == ["notes.pdf"]


def test_cyrillic_and_latin_names_match_each_other(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    assert "Лиза видео.mp4" in names(fa.search(fs.Query("liza")))
    assert "русский фильм.avi" in names(fa.search(fs.Query("русский")))
    assert "Лиза видео.mp4" in names(fa.search(fs.Query("lizani")))           # uzbekcha qo'shimcha


def test_latest_returns_the_newest_file_by_modification_time(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    out = fa.search(fs.Query(kinds=frozenset({"video"}), latest=True, limit=1))
    assert names(out) == ["newest_clip.webm"]
    assert names(fa.search(fs.Query(kinds=frozenset({"video"}), latest=True, limit=3)))[0] == "newest_clip.webm"


def test_language_filter_uses_names_only(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    ru = set(names(fa.search(fs.Query(kinds=frozenset({"video"}), lang="ru"))))
    assert ru == {"Лиза видео.mp4", "русский фильм.avi"}
    assert fs.lang_hint("ru", "Movie", "Russian") and not fs.lang_hint("ru", "Movie.mp4", "Videos")


def test_fuzzy_results_are_flagged_and_exact_misses_find_nothing_else(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    out = fa.search(fs.Query("exampel"))
    assert out.fuzzy and "example.mp4" in names(out)
    assert not fa.search(fs.Query("example")).fuzzy
    nothing = fa.search(fs.Query("zzzzqqqq"))
    assert nothing.entries == [] and not nothing.fuzzy


def test_sensitive_files_are_never_listed(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    listed = names(fa.search(fs.Query()))
    assert "secrets.env" not in listed and "key.pem" not in listed
    items, _t, _d = fa.list_dir(tree)
    assert "secrets.env" not in [e.name for e in items]


def test_protected_subfolders_are_skipped(tmp_path, tree, monkeypatch):
    prot = tree / "nested"
    monkeypatch.setattr(fs, "protected_dirs", lambda: [prot])
    st, fa = access(tmp_path, tree)
    assert "example_copy.mp4" not in names(fa.search(fs.Query("example"))) and not fa.is_allowed(prot / "deep" / "newest_clip.webm")


def test_windows_permission_errors_are_counted_and_skipped(tmp_path, tree, monkeypatch):
    real = os.scandir

    def fake(path):
        if Path(path).name == "nested":
            raise PermissionError("denied")
        return real(path)
    monkeypatch.setattr(fs.os, "scandir", fake)
    st, fa = access(tmp_path, tree)
    out = fa.search(fs.Query("example"))
    assert names(out) == ["example.mp4"] and out.denied == 1


def test_search_can_be_cancelled_and_has_limits(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    ev = threading.Event(); ev.set()
    assert fa.search(fs.Query(), cancel=ev).cancelled
    small = fa.search(fs.Query(), max_entries=3)
    assert small.truncated and small.scanned <= 4


def test_results_have_full_paths_sizes_and_dates(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    e = fa.search(fs.Query("holiday_2025")).entries[0]
    assert e.path.is_absolute() and e.size == 4096 and e.mtime and fs.fmt_size(e.size) == "4.0 KB" and len(fs.fmt_date(e.mtime)) == 16


def test_list_dir_lists_folders_first_inside_authorized_folders_only(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    items, total, _d = fa.list_dir(tree)
    assert items[0].kind == "folder" and items[0].name == "nested" and total == len(items)
    assert fa.list_dir(tmp_path) == ([], 0, 0)                                 # ruxsatsiz papka


# ------------------------------------------------------------------ ochishdan oldingi tekshiruv
def listed(fa, query):
    return fa.search(fs.Query(query)).entries[0]


def test_only_listed_openable_files_pass_the_check(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    assert fa.check_openable(tree / "example.mp4") == (None, "not_listed")      # ro'yxatda yo'q — hatto ruxsat etilgan joyda ham
    e = listed(fa, "example")
    assert fa.check_openable(e.path)[1] == ""


@pytest.mark.parametrize("q,why", [("setup", "type_blocked"), ("report", "type_blocked")])
def test_programs_scripts_and_macro_documents_are_never_openable(tmp_path, tree, q, why):
    st, fa = access(tmp_path, tree)
    e = listed(fa, q)
    assert fa.check_openable(e.path) == (None, why)


def test_deleted_file_is_reported_missing(tmp_path, tree):
    st, fa = access(tmp_path, tree)
    e = listed(fa, "photo")
    e.path.unlink()
    assert fa.check_openable(e.path) == (None, "missing")


def test_display_names_are_sanitized():
    evil = "invoice‮fdp.exe\x07\x1b[31m"
    s = fs.safe_display(evil)
    assert "‮" not in s and "\x07" not in s and "\x1b" not in s
    assert len(fs.safe_display("a" * 500)) <= 120


# ------------------------------------------------------------------ tushunish (uz / ru / en)
def p(text):
    r = commands.parse(text)
    c = r.commands[0] if r.commands else None
    return r, c


@pytest.mark.parametrize("text,action,sub", [
    ("Downloads papkasidan videoni top.", "find_files", {"kinds": ["video"], "folder": "downloads", "then": "show"}),
    ("Find the video named example.mp4", "find_files", {"query": "example", "exts": ["mp4"], "kinds": ["video"]}),
    ("Videolar papkasidagi eng yangi videoni ko‘rsat.", "find_files", {"folder": "videos", "latest": True, "kinds": ["video"], "then": "show"}),
    ("Rus tilidagi videolarni top.", "find_files", {"lang": "ru", "kinds": ["video"]}),
    ("Show me the available files in my authorized folders.", "list_files", {}),
    ("Open the video I requested.", "find_files", {"then": "open", "ref": True, "kinds": ["video"]}),
    ("Kompyuterimdagi barcha ruxsat berilgan joylardan shu faylni qidir.", "find_files", {"ref": True, "bare": True, "query": ""}),
    ("Открой видео example.mp4", "find_files", {"query": "example", "then": "open", "exts": ["mp4"]}),
    ("Найди видео в папке Загрузки", "find_files", {"folder": "downloads", "kinds": ["video"]}),
    ("Покажи самое новое видео в папке Видео", "find_files", {"folder": "videos", "latest": True}),
    ("Покажи русские видео", "find_files", {"lang": "ru"}),
    ("Rasmlar papkasidagi rasmlarni ko'rsat", "find_files", {"folder": "pictures", "kinds": ["image"]}),
    ("find mp3 songs in Music folder", "find_files", {"folder": "music", "kinds": ["audio"]}),
    ("Hujjatlar papkasidagi pdf fayllarni ko'rsat", "find_files", {"folder": "documents", "exts": ["pdf"]}),
    ("ish stolidagi rasmlarni top", "find_files", {"folder": "desktop", "kinds": ["image"]}),
    ("Desktopdagi fayllarni ko'rsat", "list_files", {"folder": "desktop"}),
    ("«Yozgi tatil» videosini och", "find_files", {"query": "Yozgi tatil", "then": "open"}),
    ("Find the latest video in Downloads", "find_files", {"latest": True, "folder": "downloads"}),
])
def test_file_commands_are_understood(text, action, sub):
    r, c = p(text)
    assert r.kind == "ok" and c.action == action, (text, r)
    for k, v in sub.items():
        assert c.args.get(k) == v, (text, k, c.args)
    assert c.needs_confirm is False                                            # qidirish faqat o'qiydi; ochish alohida tasdiqlanadi


@pytest.mark.parametrize("text", ["Downloads papkasini och", "Chrome'ni och", "Fayl menejerini och", "Kalkulyatorni och", "File Explorer ochilsin",
                                  "YouTube'da video top", "Google'dan video qidir", "Python haqida qidir", "Google'da faylni o'chirish haqida qidir"])
def test_existing_commands_are_not_hijacked(text):
    r, c = p(text)
    assert not (c and c.action in commands.FILE_ACTIONS), (text, c)


@pytest.mark.parametrize("text", [
    "Delete the video named example.mp4", "videoni o'chir", "Find and delete old videos", "Downloads papkasidagi fayllarni ko'chir",
    "Rename the file report.pdf", "Удали видео example.mp4", "Faylni boshqa joyga ko'chir", "Send the video example.mp4 to John", "Move the file to Desktop",
    "Open the video and delete it", "videoni top va o'chir", "Faylni nusxala",
])
def test_destructive_file_requests_are_always_blocked(text):
    r, c = p(text)
    assert r.kind == "blocked" and not r.commands, (text, r)


def test_dangerous_words_inside_a_file_name_are_just_data():
    r, c = p("Find the video named delete_me.mp4")
    assert r.kind == "ok" and c.action == "find_files" and c.args["query"] == "delete_me"
    r, c = p("«remove all files» videosini top")
    assert r.kind == "ok" and c.action == "find_files" and c.args["query"] == "remove all files"


@pytest.mark.parametrize("text", ["Open that person's video", "Открой видео того человека", "o'sha odamning videosini och"])
def test_ambiguous_person_request_asks_instead_of_guessing(text):
    r, c = p(text)
    assert r.kind == "clarify" and not r.commands


def test_open_without_any_name_is_marked_bare_so_the_executor_asks():
    r, c = p("Videoni och")
    assert c.args["bare"] is True and c.args["then"] == "open"


@pytest.mark.parametrize("text,n,kind,idx", [
    ("2", 5, "pick", 1), ("birinchisini och", 3, "open", 0), ("ikkinchi", 3, "pick", 1), ("open the third one", 5, "open", 2), ("открой первый", 3, "open", 0),
    ("второй", 3, "pick", 1), ("number 4", 5, "pick", 3), ("ochib ber", 1, "open", None), ("open it", 1, "open", None), ("bekor", 3, "cancel", None),
    ("cancel", 3, "cancel", None), ("отмена", 3, "cancel", None),
])
def test_choosing_from_the_list(text, n, kind, idx):
    ch = fileintent.parse_choice(text, n)
    assert ch is not None and (ch.kind, ch.index) == (kind, idx), (text, ch)


@pytest.mark.parametrize("text", ["Chrome'ni och", "Salom", "100 dollar necha so'm", "Python nima?", "Downloads papkasidan videoni top", "video"])
def test_other_sentences_are_not_choices(text):
    assert fileintent.parse_choice(text, 5) is None


# ------------------------------------------------------------------ ijrochi
def setup_exec(tmp_path, tree, confirm=True):
    st = Settings(); st.confirm_commands = confirm
    plat = FakePlatform({}, tree)
    fa = fs.FileAccess(st, save=False)
    assert fa.add_root(tree)[0]
    return st, plat, fa, Executor(st, plat, files=fa)


def run(ex, text):
    r = commands.parse(text)
    assert r.kind == "ok", (text, r)
    return ex.execute(r.commands[0], r.lang)


def test_find_reports_names_paths_sizes_and_remembers_results(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    res = run(ex, "Find the video named holiday")
    assert res.ok and len(res.files) == 2 and "holiday_2025.mp4" in res.message and str(tree) in res.message and "KB" in res.message
    assert ex.last_results == res.files and res.then == "show"


def test_nothing_found_is_reported_clearly(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    res = run(ex, "Find the video named nosuchfile123.mp4")
    assert res.files == [] and "nosuchfile123" in res.message
    assert run(ex, "Open the video named nosuchfile123.mp4").ok is False


def test_issue_detection_no_roots_scope_denied_and_missing_name(tmp_path, tree):
    st = Settings(); plat = FakePlatform({}, tree); ex = Executor(st, plat, files=fs.FileAccess(st, save=False))
    cmd = commands.parse("Downloads papkasidan videoni top").commands[0]
    issue = ex.file_issue(cmd, "uz")
    assert issue.kind == "no_roots" and issue.hint == tree
    other = tmp_path / "Other"; other.mkdir()
    ex.files.add_root(other)
    assert ex.file_issue(cmd, "uz").kind == "scope_denied"
    ex.files.add_root(tree)
    assert ex.file_issue(cmd, "uz") is None
    assert ex.file_issue(commands.parse("Videoni och").commands[0], "uz").kind == "ask_name"
    assert ex.file_issue(commands.parse("shu faylni qidir").commands[0], "uz").kind == "ask_name"


def test_scope_denied_search_does_not_leak_files_from_other_authorized_folders(tmp_path, tree):
    other = tmp_path / "Other"; other.mkdir(); (other / "other.mp4").write_bytes(b"x")
    st = Settings(); plat = FakePlatform({}, tmp_path / "Elsewhere")
    ex = Executor(st, plat, files=fs.FileAccess(st, save=False)); ex.files.add_root(other)
    res = run(ex, "Downloads papkasidan videoni top")
    assert res.ok is False and "other.mp4" not in res.message


def open_result(ex, query, **kw):
    e = ex.files.search(fs.Query(query)).entries[0]
    return e, ex.execute(commands.Command("open_file", {"path": str(e.path)}), "en")


def test_open_sends_the_real_file_to_windows_and_does_not_claim_it_is_playing(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    e, res = open_result(ex, "example")
    assert res.ok and plat.calls == [("file", str(Path(os.path.realpath(e.path))))]
    assert "request" in res.message.lower() and "cannot verify" in res.message.lower() and "playing" not in res.message.lower()


def test_unlisted_path_is_never_opened(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    res = ex.execute(commands.Command("open_file", {"path": str(tree / "example.mp4")}), "en")
    assert res.ok is False and plat.calls == []
    outside = tmp_path / "outside.mp4"; outside.write_bytes(b"x")
    assert ex.execute(commands.Command("open_file", {"path": str(outside)}), "en").ok is False and plat.calls == []


def test_exe_and_macro_files_are_refused_with_a_reason(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    for q in ("setup", "report"):
        e, res = open_result(ex, q)
        assert res.ok is False and "safety" in res.message and plat.calls == []


def test_open_after_revoke_missing_file_and_windows_errors_are_reported(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    e = fa.search(fs.Query("photo")).entries[0]
    e.path.unlink()
    res = ex.execute(commands.Command("open_file", {"path": str(e.path)}), "en")
    assert res.ok is False and "not found" in res.message and plat.calls == []
    e2 = fa.search(fs.Query("example")).entries[0]
    plat.open_error = OSError(0, "boom"); assert ex.execute(commands.Command("open_file", {"path": str(e2.path)}), "en").ok is False
    err = OSError(1155, "No application is associated"); err.winerror = 1155
    plat.open_error = err
    assert "default app" in ex.execute(commands.Command("open_file", {"path": str(e2.path)}), "en").message
    plat.open_error = None
    fa.remove_root(tree)
    res = ex.execute(commands.Command("open_file", {"path": str(e2.path)}), "en")
    assert res.ok is False and plat.calls == []


def test_configured_video_player_is_used_only_for_videos_and_without_a_shell(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    player = tmp_path / "vlc.exe"; player.write_bytes(b"x")
    st.video_player = str(player)
    e, res = open_result(ex, "example")
    assert res.ok and plat.calls == [("player", str(player), str(Path(os.path.realpath(e.path))))]
    plat.calls.clear()
    e, res = open_result(ex, "notes")
    assert plat.calls[0][0] == "file"                                           # hujjat -> standart ilova
    plat.calls.clear()
    st.video_player = str(tmp_path / "missing.exe")
    e, res = open_result(ex, "example")
    assert plat.calls[0][0] == "file" and "was not found" in res.message


def test_list_files_shows_contents_of_authorized_folders(tmp_path, tree):
    st, plat, fa, ex = setup_exec(tmp_path, tree)
    res = run(ex, "Show me the available files in my authorized folders.")
    assert res.ok and "nested" in res.message and "example.mp4" in res.message and "secrets.env" not in res.message and str(tree) in res.message
    assert ex.last_results == res.files


def test_ui_lists_never_contain_markup_that_is_interpreted(tmp_path):
    d = tmp_path / "Media"; d.mkdir()
    (d / "<b>bold<i>.mp4").write_bytes(b"x")
    st = Settings(); fa = fs.FileAccess(st, save=False); fa.add_root(d)
    e = fa.search(fs.Query()).entries[0]
    assert e.display == "<b>bold<i>.mp4"          # matn o'zgarmaydi; ko'rsatish qatlami PlainText bilan chizadi (test_files_ui)
