#!/bin/bash
# Turn apply-star2lte.py into xnu/patches/0125-star2lte.patch.
# Needs a tree where patches 0001-0124 are already applied:
#   tools/dreamlte/prep-xnu-tree.sh xnu/patches WORK   ->  WORK/xnu
#   tools/star2lte/export-0125.sh WORK/xnu xnu/patches
# Fails (and writes nothing) if an anchor misses or the result does not
# re-apply with plain `git apply` on the pre-0125 tree, which is what CI does.
set -euo pipefail
tree=$(realpath "$1"); out=$(realpath "$2")
here=$(dirname "$(realpath "$0")")
cd "$tree"
git diff --quiet && git diff --cached --quiet || { echo "tree has uncommitted changes; use a fresh prep-xnu-tree.sh output" >&2; exit 1; }
python3 "$here/apply-star2lte.py" .
git diff --no-color --no-prefix | sed -e 's#^--- \([^/]\)#--- a/\1#' -e 's#^+++ \([^/]\)#+++ b/\1#' > /tmp/0125.patch
[ -s /tmp/0125.patch ] || { echo "empty diff" >&2; exit 1; }
git checkout -q -- .
git apply --check /tmp/0125.patch || { echo "0125 does not git-apply on the 0124 tree" >&2; exit 1; }
cp /tmp/0125.patch "$out/0125-star2lte.patch"
echo "wrote $out/0125-star2lte.patch ($(grep -c '^@@' /tmp/0125.patch) hunks, $(grep -c '^diff' /tmp/0125.patch) files)"
