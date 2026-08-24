"""Reports — one screen that runs every report, prints it or exports it."""

from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QListWidget

from ...core import config, dates
from ...core.money import fmt
from ...core.services import reports as report_module
from .. import printing, theme
from ..widgets.common import Card, DateEdit, MutedLabel, SectionTitle, button, info, warn
from ..widgets.table import Col, DataTable
from .base import Page

KIND_MAP = {
    report_module.MONEY: "money",
    report_module.INT: "int",
    report_module.PERCENT: "percent",
    report_module.DATE: "date",
    report_module.DATETIME: "datetime",
    report_module.TEXT: "text",
}

QUICK_RANGES = [
    ("Today", "today"),
    ("Yesterday", "yesterday"),
    ("This week", "week"),
    ("This month", "month"),
    ("Last month", "last_month"),
    ("Last 30 days", "last30"),
    ("This year", "year"),
]


class ReportsPage(Page):
    title = "Reports"
    subtitle = "Sales, profit, stock and money owed"

    def build(self) -> None:
        self.header.add_action(button("Print", on_click=self._print))
        self.header.add_action(button("Export to CSV", kind="Primary", on_click=self._export))

        split = QHBoxLayout()
        split.setSpacing(12)

        chooser = Card()
        chooser.body.addWidget(SectionTitle("Choose a report"))
        self.list = QListWidget()
        self.list.setMaximumWidth(280)
        self.reports = self.context.reports.available()
        for _key, label, _needs_dates in self.reports:
            self.list.addItem(label)
        self.list.setCurrentRow(0)
        self.list.currentRowChanged.connect(lambda _i: self.reload())
        chooser.body.addWidget(self.list, 1)
        split.addWidget(chooser, 2)

        result = Card()
        controls = QHBoxLayout()
        self.range_picker = QComboBox()
        for label, value in QUICK_RANGES:
            self.range_picker.addItem(label, value)
        self.range_picker.setCurrentIndex(3)
        self.range_picker.currentIndexChanged.connect(self._apply_quick_range)
        controls.addWidget(MutedLabel("Period"))
        controls.addWidget(self.range_picker)
        self.date_from = DateEdit(dates.month_start())
        self.date_to = DateEdit()
        for widget in (self.date_from, self.date_to):
            widget.dateChanged.connect(lambda _d: self.reload())
        controls.addWidget(MutedLabel("From"))
        controls.addWidget(self.date_from)
        controls.addWidget(MutedLabel("to"))
        controls.addWidget(self.date_to)
        controls.addStretch(1)
        result.body.addLayout(controls)

        self.result_title = SectionTitle("")
        result.body.addWidget(self.result_title)
        self.result_subtitle = MutedLabel("")
        result.body.addWidget(self.result_subtitle)

        self.table = DataTable([Col("placeholder", "")])
        result.body.addWidget(self.table, 1)
        self.totals_label = MutedLabel("")
        self.totals_label.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {theme.GREEN_DARK}; padding: 4px;"
        )
        result.body.addWidget(self.totals_label)
        split.addWidget(result, 8)
        self.body.addLayout(split, 1)
        self.current_report = None

    def _apply_quick_range(self) -> None:
        start, end = dates.date_range(self.range_picker.currentData())
        self.date_from.blockSignals(True)
        self.date_to.blockSignals(True)
        self.date_from.set_iso(start)
        self.date_to.set_iso(end)
        self.date_from.blockSignals(False)
        self.date_to.blockSignals(False)
        self.reload()

    # ---------------------------------------------------------------- reload
    def reload(self) -> None:
        index = max(self.list.currentRow(), 0)
        key, _label, needs_dates = self.reports[index]
        for widget in (self.date_from, self.date_to, self.range_picker):
            widget.setEnabled(needs_dates)
        report = self.context.reports.run(key, self.date_from.iso(), self.date_to.iso())
        self.current_report = report
        self.result_title.setText(report.title)
        self.result_subtitle.setText(report.subtitle)

        stretch_at = next(
            (
                position
                for position, column in enumerate(report.columns)
                if column.kind == report_module.TEXT
            ),
            None,
        )
        columns = [
            Col(
                column.key,
                column.label,
                KIND_MAP.get(column.kind, "text"),
                stretch=(position == stretch_at),
            )
            for position, column in enumerate(report.columns)
        ]
        parent_layout = self.table.parentWidget().layout()
        old = self.table
        self.table = DataTable(columns)
        parent_layout.replaceWidget(old, self.table)
        old.deleteLater()
        self.table.set_rows(report.rows)

        if report.totals:
            parts = []
            for column in report.columns:
                value = report.totals.get(column.key)
                if value in (None, ""):
                    continue
                if column.kind == report_module.MONEY:
                    parts.append(f"{column.label}: {fmt(int(value), symbol=True)}")
                elif column.kind == report_module.PERCENT:
                    parts.append(f"{column.label}: {float(value):.2f}%")
                elif column.kind == report_module.INT:
                    parts.append(f"{column.label}: {int(value):,}")
                else:
                    parts.append(str(value))
            self.totals_label.setText("   ·   ".join(parts))
        else:
            self.totals_label.setText(f"{len(report.rows)} row(s)")

    # --------------------------------------------------------------- output
    def _export(self) -> None:
        if self.current_report is None:
            return
        if not self.current_report.rows:
            warn(self, "There is nothing in this report to export.")
            return
        suggested = self.current_report.title.lower().replace(" ", "-").replace("/", "-")
        path, _filter = QFileDialog.getSaveFileName(
            self,
            "Save report",
            str(config.export_dir() / f"{suggested}.csv"),
            "Spreadsheet (*.csv)",
        )
        if not path:
            return
        self.current_report.export_csv(path)
        info(self, f"Saved to:\n{path}\n\nThis file opens in Excel.")

    def _print(self) -> None:
        if self.current_report is None:
            return
        printing.preview_html(
            self,
            printing.report_html(self.context.settings, self.current_report),
            page_format=printing.A4,
        )
