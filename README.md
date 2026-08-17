# 10% Discount Pharmacy — Bonus Offer App

Broadcast tool for **10% Discount Pharmacy, Kahror Pakka**. The pharmacy owner
posts bonus offers ("buy 5 boxes, get 1 free") from a web dashboard; affiliated
medical stores see them in an Android app and get a push notification each time
a new one is published. Offers expire on their own.

No ordering, no cart, no payments, no stock tracking. English only.

```
┌──────────────────────┐        ┌───────────────────────────┐        ┌──────────────────────┐
│  Admin web dashboard │──────▶ │  Firebase                 │ ─────▶ │  Android app         │
│  (React, Firebase    │        │  Auth · Firestore ·       │  FCM   │  (Kotlin + Compose)  │
│   Hosting)           │ ◀──────│  Cloud Functions          │        │  store owners        │
└──────────────────────┘        └───────────────────────────┘        └──────────────────────┘
```

| Folder | What it is |
|---|---|
| `functions/` | Cloud Functions (TypeScript): account management, push notifications, daily expiry job |
| `web/` | Admin dashboard (React + Vite + TypeScript) |
| `android/` | Store owner app (Kotlin + Jetpack Compose) |
| `firestore.rules` | Security rules |
| `firestore.indexes.json` | Composite indexes |

---

## 1. Data model

**`users/{uid}`** — one document per account.

| Field | Type | Notes |
|---|---|---|
| `role` | `'admin'` \| `'store_owner'` | also mirrored as a custom auth claim |
| `username` | string | unique; what the store owner types to log in |
| `storeName`, `ownerName`, `phone`, `address` | string / null | `ownerName`, `phone`, `address` optional |
| `isActive` | boolean | deactivating also disables the Firebase Auth user |
| `fcmTokens` | string[] | one per device; the only field the app may write |
| `createdAt`, `updatedAt` | timestamp | |

**`bonusOffers/{id}`**

| Field | Type | Notes |
|---|---|---|
| `productName` | string | |
| `buyQty`, `freeQty` | int | "Buy 5 Get 1 Free" |
| `startDate`, `expiryDate` | string | `YYYY-MM-DD`, Asia/Karachi calendar dates |
| `status` | `'active'` \| `'expiring_soon'` \| `'expired'` | **written by the server only** |
| `createdBy` | uid | the admin who published it |
| `notifiedAt`, `notifiedCount` | timestamp / int | stamped after the push goes out |
| `createdAt`, `updatedAt` | timestamp | feed order is `createdAt` descending |

**`notificationsLog/{id}`** — `offerId`, `productName`, `title`, `body`,
`recipientCount`, `successCount`, `failureCount`, `sentAt`.

Dates are stored as plain calendar strings rather than timestamps: an offer
expires *on a day*, and a date string has no timezone edge cases.

### Offer lifecycle

```
Admin publishes offer ─▶ status = ACTIVE ─▶ push to every active store
                                │
                    daily job, 00:05 Asia/Karachi
                                │
        today ≥ expiry − 3 days ─▶ EXPIRING SOON (amber badge)
        today  >  expiry        ─▶ EXPIRED (greyed out, sinks to the bottom of the feed)
```

Status is computed **server-side** (`functions/src/status.ts`) and stamped onto
each document, so every phone shows the same badge no matter when it last
opened the app or what its clock says. Expired offers are kept, never deleted.

---

## 2. Firebase project setup (once)

1. Create a Firebase project at <https://console.firebase.google.com>.
   Pick a Firestore location near Pakistan (`asia-south1`) — it cannot be
   changed later.
2. Enable **Authentication → Sign-in method → Email/Password**.
3. Enable **Firestore Database** (production mode) and **Cloud Messaging**.
4. Cloud Functions requires the **Blaze** (pay-as-you-go) plan. At this scale
   usage sits inside the free allowance.
5. Put your project id in `.firebaserc`.

Install the CLI and log in:

```bash
npm install -g firebase-tools
firebase login
```

### Deploy the backend

```bash
cd functions && npm install && npm run build && cd ..
firebase deploy --only firestore:rules,firestore:indexes,functions
```

Functions deploy to **asia-south1** (`functions/src/index.ts`). The dashboard
must call the same region — that is what `VITE_FIREBASE_FUNCTIONS_REGION` does.

### Create the admin account

There is no self-registration anywhere, so the first admin is made with the
Admin SDK. Download a service account key
(*Project settings → Service accounts → Generate new private key*), then:

```bash
cd functions
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/serviceAccountKey.json
export FIREBASE_PROJECT_ID=your-project-id
npm run create-admin -- owner@example.com 'a-strong-password' 'Pharmacy Owner'
```

Keep that key file off the repo — it is git-ignored, and it can be deleted once
the admin exists. Re-running the script resets the admin's password.

---

## 3. Admin dashboard (`web/`)

```bash
cd web
cp .env.example .env      # fill in from Firebase console → Web app config
npm install
npm run dev               # http://localhost:5173
```

Deploy to Firebase Hosting:

