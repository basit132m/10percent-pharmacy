"""The medicine master: products, categories and manufacturers.

Prices here are the *defaults* used when a medicine is sold or received; the
price actually charged is copied onto the batch and onto the invoice line, so
raising a price tomorrow never rewrites yesterday's sales.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from ..db import Database
from ..errors import NotFoundError, ValidationError
from ..money import to_paisa, to_rupees
from .audit import AuditService

DOSAGE_FORMS = (
    "Tablet",
    "Capsule",
    "Syrup",
    "Suspension",
    "Injection",
    "Drops",
    "Cream",
    "Ointment",
    "Sachet",
    "Inhaler",
    "Suppository",
    "Solution",
    "Powder",
    "Device",
    "Other",
)

DEFAULT_CATEGORIES = (
    "Antibiotic",
    "Painkiller / Analgesic",
    "Anti-allergy",
    "Cardiac",
    "Diabetes",
    "Gastro",
    "Respiratory",
    "Vitamin / Supplement",
    "Baby care",
    "Surgical / Disposable",
    "Cosmetic",
    "General",
)

# The only columns a caller may write. Anything else in the dictionary — the
# joined names and stock figures the list query adds, for instance — is dropped
# rather than blowing up the UPDATE.
EDITABLE_COLUMNS = (
    "code",
    "barcode",
    "name",
    "generic_name",
    "category_id",
    "manufacturer_id",
    "form",
    "strength",
    "pack_size",
    "unit_label",
    "purchase_price",
    "sale_price",
    "tax_percent",
    "reorder_level",
    "rack",
    "prescription_required",
    "discount_eligible",
    "is_active",
    "notes",
)

IMPORT_COLUMNS = (
    "name",
    "generic_name",
    "category",
    "manufacturer",
    "form",
    "strength",
    "pack_size",
    "unit_label",
    "purchase_price",
    "sale_price",
    "tax_percent",
    "reorder_level",
    "rack",
    "barcode",
    "code",
    "prescription_required",
    "opening_quantity",
    "batch_no",
    "expiry_date",
)


class CatalogService:
    def __init__(self, db: Database, audit: AuditService | None = None):
        self.db = db
        self.audit = audit or AuditService(db)

    # ------------------------------------------------------------ lookup lists
    def ensure_default_categories(self) -> None:
        if self.db.scalar("SELECT COUNT(*) FROM categories"):
            return
        self.db.executemany(
            "INSERT INTO categories (name) VALUES (?)", [(c,) for c in DEFAULT_CATEGORIES]
        )

    def categories(self) -> list:
        return self.db.query("SELECT * FROM categories ORDER BY name")

    def manufacturers(self) -> list:
        return self.db.query("SELECT * FROM manufacturers ORDER BY name")

    def _lookup_id(self, table: str, name: str | None) -> int | None:
        """Find a category/manufacturer by name, creating it when it is new."""
        name = (name or "").strip()
        if not name:
            return None
        row = self.db.query_one(
            f"SELECT id FROM {table} WHERE name = ? COLLATE NOCASE", (name,)
        )
        if row:
            return int(row["id"])
        return self.db.insert(table, {"name": name})

    def category_id(self, name: str | None) -> int | None:
        return self._lookup_id("categories", name)

    def manufacturer_id(self, name: str | None) -> int | None:
        return self._lookup_id("manufacturers", name)

    def rename_category(self, category_id: int, name: str) -> None:
        if not name.strip():
            raise ValidationError("Category name is required.")
        self.db.update("categories", category_id, {"name": name.strip()})

    def delete_category(self, category_id: int) -> None:
        self.db.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def rename_manufacturer(self, manufacturer_id: int, name: str) -> None:
        if not name.strip():
            raise ValidationError("Company name is required.")
        self.db.update("manufacturers", manufacturer_id, {"name": name.strip()})

    def delete_manufacturer(self, manufacturer_id: int) -> None:
        self.db.execute("DELETE FROM manufacturers WHERE id = ?", (manufacturer_id,))

    # --------------------------------------------------------------- products
    _SELECT = """
        SELECT p.*,
               c.name  AS category_name,
               m.name  AS manufacturer_name,
               COALESCE(s.quantity, 0)          AS stock_quantity,
               COALESCE(s.sellable_quantity, 0) AS sellable_quantity,
               (SELECT MIN(b.expiry_date) FROM batches b
                 WHERE b.product_id = p.id AND b.quantity > 0
                   AND b.expiry_date IS NOT NULL) AS nearest_expiry
        FROM products p
        LEFT JOIN categories    c ON c.id = p.category_id
        LEFT JOIN manufacturers m ON m.id = p.manufacturer_id
        LEFT JOIN product_stock s ON s.product_id = p.id
    """

    def get(self, product_id: int):
        row = self.db.query_one(self._SELECT + " WHERE p.id = ?", (product_id,))
        if row is None:
            raise NotFoundError("That medicine is not in the list any more.")
        return row

    def find_by_barcode(self, barcode: str):
        barcode = (barcode or "").strip()
        if not barcode:
            return None
        return self.db.query_one(
            self._SELECT + " WHERE (p.barcode = ? OR p.code = ?) AND p.is_active = 1",
            (barcode, barcode),
        )

    def list_products(
        self,
        search: str = "",
        *,
        category_id: int | None = None,
        manufacturer_id: int | None = None,
        only_active: bool = True,
        stock_filter: str = "all",
        limit: int | None = None,
    ) -> list:
        """Search the master list. ``stock_filter`` is all/in/low/out."""
        clauses: list[str] = []
        params: list[Any] = []
        if only_active:
            clauses.append("p.is_active = 1")
        search = (search or "").strip()
        if search:
            like = f"%{search}%"
            clauses.append(
                "(p.name LIKE ? OR p.generic_name LIKE ? OR p.barcode = ? OR p.code = ? "
                "OR m.name LIKE ?)"
            )
            params += [like, like, search, search, like]
        if category_id:
            clauses.append("p.category_id = ?")
            params.append(category_id)
        if manufacturer_id:
            clauses.append("p.manufacturer_id = ?")
            params.append(manufacturer_id)
        if stock_filter == "in":
            clauses.append("COALESCE(s.quantity, 0) > 0")
        elif stock_filter == "out":
            clauses.append("COALESCE(s.quantity, 0) <= 0")
        elif stock_filter == "low":
            clauses.append(
                "COALESCE(s.quantity, 0) <= p.reorder_level AND p.reorder_level > 0"
            )
        sql = self._SELECT
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY p.name"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return self.db.query(sql, params)

    def search_for_sale(self, term: str, limit: int = 40) -> list:
        """POS search: only sellable medicines, in-stock ones first."""
        term = (term or "").strip()
        like = f"%{term}%"
        return self.db.query(
            self._SELECT
            + """
             WHERE p.is_active = 1
               AND (? = '' OR p.name LIKE ? OR p.generic_name LIKE ?
                    OR p.barcode = ? OR p.code = ?)
             ORDER BY (COALESCE(s.sellable_quantity, 0) > 0) DESC,
                      (p.name LIKE ?) DESC, p.name
             LIMIT ?
            """,
            (term, like, like, term, term, f"{term}%", limit),
        )

    # ------------------------------------------------------------ write paths
    @staticmethod
    def _clean(values: dict[str, Any]) -> dict[str, Any]:
        name = (values.get("name") or "").strip()
        if not name:
            raise ValidationError("Medicine name is required.")
        pack_size = int(values.get("pack_size") or 1)
        if pack_size < 1:
            raise ValidationError("Pack size must be 1 or more.")
        sale_price = int(values.get("sale_price") or 0)
        purchase_price = int(values.get("purchase_price") or 0)
        if sale_price < 0 or purchase_price < 0:
            raise ValidationError("Prices cannot be negative.")
        tax_percent = float(values.get("tax_percent") or 0)
        if not 0 <= tax_percent <= 100:
            raise ValidationError("Tax % must be between 0 and 100.")
        cleaned = {key: values[key] for key in EDITABLE_COLUMNS if key in values}
        cleaned.update(
            {
                "name": name,
                "pack_size": pack_size,
                "sale_price": sale_price,
                "purchase_price": purchase_price,
                "tax_percent": tax_percent,
                "reorder_level": max(0, int(values.get("reorder_level") or 0)),
            }
        )
        for key in ("code", "barcode"):
            value = (cleaned.get(key) or "").strip()
            cleaned[key] = value or None
        return cleaned

    def create_product(self, values: dict[str, Any]) -> int:
        values = self._clean(values)
        self._assert_unique(values.get("code"), values.get("barcode"), None)
        now = datetime.now().isoformat(timespec="seconds")
        values.update({"created_at": now, "updated_at": now})
        product_id = self.db.insert("products", values)
        self.audit.log(
            "product.create",
            entity="product",
            entity_id=product_id,
            details=values["name"],
        )
        return product_id

    def update_product(self, product_id: int, values: dict[str, Any]) -> None:
        values = self._clean(values)
        self._assert_unique(values.get("code"), values.get("barcode"), product_id)
        values["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.db.update("products", product_id, values)
        self.audit.log(
            "product.update", entity="product", entity_id=product_id, details=values["name"]
        )

    def _assert_unique(self, code: str | None, barcode: str | None, product_id: int | None):
        for column, value in (("code", code), ("barcode", barcode)):
            if not value:
                continue
            row = self.db.query_one(
                f"SELECT id, name FROM products WHERE {column} = ? COLLATE NOCASE",
                (value,),
            )
            if row and row["id"] != product_id:
                raise ValidationError(
                    f"{column.title()} '{value}' is already used by {row['name']}."
                )

    def set_active(self, product_id: int, active: bool) -> None:
        self.db.update(
            "products",
            product_id,
            {
                "is_active": 1 if active else 0,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )
        self.audit.log(
            "product.enable" if active else "product.disable",
            entity="product",
            entity_id=product_id,
        )

    def delete_product(self, product_id: int) -> None:
        """Only ever removes a medicine that was never bought or sold."""
        sold = self.db.scalar(
            "SELECT COUNT(*) FROM sale_items WHERE product_id = ?", (product_id,)
        )
        purchased = self.db.scalar(
            "SELECT COUNT(*) FROM purchase_items WHERE product_id = ?", (product_id,)
        )
        if sold or purchased:
            raise ValidationError(
                "This medicine appears on past invoices, so it cannot be deleted. "
                "Mark it inactive instead — it will disappear from the counter screen."
            )
        self.db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        self.audit.log("product.delete", entity="product", entity_id=product_id)

    def update_prices(self, product_id: int, purchase_price: int, sale_price: int) -> None:
        self.db.update(
            "products",
            product_id,
            {
                "purchase_price": purchase_price,
                "sale_price": sale_price,
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

    # ------------------------------------------------------------- CSV in/out
    def export_csv(self, path: str | Path, rows: Iterable | None = None) -> Path:
        path = Path(path)
        rows = list(rows if rows is not None else self.list_products(only_active=False))
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "code",
                    "barcode",
                    "name",
                    "generic_name",
                    "category",
                    "manufacturer",
                    "form",
                    "strength",
                    "pack_size",
                    "unit_label",
                    "purchase_price",
                    "sale_price",
                    "tax_percent",
                    "reorder_level",
                    "rack",
                    "prescription_required",
                    "stock_quantity",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row["code"] or "",
                        row["barcode"] or "",
                        row["name"],
                        row["generic_name"] or "",
                        row["category_name"] or "",
                        row["manufacturer_name"] or "",
                        row["form"] or "",
                        row["strength"] or "",
                        row["pack_size"],
                        row["unit_label"],
                        to_rupees(row["purchase_price"]),
                        to_rupees(row["sale_price"]),
                        row["tax_percent"],
                        row["reorder_level"],
                        row["rack"] or "",
                        "yes" if row["prescription_required"] else "no",
                        row["stock_quantity"],
                    ]
                )
        return path

    def write_import_template(self, path: str | Path) -> Path:
        path = Path(path)
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle)
            writer.writerow(IMPORT_COLUMNS)
            writer.writerow(
                [
                    "Panadol 500mg",
                    "Paracetamol",
                    "Painkiller / Analgesic",
                    "GSK",
                    "Tablet",
                    "500mg",
                    "10",
                    "Tablet",
                    "2.50",
                    "3.00",
                    "0",
                    "50",
                    "A-1",
                    "",
                    "",
                    "no",
                    "200",
                    "B-1024",
                    "2027-12-31",
                ]
            )
        return path

    def import_csv(self, path: str | Path, *, update_existing: bool = True) -> dict:
        """Bulk-load the medicine list from a spreadsheet export.

        Rows are matched on barcode, then code, then name. Anything that cannot
        be read is reported back with its line number instead of aborting the
        whole file.
        """
        path = Path(path)
        created = updated = 0
        errors: list[str] = []
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "name" not in [
                (f or "").strip().lower() for f in reader.fieldnames
            ]:
                raise ValidationError(
                    "The file needs a 'name' column. Use the template button to get "
                    "a file with the right headings."
                )
            for line_no, raw in enumerate(reader, start=2):
                row = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
                try:
                    result = self._import_row(row, update_existing=update_existing)
                except (ValidationError, ValueError) as exc:
                    errors.append(f"Line {line_no}: {exc}")
                    continue
                if result == "created":
                    created += 1
                elif result == "updated":
                    updated += 1
        self.audit.log(
            "product.import",
            entity="product",
            details=f"{created} added, {updated} updated, {len(errors)} skipped",
        )
        return {"created": created, "updated": updated, "errors": errors}

    def _import_row(self, row: dict[str, str], *, update_existing: bool) -> str:
        name = row.get("name", "").strip()
        if not name:
            raise ValidationError("name is empty")
        values = {
            "name": name,
            "generic_name": row.get("generic_name") or None,
            "category_id": self.category_id(row.get("category")),
            "manufacturer_id": self.manufacturer_id(row.get("manufacturer")),
            "form": row.get("form") or None,
            "strength": row.get("strength") or None,
            "pack_size": int(row.get("pack_size") or 1),
            "unit_label": row.get("unit_label") or "Unit",
            "purchase_price": to_paisa(row.get("purchase_price") or 0),
            "sale_price": to_paisa(row.get("sale_price") or 0),
            "tax_percent": float(row.get("tax_percent") or 0),
            "reorder_level": int(float(row.get("reorder_level") or 0)),
            "rack": row.get("rack") or None,
            "code": row.get("code") or None,
            "barcode": row.get("barcode") or None,
            "prescription_required": 1
            if row.get("prescription_required", "").lower() in {"1", "yes", "true", "y"}
            else 0,
        }
        existing = None
        if values["barcode"]:
            existing = self.db.query_one(
                "SELECT id FROM products WHERE barcode = ? COLLATE NOCASE",
                (values["barcode"],),
            )
        if existing is None and values["code"]:
            existing = self.db.query_one(
                "SELECT id FROM products WHERE code = ? COLLATE NOCASE", (values["code"],)
            )
        if existing is None:
            existing = self.db.query_one(
                "SELECT id FROM products WHERE name = ? COLLATE NOCASE", (name,)
            )

        opening = int(float(row.get("opening_quantity") or 0))
        if existing is not None:
            if not update_existing:
                return "skipped"
            self.update_product(int(existing["id"]), values)
            product_id, outcome = int(existing["id"]), "updated"
        else:
            product_id, outcome = self.create_product(values), "created"

        if opening > 0:
            from .inventory import InventoryService  # local import: avoids a cycle

            InventoryService(self.db, self.audit).add_stock(
                product_id=product_id,
                quantity=opening,
                batch_no=row.get("batch_no") or "-",
                expiry_date=row.get("expiry_date") or None,
                purchase_price=values["purchase_price"],
                sale_price=values["sale_price"],
                source="import",
            )
        return outcome
