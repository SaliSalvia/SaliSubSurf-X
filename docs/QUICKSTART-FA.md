# راهنمای شروع سریع (فارسی)

> این سند کوتاه‌ترین مسیر «زیپ → ریپوی خالی → APK آماده نصب» را قدم‌به‌قدم نشان می‌دهد.
> **سریع‌ترین مسیر (پیشنهادی):** زیپ را در پوشه‌ی Download گوشی بگذارید و فقط این را اجرا کنید:
> `bash salisurf-x-deploy.sh` — ساخت ریپو، پوش، کلید امضای تعاملی، ریلیز و دانلود APK، همه یک‌جا.
> جزئیات کامل‌تر: `README.md`، `docs/SIGNING-TERMUX.md` (امضای شخصی)،
> `docs/OPERATIONS.md` (اجراهای مختلف بک‌اند و گردش کار داده)، `docs/SCIENCE-SCOPE.md` (معنای شاخص‌ها).

---

## ۰) پیش‌نیازها

| نیاز | توضیح |
|---|---|
| **Termux** | از [F-Droid](https://f-droid.org/packages/com.termux/) یا GitHub Releases نصب کنید (نسخهٔ Play Store قدیمی است) |
| **اکانت GitHub** | رایگان؛ ریپوی **Public** بسازید تا Actions بدون محدودیت اجرا شود |
| اینترنت روی گوشی | برای push و اجرای Actions |

> **نکتهٔ مهم دربارهٔ آپلود وبی:** اگر پوشه را با «Add file → Upload files» در سایت گیت‌هاب آپلود کنید،
> پوشه‌های مخفی مثل `.github/` **آپلود نمی‌شوند** و ورک‌فلو ساخته نمی‌شود! دو راه‌حل:
> راه A (پیشنهادی): از اسکریپت `scripts/upload-to-github.sh` با `git` استفاده کنید — همه‌چیز دست‌نخورده می‌رود.
> راه B: بعد از آپلود وبی، دو فایل پوشهٔ `github-workflow-backup/` این زیپ را دستی در گیت‌هاب
> با نام‌های `.github/workflows/android.yml` و `.github/workflows/backend.yml` بسازید (Add file → Create new file).

---

## ۱) گشودن زیپ در ترموکس

```bash
pkg update -y && pkg install -y unzip git
pkg install -y gh && gh auth login   # یک بار؛ برای مسیر خودکار لازم است
cd ~
unzip /sdcard/Download/SaliSurf-X-v1.5.0-clean.zip   # مسیر دانلود خودتان
cd SaliSurf-X
ls    # باید android/  backend/  docs/  scripts/  .github/  … را ببینید
```

## ۲) آپلود به ریپوی خالی جدید

ساده‌ترین راه: `bash salisurf-x-deploy.sh` — ریپوی `SaliSurf-X` را خودش می‌سازد و پوش می‌کند.

راه دستی: در گیت‌هاب ریپوی خالی جدیدی ساخته‌اید (مثلا `SaliSurf-X`). سپس:

```bash
# با توکن (پیشنهادی) — توکن را از Settings → Developer settings →
# Personal access tokens با دسترسی repo بسازید:
bash scripts/upload-to-github.sh https://<TOKEN>@github.com/USER/SaliSurf-X.git

# یا بدون توکن (اسم/رمز گیت‌هاب را می‌پرسد):
bash scripts/upload-to-github.sh https://github.com/USER/SaliSurf-X.git
```

## ۳) گرفتن APK

1. در گیت‌هاب تب **Actions** ریپو را باز کنید — ورک‌فلو «Android APK» خودکار اجرا شده است.
2. بعد از چند دقیقه (زمان سبز شدن علامت):
   - هر push به **main** خودکار یک **GitHub Release** (مثلا `v1.5.0`) با هر دو APK می‌سازد.
   - در همان run هم بخش **Artifacts** موجود است:
     - `SaliSurf-X-debug.apk` — همیشه هست، همیشه قابل نصب.
     - `SaliSurf-X-release-signed.apk` — اگر Secrets امضا را تنظیم کرده‌اید (بخش ۴).
3. APK را نصب کنید («نصب از منابع ناشناس» برای مرورگر/دانلودمنیجر فعال باشد).
4. برای نسخه‌ی بعدی: `versionName`/`versionCode` را در `android/app/build.gradle.kts` بالا ببرید و push کنید — ریلیز تازه با تگ جدید ساخته می‌شود.

## ۴) امضای شخصی (اختیاری اما توصیه‌شده)

فقط یک بار:

```bash
bash scripts/termux-sign.sh
```

این اسکریپت: `openjdk-17` و `gh` را نصب می‌کند، کلید RSA-4096 (۳۰ ساله) می‌سازد،
و ۴ Secret (`KEYSTORE_BASE64`, `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`) را در ریپو ثبت می‌کند.
از آن پس هر build، APK release **با امضای خود شما** می‌سازد.

راهنمای کامل‌تر + امضای دستی بدون Secrets: `docs/SIGNING-TERMUX.md`.

## ۵) اجرای بک‌اند (برای تحلیل واقعی)

اپ بدون بک‌اند فقط اعتبارسنجی محلی و رسم محدوده را می‌دهد؛ برای **جستجوی کاتالوگ Sentinel-2
و شاخص‌های زمینی واقعی** بک‌اند لازم است. گزینه‌ها:

**A) رایانه در همان Wi-Fi:**
```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -e . && uvicorn subsurface_api.main:app --host 0.0.0.0 --port 8000
```
سپس در اپ → تنظیمات → `http://<IP-رایانه>:8000/`

