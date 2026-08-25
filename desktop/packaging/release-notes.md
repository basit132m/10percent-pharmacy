# Ten Percent Discount Pharmacy — management software 1.0.0

Offline management software for the pharmacy counter, for Windows 10 and 11
(64-bit). Everything runs on the shop's own computer — no internet connection
is used or needed, and no data leaves the machine.

## Install

1. Download **TenPercentPharmacy-Setup-1.0.0.exe** below.
2. Run it. Windows will say *"Windows protected your PC"* because the file is
   not code-signed — click **More info → Run anyway**. (Code signing is a paid
   certificate that can be added later.)
3. Start the program from the desktop shortcut.
4. Sign in as **admin** with the password **admin123**. It will immediately ask
   you to choose your own password.

To try it before entering real stock: *Settings → Backup & data → Load sample
data* fills the program with 40 medicines and a week of sales.

## What it does

- **Counter sale** — scan a barcode or type a name; the 10% discount is applied
  to every line automatically. Held bills, change calculation, credit sales,
  receipts on an 80 mm thermal roll, A5 or A4.
- **Medicines** — full master list, import from an Excel/CSV file, per-unit
  pricing that shows what the shop keeps after the discount.
- **Stock & expiry** — quantities per batch, the batch expiring first is sold
  first, expired stock can never be sold, one-click write-off, adjustments that
  record who did it and why.
- **Purchases** — supplier bills received into batches, bonus units, trade
  discounts, returns to supplier.
- **Customers & suppliers** — credit ledgers, payments, printable statements.
- **Sales & returns** — reprint any bill, save as PDF, partial returns that
  refund the discounted price.
- **15 reports** — sales, profit, discount given, day book, stock valuation,
  reorder list, expiry watch, balances. All printable and exportable to Excel.
- **Users** in three roles, an activity log, automatic backups and restore.

The 10% rate is a setting, so a festival discount takes seconds to change.

## Your data

Everything lives in `%LOCALAPPDATA%\TenPercentPharmacy` — the database, the
automatic backups, and anything you export. Uninstalling leaves that folder
alone, so the records survive a reinstall.

**Copy a backup to a USB stick every week** (*Settings → Backup & data → Copy
backup to…*). A backup on the same computer does not survive a broken hard
disk.

## Before you rely on it

Run it alongside your present method for a week or two: enter the real medicine
list and opening stock, bill some real customers, do one supplier bill, one
return and one credit customer, then compare the *Day book* report against the
cash drawer at the end of a day.

The full guide for counter staff is
[USER-MANUAL.md](https://github.com/basit132m/10percent-pharmacy/blob/claude/pharmacy-management-software-1v211x/desktop/USER-MANUAL.md).
