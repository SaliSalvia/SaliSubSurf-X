# ساخت امضای شخصی و انتشار APK — راهنمای کامل ترموکس
# Creating your own signing key and releasing the APK — complete Termux guide

> این راهنما دو زبانه است: فارسی اول، سپس English.
> This guide is bilingual: Persian first, then English.

> **میان‌بر:** برای کل مسیر (ساخت ریپو + پوش + کلید + ریلیز + دانلود APK) فقط
> `bash salisurf-x-deploy.sh` را اجرا کنید — این سند حالت دستی/گام‌به‌گام همان کار است.
> **Shortcut:** for the whole pipeline (repo + push + key + release + APK download) just run
> `bash salisurf-x-deploy.sh` — this document is the manual, step-by-step equivalent.

---

## فارسی

### ۰) پیش‌نیازها

- اپلیکیشن **Termux** (نسخه F-Droid یا GitHub Releases — نسخه Play Store قدیمی است و به‌روزرسانی نمی‌شود)
- یک اکانت رایگان GitHub
- internet روی گوشی

### ۱) نصب ابزارها

```bash
pkg update -y && pkg upgrade -y
pkg install -y openjdk-17 apksigner git
```

| ابزار | نقش |
|---|---|
| `openjdk-17` | شامل `keytool` برای ساخت کلید |
| `apksigner` | امضای APK (طرح امضای v2/v3 — همان چیزی که اندروید می‌خواهد) |
| `git` | آپلود پروژه (اختیاری، ولی توصیه‌شده) |

> **نکته درباره `zipalign`:** این ابزار در مخزن اصلی Termux بسته‌بندی نشده است و **لازم هم نیست**؛
> خروجی Releaseِ Gradle از قبل به‌صورت استاندارد align شده است. فقط اگر APK دست‌ساز خارج از Gradle
> دارید، روی یک PC آن را zipalign کنید و بعد امضا کنید.

### ۲) ساخت keystore (فقط یک بار در عمر اپ انجام دهید)

```bash
keytool -genkeypair -v \
  -keystore "$HOME/salisurf-x-release.keystore" \
  -alias salisurf-x \
  -keyalg RSA -keysize 4096 \
  -validity 10950 \
  -storetype PKCS12
```

توضیح پارامترها:

| پارامتر | معنی |
|---|---|
| `-keyalg RSA -keysize 4096` | کلید RSA قوی (۲۰۴۸ حداقل است؛ ۴۰۹۶ اضافه‌امنیتی) |
| `-validity 10950` | اعتبار ۳۰ سال — برای کل عمر اپ |
| `-storetype PKCS12` | فرمت استاندارد مدرن؛ در این حالت **رمز key با رمز keystore یکی است** |
| `-alias salisurf-x` | نام کلید داخل فایل |

در حین اجرا سؤال‌ها را پاسخ دهید:

1. **Keystore password** → یک رمز قوی انتخاب و در جای امن ذخیره کنید (دو بار پرسیده می‌شود).
2. **First and last name** → نام شما، مثلا `Sali Salvia`
3. **Organizational unit** → مثلا `Mobile`
4. **Organization** → مثلا `SaliSalvia`
5. **City / State / Country code** → مثلا `Tehran` / `Tehran` / `IR`

> ⚠️ **مهم:** این فایل `.keystore` و رمزش را هرگز از دست ندهید و هرگز commit نکنید.
> اگر کلید عوض شود، کاربران نمی‌توانند نسخه جدید را روی نسخه قبلی نصب کنند (امضا باید ثابت بماند).
> یک نسخه پشتیبان در جای امن (مثلا رمزشده در ابر شخصی) نگه دارید و از فایل حذف‌نشدن با
> `ls -l "$HOME/salisurf-x-release.keystore"` مطمئن شوید. ریپو هم `.gitignore` دارد که
> `*.keystore` و `*.jks` را مسدود می‌کند.

