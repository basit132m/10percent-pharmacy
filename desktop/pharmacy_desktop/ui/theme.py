"""Look and feel.

Colours follow the pharmacy's own signboard — bottle green with a gold accent.
Everything is deliberately large: this software is used standing up, in a hurry,
often by someone who is not a computer person.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

GREEN = "#0F6B4F"
GREEN_DARK = "#0A503B"
GREEN_LIGHT = "#E7F3EE"
GOLD = "#C89211"
GOLD_LIGHT = "#FBF3DF"
INK = "#1B2733"
MUTED = "#66788A"
LINE = "#D8E0E8"
CANVAS = "#F2F5F7"
SURFACE = "#FFFFFF"
DANGER = "#C0392B"
DANGER_LIGHT = "#FDECEA"
WARNING = "#E08A0B"
WARNING_LIGHT = "#FDF3E2"
SUCCESS = "#1E8E3E"
INFO = "#1B6FB5"

STATUS_COLOURS = {
    "ok": QColor(SUCCESS),
    "warning": QColor(WARNING),
    "danger": QColor(DANGER),
    "muted": QColor(MUTED),
}


def preferred_font() -> QFont:
    families = set(QFontDatabase.families())
    for name in ("Segoe UI", "Noto Sans", "DejaVu Sans", "Arial"):
        if name in families:
            return QFont(name, 10)
    return QFont(QApplication.font().family(), 10)


STYLESHEET = f"""
* {{ outline: none; }}

QWidget {{
    color: {INK};
    font-size: 14px;
}}

QMainWindow, QDialog {{ background: {CANVAS}; }}

/* ------------------------------------------------------------- side bar */
#Sidebar {{
    background: {GREEN_DARK};
    border: none;
}}
#SidebarBrand {{
    color: #FFFFFF;
    font-size: 17px;
    font-weight: 700;
    padding: 18px 16px 2px 16px;
}}
#SidebarTagline {{
    color: {GOLD};
    font-size: 12px;
    font-weight: 600;
    padding: 0 16px 14px 16px;
}}
#SidebarFooter {{
    color: #9CC4B5;
    font-size: 11px;
    padding: 10px 16px;
}}
QPushButton#NavButton {{
    background: transparent;
    border: none;
    border-left: 4px solid transparent;
    color: #D8E9E2;
    font-size: 15px;
    padding: 11px 14px;
    text-align: left;
}}
QPushButton#NavButton:hover {{ background: rgba(255, 255, 255, 0.08); color: #FFFFFF; }}
QPushButton#NavButton:checked {{
    background: rgba(255, 255, 255, 0.14);
    border-left: 4px solid {GOLD};
    color: #FFFFFF;
    font-weight: 600;
}}

/* -------------------------------------------------------------- header */
#PageHeader {{ background: {SURFACE}; border-bottom: 1px solid {LINE}; }}
#PageTitle {{ font-size: 20px; font-weight: 700; }}
#PageSubtitle {{ color: {MUTED}; font-size: 13px; }}

/* --------------------------------------------------------------- cards */
QFrame#Card {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 10px;
}}
QLabel#CardTitle {{ color: {MUTED}; font-size: 12px; font-weight: 600; }}
QLabel#CardValue {{ font-size: 26px; font-weight: 700; }}
QLabel#CardHint {{ color: {MUTED}; font-size: 12px; }}
QLabel#SectionTitle {{ font-size: 15px; font-weight: 700; padding: 2px 0; }}
QLabel#Muted {{ color: {MUTED}; }}

/* ------------------------------------------------------------- buttons */
QPushButton {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 14px;
}}
QPushButton:hover {{ border-color: {GREEN}; color: {GREEN_DARK}; }}
QPushButton:pressed {{ background: {GREEN_LIGHT}; }}
QPushButton:disabled {{ color: #A7B4C0; background: #F3F5F7; border-color: {LINE}; }}
QPushButton#Primary {{
    background: {GREEN}; border-color: {GREEN}; color: #FFFFFF; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {GREEN_DARK}; border-color: {GREEN_DARK};
                             color: #FFFFFF; }}
QPushButton#Accent {{
    background: {GOLD}; border-color: {GOLD}; color: #23303C; font-weight: 700;
}}
QPushButton#Accent:hover {{ background: #B07F0C; color: #FFFFFF; }}
QPushButton#Danger {{ color: {DANGER}; border-color: #E9B7B1; }}
QPushButton#Danger:hover {{ background: {DANGER_LIGHT}; border-color: {DANGER};
                            color: {DANGER}; }}
