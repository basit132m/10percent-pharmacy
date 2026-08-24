"""SQLite access layer: connection handling, schema creation and migrations.

One file, no server, nothing to configure — which is exactly what an offline
counter machine needs. WAL journalling keeps the database readable while a sale
is being written, and foreign keys are enforced so a batch can never outlive its
product.
"""

from __future__ import annotations

import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from . import config
from .errors import ValidationError

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    full_name       TEXT NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'cashier')),
    is_active       INTEGER NOT NULL DEFAULT 1,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    last_login_at   TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username    TEXT,
    action      TEXT NOT NULL,
    entity      TEXT,
    entity_id   INTEGER,
    details     TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at DESC);

CREATE TABLE IF NOT EXISTS categories (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS manufacturers (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE COLLATE NOCASE
);

CREATE TABLE IF NOT EXISTS products (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    code                  TEXT UNIQUE COLLATE NOCASE,
    barcode               TEXT COLLATE NOCASE,
    name                  TEXT NOT NULL COLLATE NOCASE,
    generic_name          TEXT,
    category_id           INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    manufacturer_id       INTEGER REFERENCES manufacturers(id) ON DELETE SET NULL,
    form                  TEXT,
    strength              TEXT,
    pack_size             INTEGER NOT NULL DEFAULT 1 CHECK (pack_size > 0),
    unit_label            TEXT NOT NULL DEFAULT 'Unit',
    purchase_price        INTEGER NOT NULL DEFAULT 0,
    sale_price            INTEGER NOT NULL DEFAULT 0,
    tax_percent           REAL NOT NULL DEFAULT 0,
    reorder_level         INTEGER NOT NULL DEFAULT 0,
    rack                  TEXT,
    prescription_required INTEGER NOT NULL DEFAULT 0,
    discount_eligible     INTEGER NOT NULL DEFAULT 1,
    is_active             INTEGER NOT NULL DEFAULT 1,
    notes                 TEXT,
    created_at            TEXT NOT NULL,
    updated_at            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);

CREATE TABLE IF NOT EXISTS batches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_no        TEXT NOT NULL DEFAULT '-',
    expiry_date     TEXT,
    quantity        INTEGER NOT NULL DEFAULT 0,
    purchase_price  INTEGER NOT NULL DEFAULT 0,
    sale_price      INTEGER NOT NULL DEFAULT 0,
    received_at     TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'opening',
    UNIQUE (product_id, batch_no, expiry_date)
);
CREATE INDEX IF NOT EXISTS idx_batches_product ON batches(product_id);
CREATE INDEX IF NOT EXISTS idx_batches_expiry ON batches(expiry_date);

CREATE TABLE IF NOT EXISTS parties (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT NOT NULL CHECK (type IN ('customer', 'supplier')),
    name            TEXT NOT NULL COLLATE NOCASE,
    phone           TEXT,
    email           TEXT,
    address         TEXT,
    opening_balance INTEGER NOT NULL DEFAULT 0,
    credit_limit    INTEGER NOT NULL DEFAULT 0,
    is_active       INTEGER NOT NULL DEFAULT 1,
    notes           TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parties_type ON parties(type, name);

-- Running account for a customer or supplier. Debit increases what the party
-- owes us, credit decreases it; a supplier's balance is read the other way
-- round by the reports layer.
CREATE TABLE IF NOT EXISTS ledger_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    party_id    INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    entry_date  TEXT NOT NULL,
    doc_type    TEXT NOT NULL,
    doc_id      INTEGER,
    reference   TEXT,
    description TEXT,
    debit       INTEGER NOT NULL DEFAULT 0,
    credit      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ledger_party ON ledger_entries(party_id, entry_date);

CREATE TABLE IF NOT EXISTS sales (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no       TEXT NOT NULL UNIQUE,
    sale_date        TEXT NOT NULL,
    customer_id      INTEGER REFERENCES parties(id) ON DELETE SET NULL,
    customer_name    TEXT,
    doctor_name      TEXT,
    user_id          INTEGER REFERENCES users(id) ON DELETE SET NULL,
    gross_amount     INTEGER NOT NULL DEFAULT 0,
    discount_amount  INTEGER NOT NULL DEFAULT 0,
    tax_amount       INTEGER NOT NULL DEFAULT 0,
    round_off        INTEGER NOT NULL DEFAULT 0,
    net_amount       INTEGER NOT NULL DEFAULT 0,
    cost_amount      INTEGER NOT NULL DEFAULT 0,
    paid_amount      INTEGER NOT NULL DEFAULT 0,
    change_amount    INTEGER NOT NULL DEFAULT 0,
    payment_method   TEXT NOT NULL DEFAULT 'cash',
    status           TEXT NOT NULL DEFAULT 'completed',
    notes            TEXT
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);

CREATE TABLE IF NOT EXISTS sale_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id           INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id        INTEGER REFERENCES products(id) ON DELETE SET NULL,
    batch_id          INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    product_name      TEXT NOT NULL,
    batch_no          TEXT,
    expiry_date       TEXT,
    quantity          INTEGER NOT NULL,
    returned_quantity INTEGER NOT NULL DEFAULT 0,
    unit_price        INTEGER NOT NULL,
    unit_cost         INTEGER NOT NULL DEFAULT 0,
    discount_percent  REAL NOT NULL DEFAULT 0,
    discount_amount   INTEGER NOT NULL DEFAULT 0,
    tax_percent       REAL NOT NULL DEFAULT 0,
    tax_amount        INTEGER NOT NULL DEFAULT 0,
    line_total        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);

