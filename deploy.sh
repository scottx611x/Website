#!/usr/bin/env bash
#
# Deploy the site to AWS Lambda via Zappa.
#
# Stamps the current commit into version.txt FIRST — that SHA shows in the
# footer and is folded into the cache key (css/js ?v= + page ETag), so every
# deploy busts stale caches and you can always tell what's live. Skipping this
# step is exactly what leaves the footer/cache stale, so it's baked in here.
#
# Usage:
#   ./deploy.sh          # stamp version + zappa update production
#   ./deploy.sh --push   # ...then also push the current branch to origin
#
set -euo pipefail
cd "$(dirname "$0")"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "⚠  Working tree not clean — deploying uncommitted changes."
    echo "   (version.txt will point at HEAD, which won't include them.)"
fi

git rev-parse --short HEAD > version.txt
echo "→ version.txt = $(cat version.txt)  ($(git log -1 --format=%s))"

# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ zappa update production…"
zappa update production

if [[ "${1:-}" == "--push" ]]; then
    branch="$(git rev-parse --abbrev-ref HEAD)"
    echo "→ pushing $branch to origin…"
    git push origin "$branch"
fi

echo "✓ Live. Footer should read $(cat version.txt)."
