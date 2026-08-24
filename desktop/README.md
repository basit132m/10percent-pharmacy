# Ten Percent Discount Pharmacy — desktop software

Offline management software for the pharmacy counter, for Windows.

Everything runs on the shop's own computer: one SQLite file, no server, no
internet, no monthly fee. The standard **10% discount is applied to every line
of every bill automatically** — the rate is a setting, not something buried in
the code.

```
┌───────────────────────────────────────────────────────────────────┐
│  TenPercentPharmacy.exe   (PySide6 / Qt 6 desktop app)            │
│                                                                   │
│   ui/        screens: counter sale, medicines, stock, purchases,  │
│              customers & suppliers, sales & returns, reports,     │
│              users, settings  ·  receipt & report printing        │
│   core/      no Qt at all: money, dates, database, services       │
│              (auth · catalog · inventory · sales · purchases ·    │
│               parties · reports · backup · audit)                 │
└──────────────────────────────┬────────────────────────────────────┘
                               │
              %LOCALAPPDATA%\TenPercentPharmacy\
                  pharmacy.db          the whole shop
                  backups\             automatic copies
                  exports\             CSV and PDF you saved
                  pharmacy.log         what happened, for support
```

The split matters: `core/` holds every rule about money and stock and can be
tested without a screen, which is why the arithmetic has tests and the UI is
thin.

---

## 1. Installing it in the shop

1. Open the repository's **Actions → Build Windows desktop app** and download
   the **TenPercentPharmacy-Setup** artifact from the latest green run
   (or build it yourself, section 4).
2. Unzip it and run `TenPercentPharmacy-Setup-1.0.0.exe`.
3. Start the program from the desktop shortcut.
4. Sign in as **admin** / **admin123**. It immediately asks for a new password —
   choose one and write it down somewhere safe.

Then follow [USER-MANUAL.md](USER-MANUAL.md), which is written for the people
behind the counter rather than for programmers.

Windows 10 or 11, 64-bit. Nothing else to install — Python and Qt are inside
the program folder.

---

## 2. Running from source (development)

```bash
cd desktop
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt     # Windows: .venv\Scripts\pip
.venv/bin/python run.py
```

Useful switches:

```bash
python run.py --seed-demo          # 40 medicines, 2 supplier bills, ~90 sales
python run.py --data-dir ./sandbox # keep the database out of the real folder
python run.py --self-check         # open the database, print a line, exit
python run.py --reset-admin "newpassword"   # the owner is locked out
```

On Linux the Qt runtime needs a few system libraries:
`sudo apt-get install libegl1 libxkbcommon0 libfontconfig1 libdbus-1-3`.

---

## 3. Tests

```bash
cd desktop
.venv/bin/python -m pytest tests -q        # 78 tests, about 12 seconds
.venv/bin/python -m pyflakes pharmacy_desktop tests
```

The suite covers the parts where a mistake costs money: paisa arithmetic and
the 10% discount, FEFO batch picking, expiry, credit ledgers, returns, backup
and restore, and every report. The UI tests run Qt headless
(`QT_QPA_PLATFORM=offscreen`) and build all ten screens, add and remove lines on
the counter screen, and render receipts to PDF — so a broken signal or a missing
column fails in CI rather than in the shop.

---

## 4. Building the Windows program

On a Windows machine with Python 3.12 and
[Inno Setup 6](https://jrsoftware.org/isdl.php):

```powershell
cd desktop
.\packaging\build_windows.ps1
```

That runs the tests, generates the multi-size `app.ico` from the pharmacy logo,
bundles the program with PyInstaller, and compiles the installer:

| Output | What it is |
|---|---|
| `dist\TenPercentPharmacy\TenPercentPharmacy.exe` | the program, one folder, portable |
| `packaging\output\TenPercentPharmacy-Setup-1.0.0.exe` | the installer |

`.github/workflows/windows-desktop.yml` does exactly the same on GitHub's
Windows runners on every push — that is what verifies the build, since the
container these files were written in has no Windows.

A one-folder build (rather than one big .exe) is deliberate: it starts in about
a second instead of unpacking itself on every launch, and antivirus software
treats it far more kindly.

---

## 5. Where the data lives

| Path | Contents |
|---|---|
| `%LOCALAPPDATA%\TenPercentPharmacy\pharmacy.db` | everything — stock, sales, customers, users |
| `…\backups\` | automatic copy on every close, newest 20 kept |
| `…\exports\` | CSV and PDF files you save |
| `…\pharmacy.log` | a log to send if something goes wrong |

Uninstalling leaves that folder alone, so the records survive a reinstall.
Copy it (or a file from `backups\`) to a USB stick weekly — a backup on the
same disk is not a backup.

## 6. Design notes worth knowing

- **Money is integer paisa everywhere.** Floats cannot represent 0.1, and a
  shop that gives 10% off a hundred times a day would drift. Conversion happens
  only where a human types or reads an amount (`core/money.py`).
- **Stock is held per batch, never as one number.** A recall or an expiry
  notice is about a batch, and selling has to take the batch that expires first
  (FEFO). `core/services/inventory.py` owns that rule; the counter screen just
  shows the result.
- **Prices are copied onto the batch and onto the invoice line.** Raising a
  price tomorrow never rewrites what yesterday's customer paid.
- **A sale is one transaction.** Invoice, lines, stock movements and the
  customer's ledger are written together or not at all, so a power cut cannot
  half-sell a box.
- **Dates are `YYYY-MM-DD` strings.** They sort correctly in SQL, read
  correctly in a backup, and a medicine expires on a day — there is no timezone
  in that.
- **Roles, not honour.** A cashier can sell; changing a price, a discount, the
  stock or the settings needs a manager or the owner. Everything anyone does is
  written to the activity log.
