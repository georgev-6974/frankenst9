#!/usr/bin/env python3
# fix-ci-kdk.py [WORKFLOW]   (default .github/workflows/xnu.yml)
# 1. Adds a step before "- name: Build" that installs KDK 13.5 (22G74) with an
#    authenticated `gh release download` (dortania/KdkSupportPkg, tag = build id),
#    validated, with retries. build.sh skips its own download when the .kdk dir exists.
# 2. Makes the "Inspect closed KDK support libs" loop skip when the glob matches nothing
#    (that literal "lib*.members.txt" broke artifact upload).
# UNTESTED: written from the xnu.yml lines seen in chat (95-125, plus grep output).
import re, sys, pathlib

p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".github/workflows/xnu.yml")
s = p.read_text()

if "Install KDK (authenticated)" in s:
    sys.exit("already patched")

# --- 1. KDK install step, before the Build step ---
pat = re.compile(r"^([ \t]*)- name: Build[ \t]*\n", re.M)
m = pat.findall(s)
if len(m) != 1:
    sys.exit("expected exactly one '- name: Build' step, found %d" % len(m))

def step(mm):
    i = mm.group(1)
    body = """- name: Install KDK (authenticated)
  env:
    GH_TOKEN: ${{ github.token }}
  run: |
    set -eu
    KDK_DIR=/Library/Developer/KDKs/KDK_13.5_22G74.kdk
    if [ -d "$KDK_DIR" ]; then echo "KDK already installed"; exit 0; fi
    ok=0
    for try in 1 2 3 4; do
      rm -f /tmp/KDK.dmg
      mkdir -p /tmp/kdkdl && rm -f /tmp/kdkdl/*
      if gh release download 22G74 --repo dortania/KdkSupportPkg --pattern '*.dmg' --dir /tmp/kdkdl; then
        f=$(ls /tmp/kdkdl/*.dmg | head -n 1)
        sz=$(stat -f%z "$f")
        echo "try $try: $f $sz bytes"
        if [ "$sz" -gt 100000000 ] && hdiutil imageinfo "$f" >/dev/null 2>&1; then
          mv "$f" /tmp/KDK.dmg; ok=1; break
        fi
      fi
      echo "try $try failed, retrying"; sleep 30
    done
    [ "$ok" = 1 ] || { echo "KDK download failed"; exit 1; }
    hdiutil attach /tmp/KDK.dmg
    sudo mkdir -p /Library/Developer/KDKs
    sudo installer -pkg '/Volumes/Kernel Debug Kit/KernelDebugKit.pkg' -target /
    hdiutil detach '/Volumes/Kernel Debug Kit'
    ls -lah /Library/Developer/KDKs
"""
    lines = body.splitlines()
    return "".join((i + l + "\n") if l else "\n" for l in lines) + "\n" + mm.group(0)

s = pat.sub(step, s, count=1)

# --- 2. kdk-libs glob guard ---
pat2 = re.compile(r"^([ \t]*)(for lib in /Library/Developer/KDKs/\*/System/Library/KernelSupport/lib\*\.a; do)[ \t]*\n", re.M)
m2 = pat2.findall(s)
if len(m2) != 1:
    sys.exit("expected exactly one kdk-libs for-loop, found %d" % len(m2))
s = pat2.sub(lambda mm: mm.group(0) + mm.group(1) + '  [ -f "$lib" ] || continue\n', s, count=1)

p.write_text(s)
print("patched", p)
