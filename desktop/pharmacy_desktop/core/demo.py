"""Sample data.

Loading the demo fills an empty database with a believable week of trading so
the owner can click through every screen before typing in real stock. It is
offered on the Settings screen and is never loaded automatically.
"""

from __future__ import annotations

import random
from datetime import timedelta

from . import dates
from .context import AppContext
from .money import to_paisa
from .services.purchases import PurchaseDraft, PurchaseLine

# name, generic, company, form, strength, pack, unit, cost, retail, reorder
MEDICINES = [
    ("Panadol 500mg", "Paracetamol", "GSK", "Tablet", "500mg", 10, "Tablet", 2.20, 2.75, 200),
    ("Panadol Extra", "Paracetamol + Caffeine", "GSK", "Tablet", "", 10, "Tablet", 3.10, 3.90, 150),
    ("Brufen 400mg", "Ibuprofen", "Abbott", "Tablet", "400mg", 10, "Tablet", 4.50, 5.60, 120),
    ("Disprin", "Aspirin", "Reckitt", "Tablet", "300mg", 10, "Tablet", 1.60, 2.00, 200),
    ("Augmentin 625mg", "Co-amoxiclav", "GSK", "Tablet", "625mg", 6, "Tablet", 62.0, 78.0, 60),
    ("Amoxil 500mg", "Amoxicillin", "GSK", "Capsule", "500mg", 10, "Capsule", 14.0, 17.5, 80),
    ("Azomax 500mg", "Azithromycin", "Getz Pharma", "Tablet", "500mg", 3, "Tablet", 55.0, 69.0, 40),
    ("Ciproxin 500mg", "Ciprofloxacin", "Bayer", "Tablet", "500mg", 10, "Tablet", 28.0, 35.0, 50),
    ("Flagyl 400mg", "Metronidazole", "Sanofi", "Tablet", "400mg", 10, "Tablet", 6.20, 7.80, 90),
    ("Risek 20mg", "Omeprazole", "Getz Pharma", "Capsule", "20mg", 14, "Capsule", 11.0, 14.0, 100),
    ("Nexum 40mg", "Esomeprazole", "Searle", "Capsule", "40mg", 14, "Capsule", 19.0, 24.0, 60),
    ("Motilium 10mg", "Domperidone", "Highnoon", "Tablet", "10mg", 10, "Tablet", 5.40, 6.75, 80),
    ("Gravinate 50mg", "Dimenhydrinate", "Searle", "Tablet", "50mg", 10, "Tablet", 4.00, 5.00, 80),
    ("Imodium", "Loperamide", "Johnson & Johnson", "Capsule", "2mg", 10, "Capsule", 9.0, 11.5, 40),
    ("ORS Sachet", "Oral rehydration salts", "Local", "Sachet", "", 1, "Sachet", 12.0, 15.0, 100),
    ("Ventolin Inhaler", "Salbutamol", "GSK", "Inhaler", "100mcg", 1, "Inhaler", 380.0, 470.0, 15),
    ("Ventolin Syrup", "Salbutamol", "GSK", "Syrup", "2mg/5ml", 1, "Bottle", 95.0, 118.0, 25),
    ("Calpol Syrup", "Paracetamol", "GSK", "Syrup", "120mg/5ml", 1, "Bottle", 88.0, 110.0, 40),
    ("Klaricid Syrup", "Clarithromycin", "Abbott", "Syrup", "125mg/5ml", 1, "Bottle", 430.0, 535.0, 12),
    ("Zyrtec 10mg", "Cetirizine", "GSK", "Tablet", "10mg", 10, "Tablet", 7.80, 9.75, 70),
    ("Avil 25mg", "Pheniramine", "Sanofi", "Tablet", "25mg", 10, "Tablet", 2.90, 3.60, 90),
    ("Piriton", "Chlorpheniramine", "GSK", "Tablet", "4mg", 10, "Tablet", 2.10, 2.65, 90),
    ("Glucophage 500mg", "Metformin", "Merck", "Tablet", "500mg", 20, "Tablet", 4.30, 5.40, 150),
    ("Diamicron MR 60", "Gliclazide", "Servier", "Tablet", "60mg", 10, "Tablet", 24.0, 30.0, 60),
    ("Lantus SoloStar", "Insulin glargine", "Sanofi", "Injection", "100IU", 1, "Pen", 2250.0, 2700.0, 6),
    ("Concor 5mg", "Bisoprolol", "Merck", "Tablet", "5mg", 10, "Tablet", 16.0, 20.0, 60),
    ("Tenormin 50mg", "Atenolol", "AstraZeneca", "Tablet", "50mg", 14, "Tablet", 8.40, 10.5, 60),
    ("Norvasc 5mg", "Amlodipine", "Pfizer", "Tablet", "5mg", 14, "Tablet", 11.0, 13.8, 60),
    ("Lipitor 20mg", "Atorvastatin", "Pfizer", "Tablet", "20mg", 10, "Tablet", 32.0, 40.0, 40),
    ("Cardiprin 100", "Aspirin", "Reckitt", "Tablet", "100mg", 10, "Tablet", 3.40, 4.25, 80),
    ("Surbex Z", "Multivitamin + Zinc", "Abbott", "Tablet", "", 30, "Tablet", 9.20, 11.5, 100),
    ("Calcium Sandoz", "Calcium + Vit D", "GSK", "Tablet", "", 10, "Tablet", 15.0, 18.75, 60),
    ("Ferrous Sulphate", "Iron", "Local", "Tablet", "200mg", 30, "Tablet", 1.80, 2.25, 120),
    ("Polyfax Ointment", "Polymyxin B", "GSK", "Ointment", "20g", 1, "Tube", 165.0, 205.0, 20),
    ("Betnovate C", "Betamethasone", "GSK", "Cream", "20g", 1, "Tube", 178.0, 220.0, 20),
    ("Dettol Antiseptic", "Chloroxylenol", "Reckitt", "Solution", "250ml", 1, "Bottle", 320.0, 395.0, 15),
    ("Surgical Face Mask", "Disposable mask", "Local", "Device", "", 50, "Piece", 4.00, 6.00, 200),
    ("Insulin Syringe", "Disposable syringe", "BD", "Device", "1ml", 1, "Piece", 22.0, 28.0, 100),
    ("Digital Thermometer", "Thermometer", "Omron", "Device", "", 1, "Piece", 480.0, 600.0, 10),
    ("BP Apparatus", "Digital BP monitor", "Omron", "Device", "", 1, "Piece", 5400.0, 6600.0, 4),
]

