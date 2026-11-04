#!/bin/bash
# Pinned, portable constant-time AES for the SWEET legacy CBC/ECB API.
set -euo pipefail
case "${MACHINE_CONFIG:-}" in SWEET|A5XELTE) ;; *) exit 0 ;; esac
[[ -f libkern/crypto/corecrypto_aes.c ]] || exit 1
bearssl_sha=7bea48e5e850ab4cafbe68d3765cdaba13a86d6f
bearssl_tmp=$(mktemp -d)
trap 'rm -rf "$bearssl_tmp"' EXIT
# Preferred source: a copy of the pinned commit committed to this repo
# (xnu/patches/bearssl-<sha>.tar.gz = `git archive` of inc/ src/ LICENSE.txt),
# because www.bearssl.org returned HTTP 502 for minutes in CI on 2026-11-04 and
# the GitHub mirrors do not carry this commit. See STAR2LTE_PROGRESS.md.
vendor_dir="${GITHUB_WORKSPACE:-/nonexistent}/xnu/patches"
vendored=
for f in "$vendor_dir/bearssl-$bearssl_sha.tar.gz" "$vendor_dir"/bearssl-*.tar.gz \
    "$vendor_dir"/bearssl-*.tar.xz "$vendor_dir"/bearssl-*.tgz; do
    if [[ -f "$f" ]]; then vendored=$f; break; fi
done
bearssl_src=$bearssl_tmp
if [[ -n "$vendored" ]]; then
    # Any layout works: `git archive` (inc/ src/ at top), a gitweb snapshot or a
    # release/Debian tarball (one top directory holding inc/ and src/).
    tar -xf "$vendored" -C "$bearssl_tmp"
    if [[ ! -d "$bearssl_tmp/inc" ]]; then
        bearssl_src=$(find "$bearssl_tmp" -mindepth 2 -maxdepth 2 -type d -name inc -printf '%h\n' | head -1)
        [[ -n "$bearssl_src" && -d "$bearssl_src/src" ]] || { echo "vendored $vendored has no inc/ + src/" >&2; exit 1; }
    fi
    [[ "$vendored" == *"$bearssl_sha"* ]] || echo "WARNING: vendored BearSSL is not the pinned commit $bearssl_sha: $vendored" >&2
    echo "Using vendored BearSSL $vendored"
else
    git init -q "$bearssl_tmp"
    fetched=0
    for attempt in 1 2 3; do
        for url in https://www.bearssl.org/git/BearSSL \
            https://github.com/nickray/bearssl https://github.com/tarigo/BearSSL; do
            if git -C "$bearssl_tmp" fetch -q --depth 1 "$url" "$bearssl_sha"; then
                fetched=1
                break 2
            fi
            echo "BearSSL fetch failed from $url (attempt $attempt)" >&2
        done
        sleep $((attempt * 15))
    done
    [[ $fetched = 1 ]] || { echo "could not fetch BearSSL $bearssl_sha" >&2; exit 1; }
    git -C "$bearssl_tmp" checkout -q FETCH_HEAD
    [[ "$(git -C "$bearssl_tmp" rev-parse HEAD)" == "$bearssl_sha" ]]
fi
python3 - "$bearssl_src" <<'PY'
from pathlib import Path
import shutil
import sys

source = Path(sys.argv[1])
target = Path('libkern/crypto/sweet_bearssl')
if target.exists():
    raise SystemExit(f'refusing to overwrite existing AES source: {target}')
shutil.copytree(source / 'inc', target / 'inc')
(target / 'src/symcipher').mkdir(parents=True)
for file in ('inner.h', 'config.h'):
    shutil.copy2(source / 'src' / file, target / 'src' / file)
# XNU exports machine/limits.h instead of the userspace limits.h.
header = target / 'src/inner.h'
text = header.read_text()
assert text.count('#include <limits.h>') == 1
header.write_text(text.replace('#include <limits.h>',
    '#if defined(KERNEL)\n#include <machine/limits.h>\n'
    '#else\n#include <limits.h>\n#endif'))
for name in ('aes_ct', 'aes_ct_enc', 'aes_ct_dec', 'aes_ct_cbcenc', 'aes_ct_cbcdec'):
    shutil.copy2(source / 'src/symcipher' / (name + '.c'),
                 target / 'src/symcipher' / (name + '.c'))
# MD5, SHA-1 and SHA-384/512 for the legacy hash APIs, with their codecs.
for name in ('hash/md5.c', 'codec/dec32le.c', 'codec/enc32le.c',
             'hash/sha1.c', 'codec/dec32be.c', 'codec/enc32be.c',
             'hash/sha2big.c', 'codec/dec64be.c', 'codec/enc64be.c'):
    (target / 'src' / name).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / 'src' / name, target / 'src' / name)
shutil.copy2(source / 'LICENSE.txt', target / 'LICENSE.txt')
PY
echo "Staged BearSSL portable AES, MD5, SHA-1 and SHA-384/512 (source: ${vendored:-git $bearssl_sha}) for SWEET"