```bash
firebase deploy --only hosting
```

Screens: **Dashboard** (active offers, offers expiring in 3 days, active
stores), **Bonus Offers** (create / edit / delete, filter by status),
**Store Owners** (add / edit / activate / deactivate), **Notification Log**.

Only accounts carrying the `admin` claim get in — a store owner signing in here
is signed straight back out.

Notes:
- Publishing an offer sends the push. Editing one does not re-notify.
- Expired offers cannot be edited (they are a record), but can be deleted.
- Deactivating a store logs it out, blocks its login, and clears its push
  tokens. Reactivating restores access with the same password.

---

## 4. Android app (`android/`)

Open the `android/` folder in Android Studio (Ladybug or newer). Requirements:
AGP 8.7, Kotlin 2.0, JDK 17, min SDK 24, target SDK 35.

Before the first build, register the app in Firebase
(*Add app → Android*, package name **`pk.tenpercent.pharmacy`**) and save the
downloaded `google-services.json` into `android/app/`. The build fails without
it; `android/app/google-services.json.example` shows the shape.

```bash
cd android
./gradlew assembleDebug        # APK in app/build/outputs/apk/debug/
```

### Getting an APK without Android Studio (verified working)

`.github/workflows/android-apk.yml` builds the APK on GitHub's runners and
attaches it to the run. Open **Actions → Build Android APK → Run workflow**,
then download the `pharmacy-bonus-app-debug` artifact when it finishes.

For an APK that reaches your Firebase project, add your `google-services.json`
as a repository secret first (*Settings → Secrets and variables → Actions*):

```bash
base64 -w0 google-services.json      # macOS: base64 -i google-services.json
# paste the output as a secret named GOOGLE_SERVICES_JSON
```

Without that secret the workflow still produces an installable APK, but it is
wired to a placeholder project and login will fail — useful for checking the
build and looking at the screens, not for real use.

### App icon

The launcher icon is the pharmacy logo itself. `design/pharmacy-logo.png` is
the source artwork; the Android assets are generated from it:

```bash
npm install sharp
node tools/generate-launcher-icons.mjs
```

That writes, for every density bucket, the legacy icon (`ic_launcher.png`,
API 24-25), the round variant, and the adaptive foreground layer
(`ic_launcher_foreground.png`, API 26+) which sits on a white background.
Re-run it whenever the artwork changes.

The logo is scaled to 68 of the adaptive icon's 108dp canvas, so it fills a
circular launcher mask almost exactly while keeping the gold ring clear of
tighter masks. Android 13+ themed icons use a mortar-and-pestle silhouette
(`drawable/ic_launcher_monochrome.xml`) — a themed icon is recoloured to match
the wallpaper, so it has to be one flat shape.

One caveat worth knowing: a launcher icon is drawn at roughly 48dp on a phone.
At that size the "PHARMACY" wordmark, the "10% DISCOUNT" badge and the Urdu
tagline are not readable — the badge shape and the green/gold colouring are
what identify the app. That is expected for a detailed logo used as an icon,
not a bug.

---

## 5. Security model

- **Admin**: custom claim `role=admin`. Reads everything, writes offers
  directly, manages store accounts through callable functions (creating Auth
  users needs the Admin SDK).
- **Store owner**: custom claim `role=store_owner`. Reads offers and its own
  user document. The only thing it can write anywhere is its own `fcmTokens`.
- Offer `status` is never accepted from a client as authoritative — the daily
  job and the edit trigger overwrite it.
- Deactivation disables the Auth user and revokes refresh tokens, so the app is
  signed out within the hour rather than staying live until it restarts.

---

## 6. Running locally with the emulators

```bash
cd functions && npm run build && cd ..
firebase emulators:start          # UI at http://localhost:4000
```

Then set `VITE_USE_EMULATORS=true` in `web/.env` and run `npm run dev`.
Seed an admin against the Auth emulator with `FIRESTORE_EMULATOR_HOST` and
`FIREBASE_AUTH_EMULATOR_HOST` set.

## 7. Tests

```bash
cd functions
npm test                  # date/status logic, no emulator needed        (9 tests)
npm run test:rules        # security rules                              (10 tests)
npm run test:integration  # the daily expiry job                         (4 tests)
npm run test:callables    # store account management, login end to end   (6 tests)
npm run test:triggers     # notification log + status sync on edit       (2 tests)

cd ../web
npm run build             # typecheck + bundle
```

The emulator suites start and stop the emulators themselves; the first run
downloads the Firestore emulator. All 31 tests pass as of this commit.

What the emulators cannot cover: actual FCM delivery needs real credentials, so
`test:triggers` exercises the publish path with no registered devices. Send a
test offer to a real phone once the project is deployed.

The Android app is built by the `Build Android APK` workflow on every push to
the feature branch, which is also what verifies it compiles — the container
these files were written in has no Android SDK.

---

## 8. Deliberately out of scope

In-app ordering, cart or payments · store self-registration · multiple staff
logins per store · product catalog, inventory or stock levels · Urdu · iOS.
