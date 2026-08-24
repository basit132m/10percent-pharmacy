"""Small building blocks every screen shares."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...core import dates
from ...core.money import fmt, to_paisa
from .. import theme


class Card(QFrame):
    """A white panel with a border — the unit every screen is built from."""

    def __init__(self, parent: QWidget | None = None, *, margins: int = 14, spacing: int = 10):
        super().__init__(parent)
        self.setObjectName("Card")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(margins, margins, margins, margins)
        self.body.setSpacing(spacing)


class KpiCard(Card):
    """A headline number for the dashboard, clickable when it leads somewhere."""

    clicked = Signal()

    def __init__(self, title: str, value: str = "—", hint: str = "", accent: str = theme.INK):
        super().__init__(margins=16, spacing=4)
        self._title = QLabel(title.upper())
        self._title.setObjectName("CardTitle")
        self._value = QLabel(value)
        self._value.setObjectName("CardValue")
        self._value.setStyleSheet(f"color: {accent};")
        self._hint = QLabel(hint)
        self._hint.setObjectName("CardHint")
        self._hint.setWordWrap(True)
        self.body.addWidget(self._title)
        self.body.addWidget(self._value)
        self.body.addWidget(self._hint)
        self.setMinimumWidth(190)

    def set_value(self, value: str, hint: str | None = None) -> None:
        self._value.setText(value)
        if hint is not None:
            self._hint.setText(hint)

    def set_accent(self, colour: str) -> None:
        self._value.setStyleSheet(f"color: {colour};")

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt naming
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class SectionTitle(QLabel):
    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("SectionTitle")


class MutedLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setObjectName("Muted")
        self.setWordWrap(True)


class SearchBox(QLineEdit):
    def __init__(self, placeholder: str = "Search…", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("SearchBox")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)


class MoneyEdit(QLineEdit):
    """A text box that only accepts an amount and hands it back in paisa."""

    def __init__(self, value: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignRight)
        self.setPlaceholderText("0.00")
        self.set_paisa(value)

    def set_paisa(self, value: int) -> None:
        self.setText(fmt(value, grouping=False) if value else "")

    def paisa(self) -> int:
        try:
            return to_paisa(self.text())
        except ValueError:
            return 0

    def focusInEvent(self, event):  # noqa: N802 - Qt naming
        super().focusInEvent(event)
        self.selectAll()


class DateEdit(QDateEdit):
    def __init__(self, value=None, parent: QWidget | None = None, *, allow_empty: bool = False):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("dd-MM-yyyy")
        self.setDate(QDate.currentDate())
        if value:
            self.set_iso(value)
        if allow_empty:
            self.setSpecialValueText(" — ")
            self.setMinimumDate(QDate(1900, 1, 1))

    def set_iso(self, value) -> None:
        parsed = dates.parse_date(value)
        if parsed:
            self.setDate(QDate(parsed.year, parsed.month, parsed.day))

    def iso(self) -> str:
        return self.date().toString("yyyy-MM-dd")


class Badge(QLabel):
    """A coloured status pill — expired, low stock, credit, and so on."""

    TONES = {
        "ok": (theme.SUCCESS, "#E7F5EC"),
        "warning": (theme.WARNING, theme.WARNING_LIGHT),
        "danger": (theme.DANGER, theme.DANGER_LIGHT),
        "info": (theme.INFO, "#E8F1FA"),
        "muted": (theme.MUTED, "#EEF2F5"),
        "gold": ("#8A6508", theme.GOLD_LIGHT),
    }

    def __init__(self, text: str = "", tone: str = "muted", parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        colour, background = self.TONES.get(tone, self.TONES["muted"])
        self.setStyleSheet(
            f"color: {colour}; background: {background}; border-radius: 9px; "
            "padding: 3px 10px; font-size: 12px; font-weight: 700;"
        )


class HeaderBar(QWidget):
    """The white strip at the top of every page: title, subtitle, actions."""

    def __init__(self, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("PageHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 12, 20, 12)
        layout.setSpacing(12)
        text = QVBoxLayout()
        text.setSpacing(1)
        self._title = QLabel(title)
        self._title.setObjectName("PageTitle")
        self._subtitle = QLabel(subtitle)
        self._subtitle.setObjectName("PageSubtitle")
        text.addWidget(self._title)
        text.addWidget(self._subtitle)
        layout.addLayout(text)
        layout.addStretch(1)
        self.actions = QHBoxLayout()
        self.actions.setSpacing(8)
        layout.addLayout(self.actions)

    def set_subtitle(self, text: str) -> None:
        self._subtitle.setText(text)

    def add_action(self, button: QWidget) -> QWidget:
        self.actions.addWidget(button)
        return button


def button(
    text: str,
    *,
    kind: str = "",
    tooltip: str = "",
    on_click=None,
    shortcut: str = "",
    big: bool = False,
) -> QPushButton:
    widget = QPushButton(text.replace("&", "&&"))
    if kind:
        widget.setObjectName(kind)
    if big:
        widget.setMinimumHeight(44)
        font = widget.font()
        font.setPointSizeF(font.pointSizeF() + 1.5)
        font.setWeight(QFont.DemiBold)
        widget.setFont(font)
    if tooltip or shortcut:
        widget.setToolTip(f"{tooltip} ({shortcut})" if tooltip and shortcut else tooltip or shortcut)
    if shortcut:
        widget.setShortcut(shortcut)
    if on_click:
        widget.clicked.connect(on_click)
    return widget


def combo(items: list[tuple[str, object]], parent: QWidget | None = None) -> QComboBox:
    widget = QComboBox(parent)
    for label, value in items:
        widget.addItem(label, value)
    return widget


def row(*widgets, spacing: int = 8, stretch_last: bool = False) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for index, widget in enumerate(widgets):
        if widget is None:
            layout.addStretch(1)
        elif isinstance(widget, str):
            layout.addWidget(QLabel(widget))
        else:
            layout.addWidget(widget, 1 if stretch_last and index == len(widgets) - 1 else 0)
    return container


def separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(f"color: {theme.LINE}; background: {theme.LINE}; max-height: 1px;")
    line.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return line


# ------------------------------------------------------------------ dialogs
def info(parent, text: str, title: str = "Ten Percent Discount Pharmacy") -> None:
    QMessageBox.information(parent, title, text)


def warn(parent, text: str, title: str = "Please check") -> None:
    QMessageBox.warning(parent, title, text)


def error(parent, text: str, title: str = "Could not do that") -> None:
    QMessageBox.critical(parent, title, text)


def confirm(parent, text: str, title: str = "Please confirm", *, danger: bool = False) -> bool:
    box = QMessageBox(parent)
    box.setWindowTitle(title)
    box.setText(text)
    box.setIcon(QMessageBox.Warning if danger else QMessageBox.Question)
    yes = box.addButton("Yes", QMessageBox.YesRole)
    box.addButton("No", QMessageBox.RejectRole)
    box.setDefaultButton(yes)
    box.exec()
    return box.clickedButton() is yes
