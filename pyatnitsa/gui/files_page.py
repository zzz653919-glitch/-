"""File Access: ruxsat etilgan papkalar, qidirish, natijalar va faylni ochish. Faqat foydalanuvchi AYNAN ruxsat bergan joylar."""
from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QFileDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QMenu, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from .. import apps, files as fs
from ..settings import Settings
from .icons import icon
from .pages import page_header
from .theme import C

REASONS = {
    "missing": "That folder does not exist.",
    "not_dir": "Please choose a folder or a drive, not a file.",
    "protected": "This is a protected system location (Windows, Program Files, ProgramData, AppData or Пятница's own data). It cannot be authorized.",
    "too_broad": "The whole system root cannot be authorized. Choose a specific folder.",
    "exists": "This location is already authorized.",
}
STD_FOLDERS = [("Desktop", "desktop"), ("Documents", "documents"), ("Downloads", "downloads"), ("Pictures", "pictures"), ("Music", "music"), ("Videos", "videos")]
TYPE_FILTERS = [("All files", ""), ("Videos", "video"), ("Images", "image"), ("Audio", "audio"), ("Documents", "document"), ("Other", "other")]


class FilesPage(QWidget):
    accessChanged = Signal()           # ruxsat qo'shildi/bekor qilindi (oyna ro'yxatni tozalaydi, terminalga yozadi)
    _done = Signal(object)

    def __init__(self, access: fs.FileAccess, platform: apps.Platform, settings: Settings, open_cb=None, log_cb=None):
        super().__init__()
        self.access, self.platform, self.s = access, platform, settings
        self._open_cb, self._log = open_cb, log_cb or (lambda *a: None)
        self._rid = 0
        self._cancel = threading.Event()
        self._entries: list[fs.FileEntry] = []
        self._retry = None
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        lay.addLayout(page_header("FILE ACCESS", "Пятница can search and open files only inside the folders you authorize here. Nothing is deleted, changed, moved or uploaded."))

        # ---- ruxsat etilgan joylar
        acc = QFrame(); acc.setObjectName("panel"); al = QVBoxLayout(acc); al.setContentsMargins(16, 12, 16, 12); al.setSpacing(8)
        t = QLabel("AUTHORIZED LOCATIONS"); t.setObjectName("section"); al.addWidget(t)
        row = QHBoxLayout(); row.setSpacing(10)
        self.roots = QListWidget(); self.roots.setMinimumHeight(70); self.roots.setMaximumHeight(130); self.roots.setSelectionMode(QAbstractItemView.SingleSelection)
        row.addWidget(self.roots, 1)
        btns = QVBoxLayout(); btns.setSpacing(6)
        self.add_btn = QPushButton("Add Folder…"); self.add_btn.setObjectName("primary"); self.add_btn.setIcon(icon("files", C["cyan"], 16))
        self.add_btn.setToolTip("Choose a folder or a whole drive that Пятница may search. Windows permissions still apply.")
        self.add_btn.clicked.connect(self.add_folder)
        self.std_btn = QPushButton("Add standard folder"); self.std_btn.setToolTip("Desktop, Documents, Downloads, Pictures, Music, Videos")
        menu = QMenu(self.std_btn)
        for label, key in STD_FOLDERS:
            menu.addAction(label, lambda k=key: self.add_standard(k))
        self.std_btn.setMenu(menu)
        self.rm_btn = QPushButton("Remove Access"); self.rm_btn.setIcon(icon("trash", C["muted"], 16)); self.rm_btn.setEnabled(False)
        self.rm_btn.setToolTip("Revoke access to the selected location immediately.")
        self.rm_btn.clicked.connect(self.remove_selected)
        for b in (self.add_btn, self.std_btn, self.rm_btn):
            btns.addWidget(b)
        btns.addStretch(1); row.addLayout(btns); al.addLayout(row)
        self.perm = QLabel(); self.perm.setObjectName("sub"); self.perm.setWordWrap(True); self.perm.setTextFormat(Qt.RichText); al.addWidget(self.perm)
        prow = QHBoxLayout(); prow.setSpacing(8)
        prow.addWidget(QLabel("Video player:"))
        self.player_lbl = QLabel(); self.player_lbl.setObjectName("sub"); prow.addWidget(self.player_lbl, 1)
        self.player_btn = QPushButton("Choose…"); self.player_btn.setToolTip("Optional: open videos with this program instead of the Windows default.")
        self.player_btn.clicked.connect(self.choose_player)
        self.player_reset = QPushButton("Use Windows default"); self.player_reset.clicked.connect(self.reset_player)
        prow.addWidget(self.player_btn); prow.addWidget(self.player_reset); al.addLayout(prow)
        lay.addWidget(acc)

        # ---- qidirish
        sp = QFrame(); sp.setObjectName("panel"); sl = QVBoxLayout(sp); sl.setContentsMargins(16, 12, 16, 12); sl.setSpacing(8)
        t2 = QLabel("SEARCH"); t2.setObjectName("section"); sl.addWidget(t2)
        srow = QHBoxLayout(); srow.setSpacing(8)
        self.query = QLineEdit(); self.query.setPlaceholderText("File name or part of it (leave empty to list the newest files of the chosen type)")
        self.kind = QComboBox(); [self.kind.addItem(n, v) for n, v in TYPE_FILTERS]
        self.search_btn = QPushButton("Search"); self.search_btn.setObjectName("primary"); self.search_btn.setIcon(icon("files", C["cyan"], 16))
        self.cancel_btn = QPushButton("Cancel"); self.cancel_btn.hide()
        srow.addWidget(self.query, 1); srow.addWidget(self.kind); srow.addWidget(self.search_btn); srow.addWidget(self.cancel_btn)
        sl.addLayout(srow)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Name", "Location", "Type", "Size", "Modified"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows); self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers); self.table.verticalHeader().hide(); self.table.setShowGrid(False)
        hh = self.table.horizontalHeader(); hh.setSectionResizeMode(0, QHeaderView.Stretch); hh.setSectionResizeMode(1, QHeaderView.Stretch)
        for c in (2, 3, 4):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.empty = QLabel(); self.empty.setObjectName("empty"); self.empty.setAlignment(Qt.AlignCenter); self.empty.setWordWrap(True)
        sl.addWidget(self.table, 1); sl.addWidget(self.empty, 1)
        orow = QHBoxLayout()
        self.status = QLabel(); self.status.setObjectName("sub"); self.status.setWordWrap(True); self.status.setTextFormat(Qt.PlainText)
        self.open_btn = QPushButton("Open File"); self.open_btn.setObjectName("primary"); self.open_btn.setIcon(icon("play", C["cyan"], 16)); self.open_btn.setEnabled(False)
        self.open_btn.setToolTip("Opens the selected file with its default Windows app (or the video player you chose). Programs and scripts are never opened.")
        orow.addWidget(self.status, 1); orow.addWidget(self.open_btn, 0, Qt.AlignRight); sl.addLayout(orow)
        lay.addWidget(sp, 1)

        self.roots.itemSelectionChanged.connect(lambda: self.rm_btn.setEnabled(bool(self.roots.selectedItems())))
        self.table.itemSelectionChanged.connect(lambda: self.open_btn.setEnabled(bool(self.table.selectedItems())))
        self.table.itemDoubleClicked.connect(lambda _i: self.open_selected())
        self.search_btn.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        self.cancel_btn.clicked.connect(self._cancel_search)
        self.open_btn.clicked.connect(self.open_selected)
        self._done.connect(self._on_done)
        self.refresh()
        self._show_empty("Add a folder, then search it. Results appear here.")

    # ------------------------------------------------------------------ ruxsat ro'yxati
    def refresh(self) -> None:
        self.roots.clear()
        for r in self.access.stored():
            bad = fs.root_problem(r)
            it = QListWidgetItem(r + ("   (unavailable — folder missing or protected)" if bad else ""))
            it.setData(Qt.UserRole, r)
            if bad:
                it.setForeground(Qt.gray)
            self.roots.addItem(it)
        n = len(self.access.roots())
        if n:
            self.perm.setText(f"<span style='color:{C['ok']}'>● {n} location{'s' if n != 1 else ''} authorized.</span> Пятница cannot see anything outside "
                              "the list above. Windows permissions still apply and system folders are skipped.")
        else:
            self.perm.setText(f"<span style='color:{C['warn']}'>● No folders authorized yet.</span> Add a folder to let Пятница search it.")
        player = (self.s.video_player or "").strip()
        self.player_lbl.setText(player or "Windows default")
        self.player_reset.setEnabled(bool(player))
        self.search_btn.setEnabled(n > 0)

    def _pick_folder(self, start: str = "") -> str:
        return QFileDialog.getExistingDirectory(self, "Choose a folder Пятница may access", start or str(Path.home()))

    def _confirm(self, title: str, text: str) -> bool:
        return QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def grant(self, path: str) -> bool:
        """Foydalanuvchi aniq tasdiqlagan joyga ruxsat. Disk ildizi uchun alohida ogohlantirish."""
        p = Path(path)
        if p.parent == p:
            if not self._confirm("Authorize a whole drive?", f"This lets Пятница search the entire drive {path}.\n\nWindows, Program Files, ProgramData, AppData and other "
                                 "protected system folders are always skipped. Continue?"):
                self.set_status("Access was not granted.", "warn")
                return False
        ok, why = self.access.add_root(p)
        if ok:
            self.set_status(f"Access granted: {path}", "ok")
            self._log("info", "SECURITY", f"File access granted: {path}")
            self.refresh(); self.accessChanged.emit()
            return True
        self.set_status(REASONS.get(why, why), "warn" if why == "exists" else "err")
        self.refresh()
        return False

    def add_folder(self) -> None:
        path = self._pick_folder()
        if path:
            self.grant(path)

    def add_standard(self, key: str) -> None:
        p = self.platform.folder_path(key)
        if p is None or not Path(p).is_dir():
            self.set_status(f"The {key.capitalize()} folder was not found on this computer.", "err")
            return
        self.grant(str(p))

    def remove_selected(self) -> None:
        items = self.roots.selectedItems()
        if not items:
            return
        path = items[0].data(Qt.UserRole)
        if self.access.remove_root(path):
            self.set_status(f"Access revoked: {path}. Пятница can no longer see this location.", "ok")
            self._log("info", "SECURITY", f"File access revoked: {path}")
            self._entries = [e for e in self._entries if self.access.is_allowed(e.path)]
            self._fill(self._entries)
            self.refresh(); self.accessChanged.emit()

    # ------------------------------------------------------------------ buyruq orqali ruxsat so'rash (boshqaruvchi signali)
    def request_grant(self, hint: str, retry) -> None:
        """Ovozli/matnli buyruq ruxsatsiz papkani so'radi: foydalanuvchidan aniq ruxsat (dialog) so'raladi; berilsa buyruq qayta bajariladi."""
        self._retry = retry
        if hint and Path(hint).is_dir():
            text = (f"Пятница wants to search inside:\n\n{hint}\n\nOnly this folder and what is inside it will be accessible. Allow?")
            if self._confirm("Allow access to this folder?", text) and self.grant(hint):
                retry()
                return
            self.set_status("Access was not granted. Nothing was searched.", "warn")
            return
        if self._confirm("Choose a folder", "Пятница can only search folders you authorize. Do you want to choose a folder now?"):
            path = self._pick_folder()
            if path and self.grant(path):
                retry()
                return
        self.set_status("Access was not granted. Nothing was searched.", "warn")

    # ------------------------------------------------------------------ pleyer
    def choose_player(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose a video player", "", "Programs (*.exe)")
        if not path:
            return
        if Path(path).suffix.lower() != ".exe" or not Path(path).is_file():
            self.set_status("Please choose a program (.exe).", "err")
            return
        self.s.video_player = path
        self.s.save(); self.refresh()
        self.set_status(f"Videos will open with: {path}", "ok")

    def reset_player(self) -> None:
        self.s.video_player = ""
        self.s.save(); self.refresh()
        self.set_status("Videos will open with the Windows default app.", "ok")

    # ------------------------------------------------------------------ qidirish
    def search(self) -> None:
        if not self.access.roots():
            self.set_status("No folders are authorized yet. Add a folder first.", "warn")
            return
        self._cancel.set()
        self._rid += 1
        rid, ev = self._rid, threading.Event()
        self._cancel = ev
        q = fs.Query(self.query.text().strip()[:200], frozenset({k for k in (self.kind.currentData(),) if k}), limit=200)
        self.search_btn.setEnabled(False); self.cancel_btn.show()
        self.set_status("Searching…", "neutral")

        def work():
            try:
                out = self.access.search(q, None, cancel=ev)
            except Exception as e:  # noqa: BLE001
                out = e
            self._done.emit((rid, out))
        threading.Thread(target=work, name="file-search", daemon=True).start()

    def _cancel_search(self) -> None:
        self._cancel.set()

    def _on_done(self, payload) -> None:
        rid, out = payload
        if rid != self._rid:
            return                                             # eskirgan natija
        self.cancel_btn.hide(); self.search_btn.setEnabled(bool(self.access.roots()))
        if isinstance(out, Exception):
            self.set_status(f"Search failed: {type(out).__name__}: {out}", "err")
            return
        self._entries = list(out.entries)
        self._fill(self._entries)
        notes = []
        if out.denied:
            notes.append(f"{out.denied} folder(s) skipped — Windows denied access")
        if out.cancelled:
            notes.append("search cancelled")
        if out.truncated:
            notes.append("result incomplete (limit or time reached) — refine the name")
        if out.fuzzy:
            notes.append("no exact match — showing similar names")
        base = f"{len(self._entries)} result(s) · {out.scanned} items checked in {out.elapsed:.1f} s"
        self.set_status(base + ("  ·  " + "; ".join(notes) if notes else ""), "warn" if notes else ("ok" if self._entries else "neutral"))
        if not self._entries:
            self._show_empty("Nothing found in the authorized folders." + ("" if not self.query.text().strip() else " Check the spelling or try a shorter part of the name."))

    def _fill(self, entries: list[fs.FileEntry]) -> None:
        self.table.setRowCount(0)
        for e in entries:
            r = self.table.rowCount(); self.table.insertRow(r)
            vals = [e.display, fs.safe_display(str(e.parent), 260), e.kind if e.kind != "other" else (e.ext or "file"), fs.fmt_size(e.size), fs.fmt_date(e.mtime)]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.UserRole, str(e.path)); it.setToolTip(str(e.path))
                self.table.setItem(r, c, it)
        self.table.setVisible(bool(entries)); self.empty.setVisible(not entries)

    def _show_empty(self, text: str) -> None:
        self.table.setRowCount(0); self.table.setVisible(False)
        self.empty.setText(text); self.empty.setVisible(True)

    # ------------------------------------------------------------------ ochish
    def selected_path(self) -> str:
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return ""
        return self.table.item(rows[0].row(), 0).data(Qt.UserRole) or ""

    def open_selected(self) -> None:
        path = self.selected_path()
        if not path:
            return
        if not self._open_cb:
            self.set_status("Opening is not available.", "err")
            return
        self.set_status("Opening… the result is shown in the conversation.", "neutral")
        self._open_cb(path)

    # ------------------------------------------------------------------ holat
    def set_status(self, text: str, level: str = "neutral") -> None:
        col = {"ok": C["ok"], "warn": C["warn"], "err": C["err"]}.get(level, C["muted"])
        self.status.setStyleSheet(f"color:{col};")
        self.status.setText(text)

    def stop(self) -> None:
        self._cancel.set()