CREATE TABLE IF NOT EXISTS sale_returns (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    return_no    TEXT NOT NULL UNIQUE,
    sale_id      INTEGER NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    return_date  TEXT NOT NULL,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    total_amount INTEGER NOT NULL DEFAULT 0,
    restocked    INTEGER NOT NULL DEFAULT 1,
    reason       TEXT
);

CREATE TABLE IF NOT EXISTS sale_return_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id     INTEGER NOT NULL REFERENCES sale_returns(id) ON DELETE CASCADE,
    sale_item_id  INTEGER REFERENCES sale_items(id) ON DELETE SET NULL,
    product_id    INTEGER REFERENCES products(id) ON DELETE SET NULL,
    batch_id      INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    product_name  TEXT NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    INTEGER NOT NULL,
    refund_amount INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS purchases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    reference_no    TEXT NOT NULL UNIQUE,
    supplier_bill_no TEXT,
    purchase_date   TEXT NOT NULL,
    supplier_id     INTEGER REFERENCES parties(id) ON DELETE SET NULL,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    gross_amount    INTEGER NOT NULL DEFAULT 0,
    discount_amount INTEGER NOT NULL DEFAULT 0,
    tax_amount      INTEGER NOT NULL DEFAULT 0,
    net_amount      INTEGER NOT NULL DEFAULT 0,
    paid_amount     INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'received',
    notes           TEXT
);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date);

CREATE TABLE IF NOT EXISTS purchase_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id       INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    product_id        INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_id          INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    product_name      TEXT NOT NULL,
    batch_no          TEXT,
    expiry_date       TEXT,
    quantity          INTEGER NOT NULL,
    bonus_quantity    INTEGER NOT NULL DEFAULT 0,
    unit_cost         INTEGER NOT NULL,
    unit_sale_price   INTEGER NOT NULL DEFAULT 0,
    discount_percent  REAL NOT NULL DEFAULT 0,
    tax_percent       REAL NOT NULL DEFAULT 0,
    line_total        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_purchase_items_purchase ON purchase_items(purchase_id);

CREATE TABLE IF NOT EXISTS stock_adjustments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT NOT NULL,
    product_id  INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_id    INTEGER REFERENCES batches(id) ON DELETE SET NULL,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    quantity    INTEGER NOT NULL,
    reason      TEXT NOT NULL,
    note        TEXT
);
CREATE INDEX IF NOT EXISTS idx_adjustments_created ON stock_adjustments(created_at);