**B) همان گوشی با Termux (کاملاً مستقل):**
```bash
pkg install -y python git
pip install -e ./backend
uvicorn subsurface_api.main:app --host 127.0.0.1 --port 8000
```
سپس در اپ آدرس `http://127.0.0.1:8000/` را بدهید.

**C) رانفلر (RunFlare) — سکوی ابری ایرانی با پلن رایگان:**

| مشخصات پلن رایگان | مقدار |
|---|---|
| RAM / CPU | ۳ GB / ۱.۵ GHz |
| دیسک / ترافیک | ۳ GB / نامحدود |
| دیپلوی | ۲ عدد |
| اعتبار | **۳ ماه** (بعد از آن حذف می‌شود؛ دوباره قابل ساخت است) |
| مناسب برای | تست و توسعه (خوشهٔ غیر-پروداکشن، بدون بکاپ) |

ثبت‌نام حقیقی در `runflare.com` رایگان است و کارت بانکی بین‌المللی نمی‌خواهد. دو روش دیپلوی:
- **Docker** (ریپو شامل `backend/Dockerfile` است): برنامهٔ Docker بسازید و ریپوی گیت‌هاب را وصل کنید
  (اتصال GitHub/GitLab پشتیبانی می‌شود و با هر push خودکار دیپلوی می‌شود)، یا با CLI:
  ```bash
  /bin/bash -c "$(curl -fsSL https://get.runflare.com/install.sh)"
  cd backend && runflare deploy
  ```
- **Python**: دستور شروع را بدهید: `uvicorn subsurface_api.main:app --host 0.0.0.0 --port $PORT`

سپس «دامنهٔ موقت» را فعال کنید و آدرس https آن را در تنظیمات اپ وارد کنید.

> جایگزین‌های دیگر برای کاربر ایرانی: همین گزینهٔ B (Termux روی گوشی) صددرصد رایگان و بدون
> تحریم است؛ گزینهٔ A هم بدون سرویس بیرونی است. سکوهای رایگان بین‌المللی
> (Render/Railway/Fly و…) معمولاً کارت بین‌المللی می‌خواهند یا IP ایران را می‌بندند —
> برای شروع روی آن‌ها حساب نکنید. GitHub Actions روی ریپوی Public برای ساخت APK کاملاً کافی و آزاد است.

**D) سرور شخصی + HTTPS:** برای استفاده بلندمدت/چندنفره (ببینید `docs/OPERATIONS.md` گزینهٔ D).

## ۶) اولین استفاده از اپ

1. زبانهٔ **نقشه**: ۳ تا ۱۰ ضربه = رأس‌های محدوده. کارت بالا، تعداد رأس و مساحت زنده را نشان می‌دهد.
2. دکمهٔ **تحلیل** → اعتبارسنجی → جستجوی محصولات Sentinel-2 L2A (۹۰ روز اخیر، ابر ≤ ۳۰٪) → زبانهٔ نتایج.
3. کارت «شاخص‌های زمینی» → **محاسبه** → آمار ارتفاع/شیب/زبری + نمرهٔ ناهنجاری سطح + provenance + caveats.
4. تنظیمات: آدرس بک‌اند + تست اتصال.

## ۷) چه چیزی «واقعی» است؟

- ✅ فرادادهٔ Sentinel-2 از کاتالوگ رسمی کوپرنیکوس (بدون اکانت) — تاریخ/ابر/حجم/شناسهٔ محصولات.
- ✅ شاخص‌های زمینی از DEM عمومی (کاشی‌های Terrarium) — ارتفاع، شیب هورن، زبری TRI، جهت گرادیان.
- ✅ نمرهٔ ترکیبی «ناهنجاری سطح» با وزن‌های منتشرشده و provenance کامل.
- ⛔ ادعای «فلز/تونل/حفره در عمق X» — این‌ها از دل دادهٔ ماهواره‌ای/DEM در نمی‌آید؛
  تأیید نهایی همیشه با ژئوفیزیک میدانی (مگنت‌سنجی، EMI، GPR) است. اپ شما را صادقانه
  به سمت نواحی «جالب برای بررسی» هدایت می‌کند، نه به ادعای قطعی.

مسیر ارتقا (نسخه‌های بعدی): `docs/ROADMAP.md`.
