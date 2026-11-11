# عملیات میدانی: جمع‌آوری و انطباق داده‌ها
# Operations: data collection, registration and practical use

> فارسی اول، سپس English.

---

## فارسی

### ۱) چرخه کاری کلی

```
رسم محدوده روی نقشه (۳–۱۰ رأس)
        │
        ├─► اعتبارسنجی محلی داخل اپ (آفلاین، فوری)
        │
        ├─► POST /api/v1/regions/validate        ← اعتبارسنجی سمت سرور (shapely)
        │
        ├─► POST /api/v1/regions/catalog-search  ← فراداده سنتینل-۲ L2A (کوپرنیکوس)
        │
        └─► POST /api/v1/regions/terrain-indicators ← تحلیل واقعی DEM (کاشی‌های Terrarium)
```

هر پاسخ شامل **provenance** (خاستگاه داده) و **caveats** (تذکرهای علمی) است؛ هیچ عددی
بدون ذکر منبع و رزولوشن نمایش داده نمی‌شود.

### ۲) اجرای بک‌اند — چهار گزینه عملی

**گزینه A — رایانه در همان شبکه Wi-Fi (سریع‌ترین شروع):**

```bash
cd backend && python -m venv .venv
source .venv/bin/activate            # ویندوز: .venv\Scripts\activate
pip install -e ".[dev]"
uvicorn subsurface_api.main:app --host 0.0.0.0 --port 8000
```

سپس در اپ → تنظیمات → آدرس API: `http://<IP رایانه>:8000/`
(IP را با `ip addr` در لینوکس یا `ipconfig` در ویندوز بگیرید؛ فایروال پورت ۸۰۰۰ را باز کنید.)

**گزینه B — کابل USB بدون شبکه (ADB reverse):**

```bash
adb reverse tcp:8000 tcp:8000
```

سپس آدرس اپ: `http://127.0.0.1:8000/` — روی شبیه‌ساز هم همین آدرس پیش‌فرض است
(شبیه‌ساز: `10.0.2.2` = حلقه برگشت میزبان).

**گزینه C — همان گوشی با ترموکس (کاملاً مستقل از رایانه):**

```bash
pkg install -y python git
pip install --upgrade pip
git clone <ریپوی شما> ~/subsurf && cd ~/subsurf/backend
pip install -e .
uvicorn subsurface_api.main:app --host 127.0.0.1 --port 8000
```

در اپ آدرس `http://127.0.0.1:8000/` را بدهید. (نمونه‌برداری DEM روی گوشی جواب می‌دهد
ولی کندتر است؛ برای محدوده‌های کوچک عالی است.)

**گزینه D — سرور شخصی با HTTPS (برای استفاده دائمی/چند نفره):**

بک‌اند را روی VPS اجرا کنید و جلوی آن Caddy/Traefik بگذارید تا TLS خودکار بگیرد:

```
subs.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

سپس در اپ: `https://subs.example.com/` — توصیه‌شده برای استفاده بلندمدت.

**گزینه E — رانفلر (RunFlare)؛ سکوی ابری ایرانی با پلن رایگان:**