CREATE TABLE IF NOT EXISTS payments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    party_id    INTEGER NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
    direction   TEXT NOT NULL CHECK (direction IN ('in', 'out')),
    amount      INTEGER NOT NULL,
    method      TEXT NOT NULL DEFAULT 'cash',
    paid_at     TEXT NOT NULL,
    reference   TEXT,
    note        TEXT,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS held_sales (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    label       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    payload     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_counters (
    name        TEXT PRIMARY KEY,
    next_value  INTEGER NOT NULL
);

CREATE VIEW IF NOT EXISTS product_stock AS
SELECT p.id AS product_id,
       COALESCE(SUM(b.quantity), 0) AS quantity,
       COALESCE(SUM(CASE WHEN b.expiry_date IS NULL OR b.expiry_date >= date('now')
                         THEN b.quantity ELSE 0 END), 0) AS sellable_quantity
FROM products p
LEFT JOIN batches b ON b.product_id = p.id
GROUP BY p.id;
"""


class Database:
    """A thread-confined SQLite handle with helpers the services build on."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else config.database_path()
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._depth = 0
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self.conn.execute("PRAGMA synchronous = FULL")
        self.conn.execute("PRAGMA busy_timeout = 5000")
        self.migrate()

    # ---------------------------------------------------------------- schema
    def migrate(self) -> None:
        """Create the schema, then apply any migration newer than the file."""
        with self._lock:
            self.conn.executescript(SCHEMA)
            version = self.conn.execute("PRAGMA user_version").fetchone()[0]
            for step in range(version + 1, SCHEMA_VERSION + 1):
                migration = MIGRATIONS.get(step)
                if migration:
                    migration(self.conn)
            self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self.conn.commit()

    # ----------------------------------------------------------- transactions
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Atomic unit of work; nesting joins the outermost transaction."""
        with self._lock:
            outermost = self._depth == 0
            if outermost and not self.conn.in_transaction:
                self.conn.execute("BEGIN IMMEDIATE")
            self._depth += 1
            try:
                yield self.conn
            except Exception:
                self._depth -= 1
                if self._depth == 0:
                    self.conn.rollback()
                raise
            else:
                self._depth -= 1
                if self._depth == 0:
                    self.conn.commit()

    # ---------------------------------------------------------------- queries
    def query(self, sql: str, params: Sequence[Any] | dict = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self.conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: Sequence[Any] | dict = ()) -> sqlite3.Row | None:
        with self._lock:
            return self.conn.execute(sql, params).fetchone()

    def scalar(self, sql: str, params: Sequence[Any] | dict = (), default: Any = 0) -> Any:
        row = self.query_one(sql, params)
        if row is None or row[0] is None:
            return default
        return row[0]

    def execute(self, sql: str, params: Sequence[Any] | dict = ()) -> sqlite3.Cursor:
        with self.transaction() as conn:
            return conn.execute(sql, params)

    def executemany(self, sql: str, seq: Iterable[Sequence[Any]]) -> None:
        with self.transaction() as conn:
            conn.executemany(sql, seq)

    def insert(self, table: str, values: dict[str, Any]) -> int:
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        cursor = self.execute(
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
            list(values.values()),
        )
        return int(cursor.lastrowid)

    def update(self, table: str, row_id: int, values: dict[str, Any]) -> None:
        if not values:
            return
        assignments = ", ".join(f"{key} = ?" for key in values)
        self.execute(
            f"UPDATE {table} SET {assignments} WHERE id = ?",
            [*values.values(), row_id],
        )

    # ------------------------------------------------------- document numbers
    def next_document_number(self, counter: str, prefix: str, width: int = 5) -> str:
        """Hand out the next invoice/return/purchase number, gap-free."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT next_value FROM document_counters WHERE name = ?", (counter,)
            ).fetchone()
            value = int(row["next_value"]) if row else 1
            if row:
                conn.execute(
                    "UPDATE document_counters SET next_value = ? WHERE name = ?",
                    (value + 1, counter),
                )
            else:
                conn.execute(
                    "INSERT INTO document_counters (name, next_value) VALUES (?, ?)",
                    (counter, value + 1),
                )
        return f"{prefix}{value:0{width}d}"

    def peek_document_number(self, counter: str, prefix: str, width: int = 5) -> str:
        row = self.query_one(
            "SELECT next_value FROM document_counters WHERE name = ?", (counter,)
        )
        value = int(row["next_value"]) if row else 1
        return f"{prefix}{value:0{width}d}"

    # ------------------------------------------------------------ maintenance
    def backup_to(self, destination: str | Path) -> Path:
        """Consistent copy of the live database, safe to run while it is open."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            raise ValidationError(f"{destination.name} already exists.")
        with self._lock:
            target = sqlite3.connect(str(destination))
            try:
                self.conn.backup(target)
            finally:
                target.close()
        return destination

    def restore_from(self, source: str | Path) -> None:
        """Replace the live database with a backup file, keeping a safety copy."""
        source = Path(source)
        if not source.exists():
            raise ValidationError(f"Backup file not found: {source}")
        try:
            probe = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
            try:
                tables = {
                    row[0]
                    for row in probe.execute(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    )
                }
            finally:
                probe.close()
        except sqlite3.DatabaseError as exc:
            raise ValidationError(
                f"{source.name} cannot be opened — it is not a pharmacy backup file."
            ) from exc
        if "products" not in tables or "sales" not in tables:
            raise ValidationError(f"{source.name} is not a pharmacy backup file.")
        with self._lock:
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            shutil.copy2(self.path, self.path.with_suffix(f".pre-restore-{stamp}.db"))
            self.conn.close()
            for suffix in ("-wal", "-shm"):
                sidecar = Path(str(self.path) + suffix)
                if sidecar.exists():
                    sidecar.unlink()
            shutil.copy2(source, self.path)
            self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute("PRAGMA journal_mode = WAL")
            self._depth = 0
            self.migrate()

    def vacuum(self) -> None:
        with self._lock:
            self.conn.execute("VACUUM")

    def close(self) -> None:
        with self._lock:
            try:
                self.conn.execute("PRAGMA optimize")
            except sqlite3.Error:  # pragma: no cover - closing a broken handle
                pass
            self.conn.close()


# Future schema changes append here: {version: callable(conn)}.
MIGRATIONS: dict[int, Any] = {}
