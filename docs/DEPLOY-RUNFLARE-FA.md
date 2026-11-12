# استقرار بک‌اند SaliSurf-X در رانفلر (Runflare)

راهنمای کامل فارسی برای دیپلوی `backend/` روی پلتفرم ابری رانفلر.
منبع رسمی: https://docs.runflare.com (بخش FastAPI).

---

## گام ۰ — پیش‌نیازها

- حساب رانفلر (ایمیل + شماره موبایل، تأیید‌شده) → https://runflare.com
- فایل‌های بک‌اند (همین ریپو، پوشه `backend/`) شامل:
  - `requirements.lock` ← وابستگی‌های کاملاً قفل‌شده با hash (fastapi، uvicorn، numpy، …)؛ `requirements.txt` هم به همان اشاره می‌کند
  - `requirements-build.lock` ← setuptools قفل‌شده برای ساخت wheel (بدون حل وابستگی در زمان بیلد)
  - `Dockerfile` ← به `$PORT` احترام می‌گذارد + health check داخلی
  - پکیج `subsurface_api/` (شامل ماژول پردازش عمیق `deep/`)

---

## روش ۰ — اسکریپت خودکار (ترموکس، پیشنهادی)

اگر روی گوشی ترموکس دارید و `gh` به گیت‌هابتان وصل است، همه‌ی روش ۲ + تست سلامت را
یک اسکریپت انجام می‌دهد (پیدا کردن پروژه، commit، force-push به ریپوی متصل به
رانفلر، تأیید نشستن کامیت، و زیر نظر گرفتن سلامت با تشخیص دقیق):

```bash
# از هرجای ترموکس — اسکریپت خودش پروژه را پیدا می‌کند
bash scripts/salisurf-x-runflare.sh --git

# با پیش‌فرض‌ها (بدون هیچ پرسش):
bash scripts/salisurf-x-runflare.sh --git --yes

# اگر CLI رانفلر نصب دارید (روش ۱ خودکار):
bash scripts/salisurf-x-runflare.sh --cli
```

پرچم‌ها: `--repo SaliSubSurfX` (ریپوی مقصد) · `--domain https://…` (دامنه سرویس) ·
`--polls N` (تعداد تلاش سلامت) · `--yes` (بدون پرسش).

> پیش‌نیاز روش git: ریپو از قبل در پنل رانفلر به سرویس وصل باشد (روش ۲، گام‌های ۲–۴)
> و تیک «دریافت خودکار» روشن باشد؛ بعد هر push خودکار دیپلوی می‌شود.

---

## روش ۱ — دیپلوی با CLI (سریع‌ترین راه)

```bash
# نصب CLI (لینوکس/مک/Termux بدون proot)
/bin/bash -c "$(curl -fsSL https://get.runflare.com/install.sh)"

# ورود به حساب
runflare login

# از داخل پوشه backend (مسیر دیپلوی همان محتوای این پوشه است)
cd backend
runflare deploy          # در پایان سوال y/n لاگ زنده می‌پرسد
# دفعه‌های بعد بدون سوال:
# runflare deploy -y
```

## روش ۲ — دیپلوی از GitHub (پیشنهادی برای CI/CD)

1. وارد پنل رانفلر شوید → **مدیریت پروژه** → پروژه مورد نظر.
2. در صفحه جزئیات سرویس، روی **«اتصال به مخزن گیت»** کلیک کنید.
3. گزینه **«گیت هاب oAuth app»** → **«افزودن حساب»** → در GitHub روی
   **Authorize runflare cloud** → انتخاب دسترسی (همه ریپوها یا فقط
   `SaliSalvia/Sali-Subsurf`) → **Install & Authorize**.
4. برگردید به رانفلر → دوباره **oAuth app** → دکمه **اتصال** →
   ریپو و برنچ (`main`) را انتخاب و **ذخیره** کنید.
5. جلوی کامیت موردنظر **revert** بزنید تا همان کامیت مستقر شود.
6. تیک **«دریافت خودکار» (auto pull)** را بزنید — از این پس هر
   `git push` به‌صورت خودکار روی رانفلر مستقر می‌شود.

> روش کلاسیک (توکن): GitHub → Settings → Developer settings →
> Personal access tokens (classic) → فقط دسترسی `repo` → آدرس HTTPS ریپو +
> توکن را در «گیت هاب کلاسیک» رانفلر وارد کنید.

---

## تنظیمات سرویس (حیاتی)

### پورت

رانفلر روی Docker/Kubernetes است؛ در **تنظیمات شبکه** سرویس، پورت ورودی
دامنه (۸۰/۴۴۳) را به پورت برنامه داخل کانتینر وصل کنید:

| ورودی (دامنه) | پورت برنامه |
|---|---|
| 80 | 8000 (یا هر مقدار `$PORT` که رانفلر تزریق می‌کند — Dockerfile ما خودکار می‌خواند) |

دستور اجرا (اگر از نوع سرویس FastAPI/Python استفاده می‌کنید به‌جای Docker):

