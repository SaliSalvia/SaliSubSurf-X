#!/usr/bin/env bash
# =============================================================================
# SaliSurf-X — استقرار کاملِ یک‌اجرایی (Termux)
#
# این اسکریپت «همه‌چیز» را در یک اجرا و به‌صورت تعاملی انجام می‌دهد:
#
#   ۱) پیدا/استخراج ZIP پروژه از پوشه‌ی Download گوشی (یا استفاده از پوشه فعلی)
#   ۲) ساخت ریپوی جدید GitHub با نام SaliSurf-X (با gh — از قبل auth شده)
#   ۳) اگر کلید امضای شخصی هنوز تنظیم نشده: ساخت keystore همین‌جا در ترمینال
#      (رمزها را خودتان مخفی وارد می‌کنید) + ثبت خودکار ۴ Secret در ریپو
#   ۴) push پروژه → اجرای خودکار ورک‌فلو «Android APK»
#   ۵) زیر نظر گرفتن بیلد تا پایان + ساخت GitHub Release (vX.Y.Z)
#   ۶) دانلود APK ریلیزشده مستقیم به پوشه‌ی Download گوشی
#
# هیچ رمزی در فایل یا خروجی ذخیره نمی‌شود؛ فقط در GitHub Secrets.
# فایل keystore هرگز داخل ریپو قرار نمی‌گیرد (.gitignore مسدودش می‌کند).
#
# اجرا از هرجا (ترموکس):
#   bash salisurf-x-deploy.sh
# یا اگر پروژه از قبل استخراج شده، از ریشه‌ی همان پوشه:
#   bash scripts/salisurf-x-deploy.sh
#
# English: one-shot deploy — create repo SaliSurf-X, push, interactively create
# a personal signing keystore (passwords entered hidden in this terminal), let
# the workflow build + release the APK, then download it to the Download folder.
# =============================================================================
set -euo pipefail

# --- ثابت‌ها ---------------------------------------------------------------
REPO_NAME_DEFAULT="SaliSurf-X"
ALIAS_DEFAULT="salisurf-x"
VALIDITY=10950          # ≈ ۳۰ سال — یک بار برای همیشه بسازید و نگه دارید
KEYSIZE=4096            # RSA-4096
STORETYPE=PKCS12
WORK_DIR_DEFAULT="$HOME/SaliSurf-X-src"
REPO_DESC="SaliSurf-X — evidence-aware geospatial workspace (Android + FastAPI + CI)"

# --- رنگ‌ها (فقط وقتی ترمینال واقعی است) -----------------------------------
if [ -t 1 ]; then
    B=$'\033[1m'; C=$'\033[1;36m'; G=$'\033[1;32m'; Y=$'\033[1;33m'; Rd=$'\033[1;31m'; N=$'\033[0m'
else
    B=''; C=''; G=''; Y=''; Rd=''; N=''
fi
banner() { printf '\n%s== %s ==%s\n' "$C" "$*" "$N"; }
info()   { printf '%s%s%s\n' "$G" "$*" "$N"; }
warn()   { printf '%s%s%s\n' "$Y" "$*" "$N"; }
die()    { printf '%s[!] %s%s\n' "$Rd" "$*" "$N" >&2; exit 1; }

# فایل‌های موقت — همیشه پاک می‌شوند (TMPB64 حاوی کل کامل شماست!)
TMPB64=""
ERRFILE=""
cleanup() {
    [ -n "$TMPB64" ] && [ -f "$TMPB64" ] && rm -f "$TMPB64"
    [ -n "$ERRFILE" ] && [ -f "$ERRFILE" ] && rm -f "$ERRFILE"
}
trap cleanup EXIT

# --- پرسش‌های تعاملی --------------------------------------------------------
ask() {
    local __var=$1 __prompt=$2 __def=$3 __ans=""
    read -r -e -i "$__def" -p "$(printf '%s%s%s' "$B" "$__prompt" "$N")" __ans || true
    [ -z "$__ans" ] && __ans=$__def
    printf -v "$__var" '%s' "$__ans"
}

