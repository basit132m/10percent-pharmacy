"""Application bootstrap: logging, crash handling, sign-in loop."""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

import shiboken6
from PySide6.QtCore import QLockFile
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from . import APP_NAME, __version__
from .core import config
from .core.context import AppContext
from .ui import theme
from .ui.login import LoginDialog
from .ui.main_window import MainWindow

log = logging.getLogger("pharmacy")


def setup_logging() -> None:
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    try:
        handlers.append(logging.FileHandler(config.log_path(), encoding="utf-8"))
    except OSError:  # pragma: no cover - read-only disk
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
    )


def install_crash_handler(app: QApplication) -> None:
    """Show a readable message instead of vanishing when something goes wrong."""

    def handler(kind, value, tb):
        if issubclass(kind, KeyboardInterrupt):  # pragma: no cover
            sys.__excepthook__(kind, value, tb)
            return
        text = "".join(traceback.format_exception(kind, value, tb))
        log.error("Unhandled error\n%s", text)
        box = QMessageBox()
        box.setIcon(QMessageBox.Critical)
        box.setWindowTitle("Something went wrong")
        box.setText(
            "The program hit an unexpected problem. Your data is safe — the last "
            "completed action was saved.\n\nIf this keeps happening, send the file below "
            "to whoever supports this software."
        )
        box.setInformativeText(str(config.log_path()))
        box.setDetailedText(text)
        box.exec()

    sys.excepthook = handler


def run(argv: list[str] | None = None, *, data_dir: str | None = None) -> int:
    setup_logging()
    if data_dir:
        import os

        os.environ[config.ENV_DATA_DIR] = data_dir

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Ten Percent Discount Pharmacy")
    theme.apply(app)
    install_crash_handler(app)

    logo = config.resource_path("pharmacy-logo.png")
    if logo.exists():
        app.setWindowIcon(QIcon(QPixmap(str(logo))))

    lock = QLockFile(str(Path(config.data_dir()) / "pharmacy.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(100):
        QMessageBox.warning(
            None,
            APP_NAME,
            "The program is already running on this computer.\n\n"
            "Look for it on the taskbar. Opening it twice can cause two different "
            "invoice numbers to be given out at the same time.",
        )
        return 1

    log.info("Starting %s %s — data in %s", APP_NAME, __version__, config.data_dir())
    context = AppContext()
    exit_code = 0
    try:
        while True:
            login = LoginDialog(context)
            accepted = login.exec() == QDialog.Accepted
            _destroy(login)
            if not accepted:
                break
            window = MainWindow(context)
            window.showMaximized()
            exit_code = app.exec()
            signed_out = getattr(window, "signed_out", False)
            # Take the window down while Python still owns it. Left to the
            # interpreter's own shutdown, Qt tears the window apart after the
            # objects it points at have gone and the program dies noisily on
            # the way out — which, to whoever just clicked Close, looks like a
            # crash.
            _destroy(window)
            app.processEvents()
            if not signed_out:
                break
    finally:
        context.close()
        lock.unlock()
    log.info("Closed")
    return exit_code


def _destroy(widget) -> None:
    """Free a top-level window's C++ side now, not at interpreter exit."""
    widget.close()
    if shiboken6.isValid(widget):
        shiboken6.delete(widget)
