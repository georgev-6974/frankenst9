#!/usr/bin/env python3
"""Offline check of apply-star2lte.py without the XNU tree.

Rebuilds, per file, the text visible in patch 0124 (context + added lines of
every hunk, hunks joined by a marker line), runs apply-star2lte.py on that
pseudo tree and preprocesses the resulting A5XELTE.h. It proves the anchors
match and the macros resolve; it does NOT prove the kernel builds.
Usage: verify-apply.py [workdir]
"""
import re, subprocess, sys, tempfile
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
patch = (repo / 'xnu/patches/0124-dreamlte-s8.patch').read_text().split('\n')
work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix='s9tree-'))

files, cur = {}, None
for line in patch:
    m = re.match(r'diff --git (\S+) ', line)
    if m:
        cur = m.group(1); files.setdefault(cur, []); continue
    if cur is None or line.startswith(('index ', '--- ', '+++ ', 'new file')):
        continue
    if line.startswith('@@'):
        files[cur].append('/* ---- hunk ---- */'); continue
    if line[:1] in (' ', '+'):
        files[cur].append(line[1:])
for rel, lines in files.items():
    p = work / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('\n'.join(lines) + '\n')
print(f'pseudo tree: {work} ({len(files)} files)')

subprocess.run([sys.executable, str(repo / 'tools/star2lte/apply-star2lte.py'), str(work)], check=True)

# Preprocess the header with and without the new block's effects.
hdr = work / 'pexpert/pexpert/arm64/A5XELTE.h'
probe = work / 'probe.c'
probe.write_text(
    '#include "pexpert/pexpert/arm64/A5XELTE.h"\n'
    'MARK A5_ENTRY_MARKER_PHYS A5_BOOT_MPIDR A5_KEYS_DEFAULT A5_TOUCH_DEFAULT '
    'A5_FB_PHYS A5_FB_STRIDE A5XELTE_VTIMER_INTID A5_USE_PHYS_TIMER STAR2LTE\n')
out = subprocess.run(['cc', '-E', '-P', '-I', str(work), str(probe)],
                     capture_output=True, text=True)
line = [l for l in out.stdout.splitlines() if l.startswith('MARK')]
print(line[0] if line else out.stderr[:600])