ask_yes() {
    local __prompt=$1 __def=${2:-n} __ans=""
    while :; do
        read -r -p "$(printf '%s%s [y/N]: %s' "$B" "$__prompt" "$N")" __ans || true
        __ans=$(printf '%s' "$__ans" | tr '[:upper:]' '[:lower:]')
        [ -z "$__ans" ] && __ans=$__def
        case "$__ans" in y|yes) return 0 ;; n|no) return 1 ;; *) warn "فقط y یا n." ;; esac
    done
}

ask_secret() {
    local __var=$1 __prompt=$2 __min=${3:-6} __a="" __b=""
    while :; do
        __a=""
        read -rs -p "$(printf '%s%s%s' "$B" "$__prompt" "$N")" __a \
            || [ -n "$__a" ] || { printf '\n'; die "ورودی بسته شد (EOF) — اسکریپت را دوباره اجرا کنید."; }
        printf '\n'
        if [ "${#__a}" -lt "$__min" ]; then
            warn "رمز باید حداقل $__min کاراکتر باشد (keytool این را الزام می‌کند)."
            continue
        fi
        __b=""
        read -rs -p "$(printf '%s%s%s' "$B" "(تکرار برای تأیید) $__prompt" "$N")" __b \
            || [ -n "$__b" ] || { printf '\n'; die "ورودی بسته شد (EOF) — اسکریپت را دوباره اجرا کنید."; }
        printf '\n'
        if [ "$__a" != "$__b" ]; then warn "دو ورودی یکسان نبود — دوباره."; continue; fi
        printf -v "$__var" '%s' "$__a"
        break
    done
}

b64_encode() { # b64_encode FILE → stdout (یک خط)
    base64 -w0 "$1" 2>/dev/null || { base64 "$1" | tr -d '\n'; }
}

# =============================================================================
banner "SaliSurf-X — استقرار کامل (repo + push + امضا + ریلیز + دانلود APK)"
echo "ترتیب کار: ابزارها ← پروژه ← ریپو ← کلید امضا ← push ← بیلد ← ریلیز ← دانلود"
echo

# --- ۰/۸ ابزارها و ورود -----------------------------------------------------
banner "0/8 ابزارها و ورود به GitHub"
IN_TERMUX=0
command -v termux-info >/dev/null 2>&1 && IN_TERMUX=1
[ -d "/data/data/com.termux" ] && IN_TERMUX=1
if [ "$IN_TERMUX" -eq 1 ]; then info "محیط: Termux ✔"; else warn "محیط: Termux نیست — ادامه می‌دهم (git/gh/unzip لازم است)."; fi

install_pkg() {
    if command -v pkg >/dev/null 2>&1; then pkg install -y "$@"
    elif command -v apt-get >/dev/null 2>&1; then apt-get install -y "$@" || sudo apt-get install -y "$@"
    else return 1
    fi
}

MISSING=""
for c in git gh unzip keytool; do command -v "$c" >/dev/null 2>&1 || MISSING="$MISSING $c"; done
if [ -n "$MISSING" ]; then
    warn "این ابزارها پیدا نشد:$MISSING"
    if ask_yes "همه را با یک دستور نصب کنیم؟ (Termux: pkg)"; then
        # keytool جزو بسته‌ها نیست — همراه openjdk-17 نصب می‌شود
        PKGS=""
        for c in $MISSING; do
            case "$c" in
                keytool) PKGS="$PKGS openjdk-17" ;;
                *)       PKGS="$PKGS $c" ;;
            esac
        done
        install_pkg $PKGS || die "نصب ناموفق — دستی: pkg install -y git gh unzip openjdk-17"
    else
        die "بدون این ابزارها ادامه نمی‌شود: pkg install -y git gh unzip openjdk-17"
    fi
fi
for c in git gh unzip keytool; do command -v "$c" >/dev/null 2>&1 || die "$c هنوز در دسترس نیست."; done
info "git / gh / unzip / keytool ✔"

if ! gh auth status >/dev/null 2>&1; then
    warn "هنوز وارد GitHub نشده‌اید. همین الآن:"
    printf '    %sgh auth login%s\n' "$B" "$N"
    printf '    گزینه‌ها: GitHub.com → HTTPS → «Login with a web browser»\n'
    printf '    (کد ۸ رقمی را در مرورگر باز کنید و وارد شوید؛ بعد دوباره این اسکریپت را اجرا کنید.)\n'
    exit 0
