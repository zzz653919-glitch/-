"""Ranglar, shriftlar va umumiy QSS. Barcha vidjetlar ranglarni shu yerdan oladi."""
from __future__ import annotations

C = {
    "bg0": "#04060b", "bg1": "#090e18", "bg2": "#0d1424", "panel": "rgba(13, 21, 38, 0.72)", "panel_solid": "#0d1526",
    "border": "#1a2a47", "border_hi": "rgba(0, 229, 255, 0.55)",
    "cyan": "#00e5ff", "blue": "#2979ff", "violet": "#8b5cf6", "purple": "#6d28d9",
    "text": "#e8f1ff", "muted": "#8aa0bd", "dim": "#5a6f8c",
    "ok": "#2ee6a6", "warn": "#ffb020", "err": "#ff4d6d",
}
STATE_COLORS = {   # AI Core holatlari
    "standby": "#00bcd4", "listening": "#00e5ff", "processing": "#6c7bff", "interpreting": "#9d7bff", "thinking": "#8b5cf6", "speaking": "#2ee6a6", "confirm": "#a78bfa",
    "executing": "#38bdf8", "responding": "#22d3ee", "error": "#ff4d6d",
}
STATE_LABELS = {"standby": "READY", "listening": "LISTENING", "processing": "PROCESSING", "interpreting": "PROCESSING", "thinking": "THINKING", "speaking": "SPEAKING", "confirm": "AWAITING CONFIRMATION",
                "executing": "EXECUTING", "responding": "RESPONDING", "error": "ERROR"}
LEVEL_COLORS = {"info": "#8aa0bd", "active": "#8b9dff", "success": "#2ee6a6", "warn": "#ffb020", "error": "#ff4d6d"}
FONT_UI = "'Bahnschrift','Segoe UI Variable Text','Segoe UI','Inter','Noto Sans',sans-serif"
FONT_MONO = "'Cascadia Mono','Consolas','DejaVu Sans Mono',monospace"

