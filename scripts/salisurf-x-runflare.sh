#!/usr/bin/env bash
# =============================================================================
# SaliSurf-X — دیپلوی بک‌اند روی Runflare، یک‌اجرایی (Termux + gh)
#
# کار این اسکریپت:
#   ۱) پیدا کردن پروژه (پوشه فعلی / ~/SaliSurf-X-src / استخراج ZIP از Download)
#   ۲) انتخاب روش دیپلوی:
#        --git  (پیش‌فرض)  force-push به ریپوی متصل به سرویس Runflare؛
#                          «دریافت خودکار» رانفلر خودش بیلد می‌کند
#        --cli             runflare login + runflare deploy -y (اگر CLI نصب باشد)
#   ۳) push فقط وقتی موفق است ادامه می‌یابد — هر خطا فوراً قطع می‌شود
#   ۴) زیر نظر گرفتن سلامت سرویس روی دامنه‌ی رانفلر با تشخیص دقیق:
#        • پاسخ JSON سالم           → موفق
#        • صفحه placeholder رانفلر  → تشخیص و راه‌حل (Revert / پورت 8000 / Dockerfile ریشه)
#        • قطع اتصال               → پورت/سرویس
#   ۵) چاپ endpointهای نهایی
#
# اجرا (از هرجای ترموکس — اسکریپت خودش پروژه را پیدا می‌کند):
#   bash scripts/salisurf-x-runflare.sh --git
#   bash ~/SaliSurf-X-src/scripts/salisurf-x-runflare.sh --git
#
# پرچم‌ها:
#   --git | --cli        روش دیپلوی (پیش‌فرض: git)
#   --repo NAME          ریپوی مقصد (پیش‌فرض: SaliSubSurfX)
#   --domain URL         دامنه سرویس رانفلر
#   --polls N           تعداد تلاش سلامت (پیش‌فرض: 60 روش git، 45 روش cli)
#   -y | --yes          بدون پرسش — همه پیش‌فرض‌ها
#   -h | --help         همین راهنما
#
# English: one-shot Runflare backend deploy from Termux. Requires git + gh
# (authenticated) for --git mode, or the `runflare` CLI for --cli mode.
# =============================================================================

set -euo pipefail

# --- ثابت‌ها -----------------------------------------------------------------
REPO_NAME_DEFAULT="SaliSubSurfX"
DOMAIN_DEFAULT="https://salisurf-x-apz-salisalvia.runflare.cloud"
WORK_DIR_DEFAULT="$HOME/SaliSurf-X-src"
BRANCH="main"
POLL_SLEEP=10
ASSUME_YES=0
MODE="git"
N_POLLS_GIT=60
N_POLLS_CLI=45

usage() {
    sed -n '2,31p' "$0" | sed 's/^# \{0,1\}//'
    exit 0
}

# --- رنگ‌ها -------------------------------------------------------------------
if [ -t 1 ]; then
    B=$'\033[1m'; C=$'\033[1;36m'; G=$'\033[1;32m'; Y=$'\033[1;33m'; Rd=$'\033[1;31m'; N=$'\033[0m'
else
    B=''; C=''; G=''; Y=''; Rd=''; N=''
fi
banner() { printf '\n%s== %s ==%s\n' "$C" "$*" "$N"; }
info()   { printf '%s%s%s\n' "$G" "$*" "$N"; }
warn()   { printf '%s%s%s\n' "$Y" "$*" "$N"; }
die()    { printf '%s[!] %s%s\n' "$Rd" "$*" "$N" >&2; exit 1; }

TMPFILES=""
cleanup() { [ -n "$TMPFILES" ] && rm -f $TMPFILES 2>/dev/null || true; }
trap cleanup EXIT
tmpname() { local f; f="$(mktemp)"; TMPFILES="$TMPFILES $f"; printf '%s' "$f"; }

