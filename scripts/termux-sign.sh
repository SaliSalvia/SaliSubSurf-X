#!/usr/bin/env bash
# =============================================================================
# SaliSurf-X — ساخت تعاملی کلید امضای شخصی + ثبت خودکار در GitHub Secrets
# (Termux)
#
# این اسکریپت همه‌چیز را «در همین ترمینال» و به‌صورت تعاملی می‌پرسد:
#   ریپو، مسیر فایل کلید، نام کلید (alias)، مشخصات صاحب کلید، و رمز (مخفی،
#   با تأیید). هیچ رمزی در فایل یا خروجی ذخیره نمی‌شود؛ فقط در GitHub Secrets.
#
# خروجی: از بیلد بعدی، ورک‌فلو «Android APK» علاوه بر debug، این را هم می‌سازد:
#   SaliSurf-X-release-signed.apk   ← امضاشده با کلید شخصی شما
#
# اجرا (پیشنهاد: از ریشه مخزن استخراج‌شده):  bash scripts/termux-sign.sh
#
# نکته: برای مسیر کامل (ساخت ریپو جدید + پوش + امضا + ریلیز + دانلود APK)
# اسکریپت salisurf-x-deploy.sh را اجرا کنید — این اسکریپت فقط بخش امضاست.
# =============================================================================
set -euo pipefail

# --- ثابت‌ها ---------------------------------------------------------------
ALIAS_DEFAULT="salisurf-x"
VALIDITY=10950          # ≈ ۳۰ سال — یک بار برای همیشه بسازید و نگه دارید
KEYSIZE=4096            # RSA-4096
STORETYPE=PKCS12

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

# فایل موقت base64 — همیشه پاک می‌شود (حاوی کل کامل شماست!)
TMPB64=""
cleanup() { [ -n "$TMPB64" ] && [ -f "$TMPB64" ] && rm -f "$TMPB64"; }
trap cleanup EXIT

# --- پرسش‌های تعاملی --------------------------------------------------------
# ask VAR "متن سؤال" "مقدار پیش‌فرض"  ← ورودی معمولی با پیش‌فرض قابل‌ویرایش
ask() {
    local __var=$1 __prompt=$2 __def=$3 __ans=""
    read -r -e -i "$__def" -p "$(printf '%s%s%s' "$B" "$__prompt" "$N")" __ans || true
    [ -z "$__ans" ] && __ans=$__def
    printf -v "$__var" '%s' "$__ans"
}

# ask_yes "متن سؤال" [default:y|n]  ← فقط y / n
ask_yes() {
    local __prompt=$1 __def=${2:-n} __ans=""
    while :; do
        read -r -p "$(printf '%s%s [y/N]: %s' "$B" "$__prompt" "$N")" __ans || true
        __ans=$(printf '%s' "$__ans" | tr '[:upper:]' '[:lower:]')
        [ -z "$__ans" ] && __ans=$__def
        case "$__ans" in y|yes) return 0 ;; n|no) return 1 ;; *) warn "فقط y یا n." ;; esac
    done
}