STYLE = f"""
* {{ font-family: {FONT_UI}; font-size: 13px; color: {C['text']}; }}
QMainWindow, QDialog {{ background: {C['bg0']}; }}
QWidget#root {{ background: transparent; }}
QToolTip {{ background: {C['bg2']}; color: {C['text']}; border: 1px solid {C['cyan']}; padding: 4px 6px; }}

QFrame#panel {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 14px; }}
QFrame#panelHi {{ background: {C['panel']}; border: 1px solid {C['border_hi']}; border-radius: 14px; }}
QFrame#card {{ background: rgba(10, 17, 32, 0.78); border: 1px solid {C['border']}; border-radius: 12px; }}
QFrame#card:hover {{ border: 1px solid rgba(0, 229, 255, 0.35); }}
QFrame#sidebar {{ background: rgba(6, 10, 18, 0.88); border-right: 1px solid {C['border']}; }}
QFrame#rightbar {{ background: rgba(6, 10, 18, 0.60); border-left: 1px solid {C['border']}; }}

QLabel {{ background: transparent; }}
QLabel#title {{ font-size: 30px; font-weight: 700; letter-spacing: 9px; color: {C['text']}; }}
QLabel#status {{ font-size: 15px; font-weight: 700; letter-spacing: 4px; }}
QLabel#sub {{ color: {C['muted']}; }}
QLabel#dim {{ color: {C['dim']}; font-size: 12px; }}
QLabel#section {{ color: {C['muted']}; font-size: 11px; font-weight: 700; letter-spacing: 3px; }}
QLabel#big {{ font-size: 26px; font-weight: 700; }}
QLabel#pageTitle {{ font-size: 20px; font-weight: 700; letter-spacing: 3px; }}
QLabel#mono {{ font-family: {FONT_MONO}; font-size: 12px; color: {C['muted']}; }}
QLabel#empty {{ color: {C['dim']}; font-size: 13px; }}

QPushButton {{ background: rgba(18, 30, 54, 0.9); border: 1px solid {C['border']}; border-radius: 10px; padding: 8px 14px; }}
QPushButton:hover {{ border: 1px solid {C['cyan']}; background: rgba(0, 229, 255, 0.08); }}
QPushButton:pressed {{ background: rgba(0, 229, 255, 0.18); }}
QPushButton:disabled {{ color: {C['dim']}; border-color: #121c30; }}
QPushButton#primary {{ background: rgba(0, 229, 255, 0.16); border: 1px solid {C['cyan']}; font-weight: 700; }}
QPushButton#primary:hover {{ background: rgba(0, 229, 255, 0.28); }}
QPushButton#rec {{ background: rgba(255, 77, 109, 0.20); border: 1px solid {C['err']}; font-weight: 700; }}
QPushButton#ghost {{ background: transparent; border: 1px solid transparent; color: {C['muted']}; padding: 4px 8px; }}
QPushButton#ghost:hover {{ color: {C['text']}; border: 1px solid {C['border']}; }}
QPushButton#nav {{ background: transparent; border: none; border-left: 3px solid transparent; border-radius: 0;
                   text-align: left; padding: 11px 16px; color: {C['muted']}; font-size: 13px; letter-spacing: 1px; }}
QPushButton#nav:hover {{ background: rgba(0, 229, 255, 0.07); color: {C['text']}; }}
QPushButton#nav:checked {{ background: rgba(0, 229, 255, 0.12); border-left: 3px solid {C['cyan']}; color: {C['cyan']}; font-weight: 700; }}

QFrame#bubbleUser {{ background: rgba(109, 40, 217, 0.28); border: 1px solid rgba(139, 92, 246, 0.55); border-radius: 12px; }}
QFrame#bubbleAI {{ background: rgba(0, 229, 255, 0.07); border: 1px solid rgba(0, 229, 255, 0.35); border-radius: 12px; }}
QFrame#bubbleErr {{ background: rgba(255, 77, 109, 0.10); border: 1px solid rgba(255, 77, 109, 0.55); border-radius: 12px; }}
QLabel#bubbleHead {{ color: {C['muted']}; font-size: 11px; letter-spacing: 1px; }}
QLabel#bubbleSys {{ color: {C['dim']}; font-size: 12px; }}

QPlainTextEdit, QTextEdit, QLineEdit, QComboBox, QListWidget, QTableWidget, QSpinBox, QDateTimeEdit, QDateEdit, QTimeEdit {{
    background: rgba(6, 11, 22, 0.9); border: 1px solid {C['border']}; border-radius: 10px; padding: 7px;
    selection-background-color: rgba(0, 229, 255, 0.35); selection-color: #fff; }}
QSpinBox {{ min-width: 110px; padding-right: 22px; }}
QSpinBox::up-button, QSpinBox::down-button {{ width: 18px; border: none; background: transparent; }}
QSpinBox::up-arrow, QSpinBox::down-arrow {{ width: 8px; height: 8px; }}
QPlainTextEdit:focus, QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDateTimeEdit:focus, QTimeEdit:focus {{ border: 1px solid {C['cyan']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {C['bg2']}; border: 1px solid {C['border']}; selection-background-color: rgba(0,229,255,0.25); }}
QDateTimeEdit, QDateEdit, QTimeEdit {{ min-width: 150px; padding-right: 22px; }}
QDateTimeEdit::drop-down, QDateEdit::drop-down {{ width: 20px; border: none; }}
QCalendarWidget QWidget {{ background: {C['bg2']}; color: {C['text']}; }}
QCalendarWidget QAbstractItemView {{ selection-background-color: rgba(0,229,255,0.3); }}
QMenu {{ background: {C['bg2']}; border: 1px solid {C['border']}; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: rgba(0, 229, 255, 0.18); }}
QTabWidget::pane {{ border: 1px solid {C['border']}; border-radius: 10px; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {C['muted']}; padding: 8px 16px; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {C['cyan']}; border-bottom: 2px solid {C['cyan']}; }}
QListWidget::item {{ padding: 6px; border-radius: 6px; }}
QListWidget::item:selected {{ background: rgba(0, 229, 255, 0.18); }}
QFrame#toast {{ background: rgba(255, 176, 32, 0.14); border: 1px solid {C['warn']}; border-radius: 12px; }}
QPlainTextEdit#terminal {{ font-family: {FONT_MONO}; font-size: 12px; background: rgba(2, 5, 10, 0.92); }}
QHeaderView::section {{ background: {C['bg2']}; color: {C['muted']}; border: none; border-bottom: 1px solid {C['border']}; padding: 6px; }}
QTableWidget {{ gridline-color: #111b30; }}
QTableWidget::item:selected {{ background: rgba(0, 229, 255, 0.18); }}

QProgressBar {{ background: rgba(255,255,255,0.06); border: none; border-radius: 3px; max-height: 6px; min-height: 6px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {C['cyan']}; border-radius: 3px; }}
QProgressBar[level="warn"]::chunk {{ background: {C['warn']}; }}
QProgressBar[level="high"]::chunk {{ background: {C['err']}; }}
QProgressBar[level="na"]::chunk {{ background: transparent; }}

QSlider::groove:horizontal {{ height: 4px; background: #1a2a47; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {C['cyan']}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QSlider::sub-page:horizontal {{ background: {C['blue']}; border-radius: 2px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border: 1px solid {C['border']}; border-radius: 4px; background: rgba(6,11,22,0.9); }}
QCheckBox::indicator:checked {{ background: {C['cyan']}; border-color: {C['cyan']}; }}
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #223556; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: {C['cyan']}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ height: 8px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: #223556; border-radius: 4px; }}
"""


def level_color(level: str) -> str:
    return {"good": C["ok"], "warn": C["warn"], "high": C["err"], "na": C["dim"]}.get(level, C["muted"])


def soft_wrap(text: str, width: int = 40) -> str:
    """Juda uzun (bo'shliqsiz) so'zlarni ko'rinmas bo'shliq bilan bo'ladi, shunda xabar maketni buzmaydi."""
    out = []
    for word in text.split(" "):
        if len(word) > width:
            word = "​".join(word[i:i + width] for i in range(0, len(word), width))
        out.append(word)
    return " ".join(out)
