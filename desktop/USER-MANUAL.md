# Ten Percent Discount Pharmacy — how to use the software

A guide for the people behind the counter. No computer knowledge assumed.

---

## 1. The first day

**Sign in.** Username `admin`, password `admin123`. The program immediately
asks you to choose your own password. Do it and write the new password down
somewhere safe — nobody can recover it for you, though the owner can reset any
other user's password.

Then set the shop up, in this order.

### a) Pharmacy details — *Settings → Pharmacy details*
Name, address, phone, drug licence number. These print at the top of every
customer receipt. Press **Save changes**.

### b) Check the discount — *Settings → Selling rules*
The standard discount starts at **10%**. Change it here if you ever run a
special. "Most a manager may give" is the ceiling for one-off discounts at the
counter.

### c) Staff accounts — *Users*
Add one account per person. Roles:

| Role | Can do |
|---|---|
| **Administrator (owner)** | everything, including users, settings and backups |
| **Manager / senior pharmacist** | stock, purchases, reports, returns, discounts |
| **Cashier / salesman** | sell at the counter, look up medicines, add customers |

Give each person their own account — the activity log then shows who did what.

### d) The medicine list — *Medicines*
Two ways in:

- **Add medicine** — one at a time. Only the name is required; fill in the
  company, pack size, cost, retail price and reorder level as you go.
- **Import from file…** — if you already have a list in Excel. Click
  *Download a blank template*, fill it in, save as CSV, then import. Add an
  `opening_quantity` column (with `batch_no` and `expiry_date`) to load your
  present stock at the same time.

Prices are **per single unit**. If a strip of 10 tablets costs Rs 27.50, the
cost is 2.75 and the retail is whatever you sell one tablet for. The counter
screen sells in units.

### e) Opening stock — *Stock & expiry → Receive stock*
For each medicine: quantity, batch number, expiry date, cost. Do this once, at
the start; after that stock arrives through **Purchases**.

> Want to practise first? *Settings → Backup & data → Load sample data* fills
> the program with 40 medicines and a week of sales so you can try everything.
> Use it on a fresh installation only.

---

## 2. Selling — the counter screen (**F2**)

1. **Scan the barcode**, or type part of the name or the generic name.
2. Set the **quantity** if it is not 1.
3. Press **Enter** — the medicine goes onto the bill with the 10% already off.
4. Repeat for every item.
5. Press **Ctrl+Enter** (or click **Take payment**).
6. Type what the customer handed over — the change to give back is shown in
   large type. Press **Save & print**.

The batch that expires first is used automatically. To sell from a particular
batch instead, double-click it in the small list under the search results.

| Key | Does |
|---|---|
| **Ctrl+F** | jump back to the search box |
| **Enter** | add the highlighted medicine |
| **+ / −** | change the quantity of the selected line |
| **Delete** | remove the selected line |
| **Ctrl+Enter** | take payment |
| **Ctrl+H** | hold the bill (customer went to fetch money) |

**A named customer** — click *Customer…*. Needed only for credit, or when the
customer wants a running account.

**Credit / part payment** — choose the customer first, then enter less than the
total. The balance goes onto their account automatically. A walk-in customer
cannot be given credit; the program will say so.

**Changing a price or a discount on one line** — select the line, click *Edit
line…*. Only a manager or the owner can do this.

---

## 3. Returns — *Sales & returns* (**F8**)

Find the bill (search by invoice number or customer, or set the dates), select
it, then **Return goods…**. Enter how many units of each line are coming back.
The refund keeps the discount the customer originally got, and the units go
back into stock — untick *Put the returned units back into stock* if the
medicine cannot be sold again.

**Reprint a receipt**: select the bill and click *Reprint receipt*, or *Save as
PDF* to keep a copy.

**Cancel a whole bill**: owner only, and only for a mistake — the medicines go
back on the shelf and the bill disappears from the day's takings.

---

## 4. Buying — *Purchases* (**F6**)

When a supplier's delivery arrives, click **Enter supplier bill**:

