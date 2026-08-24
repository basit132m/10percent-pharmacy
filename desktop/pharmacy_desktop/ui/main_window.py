"""The main window: a sidebar of screens, a status bar, and global shortcuts."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..core import config, dates
from ..core.errors import PharmacyError
from .login import ChangePasswordDialog
from .pages.dashboard import DashboardPage
from .pages.parties import PartiesPage
from .pages.pos import PosPage
from .pages.products import ProductsPage
from .pages.purchases import PurchasesPage
from .pages.reports import ReportsPage
from .pages.sales_history import SalesHistoryPage
from .pages.settings_page import SettingsPage
from .pages.stock import StockPage
from .pages.users import UsersPage
from .widgets.common import confirm, error

# label, key, factory, permission, shortcut
PAGES = [
    ("Dashboard", "dashboard", DashboardPage, None, "F1"),
    ("Counter sale", "pos", PosPage, "pos.sell", "F2"),
    ("Medicines", "products", ProductsPage, "catalog.view", "F3"),
    ("Stock & expiry", "stock", StockPage, "stock.view", "F4"),
    ("Purchases", "purchases", PurchasesPage, "purchases.view", "F6"),
    ("Customers & suppliers", "parties", PartiesPage, "parties.view", "F7"),
    ("Sales & returns", "sales", SalesHistoryPage, "sales.history", "F8"),
    ("Reports", "reports", ReportsPage, "reports.view", "F9"),
    ("Users", "users", UsersPage, "users.manage", None),
    ("Settings", "settings", SettingsPage, "settings.manage", None),
]


class MainWindow(QMainWindow):
    def __init__(self, context):
        super().__init__()
        self.context = context
        self.pages: dict[str, QWidget] = {}
        self.setWindowTitle(f"{APP_NAME} — Management Software")
        self.resize(1360, 860)
        self.setMinimumSize(1120, 700)
        logo = config.resource_path("pharmacy-logo.png")
        if logo.exists():
            self.setWindowIcon(QIcon(QPixmap(str(logo))))

        body = QWidget()
        self.setCentralWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        shell = QWidget()
        from PySide6.QtWidgets import QHBoxLayout

        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.sidebar = self._build_sidebar()
        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(self.stack, 1)
        layout.addWidget(shell)

        self._build_status_bar()
        self._build_shortcuts()
        self.show_page("dashboard")
        QTimer.singleShot(400, self._show_startup_alerts)

    # ------------------------------------------------------------- side bar
    def _build_sidebar(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("Sidebar")
        panel.setFixedWidth(252)
        box = QVBoxLayout(panel)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)

        brand = QLabel(self.context.settings.get("pharmacy_name"))
        brand.setObjectName("SidebarBrand")
        brand.setWordWrap(True)
        tagline = QLabel(self.context.settings.get("pharmacy_tagline"))
        tagline.setObjectName("SidebarTagline")
        tagline.setWordWrap(True)
        box.addWidget(brand)
        box.addWidget(tagline)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        user = self.context.user
        for label, key, _factory, permission, shortcut in PAGES:
            if permission and user and not user.can(permission):
                continue
            item = QPushButton(f"{label}    {shortcut or ''}".rstrip().replace("&", "&&"))
            item.setObjectName("NavButton")
            item.setCheckable(True)
            item.setCursor(Qt.PointingHandCursor)
            item.setIconSize(QSize(18, 18))
            item.clicked.connect(lambda _checked=False, page=key: self.show_page(page))
            self.nav_group.addButton(item)
            self.nav_buttons[key] = item
            box.addWidget(item)

        box.addStretch(1)
        account = QPushButton(f"{user.full_name}  ▾" if user else "Account ▾")
        account.setObjectName("NavButton")
        account.setMenu(self._account_menu())
        box.addWidget(account)
        footer = QLabel(f"Offline · v{__version__}")
        footer.setObjectName("SidebarFooter")
        box.addWidget(footer)
        return panel

    def _account_menu(self) -> QMenu:
        menu = QMenu(self)
        change = QAction("Change my password…", self)
        change.triggered.connect(self._change_password)
        menu.addAction(change)
        backup = QAction("Back up now", self)
        backup.triggered.connect(self._backup_now)
        menu.addAction(backup)
        menu.addSeparator()
        shortcuts = QAction("Keyboard shortcuts", self)
        shortcuts.triggered.connect(self._show_shortcuts)
        menu.addAction(shortcuts)
        about = QAction("About this software", self)
        about.triggered.connect(self._show_about)
        menu.addAction(about)
        menu.addSeparator()
        sign_out = QAction("Sign out / switch user", self)
        sign_out.setShortcut(QKeySequence("Ctrl+L"))
        sign_out.triggered.connect(self.sign_out)
        menu.addAction(sign_out)
        quit_action = QAction("Close the program", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)
        return menu

    # ---------------------------------------------------------- status bar
    def _build_status_bar(self) -> None:
        bar = QStatusBar()
        self.setStatusBar(bar)
        user = self.context.user
        self.status_user = QLabel(
            f"  Signed in: {user.full_name} ({user.role_label})  " if user else ""
        )
        self.status_discount = QLabel()
        self.status_clock = QLabel()
        for widget in (self.status_user, self.status_discount):
            bar.addWidget(widget)
        bar.addPermanentWidget(self.status_clock)
        self._tick_clock()
        timer = QTimer(self)
        timer.timeout.connect(self._tick_clock)
        timer.start(30_000)
        self.refresh_status()

    def refresh_status(self) -> None:
        percent = self.context.settings.discount_percent
        self.status_discount.setText(
            f"  |  Standard discount: {percent:g}%  |  Data folder: {config.data_dir()}  "
        )

    def _tick_clock(self) -> None:
        self.status_clock.setText(f"  {dates.fmt_datetime(dates.now_iso())}  ")

    # ---------------------------------------------------------- shortcuts
    def _build_shortcuts(self) -> None:
        for _label, key, _factory, permission, shortcut in PAGES:
            if not shortcut or key not in self.nav_buttons:
                continue
            action = QAction(self)
            action.setShortcut(QKeySequence(shortcut))
            action.triggered.connect(lambda _checked=False, page=key: self.show_page(page))
            self.addAction(action)
        refresh = QAction(self)
        refresh.setShortcut(QKeySequence("F5"))
        refresh.triggered.connect(self.refresh_current)
        self.addAction(refresh)
        lock = QAction(self)
        lock.setShortcut(QKeySequence("Ctrl+L"))
        lock.triggered.connect(self.sign_out)
        self.addAction(lock)

    # -------------------------------------------------------------- pages
    def show_page(self, key: str) -> None:
        if key not in self.nav_buttons:
            return
        page = self.pages.get(key)
        if page is None:
            factory = next(item[2] for item in PAGES if item[1] == key)
            page = factory(self.context, self)
            self.pages[key] = page
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(page)
        self.nav_buttons[key].setChecked(True)
        self.refresh_current()
        focus = getattr(page, "focus_default", None)
        if callable(focus):
            focus()

    def refresh_current(self) -> None:
        page = self.stack.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except PharmacyError as exc:
                error(self, str(exc))

    def refresh_all(self) -> None:
        """Called after a change that ripples across screens (a sale, a purchase)."""
        for page in self.pages.values():
            marker = getattr(page, "mark_stale", None)
            if callable(marker):
                marker()
        self.refresh_current()
        self.refresh_status()

    # ------------------------------------------------------------- actions
    def _change_password(self) -> None:
        ChangePasswordDialog(self.context, self).exec()

    def _backup_now(self) -> None:
        try:
            path = self.context.backups.create("manual")
        except PharmacyError as exc:
            error(self, str(exc))
            return
        QMessageBox.information(
            self, "Backup taken", f"A copy of today's data was saved as:\n\n{path}"
        )

    def _show_shortcuts(self) -> None:
        lines = [f"<tr><td><b>{s}</b></td><td>&nbsp;{l}</td></tr>"
                 for l, _k, _f, _p, s in PAGES if s]
        lines += [
            "<tr><td><b>F5</b></td><td>&nbsp;Refresh the screen</td></tr>",
            "<tr><td><b>Ctrl+L</b></td><td>&nbsp;Sign out / switch user</td></tr>",
            "<tr><td colspan='2'><br/><b>On the counter sale screen</b></td></tr>",
            "<tr><td><b>Ctrl+F</b></td><td>&nbsp;Jump to the medicine search box</td></tr>",
            "<tr><td><b>Enter</b></td><td>&nbsp;Add the highlighted medicine to the bill</td></tr>",
            "<tr><td><b>+ / -</b></td><td>&nbsp;Change the quantity of the selected line</td></tr>",
            "<tr><td><b>Delete</b></td><td>&nbsp;Remove the selected line</td></tr>",
            "<tr><td><b>Ctrl+Enter</b></td><td>&nbsp;Take payment and print</td></tr>",
            "<tr><td><b>Ctrl+H</b></td><td>&nbsp;Hold the bill / pick it up later</td></tr>",
        ]
        QMessageBox.information(
            self, "Keyboard shortcuts", "<table>" + "".join(lines) + "</table>"
        )

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            f"<b>{APP_NAME}</b><br/>Pharmacy management software, version {__version__}"
            "<br/><br/>Runs entirely on this computer. No internet connection is used "
            "or needed; all data stays in:<br/><code>"
            f"{config.data_dir()}</code><br/><br/>"
            "Back up regularly — Settings → Backup, or copy the data folder to a USB stick.",
        )

    def _show_startup_alerts(self) -> None:
        """Nudge about expiry and reordering once, at sign-in."""
        summary = self.context.reports.dashboard()
        notes = []
        if summary["expired"]:
            notes.append(
                f"<b>{summary['expired']}</b> batch(es) have expired and are still on the shelf."
            )
        if summary["expiring"]:
            notes.append(
                f"<b>{summary['expiring']}</b> batch(es) expire within "
                f"{self.context.settings.get_int('warn_expiry_days', 90)} days."
            )
        if summary["low_stock"]:
            notes.append(f"<b>{summary['low_stock']}</b> medicine(s) are at or below "
                         "their reorder level.")
        if not notes:
            return
        box = QMessageBox(self)
        box.setWindowTitle("Things to look at today")
        box.setTextFormat(Qt.RichText)
        box.setText("<br/>".join(notes))
        box.setIcon(QMessageBox.Information)
        open_stock = box.addButton("Open stock & expiry", QMessageBox.AcceptRole)
        box.addButton("Later", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_stock:
            self.show_page("stock")

    def sign_out(self) -> None:
        if not confirm(self, "Sign out and return to the sign-in screen?"):
            return
        self.context.auth.logout()
        self.signed_out = True
        self.close()

    # -------------------------------------------------------------- closing
    def closeEvent(self, event):  # noqa: N802 - Qt naming
        pos = self.pages.get("pos")
        if pos is not None and getattr(pos, "has_unsaved_bill", lambda: False)():
            if not confirm(
                self,
                "There is a bill on the counter screen that has not been paid for. "
                "Close anyway and lose it?",
                danger=True,
            ):
                event.ignore()
                return
        event.accept()
