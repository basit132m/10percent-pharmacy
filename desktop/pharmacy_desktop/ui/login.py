"""Sign-in window, and the forced password change that follows a first login."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..core import config
from ..core.errors import PharmacyError
from . import theme
from .widgets.common import MutedLabel, button, error, info


class LoginDialog(QDialog):
    def __init__(self, context, parent=None):
        super().__init__(parent)
        self.context = context
        self.user = None
        self.setWindowTitle(f"{APP_NAME} — Sign in")
        self.setMinimumWidth(760)
        self.setModal(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._banner(), 1)
        layout.addWidget(self._form(), 1)

    # ------------------------------------------------------------------ parts
    def _banner(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(
            f"background: {theme.GREEN_DARK};"
        )
        box = QVBoxLayout(panel)
        box.setContentsMargins(34, 40, 34, 30)
        box.setSpacing(10)

        logo_path = config.resource_path("pharmacy-logo.png")
        if logo_path.exists():
            picture = QLabel()
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                picture.setPixmap(
                    pixmap.scaledToWidth(190, Qt.SmoothTransformation)
                )
            picture.setAlignment(Qt.AlignCenter)
            box.addWidget(picture)

        name = QLabel(self.context.settings.get("pharmacy_name"))
        name.setWordWrap(True)
        name.setStyleSheet("color: #FFFFFF; font-size: 24px; font-weight: 700;")
        tagline = QLabel(self.context.settings.get("pharmacy_tagline"))
        tagline.setWordWrap(True)
        tagline.setStyleSheet(f"color: {theme.GOLD}; font-size: 15px; font-weight: 600;")
        blurb = QLabel(
            "Counter sales · stock and expiry · purchases · customer credit · "
            "daily reports — all on this computer, no internet needed."
        )
        blurb.setWordWrap(True)
        blurb.setStyleSheet("color: #B9D6CB; font-size: 13px;")
        box.addStretch(1)
        box.addWidget(name)
        box.addWidget(tagline)
        box.addSpacing(8)
        box.addWidget(blurb)
        box.addStretch(2)
        version = QLabel(f"Version {__version__}")
        version.setStyleSheet("color: #7FA99B; font-size: 11px;")
        box.addWidget(version)
        return panel

    def _form(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet(f"background: {theme.SURFACE};")
        box = QVBoxLayout(panel)
        box.setContentsMargins(38, 44, 38, 34)
        box.setSpacing(14)

        title = QLabel("Sign in")
        title.setStyleSheet("font-size: 22px; font-weight: 700;")
        box.addWidget(title)
        box.addWidget(MutedLabel("Use the username the owner gave you."))

        form = QFormLayout()
        form.setSpacing(10)
        self.username = QLineEdit()
        self.username.setPlaceholderText("e.g. admin")
        self.username.setMinimumHeight(40)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("Password")
        self.password.setMinimumHeight(40)
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        box.addLayout(form)

        self.message = QLabel("")
        self.message.setWordWrap(True)
        self.message.setStyleSheet(f"color: {theme.DANGER}; font-weight: 600;")
        box.addWidget(self.message)

        sign_in = button("Sign in", kind="Primary", big=True, on_click=self._attempt)
        sign_in.setDefault(True)
        box.addWidget(sign_in)
        box.addWidget(button("Close", on_click=self.reject))
        box.addStretch(1)

        if self.context.db.scalar("SELECT COUNT(*) FROM users") == 1:
            hint = MutedLabel(
                "First time here? Sign in as <b>admin</b> with the password "
                "<b>admin123</b> — you will be asked to set your own password."
            )
            hint.setTextFormat(Qt.RichText)
            hint.setStyleSheet(
                f"background: {theme.GOLD_LIGHT}; border-radius: 8px; padding: 10px; "
                f"color: #6B4E05;"
            )
            box.addWidget(hint)
            self.username.setText("admin")
            self.password.setFocus()
        else:
            self.username.setFocus()

        self.username.returnPressed.connect(self.password.setFocus)
        self.password.returnPressed.connect(self._attempt)
        return panel

    # ----------------------------------------------------------------- action
    def _attempt(self) -> None:
        try:
            user = self.context.auth.login(self.username.text(), self.password.text())
        except PharmacyError as exc:
            self.message.setText(str(exc))
            self.password.selectAll()
            self.password.setFocus()
            return
        if user.must_change_password and not self._force_new_password():
            self.context.auth.logout()
            self.message.setText("You must set a new password before you can continue.")
            return
        self.user = self.context.auth.current_user
        self.accept()

    def _force_new_password(self) -> bool:
        dialog = ChangePasswordDialog(self.context, self, first_run=True)
        return dialog.exec() == QDialog.Accepted


class ChangePasswordDialog(QDialog):
    """Used both for the forced first change and from the user's own menu."""

    def __init__(self, context, parent=None, *, first_run: bool = False):
        super().__init__(parent)
        self.context = context
        self.first_run = first_run
        self.setWindowTitle("Change password")
        self.setMinimumWidth(420)
        box = QVBoxLayout(self)
        box.setContentsMargins(22, 20, 22, 18)
        box.setSpacing(12)

        heading = QLabel(
            "Set your own password" if first_run else "Change your password"
        )
        heading.setStyleSheet("font-size: 17px; font-weight: 700;")
        box.addWidget(heading)
        if first_run:
            box.addWidget(
                MutedLabel(
                    "This account still has the password it was created with. "
                    "Choose a new one that only you know."
                )
            )

        form = QFormLayout()
        form.setSpacing(9)
        self.current = QLineEdit()
        self.current.setEchoMode(QLineEdit.Password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.Password)
        self.confirm = QLineEdit()
        self.confirm.setEchoMode(QLineEdit.Password)
        form.addRow("Current password", self.current)
        form.addRow("New password", self.new_password)
        form.addRow("Repeat new password", self.confirm)
        box.addLayout(form)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        if not first_run:
            buttons.addWidget(button("Cancel", on_click=self.reject))
        buttons.addWidget(button("Save password", kind="Primary", on_click=self._save))
        box.addLayout(buttons)
        self.current.setFocus()

    def _save(self) -> None:
        if self.new_password.text() != self.confirm.text():
            error(self, "The two new passwords do not match.")
            return
        try:
            self.context.auth.change_own_password(self.current.text(), self.new_password.text())
        except PharmacyError as exc:
            error(self, str(exc))
            return
        info(self, "Your password has been changed.")
        self.accept()