### ۳) کدگذاری keystore برای GitHub Secrets

```bash
base64 -w0 "$HOME/salisurf-x-release.keystore" > "$HOME/keystore.b64"
wc -c "$HOME/keystore.b64"   # حدود ۷ هزار کاراکتر برای کلید 4096 بیتی
```

### ۴) تنظیم Secrets در گیت‌هاب — دو روش

**روش A — از داخل ترموکس با `gh` (پیشنهادی):**

```bash
pkg install -y gh
gh auth login          # GitHub.com → HTTPS → Login with a web browser (یا token)
gh secret set KEYSTORE_BASE64 < "$HOME/keystore.b64"
gh secret set KEYSTORE_PASSWORD     # بعد Enter، رمز keystore را paste کنید
gh secret set KEY_ALIAS --body "salisurf-x"
gh secret set KEY_PASSWORD          # برای PKCS12 همان رمز keystore
```

**روش B — از وب:**

1. ریپوی خود را باز کنید → `Settings` → `Secrets and variables` → `Actions`
2. دکمه `New repository secret` را بزنید و این چهار مورد را بسازید:

| نام Secret | مقدار |
|---|---|
| `KEYSTORE_BASE64` | محتوای فایل `keystore.b64` (یک خط طولانی) |
| `KEYSTORE_PASSWORD` | رمز keystore |
| `KEY_ALIAS` | `sal-subsurf` |
| `KEY_PASSWORD` | همان رمز keystore |

### ۵) نتیجه: بیلد خودکار امضاشده

با وجود این ۴ Secret، ورک‌فلو `Android APK` در هر push:

1. `SaliSurf-X-debug.apk` (بدون امضای release — برای تست)
2. `SaliSurf-X-release-signed.apk` ← **با امضای شخصی شما**

را می‌سازد و در بخش Artifacts همان run قرار می‌دهد. هر push به شاخه‌ی `main` نیز خودکار یک
**GitHub Release** (تگ `v` + نسخه‌ی `versionName`، مثلا `v1.5.0`) با هر دو APK می‌سازد —
دیگر نیازی به زدن دستی تگ نیست (تگ `v*` همچنان ریلیز پین‌شده به همان تگ می‌دهد).

> اگر Secrets را تنظیم نکنید، ورک‌فلو همچنان کار می‌کند و به‌جای نسخه امضاشده،
> `SaliSurf-X-release-unsigned.apk` می‌دهد — بعد می‌توانید خودتان در ترموکس امضا کنید (بخش ۶).

### ۶) مسیر جایگزین: امضای دستی در ترموکس

اگر ترجیح می‌دهید keystore فقط روی گوشی خودتان بماند و به گیت‌هاب داده نشود:

```bash
# 1) APK بدون امضا را از Artifacts ریپو دانلود کنید، بعد در ترموکس:
cd ~/downloads   # یا مسیر دانلود شما

# 2) امضا (پیش از امضا هرگونه zipalign لازم نیست؛ خروجی Gradle تراز است):
apksigner sign \
  --ks "$HOME/salisurf-x-release.keystore" \
  --ks-key-alias salisurf-x \
  --ks-pass pass:YOUR_STORE_PASSWORD \
  --key-pass pass:YOUR_KEY_PASSWORD \
  --out SaliSurf-X-release-signed.apk \
  SaliSurf-X-release-unsigned.apk

# 3) تأیید امضا:
apksigner verify --print-certs --verbose SaliSurf-X-release-signed.apk
```

خروجی مورد انتظار: `Verifies` + نمایش گواهی (`CN=...`) شما. فایل امضاشده آماده نصب است:

```bash
pkg install -y openjdk-17   # در صورت نیاز
# نصب مستقیم: فایل را در فایل‌منیجر باز کنید، یا:
am start -a android.intent.action.VIEW -d "file:///path/SaliSurf-X-release-signed.apk" -t "application/vnd.android.package-archive"
```

