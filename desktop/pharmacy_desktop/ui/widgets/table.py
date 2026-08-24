"""A table that formats itself.

Screens describe their columns once — key, heading, kind — and hand over rows
of raw data (sqlite rows or dictionaries). Money arrives as paisa and is shown
right-aligned with two decimals; dates arrive as ``YYYY-MM-DD`` and are shown
the way people read them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from ...core import dates
from ...core.money import fmt
from .. import theme

TEXT, MONEY, INT, DATE, DATETIME, PERCENT, BOOL = (
    "text",
    "money",
    "int",
    "date",
    "datetime",
    "percent",
    "bool",
)


@dataclass
class Col:
    key: str
    label: str
    kind: str = TEXT
    width: int | None = None
    stretch: bool = False
    tooltip: str = ""


def format_value(value: Any, kind: str) -> str:
    if value is None or value == "":
        return "—" if kind in (DATE, DATETIME) else ""
    if kind == MONEY:
        return fmt(int(value))
    if kind == INT:
        return f"{int(value):,}"
    if kind == PERCENT:
        return f"{float(value):.2f}%"
    if kind == DATE:
        return dates.fmt_date(value, "—")
    if kind == DATETIME:
        return dates.fmt_datetime(value, "—")
    if kind == BOOL:
        return "Yes" if value else "No"
    return str(value)


class DataTable(QTableWidget):
    """Read-only grid with typed columns and one row object per line."""

    rowActivated = Signal(object)
    rowSelected = Signal(object)

    def __init__(self, columns: Sequence[Col], parent=None, *, row_height: int = 34):
        super().__init__(0, len(columns), parent)
        self.columns = list(columns)
        self._rows: list[Any] = []
        self.row_style: Callable[[Any], str] | None = None
        self.setHorizontalHeaderLabels([column.label for column in self.columns])
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(row_height)
        self.setSortingEnabled(False)
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setMinimumSectionSize(56)
        self._stretch_index: int | None = None
        self._stretch_minimum = 140
        for index, column in enumerate(self.columns):
            if column.stretch:
                # Not QHeaderView.Stretch: with several auto-sized columns beside it
                # Qt squeezes the stretch column down to nothing, and the name of the
                # medicine is the one column that must stay readable.
                self._stretch_index = index
                self._stretch_minimum = column.width or 160
                header.setSectionResizeMode(index, QHeaderView.Interactive)
                self.setColumnWidth(index, self._stretch_minimum)
            elif column.width:
                header.setSectionResizeMode(index, QHeaderView.Interactive)
                self.setColumnWidth(index, column.width)
            else:
                header.setSectionResizeMode(index, QHeaderView.ResizeToContents)
            if column.tooltip:
                item = self.horizontalHeaderItem(index)
                if item:
                    item.setToolTip(column.tooltip)
        if self._stretch_index is None:
            header.setStretchLastSection(True)
        self.itemDoubleClicked.connect(self._emit_activated)
        self.itemSelectionChanged.connect(self._emit_selected)

    # ------------------------------------------------------------------ data
    def set_rows(self, rows: Sequence[Mapping | Any]) -> None:
        previous = self.currentRow()
        self.setUpdatesEnabled(False)
        self.clearContents()
        self._rows = list(rows)
        self.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            tone = self.row_style(row) if self.row_style else ""
            for column_index, column in enumerate(self.columns):
                value = _get(row, column.key)
                item = QTableWidgetItem(format_value(value, column.kind))
                if column.kind in (MONEY, INT, PERCENT):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                elif column.kind in (DATE, DATETIME):
                    item.setTextAlignment(Qt.AlignCenter)
                else:
                    item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                if column.kind == MONEY and value is not None and int(value or 0) < 0:
                    item.setForeground(QBrush(QColor(theme.DANGER)))
                if tone:
                    _apply_tone(item, tone)
                self.setItem(row_index, column_index, item)
        self.setUpdatesEnabled(True)
        self._fit_stretch_column()
        if 0 <= previous < self.rowCount():
            self.selectRow(previous)
        elif self._rows:
            self.selectRow(0)

    # ------------------------------------------------------------------ layout
    def _fit_stretch_column(self) -> None:
        """Hand whatever width is left over to the stretch column."""
        index = self._stretch_index
        if index is None:
            return
        header = self.horizontalHeader()
        others = sum(
            header.sectionSize(position)
            for position in range(self.columnCount())
            if position != index
        )
        available = self.viewport().width() - others
        self.setColumnWidth(index, max(self._stretch_minimum, available))

    def resizeEvent(self, event):  # noqa: N802 - Qt naming
        super().resizeEvent(event)
        self._fit_stretch_column()

    def rows(self) -> list[Any]:
        return list(self._rows)

    def current(self) -> Any | None:
        index = self.currentRow()
        if 0 <= index < len(self._rows):
            return self._rows[index]
        return None

    def select_first(self) -> None:
        if self.rowCount():
            self.selectRow(0)

    def _emit_activated(self, *_args) -> None:
        current = self.current()
        if current is not None:
            self.rowActivated.emit(current)

    def _emit_selected(self) -> None:
        current = self.current()
        if current is not None:
            self.rowSelected.emit(current)

    def keyPressEvent(self, event):  # noqa: N802 - Qt naming
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self._emit_activated()
            return
        super().keyPressEvent(event)


def _get(row: Any, key: str) -> Any:
    if isinstance(row, Mapping):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return getattr(row, key, None)


def _apply_tone(item: QTableWidgetItem, tone: str) -> None:
    if tone == "danger":
        item.setForeground(QBrush(QColor(theme.DANGER)))
    elif tone == "warning":
        item.setForeground(QBrush(QColor("#8A5A00")))
    elif tone == "muted":
        item.setForeground(QBrush(QColor(theme.MUTED)))
    elif tone == "bold":
        font = item.font()
        font.setWeight(QFont.DemiBold)
        item.setFont(font)