CATEGORY_BY_FORM = {
    "Inhaler": "Respiratory",
    "Injection": "Diabetes",
    "Device": "Surgical / Disposable",
    "Cream": "Cosmetic",
    "Ointment": "Cosmetic",
}

SUPPLIERS = [
    ("Al-Madina Pharma Distributors", "0300-1234567", "Multan Road, Kahror Pakka"),
    ("Bismillah Medicine Agency", "0301-7654321", "Hospital Road, Lodhran"),
    ("Punjab Drug House", "0333-9876543", "Chowk Shaheedan, Multan"),
]

CUSTOMERS = [
    ("Muhammad Aslam", "0300-4455667"),
    ("Dr. Farhan Clinic", "0321-1122334"),
    ("Ayesha Bibi", "0345-5566778"),
    ("Rana Medical Store", "0302-9988776"),
]


def seed_demo(context: AppContext, *, days: int = 10, seed: int = 7) -> dict:
    """Fill an empty database with medicines, suppliers, purchases and sales."""
    rng = random.Random(seed)
    catalog, inventory, parties = context.catalog, context.inventory, context.parties
    user = context.auth.current_user or context.auth.get_user(
        int(context.db.scalar("SELECT MIN(id) FROM users"))
    )

    product_ids: list[int] = []
    for (
        name,
        generic,
        company,
        form,
        strength,
        pack,
        unit,
        cost,
        retail,
        reorder,
    ) in MEDICINES:
        if context.db.query_one("SELECT id FROM products WHERE name = ?", (name,)):
            continue
        product_ids.append(
            catalog.create_product(
                {
                    "name": name,
                    "generic_name": generic,
                    "category_id": catalog.category_id(
                        CATEGORY_BY_FORM.get(form, _category_for(generic))
                    ),
                    "manufacturer_id": catalog.manufacturer_id(company),
                    "form": form,
                    "strength": strength,
                    "pack_size": pack,
                    "unit_label": unit,
                    "purchase_price": to_paisa(cost),
                    "sale_price": to_paisa(retail),
                    "tax_percent": 0,
                    "reorder_level": reorder,
                    "rack": f"{rng.choice('ABCDE')}-{rng.randint(1, 9)}",
                    "prescription_required": 1 if form in {"Injection", "Inhaler"} else 0,
                    "discount_eligible": 1,
                }
            )
        )

    supplier_ids = [
        parties.create("supplier", {"name": name, "phone": phone, "address": address})
        for name, phone, address in SUPPLIERS
    ]
    customer_ids = [
        parties.create("customer", {"name": name, "phone": phone})
        for name, phone in CUSTOMERS
    ]

    # Goods received: two supplier bills covering the whole shelf.
    today = dates.today()
    for index, supplier_id in enumerate(supplier_ids[:2]):
        draft = PurchaseDraft(
            supplier_id=supplier_id,
            supplier_bill_no=f"B-{1000 + index}",
            purchase_date=(today - timedelta(days=days + 2 - index)).strftime(dates.ISO),
        )
        for product_id in product_ids[index::2]:
            product = catalog.get(product_id)
            quantity = max(20, int(product["reorder_level"] * rng.uniform(2.0, 4.0)))
            expiry = today + timedelta(days=rng.choice([25, 70, 200, 400, 700, 900]))
            draft.lines.append(
                PurchaseLine(
                    product_id=product_id,
                    product_name=product["name"],
                    quantity=quantity,
                    unit_cost=int(product["purchase_price"]),
                    batch_no=f"B{rng.randint(1000, 9999)}",
                    expiry_date=expiry.strftime(dates.ISO),
                    bonus_quantity=quantity // 20,
                    unit_sale_price=int(product["sale_price"]),
                    discount_percent=rng.choice([0, 0, 2.5, 5]),
                )
            )
        context.purchases.create_purchase(
            draft, user=user, paid_amount=int(draft.net_amount * rng.uniform(0.4, 1.0))
        )

    # A run of trading days, busier in the evenings.
    sale_count = 0
    for day_offset in range(days, -1, -1):
        day = today - timedelta(days=day_offset)
        for _ in range(rng.randint(4, 11)):
            cart = context.sales.new_cart()
            for _ in range(rng.randint(1, 4)):
                product = catalog.get(rng.choice(product_ids))
                if inventory.sellable_on_hand(int(product["id"])) < 5:
                    continue
                try:
                    context.sales.add_to_cart(cart, product, rng.randint(1, 6))
                except Exception:
                    continue
            if cart.is_empty:
                continue
            on_credit = rng.random() < 0.12
            if on_credit or rng.random() < 0.25:
                customer_id = rng.choice(customer_ids)
                cart.customer_id = customer_id
                cart.customer_name = parties.get(customer_id)["name"]
            stamp = day.strftime("%Y-%m-%d") + f" {rng.randint(9, 21):02d}:{rng.randint(0, 59):02d}:00"
            net = cart.net_amount
            context.sales.complete_sale(
                cart,
                user=user,
                paid_amount=int(net * rng.uniform(0.2, 0.8)) if on_credit else net,
                payment_method="Credit" if on_credit else rng.choice(["Cash", "Cash", "Card"]),
                sale_date=stamp,
            )
            sale_count += 1

    for customer_id in customer_ids:
        balance = parties.balance(customer_id)
        if balance > 0 and rng.random() < 0.6:
            parties.record_payment(
                customer_id,
                amount=int(balance * rng.uniform(0.3, 1.0)),
                direction="in",
                method="Cash",
                user=user,
                note="Demo payment",
            )

    context.audit.log("demo.seed", user=user, details=f"{sale_count} sales over {days} days")
    return {
        "products": len(product_ids),
        "suppliers": len(supplier_ids),
        "customers": len(customer_ids),
        "sales": sale_count,
    }


def _category_for(generic: str) -> str:
    generic = generic.lower()
    if any(word in generic for word in ("cillin", "azith", "cipro", "metronid", "clarith")):
        return "Antibiotic"
    if any(word in generic for word in ("paracetamol", "ibuprofen", "aspirin")):
        return "Painkiller / Analgesic"
    if any(word in generic for word in ("cetirizine", "pheniramine", "chlorphen")):
        return "Anti-allergy"
    if any(word in generic for word in ("metformin", "gliclazide", "insulin")):
        return "Diabetes"
    if any(word in generic for word in ("bisoprolol", "atenolol", "amlodipine", "atorva")):
        return "Cardiac"
    if any(word in generic for word in ("omeprazole", "esomeprazole", "domperidone", "loperamide")):
        return "Gastro"
    if any(word in generic for word in ("vitamin", "calcium", "iron", "zinc")):
        return "Vitamin / Supplement"
    return "General"