# ask_secret VAR "متن سؤال" [حداقل طول]  ← ورودی مخفی + تأیید (دو بار)
ask_secret() {
    local __var=$1 __prompt=$2 __min=${3:-6} __a="" __b=""
    while :; do
        __a=""
        # در پایان ورودی (Ctrl-D) به جای حلقه بی‌نهایت، با پیام روشن خارج شو
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

# --- ۰/۶ ابزارها ------------------------------------------------------------
banner "0/6 ابزارها"
install_pkg() {
    if command -v pkg >/dev/null 2>&1; then pkg install -y "$1"
    elif command -v apt-get >/dev/null 2>&1; then sudo apt-get install -y "$1" || apt-get install -y "$1"
    else return 1
    fi
}
if ! command -v keytool >/dev/null 2>&1; then
    warn "keytool پیدا نشد → نصب openjdk-17 …"
    install_pkg openjdk-17 || die "openjdk-17 را دستی نصب کنید (در ترموکس: pkg install openjdk-17)."
fi
command -v keytool >/dev/null 2>&1 || die "keytool هنوز در دسترس نیست."
info "keytool: $(keytool -help 2>&1 | head -1 | cut -c1-60)…"

if ! command -v gh >/dev/null 2>&1; then
    warn "GitHub CLI پیدا نشد → نصب gh …"
    install_pkg gh || die "gh را دستی نصب کنید (در ترموکس: pkg install gh)."
fi
command -v gh >/dev/null 2>&1 || die "gh هنوز در دسترس نیست."

# --- ۱/۶ ورود به GitHub -----------------------------------------------------
banner "1/6 ورود به GitHub"
if ! gh auth status >/dev/null 2>&1; then
    warn "هنوز وارد GitHub نشده‌اید. همین الآن:"
    printf '    %sgh auth login%s\n' "$B" "$N"
    printf '    گزینه‌ها: GitHub.com → HTTPS → «Login with a web browser»\n'
    printf '    (کد ۸ رقمی را در مرورگر باز کنید و وارد شوید؛ بعد دوباره این اسکریپت را اجرا کنید.)\n'
    exit 0
fi
info "احراز هویت GitHub: معتبر."

# --- ۲/۶ شناسایی ریپو -------------------------------------------------------
banner "2/6 ریپوی هدف"
REPO_GUESS=""
if REMOTE=$(git config --get remote.origin.url 2>/dev/null); then
    REPO_GUESS=$(printf '%s' "$REMOTE" | sed -E \
        -e 's#^[a-z]+://[^/]*github[.]com[:/]##' -e 's#^git@github[.]com:##' \
        -e 's#^git://github[.]com/##' -e 's#[.]git$##' -e 's#^/##' -e 's#/$##')
fi
[ -z "$REPO_GUESS" ] && REPO_GUESS="SaliSalvia/SaliSurf-X"
ask REPO "ریپوی گیت‌هاب (owner/name): " "$REPO_GUESS"
printf '%s' "$REPO" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$' \
    || die "قالب ریپو درست نیست: «owner/name» (مثلاً SaliSalvia/SaliSurf-X)."
info "هدف: $REPO"

# --- ۳/۶ مشخصات کلید (تعاملی) ----------------------------------------------
banner "3/6 مشخصات کلید"
KEYSTORE_DEFAULT="$HOME/salisurf-x-release.keystore"
[ -n "${KEYSTORE_PATH:-}" ] && KEYSTORE_DEFAULT="$KEYSTORE_PATH"
ask KEYSTORE "مسیر فایل keystore: " "$KEYSTORE_DEFAULT"

if [ -f "$KEYSTORE" ]; then
    warn "فایل موجود است: $KEYSTORE"
    if ask_yes "کلید موجود را دوباره استفاده کنیم؟ (secretها با همان به‌روز می‌شوند)" "y"; then
        REUSE=1
    else
        if ask_yes "فایل موجود حذف شود و کلید تازه ساخته شود؟"; then
            rm -f "$KEYSTORE"; REUSE=0
        else
            die "بدون تغییر خارج شد — فایل موجود را خودتان مدیریت کنید."
        fi
    fi
else
    REUSE=0
fi

ask ALIAS "نام کلید (alias): " "$ALIAS_DEFAULT"
printf '%s' "$ALIAS" | grep -Eq '^[A-Za-z0-9._-]+$' || die "alias فقط حرف/رقم/نقطه/خط‌تیره."

# مشخصات صاحب کلید (در خود APK ثبت می‌شود و با «نمایش گواهی» دیده می‌شود)
ask CERT_NAME "نام صاحب کلید (CN): " "SaliSurf-X"
ask CERT_ORG  "سازمان (O) — خالی بگذارید اگر ندارید: " "SaliSurf-X"
ask CERT_CNTRY "کد کشور دوحرفی (C): " "IR"
CERT_CNTRY=$(printf '%s' "$CERT_CNTRY" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z' | cut -c1-2)
[ -z "$CERT_CNTRY" ] && CERT_CNTRY="IR"

# مقادیر dname نباید ویرگول داشته باشند
strip_commas() { printf '%s' "$1" | tr -d ','; }
CERT_NAME=$(strip_commas "$CERT_NAME")
CERT_ORG=$(strip_commas "$CERT_ORG")
DNAME="CN=$CERT_NAME"
[ -n "$CERT_ORG" ] && DNAME="$DNAME, O=$CERT_ORG"
DNAME="$DNAME, C=$CERT_CNTRY"

banner "رمز keystore"
echo "یک رمز قوی برای کلید (حداقل ۶ کاراکتر). این رمز برای کلید و فایل store"
echo "هر دو استفاده می‌شود (استاندارد PKCS12) و بعداً هنگام نصب مجدد/به‌روزرسانی"
echo "اپ به همان رمز نیاز دارید — آن را به‌خاطر بسپارید یا در جای امن یادداشت کنید."
echo "ورودی نمایش داده نمی‌شود."
ask_secret KEYSTORE_PASS "رمز کلید: " 6

# --- ۴/۶ ساخت (یا تأیید) کلید ----------------------------------------------
banner "4/6 ساخت کلید"
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

# --- ۵/۶ ثبت خودکار در GitHub Secrets ---------------------------------------
banner "5/6 ثبت Secrets در $REPO"
TMPB64=$(mktemp)
if ! base64 -w0 "$KEYSTORE" > "$TMPB64" 2>/dev/null; then
    base64 "$KEYSTORE" | tr -d '\n' > "$TMPB64"
fi
echo "keystore به base64 تبدیل شد ($(wc -c < "$TMPB64") کاراکتر) — موقت و بعداً حذف می‌شود."

gh secret set KEYSTORE_BASE64 -R "$REPO" < "$TMPB64" \
    || die "ثبت KEYSTORE_BASE64 ناموفق بود (ریپو/دسترسی را بررسی کنید)."
printf '%s' "$KEYSTORE_PASS" | gh secret set KEYSTORE_PASSWORD -R "$REPO" \
    || die "ثبت KEYSTORE_PASSWORD ناموفق بود."
printf '%s' "$ALIAS"        | gh secret set KEY_ALIAS       -R "$REPO" \
    || die "ثبت KEY_ALIAS ناموفق بود."
printf '%s' "$KEYSTORE_PASS" | gh secret set KEY_PASSWORD    -R "$REPO" \
    || die "ثبت KEY_PASSWORD ناموفق بود."

info "Secretهای ثبت‌شده در $REPO:"
gh secret list -R "$REPO" 2>/dev/null | sed 's/^/    /' || true

# --- ۶/۶ جمع‌بندی و راه بعدی -------------------------------------------------
banner "6/6 تمام شد"
echo "فایل کلید شما: $KEYSTORE   (هرگز commit نشود — .gitignore مسدودش می‌کند)"
echo
warn "پشتیبان‌گیری: این فایل + رمز را در جای امن (حافظه ابری/کامپیوتر دیگر)"
echo "نگه دارید. اگر گم شود، آپدیت‌های بعدی اپ باید با کلید و نام بسته جدید"
echo "منتشر شوند و کاربران باید اپ قدیمی را دستی حذف و جدید را نصب کنند."
echo
echo "از این به بعد هر push، این خروجی را می‌سازد:"
echo "    SaliSurf-X-release-signed.apk   ← امضاشده با کلید شما"
echo "    (تب Actions ریپو → run مربوطه → Artifacts)"
echo "    push به main علاوه بر آن، GitHub Release (vX.Y.Z) با همان APKها را می‌سازد."
echo
if ask_yes "همین حالا یک بیلد manual راه بیندازیم؟ (workflow_dispatch)"; then
    if gh workflow run "Android APK" -R "$REPO" 2>/dev/null; then
        info "بیلد آغاز شد — وضعیت: gh run list -R \"$REPO\" --limit 3"
    else
        warn "راه‌اندازی مستقیم ناموفق بود (شاید هنوز push نشده). با push بعدی خودکار اجرا می‌شود."
    fi
else
    echo "برای انتشار رسمی:  git tag v1.4.1 && git push origin v1.4.1"
    echo "→ APKهای امضاشده خودکار به یک GitHub Release پیوست می‌شوند."
fi