fi
GH_USER="$(gh api user --jq .login 2>/dev/null || true)"
[ -z "$GH_USER" ] && die "نام کاربری GitHub خوانده نشد — gh auth status را بررسی کنید."
info "GitHub: @$GH_USER (احراز هویت معتبر)"

# --- ۱/۸ پیدا کردن پروژه (ZIP در Download یا پوشه فعلی) ----------------------
banner "1/8 پروژه: ZIP پوشه‌ی Download یا پوشه فعلی"
SRC_DIR=""
if [ -f "android/app/build.gradle.kts" ] && [ -d ".github/workflows" ]; then
    SRC_DIR="$PWD"
    info "پوشه فعلی خود پروژه است → از همین‌جا ادامه می‌دهیم."
else
    # دسترسی به حافظه گوشی در ترموکس
    DL_DIR=""
    for d in "$HOME/storage/downloads" "$HOME/Downloads" "$HOME/downloads"; do
        [ -d "$d" ] && DL_DIR="$d" && break
    done
    if [ -z "$DL_DIR" ] && [ "$IN_TERMUX" -eq 1 ] && command -v termux-setup-storage >/dev/null 2>&1; then
        warn "دسترسی به حافظه گوشی داده نشده — الان اجازه می‌خواهیم (روی صفحه «Allow» را بزنید)…"
        termux-setup-storage || true
        [ -d "$HOME/storage/downloads" ] && DL_DIR="$HOME/storage/downloads"
    fi
    [ -z "$DL_DIR" ] && die "پوشه Download پیدا نشد. termux-setup-storage را اجرا کنید یا مسیر ZIP را بدهید."

    # جدیدترین ZIPهای SaliSurf-X / Sal-Subsurf در Download
    mapfile -t CANDS < <(ls -t "$DL_DIR"/SaliSurf-X*.zip "$DL_DIR"/Sal-Subsurf*.zip 2>/dev/null || true)
    ZIP_PATH=""
    if [ "${#CANDS[@]}" -ge 1 ]; then
        if [ "${#CANDS[@]}" -gt 1 ]; then
            echo "این ZIPها در $DL_DIR پیدا شد (جدیدی‌ها اول):"
            i=1
            for f in "${CANDS[@]}"; do printf '  %d) %s\n' "$i" "$(basename "$f")"; i=$((i+1)); done
            ask PICK "کدام؟ [شماره] " "1"
            case "$PICK" in ''|*[!0-9]*) PICK=1 ;; esac
            [ "$PICK" -lt 1 ] && PICK=1
            [ "$PICK" -gt "${#CANDS[@]}" ] && PICK=1
            ZIP_PATH="${CANDS[$((PICK-1))]}"
        else
            ZIP_PATH="${CANDS[0]}"
        fi
        info "انتخاب: $(basename "$ZIP_PATH")"
    fi
    while [ -z "$ZIP_PATH" ] || [ ! -f "$ZIP_PATH" ]; do
        ask ZIP_PATH "مسیر کامل ZIP پروژه: " ""
        [ -f "$ZIP_PATH" ] || warn "چنین فایلی نیست — دوباره."
    done

    ask WORK_DIR "پوشه استخراج: " "$WORK_DIR_DEFAULT"
    if [ -d "$WORK_DIR" ]; then
        if ask_yes "«$WORK_DIR» موجود است — پاک و از ZIP تازه استخراج شود؟" "y"; then
            rm -rf "$WORK_DIR"
        else
            die "پوشه موجود را خودتان مدیریت کنید و دوباره اجرا کنید."
        fi
    fi
    mkdir -p "$WORK_DIR"
    info "استخراج…"
    unzip -q -o "$ZIP_PATH" -d "$WORK_DIR"

    # اگر ZIP یک پوشه‌ی سطح‌بالا دارد، واردش شویم
    if [ ! -f "$WORK_DIR/android/app/build.gradle.kts" ]; then
        INNER="$(find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type d | head -n1 || true)"
        if [ -n "$INNER" ] && [ -f "$INNER/android/app/build.gradle.kts" ]; then
            WORK_DIR="$INNER"
        else
            die "ساختار پروژه در ZIP درست نیست (android/app/build.gradle.kts پیدا نشد)."
        fi
    fi
    SRC_DIR="$WORK_DIR"