ثبت‌نام حقیقی در [runflare.com](https://runflare.com) رایگان است و کارت بانکی بین‌المللی نمی‌خواهد —
برای کاربر ایرانی عملی‌ترین سکوی ابری بدون تحریم است. پلن رایگان: ۳ GB RAM، ۱.۵ GHz CPU،
۳ GB دیسک، ترافیک نامحدود، ۲ دیپلوی. محدودیت‌ها: خوشهٔ غیر-پروداکشن، بدون بکاپ،
**اعتبار ۳ ماهه** (پس از آن سرویس حذف می‌شود ولی می‌توانید دوباره بسازید).

دو روش دیپلوی (ریپو شامل `backend/Dockerfile` است و `$PORT` را رعایت می‌کند):

1. **Docker (پیشنهادی):** در داشبورد رانفلر برنامهٔ Docker بسازید و ریپوی گیت‌هاب را وصل کنید
   (دیپلوی خودکار با هر push) یا با CLI:
   ```bash
   /bin/bash -c "$(curl -fsSL https://get.runflare.com/install.sh)"
   cd backend && runflare deploy
   ```
2. **Python:** برنامهٔ Python بسازید با دستور شروع:
   `uvicorn subsurface_api.main:app --host 0.0.0.0 --port $PORT`

سپس «دامنهٔ موقت» (Temporary domain) را فعال کنید و آدرس `https` آن را در تنظیمات اپ بدهید.
برای مصرف دادهٔ API بسیار کم است (فراداده + کاشی‌های DEM)؛ پلن رایگان کاملاً کافی است.

### ۳) گردش کار داخل اپ (قدم‌به‌قدم)

1. زبانه **نقشه**: با هر ضربه یک رأس اضافه می‌شود (۳ تا ۱۰ رأس). دکمه‌های «برگرداندن/پاک کردن».
   کارت بالای نقشه تعداد رأس‌ها و مساحت ژئودزیک زنده را نشان می‌دهد.
2. دکمه **تحلیل**: اول اعتبارسنجی محلی، بعد سرور؛ اگر محدوده معتبر باشد بلافاصله
   جستجوی کاتالوگ (۹۰ روز اخیر، ابر ≤ ۳۰٪، حداکثر ۱۲ محصول) انجام می‌شود و اپ به زبانه
   **نتایج** می‌پرد.
3. زبانه **نتایج**:
   - کارت اعتبارسنجی: وضعیت، مساحت (هکتار)، محیط، خطاها/هشدارها؛
   - کارت محصولات سنتینل-۲: نام، تاریخ، درصد ابر، حجم — برای انتخاب صحنه کم‌ابر؛
   - کارت شاخص‌های زمینی: دکمه محاسبه (چند ثانیه تا ~دقیقه بسته به اندازه محدوده)؛
   - کارت‌های خاستگاه و تذکرهای علمی.
4. نمره «ناهنجاری سطح» خروجی ترکیبی شفاف است — اجزایش با وزن‌ها در همین پاسخ می‌آید.

### ۴) انطباق/ثبت داده‌ها (Registration) چگونه انجام می‌شود؟

منابع مختلف، شبکه‌های مرجع متفاوتی دارند؛ برای مقایسه‌پذیری همه چیز روی یک شبکه مشترک
نمونه‌برداری می‌شود:

| منبع | شبکه مرجع بومی | انطباق در این پروژه |
|---|---|---|
| کاشی‌های DEM (Terrarium) | Web Mercator، کاشی ۲۵۶×۲۵۶ در zoom z | نمونه‌برداری دوبیلی از فضاپیکسل‌های مرکاتور روی شبکه منظم lat/lon 256×256 روی bbox محدوده |
| فراداده سنتینل-۲ | ردپای جغرافیایی (GeoJSON) | فیلتر هندسی `OData.CSC.Intersects` با WKT — بدون بازتابانی |
| هندسه کاربر | WGS84 (lon/lat درجه) | نرمال‌سازی حلقه + مساحت/محیط ژئودزیک (کره با R=6378137) |

- **رزولوشن مؤثر:** DEM در عرض جغرافیایی میانی ≈ `156543 × cos(lat) / 2^z` متر بر پیکسل است
  و در پاسخ API گزارش می‌شود (مثلا حدود ۹٫۵ متر در zoom ۱۳ نزدیک استوا). در محدوده‌های بزرگ
  زوم خودکار کوچک می‌شود تا سقف ۶۴ کاشی حفظ شود — این محدودیت در پاسخ (zoom،
  tiles_fetched، resolution) قابل مشاهده است.
- **نان‌دیتا:** کاشی‌های دریایی/۴۰۴ به‌عنوان «فاقد داده» شمرده می‌شوند و نسبتشان
  (`nodata_fraction`) گزارش می‌شود؛ آمارها از داده معتبر محاسبه می‌گردد.
- **همه‌چیز ثبت می‌شود:** تاریخ/ساعت دریافت، نام ارائه‌دهنده، مجموعه، مجوز، zoom و
  تعداد کاشی در `provenance` هر پاسخ می‌آید — پس نتایج قابل استناد و تکرارپذیرند.

### ۵) معنای شاخص‌ها و «تشخیص واقعی»

- **آنچه واقعاً محاسبه می‌شود:** آمار ارتفاع، شیب هورن، زبری TRI، جهت غالب گرادیان و
  انسجام آن، و نمره ترکیبی شکل زمین.
- **آنچه محاسبه نمی‌شود و نباید هم بشود:** عمق، نوع هدف، «وجود فلز/تونل/حفره».
  داده‌های ماهواره‌ای/DEM به‌تنهایی مدرک دفن‌شدگی نیستند؛ این محدودیت فیزیکی داده است،
  نه سخت‌گیری نرم‌افزار.
- **مسیر درست برای «تشخیص واقعی»:** شاخص‌های سطحی → اولویت‌بندی نواحی → تأیید زمینی با
  ژئوفیزیک (مگنت‌سنجی، EMI، GPR) طبق قوانین محلی. اپ داده‌های قابل استناد برای همان
  اولویت‌بندی می‌دهد؛ ادعای بیشتر علم‌گرایی نیست.

### ۶) رفع اشکال

| نشانه | علت محتمل | راه‌حل |
|---|---|---|
| «Error: Failed to connect» | بک‌اند روشن نیست / آدرس غلط | گزینه‌های بخش ۲؛ در تنظیمات تست اتصال بزنید |
| خطای کاتالوگ HTTP 429/502 | شلوغی سرویس کوپرنیکوس | چند ثانیه بعد دوباره «تحلیل» |
| DEM خیلی درشت | محدوده بزرگ است | محدوده کوچک‌تر (تا زیر ۱۰۰ km²) رسم کنید |
| `nodata` زیاد | ناحیه دریایی/مرزی | طبیعی است؛ نسبت گزارش می‌شود |
| نصب APK «App not installed» | امضای متفاوت با نسخه قبلی | نسخه قبلی را حذف و دوباره نصب کنید |

---

## English

### 1) End-to-end flow

Sketch (3–10 taps) → local validation → server validation → Sentinel-2 L2A catalog
metadata (last 90 days, ≤30 % cloud, ≤12 products) → optional open-DEM terrain
indicators. Every response carries provenance and caveats; nothing is shown without
its source and resolution.

### 2) Backend deployment options

* **A — LAN PC:** `uvicorn subsurface_api.main:app --host 0.0.0.0 --port 8000`, then set
  the in-app base URL to `http://<PC-IP>:8000/`.
* **B — USB only:** `adb reverse tcp:8000 tcp:8000` → use `http://127.0.0.1:8000/`.
* **C — the phone itself (Termux):** `pkg install python git`, `pip install -e backend`,
  run uvicorn on `127.0.0.1:8000`, point the app there. Fully offline workflow.
* **D — VPS + HTTPS:** run behind Caddy/Traefik with automatic TLS and set
  `https://your.host/` in Settings. Recommended for durable use.
* **E — RunFlare (Iranian platform, free tier):** sign up at runflare.com (individual account,
  no international card). Free tier: 3 GB RAM / 1.5 GHz CPU / 3 GB disk / unlimited traffic /
  2 deployments — non-production cluster, no backups, **3-month validity** (recreatable).
  Deploy as a Docker app from your GitHub repo (auto-deploy on push) or with the CLI
  (`bash -c "$(curl -fsSL https://get.runflare.com/install.sh)"` then `cd backend && runflare deploy`);
  the repo's `backend/Dockerfile` honours `$PORT`. Or create a Python app with start command
  `uvicorn subsurface_api.main:app --host 0.0.0.0 --port $PORT`. Enable the temporary domain
  and point the app at its `https` URL. API traffic is tiny (metadata + DEM tiles), so the free
  tier is comfortably enough.

### 3) Data registration (alignment) summary

* DEM tiles (Web Mercator) are bilinearly resampled onto a regular 256×256 lat/lon grid
  over the region bbox — the common reference grid for all terrain metrics.
* Effective DEM resolution ≈ `156543 × cos(lat) / 2^z` m/px and is reported per response;
  the zoom auto-drops (z14 → z8) so the tile budget (≤ 64 tiles) holds.
* Missing/ocean tiles count into `nodata_fraction`; statistics use valid samples only.
* Catalog search never reprojects — it filters footprints geometrically with
  `OData.CSC.Intersects(area=geography'SRID=4326;POLYGON(...))`.
* Every response embeds provider, collection, licence note and retrieval timestamp.

### 4) Realistic expectations

Terrain indicators (elevation stats, Horn slope, Riley TRI, gradient-orientation
consistency, weighted surface score) are genuine, reproducible **surface** measurements.
They prioritise interesting areas; they are **not** evidence of buried objects. Field
confirmation with EMI / magnetometry / GPR — within local law — is the only path to
ground truth. See `docs/SCIENCE-SCOPE.md` for the exact scoring definition.

### 5) Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| "Failed to connect" | backend not running / wrong URL | options above; use Test connection |
| Catalog HTTP 429 / 502 | Copernicus service busy | retry after a few seconds |
| Coarse DEM | region too large | sketch < 100 km² |
| High `nodata_fraction` | sea/edge coverage | expected, reported honestly |
| "App not installed" | different signing key | uninstall previous app first |
