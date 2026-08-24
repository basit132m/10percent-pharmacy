"""Users — staff accounts, their roles, and the audit trail."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ...core.errors import PharmacyError
from ...core.services.auth import ROLE_LABELS, ROLES
from ..widgets.common import (
    MutedLabel,
    SearchBox,
    button,
    confirm,
    error,
    info,
    warn,
)
from ..widgets.table import BOOL, Col, DataTable, DATETIME
from .base import Page


class UsersPage(Page):
    title = "Users"
    subtitle = "Who may sign in, and what they may do"

    def build(self) -> None:
        self.header.add_action(button("Add user", kind="Primary", on_click=self._add))

        self.tabs = QTabWidget()
        self.tabs.addTab(self._users_tab(), "Staff accounts")
        self.tabs.addTab(self._audit_tab(), "Activity log")
        self.tabs.currentChanged.connect(lambda _i: self.reload())
        self.body.addWidget(self.tabs, 1)

    def _users_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 12, 10, 10)
        self.table = DataTable(
            [
                Col("username", "Username"),
                Col("full_name", "Full name", stretch=True),
                Col("role_label", "Role"),
                Col("is_active", "Can sign in", BOOL),
                Col("must_change_password", "Must change password", BOOL),
                Col("last_login_at", "Last signed in", DATETIME),
                Col("created_at", "Added", DATETIME),
            ]
        )
        self.table.row_style = lambda row: "" if row["is_active"] else "muted"
        self.table.rowActivated.connect(lambda _row: self._edit())
        layout.addWidget(self.table, 1)

        tools = QHBoxLayout()
        tools.addWidget(
            MutedLabel(
                "Owner sees everything · Manager: stock, purchases, reports, returns · "
                "Cashier: the counter screen only."
            )
        )
        tools.addStretch(1)
        tools.addWidget(button("Edit", on_click=self._edit))
        tools.addWidget(button("Reset password…", on_click=self._reset_password))
        tools.addWidget(button("Enable / disable", on_click=self._toggle))
        layout.addLayout(tools)
        return page

    def _audit_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(10, 12, 10, 10)
        self.audit_search = SearchBox("Search the activity log…")
        self.audit_search.textChanged.connect(lambda _t: self._reload_audit())
        layout.addWidget(self.audit_search)
        self.audit_table = DataTable(
            [
                Col("created_at", "When", DATETIME),
                Col("username", "Who"),
                Col("action", "What"),
                Col("entity", "On"),
                Col("details", "Detail", stretch=True),
            ]
        )
        layout.addWidget(self.audit_table, 1)
        layout.addWidget(
            MutedLabel(
                "Every sale, price change, stock adjustment and sign-in is recorded here "
                "and kept for good."
            )
        )
        return page

    # ---------------------------------------------------------------- reload
    def reload(self) -> None:
        if self.tabs.currentIndex() == 1:
            self._reload_audit()
            return
        rows = []
        for row in self.context.auth.list_users():
            entry = dict(row)
            entry["role_label"] = ROLE_LABELS.get(row["role"], row["role"])
            rows.append(entry)
        self.table.set_rows(rows)

    def _reload_audit(self) -> None:
        self.audit_table.set_rows(self.context.audit.recent(search=self.audit_search.text()))

    # --------------------------------------------------------------- actions
    def _selected(self):
        row = self.table.current()
        if row is None:
            warn(self, "Choose a user from the list first.")
        return row

    def _add(self) -> None:
        if UserDialog(self.context, parent=self).exec() == QDialog.Accepted:
            self.reload()

    def _edit(self) -> None:
        row = self._selected()
        if row is None:
            return
        if UserDialog(self.context, row, parent=self).exec() == QDialog.Accepted:
            self.reload()

    def _reset_password(self) -> None:
        row = self._selected()
        if row is None:
            return
        dialog = ResetPasswordDialog(self.context, row, self)
        if dialog.exec() == QDialog.Accepted:
            info(
                self,
                f"The password for {row['username']} has been set. They will be asked to "
                "choose their own password the next time they sign in.",
            )

    def _toggle(self) -> None:
        row = self._selected()
        if row is None:
            return
        active = not row["is_active"]
        if not active and not confirm(
            self, f"Stop {row['username']} from signing in?", danger=True
        ):
            return
        try:
            self.context.auth.set_active(int(row["id"]), active)
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.reload()


class UserDialog(QDialog):
    def __init__(self, context, row=None, parent=None):
        super().__init__(parent)
        self.context = context
        self.row = row
        self.setWindowTitle(row["username"] if row is not None else "New user")
        self.setMinimumWidth(440)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(9)
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.role = QComboBox()
        for role in ROLES:
            self.role.addItem(ROLE_LABELS[role], role)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        form.addRow("Username", self.username)
        form.addRow("Full name", self.full_name)
        form.addRow("Role", self.role)
        if row is None:
            form.addRow("First password", self.password)
        box.addLayout(form)
        box.addWidget(
            MutedLabel(
                "The user will be asked to change this password the first time they sign in."
                if row is None
                else "Use “Reset password…” on the list to give this user a new password."
            )
        )
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Save", kind="Primary", on_click=self._save))
        box.addLayout(buttons)

        if row is not None:
            self.username.setText(row["username"])
            self.username.setEnabled(False)
            self.full_name.setText(row["full_name"])
            index = self.role.findData(row["role"])
            if index >= 0:
                self.role.setCurrentIndex(index)

    def _save(self) -> None:
        try:
            if self.row is None:
                self.context.auth.create_user(
                    self.username.text(),
                    self.full_name.text(),
                    self.password.text(),
                    self.role.currentData(),
                )
            else:
                self.context.auth.update_user(
                    int(self.row["id"]),
                    full_name=self.full_name.text(),
                    role=self.role.currentData(),
                )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()


class ResetPasswordDialog(QDialog):
    def __init__(self, context, row, parent=None):
        super().__init__(parent)
        self.context = context
        self.row = row
        self.setWindowTitle(f"Reset password — {row['username']}")
        self.setMinimumWidth(400)
        box = QVBoxLayout(self)
        box.setSpacing(12)
        form = QFormLayout()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        form.addRow("New password", self.password)
        form.addRow("Repeat password", self.confirm)
        box.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Set password", kind="Primary", on_click=self._save))
        box.addLayout(buttons)

    def _save(self) -> None:
        if self.password.text() != self.confirm.text():
            error(self, "The two passwords do not match.")
            return
        try:
            self.context.auth.set_password(
                int(self.row["id"]), self.password.text(), force_change=True
            )
        except PharmacyError as exc:
            error(self, str(exc))
            return
        self.accept()
