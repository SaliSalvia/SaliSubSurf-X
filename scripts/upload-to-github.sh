#!/usr/bin/env bash
# =============================================================================
# SaliSurf-X — آپلود پروژه به یک ریپوی خالی جدید GitHub (Termux / Linux)
# Preserves hidden files (.github/workflows) that the GitHub web uploader drops.
#
# Usage (from the extracted repository root):
#   bash scripts/upload-to-github.sh https://github.com/USER/REPO.git [branch]
#
# With a personal access token (recommended in Termux):
#   bash scripts/upload-to-github.sh https://<TOKEN>@github.com/USER/REPO.git
# Token: GitHub → Settings → Developer settings → Personal access tokens →
#        "Generate new token (classic)" → scope: repo
#
# نکته: برای مسیر کامل خودکار (ساخت ریپو + امضای تعاملی + ریلیز + دانلود APK)
# اسکریپت salisurf-x-deploy.sh را اجرا کنید.
# =============================================================================
set -euo pipefail

REMOTE="${1:?Usage: upload-to-github.sh https://github.com/USER/REPO.git [branch]}"
BRANCH="${2:-main}"

banner() { printf '\n\033[1;36m== %s ==\033[0m\n' "$1"; }

banner "0/3 ابزارها"
if ! command -v git >/dev/null 2>&1; then
  echo "git not found → installing …"
  pkg install -y git 2>/dev/null || sudo apt-get install -y git
fi

if [ ! -d .git ]; then
  banner "1/3 مقداردهی مخزن محلی"
  git init -b "$BRANCH" 2>/dev/null || { git init && git checkout -b "$BRANCH"; }
  git config user.name  >/dev/null 2>&1 || git config --global user.name  "Sal Dev"
  git config user.email >/dev/null 2>&1 || git config --global user.email "sal@example.invalid"
  VERSION="$(sed -nE 's/.*versionName = "([^"]+)".*/\1/p' android/app/build.gradle.kts | head -n1)"
  [ -z "$VERSION" ] && VERSION="x.y.z"
  git add -A
  git commit -m "SaliSurf-X v$VERSION (app + API + CI)" -q
else
  banner "1/3 مخزن محلی از قبل موجود است"
  git add -A
  git commit -m "Update SaliSurf-X" -q || echo "(چیزی برای commit نبود)"
fi

banner "2/3 اتصال ریموت و push"
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE"
git push -u origin "$BRANCH"

banner "3/3 تمام شد ✔"
echo "حالا در گیت‌هاب: تب Actions ریپو → ورک‌فلو «Android APK» به‌صورت خودکار اجرا می‌شود."
echo "پس از چند دقیقه، خروجی‌ها:"
echo "    SaliSurf-X-debug.apk            (همیشه، در Artifacts)"
echo "    SaliSurf-X-release-signed.apk   (اگر Secrets امضا را تنظیم کرده باشید)"
echo "    push به main خودکار یک GitHub Release (vX.Y.Z) با همان APKها می‌سازد."
echo "امضای APK: ریپو → Settings → Secrets and variables → Actions →"
echo "    KEYSTORE_BASE64 / KEYSTORE_PASSWORD / KEY_ALIAS / KEY_PASSWORD"
echo "(راه خودکار تعاملی: bash scripts/termux-sign.sh)"