1. Pick the supplier (or add a new one), type their bill number and date.
2. For each item: medicine, quantity in units, bonus units, batch number,
   expiry date, cost, trade discount, and the retail price you will sell at.
   Click **Add line** (or Ctrl+Enter).
3. Enter how much you paid now and click **Save & receive stock**.

Stock appears on the shelf immediately, batch by batch. Whatever you did not
pay stays on the supplier's account. Bonus (free) units are included in stock
and pull the average cost down, so the profit report stays honest.

To pay a supplier later: *Customers & suppliers → Suppliers → Pay supplier*.

---

## 5. Stock and expiry — **F4**

The view list at the top switches between everything in stock, **expiring
soon**, **already expired**, finished batches and all batches.

Make this a weekly routine:

1. Open **Expiring soon** (the window is 90 days by default, changeable in
   Settings). Return those batches to the supplier or move them to the front.
2. Open **Already expired**. Click **Write off expired** — every expired batch
   is taken off the shelf in one action, and each removal is recorded.
3. Look at the dashboard's *Medicines to reorder* card and order what is low.

**Adjust…** changes a batch's quantity when something is broken, lost, or the
count was wrong. A reason is required and it is kept forever — that is what
makes the stock figures trustworthy.

Expired medicines can never be sold: the counter screen refuses them.

---

## 6. Customers and suppliers — **F7**

Two tabs. Select an account and its full ledger appears on the right: every
bill, every payment, and the running balance.

- **Receive payment** (customers) / **Pay supplier** — records the money and
  updates the balance.
- **Print statement** — a printable copy of the ledger to hand over.
- An account with bills against it can never be deleted, only switched off.

---

## 7. Reports — **F9**

Pick a report on the left, pick the period, and the numbers appear. Every one
of them can be **printed** or **exported to CSV** (which opens in Excel).

| Report | Answers |
|---|---|
| Sales summary | what did we sell each day? |
| Invoice register | every bill in one list |
| Sales by medicine | what moves, what sits |
| Sales by counter staff | who sold what |
| Customer savings | how much discount we have given |
| Profit report | revenue less the cost of the batch actually sold |
| Sale returns | what came back, and why |
| Purchase register | what we bought and still owe |
| Day book | cash and bank movement, for closing the till |
| Stock adjustments | every correction, with the reason and the person |
| Stock valuation | what is on the shelf, at cost and at retail |
| Reorder list | what to order, and what it will cost |
| Expiry watch | what is about to expire |
| Customer / supplier balances | who owes whom |

**Closing the day**: *Day book* for the till, *Sales summary* for the takings.

---

## 8. Backups — *Settings → Backup & data*

A copy is taken automatically every time the program is closed, and the newest
20 are kept.

**Do this every week**: plug in a USB stick, click **Copy backup to…**, choose
the stick. A backup that lives on the same computer does not survive a broken
hard disk or a stolen machine.

**Restoring** replaces everything with the contents of the chosen backup. The
present data is copied aside first, but anything sold since that backup was
taken is gone. Close and reopen the program afterwards.

---

## 9. If something goes wrong

| What you see | What to do |
|---|---|
| "Incorrect username or password" | check Caps Lock; the owner can reset it in *Users* |
| The owner forgot the password | open Command Prompt and run: `"C:\Program Files\TenPercentPharmacy\TenPercentPharmacy.exe" --reset-admin "newpassword"` |
| "only N in stock (not expired)" | the shelf figure is lower than you thought, or the batch has expired — check *Stock & expiry* |
| "This medicine has no batch on file" | it has never been received; use *Receive stock* or a purchase bill |
| "The program is already running" | it is open on the taskbar; opening it twice could hand out the same invoice number twice |
| A price is wrong on new stock | the retail price on the purchase line updates the medicine — fix it in *Medicines* |
| Something crashed | the message shows the path of `pharmacy.log`; send that file to whoever supports the software |

Nothing here needs an internet connection. The program never sends your data
anywhere — it only reads and writes the one folder on this computer.
