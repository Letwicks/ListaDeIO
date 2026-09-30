"""Tema visual do app, com a paleta da Autolinx Automação (https://autolinx.me).

Mesma identidade usada nas outras ferramentas da Autolinx (navy/azul/verde).
"""
from __future__ import annotations

NAVY = "#0a3b6d"
BLUE = "#1a73e8"
BLUE_MID = "#0d4f8e"
GREEN = "#00a544"
BG = "#f4f6f8"
CARD = "#ffffff"
TEXT = "#1a202c"
MUTED = "#6a7282"
BORDER = "#d1d5dc"

QSS = f"""
* {{
    font-size: 10pt;
}}
QMainWindow, QDialog, QWidget {{
    background: {BG};
    color: {TEXT};
}}
QLabel {{
    background: transparent;
}}

#brandHeader {{
    background: {NAVY};
    border-bottom: 2px solid {GREEN};
}}
#brandName {{
    color: #ffffff;
    font-size: 12pt;
    font-weight: 600;
}}
#brandTagline {{
    color: #9fc0e4;
}}

QGroupBox {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 8px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: {NAVY};
}}

QPushButton {{
    background: {CARD};
    color: {NAVY};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton:hover {{
    border-color: {BLUE};
    color: {BLUE_MID};
}}
QPushButton:pressed {{
    background: #eef4fb;
}}
QPushButton:disabled {{
    color: #9aa3af;
    border-color: #e5e7eb;
    background: #f3f4f6;
}}
QPushButton[accent="true"] {{
    background: {BLUE};
    color: #ffffff;
    border: 1px solid {BLUE};
    font-weight: 600;
}}
QPushButton[accent="true"]:hover {{
    background: {BLUE_MID};
    border-color: {BLUE_MID};
    color: #ffffff;
}}
QPushButton[accent="true"]:pressed {{
    background: {NAVY};
    border-color: {NAVY};
}}
QPushButton[accent="true"]:disabled {{
    background: #b9c4d4;
    border-color: #b9c4d4;
    color: #eef2f7;
}}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 4px 6px;
    selection-background-color: {BLUE};
    selection-color: #ffffff;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
QDoubleSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {BLUE};
}}

QTableWidget {{
    background: {CARD};
    alternate-background-color: {BG};
    gridline-color: #e5e7eb;
    border: 1px solid {BORDER};
    border-radius: 6px;
    selection-background-color: #dbeafe;
    selection-color: {TEXT};
}}
QHeaderView::section {{
    background: {NAVY};
    color: #ffffff;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {BLUE_MID};
    font-weight: 600;
}}
QTableWidget QTableCornerButton::section {{
    background: {NAVY};
    border: none;
}}

QMenuBar {{
    background: {NAVY};
    color: #ffffff;
}}
QMenuBar::item {{
    background: transparent;
    padding: 6px 10px;
}}
QMenuBar::item:selected {{
    background: {BLUE_MID};
}}
QMenu {{
    background: {CARD};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background: #dbeafe;
    color: {NAVY};
}}
QStatusBar {{
    background: {CARD};
    color: {MUTED};
    border-top: 1px solid {BORDER};
}}
QCheckBox {{
    spacing: 6px;
}}
"""


def apply_theme(app) -> None:
    """Aplica a base Fusion + o QSS da Autolinx à ``QApplication``."""
    try:
        app.setStyle("Fusion")
    except Exception:  # noqa: BLE001 - estilo é opcional
        pass
    app.setStyleSheet(QSS)