```
pip install -r requirements.lock && pip install -r requirements-build.lock && \
  SOURCE_DATE_EPOCH=1794182400 pip install --no-build-isolation --no-deps . && \
  uvicorn subsurface_api.main:app --host 0.0.0.0 --port $PORT
```

### متغیرهای محیطی و Secrets

در جزئیات سرویس → **Secrets / متغیر محیطی**:

| متغیر | الزامی؟ | توضیح |
|---|---|---|
| `PORT` | خودکار | پورتی که رانفلر به برنامه می‌دهد |
| `COPERNICUS_USERNAME` | برای حالت زنده | حساب رایگان https://dataspace.copernicus.eu |
| `COPERNICUS_PASSWORD` | برای حالت زنده | رمز همان حساب |
| `COPERNICUS_CLIENT_ID` / `COPERNICUS_CLIENT_SECRET` | جایگزین بالا | OAuth Client ساخته‌شده در پروفایل CDSE |
| `DEEP_API_KEY` | اختیاری | اگر تنظیم شود همه endpointهای deep هدر `X-API-Key` می‌خواهند (مقایسه constant-time) |
| `CORS_ORIGINS` | اختیاری | پیش‌فرض `*` ؛ برای استقرار عمومی دامنه‌های مجاز را با ویرگول بگذارید |
| `DEEP_DATA_DIR` | اختیاری | مسیر ذخیره خروجی‌ها (پیش‌فرض `./deep_jobs`) |

> ⚠️ **بدون اعتبارنامه Copernicus** فقط `mode: selftest` کار می‌کند؛
> `mode: live` خطای 503 با پیام راهنما برمی‌گرداند.

### دیسک (اختیاری ولی توصیه‌شده)

خروجی‌های deep (PNG/GeoTIFF) روی دیسک محلی نوشته می‌شوند. برای ماندگاری
بین ری‌استارت‌ها، از بخش **«ساخت دیسک جدید»** یک دیسک وصل کنید و
`DEEP_DATA_DIR` را روی مسیر همان دیسک بگذارید.

---

## تست بعد از دیپلوی

```bash
BASE="https://<دامنه-سرویس-شما>"

# 1) سلامت
curl -s "$BASE/api/v1/health"

# 2) قابلیت‌ها (live_mode_available باید true شود اگر اعتبارنامه دادید)
curl -s "$BASE/api/v1/deep/capabilities"

# 3) خودآزمایی کامل پایپ‌لاین بدون نیاز به حساب (چند ثانیه)
curl -s -X POST "$BASE/api/v1/deep/selftest?grid=160"

# 4) شروع یک تحلیل واقعی
curl -s -X POST "$BASE/api/v1/deep/analyze" \
  -H 'Content-Type: application/json' \
  -d '{"polygon":[[52.50,29.55],[52.70,29.55],[52.70,29.70],[52.50,29.70]],
       "date_from":"2026-06-01","date_to":"2026-11-07",
       "grid":512,"model":"pca","mode":"live"}'
# → job_id بگیرید، بعد:
#   GET  $BASE/api/v1/deep/jobs/<job_id>          (وضعیت/درصد)
#   GET  $BASE/api/v1/deep/jobs/<job_id>/result   (گزارش)
#   GET  $BASE/api/v1/deep/jobs/<job_id>/files/overlay.png

# 5) کنسول مرورگر:  https://<دامنه>/deep-console
```

## حساب‌های API و ثبت‌نام Copernicus (CDSE)

اکانت‌هایی که برای داده ماهواره‌ای لازم/مفید است:

| سرویس | لینک ثبت‌نام | کاربرد در SaliSurf-X |
|---|---|---|
| **CDSE (Copernicus Data Space)** | https://dataspace.copernicus.eu (Login → Register) | Sentinel-1/2، SMOS شوری سطح — هسته‌ی حالت live |
| CDSE OAuth Client | https://shapps.dataspace.copernicus.eu/dashboard/ ← User Settings ← OAuth clients | جفت client_id/secret برای `COPERNICUS_CLIENT_*` |
| Copernicus Marine (اختیاری) | https://marine.copernicus.eu | L3 شوری/دما در صورت نیاز آینده |
| NASA Earthdata (اختیاری) | https://urs.earthdata.nasa.gov | SRTM/DEM مکمل |
| AWS Terrain Tiles | بدون اکانت — https://s3.amazonaws.com/elevation-tiles-prod | terrain خودکار، همین حالت کار می‌کند |

تنظیمات بهینه ثبت‌نام CDSE برای شما (ریسرچر):

1. با **همان نامی که در ORCID** (0009-0008-7236-9241) ثبت می‌کنید ثبت‌نام کنید —
   هویت پژوهشی یکدست می‌ماند و برای Access Token بلند‌مدت مهم است.