fi
cd "$SRC_DIR"
[ -f "android/app/build.gradle.kts" ] || die "android/app/build.gradle.kts پیدا نشد."
[ -f ".github/workflows/android.yml" ] || die ".github/workflows/android.yml پیدا نشد — ZIP ناقص است."

VERSION="$(sed -nE 's/.*versionName = "([^"]+)".*/\1/p' android/app/build.gradle.kts | head -n1)"
[ -z "$VERSION" ] && die "versionName از build.gradle.kts خوانده نشد."
info "پروژه: SaliSurf-X v$VERSION در $SRC_DIR"

# --- ۲/۸ مخزن محلی git -------------------------------------------------------
banner "2/8 مخزن محلی git"
if [ ! -d ".git" ]; then
    git init -b main >/dev/null 2>&1 || { git init >/dev/null && git checkout -b main; }
    info "مخزن محلی ساخته شد (شاخه main)."
fi
# هویت git: اول تنظیمات موجود، بعد حساب GitHub
GIT_NAME="$(git config user.name 2>/dev/null || true)"
GIT_MAIL="$(git config user.email 2>/dev/null || true)"
if [ -z "$GIT_NAME" ] || [ -z "$GIT_MAIL" ]; then
    DEF_NAME="${GIT_NAME:-$GH_USER}"
    DEF_MAIL="${GIT_MAIL:-$GH_USER@users.noreply.github.com}"
    ask GIT_NAME "git user.name: " "$DEF_NAME"
    ask GIT_MAIL "git user.email: " "$DEF_MAIL"
    git config user.name  "$GIT_NAME"
    git config user.email "$GIT_MAIL"
fi
info "هویت git: $(git config user.name) <$(git config user.email)>"

# احراز هویت push با توکن gh (بدون پرسیدن رمز در https)
git config credential.helper '!gh auth git-credential'

if [ -z "$(git status --porcelain 2>/dev/null)" ] && git rev-parse HEAD >/dev/null 2>&1; then
    info "همه‌چیز از قبل commit شده."
else
    git add -A
    git commit -q -m "SaliSurf-X v$VERSION — app + API + CI" || info "چیزی برای commit نبود."
    info "commit اول ساخته شد."
fi

# --- ۳/۸ ریپوی GitHub --------------------------------------------------------
banner "3/8 ریپوی GitHub"
ask REPO_NAME "نام ریپوی جدید: " "$REPO_NAME_DEFAULT"
while ! printf '%s' "$REPO_NAME" | grep -Eq '^[A-Za-z0-9_.-]+$' || [ -z "$REPO_NAME" ]; do
    warn "نام فقط حرف/رقم/نقطه/خط‌تیره."
    ask REPO_NAME "نام ریپوی جدید: " "$REPO_NAME_DEFAULT"
done

VIS="public"
if ask_yes "ریپو خصوصی (private) باشد؟ (پیش‌فرض: عمومی)"; then VIS="private"; fi

REPO="$GH_USER/$REPO_NAME"
FORCE_PUSH=0
if gh repo view "$REPO" >/dev/null 2>&1; then
    warn "ریپوی $REPO از قبل وجود دارد."
    if ask_yes "همین ریپو استفاده شود (به‌جای ساخت جدید)؟" "y"; then
        if ask_yes "ممکن است تاریخچه قدیمی داشته باشد — با force بازنویسی شود؟"; then
            FORCE_PUSH=1
        fi
    else
        die "یک نام دیگر انتخاب کنید و دوباره اجرا کنید (یا ریپوی موجود را در گیت‌هاب حذف کنید)."
    fi
else
    info "ساخت ریپو: $REPO ($VIS)…"
    if [ "$VIS" = "private" ]; then
        gh repo create "$REPO_NAME" --private --description "$REPO_DESC" \
            || die "ساخت ریپو ناموفق بود (نام تکراری؟ دسترسی؟)"
    else
        gh repo create "$REPO_NAME" --public --description "$REPO_DESC" \
            || die "ساخت ریپو ناموفق بود (نام تکراری؟ دسترسی؟)"
    fi
    info "ساخته شد: https://github.com/$REPO"
fi
git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$REPO.git"
info "remote: origin → https://github.com/$REPO.git"

# --- ۴/۸ کلید امضای شخصی (تعاملی، اگر تنظیم نشده) -----------------------------
banner "4/8 امضای شخصی — بررسی Secrets ریپو"
SECRET_NAMES="$(gh secret list -R "$REPO" 2>/dev/null | awk '{print $1}' || true)"
HAVE_ALL=1
for s in KEYSTORE_BASE64 KEYSTORE_PASSWORD KEY_ALIAS KEY_PASSWORD; do
    printf '%s\n' "$SECRET_NAMES" | grep -qx "$s" || HAVE_ALL=0
done

SIGNED=0
if [ "$HAVE_ALL" -eq 1 ]; then
    SIGNED=1
    info "هر ۴ Secret امضا از قبل تنظیم است → بیلد امضاشده خواهد بود."
else
    warn "Secretهای امضا کامل نیستند — بدون آنها APK ریلیز «unsigned» خواهد بود."
    if ask_yes "همین حالا کلید شخصی بسازیم و ثبت کنیم؟ (رمز را در همین ترمینال وارد می‌کنید)" "y"; then
        KEYSTORE_DEFAULT="$HOME/salisurf-x-release.keystore"
        [ -n "${KEYSTORE_PATH:-}" ] && KEYSTORE_DEFAULT="$KEYSTORE_PATH"
        ask KEYSTORE "مسیر فایل keystore: " "$KEYSTORE_DEFAULT"

        REUSE=0
        if [ -f "$KEYSTORE" ]; then
            warn "فایل موجود است: $KEYSTORE"
            if ask_yes "کلید موجود را دوباره استفاده کنیم؟" "y"; then
                REUSE=1
            else
                if ask_yes "فایل موجود حذف شود و کلید تازه ساخته شود؟"; then
                    rm -f "$KEYSTORE"
                else
                    die "بدون تغییر خارج شد — فایل موجود را خودتان مدیریت کنید."
                fi
            fi
        fi

        ask ALIAS "نام کلید (alias): " "$ALIAS_DEFAULT"
        printf '%s' "$ALIAS" | grep -Eq '^[A-Za-z0-9._-]+$' || die "alias فقط حرف/رقم/نقطه/خط‌تیره."

        ask CERT_NAME "نام صاحب کلید (CN): " "SaliSurf-X"
        ask CERT_ORG  "سازمان (O) — خالی بگذارید اگر ندارید: " "SaliSurf-X"
        ask CERT_CNTRY "کد کشور دوحرفی (C): " "IR"
        CERT_CNTRY=$(printf '%s' "$CERT_CNTRY" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z' | cut -c1-2)
        [ -z "$CERT_CNTRY" ] && CERT_CNTRY="IR"

        strip_commas() { printf '%s' "$1" | tr -d ','; }
        CERT_NAME=$(strip_commas "$CERT_NAME")
        CERT_ORG=$(strip_commas "$CERT_ORG")
        DNAME="CN=$CERT_NAME"
        [ -n "$CERT_ORG" ] && DNAME="$DNAME, O=$CERT_ORG"
        DNAME="$DNAME, C=$CERT_CNTRY"

        echo
        echo "یک رمز قوی برای کلید (حداقل ۶ کاراکتر). این رمز برای کلید و فایل store"
        echo "هر دو استفاده می‌شود (استاندارد PKCS12) و بعداً هنگام به‌روزرسانی اپ به همان"
        echo "رمز نیاز دارید — آن را به‌خاطر بسپارید یا در جای امن یادداشت کنید."
        echo "ورودی نمایش داده نمی‌شود."
        ask_secret KEYSTORE_PASS "رمز کلید: " 6

        if [ "$REUSE" -eq 1 ]; then
            info "تأیید کلید موجود با رمز واردشده …"
            keytool -list -keystore "$KEYSTORE" -storetype "$STORETYPE" \
                -storepass "$KEYSTORE_PASS" >/dev/null 2>&1 \
                || die "رمز با این keystore نخواند — فایل یا رمز اشتباه است."
            info "کلید معتبر است."
        else
            echo "در حال ساخت: RSA-$KEYSIZE، اعتبار $VALIDITY روز (≈۳۰ سال)، $STORETYPE"
            echo "مشخصات گواهی: $DNAME"
            keytool -genkeypair -v \
                -keystore "$KEYSTORE" \
                -alias "$ALIAS" \
                -keyalg RSA -keysize "$KEYSIZE" \
                -validity "$VALIDITY" \
                -storetype "$STORETYPE" \
                -storepass "$KEYSTORE_PASS" \
                -keypass "$KEYSTORE_PASS" \
                -dname "$DNAME" >/dev/null
            info "کلید ساخته شد: $KEYSTORE"
        fi
        keytool -list -v -keystore "$KEYSTORE" -storetype "$STORETYPE" \
            -storepass "$KEYSTORE_PASS" 2>/dev/null \
            | grep -E "Alias name|Owner|Valid from|Entry type" | sed 's/^ *//' | head -4

        banner "ثبت Secrets در $REPO (قبل از push، تا اولین بیلد امضاشده باشد)"
        TMPB64=$(mktemp)
        b64_encode "$KEYSTORE" > "$TMPB64"
        echo "keystore به base64 تبدیل شد ($(wc -c < "$TMPB64") کاراکتر) — موقت و بعداً حذف می‌شود."

        gh secret set KEYSTORE_BASE64 -R "$REPO" < "$TMPB64" \
            || die "ثبت KEYSTORE_BASE64 ناموفق بود."
        printf '%s' "$KEYSTORE_PASS" | gh secret set KEYSTORE_PASSWORD -R "$REPO" \
            || die "ثبت KEYSTORE_PASSWORD ناموفق بود."
        printf '%s' "$ALIAS"        | gh secret set KEY_ALIAS       -R "$REPO" \
            || die "ثبت KEY_ALIAS ناموفق بود."
        printf '%s' "$KEYSTORE_PASS" | gh secret set KEY_PASSWORD    -R "$REPO" \
            || die "ثبت KEY_PASSWORD ناموفق بود."
        rm -f "$TMPB64"; TMPB64=""

        SIGNED=1
        info "Secretهای ثبت‌شده:"
        gh secret list -R "$REPO" 2>/dev/null | sed 's/^/    /' || true
        echo
        echo "فایل کلید شما: $KEYSTORE   (هرگز commit نمی‌شود)"
        warn "پشتیبان‌گیری: فایل + رمز را در جای امن نگه دارید — اگر گم شود،"
        echo "آپدیت‌های بعدی باید با نام بسته جدید منتشر شوند و نصب روی نسخه قبلی ممکن نمی‌شود."
    else
        warn "بدون کلید ادامه می‌دهیم — APK ریلیز «unsigned» ساخته می‌شود."
    fi
fi

# --- ۵/۸ push ------------------------------------------------------------------
banner "5/8 push به main"
ERRFILE="$(mktemp)"
if [ "$FORCE_PUSH" -eq 1 ]; then
    git push --force -u origin main 2>"$ERRFILE" || die "push ناموفق بود: $(head -n3 "$ERRFILE")"
else
    if ! git push -u origin main 2>"$ERRFILE"; then
        if grep -qiE "non-fast-forward|fetch first|rejected" "$ERRFILE"; then
            warn "ریپو خالی نیست و push عادی رد شد."
            if ask_yes "با force بازنویسی شود؟"; then
                git push --force -u origin main 2>"$ERRFILE" || die "force push هم ناموفق بود: $(head -n3 "$ERRFILE")"
            else
                die "push رد شد: $(head -n3 "$ERRFILE")"
            fi
        else
            die "push ناموفق بود: $(head -n3 "$ERRFILE")"
        fi
    fi
fi
rm -f "$ERRFILE"; ERRFILE=""
info "push شد → ورک‌فلو «Android APK» خودکار اجرا می‌شود."

# --- ۶/۸ زیر نظر گرفتن بیلد ----------------------------------------------------
banner "6/8 بیلد GitHub Actions"
RUN_URL="https://github.com/$REPO/actions"
if ask_yes "بیلد را همین‌جا زیر نظر بگیریم تا تمام شود؟ (حدود ۵–۱۰ دقیقه)" "y"; then
    RUN_ID=""
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        RUN_ID="$(gh run list -R "$REPO" --workflow "Android APK" --limit 1 --json databaseId -q '.[0].databaseId' 2>/dev/null || true)"
        [ -n "$RUN_ID" ] && break
        sleep 3
    done
    if [ -z "$RUN_ID" ]; then
        warn "run پیدا نشد — دستی بررسی کنید: gh run list -R \"$REPO\""
    else
        info "run #$RUN_ID — در حال مشاهده… (Ctrl-C بی‌خطر است؛ بیلد ادامه دارد)"
        if gh run watch "$RUN_ID" -R "$REPO" --exit-status --interval 10; then
            info "بیلد با موفقیت تمام شد ✔"
        else
            warn "بیلد ناموفق بود. گزارش خطا:"
            gh run view "$RUN_ID" -R "$REPO" --log-failed 2>/dev/null | tail -n 40 || true
            die "لاگ کامل: gh run view $RUN_ID -R \"$REPO\" --log-failed"
        fi
    fi
else
    echo "پیگیری دستی:"
    echo "    gh run watch \$(gh run list -R \"$REPO\" --workflow 'Android APK' --limit 1 --json databaseId -q '.[0].databaseId') -R \"$REPO\""
    echo "    $RUN_URL"
fi

# --- ۷/۸ ریلیز و دانلود APK -----------------------------------------------------
banner "7/8 ریلیز و دانلود APK"
TAG="v$VERSION"
info "در انتظار GitHub Release «$TAG»…"
FOUND=0
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
    if gh release view "$TAG" -R "$REPO" >/dev/null 2>&1; then FOUND=1; break; fi
    sleep 15
done

DL_DIR="$HOME/storage/downloads"
[ -d "$DL_DIR" ] || DL_DIR="$HOME/Downloads"
[ -d "$DL_DIR" ] || DL_DIR="$HOME"

if [ "$FOUND" -eq 1 ]; then
    RELEASE_URL="$(gh release view "$TAG" -R "$REPO" --json url -q '.url' 2>/dev/null || true)"
    info "ریلیز منتشر شد: ${RELEASE_URL:-https://github.com/$REPO/releases/tag/$TAG}"
    if ask_yes "APKهای ریلیز به پوشه Download گوشی دانلود شوند؟" "y"; then
        mkdir -p "$DL_DIR"
        if gh release download "$TAG" -R "$REPO" -p '*.apk' -D "$DL_DIR" --clobber; then
            info "دانلود شد → $DL_DIR:"
            ls -lh "$DL_DIR"/*.apk 2>/dev/null | awk '{printf "    %s  %s\n", $5, $9}' || true
        else
            warn "دانلود ناموفق بود — دستی: gh release download $TAG -R \"$REPO\" -p '*.apk'"
        fi
    fi
else
    warn "ریلیز «$TAG» هنوز ظاهر نشده (یا بیلد دنبال نشد/ناموفق بود). بعداً بررسی کنید:"
    echo "    gh release view $TAG -R \"$REPO\""
    echo "    gh release download $TAG -R \"$REPO\" -p '*.apk' -D \"$DL_DIR\""
fi

# --- ۸/۸ جمع‌بندی -----------------------------------------------------------------
banner "8/8 تمام شد"
echo "ریپو:      https://github.com/$REPO"
echo "اکشن‌ها:   $RUN_URL"
echo "ریلیز:     https://github.com/$REPO/releases/tag/$TAG"
if [ "$SIGNED" -eq 1 ]; then
    echo "امضا:      شخصی ✔  (SaliSurf-X-release-signed.apk)"
else
    echo "امضا:      ندارد — SaliSurf-X-release-unsigned.apk (برای امضای بعدی: bash scripts/termux-sign.sh)"
fi
echo "ورژن:      $VERSION  (نسخه‌ی بعدی: versionName/versionCode را در android/app/build.gradle.kts بالا ببرید)"
echo
echo "نصب روی گوشی: فایل APK را در فایل‌منیجر باز کنید («نصب از منابع ناشناس» روشن باشد)."
echo "اگر نسخه قبلی با کلید دیگری نصب بوده، اول آن را حذف کنید."
echo
echo "نکته: هر push بعدی به main، ریلیز همان نسخه را به‌روز می‌کند؛ برای ریلیز جدید،"
echo "نسخه را بالا ببرید (مثلاً 1.5.1 → تگ v1.5.1 و ریلیز تازه ساخته می‌شود)."