### ۷) چک‌لیست نهایی انتشار

- [ ] `apksigner verify` روی فایل نهایی بدون خطا؟
- [ ] نصب روی گوشی واقعی موفق بود؟ (فعال بودن «نصب از منابع ناشناس» برای مرورگر/فایل‌منیجر)
- [ ] آیا اپ قبلی با کلید دیگری نصب بود؟ اول حذفش کنید (`Package Installer` → Uninstall)
- [ ] keystore + رمز + alias در جای امن ثبت شد؟
- [ ] ورژن اپ (`versionName` در `app/build.gradle.kts`) برای انتشار بعدی بالا رفت؟

---

## English

### 0) Prerequisites

- **Termux** (F-Droid or GitHub build — the Play Store build is outdated)
- A free GitHub account

### 1) Install the tools

```bash
pkg update -y && pkg upgrade -y
pkg install -y openjdk-17 apksigner git
```

`openjdk-17` provides `keytool`; `apksigner` signs with the modern v2/v3 APK signature
schemes. `zipalign` is not packaged for Termux and is **not needed** — Gradle release APKs
are already aligned; only zipalign non-Gradle APKs on a PC before signing.

### 2) Generate the keystore (do this once, keep it forever)

```bash
keytool -genkeypair -v \
  -keystore "$HOME/salisurf-x-release.keystore" \
  -alias salisurf-x \
  -keyalg RSA -keysize 4096 \
  -validity 10950 \
  -storetype PKCS12
```

* `-validity 10950` = 30 years; `-storetype PKCS12` = modern standard, key password equals
  the store password.
* Answer the prompts: password (twice), name, org unit, org, city/state/country.

> ⚠️ Back the keystore up in a safe place. Never commit it (`.gitignore` already blocks
> `*.keystore` / `*.jks` / `*.b64`). If you lose it, users cannot upgrade in place.

### 3) Base64-encode for GitHub Secrets

```bash
base64 -w0 "$HOME/salisurf-x-release.keystore" > "$HOME/keystore.b64"
```

### 4) Set the four repository secrets

Via `gh` in Termux:

```bash
pkg install -y gh
gh auth login
gh secret set KEYSTORE_BASE64 < "$HOME/keystore.b64"
gh secret set KEYSTORE_PASSWORD     # paste at prompt
gh secret set KEY_ALIAS --body "salisurf-x"
gh secret set KEY_PASSWORD          # = keystore password for PKCS12
```

Or via the web UI: *Settings → Secrets and variables → Actions → New repository secret*:
`KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`.

### 5) Result

Every push now produces `SaliSurf-X-debug.apk` **and** `SaliSurf-X-release-signed.apk`
in the run artifacts; every push to `main` also publishes a rolling **GitHub Release**
(tag `v` + `versionName`, e.g. `v1.5.0`) with both APKs attached — no manual tagging
needed (`v*` tags still pin a release to the tag). Without secrets the workflow still
succeeds and yields `SaliSurf-X-release-unsigned.apk`.

### 6) Alternative: sign locally in Termux

```bash
apksigner sign \
  --ks "$HOME/salisurf-x-release.keystore" \
  --ks-key-alias salisurf-x \
  --ks-pass pass:YOUR_STORE_PASSWORD \
  --key-pass pass:YOUR_KEY_PASSWORD \
  --out SaliSurf-X-release-signed.apk \
  SaliSurf-X-release-unsigned.apk

apksigner verify --print-certs --verbose SaliSurf-X-release-signed.apk
```

Expected: `Verifies` plus your certificate. Install the signed file from your file manager.

### 7) Release checklist

- [ ] `apksigner verify` passes on the final file
- [ ] Installs on a real device
- [ ] Old installs signed with a different key were uninstalled first
- [ ] Keystore, password and alias safely backed up
- [ ] `versionName` bumped for the next release