# --- پرسش‌های تعاملی -----------------------------------------------------------
# قرارداد: ask VAR "متن پرسش" "پیش‌فرض"   (اول نام متغیر، بعد متن!)
# گارد زیر تضمین می‌کند اشتباه ترتیب آرگومان هرگز به «invalid variable name»
# نرسد (باگ نسخه قبل: متن فارسی به جای نام متغیر به printf -v می‌رسید).
ask() {
    local __var=$1 __prompt=$2 __def=${3:-} __ans=""
    case "$__var" in
        [A-Za-z_]*) ;;
        *) die "باگ داخلی: ask() نام متغیر نامعتبر '$__var' — ترتیب آرگومان‌ها VAR \"prompt\" \"default\" است." ;;
    esac
    case "$__var" in
        *[!A-Za-z0-9_]*) die "باگ داخلی: ask() نام متغیر نامعتبر '$__var'." ;;
    esac
    if [ "$ASSUME_YES" -eq 1 ]; then
        printf -v "$__var" '%s' "$__def"
        return 0
    fi
    read -r -e -i "$__def" -p "$(printf '%s%s%s' "$B" "$__prompt" "$N")" __ans || true
    [ -z "$__ans" ] && __ans=$__def
    printf -v "$__var" '%s' "$__ans"
}

ask_yes() {
    local __prompt=$1 __def=${2:-n} __ans=""
    if [ "$ASSUME_YES" -eq 1 ]; then
        case "$__def" in y|yes) return 0 ;; *) return 1 ;; esac
    fi
    while :; do
        read -r -p "$(printf '%s%s [y/N]: %s' "$B" "$__prompt" "$N")" __ans || true
        __ans=$(printf '%s' "$__ans" | tr '[:upper:]' '[:lower:]')
        [ -z "$__ans" ] && __ans=$__def
        case "$__ans" in y|yes) return 0 ;; n|no) return 1 ;; *) warn "فقط y یا n." ;; esac
    done
}

# --- پارس پرچم‌ها -----------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --git)   MODE="git" ;;
        --cli)   MODE="cli" ;;
        --repo)  [ $# -ge 2 ] || die "--repo نیازمند مقدار است"; REPO_NAME_DEFAULT="$2"; shift ;;
        --domain)[ $# -ge 2 ] || die "--domain نیازمند مقدار است"; DOMAIN_DEFAULT="$2"; shift ;;
        --polls) [ $# -ge 2 ] || die "--polls نیازمند مقدار است"; N_POLLS_GIT="$2"; N_POLLS_CLI="$2"; shift ;;
        -y|--yes) ASSUME_YES=1 ;;
        -h|--help) usage ;;
        *) warn "پرچم ناشناخته: $1 (نادیده گرفته شد)" ;;
    esac
    shift
done

banner "SaliSurf-X — دیپلوی Runflare (روش: $MODE)"
echo "ترتیب: پروژه ← ریپو ← push/دیپلوی ← سلامت ← endpointها"
echo

# --- ۱/۴ پیدا کردن پروژه ----------------------------------------------------------
banner "1/4 سورس پروژه"
IN_TERMUX=0
command -v termux-info >/dev/null 2>&1 && IN_TERMUX=1
[ -d "/data/data/com.termux" ] && IN_TERMUX=1

is_project_root() { [ -f "$1/backend/subsurface_api/main.py" ] && [ -f "$1/android/app/build.gradle.kts" ]; }

SRC_DIR=""
if is_project_root "$PWD"; then
    SRC_DIR="$PWD"
    info "پوشه فعلی خود پروژه است ✔ ($SRC_DIR)"
