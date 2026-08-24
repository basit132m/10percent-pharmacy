"""Shared page scaffolding: a header bar, a body, and refresh bookkeeping."""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from ..widgets.common import HeaderBar


class Page(QWidget):
    title = "Page"
    subtitle = ""

    def __init__(self, context, window=None):
        super().__init__()
        self.context = context
        self.window_ref = window
        self._stale = True
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = HeaderBar(self.title, self.subtitle)
        outer.addWidget(self.header)
        self.body = QVBoxLayout()
        self.body.setContentsMargins(18, 14, 18, 14)
        self.body.setSpacing(12)
        container = QWidget()
        container.setLayout(self.body)
        outer.addWidget(container, 1)
        self.build()

    # Subclasses override these two.
    def build(self) -> None:  # pragma: no cover - trivial
        ...

    def reload(self) -> None:  # pragma: no cover - trivial
        ...

    # ------------------------------------------------------------- plumbing
    def mark_stale(self) -> None:
        self._stale = True

    def refresh(self, *, force: bool = False) -> None:
        if force or self._stale or self.isVisible():
            self.reload()
            self._stale = False

    def notify_change(self) -> None:
        """Tell every other screen that the numbers behind it just moved."""
        if self.window_ref is not None:
            self.window_ref.refresh_all()
        else:  # pragma: no cover - only when a page is used stand-alone
            self.reload()

    @property
    def user(self):
        return self.context.auth.current_user

    def can(self, permission: str) -> bool:
        user = self.user
        return bool(user and user.can(permission))