QPushButton#Big {{ font-size: 16px; padding: 13px 20px; }}
QPushButton#Link {{ border: none; color: {INFO}; padding: 4px; text-decoration: underline; }}

/* --------------------------------------------------------------- input */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QPlainTextEdit, QTextEdit {{
    background: {SURFACE};
    border: 1px solid {LINE};
    border-radius: 6px;
    padding: 7px 9px;
    selection-background-color: {GREEN};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus,
QPlainTextEdit:focus, QTextEdit:focus {{ border: 2px solid {GREEN}; padding: 6px 8px; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ background: #F3F5F7;
                                                             color: {MUTED}; }}
QLineEdit#SearchBox {{ font-size: 16px; padding: 11px 12px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE}; border: 1px solid {LINE};
    selection-background-color: {GREEN_LIGHT}; selection-color: {INK};
}}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 17px; height: 17px; }}

/* -------------------------------------------------------------- tables */
QTableWidget, QTableView {{
    background: {SURFACE};
    alternate-background-color: #F8FAFB;
    border: 1px solid {LINE};
    border-radius: 8px;
    gridline-color: #EDF1F4;
    selection-background-color: {GREEN_LIGHT};
    selection-color: {INK};
}}
QTableWidget::item, QTableView::item {{ padding: 7px 6px; }}
QHeaderView::section {{
    background: #EEF2F5;
    border: none;
    border-right: 1px solid #E1E7EC;
    border-bottom: 1px solid {LINE};
    color: {MUTED};
    font-weight: 700;
    font-size: 12px;
    padding: 9px 6px;
}}
QTableCornerButton::section {{ background: #EEF2F5; border: none; }}

/* --------------------------------------------------------------- misc */
QTabWidget::pane {{ border: 1px solid {LINE}; border-radius: 8px; background: {SURFACE};
                    top: -1px; }}
QTabBar::tab {{
    background: transparent; border: 1px solid transparent; border-bottom: none;
    color: {MUTED}; font-weight: 600; padding: 9px 18px; margin-right: 2px;
}}
QTabBar::tab:selected {{
    background: {SURFACE}; border-color: {LINE}; border-top-left-radius: 8px;
    border-top-right-radius: 8px; color: {GREEN_DARK};
}}
QListWidget {{
    background: {SURFACE}; border: 1px solid {LINE}; border-radius: 8px; padding: 4px;
}}
QListWidget::item {{ padding: 8px 10px; border-radius: 6px; }}
QListWidget::item:hover {{ background: {GREEN_LIGHT}; }}
QListWidget::item:selected {{ background: {GREEN}; color: #FFFFFF; font-weight: 600; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #C4CED8; border-radius: 6px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #A9B6C2; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #C4CED8; border-radius: 6px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QStatusBar {{ background: {SURFACE}; border-top: 1px solid {LINE}; color: {MUTED}; }}
QToolTip {{ background: {INK}; color: #FFFFFF; border: none; padding: 6px 8px; }}
QSplitter::handle {{ background: transparent; }}
QGroupBox {{
    border: 1px solid {LINE}; border-radius: 8px; margin-top: 14px;
    padding: 14px 12px 10px 12px; font-weight: 600; background: {SURFACE};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {MUTED}; }}
QProgressBar {{ border: 1px solid {LINE}; border-radius: 6px; text-align: center;
                background: {SURFACE}; }}
QProgressBar::chunk {{ background: {GREEN}; border-radius: 5px; }}
"""


def apply(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(preferred_font())
    app.setStyleSheet(STYLESHEET)