else
    # جست‌وجوی مسیرهای رایج
    for d in "$WORK_DIR_DEFAULT" "$WORK_DIR_DEFAULT"/*/ "$HOME/SaliSurf-X" "$HOME/SaliSurf-X"/*/; do
        if [ -d "$d" ] && is_project_root "${d%/}"; then SRC_DIR="${d%/}"; break; fi
    done
    if [ -n "$SRC_DIR" ]; then
        info "پروژه اینجا پیدا شد: $SRC_DIR"
        cd "$SRC_DIR"
    else
        # استخراج از جدیدترین ZIP پوشه Download
        DL_DIR=""
        for d in "$HOME/storage/downloads" "$HOME/Downloads" "$HOME/downloads"; do
            [ -d "$d" ] && DL_DIR="$d" && break
        done
        if [ -z "$DL_DIR" ] && [ "$IN_TERMUX" -eq 1 ] && command -v termux-setup-storage >/dev/null 2>&1; then
            warn "دسترسی حافظه گوشی داده نشده — الان اجازه می‌خواهیم («Allow» را بزنید)…"
            termux-setup-storage || true
            [ -d "$HOME/storage/downloads" ] && DL_DIR="$HOME/storage/downloads"
        fi
        [ -z "$DL_DIR" ] && die "پوشه Download پیدا نشد — termux-setup-storage را اجرا کنید، یا در پوشه‌ی ریشه‌ی پروژه بایستید و دوباره اجرا کنید."
        mapfile -t CANDS < <(ls -t "$DL_DIR"/SaliSurf-X*.zip "$DL_DIR"/SaliSurf-X-*.zip 2>/dev/null || true)
        ZIP_PATH=""
        if [ "${#CANDS[@]}" -ge 1 ]; then
            if [ "${#CANDS[@]}" -gt 1 ]; then
                echo "این ZIPها پیدا شد (جدیدی‌ها اول):"
                i=1; for f in "${CANDS[@]}"; do printf '  %d) %s\n' "$i" "$(basename "$f")"; i=$((i+1)); done
                ask PICK "کدام؟ [شماره] " "1"
                case "$PICK" in ''|*[!0-9]*) PICK=1 ;; esac
                if [ "$PICK" -lt 1 ] 2>/dev/null; then PICK=1; fi
                if [ "$PICK" -gt "${#CANDS[@]}" ]; then PICK=1; fi
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
        command -v unzip >/dev/null 2>&1 || die "unzip لازم است: pkg install -y unzip"
        unzip -q -o "$ZIP_PATH" -d "$WORK_DIR"
        if ! is_project_root "$WORK_DIR"; then
            INNER="$(find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type d | head -n1 || true)"
            if [ -n "$INNER" ] && is_project_root "$INNER"; then
                WORK_DIR="$INNER"
            else
                die "ساختار ZIP درست نیست (backend/subsurface_api/main.py پیدا نشد)."
            fi
        fi
        SRC_DIR="$WORK_DIR"
        cd "$SRC_DIR"
    fi
fi
is_project_root "$PWD" || die "ریشه پروژه معتبر نیست (backend/subsurface_api/main.py + android/app/build.gradle.kts لازم است)."