2. **Two-Factor Authentication** را در پروفایل فعال کنید.
3. در `shapps` (لینک بالا) یک **OAuth Client** با flow «Client Credentials» بسازید؛
   secret فقط یک بار نشان داده می‌شود — همان لحظه ذخیره کنید.
4. دو مقدار را در پنل رانفلر (Secrets سرویس) به‌جای username/password بگذارید:
   `COPERNICUS_CLIENT_ID` و `COPERNICUS_CLIENT_SECRET`.

تست سریع توکن (در ترموکس):

```bash
curl -s -X POST "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=$COPERNICUS_CLIENT_ID" \
  -d "client_secret=$COPERNICUS_CLIENT_SECRET" | head -c 300
```

---

## رفع اشکال: خطای «No tile had ≥4 usable scenes» در حالت live

این پیام یعنی پایپ‌لاین هیچ تایلی با حداقل ۴ سکن قابل‌استفاده پیدا نکرده. در نسخه‌های
قبل از v1.6.3 این پیام می‌توانست گمراه‌کننده باشد؛ دو علت ممکن است:

1. **رفض API (v1.6.2 و قبل‌تر — رفع‌شده)**: evalscript دو-ورودیِ Process API توسط CDSE
   رد می‌شد («Script failed to return») و همه‌ی فراخوانی‌ها شکست می‌خوردند. از v1.6.3
   هر ۸ باند در یک شیء واحد در `input` آمده‌اند و مشکل رفع شده است. اگر باز هم همه‌ی
   فراخوانی‌ها رد شوند، پیام خطا جدید صریح می‌گوید «Process API failed for every
   requested date» — آن‌وقت اعتبارنامه/سهمیه را چک کنید.
2. **داده‌ی واقعی کم**: پنجره‌ی زمانی خیلی کوتاه یا ابری. راه‌حل: بازه را عریض‌تر
   کنید (۴–۶ ماه)، `max_cloud_percent` را به ۳۰–۴۰ برسانید، یا `min_valid_fraction`
   را به ۰٫۴۵ پایین بیاورید.

از v1.6.3 پایپ‌لاین قبل از دانلود پیکسل‌ها، **کاتالوگ بی‌نام OData** را می‌پرسد که
کدام تاریخ‌ها واقعاً سکن L2A کم‌ابر دارند و فقط همان‌ها را (به‌طور یکنواخت در طول
پنجره پخش‌شده) واکشی می‌کند — سریع‌تر و قابل‌پیش‌بینی‌تر. برای پیش‌آگاهی می‌توانید
خودتان کاتالوگ را بپرسید:

```bash
curl -s "https://catalogue.dataspace.copernicus.eu/odata/v1/Products?\$filter=Collection/Name%20eq%20'SENTINEL-2'%20and%20OData.CSC.Intersects(area=geography'SRID=4326;POLYGON((51.20%2035.60,51.25%2035.60,51.25%2035.65,51.20%2035.65,51.20%2035.60))')%20and%20ContentDate/Start%20ge%202026-06-01T00:00:00Z%20and%20ContentDate/Start%20le%202026-09-30T23:59:59Z&\$expand=Attributes&\$top=200" | python3 -m json.tool | head -50
```

---

## رفع اشکال: صفحه‌ی «Runflare default webpage»

اگر دامنه‌تان این صفحه را نشان می‌دهد، پاد فعال است ولی **اپ build نشده**. سه علت:

1. **Dockerfile در ریشه ریپو نیست** — رانفلرِ متصل به گیت، ریشه ریپو را build می‌کند؛
   از v1.6.2 یک `Dockerfile` ریشه‌ای در ریپو هست (و `backend/Dockerfile` برای روش CLI).
2. **دیپلوی صادر نشده** — در پنل رانفلر جلوی آخرین کامیت دکمه **Revert/Redeploy**
   را بزنید و ۲–۳ دقیقه صبر کنید.
3. **پورت Expose سرویس = 8000** نباشد — تنظیمات شبکه سرویس را چک کنید.

اسکریپت روش ۰ همین تشخیص‌ها را خودکار انجام می‌دهد و علت را چاپ می‌کند.

---

## اتصال اپ اندروید

اپ → **تنظیمات** → «آدرس API» → آدرس رانفلر را وارد کنید
(مثلاً `https://subsurf.runflare.app`) → دکمه تست اتصال.
آدرس در `SharedPreferences` ذخیره می‌شود (`SettingsStore.apiBaseUrl`).

> منابع پیشنهادی: حداقل 512MB RAM برای grid=512؛ برای grid=512 + مدل
> autoencoder بهتر است 1GB بگیرید. حالت `resolution_m=10` (کاشی‌کاری بومی)
> هم با 512MB کار می‌کند (هر کاشی ≤512px) ولی برای سرعت بهتر 1GB بگیرید.
> وابستگی جدید: `scipy` (در requirements/Dockerfile هست، کاری لازم نیست).
> هزینه ساعتی است؛ بعد از تست می‌توانید سرویس را **متوقف** کنید و بعداً
> دوباره روشن کنید (`runflare start`).
