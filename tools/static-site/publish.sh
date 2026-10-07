#!/usr/bin/env bash
set -euo pipefail
repo="$(cd "$(dirname "$0")/../.." && pwd)"
out="$(mktemp -d)"
uv="${UV:-$HOME/.local/bin/uv.exe}"
(cd "$repo/backend" && "$uv" run python ../tools/static-site/build.py --out "$out")
remote="$(git -C "$repo" remote get-url origin)"
cd "$out"
git init -q -b gh-pages
git add -A
git commit -q -m "docs(site): publish static snapshot of the Maule public pages"
git push -q --force "$remote" gh-pages
echo "published $out to gh-pages"