VERSION="$(sed -nE 's/.*versionName = "([^"]+)".*/\1/p' android/app/build.gradle.kts | head -n1 || true)"
[ -z "$VERSION" ] && VERSION="?"
command -v curl >/dev/null 2>&1 || die "curl لازم است: pkg install -y curl"
info "پروژه: SaliSurf-X v$VERSION در $PWD"

# پیش‌شرط دیپلوی گیت: Dockerfile در ریشه (علل صفحه‌ی پیش‌فرض رانفلر)
if [ "$MODE" = "git" ] || [ "$MODE" = "cli" ]; then
    if [ ! -f "Dockerfile" ]; then
        warn "Dockerfile در ریشه پروژه نیست — بدون آن رانفلر صفحه پیش‌فرض می‌سازد!"
        [ -f "backend/Dockerfile" ] || die "هیچ Dockerfileای پیدا نشد."
    fi
fi

# --- ۲/۴ دیپلوی ------------------------------------------------------------------
banner "2/4 دیپلوی ($MODE)"

if [ "$MODE" = "cli" ]; then
    if ! command -v runflare >/dev/null 2>&1; then
        warn "CLI «runflare» نصب نیست — به روش git (gh) سوئیچ می‌کنیم."
        warn "برای نصب CLI بعداً به مستندات رانفلر مراجعه کنید."
        MODE="git"
    fi
fi

if [ "$MODE" = "cli" ]; then
    runflare login || die "ورود رانفلر ناموفق بود (runflare login را دستی اجرا کنید)."
    command -v runflare >/dev/null 2>&1 || die "runflare CLI ناپدید شد."
    if [ -f "Dockerfile" ]; then
        runflare deploy -y || die "دیپلوی CLI ناموفق بود — خروجی بالا را ببینید."
    else
        ( cd backend && runflare deploy -y ) || die "دیپلوی CLI ناموفق بود — خروجی بالا را ببینید."
    fi
    N_POLLS="$N_POLLS_CLI"
else
    # ---------- روش git ----------
    for c in git gh; do command -v "$c" >/dev/null 2>&1 || die "$c لازم است: pkg install -y $c"; done
    gh auth status >/dev/null 2>&1 || { warn "gh وارد نشده — ابتدا: gh auth login"; exit 1; }
    GH_USER="$(gh api user --jq .login 2>/dev/null || true)"
    [ -z "$GH_USER" ] && die "نام کاربری GitHub خوانده نشد."
    info "GitHub: @$GH_USER"

    ask REPO_NAME "نام ریپوی مقصد (متصل به سرویس رانفلر): " "$REPO_NAME_DEFAULT"
    while ! printf '%s' "$REPO_NAME" | grep -Eq '^[A-Za-z0-9_.-]+$' || [ -z "$REPO_NAME" ]; do
        warn "نام فقط حرف/رقم/نقطه/خط‌تیره."
        ask REPO_NAME "نام ریپوی مقصد: " "$REPO_NAME_DEFAULT"
    done
    REPO="$GH_USER/$REPO_NAME"
    info "ریپوی مقصد: $REPO"

    if ! gh repo view "$REPO" >/dev/null 2>&1; then
        warn "ریپوی $REPO وجود ندارد."
        if ask_yes "همین حالا به‌صورت private ساخته شود؟ (بعد در پنل رانفلر به سرویس وصلش کنید)" "y"; then
            gh repo create "$REPO_NAME" --private \
                --description "SaliSurf-X backend (Runflare-connected)" \
                || die "ساخت ریپو ناموفق بود."
            info "ساخته شد: https://github.com/$REPO"
        else
            die "بدون ریپو نمی‌توان push کرد — ابتدا در پنل رانفلر سرویس را به این ریپو وصل کنید."
        fi
    fi

    # مخزن محلی
    if [ ! -d ".git" ]; then
        git init -b "$BRANCH" >/dev/null 2>&1 || { git init >/dev/null && git checkout -b "$BRANCH"; }
        info "مخزن محلی ساخته شد (شاخه $BRANCH)."
    fi
    CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [ "$CUR_BRANCH" != "$BRANCH" ] && [ "$CUR_BRANCH" != "HEAD" ]; then
        git branch -M "$BRANCH" 2>/dev/null || true
    fi
    GIT_NAME="$(git config user.name 2>/dev/null || true)"
    GIT_MAIL="$(git config user.email 2>/dev/null || true)"
    if [ -z "$GIT_NAME" ] || [ -z "$GIT_MAIL" ]; then
        ask GIT_NAME "git user.name: " "${GIT_NAME:-$GH_USER}"
        ask GIT_MAIL "git user.email: " "${GIT_MAIL:-$GH_USER@users.noreply.github.com}"
        git config user.name  "$GIT_NAME"
        git config user.email "$GIT_MAIL"
    fi
    git config credential.helper '!gh auth git-credential'

    # commit هر چیزی که جدید است
    if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
        # نبود local.properties در کامیت (اطلاعات حساس لوکال)
        if git status --porcelain | grep -q "local.properties"; then
            git rm --cached -r --quiet "$(git status --porcelain | grep "local.properties" | awk '{print $2}')" 2>/dev/null || true
            warn "local.properties از کامیت حذف شد (باید gitignore باشد)."
        fi
        git add -A
        git commit -q -m "SaliSurf-X v$VERSION — runflare deploy ($(date +%Y-%m-%d))" \
            || info "چیزی برای commit نبود."
    else
        info "درخت پاک است — چیزی برای commit نیست."
    fi

    if [ ! -f "Dockerfile" ]; then
        die "توقف: Dockerfile ریشه موجود نیست؛ رانفلر بدون آن فقط صفحه پیش‌فرض می‌سازد. ZIP تازه پروژه را بگیرید."
    fi

    git remote remove origin 2>/dev/null || true
    git remote add origin "https://github.com/$REPO.git"

    echo
    echo "این push کل شاخه $BRANCH را روی $REPO بازنویسی می‌کند (force)."
    echo "اگر سرویس رانفلر به این ریپو وصل باشد و «دریافت خودکار» روشن باشد، بیلد شروع می‌شود."
    if ask_yes "ادامه؟" "y"; then
        ERRF="$(tmpname)"
        git push --force -u origin "$BRANCH" 2>"$ERRF" \
            || die "push ناموفق بود: $(head -n3 "$ERRF")"
        info "push شد."

        # تأیید اینکه کامیت واقعاً روی GitHub نشسته
        LOCAL_SHA="$(git rev-parse HEAD)"
        REMOTE_SHA=""
        for _ in 1 2 3 4 5; do
            REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" 2>/dev/null | awk '{print $1}' || true)"
            [ -n "$REMOTE_SHA" ] && break
            sleep 3
        done
        if [ -z "$REMOTE_SHA" ]; then
            die "نشستن کامیت روی GitHub تأیید نشد — دستی بررسی کنید: git ls-remote origin $BRANCH"
        fi
        if [ "$REMOTE_SHA" != "$LOCAL_SHA" ]; then
            die "شاخه remote با کامیت محلی فرق دارد ($REMOTE_SHA ≠ $LOCAL_SHA) — دیپلوی کهنه build می‌شود؛ دوباره push کنید."
        fi
        info "کامیت $BRANCH روی GitHub تأیید شد (${LOCAL_SHA:0:7}) ✔"
        echo "اگر «دریافت خودکار» رانفلر روشن باشد بیلد همین حالا شروع شده؛"
        echo "در غیر این صورت در پنل رانفلر دکمه Deploy/Redeploy جلوی کامیت را بزنید."
    else
        die "push لغو شد."
    fi
    N_POLLS="$N_POLLS_GIT"
fi

# --- ۳/۴ سلامت سرویس ---------------------------------------------------------------
banner "3/4 سلامت سرویس"
ask DOMAIN "دامنه سرویس رانفلر: " "$DOMAIN_DEFAULT"
DOMAIN="${DOMAIN%%/}"   # حذف / انتهایی
URL="$DOMAIN/api/v1/health"
info "بررسی: $URL"

BODYF="$(tmpname)"
HDRF="$(tmpname)"
printf 'در انتظار پاسخ سالم (هر تلاش %d ثانیه)…\n' "$POLL_SLEEP"

PLACEHOLDER_SEEN=0
CONN_FAIL_SEEN=0
OK=0
i=1
while [ "$i" -le "$N_POLLS" ]; do
    CODE="$(curl -sL --max-time 20 -o "$BODYF" -D "$HDRF" -w '%{http_code}' "$URL" 2>/dev/null || true)"
    BODY="$(head -c 400 "$BODYF" 2>/dev/null || true)"
    if [ "$CODE" = "200" ] && printf '%s' "$BODY" | grep -q '"status"'; then
        OK=1
        printf '\r%s[%d/%d] سالم ✔%s\n' "$G" "$i" "$N_POLLS" "$N"
        break
    fi
    CT="$(grep -i '^content-type:' "$HDRF" 2>/dev/null | tail -n1 | tr -d '\r' || true)"
    IS_HTML=0
    printf '%s' "$CT" | grep -qi 'text/html' && IS_HTML=1
    printf '%s' "$BODY" | grep -qi '<html' && IS_HTML=1
    if printf '%s' "$BODY$CT" | grep -qi 'runflare'; then
        PLACEHOLDER_SEEN=$((PLACEHOLDER_SEEN+1))
        printf '\r%s[%d/%d] صفحهٔ پیش‌فرض رانفلر (بیلد هنوز ننشسته)%s\n' "$Y" "$i" "$N_POLLS" "$N"
    elif [ "$CODE" = "000" ] || [ -z "$CODE" ]; then
        CONN_FAIL_SEEN=$((CONN_FAIL_SEEN+1))
        printf '\r%s[%d/%d] اتصال برقرار نشد (کد %s)%s\n' "$Y" "$i" "$N_POLLS" "${CODE:-—}" "$N"
    elif [ "$IS_HTML" -eq 1 ]; then
        printf '\r%s[%d/%d] پاسخ HTML به‌جای API (کد %s)%s\n' "$Y" "$i" "$N_POLLS" "$CODE" "$N"
    else
        printf '\r%s[%d/%d] هنوز آماده نیست (کد %s)%s\n' "$Y" "$i" "$N_POLLS" "${CODE:-—}" "$N"
    fi
    i=$((i+1))
    [ "$i" -le "$N_POLLS" ] && sleep "$POLL_SLEEP"
done

if [ "$OK" -ne 1 ]; then
    echo
    warn "پس از $N_POLLS تلاش پاسخ سالم نیامد."
    if [ "$PLACEHOLDER_SEEN" -gt 0 ]; then
        echo "علت: دامنه «صفحهٔ پیش‌فرض رانفلر» نشان می‌دهد — پاد فعال است ولی اپ build نشده. چک‌لیست:"
        echo "  ۱) Dockerfile در ریشه ریپو هست؟ (این نسخه دارد: $([ -f Dockerfile ] && echo بله || echo نه!))"
        echo "  ۲) در پنل رانفلر جلوی آخرین کامیت دکمه Revert/Redeploy را بزنید و ۲–۳ دقیقه صبر کنید."
        echo "  ۳) پورت Expose سرویس = 8000 باشد."
        echo "  ۴) toggle «دریافت خودکار» روشن باشد تا push باعث بیلد شود."
    elif [ "$CONN_FAIL_SEEN" -gt 0 ]; then
        echo "علت: اتصال به دامنه برقرار نمی‌شود. چک‌لیست:"
        echo "  ۱) دامنه درست است؟ ($DOMAIN)"
        echo "  ۲) سرویس در پنل رانفلر Running است؟"
        echo "  ۳) پورت Expose سرویس = 8000 باشد."
    else
        echo "پاسخ می‌آید اما JSON سلامت نیست. چک‌لیست:"
        echo "  ۱) لاگ پاد در پنل رانفلر را ببینید (اگر crash loop است، حافظه/پورت را چک کنید)."
        echo "  ۲) پورت Expose = 8000 و مسیر /api/v1/health در لاگ 404 نیست؟"
    fi
    echo
    echo "نمونه پاسخ فعلی (۴۰۰ کاراکتر اول):"
    printf '%s\n' "$(head -c 400 "$BODYF" 2>/dev/null | tr -d '\0' || true)"
    die "دیپلوی کامل نشد — موارد بالا را اصلاح و دوباره اجرا کنید (فقط مرحله سلامت دوباره چک می‌شود)."
fi

READY_CODE="$(curl -sL --max-time 20 -o /dev/null -w '%{http_code}' "$DOMAIN/api/v1/ready" 2>/dev/null || true)"
info "بررسی آمادگی کامل (/api/v1/ready): ${READY_CODE:-—}"

# --- ۴/۴ جمع‌بندی --------------------------------------------------------------------
banner "4/4 تمام شد"
echo "سلامت:    $URL"
echo "آمادگی:   $DOMAIN/api/v1/ready"
echo "مستندات:  $DOMAIN/docs"
echo "کنسول:    $DOMAIN/deep-console"
echo
if [ "$MODE" = "git" ]; then
    echo "هر تغییر بعدی: کامیت بگیرید و این اسکریپت را دوباره اجرا کنید —"
    echo "push به ریپو، دیپلوی خودکار رانفلر را دوباره راه می‌اندازد."
fi
echo
echo "یادآوری: برای پردازش عمیق CDSE، متغیرهای COPERNICUS_CLIENT_ID و"
echo "COPERNICUS_CLIENT_SECRET را در پنل رانفلر (Environment) تنظیم کنید."
