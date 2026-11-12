# چرا این پوشه وجود دارد؟ / Why this folder exists

**فارسی:** وقتی پوشهٔ پروژه را با «Add file → Upload files» در سایت گیت‌هاب آپلود می‌کنید،
پوشه‌های مخفی (پوشه‌هایی که نامشان با نقطه شروع می‌شود) مانند `.github/` **آپلود نمی‌شوند** —
پس ورک‌فلوهای CI از بین می‌روند و APK ساخته نمی‌شود!

راه‌حل‌ها:

1. **پیشنهادی:** از `git` استفاده کنید (`scripts/upload-to-github.sh`) — همه‌چیز از جمله `.github/` منتقل می‌شود.
2. **اگر وب‌آپلود کردید:** این دو فایل را دستی در ریپو بازسازی کنید:
   - در گیت‌هاب: **Add file → Create new file**
   - نام فایل را دقیقاً تایپ کنید: `.github/workflows/android.yml` (تایپ `.github/` خودش پوشه می‌سازد)
   - محتوای `android.yml` همین پوشه را کپی-پیست کنید و Commit بزنید.
   - همین‌کار را برای `.github/workflows/backend.yml` با محتوای `backend.yml` انجام دهید.
   - اختیاری: `.github/dependabot.yml` را هم با الگوی مشابه بسازید.

**English:** The GitHub web uploader skips dot-prefixed folders (`.github/`), which would delete the
CI workflows. Either push with `git` (`scripts/upload-to-github.sh`), or recreate the files manually:
*Add file → Create new file* → name it `.github/workflows/android.yml` and paste the contents of the
matching file from this folder; repeat for `.github/workflows/backend.yml` (and optionally
`.github/dependabot.yml`).
