"""Command line entry point: ``python -m pharmacy_desktop``."""

from __future__ import annotations

import argparse
import sys

from . import APP_NAME, __version__


def say(message: str) -> None:
    """Print, tolerating a windowed build where there is no console at all."""
    stream = sys.stdout or sys.stderr
    if stream is None:  # pragma: no cover - only inside the packaged .exe
        return
    try:
        stream.write(message + "\n")
        stream.flush()
    except (OSError, ValueError):  # pragma: no cover
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pharmacy_desktop", description=f"{APP_NAME} — pharmacy management software"
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print the version and exit.",
    )
    parser.add_argument(
        "--self-check",
        action="store_true",
        help="Open the database, check the schema and exit. Used by the build.",
    )
    parser.add_argument(
        "--data-dir",
        help="Keep the database and backups here instead of the default folder.",
    )
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Fill the database with sample medicines and sales, then exit.",
    )
    parser.add_argument(
        "--reset-admin",
        metavar="PASSWORD",
        help="Set the admin password (used if the owner is locked out), then exit.",
    )
    args = parser.parse_args(argv)

    if args.version:
        say(f"{APP_NAME} {__version__}")
        return 0

    if args.self_check or args.seed_demo or args.reset_admin:
        import os

        from .core import config

        if args.data_dir:
            os.environ[config.ENV_DATA_DIR] = args.data_dir
        from .core.context import AppContext

        context = AppContext()
        try:
            if args.self_check:
                tables = context.db.scalar(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
                )
                say(
                    f"{APP_NAME} {__version__} — database ready at "
                    f"{context.db.path} ({tables} tables, "
                    f"{context.settings.discount_percent:g}% standard discount)"
                )
            if args.reset_admin:
                row = context.db.query_one(
                    "SELECT id, username FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
                )
                if row is None:
                    say("No administrator account exists.")
                    return 1
                context.auth.set_password(int(row["id"]), args.reset_admin, force_change=True)
                context.auth.set_active(int(row["id"]), True)
                say(f"Password reset for '{row['username']}'.")
            if args.seed_demo:
                from .core.demo import seed_demo

                result = seed_demo(context)
                say(
                    f"Loaded {result['products']} medicines, {result['suppliers']} suppliers, "
                    f"{result['customers']} customers, {result['sales']} sales."
                )
        finally:
            context.close(backup=False)
        return 0

    from .app import run

    return run(data_dir=args.data_dir)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
