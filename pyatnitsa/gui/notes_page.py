"""Notes: yaratish, tahrirlash, o'chirish (tasdiq bilan), nom/mazmun/teg/kategoriya bo'yicha qidirish, avtomatik saqlash va aniq holat xabari.
Format: oddiy matn + Markdown belgilari (**qalin**, *kursiv*, # sarlavha, - ro'yxat); tugmalar belgilarni qo'yib beradi. Faqat mahalliy SQLite'da."""
from __future__ import annotations

import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QVBoxLayout,
                               QWidget)

from ..notes import NoteExists
from . import common
from .common import Page, empty_label, panel, status_style
from .icons import icon
from .pages import page_header
from .theme import C

AUTOSAVE_MS = 1200


class NotesPage(Page):
    changed = Signal(str)
    watches = ("notes",)

    def __init__(self, ex, autosave_ms: int = AUTOSAVE_MS):
        super().__init__()
        self.ex = ex
        self._id: str | None = None
        self._dirty = False
        self._loaded_updated = ""
        self._loading = False
        self._timer = QTimer(self, singleShot=True, interval=autosave_ms)
        self._timer.timeout.connect(self.save)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(12)
        top = QHBoxLayout(); top.addLayout(page_header("NOTES", "Local notes with categories and tags. Changes are saved automatically; nothing is uploaded anywhere."), 1)
        self.new_btn = QPushButton("New note"); self.new_btn.setObjectName("primary"); self.new_btn.setIcon(icon("notes", C["cyan"], 16)); top.addWidget(self.new_btn, 0, Qt.AlignTop)
        lay.addLayout(top)
        body = QHBoxLayout(); body.setSpacing(12)
        # ---- chap: ro'yxat
        left, ll = panel()
        left.setMinimumWidth(240); left.setMaximumWidth(340)
        self.search = QLineEdit(); self.search.setPlaceholderText("Search title, text, tags…"); self.search.setClearButtonEnabled(True)
        self.category = QComboBox(); self.tag = QComboBox()
        self.listw = QListWidget()
        self.list_empty = empty_label("")
        self.del_btn = QPushButton("Delete note"); self.del_btn.setIcon(icon("trash", C["muted"], 16))
        ll.addWidget(self.search); ll.addWidget(self.category); ll.addWidget(self.tag); ll.addWidget(self.listw, 1); ll.addWidget(self.list_empty, 1); ll.addWidget(self.del_btn)
        body.addWidget(left)
        # ---- o'ng: muharrir
        right, rl = panel()
        self.editor_host = QWidget(); el = QVBoxLayout(self.editor_host); el.setContentsMargins(0, 0, 0, 0); el.setSpacing(8)
        self.title = QLineEdit(); self.title.setPlaceholderText("Title"); self.title.setMaxLength(120)
        row = QHBoxLayout()
        self.cat_edit = QLineEdit(); self.cat_edit.setPlaceholderText("Category"); self.cat_edit.setMaxLength(40)
        self.tags_edit = QLineEdit(); self.tags_edit.setPlaceholderText("Tags, comma-separated")
        self.pin = QCheckBox("Pin")
        row.addWidget(self.cat_edit, 1); row.addWidget(self.tags_edit, 2); row.addWidget(self.pin)
        fmt = QHBoxLayout(); fmt.setSpacing(6)
        self.fmt_btns = {}
        for key, label, tip in (("bold", "B", "Bold (**text**)"), ("italic", "I", "Italic (*text*)"), ("heading", "H", "Heading (# text)"), ("list", "•", "Bullet list (- item)")):
            b = QPushButton(label); b.setToolTip(tip); b.setFixedWidth(38); b.clicked.connect(lambda _=False, k=key: self.apply_format(k)); fmt.addWidget(b); self.fmt_btns[key] = b
        fmt.addStretch(1)
        self.body = QPlainTextEdit(); self.body.setPlaceholderText("Write your note… Simple Markdown markers are supported: **bold**, *italic*, # heading, - list")
        foot = QHBoxLayout()
        self.meta = QLabel(); self.meta.setObjectName("dim")
        self.save_status = QLabel(); self.save_status.setObjectName("sub"); self.save_status.setTextFormat(Qt.PlainText); self.save_status.setWordWrap(True)
        self.save_btn = QPushButton("Save now")
        foot.addWidget(self.meta, 1); foot.addWidget(self.save_status, 1); foot.addWidget(self.save_btn)
        el.addWidget(self.title); el.addLayout(row); el.addLayout(fmt); el.addWidget(self.body, 1); el.addLayout(foot)
        self.editor_empty = empty_label("Select a note on the left, or press “New note”.")
        rl.addWidget(self.editor_host, 1); rl.addWidget(self.editor_empty, 1)
        body.addWidget(right, 1)
        lay.addLayout(body, 1)

        self.new_btn.clicked.connect(self.create); self.del_btn.clicked.connect(self.delete); self.save_btn.clicked.connect(self.save)
        self.listw.currentItemChanged.connect(self._on_select)
        self.search.textChanged.connect(lambda _t: self.refresh())
        self.category.currentIndexChanged.connect(lambda _i: self.refresh()); self.tag.currentIndexChanged.connect(lambda _i: self.refresh())
        for w in (self.title, self.cat_edit, self.tags_edit):
            w.textEdited.connect(self._edited)
        self.body.textChanged.connect(self._edited); self.pin.toggled.connect(self._edited)
        self.refresh()

    # ---- ro'yxat
    def refresh(self) -> None:
        notes = self.ex.notes
        self.category.blockSignals(True); self.tag.blockSignals(True)
        c0, t0 = self.category.currentData(), self.tag.currentData()
        self.category.clear(); self.category.addItem("All categories", "")
        [self.category.addItem(c, c) for c in notes.categories()]
        self.tag.clear(); self.tag.addItem("All tags", "")
        [self.tag.addItem(f"#{t}", t) for t in notes.tags()]
        self.category.setCurrentIndex(max(0, self.category.findData(c0))); self.tag.setCurrentIndex(max(0, self.tag.findData(t0)))
        self.category.blockSignals(False); self.tag.blockSignals(False)
        found = notes.search(self.search.text(), self.tag.currentData() or "", self.category.currentData() or "")
        self.listw.blockSignals(True)
        self.listw.clear()
        for n in found:
            it = QListWidgetItem(("★ " if n.pinned else "") + n.title + (f"   [{n.category}]" if n.category else ""))
            it.setData(Qt.UserRole, n.id)
            it.setToolTip(" ".join(n.body.split())[:160])
            self.listw.addItem(it)
            if n.id == self._id:
                self.listw.setCurrentItem(it)
        self.listw.blockSignals(False)
        has = bool(found)
        self.listw.setVisible(has); self.list_empty.setVisible(not has)
        self.list_empty.setText("No notes yet.\nPress “New note”, or say: “Create a note called …”." if not notes.all() else "No notes match the search.")
        # ovoz yoki boshqa joyda o'zgargan bo'lsa va muharrirda saqlanmagan o'zgarish bo'lmasa — muharrir yangilanadi
        if self._id:
            cur = notes.get(self._id)
            if cur is None:
                self._show_editor(None)
            elif not self._dirty and cur.updated != self._loaded_updated:
                self._load(cur)
        self.del_btn.setEnabled(self._id is not None)

    def _show_editor(self, note) -> None:
        self._id = note.id if note else None
        self.editor_host.setVisible(note is not None); self.editor_empty.setVisible(note is None)
        self.del_btn.setEnabled(note is not None)
        if note is not None:
            self._load(note)

    def _load(self, n) -> None:
        self._loading = True
        self._id, self._loaded_updated, self._dirty = n.id, n.updated, False
        self.title.setText(n.title); self.cat_edit.setText(n.category); self.tags_edit.setText(", ".join(n.tags)); self.body.setPlainText(n.body); self.pin.setChecked(n.pinned)
        self.meta.setText(f"Created {n.created.replace('T', ' ')[:16]} · Modified {n.updated.replace('T', ' ')[:16]}")
        status_style(self.save_status, "Saved" if n.created != n.updated or n.body else "Ready", "neutral")
        self._loading = False

    def _on_select(self, cur, _prev) -> None:
        nid = cur.data(Qt.UserRole) if cur is not None else None      # flush() ro'yxatni qayta qurishi mumkin — id oldindan olinadi
        self.flush()
        if nid is None:
            self._show_editor(None)
            return
        self._show_editor(self.ex.notes.get(nid))
        for i in range(self.listw.count()):
            if self.listw.item(i).data(Qt.UserRole) == nid and self.listw.currentRow() != i:
                self.listw.blockSignals(True); self.listw.setCurrentRow(i); self.listw.blockSignals(False)

    # ---- tahrirlash va avtomatik saqlash
    def _edited(self, *_a) -> None:
        if self._loading or not self._id:
            return
        self._dirty = True
        status_style(self.save_status, "Unsaved changes… (saving automatically)", "warn")
        self._timer.start()

    def flush(self) -> None:
        if self._timer.isActive():
            self._timer.stop()
        if self._dirty:
            self.save()

    def save(self) -> bool:
        if not self._id or not self._dirty:
            return True
        self._timer.stop()
        tags = [t.strip() for t in self.tags_edit.text().split(",") if t.strip()]
        try:
            n = self.ex.notes.update(self._id, title=self.title.text(), body=self.body.toPlainText(), tags=tags, pinned=self.pin.isChecked(), category=self.cat_edit.text())
        except NoteExists as e:
            status_style(self.save_status, f"Not saved: a note titled “{e.note.title}” already exists. Choose a different title.", "err")
            return False
        except ValueError:
            status_style(self.save_status, "Not saved: the title cannot be empty.", "err")
            return False
        except Exception as e:  # noqa: BLE001
            status_style(self.save_status, f"Not saved: {type(e).__name__}", "err")
            return False
        if n is None:
            status_style(self.save_status, "Not saved: this note no longer exists.", "err")
            return False
        self._dirty, self._loaded_updated = False, n.updated
        self.meta.setText(f"Created {n.created.replace('T', ' ')[:16]} · Modified {n.updated.replace('T', ' ')[:16]}")
        status_style(self.save_status, f"Saved {time.strftime('%H:%M:%S')}", "ok")
        self.refresh()
        self.changed.emit("notes")
        return True

    def apply_format(self, kind: str) -> None:
        if not self._id:
            return
        c = self.body.textCursor()
        sel = c.selectedText().replace(" ", "\n")
        if kind in ("bold", "italic"):
            m = "**" if kind == "bold" else "*"
            c.insertText(f"{m}{sel or 'text'}{m}")
        else:
            prefix = "# " if kind == "heading" else "- "
            c.insertText("\n".join(prefix + line for line in (sel or "text").split("\n")))
        self.body.setTextCursor(c)

    # ---- yaratish / o'chirish
    def create(self) -> None:
        self.flush()
        n, _old = self.ex.notes.add_auto("New note", "")
        self._id = n.id
        self.changed.emit("notes")
        self.refresh()
        self.select(n.id)
        self.title.setFocus(); self.title.selectAll()

    def select(self, nid: str) -> None:
        for i in range(self.listw.count()):
            if self.listw.item(i).data(Qt.UserRole) == nid:
                self.listw.setCurrentRow(i)
                return
        n = self.ex.notes.get(nid)
        self._show_editor(n)

    def delete(self) -> None:
        if not self._id:
            return
        n = self.ex.notes.get(self._id)
        if n is None:
            return
        if not common.ask(self, "Delete note", f"Permanently delete this note?\n\n“{n.title}”\n\nThis cannot be undone.", yes="Delete"):
            return
        self._timer.stop(); self._dirty = False
        self.ex.notes.delete(n.id)
        self._id = None
        self._show_editor(None)
        self.refresh()
        self.changed.emit("notes")
        status_style(self.save_status, "Note deleted.", "ok")
